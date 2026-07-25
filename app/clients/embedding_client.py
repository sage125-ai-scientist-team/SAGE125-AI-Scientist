"""
app.clients.embedding_client —— 文本向量嵌入客户端。

默认后端 bailian：通过 openai SDK 的 embeddings 接口调用百炼 text-embedding-v4
（OpenAI-compatible endpoint，base_url 来自 settings.dashscope_base_url）。

安全与正确性约束：
    - 调用失败时清晰报错（脱敏），严禁伪造随机向量冒充嵌入结果；
    - EMBEDDING_BACKEND=local_qwen 时抛出 NotImplementedError，并提示本地
      Qwen3-Embedding 为可选增强、非默认功能；
    - 批量处理，避免单次请求过大。
"""

from __future__ import annotations

import re
from typing import Optional

from app.core.config import Settings, assert_qwen_model, get_settings
from app.core.logging import get_logger
from app.clients.outbound_http import build_outbound_httpx_client

# 模块级日志器。
logger = get_logger("clients.embedding")

# 单次请求的默认最大文本条数，避免请求体过大（百炼建议分批）。
_DEFAULT_BATCH_SIZE = 10

# 稳定错误码 -> 面向用户的脱敏、可执行指引。这些文案会穿过
# IndexingService / LibraryManager 到达 UI，因此不得包含原始响应体、URL 查询参数或 Key。
_EMBEDDING_GUIDANCE: dict[str, str] = {
    "EMBEDDING_CONFIG": (
        "百炼嵌入配置不完整或模型配置无效。请在项目 .env 中检查 "
        "DASHSCOPE_API_KEY 和 DASHSCOPE_BASE_URL，然后运行 "
        "`py -3 scripts/smoke_bailian.py --embedding`。"
    ),
    "EMBEDDING_DEPENDENCY": (
        "嵌入客户端依赖缺失。请运行 `py -3 -m pip install -r requirements.txt`，"
        "重启应用后再试。"
    ),
    "EMBEDDING_AUTH": (
        "百炼嵌入认证或权限失败。请确认 Key 未过期、账号已开通 "
        "text-embedding 权限，然后运行 `py -3 scripts/setup_env.py` 和 "
        "`py -3 scripts/smoke_bailian.py --embedding`。不要在前端粘贴 Key。"
    ),
    "EMBEDDING_RATE_LIMIT": (
        "百炼嵌入请求被限流或账户配额不足。请等待后重试、减少本批文件，"
        "并在百炼控制台检查配额/计费状态。"
    ),
    "EMBEDDING_PROXY": (
        "无法通过当前代理连接百炼嵌入服务。请检查 Windows 系统代理；如确需代理，"
        "请只在项目 .env 中配置 OUTBOUND_HTTPS_PROXY，再运行 "
        "`py -3 scripts/smoke_bailian.py --embedding`。"
    ),
    "EMBEDDING_TIMEOUT": (
        "连接百炼嵌入服务超时。请检查网络/代理，稍后重试或减少单次上传，"
        "并运行 `py -3 scripts/smoke_bailian.py --embedding` 验证链路。"
    ),
    "EMBEDDING_NETWORK": (
        "无法连接阿里云百炼嵌入服务。请检查本机网络、DNS、防火墙、"
        "DASHSCOPE_BASE_URL 与代理配置，然后运行 "
        "`py -3 scripts/smoke_bailian.py --embedding`。"
    ),
    "EMBEDDING_ENDPOINT": (
        "百炼嵌入 endpoint 或模型名无效。请恢复项目 .env 中的官方百炼地址与 "
        "text-embedding-v4，再运行 `py -3 scripts/smoke_bailian.py --embedding`。"
    ),
    "EMBEDDING_SERVICE": (
        "百炼嵌入服务暂时异常。原文已保留在本地；请稍后重试上传或运行 "
        "`py -3 scripts/smoke_bailian.py --embedding` 确认服务恢复。"
    ),
    "EMBEDDING_RESPONSE": (
        "百炼嵌入响应不完整，索引未写入。原文已保留在本地；"
        "请稍后重试并运行 `py -3 scripts/smoke_bailian.py --embedding`。"
    ),
    "EMBEDDING_UNKNOWN": (
        "百炼嵌入调用失败，索引未写入。原文已保留在本地；请运行 "
        "`py -3 scripts/smoke_bailian.py --embedding` 获取脱敏诊断。"
    ),
}

_EMBEDDING_CODE_PATTERN = re.compile(r"\[(EMBEDDING_[A-Z_]+)\]")


