"""Strict, workflow-owned integrity envelope for Wave C revision context.

The public revision contracts are frozen.  These models therefore live at the
T02 workflow boundary and cross-check the bounded T05/T06 projection against
the exact V1 -> V2 lineage consumed by the second revision round.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts.revision import IssueClosure, PlanVersion, ReviewFeedback
from app.workflow.revision_feedback import RevisionFeedbackProjection


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class _IntegrityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewerFeedbackTrace(_IntegrityModel):
    """Stable reviewer identity plus every revision-driving feedback field."""

    review_id: str = Field(min_length=1)
    critical_issues: tuple[str, ...]
    required_revisions: tuple[str, ...]
    comments: tuple[str, ...]
    severity: Literal["low", "medium", "high"]


class IssueClosureTransition(_IntegrityModel):
    """One issue status transition carried into the next revision round."""

    issue_id: str = Field(min_length=1)
    previous_status: Literal["open", "resolved"]
    current_status: Literal["open", "resolved"]
    closure_reason: str | None = None

    @model_validator(mode="after")
    def _require_closure_reason(self) -> "IssueClosureTransition":
        if self.current_status == "resolved" and not (
            self.closure_reason or ""
        ).strip():
            raise ValueError("resolved issue transition requires closure reason")
        if self.previous_status == "resolved" and self.current_status == "open":
            raise ValueError("issue closure state cannot reopen a resolved issue")
        return self


class RevisionLineageProvenance(_IntegrityModel):
    """Direct V1 -> V2 provenance with a content-bound context digest."""

    source_version_id: str = Field(min_length=1)
    parent_plan_version_id: str = Field(min_length=1)
    generated_version_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("generated_at")
    @classmethod
    def _require_aware_timestamp(cls, value: str) -> str:
        normalized = value.strip()
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("generated_at must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return normalized

    @model_validator(mode="after")
    def _require_direct_lineage(self) -> "RevisionLineageProvenance":
        if self.source_version_id != self.parent_plan_version_id:
            raise ValueError("source version must match parent plan version")
        run_id, marker, number = self.parent_plan_version_id.rpartition(":v")
        expected = f"{run_id}:v{int(number) + 1}" if number.isdigit() else ""
        if marker != ":v" or not run_id or self.generated_version_id != expected:
            raise ValueError(
                "generated version must directly follow parent plan version"
            )
        return self


class RevisionContextIntegrity(_IntegrityModel):
    """All cross-domain identifiers needed to reject incomplete contexts."""

    schema_version: Literal[1] = 1
    reviewer_feedback: ReviewerFeedbackTrace
    execution_feedback_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    multimodal_artifact_ids: tuple[str, ...] = Field(min_length=1)
    issue_closure_state: tuple[IssueClosureTransition, ...]
    lineage_provenance: RevisionLineageProvenance

    def hash_payload(self) -> dict[str, Any]:
        lineage = self.lineage_provenance.model_dump(
            mode="json",
            exclude={"context_hash"},
        )
        return {
            "reviewer_feedback": self.reviewer_feedback.model_dump(mode="json"),
            "execution_feedback_fingerprint": (
                self.execution_feedback_fingerprint
            ),
            "multimodal_artifact_ids": list(self.multimodal_artifact_ids),
            "issue_closure_state": [
                item.model_dump(mode="json") for item in self.issue_closure_state
            ],
            "lineage_provenance": lineage,
        }

    @model_validator(mode="after")
    def _validate_context_hash(self) -> "RevisionContextIntegrity":
        expected = _sha256(self.hash_payload())
        if self.lineage_provenance.context_hash != expected:
            raise ValueError("lineage provenance context hash does not match content")
        if len(set(self.multimodal_artifact_ids)) != len(
            self.multimodal_artifact_ids
        ):
            raise ValueError("multimodal artifact IDs must be unique")
        issue_ids = [item.issue_id for item in self.issue_closure_state]
        if len(set(issue_ids)) != len(issue_ids):
            raise ValueError("issue closure state IDs must be unique")
        return self


def reviewer_feedback_trace(feedback: ReviewFeedback) -> ReviewerFeedbackTrace:
    """Create a deterministic reviewer receipt without changing the contract."""
    payload = feedback.model_dump(mode="json")
    return ReviewerFeedbackTrace(
        review_id=f"review:{_sha256(payload)[:16]}",
        critical_issues=tuple(feedback.critical_issues),
        required_revisions=tuple(feedback.required_revisions),
        comments=tuple(feedback.reviewer_comments),
        severity=feedback.risk_level,
    )


def issue_closure_transitions(
    issues: Sequence[IssueClosure],
) -> tuple[IssueClosureTransition, ...]:
    """Snapshot status without inventing a closure reason."""
    return tuple(
        IssueClosureTransition(
            issue_id=issue.issue_id,
            previous_status="open",
            current_status=issue.status,
            closure_reason=issue.resolution_note,
        )
        for issue in issues
    )


def build_revision_context_integrity(
    *,
    previous_version: PlanVersion,
    issues: Sequence[IssueClosure],
    wave_c_feedback: RevisionFeedbackProjection,
    generated_at: str | None = None,
) -> RevisionContextIntegrity:
    """Build and hash a complete context, rejecting either missing summary."""
    if previous_version.review_feedback is None:
        raise ValueError("Reviewer feedback is required for context integrity")
    if wave_c_feedback.execution is None or not wave_c_feedback.multimodal:
        raise ValueError(
            "Wave C context requires complete execution and multimodal summaries"
        )
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    reviewer = reviewer_feedback_trace(previous_version.review_feedback)
    transitions = issue_closure_transitions(issues)
    artifact_ids = tuple(item.artifact_id for item in wave_c_feedback.multimodal)
    lineage_without_hash = {
        "source_version_id": previous_version.version_id,
        "parent_plan_version_id": previous_version.version_id,
        "generated_version_id": f"{previous_version.run_id}:v2",
        "generated_at": timestamp,
    }
    hash_payload = {
        "reviewer_feedback": reviewer.model_dump(mode="json"),
        "execution_feedback_fingerprint": wave_c_feedback.fingerprint,
        "multimodal_artifact_ids": list(artifact_ids),
        "issue_closure_state": [
            item.model_dump(mode="json") for item in transitions
        ],
        "lineage_provenance": lineage_without_hash,
    }
    return RevisionContextIntegrity(
        reviewer_feedback=reviewer,
        execution_feedback_fingerprint=wave_c_feedback.fingerprint,
        multimodal_artifact_ids=artifact_ids,
        issue_closure_state=transitions,
        lineage_provenance=RevisionLineageProvenance(
            **lineage_without_hash,
            context_hash=_sha256(hash_payload),
        ),
    )
