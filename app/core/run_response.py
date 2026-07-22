"""
app.core.run_response —— 统一 Pipeline 运行响应 Schema（RunResponse）。

POST /runs 与前端 api_client 均使用该结构，避免半截数据或异常对象导致 UI 乱渲染。
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "running", "completed", "failed", "partial_failed"]
RunMode = Literal["mock", "real"]


class RunResponse(BaseModel):
    """统一运行结果响应。"""

    run_id: Optional[str] = Field(default=None, description="运行 ID")
    question_id: str = Field(default="", description="问题 ID")
    mode: RunMode = Field(default="mock", description="运行模式")
    status: RunStatus = Field(default="failed", description="运行状态")
    plan: Optional[dict] = Field(default=None, description="ResearchPlan dict")
    errors: list[str] = Field(default_factory=list, description="错误列表（脱敏）")
    warnings: list[str] = Field(default_factory=list, description="警告列表")
    artifacts: dict = Field(default_factory=dict, description="产物清单摘要")
    llm_call_summary: dict = Field(default_factory=dict, description="LLM 调用审计摘要")
    validation_status: Optional[str] = Field(default=None, description="校验状态")
    message: str = Field(default="", description="人类可读摘要")
    mock: bool = Field(default=False, description="是否 mock 运行")
    plan_question_id: str = Field(default="", description="plan.question_id")
    evidence_cards: list[Any] = Field(default_factory=list)
    agent_trace: list[Any] = Field(default_factory=list)
    quality_gates: dict = Field(default_factory=dict)

    def to_api_dict(self) -> dict:
        """转为 API JSON dict（兼容旧字段）。"""
        d = self.model_dump()
        d["mock"] = self.mode == "mock"
        return d


def build_run_response_from_state(
    *,
    question_id: str,
    mode: str,
    state,
    plan=None,
    status: RunStatus = "completed",
    message: str = "",
) -> RunResponse:
    """
    从 PipelineState 构造 RunResponse。

    参数：
        question_id: 问题 ID。
        mode:        mock | real。
        state:       PipelineState。
        plan:        ResearchPlan 或 dict。
        status:      运行状态。
        message:     摘要信息。

    返回：
        RunResponse 实例。
    """
    from app.core.call_audit import summarize_calls

    plan_dump = plan.model_dump() if plan is not None and hasattr(plan, "model_dump") else (plan or None)
    llm_summary = summarize_calls(getattr(state, "llm_calls", []) or [])
    validation = (plan_dump or {}).get("validation_status") if plan_dump else None

    if status == "completed" and mode == "real" and llm_summary.get("qwen_call_count", 0) == 0:
        if "real_mode_no_qwen_calls" not in (state.warnings or []):
            state.warnings.append("real_mode_no_qwen_calls")

    return RunResponse(
        run_id=getattr(state, "run_id", None),
        question_id=question_id,
        mode="mock" if mode == "mock" else "real",
        status=status,
        plan=plan_dump,
        errors=list(getattr(state, "errors", []) or []),
        warnings=list(getattr(state, "warnings", []) or []),
        llm_call_summary=llm_summary,
        validation_status=validation,
        message=message or status,
        mock=(mode == "mock"),
        plan_question_id=(plan_dump or {}).get("question_id", "") if plan_dump else "",
        evidence_cards=[
            e.model_dump() if hasattr(e, "model_dump") else e for e in (getattr(state, "retrieved_evidence", None) or [])
        ],
        agent_trace=list(getattr(state, "agent_trace", []) or []),
        quality_gates=dict(getattr(state, "quality_gates", {}) or {}),
    )


def failed_run_response(
    question_id: str,
    mode: str,
    errors: list[str],
    run_id: str | None = None,
    message: str = "运行失败",
) -> RunResponse:
    """构造失败 RunResponse（无 plan）。"""
    return RunResponse(
        run_id=run_id,
        question_id=question_id,
        mode="mock" if mode == "mock" else "real",
        status="failed",
        plan=None,
        errors=errors,
        message=message,
        mock=(mode == "mock"),
    )
