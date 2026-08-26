"""幂等长任务命令：计算 idempotency_key，不另建平行 Job 系统。"""

from __future__ import annotations

import hashlib
import json

from app.api.contracts import JOB_TYPE_FULL_RESEARCH_PIPELINE

PIPELINE_VERSION = "v1"
ACTIVE_JOB_STATUSES = frozenset({"queued", "running", "retrying"})


def compute_idempotency_key(
    *,
    client_id: str,
    question_id: str,
    job_type: str = JOB_TYPE_FULL_RESEARCH_PIPELINE,
    input_digest: str = "",
    pipeline_version: str = PIPELINE_VERSION,
) -> str:
    """稳定、非敏感的幂等键；不包含 API Key / token。"""
    material = "|".join(
        (
            str(client_id or "").strip(),
            str(question_id or "").strip().upper(),
            str(job_type or JOB_TYPE_FULL_RESEARCH_PIPELINE).strip(),
            str(input_digest or "").strip(),
            str(pipeline_version or PIPELINE_VERSION).strip(),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def compute_input_digest(*, mode: str, options: dict | None = None) -> str:
    """稳定摘要：只序列化，绝不把 mode 与 options 放进同一个 sorted()。"""
    payload = {
        "mode": str(mode or ""),
        "options": {str(key): value for key, value in (options or {}).items()},
    }
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
