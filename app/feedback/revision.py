"""T03 sidecar bridge into T02 revision prompts without changing T02 models."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.contracts.revision import RevisionContext, RevisionPromptBuilder
from app.contracts.validation import (
    AuditLineage,
    AuditLineageEvent,
    FeedbackDecision,
    FeedbackRecord,
)
from app.feedback.errors import (
    FeedbackConflict,
    FeedbackStorageError,
    InvalidFeedbackInput,
)
from app.feedback.storage import FeedbackStore


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(_canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise InvalidFeedbackInput("revision prompt boundary requires JSON values") from exc


def _wire_payload(value: Any, *, label: str) -> dict[str, Any]:
    """Normalize a foreign Pydantic model or mapping through canonical JSON."""
    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        model_dump = getattr(value, "model_dump", None)
        if not callable(model_dump):
            raise InvalidFeedbackInput(f"{label} must be a mapping or model")
        payload = model_dump(mode="json")
    snapshot = _json_copy(payload)
    if not isinstance(snapshot, dict):
        raise InvalidFeedbackInput(f"{label} must serialize to an object")
    return snapshot


def _require_direct_child(source_version_id: str, resulting_version_id: str) -> None:
    source_run, source_marker, source_number = source_version_id.rpartition(":v")
    result_run, result_marker, result_number = resulting_version_id.rpartition(":v")
    if (
        source_marker != ":v"
        or result_marker != ":v"
        or not source_run
        or source_run != result_run
        or not source_number.isdigit()
        or not result_number.isdigit()
        or int(result_number) != int(source_number) + 1
    ):
        raise ValueError("resulting_version_id must directly follow source_version_id")


class RevisionExecutionMetadata(BaseModel):
    """T03 snapshot of T02's complete revision execution receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    feedback_id: str = Field(min_length=1)
    source_version_id: str = Field(min_length=1)
    resulting_version_id: str = Field(min_length=1)
    prompt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    diff_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    applied_instructions: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_direct_child(self) -> "RevisionExecutionMetadata":
        _require_direct_child(self.source_version_id, self.resulting_version_id)
        if any(not instruction.strip() for instruction in self.applied_instructions):
            raise ValueError("applied_instructions cannot contain blank values")
        return self


