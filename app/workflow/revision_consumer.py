"""Fail-closed, read-only consumer interface for T02 revision artifacts.

This module deliberately composes the frozen T02 contracts.  It does not
participate in revision generation or mutate workflow state.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.revision import IssueClosure, PlanVersion
from app.workflow.explainable_revision import (
    ExperimentRevisionContext,
    ExplainableRevisionAudit,
    ReviewScoreChange,
    RevisionExecutionState,
    StructuredRevisionDiff,
)


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


def _lineage_payload(run_id: str, versions: Sequence[PlanVersion]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "versions": [
            {
                "version_id": version.version_id,
                "version_number": version.version_number,
                "parent_version_id": version.parent_version_id,
            }
            for version in versions
        ],
    }


def _lineage_fingerprint(run_id: str, versions: Sequence[PlanVersion]) -> str:
    return _sha256(_lineage_payload(run_id, versions))


class VersionDiffEnvelope(BaseModel):
    """Address one canonical structured diff by its resulting version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    source_version_id: str = Field(min_length=1)
    target_version_id: str = Field(min_length=1)
    diff: StructuredRevisionDiff
    diff_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_envelope(self) -> "VersionDiffEnvelope":
        source_run, separator, source_number = self.source_version_id.rpartition(":v")
        target_run, target_separator, target_number = self.target_version_id.rpartition(
            ":v"
        )
        if (
            separator != ":v"
            or target_separator != ":v"
            or not source_run
            or source_run != target_run
            or not source_number.isdigit()
            or not target_number.isdigit()
            or int(target_number) != int(source_number) + 1
        ):
            raise ValueError("version diff must address a direct child version")
        if not self.diff.changes:
            raise ValueError("version diff must contain at least one change")
        change_ids = [change.change_id for change in self.diff.changes]
        if len(change_ids) != len(set(change_ids)):
            raise ValueError("version diff change IDs must be unique")
        affected = {change.affected_plan_section for change in self.diff.changes}
        if set(self.diff.substantive_sections) != affected:
            raise ValueError("version diff substantive sections do not match changes")
        expected = self.diff.fingerprint()
        if self.diff_hash != expected:
            raise ValueError("version diff hash does not match canonical content")
        return self