class EmbeddingError(Exception):
    """嵌入调用错误：错误信息在抛出前已脱敏，不含完整 API Key。"""

    def __init__(self, message: str, *, code: str = "EMBEDDING_UNKNOWN") -> None:
        self.code = code if code in _EMBEDDING_GUIDANCE else "EMBEDDING_UNKNOWN"
        super().__init__(f"[{self.code}] {message}")


def embedding_error_guidance(code: str) -> str:
    """根据稳定错误码返回不含原始异常的中文修复指引。"""
    return _EMBEDDING_GUIDANCE.get(str(code or "").upper(), _EMBEDDING_GUIDANCE["EMBEDDING_UNKNOWN"])


def classify_embedding_error_text(value: str) -> str | None:
    """
    将 SDK/网络异常文本归类为稳定错误码。

    仅返回分类，不返回或拼接原文，避免 URL、Header 或 Key 泄漏到 UI。
    """
    text = str(value or "")
    marker = _EMBEDDING_CODE_PATTERN.search(text.upper())
    if marker and marker.group(1) in _EMBEDDING_GUIDANCE:
        return marker.group(1)

    low = text.lower()
    if not low:
        return None
    if any(token in low for token in ("http_proxy", "https_proxy", "proxyerror", "proxy error", "proxy", "socks", "tunnel")):
        return "EMBEDDING_PROXY"
    if any(token in low for token in ("timed out", "timeout", "apitimeout", "readtimeout", "connecttimeout", "10060")):
        return "EMBEDDING_TIMEOUT"
    if any(token in low for token in ("rate limit", "ratelimit", "too many requests", "429", "quota", "throttl")):
        return "EMBEDDING_RATE_LIMIT"
    if any(token in low for token in ("authentication", "permissiondenied", "unauthorized", "forbidden", "invalid api key", "access denied", "401", "403")):
        return "EMBEDDING_AUTH"
    if any(token in low for token in (
        "dashscope_api_key", "dashscope_base_url", "not configured", "missing api key",
        "api key must be set", "api_key client option", "未配置", "配置不完整", "密钥缺失",
    )):
        return "EMBEDDING_CONFIG"
    if any(token in low for token in ("invalid base_url", "invalid url", "model not found", "unknown model", "bad request", "not found", "400", "404")):
        return "EMBEDDING_ENDPOINT"
    if any(token in low for token in ("apiconnection", "connection", "connecterror", "dns", "name resolution", "unreachable", "refused", "ssl", "certificate", "10061")):
        return "EMBEDDING_NETWORK"
    if any(token in low for token in ("internal server", "bad gateway", "service unavailable", "gateway timeout", "500", "502", "503", "504")):
        return "EMBEDDING_SERVICE"
    if any(token in low for token in ("no module named", "openai sdk", "依赖缺失")):
        return "EMBEDDING_DEPENDENCY"
    if any(token in low for token in ("empty embedding", "embedding response", "嵌入响应", "返回空")):
        return "EMBEDDING_RESPONSE"
    if "embedding" in low or "嵌入" in low:
        return "EMBEDDING_UNKNOWN"
    return None


def _status_code(exc: Exception) -> int | None:
    """从 OpenAI/httpx 异常中提取 HTTP 状态码，不读取响应体。"""
    candidates = [getattr(exc, "status_code", None)]
    response = getattr(exc, "response", None)
    if response is not None:
        candidates.append(getattr(response, "status_code", None))
    for value in candidates:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def classify_embedding_exception(exc: Exception) -> EmbeddingError:
    """将任意底层异常转为脱敏、可行动的 EmbeddingError。"""
    if isinstance(exc, EmbeddingError):
        return exc
    status = _status_code(exc)
    if status in (401, 403):
        code = "EMBEDDING_AUTH"
    elif status == 407:
        code = "EMBEDDING_PROXY"
    elif status == 408:
        code = "EMBEDDING_TIMEOUT"
    elif status == 429:
        code = "EMBEDDING_RATE_LIMIT"
    elif status in (400, 404, 422):
        code = "EMBEDDING_ENDPOINT"
    elif status is not None and status >= 500:
        code = "EMBEDDING_SERVICE"
    else:
        code = None
    type_name = type(exc).__name__
    if code is None:
        classification_input = f"{type_name} {status or ''} {str(exc)}"
        code = classify_embedding_error_text(classification_input)
    if code is None:
        code = "EMBEDDING_UNKNOWN"
    return EmbeddingError(embedding_error_guidance(code), code=code)


