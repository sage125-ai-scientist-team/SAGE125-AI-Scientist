"""Fail-closed production read port for T02 revision consumers.

The frozen :mod:`app.workflow.revision_consumer` API intentionally has no
``question_id`` or per-version timestamp.  This module adds a separate binding
record and service for T08 without changing that established interface.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.contracts.revision import PlanVersion, RevisionStatus
from app.workflow.explainable_revision import StructuredRevisionDiff
from app.workflow.revision_consumer import (
    RevisionConsumerRecord,
    VersionDiffEnvelope as ConsumerVersionDiffEnvelope,
)


_SCORE_FIELDS = (
    "evidence_grounding_score",
    "falsifiability_score",
    "reproducibility_score",
    "reference_reliability_score",
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


class RevisionReadPortError(ValueError):
    """Base class for an explicit production read-port rejection."""


class RevisionIdentityError(RevisionReadPortError):
    """A supplied run/question/version identity crosses an owner boundary."""


class RevisionLineageError(RevisionReadPortError):
    """A requested or stored version relationship is not a valid lineage path."""


class FeedbackVersionBinding(BaseModel):
    """Authoritative identity binding from one feedback item to its result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feedback_id: str = Field(min_length=1)
    source_version_id: str = Field(min_length=1)
    resulting_version_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_binding(self) -> "FeedbackVersionBinding":
        if self.feedback_id != self.feedback_id.strip():
            raise ValueError("feedback_id cannot contain surrounding whitespace")
        if self.source_version_id == self.resulting_version_id:
            raise ValueError("feedback cannot produce a same-version result")
        return self


class RevisionReadSnapshot(BaseModel):
    """Persistable owner record binding Gate0 data to production identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    consumer_record: RevisionConsumerRecord
    version_timestamps: dict[str, datetime]
    validation_status: RevisionStatus
    feedback_bindings: tuple[FeedbackVersionBinding, ...] = ()
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="before")
    @classmethod
    def _canonicalize_feedback_bindings(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        bindings: dict[str, FeedbackVersionBinding] = {}
        for raw in payload.get("feedback_bindings") or ():
            binding = (
                raw
                if isinstance(raw, FeedbackVersionBinding)
                else FeedbackVersionBinding.model_validate(raw)
            )
            existing = bindings.get(binding.feedback_id)
            if existing is not None and existing != binding:
                raise ValueError(
                    "duplicate feedback_id cannot map to a different resulting version"
                )
            bindings[binding.feedback_id] = binding
        payload["feedback_bindings"] = tuple(
            bindings[key] for key in sorted(bindings)
        )
        return payload

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "RevisionReadSnapshot":
        if self.run_id != self.run_id.strip():
            raise ValueError("run_id cannot contain surrounding whitespace")
        if self.question_id != self.question_id.strip():
            raise ValueError("question_id cannot contain surrounding whitespace")
        if self.consumer_record.run_id != self.run_id:
            raise ValueError("consumer record run_id does not match production run_id")

        versions = self.consumer_record.plan_versions
        version_ids = tuple(version.version_id for version in versions)
        if set(self.version_timestamps) != set(version_ids):
            raise ValueError(
                "version_timestamps must address every and only stored plan version"
            )
        timestamps = [self.version_timestamps[version_id] for version_id in version_ids]
        if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
            raise ValueError("version timestamps must be timezone-aware")
        if timestamps != sorted(timestamps):
            raise ValueError("version timestamps must follow lineage order")

        index = {version_id: position for position, version_id in enumerate(version_ids)}
        diffs = {
            (item.source_version_id, item.target_version_id)
            for item in self.consumer_record.version_diffs
        }
        for binding in self.feedback_bindings:
            if binding.source_version_id not in index:
                raise ValueError("feedback source version is not in the bound lineage")
            if binding.resulting_version_id not in index:
                raise ValueError("feedback resulting version is not in the bound lineage")
            if index[binding.source_version_id] >= index[binding.resulting_version_id]:
                raise ValueError("feedback resulting version must follow its source")
            if (
                binding.source_version_id,
                binding.resulting_version_id,
            ) not in diffs:
                raise ValueError(
                    "feedback binding requires an authoritative owner structured diff"
                )

        expected_hash = _sha256(
            self.model_dump(mode="json", exclude={"snapshot_hash"})
        )
        if self.snapshot_hash != expected_hash:
            raise ValueError("production revision snapshot hash does not match")
        return self

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        question_id: str,
        consumer_record: RevisionConsumerRecord | Mapping[str, Any],
        version_timestamps: Mapping[str, datetime],
        validation_status: RevisionStatus,
        feedback_bindings: Sequence[
            FeedbackVersionBinding | Mapping[str, Any]
        ] = (),
    ) -> "RevisionReadSnapshot":
        """Build a canonical, self-hashed owner snapshot.

        Equal repetitions of a ``feedback_id`` are collapsed. A conflicting
        repetition fails closed instead of selecting one result.
        """
        record = (
            consumer_record
            if isinstance(consumer_record, RevisionConsumerRecord)
            else RevisionConsumerRecord.model_validate(consumer_record)
        )
        bindings_by_id: dict[str, FeedbackVersionBinding] = {}
        for raw in feedback_bindings:
            binding = (
                raw
                if isinstance(raw, FeedbackVersionBinding)
                else FeedbackVersionBinding.model_validate(raw)
            )
            existing = bindings_by_id.get(binding.feedback_id)
            if existing is not None and existing != binding:
                raise ValueError(
                    "duplicate feedback_id cannot map to a different resulting version"
                )
            bindings_by_id[binding.feedback_id] = binding
        bindings = tuple(
            bindings_by_id[key] for key in sorted(bindings_by_id)
        )
        payload = {
            "schema_version": 1,
            "run_id": run_id.strip(),
            "question_id": question_id.strip(),
            "consumer_record": record.model_dump(mode="json"),
            "version_timestamps": {
                key: value.isoformat().replace("+00:00", "Z")
                for key, value in version_timestamps.items()
            },
            "validation_status": validation_status,
            "feedback_bindings": [
                binding.model_dump(mode="json") for binding in bindings
            ],
        }
        return cls.model_validate({**payload, "snapshot_hash": _sha256(payload)})


class ReviewerView(BaseModel):
    """Reviewer scores, deltas, and stable feedback identities for a version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score: dict[str, float]
    score_delta: dict[str, float]
    feedback_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_scores(self) -> "ReviewerView":
        allowed = set(_SCORE_FIELDS)
        if set(self.score) not in (set(), allowed):
            raise ValueError("reviewer score fields are incomplete")
        if set(self.score_delta) not in (set(), allowed):
            raise ValueError("reviewer score-delta fields are incomplete")
        return self