class ReviewerIssueView(BaseModel):
    """Stable reviewer issue view with an explicit Gate 0 priority mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str = Field(min_length=1)
    priority: Literal["P0", "P1"]
    category: Literal["critical_issue", "required_revision"]
    description: str = Field(min_length=1)
    status: Literal["open", "resolved"]
    severity: Literal["low", "medium", "high"]
    opened_in_version: int = Field(ge=1)
    closed_in_version: int | None = Field(default=None, ge=1)
    resolution_note: str | None = None


class LineageView(BaseModel):
    """Validated lineage projection for one run/job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    version_ids: tuple[str, ...] = Field(min_length=1)
    parents: dict[str, str | None]
    lineage_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class RevisionConsumerRecord(BaseModel):
    """One complete, validated T02 consumer snapshot for a run/job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    plan_versions: tuple[PlanVersion, ...] = Field(min_length=1, max_length=2)
    revision_context: ExperimentRevisionContext | None = None
    revision_audit: ExplainableRevisionAudit | None = None
    revision_control: RevisionExecutionState
    version_diffs: tuple[VersionDiffEnvelope, ...] = ()
    lineage_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_record(self) -> "RevisionConsumerRecord":
        versions = self.plan_versions
        expected_numbers = list(range(1, len(versions) + 1))
        if [version.version_number for version in versions] != expected_numbers:
            raise ValueError("plan version lineage must be contiguous and ordered from V1")
        for index, version in enumerate(versions):
            if version.run_id != self.run_id:
                raise ValueError("plan version run_id does not match consumer record")
            expected_parent = None if index == 0 else versions[index - 1].version_id
            if version.parent_version_id != expected_parent:
                raise ValueError("plan version parent lineage is broken")

        expected_version_ids = tuple(version.version_id for version in versions)
        if self.revision_control.run_id != self.run_id:
            raise ValueError("revision control run_id does not match consumer record")
        if self.revision_control.version_ids != expected_version_ids:
            raise ValueError("revision control version lineage does not match plan versions")
        if self.lineage_hash != _lineage_fingerprint(self.run_id, versions):
            raise ValueError("lineage hash does not match plan version content")

        self._validate_issue_history()

        if len(versions) == 1:
            if self.revision_context is not None or self.revision_audit is not None:
                raise ValueError("V1-only record cannot contain V2 revision artifacts")
            if self.version_diffs:
                raise ValueError("V1-only record cannot contain a version diff")
            return self

        if self.revision_context is None:
            raise ValueError("V2 consumer record requires revision context")
        if self.revision_audit is None:
            raise ValueError("V2 consumer record requires revision audit")
        if len(self.version_diffs) != 1:
            raise ValueError("V2 consumer record requires exactly one version diff")

        first, second = versions
        expected_lineage = [first.version_id, second.version_id]
        if PlanVersion.model_validate(
            self.revision_context.previous_plan_version
        ) != first:
            raise ValueError("revision context previous plan version does not match V1")
        if self.revision_context.parent_version_id != first.version_id:
            raise ValueError("revision context parent version does not match V1")
        if self.revision_context.lineage != expected_lineage:
            raise ValueError("revision context lineage does not match plan versions")
        if self.revision_context.reviewer_feedback != first.review_feedback:
            raise ValueError("context reviewer feedback does not match V1")
        expected_unresolved = [
            issue for issue in first.issue_closures if issue.status == "open"
        ]
        if self.revision_context.unresolved_issues != expected_unresolved:
            raise ValueError("context unresolved issues do not match V1")
        expected_previous_plan = {
            "hypothesis_generation": first.hypothesis_generation,
            "experiment_design": first.experiment_design,
        }
        if self.revision_context.previous_plan != expected_previous_plan:
            raise ValueError("revision context previous plan does not match V1")

        audit = self.revision_audit
        if PlanVersion.model_validate(audit.previous_plan_version) != first:
            raise ValueError("revision audit previous plan version does not match V1")
        if audit.parent_version_id != first.version_id:
            raise ValueError("revision audit parent version does not match V1")
        if audit.lineage != expected_lineage:
            raise ValueError("revision audit lineage does not match plan versions")
        if audit.reviewer_feedback != first.review_feedback:
            raise ValueError("revision audit reviewer feedback does not match V1")
        if audit.final_reviewer_feedback != second.review_feedback:
            raise ValueError("revision audit final reviewer feedback does not match V2")
        if audit.issue_closures != second.issue_closures:
            raise ValueError("revision audit issue closures do not match V2")
        if audit.previous_plan != expected_previous_plan:
            raise ValueError("revision audit previous plan does not match V1")
        if audit.failure_reasons != self.revision_context.failure_reasons:
            raise ValueError("revision audit failure reasons do not match context")

        envelope = self.version_diffs[0]
        if (
            envelope.source_version_id != first.version_id
            or envelope.target_version_id != second.version_id
        ):
            raise ValueError("version diff lineage does not match plan versions")
        if envelope.diff != StructuredRevisionDiff.from_audit(audit):
            raise ValueError("version diff does not match revision audit")
        self._validate_score_changes(first, second, audit)

        expected_terminal = "completed" if audit.accepted else "stopped"
        if self.revision_control.status != expected_terminal:
            raise ValueError("revision audit terminal state contradicts controller")
        if audit.stop_reason != self.revision_control.stop_reason:
            raise ValueError("revision audit stop reason contradicts revision control")
        return self

    def _validate_issue_history(self) -> None:
        previous: dict[str, IssueClosure] = {}
        for version in self.plan_versions:
            current: dict[str, IssueClosure] = {}
            for issue in version.issue_closures:
                if issue.issue_id in current:
                    raise ValueError("plan version issue IDs must be unique")
                current[issue.issue_id] = issue
                old = previous.get(issue.issue_id)
                if old is None and issue.opened_in_version != version.version_number:
                    raise ValueError(
                        "reviewer issue opened_in_version must match first appearance"
                    )
                if old is not None:
                    identity = (issue.category, issue.description, issue.opened_in_version)
                    old_identity = (old.category, old.description, old.opened_in_version)
                    if identity != old_identity:
                        raise ValueError("reviewer issue identity changed across versions")
                    if old.status == "resolved" and issue.status != "resolved":
                        raise ValueError("resolved reviewer issue cannot reopen")
                    if old.status == "resolved" and issue != old:
                        raise ValueError("resolved reviewer issue cannot change history")
                    if (
                        old.status == "open"
                        and issue.status == "resolved"
                        and issue.closed_in_version != version.version_number
                    ):
                        raise ValueError(
                            "reviewer issue closure must match transition version"
                        )
            if previous and not set(previous).issubset(current):
                raise ValueError("reviewer issue history cannot be silently dropped")

            feedback = version.review_feedback
            if feedback is not None:
                expected_open = {
                    ("critical_issue", description.strip())
                    for description in feedback.critical_issues
                    if description.strip()
                } | {
                    ("required_revision", description.strip())
                    for description in feedback.required_revisions
                    if description.strip()
                }
                actual_open = {
                    (issue.category, issue.description)
                    for issue in current.values()
                    if issue.status == "open"
                }
                if actual_open != expected_open:
                    raise ValueError(
                        "open reviewer issues do not match plan review feedback"
                    )
            previous = current

    @staticmethod
    def _validate_score_changes(
        first: PlanVersion,
        second: PlanVersion,
        audit: ExplainableRevisionAudit,
    ) -> None:
        if first.review_feedback is None or second.review_feedback is None:
            raise ValueError("V1/V2 score delta requires both reviewer feedback snapshots")
        score_fields = (
            "evidence_grounding_score",
            "falsifiability_score",
            "reproducibility_score",
            "reference_reliability_score",
        )
        if set(audit.score_changes) != set(score_fields):
            raise ValueError("revision audit score delta fields are incomplete")
        for name in score_fields:
            score = audit.score_changes[name]
            before = getattr(first.review_feedback, name)
            after = getattr(second.review_feedback, name)
            if not (
                math.isclose(score.before, before, abs_tol=1e-12)
                and math.isclose(score.after, after, abs_tol=1e-12)
                and math.isclose(score.delta, after - before, abs_tol=1e-12)
            ):
                raise ValueError(f"revision audit score delta is invalid for {name}")


class RevisionConsumerStore:
    """In-process read facade with fail-closed run, job, and version lookup."""

    def __init__(
        self,
        records: Sequence[RevisionConsumerRecord | Mapping[str, Any]] = (),
    ) -> None:
        self._records_by_run: dict[str, RevisionConsumerRecord] = {}
        self._run_by_job: dict[str, str] = {}
        self._versions: dict[str, PlanVersion] = {}
        self._diffs: dict[str, VersionDiffEnvelope] = {}
        for value in records:
            record = RevisionConsumerRecord.model_validate(
                value.model_dump(mode="json")
                if isinstance(value, RevisionConsumerRecord)
                else value
            )
            if record.job_id in self._run_by_job:
                raise ValueError(f"duplicate job_id: {record.job_id}")
            if record.run_id in self._records_by_run:
                raise ValueError(f"duplicate run_id: {record.run_id}")
            for version in record.plan_versions:
                if version.version_id in self._versions:
                    raise ValueError(f"duplicate version_id: {version.version_id}")
            for envelope in record.version_diffs:
                if envelope.target_version_id in self._diffs:
                    raise ValueError(
                        f"duplicate version diff: {envelope.target_version_id}"
                    )
            self._records_by_run[record.run_id] = record
            self._run_by_job[record.job_id] = record.run_id
            self._versions.update(
                (version.version_id, version) for version in record.plan_versions
            )
            self._diffs.update(
                (diff.target_version_id, diff) for diff in record.version_diffs
            )

    @property
    def records(self) -> tuple[RevisionConsumerRecord, ...]:
        return tuple(
            RevisionConsumerRecord.model_validate(record.model_dump(mode="json"))
            for record in self._records_by_run.values()
        )

    def _resolve(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> RevisionConsumerRecord:
        normalized_run = (run_id or "").strip()
        normalized_job = (job_id or "").strip()
        if bool(normalized_run) == bool(normalized_job):
            raise ValueError("provide exactly one of run_id or job_id")
        if normalized_job:
            try:
                normalized_run = self._run_by_job[normalized_job]
            except KeyError as exc:
                raise KeyError(f"unknown job_id: {normalized_job}") from exc
        try:
            return self._records_by_run[normalized_run]
        except KeyError as exc:
            raise KeyError(f"unknown run_id: {normalized_run}") from exc

    def list_plan_versions(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> list[PlanVersion]:
        record = self._resolve(run_id=run_id, job_id=job_id)
        return [version.model_copy(deep=True) for version in record.plan_versions]

    def get_plan_version(self, version_id: str) -> PlanVersion:
        try:
            return self._versions[version_id].model_copy(deep=True)
        except KeyError as exc:
            raise KeyError(f"unknown version_id: {version_id}") from exc

    def get_version_diff(self, target_version_id: str) -> VersionDiffEnvelope:
        try:
            value = self._diffs[target_version_id]
        except KeyError as exc:
            raise KeyError(f"unknown version diff: {target_version_id}") from exc
        return VersionDiffEnvelope.model_validate(value.model_dump(mode="json"))

    def get_reviewer_issues(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> list[ReviewerIssueView]:
        record = self._resolve(run_id=run_id, job_id=job_id)
        latest = record.plan_versions[-1]
        severities = {
            version.version_number: (
                version.review_feedback.risk_level
                if version.review_feedback is not None
                else "medium"
            )
            for version in record.plan_versions
        }
        issues = [
            ReviewerIssueView(
                issue_id=issue.issue_id,
                priority="P0" if issue.category == "critical_issue" else "P1",
                category=issue.category,
                description=issue.description,
                status=issue.status,
                severity=severities[issue.opened_in_version],
                opened_in_version=issue.opened_in_version,
                closed_in_version=issue.closed_in_version,
                resolution_note=issue.resolution_note,
            )
            for issue in latest.issue_closures
        ]
        return sorted(issues, key=lambda item: (item.priority, item.issue_id))

    def get_issue_closures(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> list[IssueClosure]:
        record = self._resolve(run_id=run_id, job_id=job_id)
        return [
            issue.model_copy(deep=True)
            for issue in record.plan_versions[-1].issue_closures
        ]

    def get_score_deltas(self, target_version_id: str) -> dict[str, ReviewScoreChange]:
        envelope = self.get_version_diff(target_version_id)
        record = self._records_by_run[
            envelope.target_version_id.rsplit(":v", 1)[0]
        ]
        if record.revision_audit is None:
            raise KeyError(f"unknown score delta: {target_version_id}")
        return {
            name: ReviewScoreChange.model_validate(score.model_dump(mode="json"))
            for name, score in record.revision_audit.score_changes.items()
        }

    def get_lineage(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> LineageView:
        record = self._resolve(run_id=run_id, job_id=job_id)
        return LineageView(
            run_id=record.run_id,
            job_id=record.job_id,
            version_ids=tuple(version.version_id for version in record.plan_versions),
            parents={
                version.version_id: version.parent_version_id
                for version in record.plan_versions
            },
            lineage_hash=record.lineage_hash,
        )

    def get_stop_reason(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> str | None:
        return self._resolve(run_id=run_id, job_id=job_id).revision_control.stop_reason

    def get_open_p0_p1(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> list[ReviewerIssueView]:
        return [
            issue
            for issue in self.get_reviewer_issues(run_id=run_id, job_id=job_id)
            if issue.status == "open"
        ]


__all__ = [
    "LineageView",
    "ReviewerIssueView",
    "RevisionConsumerRecord",
    "RevisionConsumerStore",
    "VersionDiffEnvelope",
]
