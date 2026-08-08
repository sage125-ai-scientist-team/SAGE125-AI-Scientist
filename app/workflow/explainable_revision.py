"""Explainable T02 experiment revision assessment and audit sidecar.

This module deliberately reuses the Wave A ``PlanVersion``, ``ReviewFeedback``
and ``IssueClosure`` contracts.  It adds workflow-owned evidence explaining how
one experiment version changed, without extending shared public schemas.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.base import AgentOutputError
from app.agents.experiment_designer import ExperimentDesignerAgent
from app.agents.hypothesis_generator import HypothesisGeneratorAgent
from app.agents.scientific_reviewer import ScientificReviewerAgent
from app.contracts.evidence import EvidenceBundle
from app.contracts.revision import (
    IssueClosure,
    PlanVersion,
    ReviewFeedback,
    issues_from_review_feedback,
)
from app.contracts.validation import HumanFeedbackDirective
from app.workflow.revision_feedback import RevisionFeedbackProjection
from app.workflow.revision_integrity import (
    RevisionContextIntegrity,
    build_revision_context_integrity,
)


ClosureStatus = Literal["open", "resolved"]
SubstantiveSection = Literal[
    "experimental_variables",
    "control_groups",
    "experiment_steps",
    "evaluation_metrics",
    "safety_constraints",
    "stopping_conditions",
    "evidence_references",
]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _stable_id(prefix: str, *parts: Any) -> str:
    encoded = "\n".join(_canonical_json(part) for part in parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()[:16]}"


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _unique_strings(values: Sequence[str]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


class FailureReason(BaseModel):
    """Stable, source-bound reason why the previous revision failed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    failure_id: str = Field(min_length=1)
    source: Literal["scientific_reviewer", "pipeline"]
    reviewer_field: Literal[
        "passed", "critical_issues", "required_revisions"
    ]
    reason: str = Field(min_length=1)
    issue_id: str | None = None


