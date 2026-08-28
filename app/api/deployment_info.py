"""Read-only deployment identity. Never include secrets."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from app.catalog.official import load_official_catalog

_STARTED_AT = datetime.now(timezone.utc).isoformat()
_FORBIDDEN_FRAGMENTS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
    "cookie",
    "workspace_id",
    "dashscope",
)


def _safe_env(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    lowered = value.lower()
    if any(fragment in lowered for fragment in _FORBIDDEN_FRAGMENTS):
        return ""
    return value


def deployment_info_payload() -> dict[str, str | int]:
    try:
        catalog = load_official_catalog()
        digest = catalog.get_catalog_digest()
        count = len(catalog.list_questions())
    except Exception:
        digest = ""
        count = 0
    payload = {
        "environment": _safe_env("APP_ENV"),
        "service_name": _safe_env("RENDER_SERVICE_NAME"),
        "external_url": _safe_env("RENDER_EXTERNAL_URL"),
        "git_branch": _safe_env("RENDER_GIT_BRANCH"),
        "git_commit": _safe_env("RENDER_GIT_COMMIT"),
        "repo_slug": _safe_env("RENDER_GIT_REPO_SLUG"),
        "app_version": _safe_env("RENDER_GIT_COMMIT") or _safe_env("APP_VERSION"),
        "catalog_digest": digest,
        "question_count": count,
        "started_at": _STARTED_AT,
    }
    blob = " ".join(str(value) for value in payload.values()).lower()
    if any(fragment in blob for fragment in _FORBIDDEN_FRAGMENTS):
        raise RuntimeError("deployment-info attempted to emit a sensitive field")
    return payload
