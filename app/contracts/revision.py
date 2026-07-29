"""T02 reviewer-driven revision contracts.

The models in this module are deliberately independent from ``PipelineState``.
They provide a versioned, serializable boundary for reviewer feedback, prompt
construction, plan lineage, issue closure, and backward-compatible restores.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RevisionStatus = Literal["draft", "needs_data", "ready_for_validation", "validated"]
IssueCategory = Literal["critical_issue", "required_revision"]
IssueStatus = Literal["open", "resolved"]


def _canonical_json(value: Any) -> str:
    """Return deterministic JSON for fingerprints and serialized snapshots."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


class ReviewFeedback(BaseModel):
    """Serializable snapshot of the public ``ReviewResult`` fields."""

    model_config = ConfigDict(extra="forbid")

    passed: bool = False
    reviewer_comments: list[str] = Field(default_factory=list)
    critical_issues: list[str] = Field(default_factory=list)
    required_revisions: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "medium"
    evidence_grounding_score: float = Field(default=0.0, ge=0.0, le=1.0)
    falsifiability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reproducibility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reference_reliability_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def is_effective_pass(self) -> bool:
        """Require an explicit pass and no blocking issue or revision."""
        return (
            self.passed is True
            and not self.critical_issues
            and not self.required_revisions
        )

    @classmethod
    def from_review_result(
        cls,
        value: "ReviewFeedback | Mapping[str, Any] | None",
    ) -> "ReviewFeedback":
        """Create a defensive feedback snapshot from a model or mapping."""
        if isinstance(value, cls):
            return value.model_copy(deep=True)
        return cls.model_validate(dict(value or {}))


class IssueClosure(BaseModel):
    """Track one blocking reviewer issue from opening through resolution."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str = Field(min_length=1)
    category: IssueCategory
    description: str = Field(min_length=1)
    status: IssueStatus = "open"
    opened_in_version: int = Field(ge=1)
    closed_in_version: int | None = Field(default=None, ge=1)
    resolution_note: str | None = None

    @model_validator(mode="after")
    def _validate_closure(self) -> "IssueClosure":
        if self.status == "open" and self.closed_in_version is not None:
            raise ValueError("open issue cannot have closed_in_version")
        if self.status == "resolved":
            if self.closed_in_version is None:
                raise ValueError("resolved issue requires closed_in_version")
            if self.closed_in_version < self.opened_in_version:
                raise ValueError("closed_in_version cannot precede opened_in_version")
        return self


def issues_from_review_feedback(
    feedback: ReviewFeedback | Mapping[str, Any],
    *,
    opened_in_version: int,
) -> list[IssueClosure]:
    """Create stable issue IDs without UUIDs, timestamps, or random values."""
    snapshot = ReviewFeedback.from_review_result(feedback)
    issues: list[IssueClosure] = []
    seen: set[tuple[IssueCategory, str]] = set()
    groups: tuple[tuple[IssueCategory, list[str]], ...] = (
        ("critical_issue", snapshot.critical_issues),
        ("required_revision", snapshot.required_revisions),
    )
    for category, descriptions in groups:
        for description in descriptions:
            normalized = description.strip()
            key = (category, normalized)
            if not normalized or key in seen:
                continue
            seen.add(key)
            digest = hashlib.sha256(
                f"{category}\n{normalized}".encode("utf-8")
            ).hexdigest()[:12]
            issues.append(
                IssueClosure(
                    issue_id=f"{category}:{digest}",
                    category=category,
                    description=normalized,
                    opened_in_version=opened_in_version,
                )
            )
    return issues


class RevisionContext(BaseModel):
    """Authoritative semantic revision input for one generation round."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    revision_iteration: int = Field(default=1, ge=1)
    review_feedback: ReviewFeedback | None = None
    issue_closures: list[IssueClosure] = Field(default_factory=list)


