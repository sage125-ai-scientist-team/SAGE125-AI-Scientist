"""
app.agents.base —— 多智能体基类 BaseAgent。

提供统一的执行模板：构建输入摘要 -> （mock 或调用 Qwen）-> 解析 JSON ->
Pydantic 校验 -> 写入可追踪的 AgentTraceEvent。子类只需声明模型/prompt/输出
schema，并实现 build_messages() 与 build_mock() 两个钩子。

安全约束：
    - 所有生成模型必须通过 assert_qwen_model；
    - 追踪与摘要不保存完整 API Key、不保存用户上传文件全文（<=600 字符）；
    - 单个非关键 Agent 失败不应白屏：失败写入 state.errors 与 trace，
      由 pipeline 决定是否继续。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from app.clients.qwen_chat_client import QwenChatClient
from app.core.agent_schemas import AgentTraceEvent
from app.core.call_audit import LLMCallRecord
from app.core.config import Settings, assert_qwen_model, get_settings
from app.core.execution_mode import is_mock_mode
from app.core.logging import get_logger, mask_text
from app.core.run_progress import emit_progress, friendly_model_name, friendly_stage_name
from app.core.schemas import PipelineState

# 会被递归扫描以收集证据 ID 的字段名。
_EVIDENCE_ID_KEYS = (
    "evidence_ids",
    "reference_ids",
    "supporting_evidence_ids",
    "contradicted_by_evidence_ids",
)


class AgentOutputError(Exception):
    """Agent 输出解析/校验失败时抛出（错误信息已脱敏）。"""


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 字符串。"""
    # 统一时间格式，便于 trace 排序。
    return datetime.now(timezone.utc).isoformat()


def _collect_evidence_ids(obj: Any) -> list[str]:
    """
    递归收集嵌套结构中的证据 ID（evidence_ids/reference_ids/supporting_evidence_ids）。

    参数：
        obj: 任意嵌套的 dict/list 结构。

    返回：
        去重后的证据 ID 列表。
    """
    found: list[str] = []

    def _walk(node: Any) -> None:
        # 字典：命中目标键则收集其列表值，并继续深入。
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _EVIDENCE_ID_KEYS and isinstance(v, list):
                    found.extend(str(x) for x in v)
                else:
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(obj)
    # 去重且保持稳定顺序。
    return list(dict.fromkeys(found))


