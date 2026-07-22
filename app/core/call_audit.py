"""
app.core.call_audit —— LLM 调用审计（证明"是否真实调用了 Qwen"）。

设计目标：
    在不泄露任何敏感信息（API Key / prompt 全文 / response 全文）的前提下，
    为每一次 LLM 调用（chat / embedding / rerank / deep_research）保存一条可核验
    的审计记录，供前端与评委确认真实调用发生，并区分 mock / real / fallback。

安全约束：
    - 绝不保存 API Key（key_masked 恒为 True）；
    - 绝不保存 prompt 全文与完整 response；
    - request_id / usage 仅在百炼真实返回时记录；
    - mock 模式也写记录，但 provider="mock"，token 计数为 0；
    - real 模式调用失败必须写 status="failed"，禁止伪装 success。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

# 调用提供方枚举。
Provider = Literal["bailian_qwen", "dashscope_deepresearch", "mock"]
# 模型档位别名（对普通用户暴露的抽象层，不含具体模型代号）。
ModelAlias = Literal["fast", "balanced", "strong", "embedding", "rerank", "deepresearch", "unknown"]
# 调用状态。
CallStatus = Literal["success", "failed", "skipped"]


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 字符串。"""
    return datetime.now(timezone.utc).isoformat()


class LLMCallRecord(BaseModel):
    """
    单次 LLM 调用的脱敏审计记录。

    该记录会被写入 exports/{run_id}/llm_call_audit.json，并可通过
    GET /runs/{run_id}/llm-calls 以脱敏形式返回给前端。
    """

    # 调用唯一 ID。
    call_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], description="调用 ID")
    # 所属运行 ID。
    run_id: str = Field(default="", description="运行 ID")
    # 触发调用的 Agent 名称。
    agent_name: str = Field(default="", description="Agent 名称")
    # 调用提供方。
    provider: Provider = Field(default="mock", description="提供方")
    # 模型档位别名（对外抽象，不暴露具体模型代号）。
    model_alias: ModelAlias = Field(default="unknown", description="模型档位别名")
    # 内部真实模型名（仅供开发者诊断，不在普通用户界面展示）。
    model_name_internal: str = Field(default="", description="内部模型名（开发者诊断用）")
    # 是否 mock 调用。
    mock: bool = Field(default=False, description="是否 mock")
    # 开始/结束时间。
    started_at: str = Field(default_factory=_now_iso, description="开始时间")
    ended_at: Optional[str] = Field(default=None, description="结束时间")
    # 耗时（毫秒）。
    duration_ms: Optional[int] = Field(default=None, description="耗时毫秒")
    # 百炼返回的 request_id（如有）。
    request_id: Optional[str] = Field(default=None, description="request_id（脱敏保留）")
    # token 使用量（如百炼返回）。
    input_tokens: Optional[int] = Field(default=None, description="输入 token 数")
    output_tokens: Optional[int] = Field(default=None, description="输出 token 数")
    total_tokens: Optional[int] = Field(default=None, description="总 token 数")
    # 调用状态。
    status: CallStatus = Field(default="success", description="状态")
    # 错误类型（失败时填写，脱敏，不含 Key）。
    error_type: Optional[str] = Field(default=None, description="错误类型（脱敏）")
    # 是否触发了 fallback（如 rerank 失败保持原序）。
    fallback_used: bool = Field(default=False, description="是否触发 fallback")
    # fallback 原因（脱敏）。
    fallback_reason: Optional[str] = Field(default=None, description="fallback 原因")
    # 是否已对 Key 脱敏（恒为 True，作为安全断言字段）。
    key_masked: bool = Field(default=True, description="Key 是否已脱敏（恒 True）")

    def finalize(self) -> "LLMCallRecord":
        """补齐 ended_at 与 duration_ms（若缺失），返回自身。"""
        if self.ended_at is None:
            self.ended_at = _now_iso()
        if self.duration_ms is None:
            try:
                delta = datetime.fromisoformat(self.ended_at) - datetime.fromisoformat(self.started_at)
                self.duration_ms = int(delta.total_seconds() * 1000)
            except ValueError:
                self.duration_ms = None
        return self


def summarize_calls(records: list[dict]) -> dict:
    """
    汇总一组调用审计记录为前端可读摘要（全部脱敏）。

    参数：
        records: LLMCallRecord 的 dict 列表。

    返回：
        包含调用计数、涉及 Agent、request_id（脱敏）、usage 汇总的 dict。
    """
    qwen_chat = [r for r in records if r.get("provider") == "bailian_qwen" and not r.get("mock")]
    dr_calls = [r for r in records if r.get("provider") == "dashscope_deepresearch" and not r.get("mock")]
    qwen_calls = qwen_chat + dr_calls
    mock_calls = [r for r in records if r.get("mock") or r.get("provider") == "mock"]
    failed_calls = [r for r in records if r.get("status") == "failed"]
    # request_id 仅保留掩码形态（前 8 位 + ***），不泄露完整值。
    request_ids_masked: list[str] = []
    for r in records:
        rid = r.get("request_id")
        if rid:
            request_ids_masked.append(f"{str(rid)[:8]}***")
    # token 汇总。
    total_input = sum(int(r.get("input_tokens") or 0) for r in records)
    total_output = sum(int(r.get("output_tokens") or 0) for r in records)
    total_tokens = sum(int(r.get("total_tokens") or 0) for r in records)
    return {
        "qwen_call_count": len(qwen_calls),
        "real_qwen_calls": len(qwen_calls),
        "mock_call_count": len(mock_calls),
        "mock_calls": len(mock_calls),
        "failed_call_count": len(failed_calls),
        "failed_calls": len(failed_calls),
        "total_call_count": len(records),
        "total_calls": len(records),
        "deepresearch_calls": len(dr_calls),
        "agents_invoked": sorted({r.get("agent_name", "") for r in records if r.get("agent_name")}),
        "agents": sorted({r.get("agent_name", "") for r in records if r.get("agent_name")}),
        "request_ids_masked": request_ids_masked,
        "request_ids": request_ids_masked,
        "usage_summary": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
        },
        "deep_research_invoked": len(dr_calls) > 0,
        "any_real_qwen": len(qwen_calls) > 0,
        "providers": sorted({r.get("provider", "") for r in records if r.get("provider")}),
    }