class ReviewerIssueView(BaseModel):
    """One issue with canonical version IDs for its lifecycle endpoints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str = Field(min_length=1)
    category: Literal["critical_issue", "required_revision"]
    description: str = Field(min_length=1)
    severity: Literal["low", "medium", "high"]
    required_revision: bool
    opened_in_version: str = Field(min_length=1)
    closed_in_version: str | None = None
    closure_status: Literal["open", "resolved"]
    resolution_note: str | None = None


class RevisionStateView(BaseModel):
    """Current owner state returned without downstream closure inference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    validation_status: RevisionStatus
    stop_reason: str | None = None
    unresolved_p0: tuple[str, ...] = ()
    unresolved_p1: tuple[str, ...] = ()


class PlanVersionView(BaseModel):
    """T08-facing production projection for one authoritative PlanVersion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    version_id: str = Field(min_length=1)
    version_number: int = Field(ge=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    parent_version_id: str | None = None
    lineage: tuple[str, ...] = Field(min_length=1)
    timestamp: datetime
    reviewer: ReviewerView
    issues: tuple[ReviewerIssueView, ...]
    state: RevisionStateView


class VersionDiffEnvelope(BaseModel):
    """T08-facing owner diff addressed by the full production identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    from_version_id: str = Field(min_length=1)
    to_version_id: str = Field(min_length=1)
    lineage: tuple[str, ...] = Field(min_length=2)
    timestamp: datetime
    diff: StructuredRevisionDiff
    diff_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_diff_hash(self) -> "VersionDiffEnvelope":
        if self.diff_hash != self.diff.fingerprint():
            raise ValueError("version diff hash does not match canonical content")
        return self


