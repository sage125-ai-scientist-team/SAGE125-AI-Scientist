"""Application port and default T03 human-feedback processing service."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from app.contracts.validation import (
    AuditLineage,
    AuditLineageEvent,
    FeedbackDecision,
    FeedbackRecord,
    FeedbackSource,
    HumanFeedbackDirective,
)
from app.feedback.errors import (
    FeedbackConflict,
    FeedbackPermissionDenied,
    InvalidFeedbackInput,
)
from app.feedback.storage import FeedbackStore


@runtime_checkable
class FeedbackService(Protocol):
    """Wave B service contract consumed by T02 and T08."""

    def submit(self, record: FeedbackRecord) -> FeedbackRecord:
        """Validate and persist a feedback submission."""
        ...

    def decide(
        self,
        feedback_id: str,
        decision: FeedbackDecision,
    ) -> FeedbackDecision:
        """Record an accept/partial/reject decision."""
        ...

    def build_directive(
        self,
        feedback_id: str,
    ) -> HumanFeedbackDirective | None:
        """Return accepted prompt instructions; rejected feedback yields ``None``."""
        ...

    def consume_revision_lineage_handoff(
        self,
        revision_lineage_handoff: Any,
        *,
        revision_metadata: Any,
        actor_id: str,
        occurred_at: datetime | None = None,
    ) -> AuditLineage:
        """Atomically persist T02 revision events after a real decision."""
        ...


class FeedbackSubmission(BaseModel):
    """Transport-neutral request used to create a frozen ``FeedbackRecord``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str
    question_id: str
    target_version_id: str
    feedback: str
    source: FeedbackSource
    correlation_id: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


@runtime_checkable
class FeedbackAuthorizer(Protocol):
    """Explicit permission decision required before submission or decision."""

    def authorize(
        self,
        *,
        action: Literal["submit", "decide"],
        actor_id: str,
        run_id: str,
        question_id: str,
    ) -> bool:
        ...


class DenyAllFeedbackAuthorizer:
    """Secure default when the deployment has not supplied an authorizer."""

    def authorize(
        self,
        *,
        action: Literal["submit", "decide"],
        actor_id: str,
        run_id: str,
        question_id: str,
    ) -> bool:
        del action, actor_id, run_id, question_id
        return False


class AllowAllFeedbackAuthorizer:
    """Explicit opt-in helper for trusted local jobs and tests."""

    def authorize(
        self,
        *,
        action: Literal["submit", "decide"],
        actor_id: str,
        run_id: str,
        question_id: str,
    ) -> bool:
        del action, actor_id, run_id, question_id
        return True


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")
_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in (
        r"\bignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+instructions?\b",
        r"\b(?:reveal|print|show|leak)\s+(?:the\s+)?(?:system|developer)\s+prompt\b",
        r"\b(?:jailbreak|do\s+anything\s+now|developer\s+message)\b",
        r"<\|\s*(?:system|assistant|developer)\s*\|>",
        r"\[\s*INST\s*\]|#{2,}\s*(?:system|developer)\b",
        r"(?:\u5ffd\u7565|\u65e0\u89c6|\u9057\u5fd8).{0,20}"
        r"(?:\u4e4b\u524d|\u4e0a\u9762|\u6240\u6709).{0,12}"
        r"(?:\u6307\u4ee4|\u8981\u6c42|\u89c4\u5219)",
        r"(?:\u663e\u793a|\u6cc4\u9732|\u8f93\u51fa).{0,16}"
        r"(?:\u7cfb\u7edf\u63d0\u793a\u8bcd|\u5f00\u53d1\u8005\u6d88\u606f)",
        r"\bDAN\s+mode\b|\u8d8a\u72f1\u6a21\u5f0f",
    )
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _has_forbidden_control(value: str) -> bool:
    # Keep ordinary multiline feedback usable; reject NUL, C1, bidi and other
    # invisible controls that can change parser or reviewer interpretation.
    allowed = {"\t", "\n", "\r"}
    return any(
        character not in allowed
        and (
            unicodedata.category(character) in {"Cc", "Cf"}
            or ord(character) == 127
        )
        for character in value
    )


def _is_prompt_injection(value: str) -> bool:
    return any(pattern.search(value) is not None for pattern in _INJECTION_PATTERNS)


