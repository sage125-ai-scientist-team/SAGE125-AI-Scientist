"""
Qwen 视觉调用路径（canonical：百炼 OpenAI-compatible）。

- 必须显式配置视觉模型环境变量 QWEN_VL_MODEL（不得静默回退到普通 chat balanced）
- 支持 PDF 页渲染与 PNG/JPEG/WebP
- 响应经 vision_schema 解析为 MultimodalArtifact
- 空响应/非法 JSON → 不得标 success
- tokens/cost 仅记录服务返回值
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import assert_qwen_model, get_settings
from app.multimodal.audit import VisionCallAudit, paid_vision_authorized
from app.multimodal.errors import ExtractionError
from app.multimodal.pdf_io import load_source_bytes, open_pdf, render_page_png_bytes
from app.multimodal.vision_schema import mock_vision_chart_response, parse_vision_chart_json

_VISION_HINTS = ("vl", "vision", "qwen2.5-vl", "qwen2-vl", "qwen-vl")


def credential_status() -> dict[str, str]:
    return {
        "DASHSCOPE_API_KEY": "PRESENT"
        if os.environ.get("DASHSCOPE_API_KEY", "").strip()
        else "MISSING",
        "DASHSCOPE_BASE_URL": "PRESENT"
        if os.environ.get("DASHSCOPE_BASE_URL", "").strip()
        else "MISSING",
        "QWEN_VL_MODEL": "PRESENT"
        if os.environ.get("QWEN_VL_MODEL", "").strip()
        else "MISSING",
    }


def resolve_vision_model() -> str:
    model = os.environ.get("QWEN_VL_MODEL", "").strip()
    if not model:
        raise ExtractionError(
            "QWEN_VL_MODEL is required for vision calls; "
            "refusing silent fallback to non-vision balanced chat model"
        )
    model = assert_qwen_model(model)
    lowered = model.lower()
    if not any(h in lowered for h in _VISION_HINTS):
        raise ExtractionError(
            f"QWEN_VL_MODEL={model!r} does not look like a vision model "
            f"(expected name containing {[h for h in _VISION_HINTS]})"
        )
    return model


def build_vision_prompt_schema() -> dict[str, str]:
    return {
        "prompt_schema_version": "t06-vision-chart-v2",
        "prompt_summary": (
            "Return ONLY JSON with keys legend, axes[{name,label,unit,min_value,max_value}], "
            "series[{name,points[{x,y}]}], confidence, bbox{x0,y0,x1,y1}. "
            "Do not invent values; omit rather than guess."
        ),
    }


def _load_image_bytes(source_path: str, *, page: int = 1) -> tuple[bytes, str, str, int]:
    """Returns png_or_image_bytes, mime, file_sha256, page."""
    meta = load_source_bytes(source_path)
    suffix = meta.suffix
    if suffix == ".pdf":
        doc = open_pdf(source_path)
        try:
            png = render_page_png_bytes(doc, page, dpi=96)
        finally:
            doc.close()
        return png, "image/png", meta.sha256, page
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        data = Path(source_path).read_bytes()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }[suffix]
        return data, mime, meta.sha256, page
    raise ExtractionError(f"unsupported vision input type: {suffix!r}")


def run_qwen_vision(
    source_path: str,
    *,
    page: int = 1,
    max_output_tokens: int = 256,
    allow_actual: bool = False,
    mock_response_json: str | None = None,
    simulate_error: str | None = None,
) -> tuple[dict[str, Any], VisionCallAudit]:
    started = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    schema = build_vision_prompt_schema()
    creds = credential_status()
    attempt_count = 1

    audit = VisionCallAudit(
        call_id=str(uuid.uuid4()),
        provider="dashscope-openai-compatible",
        model=os.environ.get("QWEN_VL_MODEL", "").strip() or "unspecified-vision",
        prompt_schema_version=schema["prompt_schema_version"],
        status="denied_no_paid_auth",
        input_summary="",
        started_utc=started_utc,
        key_masked=True,
        actual_external_call=False,
        attempt_count=attempt_count,
        retry_count=0,
    )

    try:
        image_bytes, mime, file_sha256, page_used = _load_image_bytes(
            source_path, page=page
        )
    except ExtractionError as exc:
        audit.status = "failed"
        audit.error_type = type(exc).__name__
        audit.finished_utc = datetime.now(timezone.utc).isoformat()
        audit.latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "started_utc": started_utc,
            "finished_utc": audit.finished_utc,
            "credential_status": creds,
            "attempt_count": attempt_count,
            "error": str(exc),
        }, audit.ensure_safe()

    png_sha = hashlib.sha256(image_bytes).hexdigest()
    audit.input_summary = f"vision_input sha={file_sha256[:16]} page={page_used}"[:200]

    def _finish(status: str, **extra: Any) -> tuple[dict[str, Any], VisionCallAudit]:
        finished = datetime.now(timezone.utc).isoformat()
        audit.status = status  # type: ignore[assignment]
        audit.finished_utc = finished
        audit.latency_ms = (time.perf_counter() - started) * 1000.0
        payload = {
            "started_utc": started_utc,
            "finished_utc": finished,
            "credential_status": creds,
            "attempt_count": attempt_count,
            "input_sha256": file_sha256,
            "image_sha256": png_sha,
            **extra,
        }
        return payload, audit.ensure_safe()

    # Offline mock path for tests (explicit mock_response_json) — NOT actual.
    if mock_response_json is not None:
        audit.model = (
            resolve_vision_model()
            if creds["QWEN_VL_MODEL"] == "PRESENT"
            else "qwen2.5-vl-mock"
        )
        if simulate_error == "timeout":
            audit.error_type = "timeout"
            audit.timeout = True
            return _finish("failed", execution_mode="mock", timeout=True)
        if simulate_error == "auth":
            audit.error_type = "AuthenticationError"
            return _finish("failed", execution_mode="mock")
        content_sha = hashlib.sha256(mock_response_json.encode("utf-8")).hexdigest()
        audit.response_content_sha256 = content_sha
        try:
            artifact = parse_vision_chart_json(
                mock_response_json,
                source_path=source_path,
                source_type="pdf" if source_path.lower().endswith(".pdf") else "user_upload",
                page=page_used,
                file_sha256=file_sha256,
            )
        except ExtractionError as exc:
            audit.error_type = "invalid_or_empty_response"
            return _finish(
                "failed",
                execution_mode="mock",
                response_content_sha256=content_sha,
                parse_error=str(exc),
            )
        audit.actual_external_call = False
        return _finish(
            "success",
            execution_mode="mock",
            response_content_sha256=content_sha,
            artifact=artifact.model_dump(),
            tokens_in=None,
            tokens_out=None,
            service_reported_cost=None,
        )

    if not allow_actual or not paid_vision_authorized():
        audit.error_type = "paid_call_not_authorized_or_phase_gate"
        return _finish("denied_no_paid_auth", execution_mode="denied_no_paid_auth")

    # Actual path
    try:
        model = resolve_vision_model()
    except ExtractionError as exc:
        audit.error_type = "model_unspecified"
        return _finish("failed", error=str(exc), execution_mode="actual_external_call")
    audit.model = model

    if creds["DASHSCOPE_API_KEY"] == "MISSING" or creds["DASHSCOPE_BASE_URL"] == "MISSING":
        audit.error_type = "credential_missing"
        return _finish("failed", execution_mode="actual_external_call")

    settings = get_settings()
    from openai import OpenAI

    client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": schema["prompt_summary"]},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=max_output_tokens,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001
        audit.error_type = type(exc).__name__
        audit.actual_external_call = True
        return _finish(
            "failed",
            execution_mode="actual_external_call",
            error_type=type(exc).__name__,
        )

    usage = getattr(resp, "usage", None)
    tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
    tokens_out = getattr(usage, "completion_tokens", None) if usage else None
    content = ""
    try:
        content = resp.choices[0].message.content or ""
    except Exception:  # noqa: BLE001
        content = ""
    content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    audit.actual_external_call = True
    audit.tokens_in = int(tokens_in) if tokens_in is not None else None
    audit.tokens_out = int(tokens_out) if tokens_out is not None else None
    audit.cost_usd = None
    audit.service_reported_cost = None
    audit.response_id = getattr(resp, "id", None)
    audit.response_content_sha256 = content_sha
    try:
        artifact = parse_vision_chart_json(
            content,
            source_path=source_path,
            source_type="pdf" if source_path.lower().endswith(".pdf") else "user_upload",
            page=page_used,
            file_sha256=file_sha256,
        )
    except ExtractionError as exc:
        audit.error_type = "invalid_or_empty_response"
        return _finish(
            "failed",
            execution_mode="actual_external_call",
            response_id=audit.response_id,
            response_content_sha256=content_sha,
            parse_error=str(exc),
            tokens_in=audit.tokens_in,
            tokens_out=audit.tokens_out,
            service_reported_cost=None,
        )

    return _finish(
        "success",
        execution_mode="actual_external_call",
        response_id=audit.response_id,
        response_content_sha256=content_sha,
        artifact=artifact.model_dump(),
        tokens_in=audit.tokens_in,
        tokens_out=audit.tokens_out,
        service_reported_cost=None,
    )


# Compat alias
def run_qwen_vision_on_pdf_page(
    source_path: str,
    *,
    page: int = 1,
    max_output_tokens: int = 256,
    allow_actual: bool = False,
    **kwargs: Any,
) -> tuple[dict[str, Any], VisionCallAudit]:
    return run_qwen_vision(
        source_path,
        page=page,
        max_output_tokens=max_output_tokens,
        allow_actual=allow_actual,
        **kwargs,
    )