class BaseAgent(ABC):
    """多智能体基类：封装 LLM 调用、mock、JSON 解析、校验与追踪。"""

    # 子类应覆盖的 Agent 名称。
    name: str = "base"
    # 子类应设置的输出 Pydantic schema 类。
    output_schema: Optional[type[BaseModel]] = None

    def __init__(
        self,
        settings: Optional[Settings] = None,
        chat_client: Optional[QwenChatClient] = None,
    ) -> None:
        """
        初始化 Agent（配置、日志器、模型名、system prompt）。

        参数：
            settings:    可选注入配置；缺省使用全局单例。
            chat_client: 可选注入的 QwenChatClient（便于测试）。
        """
        # 允许注入配置以便测试。
        self.settings = settings or get_settings()
        # 命名日志器（继承脱敏能力）。
        self.logger = get_logger(f"agents.{self.name}")
        # 模型名与 system prompt 由子类在其 __init__ 中设置。
        self.model_name: str = self.settings.qwen_balanced_model
        self.system_prompt: str = ""
        # 默认要求 JSON 输出。
        self.json_output: bool = True
        # 惰性聊天客户端。
        self._chat_client = chat_client

    # ---- 能力开关 ----

    def is_mock(self) -> bool:
        """判断是否处于 MOCK_LLM 模式。"""
        return is_mock_mode()

    def model_alias(self) -> str:
        """
        将内部模型名映射为对外抽象档位（fast/balanced/strong/deepresearch）。

        返回：
            档位别名字符串；未识别返回 "unknown"。
        """
        s = self.settings
        mapping = {
            s.qwen_fast_model: "fast",
            s.qwen_balanced_model: "balanced",
            s.qwen_strong_model: "strong",
            s.qwen_deep_research_model: "deepresearch",
        }
        return mapping.get(self.model_name, "unknown")

    def _client(self) -> QwenChatClient:
        """惰性获取 QwenChatClient。"""
        # 复用注入或懒构造。
        if self._chat_client is None:
            self._chat_client = QwenChatClient(self.settings)
        return self._chat_client

    # ---- LLM 调用 ----

    def call_llm(self, messages: list[dict], temperature: float = 0.2, json_mode: bool = True):
        """
        调用 Qwen 聊天模型（强制千问校验）。

        参数：
            messages:    OpenAI 风格消息列表。
            temperature: 采样温度。
            json_mode:   是否要求 JSON 输出（True 返回 dict）。

        返回：
            json_mode=True 返回 dict；否则返回 str。

        异常：
            ValueError: 模型非千问时（assert_qwen_model）。
        """
        # 强制模型为千问。
        assert_qwen_model(self.model_name)
        client = self._client()
        # JSON 模式用 chat_json，返回 dict。
        if json_mode:
            return client.chat_json(messages, model=self.model_name, temperature=temperature)
        return client.chat(messages, model=self.model_name, temperature=temperature)

    # ---- 摘要 / 解析 / 校验 / 指纹 ----

    def safe_summarize_input(self, input_data: Any) -> str:
        """
        生成不超过 600 字符的输入摘要（不含完整 Key / 文件全文）。

        参数：
            input_data: 任意输入数据。

        返回：
            脱敏且截断的摘要字符串。
        """
        try:
            # 序列化后截断；default=str 兼容非 JSON 类型。
            text = json.dumps(input_data, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(input_data)
        # 脱敏并截断到 600 字符。
        return mask_text(text)[:600]

    def parse_json_response(self, raw: Any) -> dict:
        """
        将模型输出解析为 dict；失败则尝试一次 repair，仍失败抛错。

        参数：
            raw: chat_json 的 dict 或 chat 的字符串。

        返回：
            解析后的 dict。

        异常：
            AgentOutputError: 解析与 repair 均失败时抛出。
        """
        # 已是 dict 直接返回。
        if isinstance(raw, dict):
            return raw
        # 字符串尝试直接解析。
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # repair：请模型把内容修复为严格 JSON。
                try:
                    repaired = self.call_llm(
                        [
                            {"role": "system", "content": "把用户内容修复为严格合法的 JSON 对象，只输出 JSON。"},
                            {"role": "user", "content": raw[:4000]},
                        ],
                        temperature=0.0,
                        json_mode=True,
                    )
                    if isinstance(repaired, dict):
                        return repaired
                except Exception:
                    pass
        # 无法解析。
        raise AgentOutputError(f"{self.name} 输出无法解析为 JSON。")

    def _focus_schema_fields(self, data: dict, schema_cls: type[BaseModel]) -> dict:
        """
        从模型输出中提取 schema 字段，丢弃 question_item 等输入回显键。

        参数：
            data:        原始 dict。
            schema_cls:  目标 Pydantic 模型。

        返回：
            仅含 schema 字段的 dict（若为空则返回原 dict）。
        """
        if not isinstance(data, dict):
            return data
        fields = set(schema_cls.model_fields.keys())
        focused = {k: v for k, v in data.items() if k in fields}
        return focused if focused else data

    def _repair_schema_output(
        self, data: dict, schema_cls: type[BaseModel], error_msg: str
    ) -> dict | None:
        """
        真实模式下校验失败时，用一次 LLM 修复为合法 schema JSON（不 fallback mock）。

        参数：
            data:       无效输出。
            schema_cls: 目标 schema。
            error_msg:  Pydantic 校验错误信息。

        返回：
            修复后的 dict；失败返回 None。
        """
        if self.is_mock():
            return None
        required = list(schema_cls.model_fields.keys())
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是 JSON 修复器。将用户提供的无效输出修复为严格合法的 {schema_cls.__name__}。"
                    f"必须包含全部字段：{required}。"
                    "只输出 JSON 对象，不要回显 question_item / evidence_catalog 等输入字段。"
                    "results 未真实执行时必须写 pending 说明，禁止伪造实验数值。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"invalid_output": data, "validation_error": mask_text(error_msg)},
                    ensure_ascii=False,
                    default=str,
                )[:6000],
            },
        ]
        try:
            repaired = self.call_llm(messages, temperature=0.0, json_mode=True)
            if isinstance(repaired, dict):
                return self._focus_schema_fields(repaired, schema_cls)
        except Exception as exc:
            self.logger.warning("%s schema repair 失败：%s", self.name, mask_text(str(exc)))
        return None

    def validate_output(self, data: dict, schema_cls: type[BaseModel]) -> BaseModel:
        """
        用 Pydantic schema 校验 Agent 输出；真实模式失败时尝试一次 schema repair。

        参数：
            data:      待校验 dict。
            schema_cls: Pydantic 模型类。

        返回：
            校验通过的模型实例。

        异常：
            AgentOutputError: 校验与 repair 均失败时抛出（脱敏）。
        """
        data = self._focus_schema_fields(data, schema_cls)
        try:
            return schema_cls(**data)
        except Exception as exc:
            repaired = self._repair_schema_output(data, schema_cls, str(exc))
            if repaired:
                try:
                    return schema_cls(**repaired)
                except Exception as exc2:
                    raise AgentOutputError(
                        f"{self.name} 输出未通过 {schema_cls.__name__} 校验（repair 后仍失败）："
                        f"{mask_text(str(exc2))}"
                    ) from None
            raise AgentOutputError(
                f"{self.name} 输出未通过 {schema_cls.__name__} 校验：{mask_text(str(exc))}"
            ) from None

    def hash_prompt(self, system_prompt: str, input_summary: str) -> str:
        """
        由 system_prompt + 输入摘要生成 prompt 指纹（便于可复现追踪）。

        参数：
            system_prompt: 系统提示词。
            input_summary: 输入摘要。

        返回：
            12 位十六进制指纹。
        """
        # 稳定 hash，便于对比同一 prompt 的多次运行。
        raw = f"{self.model_name}|{system_prompt}|{input_summary}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:12]

    def create_trace_event(
        self,
        state: PipelineState,
        step_index: int,
        status: str,
        input_summary: str,
        output_summary: str,
        evidence_ids: list[str],
        warnings: list[str],
        errors: list[str],
        prompt_hash: Optional[str],
        started_at: Optional[str],
        ended_at: Optional[str],
        mock: bool,
    ) -> AgentTraceEvent:
        """
        构造并登记一条 AgentTraceEvent 到 state.agent_trace。

        参数：见字段含义（均已在 AgentTraceEvent 中定义）。

        返回：
            构造的 AgentTraceEvent。
        """
        # 计算耗时（若时间戳齐备）。
        duration = None
        if started_at and ended_at:
            try:
                d = datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)
                duration = int(d.total_seconds() * 1000)
            except ValueError:
                duration = None
        event = AgentTraceEvent(
            event_id=uuid.uuid4().hex[:12],
            run_id=state.run_id,
            step_index=step_index,
            agent_name=self.name,
            model_name=self.model_name,
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration,
            input_summary=input_summary[:600],
            output_summary=output_summary[:600],
            evidence_ids=evidence_ids,
            warnings=warnings,
            errors=errors,
            prompt_hash=prompt_hash,
            mock=mock,
        )
        # 以 dict 快照登记，便于 artifacts 序列化。
        state.agent_trace.append(event.model_dump())
        return event

    def _record_llm_call(
        self,
        state: PipelineState,
        mock: bool,
        status: str,
        error_type: Optional[str] = None,
        started_at: Optional[str] = None,
    ) -> None:
        """
        向 state.llm_calls 追加一条脱敏调用审计记录。

        参数：
            state:      流水线状态。
            mock:       是否 mock 调用。
            status:     "success" | "failed" | "skipped"。
            error_type: 失败时的错误类型（脱敏，不含 Key）。
        """
        # 真实调用从 chat client 读取 request_id / usage（若已构造）。
        request_id = None
        usage: dict = {}
        if not mock and self._chat_client is not None:
            request_id = getattr(self._chat_client, "last_request_id", None)
            usage = getattr(self._chat_client, "last_usage", {}) or {}
        record = LLMCallRecord(
            run_id=state.run_id,
            agent_name=self.name,
            provider="mock" if mock else "bailian_qwen",
            model_alias=self.model_alias(),  # type: ignore[arg-type]
            model_name_internal=self.model_name,
            mock=mock,
            request_id=request_id,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            total_tokens=usage.get("total_tokens"),
            status=status,  # type: ignore[arg-type]
            error_type=error_type,
            started_at=started_at or _now_iso(),
        ).finalize()
        state.llm_calls.append(record.model_dump())

    # ---- 子类钩子 ----

    def build_messages(self, input_data: dict) -> list[dict]:
        """
        构造发送给 Qwen 的消息（子类实现）。

        参数：
            input_data: Agent 输入。

        返回：
            OpenAI 风格消息列表。
        """
        # 默认：system prompt + 输入 JSON。
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps(input_data, ensure_ascii=False, default=str)},
        ]

    def build_mock(self, input_data: dict, state: PipelineState) -> dict:
        """
        构造 mock 输出（子类实现）。

        参数：
            input_data: Agent 输入。
            state:      流水线状态（提供 run 上下文，如证据 ID）。

        返回：
            mock dict。
        """
        # 子类必须实现。
        raise NotImplementedError

    # ---- 执行模板 ----

    def run(self, input_data: dict, state: PipelineState, step_index: int = 0) -> dict:
        """
        执行模板：mock/LLM -> 解析 -> 校验 -> 追踪，返回校验后的 dict。

        参数：
            input_data: Agent 输入。
            state:      流水线状态。
            step_index: 步序索引（用于 trace）。

        返回：
            校验后的输出 dict。

        异常：
            AgentOutputError: 解析或校验失败时抛出（已写入 trace 与 state.errors）。
        """
        # 前置准备。
        started = _now_iso()
        input_summary = self.safe_summarize_input(input_data)
        prompt_hash = self.hash_prompt(self.system_prompt, input_summary)
        output_summary = ""
        evidence_ids: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []
        status = "running"
        result: dict = {}

        mock = self.is_mock()
        try:
            # mock 或真实调用。
            if mock:
                emit_progress(
                    self.name,
                    status="running",
                    message=f"正在{friendly_stage_name(self.name)}（模拟模式）",
                    model_alias=self.model_alias(),
                    model_name_internal=self.model_name,
                )
                data = self.build_mock(input_data, state)
                # mock 调用也写审计记录（provider=mock，token=0）。
                self._record_llm_call(state, mock=True, status="success", started_at=started)
            else:
                # 真实模式：调用 Qwen；失败向上抛出，绝不静默 fallback 到 mock。
                display = friendly_model_name(self.model_alias(), self.model_name)
                emit_progress(
                    self.name,
                    status="connecting",
                    message=f"正在连接 {display}",
                    model_alias=self.model_alias(),
                    model_name_internal=self.model_name,
                )
                try:
                    raw = self.call_llm(self.build_messages(input_data), json_mode=self.json_output)
                except Exception as call_exc:
                    self._record_llm_call(
                        state, mock=False, status="failed",
                        error_type=type(call_exc).__name__,
                        started_at=started,
                    )
                    raise
                self._record_llm_call(state, mock=False, status="success", started_at=started)
                data = self.parse_json_response(raw)
            # 校验并归一化为 dict；output_schema 为 None 时（如 ReportWriter）跳过校验，
            # 由 pipeline 做后续 ResearchPlan 组装与校验。
            if self.output_schema is not None:
                model = self.validate_output(data, self.output_schema)
                result = model.model_dump()
            else:
                result = data
            allowed_ids = input_data.get("allowed_evidence_ids") if isinstance(input_data, dict) else None
            if allowed_ids:
                from app.evidence.id_guard import UnknownEvidenceIDError, assert_known_evidence_ids

                try:
                    evidence_ids = assert_known_evidence_ids(result, allowed_ids, raw_output=result)
                except UnknownEvidenceIDError as exc:
                    errors.append(str(exc))
                    raise AgentOutputError(str(exc)) from exc
            else:
                evidence_ids = _collect_evidence_ids(result)
            output_summary = self.safe_summarize_input(result)
            status = "completed"
            emit_progress(
                self.name,
                status="running",
                message=f"{friendly_stage_name(self.name)}已完成",
                model_alias=self.model_alias(),
                model_name_internal=self.model_name,
            )
            return result
        except Exception as exc:
            # 失败：脱敏记录到 trace 与 state.errors，抛出供 pipeline 决策。
            status = "failed"
            msg = mask_text(str(exc))
            errors.append(msg)
            state.errors.append(f"{self.name}: {msg}")
            emit_progress(
                self.name,
                status="failed",
                message=f"{friendly_stage_name(self.name)}失败：{msg[:180]}",
                model_alias=self.model_alias(),
                model_name_internal=self.model_name,
            )
            raise AgentOutputError(msg) from None
        finally:
            # 无论成败均登记一条 trace。
            self.create_trace_event(
                state=state,
                step_index=step_index,
                status=status,
                input_summary=input_summary,
                output_summary=output_summary,
                evidence_ids=evidence_ids,
                warnings=warnings,
                errors=errors,
                prompt_hash=prompt_hash,
                started_at=started,
                ended_at=_now_iso(),
                mock=self.is_mock(),
            )