class RevisionLineageHandoffEvent(BaseModel):
    """Strict wire snapshot of one T02-owned revision lineage event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    event_type: Literal[
        "revision_requested",
        "revision_generated",
        "issue_closed",
    ]
    sequence: int = Field(ge=1)
    subject_id: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_event_id: str | None = None
    feedback_id: str = Field(min_length=1)
    source_version_id: str = Field(min_length=1)
    resulting_version_id: str = Field(min_length=1)


class RevisionLineageHandoff(BaseModel):
    """T03's strict consumer boundary for T02's append-ready handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    feedback_id: str = Field(min_length=1)
    source_version_id: str = Field(min_length=1)
    resulting_version_id: str = Field(min_length=1)
    prompt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_diff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_parent_event_type: Literal["feedback_decided"] = "feedback_decided"
    issue_ids: tuple[str, ...] = ()
    events: tuple[RevisionLineageHandoffEvent, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _validate_handoff(self) -> "RevisionLineageHandoff":
        _require_direct_child(self.source_version_id, self.resulting_version_id)
        event_ids = tuple(event.event_id for event in self.events)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("revision handoff event IDs must be unique")
        if tuple(event.sequence for event in self.events) != tuple(
            range(1, len(self.events) + 1)
        ):
            raise ValueError("revision handoff event sequence must be contiguous")
        if tuple(event.event_type for event in self.events[:2]) != (
            "revision_requested",
            "revision_generated",
        ):
            raise ValueError("revision handoff must start requested -> generated")
        if any(event.event_type != "issue_closed" for event in self.events[2:]):
            raise ValueError("only issue closure events may follow revision_generated")
        if self.events[0].parent_event_id is not None:
            raise ValueError("first T02 event must await T03 feedback_decided parent")
        for index, event in enumerate(self.events):
            if index and event.parent_event_id != self.events[index - 1].event_id:
                raise ValueError("revision handoff event parent chain is broken")
            if (
                event.feedback_id != self.feedback_id
                or event.source_version_id != self.source_version_id
                or event.resulting_version_id != self.resulting_version_id
            ):
                raise ValueError("revision handoff event identity mismatch")
        requested, generated = self.events[:2]
        if requested.subject_id != self.feedback_id:
            raise ValueError("revision_requested must reference feedback_id")
        if requested.payload_sha256 != self.prompt_fingerprint:
            raise ValueError("revision_requested hash must match prompt fingerprint")
        if generated.subject_id != self.resulting_version_id:
            raise ValueError("revision_generated must reference result version")
        if generated.payload_sha256 != self.revision_diff_sha256:
            raise ValueError("revision_generated hash must match structured diff")
        closed_ids = tuple(event.subject_id for event in self.events[2:])
        if closed_ids != self.issue_ids or len(closed_ids) != len(set(closed_ids)):
            raise ValueError("issue closure events must match unique issue_ids")
        return self


class RevisionLineageConsumer:
    """Validate and atomically persist one T02 revision lineage handoff."""

    def __init__(
        self,
        store: FeedbackStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _snapshot_handoff(value: Any) -> RevisionLineageHandoff:
        try:
            return RevisionLineageHandoff.model_validate(
                _wire_payload(value, label="revision_lineage_handoff")
            )
        except (ValidationError, ValueError) as exc:
            raise InvalidFeedbackInput(
                "revision_lineage_handoff is invalid"
            ) from exc

    @staticmethod
    def _snapshot_metadata(value: Any) -> RevisionExecutionMetadata:
        try:
            return RevisionExecutionMetadata.model_validate(
                _wire_payload(value, label="revision_metadata")
            )
        except (ValidationError, ValueError) as exc:
            raise InvalidFeedbackInput("revision_metadata is invalid") from exc

    @staticmethod
    def _validate_pair(
        handoff: RevisionLineageHandoff,
        metadata: RevisionExecutionMetadata,
    ) -> None:
        if (
            metadata.feedback_id != handoff.feedback_id
            or metadata.source_version_id != handoff.source_version_id
            or metadata.resulting_version_id != handoff.resulting_version_id
            or metadata.prompt_fingerprint != handoff.prompt_fingerprint
            or metadata.diff_hash != handoff.revision_diff_sha256
        ):
            raise FeedbackConflict(
                "revision metadata conflicts with revision lineage handoff"
            )

    def consume(
        self,
        revision_lineage_handoff: Any,
        *,
        revision_metadata: Any,
        actor_id: str,
        occurred_at: datetime | None = None,
    ) -> AuditLineage:
        """Bind T02 events to the real decision and persist the batch once."""
        handoff = self._snapshot_handoff(revision_lineage_handoff)
        metadata = self._snapshot_metadata(revision_metadata)
        self._validate_pair(handoff, metadata)
        normalized_actor = actor_id.strip()
        if not normalized_actor:
            raise InvalidFeedbackInput("revision lineage actor_id cannot be blank")

        lineage = self._store.get_lineage_by_feedback(handoff.feedback_id)
        decision = self._store.get_decision(handoff.feedback_id)
        if decision is None:
            raise FeedbackConflict(
                "revision handoff requires a persisted feedback decision"
            )
        if decision.disposition == "rejected":
            raise FeedbackConflict("rejected feedback cannot produce a revision")
        if tuple(decision.accepted_items) != metadata.applied_instructions:
            raise FeedbackConflict(
                "revision metadata instructions differ from the persisted decision"
            )
        if (
            lineage.feedback_id != handoff.feedback_id
            or lineage.target_version_id != handoff.source_version_id
            or decision.target_version_id != handoff.source_version_id
        ):
            raise FeedbackConflict(
                "revision handoff source does not match persisted feedback"
            )
        if (
            lineage.decision_id != decision.decision_id
            or lineage.decision_disposition != decision.disposition
            or lineage.decision_sha256 != decision.fingerprint()
        ):
            raise FeedbackConflict(
                "persisted decision is not bound to the feedback lineage"
            )
        if lineage.resulting_version_id not in {
            None,
            handoff.resulting_version_id,
        } or lineage.revision_diff_sha256 not in {
            None,
            handoff.revision_diff_sha256,
        }:
            raise FeedbackConflict("lineage already contains another revision")
        if tuple(handoff.issue_ids[: len(lineage.issue_ids)]) != lineage.issue_ids:
            raise FeedbackConflict(
                "revision handoff conflicts with persisted issue history"
            )

        decision_events = tuple(
            event
            for event in lineage.events
            if event.event_type == handoff.required_parent_event_type
        )
        if len(decision_events) != 1:
            raise FeedbackConflict(
                "revision handoff requires one real feedback_decided event"
            )
        decision_event = decision_events[0]
        incoming_ids = {event.event_id for event in handoff.events}
        if (
            not incoming_ids.intersection(event.event_id for event in lineage.events)
            and lineage.events[-1].event_id != decision_event.event_id
        ):
            raise FeedbackConflict(
                "revision handoff cannot be inserted after later audit events"
            )

        timestamp = occurred_at or self._clock()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise InvalidFeedbackInput("revision lineage occurred_at needs a timezone")
        if timestamp < decision_event.occurred_at:
            raise InvalidFeedbackInput(
                "revision lineage cannot predate feedback_decided"
            )
        # An older one-event writer may have left a valid handoff prefix.  The
        # remaining events must not move backwards relative to that first write.
        timestamp = max(timestamp, lineage.events[-1].occurred_at)

        revision_metadata_payload = metadata.model_dump(mode="json")
        events: list[AuditLineageEvent] = []
        for event in handoff.events:
            audit_metadata: dict[str, Any] = {
                "handoff_source": "T02",
                "handoff_schema_version": handoff.schema_version,
                "handoff_sequence": event.sequence,
                "feedback_id": handoff.feedback_id,
                "source_version_id": handoff.source_version_id,
                "resulting_version_id": handoff.resulting_version_id,
                "t02_parent_event_id": event.parent_event_id,
            }
            if event.event_type == "revision_requested":
                audit_metadata.update(
                    {
                        "required_parent_event_type": (
                            handoff.required_parent_event_type
                        ),
                        "prompt_fingerprint": handoff.prompt_fingerprint,
                        "revision_metadata": revision_metadata_payload,
                    }
                )
            elif event.event_type == "revision_generated":
                audit_metadata.update(
                    {
                        "revision_diff_sha256": handoff.revision_diff_sha256,
                        "revision_metadata": revision_metadata_payload,
                    }
                )
            else:
                audit_metadata["issue_id"] = event.subject_id

            events.append(
                AuditLineageEvent(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    occurred_at=timestamp,
                    actor_id=normalized_actor,
                    subject_id=event.subject_id,
                    payload_sha256=event.payload_sha256,
                    parent_event_id=(
                        decision_event.event_id
                        if event.sequence == 1
                        else event.parent_event_id
                    ),
                    metadata=audit_metadata,
                )
            )

        append_batch = getattr(
            self._store,
            "append_lineage_events_atomically",
            None,
        )
        if not callable(append_batch):
            raise FeedbackStorageError(
                "feedback store lacks atomic revision handoff support"
            )
        persisted = append_batch(lineage.lineage_id, tuple(events))
        if (
            persisted.resulting_version_id != handoff.resulting_version_id
            or persisted.revision_diff_sha256 != handoff.revision_diff_sha256
            or persisted.issue_ids != handoff.issue_ids
        ):
            raise FeedbackConflict(
                "persisted lineage does not match the complete revision handoff"
            )
        return persisted


class RevisionFeedbackContext(BaseModel):
    """Auditable sidecar for one T03 decision applied to a T02 revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    feedback_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    source_version_id: str = Field(min_length=1)
    original_version_id: str = Field(min_length=1)
    disposition: Literal["accepted", "partially_accepted", "rejected"]
    decision_reason: str = Field(min_length=1)
    accepted_items: tuple[str, ...] = Field(default_factory=tuple)
    rejected_items: tuple[str, ...] = Field(default_factory=tuple)
    original_feedback_sha256: str

    @model_validator(mode="after")
    def _validate_decision_shape(self) -> "RevisionFeedbackContext":
        if self.source_version_id != self.original_version_id:
            raise ValueError("source_version_id must equal original_version_id")
        if not _SHA256.fullmatch(self.original_feedback_sha256):
            raise ValueError("original_feedback_sha256 must be lowercase SHA-256")
        if self.disposition == "accepted":
            if not self.accepted_items or self.rejected_items:
                raise ValueError("accepted feedback context has invalid item sets")
        elif self.disposition == "partially_accepted":
            if not self.accepted_items or not self.rejected_items:
                raise ValueError("partial feedback context requires both item sets")
        elif self.accepted_items or not self.rejected_items:
            raise ValueError("rejected feedback context has invalid item sets")
        return self

    @property
    def should_resume(self) -> bool:
        return self.disposition in {"accepted", "partially_accepted"}

    def to_revision_metadata(
        self,
        *,
        prompt_payload: Mapping[str, Any],
        diff_hash: str | None = None,
    ) -> dict[str, Any]:
        """Build the validation receipt expected in execution metadata."""
        if not self.should_resume:
            raise InvalidFeedbackInput(
                "rejected feedback cannot produce revision metadata"
            )
        prompt_copy = _json_copy(dict(prompt_payload))
        if diff_hash is not None and _SHA256.fullmatch(diff_hash) is None:
            raise InvalidFeedbackInput("diff_hash must be lowercase SHA-256")
        return {
            "feedback_id": self.feedback_id,
            "source_version_id": self.source_version_id,
            "prompt_fingerprint": hashlib.sha256(
                _canonical_json(prompt_copy).encode("utf-8")
            ).hexdigest(),
            "diff_hash": diff_hash,
            "applied_instructions": list(self.accepted_items),
        }


class RevisionFeedbackContextBuilder:
    """Create a v1 sidecar from separately persisted record and decision."""

    @staticmethod
    def build(
        record: FeedbackRecord,
        decision: FeedbackDecision,
    ) -> RevisionFeedbackContext:
        try:
            record_snapshot = FeedbackRecord.model_validate_json(
                _canonical_json(record.model_dump(mode="json"))
            )
            decision_snapshot = FeedbackDecision.model_validate_json(
                _canonical_json(decision.model_dump(mode="json"))
            )
        except (ValidationError, ValueError, AttributeError) as exc:
            raise InvalidFeedbackInput("feedback decision boundary is invalid") from exc
        if record_snapshot.feedback_id != decision_snapshot.feedback_id:
            raise FeedbackConflict("decision references another feedback record")
        if record_snapshot.target_version_id != decision_snapshot.target_version_id:
            raise FeedbackConflict("decision references another source version")
        payload = {
            "schema_version": 1,
            "feedback_id": record_snapshot.feedback_id,
            "decision_id": decision_snapshot.decision_id,
            "run_id": record_snapshot.run_id,
            "question_id": record_snapshot.question_id,
            "source_version_id": record_snapshot.target_version_id,
            "original_version_id": record_snapshot.target_version_id,
            "disposition": decision_snapshot.disposition,
            "decision_reason": decision_snapshot.decision_reason,
            "accepted_items": list(decision_snapshot.accepted_items),
            "rejected_items": list(decision_snapshot.rejected_items),
            "original_feedback_sha256": hashlib.sha256(
                record_snapshot.feedback.encode("utf-8")
            ).hexdigest(),
        }
        try:
            # JSON round-trip is intentional: this object crosses T03 -> T02.
            return RevisionFeedbackContext.model_validate_json(
                _canonical_json(payload)
            )
        except (ValidationError, ValueError) as exc:
            raise InvalidFeedbackInput("revision feedback context is invalid") from exc


class RevisionPromptAdapter:
    """Inject accepted instructions into complete T02 prompt inputs."""

    @staticmethod
    def inject(
        prompt_payload: Mapping[str, Any],
        feedback_context: RevisionFeedbackContext,
    ) -> dict[str, Any]:
        try:
            context = RevisionFeedbackContext.model_validate_json(
                _canonical_json(feedback_context.model_dump(mode="json"))
            )
        except (ValidationError, ValueError) as exc:
            raise InvalidFeedbackInput("revision feedback context is invalid") from exc
        payload = _json_copy(dict(prompt_payload))
        if not context.should_resume:
            # A rejected decision remains in the sidecar/audit store only.
            return payload
        if "human_feedback" in payload:
            raise FeedbackConflict("prompt already contains human_feedback")
        payload["human_feedback"] = {
            "schema_version": 1,
            "feedback_id": context.feedback_id,
            "source_version_id": context.source_version_id,
            "disposition": context.disposition,
            "applied_instructions": list(context.accepted_items),
            "original_feedback_sha256": context.original_feedback_sha256,
        }
        # Rejected items, raw feedback and policy reason never cross this boundary.
        return _json_copy(payload)

    @classmethod
    def build_hypothesis_input(
        cls,
        revision_context: RevisionContext,
        feedback_context: RevisionFeedbackContext,
        *,
        question_item: Mapping[str, Any],
        evidence_catalog: Sequence[Mapping[str, Any]],
        evidence_extraction: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        base = RevisionPromptBuilder.build_hypothesis_input(
            revision_context,
            question_item=question_item,
            evidence_catalog=evidence_catalog,
            evidence_extraction=evidence_extraction,
        )
        return cls.inject(base, feedback_context)

    @classmethod
    def build_experiment_input(
        cls,
        revision_context: RevisionContext,
        feedback_context: RevisionFeedbackContext,
        *,
        question_item: Mapping[str, Any],
        question_type: str,
        recommended_hypothesis: Mapping[str, Any],
        hypothesis_generation: Mapping[str, Any] | None,
        evidence_extraction: Mapping[str, Any] | None,
        evidence_catalog: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        base = RevisionPromptBuilder.build_experiment_input(
            revision_context,
            question_item=question_item,
            question_type=question_type,
            recommended_hypothesis=recommended_hypothesis,
            hypothesis_generation=hypothesis_generation,
            evidence_extraction=evidence_extraction,
            evidence_catalog=evidence_catalog,
        )
        return cls.inject(base, feedback_context)

    @classmethod
    def build_reviewer_input(
        cls,
        revision_context: RevisionContext,
        feedback_context: RevisionFeedbackContext,
        *,
        question_item: Mapping[str, Any],
        recommended_hypothesis: Mapping[str, Any],
        hypothesis_generation: Mapping[str, Any] | None,
        experiment_design: Mapping[str, Any] | None,
        evidence_extraction: Mapping[str, Any] | None,
        evidence_catalog: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        base = RevisionPromptBuilder.build_reviewer_input(
            revision_context,
            question_item=question_item,
            recommended_hypothesis=recommended_hypothesis,
            hypothesis_generation=hypothesis_generation,
            experiment_design=experiment_design,
            evidence_extraction=evidence_extraction,
            evidence_catalog=evidence_catalog,
        )
        return cls.inject(base, feedback_context)

    @staticmethod
    def build_execution_metadata(
        execution_metadata: Mapping[str, Any],
        feedback_context: RevisionFeedbackContext,
        *,
        prompt_payload: Mapping[str, Any],
        diff_hash: str | None = None,
    ) -> dict[str, Any]:
        """Attach the exact revision receipt consumed by T03 quality gates."""
        metadata = _json_copy(dict(execution_metadata))
        if "revision_metadata" in metadata:
            raise FeedbackConflict("execution metadata already has revision_metadata")
        metadata["revision_metadata"] = feedback_context.to_revision_metadata(
            prompt_payload=prompt_payload,
            diff_hash=diff_hash,
        )
        return _json_copy(metadata)


# Concise alias for integrations that use "builder" terminology.
FeedbackPromptAdapter = RevisionPromptAdapter


__all__ = [
    "FeedbackPromptAdapter",
    "RevisionExecutionMetadata",
    "RevisionFeedbackContext",
    "RevisionFeedbackContextBuilder",
    "RevisionLineageConsumer",
    "RevisionLineageHandoff",
    "RevisionLineageHandoffEvent",
    "RevisionPromptAdapter",
]
