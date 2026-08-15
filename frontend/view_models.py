"""Fail-closed display-state derivation for the B4 frontend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from frontend.api_client import APIClientError


class ViewState(str, Enum):
    INITIAL = "initial"
    LOADING = "loading"
    EMPTY = "empty"
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    FORBIDDEN = "forbidden"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True)
class ViewStatus:
    state: ViewState
    message: str
    retryable: bool = False


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def classify_job_view(
    payload: dict[str, Any] | None,
    *,
    loading: bool = False,
    error: APIClientError | None = None,
    now: datetime | None = None,
    stale_after_seconds: int = 60,
) -> ViewStatus:
    if loading:
        return ViewStatus(ViewState.LOADING, "正在从 API 加载任务状态…", True)
    if error is not None:
        if error.status_code in {401, 403}:
            return ViewStatus(ViewState.FORBIDDEN, "无权访问该任务。", False)
        if error.status_code in {408, 504}:
            return ViewStatus(ViewState.TIMED_OUT, error.message, error.retryable)
        if error.status_code == 503:
            return ViewStatus(ViewState.UNAVAILABLE, error.message, error.retryable)
        return ViewStatus(ViewState.FAILED, error.message, error.retryable)
    if payload is None:
        return ViewStatus(ViewState.INITIAL, "请选择问题并启动任务。")
    if not payload:
        return ViewStatus(ViewState.EMPTY, "API 未返回任务数据。", True)
    status = str(payload.get("status") or "")
    if status == "timed_out":
        return ViewStatus(ViewState.TIMED_OUT, "任务已超时。", False)
    if status in {"failed", "cancelled"}:
        return ViewStatus(ViewState.FAILED, "任务未成功完成。", False)
    updated_at = _parse_time(payload.get("updated_at"))
    current = now or datetime.now(timezone.utc)
    if (
        status in {"queued", "running", "retrying", "waiting_feedback"}
        and updated_at is not None
        and (current - updated_at).total_seconds() > stale_after_seconds
    ):
        return ViewStatus(ViewState.STALE, "状态长时间未更新，请刷新确认。", True)
    return ViewStatus(ViewState.SUCCESS, "任务状态已同步。")


def confidence_state(
    confidence: float | None,
    *,
    threshold: float = 0.6,
) -> ViewState:
    if confidence is None:
        return ViewState.EMPTY
    if float(confidence) < threshold:
        return ViewState.LOW_CONFIDENCE
    return ViewState.SUCCESS