class PlanVersion(BaseModel):
    """Complete addressable V1/V2 plan snapshot with deterministic lineage."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    version_number: int = Field(ge=1)
    version_id: str = Field(min_length=1)
    parent_version_id: str | None = None
    revision_iteration: int = Field(ge=1)
    hypothesis_generation: dict[str, Any] = Field(default_factory=dict)
    experiment_design: dict[str, Any] = Field(default_factory=dict)
    review_feedback: ReviewFeedback | None = None
    issue_closures: list[IssueClosure] = Field(default_factory=list)
    prompt_fingerprints: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_lineage(self) -> "PlanVersion":
        expected_id = f"{self.run_id}:v{self.version_number}"
        if self.version_id != expected_id:
            raise ValueError(f"version_id must be deterministic: {expected_id}")
        if self.version_number == 1 and self.parent_version_id is not None:
            raise ValueError("V1 cannot have a parent_version_id")
        if self.version_number > 1 and not self.parent_version_id:
            raise ValueError("V2+ requires parent_version_id")
        return self

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        version_number: int,
        revision_iteration: int,
        parent_version_id: str | None = None,
        hypothesis_generation: Mapping[str, Any] | None = None,
        experiment_design: Mapping[str, Any] | None = None,
        review_feedback: ReviewFeedback | Mapping[str, Any] | None = None,
        issue_closures: Sequence[IssueClosure | Mapping[str, Any]] = (),
        prompt_fingerprints: Mapping[str, str] | None = None,
    ) -> "PlanVersion":
        """Build a version with its canonical ID and defensive snapshots."""
        feedback = (
            ReviewFeedback.from_review_result(review_feedback)
            if review_feedback is not None
            else None
        )
        return cls(
            run_id=run_id,
            version_number=version_number,
            version_id=f"{run_id}:v{version_number}",
            parent_version_id=parent_version_id,
            revision_iteration=revision_iteration,
            hypothesis_generation=dict(hypothesis_generation or {}),
            experiment_design=dict(experiment_design or {}),
            review_feedback=feedback,
            issue_closures=[
                issue
                if isinstance(issue, IssueClosure)
                else IssueClosure.model_validate(issue)
                for issue in issue_closures
            ],
            prompt_fingerprints=dict(prompt_fingerprints or {}),
        )


class RevisionState(BaseModel):
    """Round-trip-safe aggregate of revision context and plan versions."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    context: RevisionContext
    versions: list[PlanVersion] = Field(default_factory=list)
    validation_status: RevisionStatus = "draft"

    @model_validator(mode="after")
    def _validate_state(self) -> "RevisionState":
        expected_numbers = list(range(1, len(self.versions) + 1))
        actual_numbers = [version.version_number for version in self.versions]
        if actual_numbers != expected_numbers:
            raise ValueError("plan versions must be contiguous and ordered from V1")
        for index, version in enumerate(self.versions):
            if version.run_id != self.context.run_id:
                raise ValueError("plan version run_id must match revision context")
            expected_parent = None if index == 0 else self.versions[index - 1].version_id
            if version.parent_version_id != expected_parent:
                raise ValueError("plan version parent must reference the previous version")
        has_open_issue = any(
            issue.status == "open"
            for issue in self.context.issue_closures
        )
        feedback_blocks = (
            self.context.review_feedback is not None
            and not self.context.review_feedback.is_effective_pass
        )
        if (
            self.validation_status in ("ready_for_validation", "validated")
            and (has_open_issue or feedback_blocks)
        ):
            raise ValueError("blocking reviewer feedback requires a draft terminal state")
        return self