class HumanFeedbackReceipt(BaseModel):
    """Frozen accepted-only T03 receipt sent at the Agent payload boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    feedback_id: str = Field(min_length=1)
    source_version_id: str = Field(min_length=1)
    disposition: Literal["accepted", "partially_accepted"]
    applied_instructions: tuple[str, ...] = Field(min_length=1)
    original_feedback_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_directive(
        cls,
        directive: HumanFeedbackDirective,
    ) -> "HumanFeedbackReceipt":
        """Snapshot one strict directive without exposing rejected/raw feedback."""
        return cls(
            feedback_id=directive.feedback_id,
            source_version_id=directive.target_version_id,
            disposition=directive.disposition,
            applied_instructions=tuple(directive.instructions),
            original_feedback_sha256=directive.original_feedback_sha256,
        )


class ExperimentRevisionContext(BaseModel):
    """Structured previous-state payload consumed by the second experiment round."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    previous_plan: dict[str, Any]
    previous_plan_version: dict[str, Any]
    parent_version_id: str = Field(min_length=1)
    lineage: list[str] = Field(min_length=2)
    unresolved_issues: list[IssueClosure] = Field(default_factory=list)
    failure_reasons: list[FailureReason] = Field(default_factory=list)
    reviewer_feedback: ReviewFeedback
    evidence_bundle: EvidenceBundle | None = None
    human_feedback: HumanFeedbackDirective | None = None
    wave_c_feedback: RevisionFeedbackProjection | None = None
    integrity: RevisionContextIntegrity | None = None
    required_change_fields: tuple[str, ...] = (
        "change_id",
        "issue_id",
        "reason",
        "before",
        "after",
        "evidence_refs",
        "affected_plan_section",
        "closure_status",
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_incomplete_lineage_provenance(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        integrity = value.get("integrity")
        if isinstance(integrity, Mapping):
            lineage = integrity.get("lineage_provenance")
            required = {
                "source_version_id",
                "parent_plan_version_id",
                "generated_version_id",
                "generated_at",
                "context_hash",
            }
            if not isinstance(lineage, Mapping) or not required.issubset(lineage):
                raise ValueError("lineage provenance is incomplete")
        return value

    @model_validator(mode="after")
    def _validate_lineage(self) -> "ExperimentRevisionContext":
        if len(set(self.lineage)) != len(self.lineage):
            raise ValueError("revision lineage cannot contain a cycle")
        if self.lineage[0] != self.parent_version_id:
            raise ValueError("lineage must start at parent_version_id")
        expected_child = self.parent_version_id.rsplit(":v", 1)[0] + ":v2"
        if self.lineage[-1] != expected_child:
            raise ValueError("revision lineage must target V2")
        if (
            self.human_feedback is not None
            and self.human_feedback.target_version_id != self.parent_version_id
        ):
            raise ValueError("human feedback must target the parent plan version")
        if self.wave_c_feedback is None:
            if self.integrity is not None:
                raise ValueError(
                    "context integrity cannot exist without Wave C feedback"
                )
            return self
        if self.integrity is None:
            raise ValueError("Wave C revision context requires context integrity")
        if (
            self.wave_c_feedback.execution is None
            or not self.wave_c_feedback.multimodal
        ):
            raise ValueError(
                "Wave C context requires complete execution and multimodal summaries"
            )
        previous = PlanVersion.model_validate(self.previous_plan_version)
        expected = build_revision_context_integrity(
            previous_version=previous,
            issues=self.unresolved_issues,
            wave_c_feedback=self.wave_c_feedback,
            generated_at=self.integrity.lineage_provenance.generated_at,
        )
        if self.integrity != expected:
            raise ValueError(
                "context integrity does not match reviewer, issue, or lineage content"
            )
        if self.parent_version_id != expected.lineage_provenance.parent_plan_version_id:
            raise ValueError("parent plan version does not match lineage provenance")
        if self.lineage[-1] != expected.lineage_provenance.generated_version_id:
            raise ValueError("generated version does not match revision lineage")
        return self


class RevisionRoundInput(BaseModel):
    """Strict transport boundary for feedback plus revision-only context."""

    model_config = ConfigDict(extra="forbid")

    review_result: ReviewFeedback
    revision_context: ExperimentRevisionContext
    human_feedback: HumanFeedbackReceipt | None = None
    revision_feedback_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def _match_feedback_fingerprint(self) -> "RevisionRoundInput":
        feedback = self.revision_context.wave_c_feedback
        expected = feedback.fingerprint if feedback is not None else None
        if self.revision_feedback_fingerprint != expected:
            raise ValueError(
                "revision feedback fingerprint must match the bounded projection"
            )
        return self


class ReviewScoreChange(BaseModel):
    """One Reviewer score delta between V1 and V2."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    before: float = Field(ge=0.0, le=1.0)
    after: float = Field(ge=0.0, le=1.0)
    delta: float


class CandidateHypothesisRank(BaseModel):
    """Deterministic candidate ranking retained in the two-round audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=1)
    original_index: int = Field(ge=0)
    hypothesis: str = Field(min_length=1)
    overall_score: float = Field(ge=0.0, le=1.0)
    recommended: bool = False


class ExperimentSectionDiff(BaseModel):
    """One structural experiment section whose canonical value changed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: SubstantiveSection
    before: Any
    after: Any


class RevisionChange(BaseModel):
    """Machine-readable issue-to-change-to-evidence mapping."""

    model_config = ConfigDict(extra="forbid")

    change_id: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    before: Any
    after: Any
    evidence_refs: list[str] = Field(default_factory=list)
    affected_plan_section: SubstantiveSection
    closure_status: ClosureStatus = "open"
    unresolved_reason: str | None = None

    @model_validator(mode="after")
    def _validate_claim(self) -> "RevisionChange":
        if _canonical_json(self.before) == _canonical_json(self.after):
            raise ValueError("before and after must differ")
        if self.closure_status == "resolved" and not self.evidence_refs:
            raise ValueError("resolved change requires evidence_refs")
        if self.closure_status == "open" and not self.unresolved_reason:
            raise ValueError("open change requires unresolved_reason")
        return self


class ExplainableRevisionAudit(BaseModel):
    """Replayable V1-to-V2 decision evidence stored beside AgentTrace events."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    previous_plan: dict[str, Any]
    previous_plan_version: dict[str, Any]
    parent_version_id: str = Field(min_length=1)
    lineage: list[str] = Field(min_length=2)
    reviewer_feedback: ReviewFeedback
    final_reviewer_feedback: ReviewFeedback
    failure_reasons: list[FailureReason] = Field(default_factory=list)
    changes: list[RevisionChange] = Field(default_factory=list)
    issue_closures: list[IssueClosure] = Field(default_factory=list)
    substantive_sections: list[SubstantiveSection] = Field(default_factory=list)
    score_changes: dict[str, ReviewScoreChange] = Field(default_factory=dict)
    candidate_hypothesis_ranking: list[CandidateHypothesisRank] = Field(
        default_factory=list
    )
    responded_issue_count: int = Field(default=0, ge=0)
    blocking_reasons: list[str] = Field(default_factory=list)
    remaining_blockers: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    accepted: bool = False

    @model_validator(mode="after")
    def _validate_decision(self) -> "ExplainableRevisionAudit":
        if len(set(self.lineage)) != len(self.lineage):
            raise ValueError("revision audit lineage cannot contain a cycle")
        has_open_issue = any(issue.status == "open" for issue in self.issue_closures)
        if self.accepted and (
            self.blocking_reasons
            or has_open_issue
            or not self.final_reviewer_feedback.is_effective_pass
            or not self.changes
            or self.responded_issue_count < 1
        ):
            raise ValueError("accepted revision cannot retain blockers")
        return self


class StructuredRevisionDiff(BaseModel):
    """The one canonical diff representation shared by trace and T03 receipts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    changes: tuple[RevisionChange, ...]
    substantive_sections: tuple[SubstantiveSection, ...]

    @classmethod
    def from_audit(
        cls,
        audit: ExplainableRevisionAudit,
    ) -> "StructuredRevisionDiff":
        return cls(
            changes=tuple(
                RevisionChange.model_validate(change.model_dump(mode="json"))
                for change in audit.changes
            ),
            substantive_sections=tuple(audit.substantive_sections),
        )

    def fingerprint(self) -> str:
        return _json_sha256(self.model_dump(mode="json"))


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


class RevisionMetadata(BaseModel):
    """Strict execution receipt consumed by T03's feedback propagation gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    feedback_id: str = Field(min_length=1)
    source_version_id: str = Field(min_length=1)
    resulting_version_id: str = Field(min_length=1)
    prompt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    diff_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    applied_instructions: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_direct_child(self) -> "RevisionMetadata":
        _require_direct_child(self.source_version_id, self.resulting_version_id)
        return self


class RevisionLineageHandoffEvent(BaseModel):
    """One deterministic T02 event awaiting append to T03's sidecar lineage."""

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
    """Strict T02 outcome that T03 can append after ``feedback_decided``."""

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
            raise ValueError("revision_requested hash must match the prompt fingerprint")
        if generated.subject_id != self.resulting_version_id:
            raise ValueError("revision_generated must reference the result version")
        if generated.payload_sha256 != self.revision_diff_sha256:
            raise ValueError("revision_generated hash must match the structured diff")
        closed_ids = tuple(event.subject_id for event in self.events[2:])
        if closed_ids != self.issue_ids or len(closed_ids) != len(set(closed_ids)):
            raise ValueError("issue closure events must match unique issue_ids")
        return self


def attach_revision_metadata(
    execution_metadata: Mapping[str, Any],
    revision_metadata: RevisionMetadata,
) -> dict[str, Any]:
    """Attach one validated receipt without overwriting conflicting metadata."""
    payload = dict(execution_metadata)
    existing = payload.get("revision_metadata")
    if existing is not None:
        if RevisionMetadata.model_validate(existing) != revision_metadata:
            raise ValueError("execution metadata contains conflicting revision_metadata")
        return json.loads(_canonical_json(payload))
    payload["revision_metadata"] = revision_metadata.model_dump(mode="json")
    return json.loads(_canonical_json(payload))


def build_revision_pairing_outputs(
    *,
    audit: ExplainableRevisionAudit,
    human_feedback: HumanFeedbackDirective,
    resulting_version_id: str,
    prompt_fingerprint: str,
) -> tuple[RevisionMetadata, RevisionLineageHandoff]:
    """Build metadata and append-ready events from one canonical diff snapshot."""
    receipt = HumanFeedbackReceipt.from_directive(human_feedback)
    structured_diff = StructuredRevisionDiff.from_audit(audit)
    diff_hash = structured_diff.fingerprint()
    metadata = RevisionMetadata(
        feedback_id=receipt.feedback_id,
        source_version_id=receipt.source_version_id,
        resulting_version_id=resulting_version_id,
        prompt_fingerprint=prompt_fingerprint,
        diff_hash=diff_hash,
        applied_instructions=receipt.applied_instructions,
    )
    requested_id = _stable_id(
        "event",
        "revision_requested",
        metadata.feedback_id,
        metadata.source_version_id,
        metadata.prompt_fingerprint,
    )
    generated_id = _stable_id(
        "event",
        "revision_generated",
        metadata.resulting_version_id,
        metadata.diff_hash,
    )
    events: list[RevisionLineageHandoffEvent] = [
        RevisionLineageHandoffEvent(
            event_id=requested_id,
            event_type="revision_requested",
            sequence=1,
            subject_id=metadata.feedback_id,
            payload_sha256=metadata.prompt_fingerprint,
            feedback_id=metadata.feedback_id,
            source_version_id=metadata.source_version_id,
            resulting_version_id=metadata.resulting_version_id,
        ),
        RevisionLineageHandoffEvent(
            event_id=generated_id,
            event_type="revision_generated",
            sequence=2,
            subject_id=metadata.resulting_version_id,
            payload_sha256=metadata.diff_hash,
            parent_event_id=requested_id,
            feedback_id=metadata.feedback_id,
            source_version_id=metadata.source_version_id,
            resulting_version_id=metadata.resulting_version_id,
        ),
    ]
    parent_event_id = generated_id
    resolved_issues = tuple(
        issue for issue in audit.issue_closures if issue.status == "resolved"
    )
    for issue in resolved_issues:
        event_id = _stable_id(
            "event",
            "issue_closed",
            issue.issue_id,
            issue.model_dump(mode="json"),
        )
        events.append(
            RevisionLineageHandoffEvent(
                event_id=event_id,
                event_type="issue_closed",
                sequence=len(events) + 1,
                subject_id=issue.issue_id,
                payload_sha256=_json_sha256(issue.model_dump(mode="json")),
                parent_event_id=parent_event_id,
                feedback_id=metadata.feedback_id,
                source_version_id=metadata.source_version_id,
                resulting_version_id=metadata.resulting_version_id,
            )
        )
        parent_event_id = event_id
    handoff = RevisionLineageHandoff(
        feedback_id=metadata.feedback_id,
        source_version_id=metadata.source_version_id,
        resulting_version_id=metadata.resulting_version_id,
        prompt_fingerprint=metadata.prompt_fingerprint,
        revision_diff_sha256=metadata.diff_hash,
        issue_ids=tuple(issue.issue_id for issue in resolved_issues),
        events=tuple(events),
    )
    return metadata, handoff


def issues_for_revision(
    feedback: ReviewFeedback | Mapping[str, Any],
    *,
    opened_in_version: int,
) -> list[IssueClosure]:
    """Return stable blocking issues, including a fail-closed implicit issue."""
    snapshot = ReviewFeedback.from_review_result(feedback)
    issues = issues_from_review_feedback(
        snapshot,
        opened_in_version=opened_in_version,
    )
    if not snapshot.is_effective_pass and not issues:
        description = "Reviewer rejected the plan without a structured blocking item."
        issues.append(
            IssueClosure(
                issue_id=_stable_id("critical_issue", description),
                category="critical_issue",
                description=description,
                opened_in_version=opened_in_version,
            )
        )
    return issues


def failure_reasons_from_feedback(
    feedback: ReviewFeedback | Mapping[str, Any],
    issues: Sequence[IssueClosure],
) -> list[FailureReason]:
    """Create deterministic failure provenance from Reviewer fields and issues."""
    snapshot = ReviewFeedback.from_review_result(feedback)
    reasons: list[FailureReason] = []
    if snapshot.passed is not True:
        reason = "ScientificReviewer returned passed=false."
        reasons.append(
            FailureReason(
                failure_id=_stable_id("failure", "scientific_reviewer", "passed", reason),
                source="scientific_reviewer",
                reviewer_field="passed",
                reason=reason,
            )
        )
    for issue in issues:
        reviewer_field = (
            "critical_issues"
            if issue.category == "critical_issue"
            else "required_revisions"
        )
        reasons.append(
            FailureReason(
                failure_id=_stable_id(
                    "failure",
                    "scientific_reviewer",
                    reviewer_field,
                    issue.issue_id,
                    issue.description,
                ),
                source="scientific_reviewer",
                reviewer_field=reviewer_field,
                reason=issue.description,
                issue_id=issue.issue_id,
            )
        )
    return reasons


def build_experiment_revision_context(
    *,
    previous_version: PlanVersion,
    unresolved_issues: Sequence[IssueClosure],
    failure_reasons: Sequence[FailureReason],
    evidence_bundle: EvidenceBundle | None = None,
    human_feedback: HumanFeedbackDirective | None = None,
    wave_c_feedback: RevisionFeedbackProjection | None = None,
    generated_at: str | None = None,
) -> ExperimentRevisionContext:
    """Build the exact structured payload supplied to revision-round agents."""
    if previous_version.version_number != 1:
        raise ValueError("Wave B two-round context requires V1 as the parent")
    if previous_version.review_feedback is None:
        raise ValueError("previous plan version requires Reviewer feedback")
    child_id = f"{previous_version.run_id}:v2"
    integrity = (
        build_revision_context_integrity(
            previous_version=previous_version,
            issues=unresolved_issues,
            wave_c_feedback=wave_c_feedback,
            generated_at=generated_at,
        )
        if wave_c_feedback is not None
        else None
    )
    return ExperimentRevisionContext(
        previous_plan={
            "hypothesis_generation": previous_version.hypothesis_generation,
            "experiment_design": previous_version.experiment_design,
        },
        previous_plan_version=previous_version.model_dump(mode="json"),
        parent_version_id=previous_version.version_id,
        lineage=[previous_version.version_id, child_id],
        unresolved_issues=[issue.model_copy(deep=True) for issue in unresolved_issues],
        failure_reasons=[reason.model_copy(deep=True) for reason in failure_reasons],
        reviewer_feedback=previous_version.review_feedback.model_copy(deep=True),
        evidence_bundle=(
            evidence_bundle.model_copy(deep=True)
            if evidence_bundle is not None
            else None
        ),
        human_feedback=(
            human_feedback.model_copy(deep=True)
            if human_feedback is not None
            else None
        ),
        wave_c_feedback=(
            wave_c_feedback.model_copy(deep=True)
            if wave_c_feedback is not None
            else None
        ),
        integrity=integrity,
    )


def inject_revision_context(
    payload: Mapping[str, Any],
    context: ExperimentRevisionContext,
) -> dict[str, Any]:
    """Attach context beside a strict ReviewFeedback without polluting its schema."""
    result = dict(payload)
    envelope = RevisionRoundInput(
        review_result=ReviewFeedback.from_review_result(
            result.get("review_result")
        ),
        revision_context=context.model_copy(deep=True),
        human_feedback=(
            HumanFeedbackReceipt.from_directive(context.human_feedback)
            if context.human_feedback is not None
            else None
        ),
        revision_feedback_fingerprint=(
            context.wave_c_feedback.fingerprint
            if context.wave_c_feedback is not None
            else None
        ),
    )
    envelope_payload = envelope.model_dump(mode="json")
    if envelope.human_feedback is None:
        envelope_payload.pop("human_feedback")
    if envelope.revision_feedback_fingerprint is None:
        envelope_payload.pop("revision_feedback_fingerprint")
        envelope_payload["revision_context"].pop("wave_c_feedback")
        envelope_payload["revision_context"].pop("integrity")
    result.update(envelope_payload)
    if envelope.revision_feedback_fingerprint is not None:
        result = {
            "revision_feedback_fingerprint": (
                envelope.revision_feedback_fingerprint
            ),
            **result,
        }
    return result


class _RevisionMessageMixin:
    """Validate and preserve the strict revision envelope in Agent messages."""

    def build_messages(self, input_data: dict) -> list[dict]:
        messages = super().build_messages(input_data)  # type: ignore[misc]
        if input_data.get("revision_context") is None:
            return messages
        envelope = RevisionRoundInput.model_validate(
            {
                "review_result": input_data.get("review_result"),
                "revision_context": input_data.get("revision_context"),
                "human_feedback": input_data.get("human_feedback"),
                "revision_feedback_fingerprint": input_data.get(
                    "revision_feedback_fingerprint"
                ),
            }
        )
        user_payload = json.loads(messages[1]["content"])
        envelope_payload = envelope.model_dump(mode="json")
        if envelope.human_feedback is None:
            envelope_payload.pop("human_feedback")
        if envelope.revision_feedback_fingerprint is None:
            envelope_payload.pop("revision_feedback_fingerprint")
            envelope_payload["revision_context"].pop("wave_c_feedback")
        user_payload.update(envelope_payload)
        return [
            dict(messages[0]),
            {
                **messages[1],
                "content": json.dumps(
                    user_payload,
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ]


class RevisionAwareHypothesisGeneratorAgent(
    _RevisionMessageMixin,
    HypothesisGeneratorAgent,
):
    """Workflow-owned HypothesisGenerator adapter for strict revision input."""


class RevisionAwareExperimentDesignerAgent(
    _RevisionMessageMixin,
    ExperimentDesignerAgent,
):
    """Workflow-owned ExperimentDesigner adapter for strict revision input."""


class RevisionAwareScientificReviewerAgent(
    _RevisionMessageMixin,
    ScientificReviewerAgent,
):
    """Workflow-owned ScientificReviewer adapter for strict revision input."""


_SECTION_ALIASES: tuple[tuple[SubstantiveSection, tuple[str, ...]], ...] = (
    (
        "experimental_variables",
        (
            "variables",
            "experimental_variables",
            "independent_variables",
            "dependent_variables",
        ),
    ),
    (
        "control_groups",
        ("baselines", "control_groups", "control_group", "controls"),
    ),
    (
        "experiment_steps",
        ("steps", "experiment_steps", "procedure_steps"),
    ),
    (
        "evaluation_metrics",
        ("metrics", "evaluation_metrics", "outcome_metrics"),
    ),
    (
        "safety_constraints",
        ("safety_constraints", "safety_rules", "guardrails"),
    ),
    (
        "stopping_conditions",
        ("stopping_conditions", "stop_conditions", "termination_criteria"),
    ),
)


def _experiments(plan: Mapping[str, Any]) -> Mapping[str, Any]:
    value = plan.get("experiments")
    return value if isinstance(value, Mapping) else {}


def _section_value(plan: Mapping[str, Any], aliases: Sequence[str]) -> Any:
    experiments = _experiments(plan)
    found = {
        alias: experiments[alias]
        for alias in aliases
        if alias in experiments and experiments[alias] not in (None, "", [], {})
    }
    if len(found) == 1:
        return next(iter(found.values()))
    return found or None


def _collect_evidence_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in {
                "evidence_id",
                "evidence_ids",
                "evidence_refs",
                "reference_id",
                "reference_ids",
                "supporting_evidence_ids",
                "contradicted_by_evidence_ids",
            }:
                if isinstance(item, str):
                    refs.append(item)
                elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
                    refs.extend(str(entry) for entry in item)
            else:
                refs.extend(_collect_evidence_refs(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            refs.extend(_collect_evidence_refs(item))
    return _unique_strings(refs)


def _normalized_section(section: SubstantiveSection, value: Any) -> Any:
    """Ignore ordering where it has no experimental meaning."""
    if isinstance(value, Mapping):
        return {
            str(key): _normalized_section(section, item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        normalized = [_normalized_section(section, item) for item in value]
        if section != "experiment_steps":
            return sorted(normalized, key=_canonical_json)
        return normalized
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    return value


def substantive_experiment_diff(
    previous: Mapping[str, Any],
    revised: Mapping[str, Any],
) -> list[ExperimentSectionDiff]:
    """Detect only structured experimental changes, ignoring narrative/bookkeeping."""
    changes: list[ExperimentSectionDiff] = []
    for section, aliases in _SECTION_ALIASES:
        before = _section_value(previous, aliases)
        after = _section_value(revised, aliases)
        if _normalized_section(section, before) != _normalized_section(section, after):
            changes.append(
                ExperimentSectionDiff(section=section, before=before, after=after)
            )
    before_refs = _collect_evidence_refs(previous)
    after_refs = _collect_evidence_refs(revised)
    if before_refs != after_refs:
        changes.append(
            ExperimentSectionDiff(
                section="evidence_references",
                before=before_refs,
                after=after_refs,
            )
        )
    return changes


def _validated_evidence_refs(
    revised_experiment: Mapping[str, Any],
    available_evidence_refs: Sequence[str],
) -> list[str]:
    available = _unique_strings(available_evidence_refs)
    declared = _collect_evidence_refs(revised_experiment)
    if declared:
        allowed = set(available)
        return [ref for ref in declared if ref in allowed]
    return available


_REVIEW_SCORE_FIELDS: tuple[str, ...] = (
    "evidence_grounding_score",
    "falsifiability_score",
    "reproducibility_score",
    "reference_reliability_score",
)


def _review_score_changes(
    before: ReviewFeedback,
    after: ReviewFeedback,
) -> dict[str, ReviewScoreChange]:
    changes: dict[str, ReviewScoreChange] = {}
    for field_name in _REVIEW_SCORE_FIELDS:
        before_value = float(getattr(before, field_name))
        after_value = float(getattr(after, field_name))
        changes[field_name] = ReviewScoreChange(
            before=before_value,
            after=after_value,
            delta=after_value - before_value,
        )
    return changes


def _candidate_hypothesis_ranking(
    hypothesis_generation: Mapping[str, Any],
) -> list[CandidateHypothesisRank]:
    raw_candidates = hypothesis_generation.get("hypotheses") or []
    if not isinstance(raw_candidates, Sequence) or isinstance(
        raw_candidates,
        (str, bytes),
    ):
        return []
    recommended_index = int(
        hypothesis_generation.get("recommended_hypothesis_index", 0)
    )
    candidates: list[tuple[int, str, float]] = []
    for index, value in enumerate(raw_candidates):
        if not isinstance(value, Mapping):
            continue
        hypothesis = str(value.get("hypothesis") or "").strip()
        if not hypothesis:
            continue
        score = float(value.get("overall_score") or 0.0)
        candidates.append((index, hypothesis, score))
    ordered = sorted(candidates, key=lambda item: (-item[2], item[0]))
    return [
        CandidateHypothesisRank(
            rank=rank,
            original_index=index,
            hypothesis=hypothesis,
            overall_score=score,
            recommended=index == recommended_index,
        )
        for rank, (index, hypothesis, score) in enumerate(ordered, start=1)
    ]


def assess_experiment_revision(
    *,
    previous_version: PlanVersion,
    revised_hypothesis: Mapping[str, Any],
    revised_experiment: Mapping[str, Any],
    final_feedback: ReviewFeedback | Mapping[str, Any],
    available_evidence_refs: Sequence[str],
) -> ExplainableRevisionAudit:
    """Assess V2 and produce issue-change-evidence-closure audit evidence."""
    if previous_version.review_feedback is None:
        raise ValueError("previous version must contain Reviewer feedback")
    initial_feedback = previous_version.review_feedback.model_copy(deep=True)
    final_snapshot = ReviewFeedback.from_review_result(final_feedback)
    initial_issues = issues_for_revision(initial_feedback, opened_in_version=1)
    failures = failure_reasons_from_feedback(initial_feedback, initial_issues)
    diffs = substantive_experiment_diff(
        previous_version.experiment_design,
        revised_experiment,
    )
    evidence_refs = _validated_evidence_refs(
        revised_experiment,
        available_evidence_refs,
    )
    final_issues = issues_for_revision(final_snapshot, opened_in_version=2)
    final_issue_ids = {issue.issue_id for issue in final_issues}

    issue_status: dict[str, ClosureStatus] = {}
    unresolved_reason: dict[str, str | None] = {}
    for issue in initial_issues:
        if issue.issue_id in final_issue_ids:
            issue_status[issue.issue_id] = "open"
            unresolved_reason[issue.issue_id] = "V2 Reviewer still reports this issue."
        elif not diffs:
            issue_status[issue.issue_id] = "open"
            unresolved_reason[issue.issue_id] = (
                "No substantive structured experiment change maps to this issue."
            )
        elif not evidence_refs:
            issue_status[issue.issue_id] = "open"
            unresolved_reason[issue.issue_id] = (
                "The mapped experiment change has no validated evidence reference."
            )
        else:
            issue_status[issue.issue_id] = "resolved"
            unresolved_reason[issue.issue_id] = None

    changes: list[RevisionChange] = []
    if diffs and initial_issues:
        mapping_count = max(len(diffs), len(initial_issues))
        for index in range(mapping_count):
            diff = diffs[index % len(diffs)]
            issue = initial_issues[index % len(initial_issues)]
            status = issue_status[issue.issue_id]
            change_id = _stable_id(
                "change",
                issue.issue_id,
                diff.section,
                diff.before,
                diff.after,
            )
            reason = (
                f"Reviewer item {issue.issue_id} requested '{issue.description}'. "
                f"V2 changes {diff.section} from the recorded before value to the "
                "recorded after value."
            )
            changes.append(
                RevisionChange(
                    change_id=change_id,
                    issue_id=issue.issue_id,
                    reason=reason,
                    before=diff.before,
                    after=diff.after,
                    evidence_refs=evidence_refs,
                    affected_plan_section=diff.section,
                    closure_status=status,
                    unresolved_reason=unresolved_reason[issue.issue_id],
                )
            )

    changes_by_issue: dict[str, list[RevisionChange]] = {}
    for change in changes:
        changes_by_issue.setdefault(change.issue_id, []).append(change)

    closures: list[IssueClosure] = []
    for issue in initial_issues:
        status = issue_status[issue.issue_id]
        mapped = changes_by_issue.get(issue.issue_id, [])
        if status == "resolved":
            note = (
                "changes="
                + ",".join(change.change_id for change in mapped)
                + "; evidence="
                + ",".join(evidence_refs)
                + "; V2 Reviewer no longer reports the issue."
            )
            closures.append(
                issue.model_copy(
                    update={
                        "status": "resolved",
                        "closed_in_version": 2,
                        "resolution_note": note,
                    },
                    deep=True,
                )
            )
        else:
            closures.append(
                issue.model_copy(
                    update={"resolution_note": unresolved_reason[issue.issue_id]},
                    deep=True,
                )
            )

    initial_ids = {issue.issue_id for issue in initial_issues}
    closures.extend(
        issue.model_copy(deep=True)
        for issue in final_issues
        if issue.issue_id not in initial_ids
    )

    blocking: list[str] = []
    if not diffs:
        blocking.append("no_substantive_experiment_change")
    if diffs and not evidence_refs:
        blocking.append("substantive_change_missing_validated_evidence")
    mapped_issue_ids = {change.issue_id for change in changes}
    for issue in initial_issues:
        if issue.issue_id not in mapped_issue_ids:
            blocking.append(f"required_revision_without_change:{issue.issue_id}")
    for issue in closures:
        if issue.status == "open":
            blocking.append(f"unresolved_issue:{issue.issue_id}")
    if not final_snapshot.is_effective_pass:
        blocking.append("final_reviewer_feedback_blocks")
    blocking = list(dict.fromkeys(blocking))
    remaining = [
        f"{issue.issue_id}: {issue.resolution_note or issue.description}"
        for issue in closures
        if issue.status == "open"
    ]
    responded_issue_count = sum(
        1
        for issue in closures
        if issue.opened_in_version == 1 and issue.status == "resolved"
    )
    accepted = not blocking
    stop_reason = None
    if not diffs:
        stop_reason = "no_improvement"
    elif not final_snapshot.is_effective_pass:
        stop_reason = "max_revision_iterations_exhausted"
    elif blocking:
        stop_reason = "revision_acceptance_blocked"

    return ExplainableRevisionAudit(
        previous_plan={
            "hypothesis_generation": previous_version.hypothesis_generation,
            "experiment_design": previous_version.experiment_design,
        },
        previous_plan_version=previous_version.model_dump(mode="json"),
        parent_version_id=previous_version.version_id,
        lineage=[previous_version.version_id, f"{previous_version.run_id}:v2"],
        reviewer_feedback=initial_feedback,
        final_reviewer_feedback=final_snapshot,
        failure_reasons=failures,
        changes=changes,
        issue_closures=closures,
        substantive_sections=[diff.section for diff in diffs],
        score_changes=_review_score_changes(initial_feedback, final_snapshot),
        candidate_hypothesis_ranking=_candidate_hypothesis_ranking(
            revised_hypothesis
        ),
        responded_issue_count=responded_issue_count,
        blocking_reasons=blocking,
        remaining_blockers=remaining,
        stop_reason=stop_reason,
        accepted=accepted,
    )


class RevisionExecutionState(BaseModel):
    """Serializable bounded-control checkpoint for one revision run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    max_iterations: int = Field(default=2, ge=1)
    max_retries: int = Field(default=1, ge=0)
    current_iteration: int = Field(default=1, ge=1)
    retry_count: int = Field(default=0, ge=0)
    status: Literal["active", "paused", "completed", "stopped"] = "active"
    processed_event_ids: tuple[str, ...] = ()
    version_ids: tuple[str, ...] = ()
    failure_reasons: tuple[str, ...] = ()
    pause_reason: str | None = None
    stop_reason: str | None = None

    @model_validator(mode="after")
    def _validate_checkpoint(self) -> "RevisionExecutionState":
        if self.current_iteration > self.max_iterations:
            raise ValueError("current iteration exceeds max_iterations")
        if len(set(self.processed_event_ids)) != len(self.processed_event_ids):
            raise ValueError("processed event IDs must be unique")
        if len(self.version_ids) > self.max_iterations:
            raise ValueError("version count exceeds max_iterations")
        expected_versions = tuple(
            f"{self.run_id}:v{number}"
            for number in range(1, len(self.version_ids) + 1)
        )
        if self.version_ids != expected_versions:
            raise ValueError("version IDs must be contiguous canonical lineage")
        if self.status == "paused" and not (self.pause_reason or "").strip():
            raise ValueError("paused revision requires pause_reason")
        if self.status != "paused" and self.pause_reason is not None:
            raise ValueError("pause_reason is only valid while paused")
        if self.status == "stopped" and not (self.stop_reason or "").strip():
            raise ValueError("stopped revision requires stop_reason")
        if self.status != "stopped" and self.stop_reason is not None:
            raise ValueError("stop_reason is only valid while stopped")
        return self


class RevisionConsumerVersion(BaseModel):
    """Flat version provenance intended for T08 and UI consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_version_id: str = Field(min_length=1)
    parent_plan_version_id: str = Field(min_length=1)
    generated_version_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class RevisionConsumerIssue(BaseModel):
    """Flat issue transition without the internal IssueClosure object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str = Field(min_length=1)
    previous_status: Literal["not_present", "open", "resolved"]
    current_status: ClosureStatus
    closure_reason: str | None = None

    @model_validator(mode="after")
    def _validate_closure_reason(self) -> "RevisionConsumerIssue":
        if self.current_status == "resolved" and not (
            self.closure_reason or ""
        ).strip():
            raise ValueError("resolved consumer issue requires closure reason")
        return self


class RevisionConsumerDiff(BaseModel):
    """Minimal issue-to-section diff suitable for an external consumer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    section: SubstantiveSection
    evidence_refs: tuple[str, ...] = ()
    closure_status: ClosureStatus


class RevisionStatusEvent(BaseModel):
    """Ordered revision lifecycle status without internal controller state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    event_type: Literal[
        "version_created",
        "revision_retry",
        "revision_active",
        "revision_paused",
        "revision_completed",
        "revision_stopped",
    ]
    subject_id: str = Field(min_length=1)
    detail: str | None = None


class RevisionConsumerSummary(BaseModel):
    """Stable T08/UI contract that avoids parsing workflow internals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    version: RevisionConsumerVersion
    issues: tuple[RevisionConsumerIssue, ...]
    diff: tuple[RevisionConsumerDiff, ...]
    status: Literal["active", "paused", "completed", "stopped"]
    retry_count: int = Field(ge=0)
    failure_reasons: tuple[str, ...]
    stop_reason: str | None = None
    status_events: tuple[RevisionStatusEvent, ...] = Field(min_length=1)
    summary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_summary_hash(self) -> "RevisionConsumerSummary":
        payload = self.model_dump(mode="json", exclude={"summary_hash"})
        if self.summary_hash != _json_sha256(payload):
            raise ValueError("revision consumer summary hash does not match")
        return self


def build_revision_consumer_summary(
    *,
    audit: ExplainableRevisionAudit,
    plan_versions: Sequence[PlanVersion],
    revision_control: RevisionExecutionState,
    integrity: RevisionContextIntegrity,
) -> RevisionConsumerSummary:
    """Project a complete, cross-checked external revision status view."""
    versions = tuple(plan_versions)
    if not versions or versions[0].version_id != (
        integrity.lineage_provenance.source_version_id
    ):
        raise ValueError("consumer summary requires the source plan version")
    if tuple(item.version_id for item in versions) != revision_control.version_ids:
        raise ValueError("consumer summary versions must match revision control")
    generated_id = integrity.lineage_provenance.generated_version_id
    if revision_control.status == "completed" and generated_id not in {
        item.version_id for item in versions
    }:
        raise ValueError("completed revision requires the generated version")

    prior_by_id = {
        item.issue_id: item for item in integrity.issue_closure_state
    }
    audit_ids = {item.issue_id for item in audit.issue_closures}
    if not set(prior_by_id).issubset(audit_ids):
        raise ValueError("consumer issue set cannot drop context issues")
    generated_exists = generated_id in {item.version_id for item in versions}
    consumer_issue_closures = (
        audit.issue_closures
        if generated_exists
        else [
            issue
            for issue in audit.issue_closures
            if issue.issue_id in prior_by_id
        ]
    )
    issues = tuple(
        RevisionConsumerIssue(
            issue_id=issue.issue_id,
            previous_status=(
                prior_by_id[issue.issue_id].current_status
                if issue.issue_id in prior_by_id
                else "not_present"
            ),
            current_status=issue.status,
            closure_reason=issue.resolution_note,
        )
        for issue in consumer_issue_closures
    )
    diff = tuple(
        RevisionConsumerDiff(
            change_id=change.change_id,
            issue_id=change.issue_id,
            section=change.affected_plan_section,
            evidence_refs=tuple(change.evidence_refs),
            closure_status=change.closure_status,
        )
        for change in audit.changes
    )

    events: list[RevisionStatusEvent] = []
    for version in versions:
        events.append(
            RevisionStatusEvent(
                event_id=_stable_id(
                    "revision-status",
                    version.version_id,
                    "version_created",
                ),
                sequence=len(events) + 1,
                event_type="version_created",
                subject_id=version.version_id,
            )
        )
    for reason in revision_control.failure_reasons:
        events.append(
            RevisionStatusEvent(
                event_id=_stable_id(
                    "revision-status",
                    revision_control.run_id,
                    "revision_retry",
                    len(events) + 1,
                    reason,
                ),
                sequence=len(events) + 1,
                event_type="revision_retry",
                subject_id=revision_control.run_id,
                detail=reason,
            )
        )
    terminal_type = {
        "active": "revision_active",
        "paused": "revision_paused",
        "completed": "revision_completed",
        "stopped": "revision_stopped",
    }[revision_control.status]
    terminal_detail = (
        revision_control.pause_reason
        if revision_control.status == "paused"
        else revision_control.stop_reason
    )
    events.append(
        RevisionStatusEvent(
            event_id=_stable_id(
                "revision-status",
                revision_control.run_id,
                terminal_type,
                terminal_detail,
            ),
            sequence=len(events) + 1,
            event_type=terminal_type,
            subject_id=revision_control.run_id,
            detail=terminal_detail,
        )
    )
    lineage = integrity.lineage_provenance
    payload = {
        "schema_version": 1,
        "version": {
            "source_version_id": lineage.source_version_id,
            "parent_plan_version_id": lineage.parent_plan_version_id,
            "generated_version_id": lineage.generated_version_id,
            "generated_at": lineage.generated_at,
            "context_hash": lineage.context_hash,
        },
        "issues": [item.model_dump(mode="json") for item in issues],
        "diff": [item.model_dump(mode="json") for item in diff],
        "status": revision_control.status,
        "retry_count": revision_control.retry_count,
        "failure_reasons": list(revision_control.failure_reasons),
        "stop_reason": revision_control.stop_reason,
        "status_events": [item.model_dump(mode="json") for item in events],
    }
    return RevisionConsumerSummary.model_validate(
        {**payload, "summary_hash": _json_sha256(payload)}
    )


class RevisionExecutionController:
    """Small deterministic controller for retry, idempotency, pause, and restore."""

    def __init__(self, state: RevisionExecutionState) -> None:
        self.state = RevisionExecutionState.model_validate(
            state.model_dump(mode="json")
        )

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        max_iterations: int = 2,
        max_retries: int = 1,
    ) -> "RevisionExecutionController":
        return cls(
            RevisionExecutionState(
                run_id=run_id,
                max_iterations=max_iterations,
                max_retries=max_retries,
            )
        )

    def _replace(self, **updates: Any) -> None:
        payload = self.state.model_dump(mode="json")
        payload.update(updates)
        self.state = RevisionExecutionState.model_validate(payload)

    def serialize(self) -> str:
        return _canonical_json(self.state.model_dump(mode="json"))

    @classmethod
    def deserialize(
        cls,
        payload: str | bytes | Mapping[str, Any],
    ) -> "RevisionExecutionController":
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        raw = json.loads(payload) if isinstance(payload, str) else dict(payload)
        return cls(RevisionExecutionState.model_validate(raw))

    def claim_event(self, event_id: str) -> bool:
        normalized = event_id.strip()
        if not normalized:
            raise ValueError("event_id cannot be blank")
        if normalized in self.state.processed_event_ids:
            return False
        self._replace(
            processed_event_ids=(*self.state.processed_event_ids, normalized)
        )
        return True

    def record_version(self, version_id: str) -> bool:
        if version_id in self.state.version_ids:
            return False
        expected = f"{self.state.run_id}:v{len(self.state.version_ids) + 1}"
        if version_id != expected:
            raise ValueError(f"expected next version {expected}")
        self._replace(version_ids=(*self.state.version_ids, version_id))
        return True

    def advance_iteration(self) -> int:
        next_iteration = self.state.current_iteration + 1
        if next_iteration > self.state.max_iterations:
            self.stop("max_revision_iterations_exhausted")
            return self.state.current_iteration
        self._replace(current_iteration=next_iteration)
        return next_iteration

    def pause(self, reason: str) -> None:
        normalized = reason.strip()
        if not normalized:
            raise ValueError("pause reason cannot be blank")
        if self.state.status != "active":
            raise ValueError("only an active revision can be paused")
        self._replace(status="paused", pause_reason=normalized)

    def resume(self) -> None:
        if self.state.status != "paused":
            raise ValueError("only a paused revision can be resumed")
        self._replace(status="active", pause_reason=None)

    def record_failure(self, reason: str) -> Literal["retry", "stopped"]:
        normalized = reason.strip()
        if not normalized:
            raise ValueError("failure reason cannot be blank")
        retry_count = self.state.retry_count + 1
        failures = (*self.state.failure_reasons, normalized)
        if retry_count <= self.state.max_retries:
            self._replace(
                retry_count=retry_count,
                failure_reasons=failures,
            )
            return "retry"
        self._replace(
            retry_count=retry_count,
            failure_reasons=failures,
            status="stopped",
            stop_reason="retry_budget_exhausted",
        )
        return "stopped"

    def stop(self, reason: str) -> None:
        normalized = reason.strip()
        if not normalized:
            raise ValueError("stop reason cannot be blank")
        self._replace(
            status="stopped",
            pause_reason=None,
            stop_reason=normalized,
        )

    def complete(self) -> None:
        if self.state.status not in {"active", "paused"}:
            raise ValueError("only an unfinished revision can complete")
        self._replace(
            status="completed",
            pause_reason=None,
            stop_reason=None,
        )

    def rollback_last_version(self) -> str:
        if len(self.state.version_ids) < 2:
            raise ValueError("rollback requires at least two versions")
        removed = self.state.version_ids[-1]
        self._replace(
            version_ids=self.state.version_ids[:-1],
            current_iteration=max(1, self.state.current_iteration - 1),
            status="active",
            pause_reason=None,
            stop_reason=None,
        )
        return removed


def run_revision_step_with_retry(
    operation: Callable[[], Mapping[str, Any]],
    *,
    controller: RevisionExecutionController,
    step_name: str,
) -> dict[str, Any]:
    """Run one revision step with a bounded retry and fail on empty output."""
    normalized_step = step_name.strip()
    if not normalized_step:
        raise ValueError("step_name cannot be blank")
    while True:
        try:
            value = operation()
        except (TimeoutError, AgentOutputError) as exc:
            outcome = controller.record_failure(
                f"{normalized_step}:{type(exc).__name__}"
            )
            if outcome == "retry":
                continue
            raise
        if isinstance(value, Mapping) and value:
            return dict(value)
        outcome = controller.record_failure(f"{normalized_step}:empty_output")
        if outcome == "retry":
            continue
        raise ValueError(f"{normalized_step} returned empty output")


class V1V2InputFingerprints(BaseModel):
    """Exact complete-input hashes for the two reproduced rounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    v1: str = Field(pattern=r"^[0-9a-f]{64}$")
    v2: str = Field(pattern=r"^[0-9a-f]{64}$")


class TwoRoundCaseReport(BaseModel):
    """Reproducible metric package proving one V1 issue is answered by V2."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    metric_id: Literal["T02-METRIC-003"] = "T02-METRIC-003"
    case_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    v1_version_id: str = Field(min_length=1)
    v2_version_id: str = Field(min_length=1)
    input_fingerprints: V1V2InputFingerprints
    responded_issue_count: int = Field(ge=0)
    issue_ids: tuple[str, ...]
    change_ids: tuple[str, ...]
    score_changes: dict[str, ReviewScoreChange]
    candidate_hypothesis_ranking: tuple[CandidateHypothesisRank, ...]
    passed: bool = False

    @model_validator(mode="after")
    def _validate_result(self) -> "TwoRoundCaseReport":
        expected_v1 = f"{self.run_id}:v1"
        expected_v2 = f"{self.run_id}:v2"
        if (self.v1_version_id, self.v2_version_id) != (expected_v1, expected_v2):
            raise ValueError("case report requires canonical V1/V2 lineage")
        if self.passed and (
            self.responded_issue_count < 1
            or not self.issue_ids
            or not self.change_ids
            or self.input_fingerprints.v1 == self.input_fingerprints.v2
        ):
            raise ValueError("passing METRIC-003 report lacks required evidence")
        return self

    @classmethod
    def from_audit(
        cls,
        *,
        case_id: str,
        audit: ExplainableRevisionAudit,
        input_fingerprints: Mapping[str, str],
    ) -> "TwoRoundCaseReport":
        fingerprints = V1V2InputFingerprints.model_validate(input_fingerprints)
        issue_ids = tuple(
            issue.issue_id
            for issue in audit.issue_closures
            if issue.opened_in_version == 1 and issue.status == "resolved"
        )
        change_ids = tuple(change.change_id for change in audit.changes)
        passed = (
            audit.accepted
            and audit.responded_issue_count >= 1
            and bool(issue_ids)
            and bool(change_ids)
            and fingerprints.v1 != fingerprints.v2
        )
        run_id = audit.parent_version_id.rsplit(":v", 1)[0]
        return cls(
            case_id=case_id,
            run_id=run_id,
            v1_version_id=audit.lineage[0],
            v2_version_id=audit.lineage[-1],
            input_fingerprints=fingerprints,
            responded_issue_count=audit.responded_issue_count,
            issue_ids=issue_ids,
            change_ids=change_ids,
            score_changes=audit.score_changes,
            candidate_hypothesis_ranking=tuple(
                audit.candidate_hypothesis_ranking
            ),
            passed=passed,
        )


class WaveBReadiness(BaseModel):
    """Technical Ready decision; repository process approval remains external."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ready: bool
    blocking_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_decision(self) -> "WaveBReadiness":
        if self.ready == bool(self.blocking_reasons):
            raise ValueError("Ready decision contradicts blocking reasons")
        return self


def evaluate_wave_b_readiness(
    *,
    audit: ExplainableRevisionAudit,
    case_report: TwoRoundCaseReport,
    evidence_bundle: EvidenceBundle,
    branch_up_to_date: bool,
    quality_gates_passed: bool,
) -> WaveBReadiness:
    """Apply the formal Wave B technical gates without approving or merging a PR."""
    EvidenceBundle.model_validate(evidence_bundle.model_dump(mode="json"))
    blockers: list[str] = []
    if not audit.accepted:
        blockers.append("revision_audit_not_accepted")
    if not case_report.passed or case_report.responded_issue_count < 1:
        blockers.append("metric_003_not_reproduced")
    if not branch_up_to_date:
        blockers.append("branch_not_up_to_date")
    if not quality_gates_passed:
        blockers.append("quality_gates_failed")
    return WaveBReadiness(
        ready=not blockers,
        blocking_reasons=tuple(blockers),
    )


def revision_trace_fields(
    audit: ExplainableRevisionAudit,
    *,
    plan_versions: Sequence[PlanVersion],
    revision_control: RevisionExecutionState | None = None,
    integrity: RevisionContextIntegrity | None = None,
) -> dict[str, Any]:
    """Build full sidecar fields to attach to the existing V2 AgentTrace event."""
    payload = audit.model_dump(mode="json")
    fields = {
        "revision_iteration": 2,
        "revision_audit_hash": _stable_id("revision-audit", payload),
        "revision_audit": payload,
        "plan_versions": [version.model_dump(mode="json") for version in plan_versions],
    }
    if (revision_control is None) != (integrity is None):
        raise ValueError(
            "revision control and context integrity must be supplied together"
        )
    if revision_control is not None and integrity is not None:
        fields["revision_consumer_summary"] = (
            build_revision_consumer_summary(
                audit=audit,
                plan_versions=plan_versions,
                revision_control=revision_control,
                integrity=integrity,
            ).model_dump(mode="json")
        )
    return fields
