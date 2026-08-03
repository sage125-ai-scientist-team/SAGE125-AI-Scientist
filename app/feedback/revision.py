"""T03 sidecar bridge into T02 revision prompts without changing T02 models."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.contracts.revision import RevisionContext, RevisionPromptBuilder
from app.contracts.validation import FeedbackDecision, FeedbackRecord
from app.feedback.errors import FeedbackConflict, InvalidFeedbackInput


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
    "RevisionFeedbackContext",
    "RevisionFeedbackContextBuilder",
    "RevisionPromptAdapter",
]