class RevisionPromptBuilder:
    """Build deterministic first- and second-round agent inputs."""

    @staticmethod
    def _base(context: RevisionContext) -> dict[str, Any]:
        if context.revision_iteration > 1 and context.review_feedback is None:
            raise ValueError("revision round requires previous ReviewFeedback")
        payload: dict[str, Any] = {
            "revision_iteration": context.revision_iteration,
        }
        if context.review_feedback is not None:
            payload["review_result"] = context.review_feedback.model_dump(mode="json")
        return payload

    @classmethod
    def build_hypothesis_input(
        cls,
        context: RevisionContext,
        *,
        question_item: Mapping[str, Any],
        evidence_catalog: Sequence[Mapping[str, Any]],
        evidence_extraction: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Build the actual HypothesisGenerator ``input_data``."""
        payload = cls._base(context)
        payload.update(
            {
                "question_item": dict(question_item),
                "evidence_catalog": [dict(item) for item in evidence_catalog],
                "evidence_extraction": dict(evidence_extraction or {}),
            }
        )
        return payload

    @classmethod
    def build_experiment_input(
        cls,
        context: RevisionContext,
        *,
        question_item: Mapping[str, Any],
        question_type: str,
        recommended_hypothesis: Mapping[str, Any],
        hypothesis_generation: Mapping[str, Any] | None,
        evidence_extraction: Mapping[str, Any] | None,
        evidence_catalog: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Build the actual ExperimentDesigner ``input_data``."""
        payload = cls._base(context)
        payload.update(
            {
                "question_item": dict(question_item),
                "question_type": question_type,
                "recommended_hypothesis": dict(recommended_hypothesis),
                "hypothesis_generation": dict(hypothesis_generation or {}),
                "evidence_extraction": dict(evidence_extraction or {}),
                "evidence_catalog": [dict(item) for item in evidence_catalog],
            }
        )
        return payload

    @classmethod
    def build_reviewer_input(
        cls,
        context: RevisionContext,
        *,
        question_item: Mapping[str, Any],
        recommended_hypothesis: Mapping[str, Any],
        hypothesis_generation: Mapping[str, Any] | None,
        experiment_design: Mapping[str, Any] | None,
        evidence_extraction: Mapping[str, Any] | None,
        evidence_catalog: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Build the actual ScientificReviewer ``input_data``."""
        payload = cls._base(context)
        payload.update(
            {
                "question_item": dict(question_item),
                "recommended_hypothesis": dict(recommended_hypothesis),
                "hypothesis_generation": dict(hypothesis_generation or {}),
                "experiment_design": dict(experiment_design or {}),
                "evidence_extraction": dict(evidence_extraction or {}),
                "evidence_catalog": [dict(item) for item in evidence_catalog],
            }
        )
        return payload

    @staticmethod
    def fingerprint(payload: Mapping[str, Any]) -> str:
        """Fingerprint the complete deterministic input, without truncation."""
        return hashlib.sha256(_canonical_json(dict(payload)).encode("utf-8")).hexdigest()


class PlanVersionStore:
    """Minimal in-process version store with serializable save/read semantics."""

    def __init__(
        self,
        versions: Sequence[PlanVersion | Mapping[str, Any]] = (),
    ) -> None:
        self._versions: dict[str, list[PlanVersion]] = {}
        for version in versions:
            self.save(version)

    def save(
        self,
        version: PlanVersion | Mapping[str, Any],
    ) -> PlanVersion:
        """Save exactly the next version and validate its parent lineage."""
        snapshot = (
            version.model_copy(deep=True)
            if isinstance(version, PlanVersion)
            else PlanVersion.model_validate(version)
        )
        existing = self._versions.setdefault(snapshot.run_id, [])
        expected_number = len(existing) + 1
        expected_parent = None if not existing else existing[-1].version_id
        if snapshot.version_number != expected_number:
            raise ValueError(f"expected V{expected_number}, got V{snapshot.version_number}")
        if snapshot.parent_version_id != expected_parent:
            raise ValueError("parent_version_id must reference the latest saved version")
        existing.append(snapshot)
        return snapshot.model_copy(deep=True)

    def get(self, run_id: str, version_number: int) -> PlanVersion:
        """Read one version by run and number without exposing mutable storage."""
        versions = self._versions.get(run_id, [])
        if version_number < 1 or version_number > len(versions):
            raise KeyError(f"unknown plan version: {run_id}:v{version_number}")
        return versions[version_number - 1].model_copy(deep=True)

    def list_versions(self, run_id: str) -> list[PlanVersion]:
        """Return ordered defensive copies for one run."""
        return [version.model_copy(deep=True) for version in self._versions.get(run_id, [])]

    def serialize(self) -> str:
        """Serialize all runs and versions in stable order."""
        payload = {
            "schema_version": 1,
            "versions": [
                version.model_dump(mode="json")
                for run_id in sorted(self._versions)
                for version in self._versions[run_id]
            ],
        }
        return _canonical_json(payload)

    @classmethod
    def deserialize(cls, payload: str | bytes | Mapping[str, Any]) -> "PlanVersionStore":
        """Restore a version store from its serialized representation."""
        raw = _load_mapping(payload)
        if int(raw.get("schema_version", 1)) != 1:
            raise ValueError("unsupported PlanVersionStore schema_version")
        versions = raw.get("versions") or []
        if not isinstance(versions, list):
            raise ValueError("versions must be a list")
        return cls(versions)


def _load_mapping(payload: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    """Load a JSON object or copy an existing mapping."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    raw: Any = json.loads(payload) if isinstance(payload, str) else dict(payload)
    if not isinstance(raw, dict):
        raise ValueError("revision state payload must be a JSON object")
    return raw


def migrate_revision_state_payload(
    payload: str | bytes | Mapping[str, Any],
) -> dict[str, Any]:
    """Upgrade legacy unversioned snapshots to the schema-version 1 contract."""
    raw = _load_mapping(payload)
    schema_version = int(raw.get("schema_version", 0))
    if schema_version > 1:
        raise ValueError("unsupported future revision schema_version")
    if schema_version == 1 and "context" in raw:
        return RevisionState.model_validate(raw).model_dump(mode="json")

    legacy_context = raw.get("context") or {}
    if not isinstance(legacy_context, Mapping):
        raise ValueError("legacy context must be an object")
    run_id = str(legacy_context.get("run_id") or raw.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("legacy revision state is missing run_id")
    review_payload = (
        legacy_context.get("review_feedback")
        or legacy_context.get("review_result")
        or raw.get("review_feedback")
        or raw.get("review_result")
    )
    iteration = int(
        legacy_context.get("revision_iteration")
        or legacy_context.get("iteration")
        or raw.get("revision_iteration")
        or raw.get("iteration")
        or 1
    )
    feedback = (
        ReviewFeedback.from_review_result(review_payload)
        if isinstance(review_payload, Mapping)
        else None
    )
    issue_payloads = (
        legacy_context.get("issue_closures")
        or raw.get("issue_closures")
        or []
    )
    if not issue_payloads and feedback is not None:
        issue_payloads = [
            issue.model_dump(mode="json")
            for issue in issues_from_review_feedback(
                feedback,
                opened_in_version=max(1, iteration - 1),
            )
        ]

    legacy_versions = raw.get("versions") or raw.get("plan_versions") or []
    if not isinstance(legacy_versions, list):
        raise ValueError("legacy plan_versions must be a list")
    versions: list[dict[str, Any]] = []
    previous_id: str | None = None
    for index, item in enumerate(legacy_versions, start=1):
        if not isinstance(item, Mapping):
            raise ValueError("legacy plan version must be an object")
        version_number = int(item.get("version_number") or item.get("version") or index)
        version_id = f"{run_id}:v{version_number}"
        version_feedback = item.get("review_feedback") or item.get("review_result")
        versions.append(
            PlanVersion.create(
                run_id=run_id,
                version_number=version_number,
                parent_version_id=previous_id,
                revision_iteration=int(item.get("revision_iteration") or version_number),
                hypothesis_generation=item.get("hypothesis_generation") or {},
                experiment_design=item.get("experiment_design") or {},
                review_feedback=(
                    version_feedback
                    if isinstance(version_feedback, Mapping)
                    else None
                ),
                issue_closures=item.get("issue_closures") or (),
                prompt_fingerprints=item.get("prompt_fingerprints") or {},
            ).model_dump(mode="json")
        )
        previous_id = version_id

    migrated = {
        "schema_version": 1,
        "context": {
            "schema_version": 1,
            "run_id": run_id,
            "revision_iteration": iteration,
            "review_feedback": (
                feedback.model_dump(mode="json") if feedback is not None else None
            ),
            "issue_closures": issue_payloads,
        },
        "versions": versions,
        "validation_status": raw.get("validation_status") or "draft",
    }
    return RevisionState.model_validate(migrated).model_dump(mode="json")


def serialize_revision_state(state: RevisionState) -> str:
    """Serialize a validated revision state deterministically."""
    return _canonical_json(state.model_dump(mode="json"))


def deserialize_revision_state(
    payload: str | bytes | Mapping[str, Any],
) -> RevisionState:
    """Migrate and restore a revision state without losing contract fields."""
    return RevisionState.model_validate(migrate_revision_state_payload(payload))