class DefaultFeedbackService:
    """Secure feedback lifecycle with idempotent persistence and audit events."""

    def __init__(
        self,
        store: FeedbackStore,
        *,
        authorizer: FeedbackAuthorizer
        | Callable[..., bool]
        | None = None,
        max_feedback_length: int = 10_000,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if max_feedback_length < 1:
            raise ValueError("max_feedback_length must be positive")
        self.store = store
        self.authorizer = authorizer or DenyAllFeedbackAuthorizer()
        self.max_feedback_length = max_feedback_length
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidFeedbackInput("service clock must return a timezone-aware time")
        return value

    def _authorize(
        self,
        *,
        action: Literal["submit", "decide"],
        actor_id: str,
        run_id: str,
        question_id: str,
    ) -> None:
        authorizer = self.authorizer
        try:
            if hasattr(authorizer, "authorize"):
                allowed = authorizer.authorize(
                    action=action,
                    actor_id=actor_id,
                    run_id=run_id,
                    question_id=question_id,
                )
            else:
                allowed = authorizer(
                    action=action,
                    actor_id=actor_id,
                    run_id=run_id,
                    question_id=question_id,
                )
        except FeedbackPermissionDenied:
            raise
        except Exception as exc:
            raise FeedbackPermissionDenied("feedback authorization failed") from exc
        if allowed is not True:
            raise FeedbackPermissionDenied("actor is not authorized for feedback action")

    @staticmethod
    def _require_safe_id(label: str, value: str) -> None:
        if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
            raise InvalidFeedbackInput(f"{label} is invalid")

    def _validate_text_and_ids(
        self,
        *,
        run_id: str,
        question_id: str,
        target_version_id: str,
        feedback: str,
        idempotency_key: str | None = None,
    ) -> str:
        for label, value in (("run_id", run_id), ("question_id", question_id)):
            self._require_safe_id(label, value)
        expected_prefix = f"{run_id}:v"
        if (
            not isinstance(target_version_id, str)
            or not target_version_id.startswith(expected_prefix)
            or not target_version_id[len(expected_prefix) :].isdigit()
            or int(target_version_id[len(expected_prefix) :]) < 1
        ):
            raise InvalidFeedbackInput("target_version_id is invalid")
        if not isinstance(feedback, str) or not feedback.strip():
            raise InvalidFeedbackInput("feedback cannot be empty")
        normalized = feedback.strip()
        if len(normalized) > self.max_feedback_length:
            raise InvalidFeedbackInput("feedback exceeds the configured length limit")
        if _has_forbidden_control(normalized):
            raise InvalidFeedbackInput("feedback contains forbidden control characters")
        if idempotency_key is not None:
            if (
                not isinstance(idempotency_key, str)
                or not idempotency_key.strip()
                or len(idempotency_key) > 256
                or _has_forbidden_control(idempotency_key)
            ):
                raise InvalidFeedbackInput("idempotency_key is invalid")
        return normalized

    @staticmethod
    def _snapshot_record(record: FeedbackRecord) -> FeedbackRecord:
        try:
            return FeedbackRecord.model_validate_json(
                _canonical_json(record.model_dump(mode="json"))
            )
        except (ValidationError, ValueError) as exc:
            raise InvalidFeedbackInput("feedback record is invalid") from exc

    def _record_from_submission(
        self,
        submission: FeedbackSubmission | Mapping[str, Any],
    ) -> FeedbackRecord:
        try:
            raw_request = (
                submission.model_dump(mode="json")
                if isinstance(submission, FeedbackSubmission)
                else dict(submission)
            )
            request = FeedbackSubmission.model_validate_json(
                _canonical_json(raw_request)
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise InvalidFeedbackInput("feedback submission is invalid") from exc

        feedback = self._validate_text_and_ids(
            run_id=request.run_id,
            question_id=request.question_id,
            target_version_id=request.target_version_id,
            feedback=request.feedback,
            idempotency_key=request.idempotency_key,
        )
        self._require_safe_id("actor_id", request.source.actor_id)
        if request.correlation_id is not None:
            self._require_safe_id("correlation_id", request.correlation_id)
        self._authorize(
            action="submit",
            actor_id=request.source.actor_id,
            run_id=request.run_id,
            question_id=request.question_id,
        )
        request_payload = {
            "schema_version": 1,
            "run_id": request.run_id,
            "question_id": request.question_id,
            "target_version_id": request.target_version_id,
            "feedback": feedback,
            "source": request.source.model_dump(mode="json"),
            "metadata": request.metadata,
        }
        try:
            return FeedbackRecord(
                feedback_id=f"feedback-{self._id_factory()}",
                run_id=request.run_id,
                question_id=request.question_id,
                target_version_id=request.target_version_id,
                feedback=feedback,
                source=request.source,
                correlation_id=(
                    request.correlation_id.strip()
                    if request.correlation_id and request.correlation_id.strip()
                    else f"corr-{self._id_factory()}"
                ),
                submitted_at=self._now(),
                request_fingerprint=_sha256(_canonical_json(request_payload)),
                idempotency_key_hash=(
                    _sha256(request.idempotency_key.strip())
                    if request.idempotency_key is not None
                    else None
                ),
                metadata=request.metadata,
            )
        except (ValidationError, ValueError) as exc:
            raise InvalidFeedbackInput("feedback submission is invalid") from exc

    def _starting_lineage(self, record: FeedbackRecord) -> AuditLineage:
        event = AuditLineageEvent(
            event_id=f"event-{self._id_factory()}",
            event_type="feedback_submitted",
            occurred_at=record.submitted_at,
            actor_id=record.source.actor_id,
            subject_id=record.feedback_id,
            payload_sha256=record.fingerprint(),
            metadata={"channel": record.source.channel},
        )
        return AuditLineage.start(
            record,
            lineage_id=f"lineage-{self._id_factory()}",
            event=event,
        )

    def _persist_submission(
        self,
        record: FeedbackRecord,
    ) -> tuple[FeedbackRecord, AuditLineage]:
        lineage = self._starting_lineage(record)
        atomic_save = getattr(self.store, "save_submission", None)
        if callable(atomic_save):
            return atomic_save(record, lineage)
        saved = self.store.save_feedback(record)
        if saved.feedback_id != record.feedback_id:
            return saved, self.store.get_lineage_by_feedback(saved.feedback_id)
        return saved, self.store.save_lineage(lineage)

    def _auto_reject_injection(
        self,
        record: FeedbackRecord,
        lineage: AuditLineage,
    ) -> None:
        existing = self.store.get_decision(record.feedback_id)
        if existing is not None:
            if existing.disposition != "rejected":
                raise FeedbackConflict("unsafe feedback has a non-rejected decision")
            return
        digest = _sha256(record.feedback_id)
        decided_at = self._now()
        if decided_at < lineage.events[-1].occurred_at:
            decided_at = lineage.events[-1].occurred_at
        decision = FeedbackDecision(
            decision_id=f"decision-safety-{digest[:20]}",
            feedback_id=record.feedback_id,
            target_version_id=record.target_version_id,
            disposition="rejected",
            decision_reason="Automated safety policy rejected suspected prompt injection.",
            rejected_items=("unsafe_prompt_injection",),
            decided_by="t03-feedback-safety-policy",
            decided_at=decided_at,
            policy_version="t03-feedback-safety-v1",
        )
        event = AuditLineageEvent(
            event_id=f"event-safety-{digest[:20]}",
            event_type="feedback_decided",
            occurred_at=decided_at,
            actor_id=decision.decided_by,
            subject_id=decision.decision_id,
            parent_event_id=lineage.events[-1].event_id,
            payload_sha256=decision.fingerprint(),
            metadata={"automated": True, "safety_reason": "prompt_injection"},
        )
        self.store.save_decision_and_append(lineage.lineage_id, decision, event)

    def submit(
        self,
        record: FeedbackRecord | FeedbackSubmission | Mapping[str, Any],
    ) -> FeedbackRecord:
        """Authorize, validate, persist, deduplicate, and safety-classify input."""
        if isinstance(record, FeedbackRecord):
            snapshot = self._snapshot_record(record)
            feedback = self._validate_text_and_ids(
                run_id=snapshot.run_id,
                question_id=snapshot.question_id,
                target_version_id=snapshot.target_version_id,
                feedback=snapshot.feedback,
            )
            if feedback != snapshot.feedback:
                raise InvalidFeedbackInput("feedback must use its canonical trimmed form")
            self._require_safe_id("feedback_id", snapshot.feedback_id)
            self._require_safe_id("actor_id", snapshot.source.actor_id)
            self._require_safe_id("correlation_id", snapshot.correlation_id)
            self._authorize(
                action="submit",
                actor_id=snapshot.source.actor_id,
                run_id=snapshot.run_id,
                question_id=snapshot.question_id,
            )
        else:
            snapshot = self._record_from_submission(record)
        saved, lineage = self._persist_submission(snapshot)
        if _is_prompt_injection(saved.feedback):
            # Raw text remains available to auditors, while an automatic rejected
            # decision ensures it can never enter a revision prompt.
            self._auto_reject_injection(saved, lineage)
        return saved

    def submit_request(
        self,
        submission: FeedbackSubmission | Mapping[str, Any],
    ) -> FeedbackRecord:
        """Named request entrypoint for API adapters."""
        return self.submit(submission)

    def decide(
        self,
        feedback_id: str,
        decision: FeedbackDecision,
    ) -> FeedbackDecision:
        """Authorize one immutable decision and atomically append its audit event."""
        try:
            snapshot = FeedbackDecision.model_validate_json(
                _canonical_json(decision.model_dump(mode="json"))
            )
        except (ValidationError, ValueError, AttributeError) as exc:
            raise InvalidFeedbackInput("feedback decision is invalid") from exc
        record = self.store.get_feedback(feedback_id)
        if snapshot.feedback_id != feedback_id:
            raise InvalidFeedbackInput("decision references another feedback_id")
        if snapshot.target_version_id != record.target_version_id:
            raise InvalidFeedbackInput("decision targets another plan version")
        if snapshot.resulting_version_id is not None:
            raise InvalidFeedbackInput(
                "revision result belongs in AuditLineage, not FeedbackDecision"
            )
        for item in snapshot.accepted_items:
            if (
                len(item) > self.max_feedback_length
                or _has_forbidden_control(item)
                or _is_prompt_injection(item)
            ):
                raise InvalidFeedbackInput(
                    "accepted feedback item is unsafe for a revision prompt"
                )
        self._require_safe_id("decision_id", snapshot.decision_id)
        self._require_safe_id("decided_by", snapshot.decided_by)
        self._authorize(
            action="decide",
            actor_id=snapshot.decided_by,
            run_id=record.run_id,
            question_id=record.question_id,
        )
        lineage = self.store.get_lineage_by_feedback(feedback_id)
        existing_decision = self.store.get_decision(feedback_id)
        if existing_decision is not None:
            if existing_decision != snapshot:
                raise FeedbackConflict("feedback already has another decision")
            if (
                lineage.decision_id != snapshot.decision_id
                or lineage.decision_sha256 != snapshot.fingerprint()
            ):
                raise FeedbackConflict(
                    "stored decision is not bound to its audit lineage"
                )
            return existing_decision
        if snapshot.decided_at < lineage.events[-1].occurred_at:
            raise InvalidFeedbackInput("decision cannot predate the audit lineage")
        event = AuditLineageEvent(
            event_id=(
                "event-decision-"
                + _sha256(snapshot.decision_id + "\n" + snapshot.fingerprint())[:20]
            ),
            event_type="feedback_decided",
            occurred_at=snapshot.decided_at,
            actor_id=snapshot.decided_by,
            subject_id=snapshot.decision_id,
            parent_event_id=lineage.events[-1].event_id,
            payload_sha256=snapshot.fingerprint(),
            metadata={"policy_version": snapshot.policy_version},
        )
        saved, _ = self.store.save_decision_and_append(
            lineage.lineage_id,
            snapshot,
            event,
        )
        return saved

    def build_directive(self, feedback_id: str) -> HumanFeedbackDirective | None:
        """Build an accepted-only prompt directive from stored v1 snapshots."""
        record = self.store.get_feedback(feedback_id)
        decision = self.store.get_decision(feedback_id)
        if decision is None or decision.disposition == "rejected":
            return None
        try:
            directive = HumanFeedbackDirective.from_feedback(record, decision)
            return HumanFeedbackDirective.model_validate_json(
                _canonical_json(directive.model_dump(mode="json"))
            )
        except (ValidationError, ValueError) as exc:
            raise InvalidFeedbackInput("stored feedback cannot form a directive") from exc

    def consume_revision_lineage_handoff(
        self,
        revision_lineage_handoff: Any,
        *,
        revision_metadata: Any,
        actor_id: str,
        occurred_at: datetime | None = None,
    ) -> AuditLineage:
        """Validate T02 outputs and atomically bind them to this feedback store."""
        # Import locally so minimal feedback adapters do not load the revision
        # bridge until they actually consume a T02 handoff.
        from app.feedback.revision import RevisionLineageConsumer

        return RevisionLineageConsumer(self.store, clock=self._now).consume(
            revision_lineage_handoff,
            revision_metadata=revision_metadata,
            actor_id=actor_id,
            occurred_at=occurred_at,
        )


__all__ = [
    "AllowAllFeedbackAuthorizer",
    "DefaultFeedbackService",
    "DenyAllFeedbackAuthorizer",
    "FeedbackAuthorizer",
    "FeedbackService",
    "FeedbackSubmission",
]
