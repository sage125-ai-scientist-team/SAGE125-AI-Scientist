"""
Qwen 视觉调用路径（canonical：百炼 OpenAI-compatible + assert_qwen_model）。

凭证只读环境变量名：DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL / QWEN_VL_MODEL。
本模块不打印密钥值。
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.config import assert_qwen_model, get_settings
from app.multimodal.audit import VisionCallAudit, paid_vision_authorized
from app.multimodal.errors import ExtractionError
from app.multimodal.pdf_io import load_source_bytes, open_pdf, render_page_png_bytes


def credential_status() -> dict[str, str]:
    """Return PRESENT/MISSING only — never values."""
    key = "PRESENT" if os.environ.get("DASHSCOPE_API_KEY", "").strip() else "MISSING"
    base = "PRESENT" if os.environ.get("DASHSCOPE_BASE_URL", "").strip() else "MISSING"
    model = "PRESENT" if os.environ.get("QWEN_VL_MODEL", "").strip() else "MISSING"
    return {
        "DASHSCOPE_API_KEY": key,
        "DASHSCOPE_BASE_URL": base,
        "QWEN_VL_MODEL": model,
    }


def resolve_vision_model() -> str:
    settings = get_settings()
    model = os.environ.get("QWEN_VL_MODEL", "").strip() or settings.qwen_balanced_model
    return assert_qwen_model(model)


def build_vision_prompt_schema() -> dict[str, str]:
    return {
        "prompt_schema_version": "t06-vision-v1",
        "prompt_summary": (
            "Extract chart axes units legend and numeric series points as JSON; "
            "do not invent values; mark low confidence."
        ),
    }


def run_qwen_vision_on_pdf_page(
    source_path: str,
    *,
    page: int = 1,
    max_output_tokens: int = 256,
    allow_actual: bool = False,
) -> tuple[dict[str, Any], VisionCallAudit]:
    """
    Execute or deny a vision call.

    allow_actual must be True AND paid_vision_authorized() AND credentials present.
    Phase-1 / Case A callers keep allow_actual=False.
    """
    started = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    meta = load_source_bytes(source_path)
    schema = build_vision_prompt_schema()
    model = resolve_vision_model()
    input_summary = f"pdf_page path_sha={meta.sha256[:16]} page={page}"
    audit = VisionCallAudit(
        call_id=str(uuid.uuid4()),
        provider="dashscope-openai-compatible",
        model=model,
        prompt_schema_version=schema["prompt_schema_version"],
        status="denied_no_paid_auth",
        input_summary=input_summary[:200],
        key_masked=True,
        actual_external_call=False,
    )

    creds = credential_status()
    if not allow_actual or not paid_vision_authorized():
        audit.status = "denied_no_paid_auth"
        audit.error_type = "paid_call_not_authorized_or_phase_gate"
        audit.latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "credential_status": creds,
            "input_sha256": meta.sha256,
        }, audit.ensure_safe()

    if creds["DASHSCOPE_API_KEY"] == "MISSING" or creds["DASHSCOPE_BASE_URL"] == "MISSING":
        audit.status = "failed"
        audit.error_type = "credential_missing"
        audit.latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "credential_status": creds,
            "input_sha256": meta.sha256,
        }, audit.ensure_safe()

    # Actual path — only when explicitly allowed by phase gates.
    settings = get_settings()
    if not settings.qwen_configured:
        audit.status = "failed"
        audit.error_type = "qwen_not_configured"
        audit.latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "credential_status": creds,
            "input_sha256": meta.sha256,
        }, audit.ensure_safe()

    doc = open_pdf(source_path)
    try:
        png = render_page_png_bytes(doc, page, dpi=96)
    finally:
        doc.close()
    png_sha = hashlib.sha256(png).hexdigest()

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("openai client missing") from exc

    client = OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)
    # Keep image out of logs; only send to API.
    import base64

    b64 = base64.standard_b64encode(png).decode("ascii")
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
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=max_output_tokens,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001
        audit.status = "failed"
        audit.error_type = type(exc).__name__
        audit.latency_ms = (time.perf_counter() - started) * 1000.0
        audit.actual_external_call = True
        return {
            "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "credential_status": creds,
            "input_sha256": meta.sha256,
            "png_sha256": png_sha,
            "error_type": type(exc).__name__,
        }, audit.ensure_safe()

    usage = getattr(resp, "usage", None)
    tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
    tokens_out = getattr(usage, "completion_tokens", None) if usage else None
    content = ""
    try:
        content = resp.choices[0].message.content or ""
    except Exception:  # noqa: BLE001
        content = ""
    content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    audit.status = "success"
    audit.actual_external_call = True
    audit.latency_ms = (time.perf_counter() - started) * 1000.0
    audit.tokens_in = int(tokens_in) if tokens_in is not None else None
    audit.tokens_out = int(tokens_out) if tokens_out is not None else None
    # cost unknown unless provider returns it — do not invent
    audit.cost_usd = None
    return {
        "started_utc": started_utc,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "credential_status": creds,
        "input_sha256": meta.sha256,
        "png_sha256": png_sha,
        "response_id": getattr(resp, "id", None),
        "response_content_sha256": content_sha,
        "response_chars": len(content),
        "tokens_in": audit.tokens_in,
        "tokens_out": audit.tokens_out,
        "service_reported_cost": None,
    }, audit.ensure_safe()
