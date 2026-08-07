"""审计记录：脱敏、tokens/cost 仅记录服务返回值，不得编造。"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.multimodal.errors import ExtractionError


class VisionCallAudit(BaseModel):
    """完整视觉调用审计记录（脱敏）。"""

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(...)
    provider: str = Field(default="qwen")
    model: str = Field(default="qwen-vl-offline-denied")
    prompt_schema_version: str = Field(default="t06-vision-v1")
    status: Literal[
        "success",
        "failed",
        "skipped",
        "not_implemented",
        "denied_no_paid_auth",
        "needs_human_review",
    ] = "denied_no_paid_auth"
    input_summary: str = Field(default="", max_length=200)
    started_utc: Optional[str] = None
    finished_utc: Optional[str] = None
    latency_ms: Optional[float] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None
    service_reported_cost: Optional[float] = None
    response_id: Optional[str] = None
    response_content_sha256: Optional[str] = None
    attempt_count: int = Field(default=1, ge=1)
    timeout: bool = False
    retry_count: int = Field(default=0, ge=0)
    error_type: Optional[str] = None
    key_masked: bool = Field(default=True)
    actual_external_call: bool = Field(default=False)

    @field_validator("key_masked")
    @classmethod
    def _key_must_be_masked(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("key_masked must be True")
        return value

    def ensure_safe(self) -> "VisionCallAudit":
        lowered = self.input_summary.lower()
        for needle in ("api_key", "sk-", "secret", "password", "token=", "bearer "):
            if needle in lowered:
                raise ValueError(
                    f"audit input_summary must not contain sensitive marker {needle!r}"
                )
        if self.actual_external_call and self.status == "denied_no_paid_auth":
            raise ValueError("inconsistent audit: external call with denied status")
        if self.cost_usd is not None and not self.actual_external_call:
            raise ValueError("cost_usd only allowed for actual external calls")
        if self.service_reported_cost is not None and not self.actual_external_call:
            raise ValueError("service_reported_cost only for actual external calls")
        if (self.tokens_in is not None or self.tokens_out is not None) and not (
            self.actual_external_call
        ):
            raise ValueError("tokens only allowed for actual external calls")
        return self


class VisionCallAuditStub(VisionCallAudit):
    """PR-A 兼容别名。"""

    status: Literal[
        "success",
        "failed",
        "skipped",
        "not_implemented",
        "denied_no_paid_auth",
        "needs_human_review",
    ] = "not_implemented"


def paid_vision_authorized() -> bool:
    """显式环境变量允许时才视为授权（默认 False）。"""
    return os.environ.get("T06_PAID_VISION_AUTHORIZED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def begin_vision_audit(input_summary: str) -> VisionCallAudit:
    return VisionCallAudit(
        call_id=str(uuid.uuid4()),
        input_summary=input_summary[:200],
        key_masked=True,
        actual_external_call=False,
        status="denied_no_paid_auth",
    )


def run_vision_or_deny(source_path: str) -> tuple[dict[str, Any], VisionCallAudit]:
    """
    无付费授权时返回 denied 审计，不发起网络请求，不猜测 tokens/cost。
    """
    started = time.perf_counter()
    audit = begin_vision_audit(f"path={source_path}")
    if not paid_vision_authorized():
        audit.status = "denied_no_paid_auth"
        audit.error_type = "paid_call_not_authorized"
        audit.latency_ms = (time.perf_counter() - started) * 1000.0
        audit.actual_external_call = False
        return {}, audit.ensure_safe()
    audit.status = "failed"
    audit.error_type = "paid_call_implementation_blocked_pending_extra_auth"
    audit.latency_ms = (time.perf_counter() - started) * 1000.0
    raise ExtractionError(
        "paid vision call requires additional captain authorization beyond Wave B flag"
    )
