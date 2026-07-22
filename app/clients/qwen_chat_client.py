"""
app.clients.qwen_chat_client —— 百炼 OpenAI-compatible Qwen 聊天客户端。

使用 openai Python SDK 作为 HTTP 客户端调用**百炼**上的 Qwen 模型：
    - api_key  来自 settings.dashscope_api_key；
    - base_url 来自 settings.dashscope_base_url（禁止 fallback 到 OpenAI 官方）；
    - model    由调用方传入，但必须通过 assert_qwen_model 校验。

安全约束：
    - 所有生成模型必须为 Qwen/千问；
    - API 调用失败抛出 QwenClientError，错误信息经脱敏，绝不含完整 Key；
    - 支持 mock 模式：环境变量 MOCK_LLM=true 时返回固定可测试 JSON，
      便于在无网络/无 Key 的情况下运行测试。
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from app.core.config import Settings, assert_qwen_model, get_settings
from app.core.execution_mode import is_mock_mode
from app.core.logging import get_logger, mask_text
from app.core.run_progress import current_progress, emit_progress, friendly_model_name

# 模块级日志器（继承根日志器的脱敏能力）。
logger = get_logger("clients.qwen_chat")


class QwenClientError(Exception):
    """Qwen 聊天调用错误：错误信息在抛出前已脱敏，不含完整 API Key。"""


def _mock_enabled() -> bool:
    """
    判断是否启用 mock 模式（环境变量 MOCK_LLM=true）。

    返回：
        True 表示启用 mock，返回固定 JSON，不发起真实请求。
    """
    # 兼容大小写与常见真值写法。
    return is_mock_mode()


def _supports_json_mode(model: str) -> bool:
    """Return whether the current Model Studio capability table supports JSON Mode."""
    # qwen3.7-max is a reasoning model and is currently not listed as supporting
    # structured output. It still follows the prompt's plain-JSON instruction.
    return not model.lower().startswith("qwen3.7-max")


def _model_alias(settings: Settings, model: str) -> str:
    if model == settings.qwen_fast_model:
        return "fast"
    if model == settings.qwen_balanced_model:
        return "balanced"
    if model == settings.qwen_strong_model:
        return "strong"
    return "unknown"


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in {408, 409, 429, 500, 502, 503, 504}:
        return True
    return type(exc).__name__ in {
        "APITimeoutError", "APIConnectionError", "ConnectError", "ReadTimeout",
        "ConnectTimeout", "RemoteProtocolError",
    }


def _friendly_error(exc: Exception) -> str:
    """Classify common Model Studio failures without leaking secrets or endpoints."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    raw = mask_text(str(exc))
    if status == 401 or name == "AuthenticationError":
        return "百炼鉴权失败（401）：请重新生成或检查当前地域的 API Key。"
    if status == 403 or name == "PermissionDeniedError":
        return "百炼拒绝访问（403）：当前 Workspace/API Key 可能没有该模型权限。"
    if status == 404 or name == "NotFoundError":
        return "百炼模型或端点不存在（404）：请检查地域、Workspace 与模型部署范围。"
    if status == 429 or name == "RateLimitError":
        return "百炼限流或额度不足（429）：请稍后重试并检查额度。"
    if status == 400 or name == "BadRequestError":
        return f"百炼请求参数不兼容（400）：{raw[:260]}"
    if "SSL" in raw.upper() or "TLS" in raw.upper():
        return "无法完成百炼 HTTPS/TLS 握手；请检查本机网络、VPN、防火墙或 HTTPS 代理。"
    if name in {"APITimeoutError", "ReadTimeout", "ConnectTimeout"} or "timed out" in raw.lower():
        return "百炼请求超时；系统已停止继续重试。请检查网络后重试。"
    if name in {"APIConnectionError", "ConnectError", "RemoteProtocolError"} or "Connection error" in raw:
        return "无法连接百炼 HTTPS 服务；请检查网络出口、VPN/防火墙，或配置 OUTBOUND_HTTPS_PROXY。"
    return f"百炼调用失败：{raw[:320]}"