class RevisionProductionReadPort:
    """Stable T08 service over authoritative, self-validating T02 snapshots."""

    def __init__(
        self,
        snapshots: Sequence[RevisionReadSnapshot | Mapping[str, Any]] = (),
    ) -> None:
        self._snapshots_by_run: dict[str, RevisionReadSnapshot] = {}
        self._runs_by_question: dict[str, set[str]] = defaultdict(set)
        self._version_owners: dict[str, tuple[str, str]] = {}
        for raw in snapshots:
            snapshot = RevisionReadSnapshot.model_validate(
                raw.model_dump(mode="json")
                if isinstance(raw, RevisionReadSnapshot)
                else raw
            )
            if snapshot.run_id in self._snapshots_by_run:
                raise ValueError(f"duplicate production run_id: {snapshot.run_id}")
            for version in snapshot.consumer_record.plan_versions:
                if version.version_id in self._version_owners:
                    raise ValueError(
                        f"duplicate production version_id: {version.version_id}"
                    )
                self._version_owners[version.version_id] = (
                    snapshot.run_id,
                    snapshot.question_id,
                )
            self._snapshots_by_run[snapshot.run_id] = snapshot
            self._runs_by_question[snapshot.question_id].add(snapshot.run_id)

    def _resolve(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> RevisionReadSnapshot:
        normalized_run = run_id.strip()
        normalized_question = question_id.strip()
        if not normalized_run or not normalized_question:
            raise RevisionIdentityError("run_id and question_id must be non-empty")
        try:
            snapshot = self._snapshots_by_run[normalized_run]
        except KeyError as exc:
            raise KeyError(f"unknown run_id: {normalized_run}") from exc
        if snapshot.question_id != normalized_question:
            if normalized_question in self._runs_by_question:
                raise RevisionIdentityError(
                    "cross-run identity: question_id belongs to another run"
                )
            raise RevisionIdentityError(
                "question_id does not match the authoritative run record"
            )
        return snapshot

    @staticmethod
    def _validated_record(snapshot: RevisionReadSnapshot) -> RevisionConsumerRecord:
        try:
            record = RevisionConsumerRecord.model_validate(
                snapshot.consumer_record.model_dump(mode="json")
            )
        except ValidationError as exc:
            raise RevisionLineageError(
                "broken lineage in authoritative consumer record"
            ) from exc
        if record.run_id != snapshot.run_id:
            raise RevisionIdentityError(
                "consumer run_id does not match the authoritative run/question lineage"
            )
        if set(snapshot.version_timestamps) != {
            version.version_id for version in record.plan_versions
        }:
            raise RevisionLineageError(
                "version timestamps do not match the authoritative lineage"
            )
        return record

    def _require_version_owner(
        self,
        *,
        run_id: str,
        question_id: str,
        version_id: str,
    ) -> None:
        try:
            owner = self._version_owners[version_id]
        except KeyError as exc:
            raise KeyError(f"unknown version_id: {version_id}") from exc
        if owner != (run_id, question_id):
            raise RevisionIdentityError(
                f"version_id {version_id!r} belongs to another run/question lineage"
            )

    @staticmethod
    def _issue_views(
        version: PlanVersion,
        versions: Sequence[PlanVersion],
    ) -> tuple[ReviewerIssueView, ...]:
        by_number = {item.version_number: item for item in versions}
        views: list[ReviewerIssueView] = []
        for issue in version.issue_closures:
            try:
                opened_version = by_number[issue.opened_in_version]
            except KeyError as exc:
                raise RevisionLineageError(
                    "issue opened_in_version is outside the authoritative lineage"
                ) from exc
            if opened_version.review_feedback is None:
                raise RevisionLineageError(
                    "issue severity is absent from the authoritative reviewer snapshot"
                )
            closed_version_id: str | None = None
            if issue.closed_in_version is not None:
                try:
                    closed_version_id = by_number[issue.closed_in_version].version_id
                except KeyError as exc:
                    raise RevisionLineageError(
                        "issue closed_in_version is outside the authoritative lineage"
                    ) from exc
            views.append(
                ReviewerIssueView(
                    issue_id=issue.issue_id,
                    category=issue.category,
                    description=issue.description,
                    severity=opened_version.review_feedback.risk_level,
                    required_revision=issue.category == "required_revision",
                    opened_in_version=opened_version.version_id,
                    closed_in_version=closed_version_id,
                    closure_status=issue.status,
                    resolution_note=issue.resolution_note,
                )
            )
        return tuple(sorted(views, key=lambda item: item.issue_id))

    @staticmethod
    def _state_view(
        snapshot: RevisionReadSnapshot,
        record: RevisionConsumerRecord,
    ) -> RevisionStateView:
        latest = record.plan_versions[-1]
        return RevisionStateView(
            validation_status=snapshot.validation_status,
            stop_reason=record.revision_control.stop_reason,
            unresolved_p0=tuple(
                sorted(
                    issue.issue_id
                    for issue in latest.issue_closures
                    if issue.status == "open" and issue.category == "critical_issue"
                )
            ),
            unresolved_p1=tuple(
                sorted(
                    issue.issue_id
                    for issue in latest.issue_closures
                    if issue.status == "open" and issue.category == "required_revision"
                )
            ),
        )

    def list_plan_versions(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> list[PlanVersionView]:
        snapshot = self._resolve(run_id=run_id, question_id=question_id)
        record = self._validated_record(snapshot)
        lineage = tuple(version.version_id for version in record.plan_versions)
        state = self._state_view(snapshot, record)
        score_deltas = (
            record.revision_audit.score_changes
            if record.revision_audit is not None
            else {}
        )
        feedback_ids_by_version: dict[str, list[str]] = defaultdict(list)
        for binding in snapshot.feedback_bindings:
            feedback_ids_by_version[binding.resulting_version_id].append(
                binding.feedback_id
            )

        result: list[PlanVersionView] = []
        for version in record.plan_versions:
            feedback = version.review_feedback
            score = (
                {name: getattr(feedback, name) for name in _SCORE_FIELDS}
                if feedback is not None
                else {}
            )
            is_diff_target = any(
                diff.target_version_id == version.version_id
                for diff in record.version_diffs
            )
            delta = (
                {name: score_deltas[name].delta for name in _SCORE_FIELDS}
                if is_diff_target and set(score_deltas) == set(_SCORE_FIELDS)
                else {}
            )
            result.append(
                PlanVersionView(
                    version_id=version.version_id,
                    version_number=version.version_number,
                    run_id=record.run_id,
                    question_id=snapshot.question_id,
                    parent_version_id=version.parent_version_id,
                    lineage=lineage,
                    timestamp=snapshot.version_timestamps[version.version_id],
                    reviewer=ReviewerView(
                        score=score,
                        score_delta=delta,
                        feedback_ids=tuple(
                            sorted(feedback_ids_by_version[version.version_id])
                        ),
                    ),
                    issues=self._issue_views(version, record.plan_versions),
                    state=state,
                )
            )
        return result

    def get_version_diff(
        self,
        *,
        run_id: str,
        question_id: str,
        from_version_id: str,
        to_version_id: str,
    ) -> VersionDiffEnvelope:
        snapshot = self._resolve(run_id=run_id, question_id=question_id)
        record = self._validated_record(snapshot)
        normalized_run = run_id.strip()
        normalized_question = question_id.strip()
        for version_id in (from_version_id, to_version_id):
            self._require_version_owner(
                run_id=normalized_run,
                question_id=normalized_question,
                version_id=version_id,
            )
        if from_version_id == to_version_id:
            raise RevisionLineageError("same-version diff is not allowed")

        versions = tuple(record.plan_versions)
        index = {version.version_id: position for position, version in enumerate(versions)}
        from_index = index[from_version_id]
        to_index = index[to_version_id]
        if from_index > to_index:
            raise RevisionLineageError("reversed version order is not allowed")

        parent_by_id = {
            version.version_id: version.parent_version_id for version in versions
        }
        cursor: str | None = to_version_id
        while cursor is not None and cursor != from_version_id:
            cursor = parent_by_id.get(cursor)
        if cursor != from_version_id:
            raise RevisionLineageError(
                "from_version_id is not an ancestor of to_version_id"
            )

        owner_diffs: list[ConsumerVersionDiffEnvelope] = [
            diff
            for diff in record.version_diffs
            if diff.source_version_id == from_version_id
            and diff.target_version_id == to_version_id
        ]
        if len(owner_diffs) != 1:
            raise RevisionLineageError(
                "no unique authoritative owner structured diff exists for this interval"
            )
        owner_diff = owner_diffs[0]
        return VersionDiffEnvelope(
            run_id=record.run_id,
            question_id=snapshot.question_id,
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            lineage=tuple(version.version_id for version in versions),
            timestamp=snapshot.version_timestamps[to_version_id],
            diff=owner_diff.diff,
            diff_hash=owner_diff.diff_hash,
        )


__all__ = [
    "FeedbackVersionBinding",
    "PlanVersionView",
    "ReviewerIssueView",
    "ReviewerView",
    "RevisionIdentityError",
    "RevisionLineageError",
    "RevisionProductionReadPort",
    "RevisionReadPortError",
    "RevisionReadSnapshot",
    "RevisionStateView",
    "VersionDiffEnvelope",
]
