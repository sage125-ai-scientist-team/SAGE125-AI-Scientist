"""AI Scientist 运行进度的纯数据与安全展示模型。

本模块刻意不依赖 Streamlit 或后端实现：后端可以复用 ``PIPELINE_STAGE_ORDER``
发布稳定的阶段键，前端则通过 :func:`normalize_progress` 将轮询结果归一化。
任何可能含内部模型名的字段都不会直接进入普通用户文案。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


@dataclass(frozen=True)
class ProgressStage:
    """一个稳定的流水线阶段。``percent`` 是缺省进度，不代表耗时占比。"""

    key: str
    label: str
    percent: int


PIPELINE_STAGES: tuple[ProgressStage, ...] = (
    ProgressStage("preparing", "准备运行环境", 2),
    ProgressStage("preflight", "检查模型连接", 5),
    ProgressStage("supervisor", "规划研究流程", 10),
    ProgressStage("question_parser", "解析科学问题", 16),
    ProgressStage("query_planner", "制定检索方案", 23),
    ProgressStage("evidence_collection", "收集研究证据", 35),
    ProgressStage("deep_research", "开展深度研究", 44),
    ProgressStage("evidence_extractor", "整理证据卡片", 52),
    ProgressStage("hypothesis_generator", "生成可证伪假设", 61),
    ProgressStage("experiment_designer", "设计验证实验", 70),
    ProgressStage("scientific_reviewer", "执行科学评审", 79),
    ProgressStage("report_writer", "撰写研究计划", 87),
    ProgressStage("quality_gates", "检查质量与引用", 93),
    ProgressStage("export", "保存运行产物", 97),
    ProgressStage("completed", "研究计划已生成", 100),
)

# 后端可安全复用这个常量，而无需依赖 Streamlit 组件。
PIPELINE_STAGE_ORDER: tuple[str, ...] = tuple(item.key for item in PIPELINE_STAGES)
_STAGE_BY_KEY = {item.key: item for item in PIPELINE_STAGES}

# 兼容 Agent 名、历史字段与较自然的事件名。
_STAGE_ALIASES = {
    "starting": "preparing",
    "queued": "preparing",
    "connecting": "preflight",
    "retrieval": "evidence_collection",
    "local_rag": "evidence_collection",
    "open_literature": "evidence_collection",
    "schema_validator": "quality_gates",
    "artifacts": "export",
    "done": "completed",
}

# model_alias 是公开、稳定的档位；model_name_internal 只供开发者诊断。
# 友好显示名与服务端的内部 model id 解耦，避免把 endpoint/原始标识带入主卡。
MODEL_DISPLAY_BY_ALIAS: dict[str, str] = {
    "fast": "千问 3.6 Flash",
    "balanced": "千问 3.7 Plus",
    "strong": "千问 3.7 Max",
    "deepresearch": "千问深度研究服务",
    "deep_research": "千问深度研究服务",
    "unknown": "千问模型",
}

_STATUS_ALIASES = {
    "pending": "queued",
    "started": "running",
    "in_progress": "running",
    "processing": "running",
    "success": "completed",
    "done": "completed",
    "error": "failed",
    "timeout": "failed",
}
_ALLOWED_STATUSES = {"queued", "connecting", "waiting", "running", "completed", "failed"}
_STATUS_LABELS = {
    "queued": "等待开始",
    "connecting": "正在连接",
    "waiting": "等待响应",
    "running": "运行中",
    "completed": "已完成",
    "failed": "运行失败",
}

# 防御性脱敏。正常情况下服务端应直接发送安全 message；这里避免错误消息把
# API Key、endpoint 或内部 qwen model id 带入普通用户进度卡。
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_API_KEY_RE = re.compile(r"\b(?:sk|ak)[-_][A-Za-z0-9_-]{10,}\b", re.IGNORECASE)
_INTERNAL_MODEL_RE = re.compile(r"\bqwen[A-Za-z0-9_.-]*\b", re.IGNORECASE)
_CN_INTERNAL_MODEL_RE = re.compile(r"千问\s*\d+(?:\.\d+)+(?:\s*[-_.]?\s*[A-Za-z]+)?", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class RunProgress:
    """归一化后的进度快照，可直接交给 UI 渲染。"""

    stage: str
    stage_label: str
    status: str
    status_label: str
    percent: int
    message: str
    model_alias: str
    model_display: str
    model_name_internal: str
    step_index: int
    step_count: int


def _clean_text(value: Any, *, limit: int) -> str:
    text = _SPACE_RE.sub(" ", str(value or "")).strip()
    return text[:limit]


def _friendly_model_name(model_alias: str, model_display: Any) -> str:
    """返回主界面可用的友好模型名，绝不回退到内部模型 id。"""

    requested = _clean_text(model_display, limit=48)
    if requested:
        requested = _URL_RE.sub("模型服务", requested)
        requested = _API_KEY_RE.sub("[已隐藏]", requested)
        # 若误把内部 id 当作 model_display，仍转换成稳定的友好档位名称。
        if _INTERNAL_MODEL_RE.fullmatch(requested):
            return MODEL_DISPLAY_BY_ALIAS.get(model_alias, "千问模型")
        return requested
    return MODEL_DISPLAY_BY_ALIAS.get(model_alias, "千问模型")


def _default_message(status: str, stage_label: str, model_display: str, has_model: bool) -> str:
    if status == "queued":
        return "任务已进入队列，正在准备运行。"
    if status == "connecting":
        return f"正在连接{model_display}。" if has_model else "正在检查模型服务连接。"
    if status == "waiting":
        return f"正在等待{model_display}响应。" if has_model else f"{stage_label}正在等待服务响应。"
    if status == "completed":
        return "全部阶段已完成，研究计划与证据链已生成。"
    if status == "failed":
        return "本次运行未能完成，请查看下方安全提示或开发者诊断。"
    if has_model:
        return f"正在询问{model_display}，完成{stage_label}。"
    return f"正在{stage_label}。"


def _safe_public_message(
    value: Any,
    *,
    fallback: str,
    model_display: str,
    model_name_internal: str,
) -> str:
    message = _clean_text(value, limit=220)
    if not message:
        return fallback
    if model_name_internal:
        message = re.sub(
            re.escape(model_name_internal),
            lambda _match: model_display,
            message,
            flags=re.IGNORECASE,
        )
    message = _URL_RE.sub("[服务地址已隐藏]", message)
    message = _API_KEY_RE.sub("[凭证已隐藏]", message)
    message = _INTERNAL_MODEL_RE.sub(lambda _match: model_display, message)
    message = _CN_INTERNAL_MODEL_RE.sub(lambda _match: model_display, message)
    return message


def normalize_progress(payload: Mapping[str, Any] | None) -> RunProgress:
    """把宽松的 API payload 转成安全、边界明确的进度快照。

    支持字段：``stage``、``status``、``percent``、``message``、
    ``model_alias``、``model_display``、``model_name_internal``。
    未知字段会被忽略；百分比会钳制在 0..100。
    """

    raw = dict(payload or {})
    raw_stage = _clean_text(raw.get("stage"), limit=64).lower() or "preparing"
    stage_key = _STAGE_ALIASES.get(raw_stage, raw_stage)
    stage = _STAGE_BY_KEY.get(stage_key, _STAGE_BY_KEY["preparing"])

    raw_status = _clean_text(raw.get("status"), limit=32).lower() or "running"
    status = _STATUS_ALIASES.get(raw_status, raw_status)
    if status not in _ALLOWED_STATUSES:
        status = "running"

    default_percent = stage.percent
    try:
        percent = round(float(raw.get("percent", default_percent)))
    except (TypeError, ValueError, OverflowError):
        percent = default_percent
    percent = max(0, min(100, percent))
    if status == "completed":
        stage = _STAGE_BY_KEY["completed"]
        percent = 100

    model_alias = _clean_text(raw.get("model_alias"), limit=32).lower() or "unknown"
    model_name_internal = _clean_text(raw.get("model_name_internal"), limit=96)
    model_display = _friendly_model_name(model_alias, raw.get("model_display"))
    has_model = bool(raw.get("model_alias") or raw.get("model_display") or model_name_internal)
    fallback = _default_message(status, stage.label, model_display, has_model)
    message = _safe_public_message(
        raw.get("message"),
        fallback=fallback,
        model_display=model_display,
        model_name_internal=model_name_internal,
    )

    step_index = PIPELINE_STAGE_ORDER.index(stage.key) + 1
    return RunProgress(
        stage=stage.key,
        stage_label=stage.label,
        status=status,
        status_label=_STATUS_LABELS[status],
        percent=percent,
        message=message,
        model_alias=model_alias,
        model_display=model_display,
        model_name_internal=model_name_internal,
        step_index=step_index,
        step_count=len(PIPELINE_STAGES),
    )


__all__ = [
    "MODEL_DISPLAY_BY_ALIAS",
    "PIPELINE_STAGES",
    "PIPELINE_STAGE_ORDER",
    "ProgressStage",
    "RunProgress",
    "normalize_progress",
]
