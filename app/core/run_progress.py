"""Backend-neutral progress events for pipeline, clients and UI callbacks."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator, Mapping


ProgressCallback = Callable[[dict], None]

_callback: ContextVar[ProgressCallback | None] = ContextVar("sage125_progress_callback", default=None)
_latest: ContextVar[dict] = ContextVar("sage125_progress_latest", default={})

MODEL_DISPLAY = {
    "fast": "千问 3.6 Flash",
    "balanced": "千问 3.7 Plus",
    "strong": "千问 3.7 Max",
    "deepresearch": "千问 DeepResearch",
}

STAGE_PERCENT = {
    "initializing": 2,
    "preflight": 4,
    "supervisor": 6,
    "question_parser": 10,
    "query_planner": 18,
    "retrieval": 28,
    "deep_research": 38,
    "evidence_extractor": 48,
    "hypothesis_generator": 59,
    "experiment_designer": 69,
    "scientific_reviewer": 79,
    "report_writer": 89,
    "schema_validator": 95,
    "artifacts": 98,
    "completed": 100,
}

STAGE_DISPLAY = {
    "supervisor": "规划研究流程",
    "question_parser": "解析科学问题",
    "query_planner": "制定检索方案",
    "evidence_extractor": "整理证据卡片",
    "hypothesis_generator": "生成可证伪假设",
    "experiment_designer": "设计验证实验",
    "scientific_reviewer": "执行科学评审",
    "report_writer": "撰写研究计划",
    "schema_validator": "检查质量与引用",
}


def friendly_stage_name(stage: str) -> str:
    return STAGE_DISPLAY.get(stage, stage.replace("_", " "))


def friendly_model_name(alias: str | None, internal: str | None = None) -> str:
    """Return a stable user-facing model label without exposing configuration."""
    if alias in MODEL_DISPLAY:
        return MODEL_DISPLAY[alias]
    name = (internal or "").lower()
    if "3.7-max" in name:
        return MODEL_DISPLAY["strong"]
    if "3.7-plus" in name:
        return MODEL_DISPLAY["balanced"]
    if "3.6-flash" in name:
        return MODEL_DISPLAY["fast"]
    if "deep-research" in name:
        return MODEL_DISPLAY["deepresearch"]
    return "千问模型"


def emit_progress(
    stage: str,
    *,
    status: str = "running",
    percent: int | None = None,
    message: str = "",
    model_alias: str | None = None,
    model_name_internal: str | None = None,
    **extra,
) -> dict:
    """Emit a sanitized progress payload; callback failures never break a run."""
    previous = dict(_latest.get() or {})
    payload = {
        **previous,
        "stage": stage,
        "status": status,
        "percent": max(0, min(100, int(percent if percent is not None else STAGE_PERCENT.get(stage, previous.get("percent", 0))))),
        "message": message,
        "model_alias": model_alias,
        "model_display": friendly_model_name(model_alias, model_name_internal) if (model_alias or model_name_internal) else previous.get("model_display", ""),
        "model_name_internal": model_name_internal,
        **extra,
    }
    _latest.set(payload)
    callback = _callback.get()
    if callback is not None:
        try:
            callback(dict(payload))
        except Exception:
            pass
    return payload


def current_progress() -> Mapping:
    """Return the latest progress snapshot in the current execution context."""
    return dict(_latest.get() or {})


@contextmanager
def progress_reporting(callback: ProgressCallback | None) -> Iterator[None]:
    """Bind a callback to this run without global mutable state."""
    cb_token = _callback.set(callback)
    latest_token = _latest.set({})
    try:
        yield
    finally:
        _latest.reset(latest_token)
        _callback.reset(cb_token)
