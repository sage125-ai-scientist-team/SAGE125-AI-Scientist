"""Explainable T02 experiment revision assessment and audit sidecar.

This module deliberately reuses the Wave A ``PlanVersion``, ``ReviewFeedback``
and ``IssueClosure`` contracts.  It adds workflow-owned evidence explaining how
one experiment version changed, without extending shared public schemas.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.revision import (
    IssueClosure,
    PlanVersion,
    ReviewFeedback,
    issues_from_review_feedback,
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

    @model_validator(mode="after")
    def _validate_lineage(self) -> "ExperimentRevisionContext":
        if len(set(self.lineage)) != len(self.lineage):
            raise ValueError("revision lineage cannot contain a cycle")
        if self.lineage[0] != self.parent_version_id:
            raise ValueError("lineage must start at parent_version_id")
        expected_child = self.parent_version_id.rsplit(":v", 1)[0] + ":v2"
        if self.lineage[-1] != expected_child:
            raise ValueError("revision lineage must target V2")
        return self


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
        ):
            raise ValueError("accepted revision cannot retain blockers")
        return self


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
) -> ExperimentRevisionContext:
    """Build the exact structured payload supplied to revision-round agents."""
    if previous_version.version_number != 1:
        raise ValueError("Wave B two-round context requires V1 as the parent")
    if previous_version.review_feedback is None:
        raise ValueError("previous plan version requires Reviewer feedback")
    child_id = f"{previous_version.run_id}:v2"
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
    )


def inject_revision_context(
    payload: Mapping[str, Any],
    context: ExperimentRevisionContext,
) -> dict[str, Any]:
    """Expose context at input top level and in the existing Agent message carrier."""
    result = dict(payload)
    details = context.model_dump(mode="json")
    result.update(details)
    review_result = dict(result.get("review_result") or {})
    review_result["revision_context"] = details
    result["review_result"] = review_result
    return result


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
    accepted = not blocking
    stop_reason = None
    if not final_snapshot.is_effective_pass:
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
        blocking_reasons=blocking,
        remaining_blockers=remaining,
        stop_reason=stop_reason,
        accepted=accepted,
    )


def revision_trace_fields(
    audit: ExplainableRevisionAudit,
    *,
    plan_versions: Sequence[PlanVersion],
) -> dict[str, Any]:
    """Build full sidecar fields to attach to the existing V2 AgentTrace event."""
    payload = audit.model_dump(mode="json")
    return {
        "revision_iteration": 2,
        "revision_audit_hash": _stable_id("revision-audit", payload),
        "revision_audit": payload,
        "plan_versions": [version.model_dump(mode="json") for version in plan_versions],
    }