class QwenChatClient:
    """
    Qwen 聊天模型封装（OpenAI-compatible）。

    通过百炼 endpoint 访问 Qwen 模型，提供文本与 JSON 两种返回形态。
    实例化时不强制建立连接；真实请求时才惰性构造底层 openai 客户端。
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        初始化聊天客户端并校验默认模型合规性。

        参数：
            settings: 可选注入配置；缺省使用全局单例。
        """
        # 允许依赖注入以便测试；默认取全局配置。
        self.settings = settings or get_settings()
        # 预校验三档默认聊天模型均为千问（防止 .env 被改坏）。
        for model in (
            self.settings.qwen_fast_model,
            self.settings.qwen_balanced_model,
            self.settings.qwen_strong_model,
        ):
            assert_qwen_model(model)
        # 底层 openai 客户端惰性构造。
        self._client = None
        # 最近一次真实调用的脱敏元数据（request_id / usage），供调用审计读取。
        self.last_request_id: Optional[str] = None
        self.last_usage: dict = {}

    def _build_client(self, timeout_seconds: float | None = None):
        """Create an OpenAI-compatible client with bounded timeouts and optional proxy."""
        try:
            import httpx
            from openai import OpenAI
        except ImportError as exc:
            raise QwenClientError("未安装 openai/httpx SDK，请先 pip install -r requirements.txt。") from exc

        timeout = httpx.Timeout(
            timeout_seconds or self.settings.llm_timeout_seconds,
            connect=min(self.settings.llm_connect_timeout_seconds, timeout_seconds or self.settings.llm_connect_timeout_seconds),
        )
        kwargs = {
            "api_key": self.settings.dashscope_api_key,
            "base_url": self.settings.dashscope_base_url,
            "timeout": timeout,
            # Avoid SDK retry multiplication (120s x 4); retry is classified below.
            "max_retries": 0,
        }
        # 禁用 Windows/环境隐式代理；只使用 .env 中显式配置的代理。
        # 这与 embedding 客户端保持一致，避免本机 loopback 代理截断百炼 TLS。
        http_kwargs = {"timeout": timeout, "trust_env": False}
        if self.settings.outbound_https_proxy:
            http_kwargs["proxy"] = self.settings.outbound_https_proxy
        kwargs["http_client"] = httpx.Client(**http_kwargs)
        return OpenAI(**kwargs)

    def _ensure_client(self):
        """
        惰性构造底层 openai 客户端（指向百炼 base_url）。

        返回：
            已配置 base_url 与 api_key 的 openai.OpenAI 实例。

        异常：
            QwenClientError: 当百炼配置缺失或 openai SDK 不可用时抛出。
        """
        # 已构造则直接复用。
        if self._client is not None:
            return self._client
        # 缺少 Key / base_url 时明确报错，避免静默失败。
        if not self.settings.qwen_configured:
            raise QwenClientError(
                "百炼未配置（DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL）。"
                "请先运行 python scripts/setup_env.py。"
            )
        # 严格使用配置中的百炼 base_url，禁止 fallback 到 OpenAI 官方 endpoint。
        self._client = self._build_client()
        return self._client

    def probe(self, model: str | None = None) -> dict:
        """Run a tiny, zero-retry request so bad network/auth fails within ~20 seconds."""
        model = model or self.settings.qwen_fast_model
        assert_qwen_model(model)
        if _mock_enabled():
            return {"ok": True, "mock": True, "model": model}
        if not self.settings.qwen_configured:
            raise QwenClientError("百炼未配置（DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL）。")
        display = friendly_model_name(_model_alias(self.settings, model), model)
        emit_progress("preflight", status="connecting", percent=4, message=f"正在连接 {display}",
                      model_alias=_model_alias(self.settings, model), model_name_internal=model)
        client = self._build_client(self.settings.qwen_probe_timeout_seconds)
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "仅回复 OK"}],
                max_tokens=8,
                stream=True,
                stream_options={"include_usage": True},
                extra_body={"enable_thinking": False},
            )
            received = False
            for chunk in stream:
                if getattr(chunk, "choices", None):
                    received = True
            if not received:
                raise QwenClientError("百炼连通性探测未返回内容。")
            emit_progress("preflight", status="completed", percent=5, message=f"已连接 {display}",
                          model_alias=_model_alias(self.settings, model), model_name_internal=model)
            return {"ok": True, "mock": False, "model": model}
        except QwenClientError:
            raise
        except Exception as exc:
            raise QwenClientError(_friendly_error(exc)) from None

    def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.2,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        发送一次多轮对话请求并返回模型文本。

        参数：
            messages:        OpenAI 风格消息列表，如 [{"role":"user","content":"..."}]。
            model:           模型名称，必须为 Qwen/千问（经 assert_qwen_model 校验）。
            temperature:     采样温度，默认 0.2（偏确定性）。
            response_format: 可选的响应格式（如 {"type": "json_object"}）。

        返回：
            模型生成的文本内容。

        异常：
            QwenClientError: 模型非千问或 API 调用失败（错误已脱敏）。
        """
        # 强制校验模型为千问，任何非千问模型立即拒绝。
        assert_qwen_model(model)

        # 每次调用先重置最近元数据。
        self.last_request_id = None
        self.last_usage = {}

        # mock 模式：返回固定文本，便于离线测试。
        if _mock_enabled():
            logger.debug("chat 使用 mock 模式返回固定文本：model=%s", model)
            return "【MOCK】这是用于测试的固定回答，不代表真实模型输出。"

        # JSON agents must disable default thinking; JSON Mode and thinking are
        # incompatible in Model Studio. qwen3.7-max is prompt-JSON only.
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.settings.llm_max_output_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "extra_body": {"enable_thinking": False},
        }
        if response_format is not None and _supports_json_mode(model):
            kwargs["response_format"] = response_format

        # Stream output avoids Model Studio's fixed non-streaming timeout and lets
        # the UI show connection/response progress while content is generated.
        client = self._ensure_client()
        alias = _model_alias(self.settings, model)
        display = friendly_model_name(alias, model)
        snapshot = current_progress()
        stage = str(snapshot.get("stage") or "model_call")
        percent = int(snapshot.get("percent") or 0)
        emit_progress(stage, status="waiting", percent=percent, message=f"正在询问 {display}",
                      model_alias=alias, model_name_internal=model)

        for attempt in range(self.settings.llm_max_retries + 1):
            parts: list[str] = []
            first_chunk = False
            try:
                completion = client.chat.completions.create(**kwargs)
                for chunk in completion:
                    self.last_request_id = getattr(chunk, "id", None) or self.last_request_id
                    choices = getattr(chunk, "choices", None) or []
                    if choices:
                        if not first_chunk:
                            first_chunk = True
                            emit_progress(stage, status="running", percent=percent,
                                          message=f"{display} 已连接，正在接收响应",
                                          model_alias=alias, model_name_internal=model)
                        content = getattr(choices[0].delta, "content", None)
                        if content:
                            parts.append(content)
                    usage = getattr(chunk, "usage", None)
                    if usage is not None:
                        self.last_usage = {
                            "input_tokens": getattr(usage, "prompt_tokens", None),
                            "output_tokens": getattr(usage, "completion_tokens", None),
                            "total_tokens": getattr(usage, "total_tokens", None),
                        }
                return "".join(parts)
            except Exception as exc:
                if parts or attempt >= self.settings.llm_max_retries or not _retryable(exc):
                    raise QwenClientError(_friendly_error(exc)) from None
                emit_progress(stage, status="connecting", percent=percent,
                              message=f"{display} 连接波动，正在进行最后一次重试",
                              model_alias=alias, model_name_internal=model)
                time.sleep(min(1.5 * (attempt + 1), 3.0))

    def chat_json(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.1,
    ) -> dict:
        """
        发送对话请求并将模型输出解析为 JSON 字典。

        参数：
            messages:    OpenAI 风格消息列表。
            model:       模型名称，必须为 Qwen/千问。
            temperature: 采样温度，默认 0.1（JSON 更需稳定）。

        返回：
            解析后的字典。

        异常：
            QwenClientError: 模型非千问、API 失败或返回非合法 JSON（错误已脱敏）。
        """
        # 强制校验模型为千问。
        assert_qwen_model(model)

        # mock 模式：返回固定可测试 JSON。
        if _mock_enabled():
            logger.debug("chat_json 使用 mock 模式返回固定 JSON：model=%s", model)
            return {
                "mock": True,
                "hypothesis": "【MOCK】假设占位",
                "evidence": [],
                "note": "MOCK_LLM=true 时的固定输出，仅用于测试。",
            }

        # 请求 JSON 格式输出；qwen3.7-max 会自动退化为 prompt-JSON。
        text = self.chat(
            messages,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        # 解析为字典；失败时抛出脱敏后的错误。
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Tolerate fenced JSON or a short natural-language prefix from models
            # without native JSON Mode, while still rejecting trailing garbage.
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            decoder = json.JSONDecoder()
            start = cleaned.find("{")
            try:
                obj, _end = decoder.raw_decode(cleaned[start:])
                if isinstance(obj, dict):
                    return obj
            except (json.JSONDecodeError, ValueError):
                pass
            raise QwenClientError("千问返回内容不是合法 JSON；已停止本次步骤，未降级为模拟数据。") from None
