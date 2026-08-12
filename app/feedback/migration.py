"""Fail-closed import of legacy feedback into unverified T03 lineage."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.contracts.validation import AuditLineage, AuditLineageEvent, FeedbackRecord
from app.feedback.errors import InvalidFeedbackInput
from app.feedback.storage import FeedbackStore


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _load(payload: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        raw = json.loads(payload) if isinstance(payload, str) else dict(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise InvalidFeedbackInput("legacy feedback must be a JSON object") from exc
    if not isinstance(raw, dict):
        raise InvalidFeedbackInput("legacy feedback must be a JSON object")
    return raw


def _legacy_time(value: Any) -> datetime:
    if value is None:
        # A fixed timestamp keeps repeated imports byte-for-byte idempotent.
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    if not isinstance(value, str):
        raise InvalidFeedbackInput("legacy submitted_at must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidFeedbackInput("legacy submitted_at is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidFeedbackInput("legacy submitted_at must include a timezone")
    return parsed


def migrate_legacy_feedback_payload(
    payload: str | bytes | Mapping[str, Any],
) -> tuple[FeedbackRecord, AuditLineage]:
    """Convert one untrusted legacy object to an explicitly unverified lineage.

    No decision or validation state is inferred. In particular, legacy booleans
    such as ``accepted`` or ``passed`` are intentionally ignored.
    """
    raw = _load(payload)
    try:
        schema_version = int(raw.get("schema_version", 0))
    except (TypeError, ValueError) as exc:
        raise InvalidFeedbackInput("legacy schema_version is invalid") from exc
    if schema_version < 0:
        raise InvalidFeedbackInput("legacy schema_version is invalid")
    if schema_version > 1:
        raise InvalidFeedbackInput("future feedback schema_version is unsupported")

    run_id = str(raw.get("run_id") or "").strip()
    question_id = str(raw.get("question_id") or raw.get("question") or "").strip()
    target_version_id = str(
        raw.get("target_version_id") or raw.get("version_id") or ""
    ).strip()
    feedback = str(
        raw.get("feedback")
        or raw.get("text")
        or raw.get("reviewer_feedback")
        or ""
    ).strip()
    for label, value in (("run_id", run_id), ("question_id", question_id)):
        if _SAFE_ID.fullmatch(value) is None:
            raise InvalidFeedbackInput(f"legacy {label} is invalid")
    expected_prefix = f"{run_id}:v"
    suffix = (
        target_version_id[len(expected_prefix) :]
        if target_version_id.startswith(expected_prefix)
        else ""
    )
    if not suffix.isdigit() or int(suffix) < 1:
        raise InvalidFeedbackInput("legacy target_version_id is invalid")
    if not feedback:
        raise InvalidFeedbackInput("legacy feedback cannot be empty")
    if len(feedback) > 10_000:
        raise InvalidFeedbackInput("legacy feedback exceeds the length limit")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in feedback):
        raise InvalidFeedbackInput("legacy feedback contains control characters")

    actor_id = str(raw.get("actor_id") or raw.get("reviewer_id") or "legacy-import").strip()
    if _SAFE_ID.fullmatch(actor_id) is None:
        actor_id = "legacy-import"
    submitted_at = _legacy_time(raw.get("submitted_at") or raw.get("created_at"))
    semantic_request = {
        "schema_version": 1,
        "run_id": run_id,
        "question_id": question_id,
        "target_version_id": target_version_id,
        "feedback": feedback,
        "source": {"channel": "migration", "actor_id": actor_id},
        "metadata": {"legacy_schema_version": schema_version, "verified": False},
    }
    request_fingerprint = hashlib.sha256(
        _canonical_json(semantic_request).encode("utf-8")
    ).hexdigest()
    digest = hashlib.sha256(
        ("legacy-feedback\n" + _canonical_json(semantic_request)).encode("utf-8")
    ).hexdigest()
    correlation_id = str(raw.get("correlation_id") or "").strip()
    if not correlation_id:
        correlation_id = f"corr-migration-{digest[:20]}"
    elif _SAFE_ID.fullmatch(correlation_id) is None:
        raise InvalidFeedbackInput("legacy correlation_id is invalid")
    legacy_record_id = raw.get("feedback_id") or raw.get("id")
    metadata: dict[str, Any] = {
        "legacy_schema_version": schema_version,
        "verified": False,
    }
    if legacy_record_id is not None:
        metadata["legacy_record_id"] = str(legacy_record_id)[:256]

    try:
        record = FeedbackRecord(
            feedback_id=f"feedback-migration-{digest[:20]}",
            run_id=run_id,
            question_id=question_id,
            target_version_id=target_version_id,
            feedback=feedback,
            source={"channel": "migration", "actor_id": actor_id},
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            request_fingerprint=request_fingerprint,
            metadata=metadata,
        )
        event = AuditLineageEvent(
            event_id=f"event-migration-{digest[:20]}",
            event_type="legacy_unverified",
            occurred_at=submitted_at,
            actor_id="t03-legacy-importer",
            subject_id=record.feedback_id,
            payload_sha256=record.fingerprint(),
            metadata={
                "verified": False,
                "source_schema_version": schema_version,
            },
        )
        lineage = AuditLineage(
            lineage_id=f"lineage-migration-{digest[:20]}",
            run_id=record.run_id,
            question_id=record.question_id,
            feedback_id=record.feedback_id,
            feedback_sha256=record.fingerprint(),
            target_version_id=record.target_version_id,
            correlation_id=record.correlation_id,
            events=(event,),
        )
        # Enforce the same v1 JSON boundary used by live submissions.
        record = FeedbackRecord.model_validate_json(
            _canonical_json(record.model_dump(mode="json"))
        )
        lineage = AuditLineage.model_validate_json(
            _canonical_json(lineage.model_dump(mode="json"))
        )
    except (ValidationError, ValueError) as exc:
        raise InvalidFeedbackInput("legacy feedback cannot be migrated safely") from exc
    return record, lineage


def import_legacy_feedback(
    payload: str | bytes | Mapping[str, Any],
    store: FeedbackStore,
) -> tuple[FeedbackRecord, AuditLineage]:
    """Migrate and persist without ever creating a decision or pass state."""
    record, lineage = migrate_legacy_feedback_payload(payload)
    atomic_save = getattr(store, "save_submission", None)
    if callable(atomic_save):
        return atomic_save(record, lineage)
    saved_record = store.save_feedback(record)
    if saved_record.feedback_id != record.feedback_id:
        return saved_record, store.get_lineage_by_feedback(saved_record.feedback_id)
    return saved_record, store.save_lineage(lineage)


# Alternate name used by migration runners.
migrate_legacy_feedback = migrate_legacy_feedback_payload


__all__ = [
    "import_legacy_feedback",
    "migrate_legacy_feedback",
    "migrate_legacy_feedback_payload",
]
