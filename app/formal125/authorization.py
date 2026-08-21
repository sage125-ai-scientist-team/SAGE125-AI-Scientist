"""Captain authorization gate for formal 125 actual runs.

Dry-run does not require an authorization file. Actual runs without a valid
authorization file must exit non-zero and must not call a provider.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field, field_validator


AUTHORIZATION_SCHEMA_ID = "formal125.run-authorization.v1"
REQUIRED_ROLE = "captain"


class Formal125AuthorizationError(RuntimeError):
    """Raised when an actual run is missing or has an invalid authorization."""


class Formal125RunAuthorization(BaseModel):
    authorization_id: str = Field(min_length=8)
    authorized_by_role: str
    authorized_case_ids: list[str] = Field(min_length=1)
    provider: str
    model_lock_hash: str = Field(min_length=64, max_length=64)
    prompt_lock_hash: str = Field(min_length=64, max_length=64)
    schema_lock_hash: str = Field(min_length=64, max_length=64)
    catalog_hash: str = Field(min_length=64, max_length=64)
    max_total_provider_calls: int = Field(gt=0)
    max_retries: int = Field(ge=0)
    max_total_input_tokens: int = Field(gt=0)
    max_total_output_tokens: int = Field(gt=0)
    max_concurrency: int = Field(ge=1)
    output_root: str = Field(min_length=1)
    expires_at: str = Field(min_length=10)
    authorization_hash: str = Field(min_length=64, max_length=64)

    @field_validator("authorized_by_role")
    @classmethod
    def _captain_only(cls, value: str) -> str:
        if value != REQUIRED_ROLE:
            raise ValueError("authorized_by_role must be captain")
        return value

    @field_validator("provider")
    @classmethod
    def _bailian_only(cls, value: str) -> str:
        if value != "bailian":
            raise ValueError("provider must be bailian")
        return value


def authorization_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": AUTHORIZATION_SCHEMA_ID,
        "title": "Formal 125 captain actual-run authorization",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "authorization_id",
            "authorized_by_role",
            "authorized_case_ids",
            "provider",
            "model_lock_hash",
            "prompt_lock_hash",
            "schema_lock_hash",
            "catalog_hash",
            "max_total_provider_calls",
            "max_retries",
            "max_total_input_tokens",
            "max_total_output_tokens",
            "max_concurrency",
            "output_root",
            "expires_at",
            "authorization_hash",
        ],
        "properties": {
            "authorization_id": {"type": "string", "minLength": 8},
            "authorized_by_role": {"const": "captain"},
            "authorized_case_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "pattern": "^Q[0-9]{3}$"},
            },
            "provider": {"const": "bailian"},
            "model_lock_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "prompt_lock_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "schema_lock_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "catalog_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "max_total_provider_calls": {"type": "integer", "minimum": 1},
            "max_retries": {"type": "integer", "minimum": 0},
            "max_total_input_tokens": {"type": "integer", "minimum": 1},
            "max_total_output_tokens": {"type": "integer", "minimum": 1},
            "max_concurrency": {"type": "integer", "minimum": 1},
            "output_root": {"type": "string", "minLength": 1},
            "expires_at": {"type": "string", "minLength": 10},
            "authorization_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
    }


def compute_authorization_hash(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "authorization_hash"}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_authorization(path: Path) -> Formal125RunAuthorization:
    if not path.is_file():
        raise Formal125AuthorizationError(
            f"actual run authorization file is missing: {path}"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Formal125AuthorizationError("authorization must be a JSON object")
    expected = compute_authorization_hash(payload)
    actual = str(payload.get("authorization_hash") or "")
    if actual != expected:
        raise Formal125AuthorizationError("authorization_hash mismatch")
    auth = Formal125RunAuthorization.model_validate(payload)
    expires = datetime.fromisoformat(auth.expires_at.replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        raise Formal125AuthorizationError("authorization has expired")
    return auth


def require_actual_authorization(path: Path | None) -> Formal125RunAuthorization:
    """Fail closed before any provider boundary is crossed."""

    if path is None:
        raise Formal125AuthorizationError(
            "actual run requires a captain authorization file"
        )
    return load_authorization(path)


def blocked_actual_run_exit(
    *,
    authorization_path: Path | None,
    stream=None,
) -> int:
    """Return a non-zero exit code without creating official outputs."""

    try:
        require_actual_authorization(authorization_path)
    except Formal125AuthorizationError as exc:
        print(f"ACTUAL_RUN_BLOCKED={exc}", file=stream or sys.stderr)
        print("PROVIDER_CALLS=0", file=stream or sys.stderr)
        print("OFFICIAL_RESULTS=0", file=stream or sys.stderr)
        return 2
    return 0