class EmbeddingClient:
    """向量嵌入客户端：将文本编码为向量，供 zvec 索引与检索使用。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        初始化嵌入客户端并确定后端类型。

        参数：
            settings: 可选注入配置；缺省使用全局单例。
        """
        # 允许注入配置以便测试。
        self.settings = settings or get_settings()
        # 记录所选后端（bailian / local_qwen）。
        self.backend = self.settings.embedding_backend
        # 底层 openai 客户端惰性构造。
        self._client = None

    def _ensure_client(self):
        """
        惰性构造底层 openai 客户端（指向百炼 base_url）。

        返回：
            已配置的 openai.OpenAI 实例。

        异常：
            EmbeddingError: 当百炼未配置或 openai SDK 不可用时抛出。
        """
        # 已构造则复用。
        if self._client is not None:
            return self._client
        # 缺少配置时明确报错。
        if not self.settings.qwen_configured:
            raise EmbeddingError(
                embedding_error_guidance("EMBEDDING_CONFIG"), code="EMBEDDING_CONFIG"
            )
        # 延迟导入 openai。
        try:
            import httpx
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingError(
                embedding_error_guidance("EMBEDDING_DEPENDENCY"), code="EMBEDDING_DEPENDENCY"
            ) from exc
        # 只尊重项目显式 OUTBOUND_HTTPS_PROXY；禁用 Windows/环境隐式代理。
        # 本机 loopback 系统代理可能接受 TCP 却在 TLS 握手阶段提前断开，表现为
        # APIConnectionError/SSLEOFError。trust_env=False 可确保“未配置即直连”。
        try:
            timeout_seconds = float(getattr(self.settings, "llm_timeout_seconds", 180.0))
            connect_seconds = float(
                getattr(self.settings, "llm_connect_timeout_seconds", 20.0)
            )
            timeout = httpx.Timeout(
                timeout_seconds,
                connect=min(connect_seconds, timeout_seconds),
            )
            http_client = build_outbound_httpx_client(self.settings, timeout=timeout)
            self._client = OpenAI(
                api_key=self.settings.dashscope_api_key,
                base_url=self.settings.dashscope_base_url,
                timeout=timeout,
                max_retries=int(getattr(self.settings, "llm_max_retries", 1)),
                http_client=http_client,
            )
        except Exception as exc:
            raise classify_embedding_exception(exc) from None
        return self._client

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        将一组文本编码为向量列表（分批请求）。

        参数：
            texts: 待编码文本列表。

        返回：
            与输入等长、顺序一致的向量列表。

        异常：
            NotImplementedError: 当后端为 local_qwen 时（可选增强，未默认实现）。
            EmbeddingError:       百炼调用失败时（错误已脱敏；不伪造向量）。
        """
        # 本地 Qwen3-Embedding 为可选增强，默认不实现。
        if self.backend == "local_qwen":
            raise NotImplementedError(
                "EMBEDDING_BACKEND=local_qwen 为可选增强（需自行安装 transformers/torch 与本地权重），"
                "非默认功能。默认请使用 bailian 后端（text-embedding-v4）。"
            )

        # 空输入直接返回空列表。
        if not texts:
            return []

        # 校验嵌入模型名（text-embedding-v4 在白名单内）。
        model = self.settings.bailian_embedding_model
        try:
            assert_qwen_model(model)
        except Exception:
            raise EmbeddingError(
                embedding_error_guidance("EMBEDDING_CONFIG"), code="EMBEDDING_CONFIG"
            ) from None

        client = self._ensure_client()
        vectors: list[list[float]] = []
        # 分批处理，避免单次请求过大。
        for start in range(0, len(texts), _DEFAULT_BATCH_SIZE):
            batch = texts[start : start + _DEFAULT_BATCH_SIZE]
            try:
                resp = client.embeddings.create(model=model, input=batch)
                # 保持与输入相同顺序追加向量。
                data = list(getattr(resp, "data", []) or [])
                batch_vectors = [list(getattr(item, "embedding", []) or []) for item in data]
                if len(batch_vectors) != len(batch) or any(not vector for vector in batch_vectors):
                    raise EmbeddingError(
                        embedding_error_guidance("EMBEDDING_RESPONSE"), code="EMBEDDING_RESPONSE"
                    )
                vectors.extend(batch_vectors)
            except Exception as exc:
                # 仅记录分类/类型，不记录可能包含 Header/URL/Key 的原始文本。
                mapped = classify_embedding_exception(exc)
                logger.warning(
                    "embedding 失败：batch_start=%d code=%s exception_type=%s",
                    start,
                    mapped.code,
                    type(exc).__name__,
                )
                raise mapped from None
        return vectors
