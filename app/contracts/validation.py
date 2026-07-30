"""T03 Wave A contracts for human feedback, validation, and audit lineage.

This module is a sidecar boundary.  It deliberately does not extend T02's
``RevisionContext`` or ``PlanVersion`` models, both of which forbid additional
fields.  Cross-task integration uses their canonical ``<run_id>:vN`` version
identifier and keeps T03 feedback and validation records independently
serializable.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PlainSerializer,
    field_validator,
    model_validator,
)


FeedbackDisposition = Literal["accepted", "partially_accepted", "rejected"]
FeedbackChannel = Literal["api", "ui", "cli", "migration", "internal"]
ClosureStatus = Literal["open", "resolved", "not_applicable"]
PlanValidationStatus = Literal[
    "draft",
    "needs_data",
    "ready_for_validation",
    "validated",
]
ValidationStatus = Literal["passed", "blocked"]
AuditEventType = Literal[
    "feedback_submitted",
    "feedback_decided",
    "revision_requested",
    "revision_generated",
    "gate_evaluated",
    "validation_completed",
    "issue_closed",
    "legacy_unverified",
]

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_VERSION_PATTERN = re.compile(r"^(?P<run_id>.+):v(?P<number>[1-9]\d*)$")
_AUDIT_EVENT_RANK = {
    "feedback_submitted": 0,
    "legacy_unverified": 0,
    "feedback_decided": 1,
    "revision_requested": 2,
    "revision_generated": 3,
    "issue_closed": 4,
    "gate_evaluated": 5,
    "validation_completed": 6,
}


class FrozenDict(Mapping[str, Any]):
    """Small recursively immutable mapping with safe copy semantics."""

    __slots__ = ("__data",)

    def __init__(self, value: Mapping[str, Any]) -> None:
        self.__data = dict(value)

    def __getitem__(self, key: str) -> Any:
        return self.__data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.__data)

    def __len__(self) -> int:
        return len(self.__data)

    def __repr__(self) -> str:
        return f"FrozenDict({self.__data!r})"

    def __copy__(self) -> "FrozenDict":
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> "FrozenDict":
        memo[id(self)] = self
        return self


def _freeze_json(value: Any) -> Any:
    """Recursively freeze a JSON value while preserving its wire shape."""
    if isinstance(value, Mapping):
        return FrozenDict(
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    """Return ordinary JSON containers for deterministic serialization."""
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _freeze_json_mapping(
    value: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    return _freeze_json(value)


FrozenJsonMapping = Annotated[
    Mapping[str, JsonValue],
    AfterValidator(_freeze_json_mapping),
    PlainSerializer(_thaw_json, return_type=dict),
]


class _StrictContract(BaseModel):
    """Shared deeply snapshot-safe and forward-safe Pydantic settings."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
    )


class Severity(str, Enum):
    """Quality finding severity; unresolved P0/P1 findings are blocking."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

    @property
    def is_blocking(self) -> bool:
        return self in {Severity.P0, Severity.P1}

    @property
    def rank(self) -> int:
        return {
            Severity.P0: 0,
            Severity.P1: 1,
            Severity.P2: 2,
            Severity.P3: 3,
        }[self]


def _require_aware_datetime(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value


def _validate_sha256(value: str, field_name: str) -> str:
    if value != value.strip().lower() or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


def _parse_version_id(version_id: str) -> tuple[str, int]:
    if version_id != version_id.strip():
        raise ValueError(
            "target/version id must use canonical "
            "'<run_id>:v<positive integer>' format"
        )
    match = _VERSION_PATTERN.fullmatch(version_id)
    if match is None:
        raise ValueError(
            "target/version id must use canonical '<run_id>:v<positive integer>' format"
        )
    return match.group("run_id"), int(match.group("number"))


def _version_run_id(version_id: str) -> str:
    return _parse_version_id(version_id)[0]


def _require_canonical_version(run_id: str, version_id: str) -> str:
    version_run_id = _version_run_id(version_id)
    if version_run_id != run_id:
        raise ValueError(
            "canonical version id must use the same run_id as its record"
        )
    return version_id


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_optional_artifact_identity(
    artifact: Mapping[str, JsonValue],
    *,
    label: str,
    run_id: str,
    version_id: str,
    question_id: str,
    allow_ancestor_version: bool = False,
) -> None:
    expected = {"run_id": run_id, "question_id": question_id}
    for field_name, expected_value in expected.items():
        if field_name not in artifact:
            continue
        actual = artifact[field_name]
        if not isinstance(actual, str) or actual != expected_value:
            raise ValueError(
                f"{label}.{field_name} does not match validation context"
            )

    if "version_id" not in artifact:
        return
    artifact_version = artifact["version_id"]
    if not isinstance(artifact_version, str):
        raise ValueError(f"{label}.version_id must be a string")
    artifact_run_id, artifact_number = _parse_version_id(artifact_version)
    context_run_id, context_number = _parse_version_id(version_id)
    if artifact_run_id != run_id or context_run_id != run_id:
        raise ValueError(f"{label}.version_id belongs to a different run")
    if allow_ancestor_version:
        if artifact_number > context_number:
            raise ValueError(
                f"{label}.version_id cannot be newer than validation context"
            )
    elif artifact_version != version_id:
        raise ValueError(
            f"{label}.version_id does not match validation context"
        )


class FeedbackSource(_StrictContract):
    """Opaque origin metadata; authorization remains a service concern."""

    channel: FeedbackChannel
    actor_id: str = Field(min_length=1)

    @field_validator("actor_id")
    @classmethod
    def _strip_actor_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("actor_id cannot be blank")
        return normalized


class FeedbackRecord(_StrictContract):
    """Immutable human-feedback submission targeting one canonical plan version."""

    schema_version: Literal[1] = 1
    feedback_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    target_version_id: str = Field(min_length=1)
    feedback: str = Field(min_length=1)
    source: FeedbackSource
    correlation_id: str = Field(min_length=1)
    submitted_at: datetime
    request_fingerprint: str
    idempotency_key_hash: str | None = None
    metadata: FrozenJsonMapping = Field(default_factory=dict)

    @field_validator(
        "feedback_id",
        "run_id",
        "question_id",
        "correlation_id",
        "feedback",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("required text cannot be blank")
        return normalized

    @field_validator("submitted_at")
    @classmethod
    def _validate_submitted_at(cls, value: datetime) -> datetime:
        return _require_aware_datetime(value, "submitted_at")

    @field_validator("request_fingerprint")
    @classmethod
    def _validate_request_fingerprint(cls, value: str) -> str:
        return _validate_sha256(value, "request_fingerprint")

    @field_validator("idempotency_key_hash")
    @classmethod
    def _validate_idempotency_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_sha256(value, "idempotency_key_hash")

    @model_validator(mode="after")
    def _validate_target_version(self) -> "FeedbackRecord":
        _require_canonical_version(self.run_id, self.target_version_id)
        return self

    def fingerprint(self) -> str:
        """Return a deterministic hash for audit-lineage binding."""
        return _json_sha256(self.model_dump(mode="json"))


class FeedbackDecision(_StrictContract):
    """Auditable policy decision for one feedback record."""

    schema_version: Literal[1] = 1
    decision_id: str = Field(min_length=1)
    feedback_id: str = Field(min_length=1)
    target_version_id: str = Field(min_length=1)
    disposition: FeedbackDisposition
    decision_reason: str = Field(min_length=1)
    accepted_items: tuple[str, ...] = Field(default_factory=tuple)
    rejected_items: tuple[str, ...] = Field(default_factory=tuple)
    decided_by: str = Field(min_length=1)
    decided_at: datetime
    policy_version: str = Field(min_length=1)
    resulting_version_id: str | None = None

    @field_validator(
        "decision_id",
        "feedback_id",
        "decision_reason",
        "decided_by",
        "policy_version",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("required decision text cannot be blank")
        return normalized

    @field_validator("accepted_items", "rejected_items")
    @classmethod
    def _normalize_items(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in values if item.strip())
        normalized_keys = tuple(item.casefold() for item in normalized)
        if len(normalized_keys) != len(set(normalized_keys)):
            raise ValueError("decision items must be unique")
        return normalized

    @field_validator("decided_at")
    @classmethod
    def _validate_decided_at(cls, value: datetime) -> datetime:
        return _require_aware_datetime(value, "decided_at")

    @model_validator(mode="after")
    def _validate_disposition(self) -> "FeedbackDecision":
        accepted_keys = {item.casefold() for item in self.accepted_items}
        rejected_keys = {item.casefold() for item in self.rejected_items}
        if accepted_keys & rejected_keys:
            raise ValueError(
                "accepted_items and rejected_items must not overlap"
            )

        if self.disposition == "accepted":
            if not self.accepted_items or self.rejected_items:
                raise ValueError(
                    "accepted decision requires accepted_items and no rejected_items"
                )
        elif self.disposition == "partially_accepted":
            if not self.accepted_items or not self.rejected_items:
                raise ValueError(
                    "partially_accepted decision requires accepted_items "
                    "and rejected_items"
                )
        elif self.accepted_items or not self.rejected_items:
            raise ValueError(
                "rejected decision requires rejected_items and no accepted_items"
            )

        target_run_id, target_number = _parse_version_id(
            self.target_version_id
        )
        if self.resulting_version_id is not None:
            _require_canonical_version(target_run_id, self.resulting_version_id)
            if self.disposition == "rejected":
                raise ValueError(
                    "rejected decision cannot have resulting_version_id"
                )
            _, resulting_number = _parse_version_id(
                self.resulting_version_id
            )
            if resulting_number != target_number + 1:
                raise ValueError(
                    "resulting_version_id must be the direct next version"
                )
            if self.revision_diff_sha256 is None:
                raise ValueError(
                    "resulting_version_id requires revision_diff_sha256"
                )
        return self

    def fingerprint(self) -> str:
        """Return a deterministic hash for audit-lineage binding."""
        return _json_sha256(self.model_dump(mode="json"))


class HumanFeedbackDirective(_StrictContract):
    """Sanitized prompt input containing accepted human instructions only."""

    schema_version: Literal[1] = 1
    feedback_id: str = Field(min_length=1)
    target_version_id: str = Field(min_length=1)
    disposition: Literal["accepted", "partially_accepted"]
    instructions: tuple[str, ...] = Field(min_length=1)
    original_feedback_sha256: str

    @field_validator("instructions")
    @classmethod
    def _normalize_instructions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in values if item.strip())
        if not normalized:
            raise ValueError("instructions cannot be empty")
        normalized_keys = tuple(item.casefold() for item in normalized)
        if len(normalized_keys) != len(set(normalized_keys)):
            raise ValueError("instructions must be unique")
        return normalized

    @field_validator("original_feedback_sha256")
    @classmethod
    def _validate_feedback_hash(cls, value: str) -> str:
        return _validate_sha256(value, "original_feedback_sha256")

    @model_validator(mode="after")
    def _validate_version(self) -> "HumanFeedbackDirective":
        _version_run_id(self.target_version_id)
        return self

    @classmethod
    def from_feedback(
        cls,
        record: FeedbackRecord,
        decision: FeedbackDecision,
    ) -> "HumanFeedbackDirective":
        """Build a safe directive without forwarding rejected text to an LLM."""
        if record.feedback_id != decision.feedback_id:
            raise ValueError("feedback decision does not reference the record")
        if record.target_version_id != decision.target_version_id:
            raise ValueError("feedback decision targets a different plan version")
        if decision.disposition == "rejected":
            raise ValueError("rejected feedback cannot produce a prompt directive")
        return cls(
            feedback_id=record.feedback_id,
            target_version_id=record.target_version_id,
            disposition=decision.disposition,
            instructions=decision.accepted_items,
            original_feedback_sha256=hashlib.sha256(
                record.feedback.encode("utf-8")
            ).hexdigest(),
        )


class RevisionIssueSnapshot(_StrictContract):
    """T03 severity sidecar for a read-only snapshot of a T02 issue."""

    issue_id: str = Field(min_length=1)
    status: Literal["open", "resolved"]
    severity: Severity
    opened_in_version: int = Field(ge=1)
    closed_in_version: int | None = Field(default=None, ge=1)
    resolution_note: str | None = None

    @model_validator(mode="after")
    def _validate_closure(self) -> "RevisionIssueSnapshot":
        if self.status == "open" and self.closed_in_version is not None:
            raise ValueError("open issue cannot have closed_in_version")
        if self.status == "resolved":
            if self.closed_in_version is None or not (
                self.resolution_note or ""
            ).strip():
                raise ValueError(
                    "resolved issue requires closed_in_version and resolution_note"
                )
            if self.closed_in_version < self.opened_in_version:
                raise ValueError("closed_in_version cannot precede opened_in_version")
        return self

    @property
    def is_blocking(self) -> bool:
        return self.status == "open" and self.severity.is_blocking


class ValidationContext(_StrictContract):
    """Complete raw artifact envelope consumed by the T03 validator."""

    schema_version: Literal[1] = 1
    validation_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    research_plan: FrozenJsonMapping
    evidence_cards: tuple[FrozenJsonMapping, ...]
    agent_trace: tuple[FrozenJsonMapping, ...]
    execution_metadata: FrozenJsonMapping
    question_item: FrozenJsonMapping
    revision_issues: tuple[RevisionIssueSnapshot, ...] = Field(
        default_factory=tuple
    )
    human_feedback: HumanFeedbackDirective | None = None
    correlation_id: str | None = None

    @model_validator(mode="after")
    def _validate_artifact_identity(self) -> "ValidationContext":
        _require_canonical_version(self.run_id, self.version_id)
        _, context_version_number = _parse_version_id(self.version_id)

        plan_question_id = str(self.research_plan.get("question_id") or "").strip()
        item_question_id = str(self.question_item.get("id") or "").strip()
        if not plan_question_id or not item_question_id:
            raise ValueError(
                "research_plan.question_id and question_item.id are required"
            )
        if plan_question_id != item_question_id:
            raise ValueError(
                "research plan and question item refer to different questions"
            )

        _validate_optional_artifact_identity(
            self.research_plan,
            label="research_plan",
            run_id=self.run_id,
            version_id=self.version_id,
            question_id=item_question_id,
        )
        _validate_optional_artifact_identity(
            self.execution_metadata,
            label="execution_metadata",
            run_id=self.run_id,
            version_id=self.version_id,
            question_id=item_question_id,
        )
        _validate_optional_artifact_identity(
            self.question_item,
            label="question_item",
            run_id=self.run_id,
            version_id=self.version_id,
            question_id=item_question_id,
        )
        for index, evidence_card in enumerate(self.evidence_cards):
            _validate_optional_artifact_identity(
                evidence_card,
                label=f"evidence_cards[{index}]",
                run_id=self.run_id,
                version_id=self.version_id,
                question_id=item_question_id,
                allow_ancestor_version=True,
            )

        plan_question = " ".join(
            str(self.research_plan.get("input_question") or "").split()
        )
        item_question = " ".join(str(self.question_item.get("question") or "").split())
        if not plan_question or not item_question:
            raise ValueError(
                "research_plan.input_question and question_item.question are required"
            )
        if plan_question != item_question:
            raise ValueError("research plan question text does not match question item")

        if "actual_execution" not in self.research_plan:
            raise ValueError("research_plan.actual_execution is required")
        if "actual_execution" not in self.execution_metadata:
            raise ValueError("execution_metadata.actual_execution is required")
        plan_actual = self.research_plan["actual_execution"]
        metadata_actual = self.execution_metadata["actual_execution"]
        if type(plan_actual) is not bool or type(metadata_actual) is not bool:
            raise ValueError("actual_execution values must be booleans")
        if plan_actual is not metadata_actual:
            raise ValueError(
                "research_plan.actual_execution does not match execution_metadata"
            )

        for index, event in enumerate(self.agent_trace):
            event_run_id = event.get("run_id")
            if not event_run_id:
                raise ValueError(f"agent_trace[{index}].run_id is required")
            if not isinstance(event_run_id, str) or event_run_id != self.run_id:
                raise ValueError(
                    f"agent_trace[{index}] belongs to a different run"
                )
            _validate_optional_artifact_identity(
                event,
                label=f"agent_trace[{index}]",
                run_id=self.run_id,
                version_id=self.version_id,
                question_id=item_question_id,
                allow_ancestor_version=True,
            )

        if self.human_feedback is not None:
            _require_canonical_version(
                self.run_id,
                self.human_feedback.target_version_id,
            )
            _, feedback_version_number = _parse_version_id(
                self.human_feedback.target_version_id
            )
            if feedback_version_number > context_version_number:
                raise ValueError(
                    "human feedback cannot target a future plan version"
                )

        issue_ids = [issue.issue_id for issue in self.revision_issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("revision issue_id values must be unique")
        for issue in self.revision_issues:
            if issue.opened_in_version > context_version_number:
                raise ValueError(
                    "revision issue cannot open in a future plan version"
                )
            if (
                issue.closed_in_version is not None
                and issue.closed_in_version > context_version_number
            ):
                raise ValueError(
                    "revision issue cannot close in a future plan version"
                )
        return self

    def fingerprint(self) -> str:
        """Return a deterministic hash of the complete immutable context."""
        return _json_sha256(self.model_dump(mode="json"))


class GateFinding(_StrictContract):
    """One stable, traceable finding emitted by a quality gate."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: Severity
    closure_status: ClosureStatus = "open"
    issue_id: str | None = None
    path: str | None = None
    source_ids: tuple[str, ...] = Field(default_factory=tuple)
    resolution_note: str | None = None

    @model_validator(mode="after")
    def _validate_closure(self) -> "GateFinding":
        if self.closure_status in {"resolved", "not_applicable"} and not (
            self.resolution_note or ""
        ).strip():
            raise ValueError(
                "closed or not-applicable finding requires resolution_note"
            )
        if (
            self.severity.is_blocking
            and self.closure_status != "open"
            and not (self.issue_id or "").strip()
        ):
            raise ValueError(
                "closed P0/P1 finding requires an auditable issue_id"
            )
        return self

    @property
    def is_blocking(self) -> bool:
        return self.closure_status == "open" and self.severity.is_blocking


class GateResult(_StrictContract):
    """Versioned quality-gate result with fail-closed P0/P1 semantics."""

    schema_version: Literal[1] = 1
    gate_id: str = Field(min_length=1)
    passed: bool
    severity: Severity
    findings: tuple[GateFinding, ...] = Field(default_factory=tuple)
    errors: tuple[str, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    score: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_gate_outcome(self) -> "GateResult":
        blocking = any(finding.is_blocking for finding in self.findings)
        if self.passed and blocking:
            raise ValueError("gate cannot pass with an open P0/P1 finding")
        if self.passed and self.errors:
            raise ValueError("passed gate cannot contain errors")
        if self.errors and not self.severity.is_blocking:
            raise ValueError("gate errors require P0 or P1 severity")
        if not self.passed and not (self.findings or self.errors):
            raise ValueError("failed gate requires findings or errors")
        if not self.passed and not (blocking or self.errors):
            raise ValueError("non-blocking findings alone cannot fail a gate")
        if self.findings:
            most_severe = min(
                (finding.severity for finding in self.findings),
                key=lambda item: item.rank,
            )
            if self.severity.rank > most_severe.rank:
                raise ValueError("gate severity cannot understate its findings")
        return self

    @property
    def is_blocking(self) -> bool:
        return bool(self.errors) or any(
            finding.is_blocking for finding in self.findings
        )

    @classmethod
    def from_legacy(
        cls,
        gate_id: str,
        payload: Mapping[str, Any],
        *,
        default_severity: Severity = Severity.P1,
    ) -> "GateResult":
        """Convert the current dictionary gate shape without losing messages."""
        passed = payload.get("passed")
        if type(passed) is not bool:
            raise ValueError("legacy gate passed must be a boolean")

        raw_errors = payload.get("errors")
        raw_warnings = payload.get("warnings")
        if not isinstance(raw_errors, list) or not all(
            isinstance(item, str) for item in raw_errors
        ):
            raise ValueError("legacy gate errors must be a list of strings")
        if not isinstance(raw_warnings, list) or not all(
            isinstance(item, str) for item in raw_warnings
        ):
            raise ValueError("legacy gate warnings must be a list of strings")
        errors = list(raw_errors)
        warnings = list(raw_warnings)

        score = payload.get("score")
        if type(score) not in {int, float}:
            raise ValueError("legacy gate score must be numeric")

        findings = [
            GateFinding(
                code=f"LEGACY_ERROR_{index}",
                message=message,
                severity=default_severity,
                closure_status="open",
            )
            for index, message in enumerate(errors, start=1)
        ]
        findings.extend(
            GateFinding(
                code=f"LEGACY_WARNING_{index}",
                message=message,
                severity=Severity.P3,
                closure_status="not_applicable",
                resolution_note="Legacy warning is advisory and non-blocking.",
            )
            for index, message in enumerate(warnings, start=1)
        )
        severity = default_severity if errors else Severity.P3
        return cls(
            gate_id=gate_id,
            passed=passed,
            severity=severity,
            findings=findings,
            errors=errors,
            warnings=warnings,
            score=float(score),
        )

    def to_legacy(self) -> dict[str, Any]:
        """Return the current workflow gate shape for gradual integration."""
        return {
            "passed": self.passed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "score": self.score,
        }


class ValidationReport(_StrictContract):
    """Aggregate decision that cannot pass unresolved blocking findings."""

    schema_version: Literal[1] = 1
    report_id: str = Field(min_length=1)
    validation_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    validation_context_sha256: str
    validation_status: ValidationStatus
    recommended_plan_status: PlanValidationStatus
    gate_results: tuple[GateResult, ...] = Field(min_length=1)
    revision_issues: tuple[RevisionIssueSnapshot, ...]
    created_at: datetime
    lineage_id: str | None = None

    @field_validator("validation_context_sha256")
    @classmethod
    def _validate_context_hash(cls, value: str) -> str:
        return _validate_sha256(value, "validation_context_sha256")

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _require_aware_datetime(value, "created_at")

    @model_validator(mode="after")
    def _validate_report_outcome(self) -> "ValidationReport":
        _require_canonical_version(self.run_id, self.version_id)
        gate_ids = [result.gate_id for result in self.gate_results]
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("validation gate_id values must be unique")
        has_gate_blocker = any(
            result.is_blocking for result in self.gate_results
        )
        has_issue_blocker = any(
            issue.is_blocking for issue in self.revision_issues
        )
        has_blocker = has_gate_blocker or has_issue_blocker
        if has_blocker and self.validation_status != "blocked":
            raise ValueError(
                "validation report cannot pass a blocking gate or issue"
            )
        if has_blocker and self.recommended_plan_status in {
            "ready_for_validation",
            "validated",
        }:
            raise ValueError("blocking gate requires draft or needs_data plan status")
        if self.validation_status == "blocked" and self.recommended_plan_status in {
            "ready_for_validation",
            "validated",
        }:
            raise ValueError(
                "blocked validation requires draft or needs_data plan status"
            )
        if self.validation_status == "passed" and not all(
            result.passed for result in self.gate_results
        ):
            raise ValueError("passed validation requires every gate to pass")
        return self

    @classmethod
    def from_context(
        cls,
        context: ValidationContext,
        *,
        report_id: str,
        validation_status: ValidationStatus,
        recommended_plan_status: PlanValidationStatus,
        gate_results: Sequence[GateResult],
        created_at: datetime,
        lineage_id: str | None = None,
    ) -> "ValidationReport":
        """Build a report bound to the exact immutable validation context."""
        return cls(
            report_id=report_id,
            validation_id=context.validation_id,
            run_id=context.run_id,
            version_id=context.version_id,
            validation_context_sha256=context.fingerprint(),
            validation_status=validation_status,
            recommended_plan_status=recommended_plan_status,
            gate_results=tuple(gate_results),
            revision_issues=context.revision_issues,
            created_at=created_at,
            lineage_id=lineage_id,
        )

    @property
    def passed(self) -> bool:
        return self.validation_status == "passed"


class AuditLineageEvent(_StrictContract):
    """One append-only event in the T03 sidecar lineage."""

    event_id: str = Field(min_length=1)
    event_type: AuditEventType
    occurred_at: datetime
    actor_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    payload_sha256: str
    parent_event_id: str | None = None
    metadata: FrozenJsonMapping = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def _validate_occurred_at(cls, value: datetime) -> datetime:
        return _require_aware_datetime(value, "occurred_at")

    @field_validator("payload_sha256")
    @classmethod
    def _validate_payload_hash(cls, value: str) -> str:
        return _validate_sha256(value, "payload_sha256")


class AuditLineage(_StrictContract):
    """Append-only sidecar linking feedback, versions, gates, and validation."""

    schema_version: Literal[1] = 1
    lineage_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    feedback_id: str = Field(min_length=1)
    feedback_sha256: str
    target_version_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    decision_id: str | None = None
    decision_disposition: FeedbackDisposition | None = None
    decision_sha256: str | None = None
    resulting_version_id: str | None = None
    revision_diff_sha256: str | None = None
    validation_report_id: str | None = None
    issue_ids: tuple[str, ...] = Field(default_factory=tuple)
    events: tuple[AuditLineageEvent, ...] = Field(min_length=1)

    @field_validator(
        "feedback_sha256",
        "decision_sha256",
        "revision_diff_sha256",
    )
    @classmethod
    def _validate_optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_sha256(value, "audit linkage hash")

    @model_validator(mode="after")
    def _validate_event_chain(self) -> "AuditLineage":
        _, target_number = _parse_version_id(self.target_version_id)
        _require_canonical_version(self.run_id, self.target_version_id)
        if self.decision_id is None:
            if (
                self.decision_disposition is not None
                or self.decision_sha256 is not None
            ):
                raise ValueError(
                    "decision metadata requires decision_id"
                )
        elif (
            self.decision_disposition is None
            or self.decision_sha256 is None
        ):
            raise ValueError(
                "decision_id requires disposition and decision_sha256"
            )
        if self.resulting_version_id is not None:
            _require_canonical_version(self.run_id, self.resulting_version_id)
            if self.decision_id is None:
                raise ValueError("resulting_version_id requires decision_id")
            _, resulting_number = _parse_version_id(self.resulting_version_id)
            if resulting_number != target_number + 1:
                raise ValueError(
                    "resulting_version_id must be the direct next version"
                )
        if self.decision_disposition == "rejected" and (
            self.resulting_version_id is not None
            or self.revision_diff_sha256 is not None
        ):
            raise ValueError(
                "rejected feedback cannot produce a revision"
            )
        if self.revision_diff_sha256 is not None:
            if self.resulting_version_id is None:
                raise ValueError(
                    "revision_diff_sha256 requires resulting_version_id"
                )

        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("audit event_id values must be unique")
        if len(self.issue_ids) != len(set(self.issue_ids)):
            raise ValueError("audit issue_ids must be unique")

        first = self.events[0]
        if first.event_type not in {
            "feedback_submitted",
            "legacy_unverified",
        }:
            raise ValueError(
                "audit lineage must start with feedback_submitted "
                "or legacy_unverified"
            )
        if first.parent_event_id is not None:
            raise ValueError("first audit event cannot have a parent")
        if first.payload_sha256 != self.feedback_sha256:
            raise ValueError(
                "first audit event payload hash must match feedback"
            )

        previous_time: datetime | None = None
        previous_event: AuditLineageEvent | None = None
        previous_rank = -1
        event_types: set[str] = set()
        for event in self.events:
            if previous_event is not None and (
                event.parent_event_id != previous_event.event_id
            ):
                raise ValueError(
                    "audit events must form one chain through the prior event"
                )
            if previous_time is not None and event.occurred_at < previous_time:
                raise ValueError("audit events must be chronological")
            rank = _AUDIT_EVENT_RANK[event.event_type]
            if rank < previous_rank:
                raise ValueError("audit event types are out of order")
            if event.event_type in {
                "feedback_submitted",
                "feedback_decided",
                "revision_requested",
                "revision_generated",
                "validation_completed",
            } and event.event_type in event_types:
                raise ValueError(
                    f"audit event type {event.event_type} cannot repeat"
                )

            if event.event_type in {
                "feedback_submitted",
                "legacy_unverified",
            } and event.subject_id != self.feedback_id:
                raise ValueError(
                    "feedback audit event subject must match feedback_id"
                )
            if event.event_type == "feedback_decided":
                if self.decision_id is None or event.subject_id != self.decision_id:
                    raise ValueError(
                        "feedback_decided subject must match decision_id"
                    )
                if event.payload_sha256 != self.decision_sha256:
                    raise ValueError(
                        "feedback_decided payload hash must match decision"
                    )
            if (
                event.event_type in {
                    "revision_requested",
                    "revision_generated",
                }
                and self.decision_disposition == "rejected"
            ):
                raise ValueError(
                    "rejected feedback cannot request or generate a revision"
                )
            if event.event_type == "revision_generated":
                if (
                    self.resulting_version_id is None
                    or event.subject_id != self.resulting_version_id
                ):
                    raise ValueError(
                        "revision_generated subject must match resulting_version_id"
                    )
                if event.payload_sha256 != self.revision_diff_sha256:
                    raise ValueError(
                        "revision_generated payload hash must match revision diff"
                    )
            if event.event_type == "validation_completed":
                if (
                    self.validation_report_id is None
                    or event.subject_id != self.validation_report_id
                ):
                    raise ValueError(
                        "validation_completed subject must match "
                        "validation_report_id"
                    )
            if (
                event.event_type == "issue_closed"
                and event.subject_id not in self.issue_ids
            ):
                raise ValueError(
                    "issue_closed subject must be listed in issue_ids"
                )

            event_types.add(event.event_type)
            previous_event = event
            previous_time = event.occurred_at
            previous_rank = rank

        required_events = {
            "feedback_decided": self.decision_id,
            "revision_generated": self.resulting_version_id,
            "validation_completed": self.validation_report_id,
        }
        for event_type, linked_id in required_events.items():
            if linked_id is not None and event_type not in event_types:
                raise ValueError(
                    f"{event_type} event is required for its linked identifier"
                )
        return self

    @classmethod
    def start(
        cls,
        record: FeedbackRecord,
        *,
        lineage_id: str,
        event: AuditLineageEvent,
    ) -> "AuditLineage":
        """Start a lineage from one validated feedback submission."""
        if event.event_type != "feedback_submitted":
            raise ValueError("lineage start requires feedback_submitted event")
        if event.subject_id != record.feedback_id:
            raise ValueError("submission event does not reference feedback")
        return cls(
            lineage_id=lineage_id,
            run_id=record.run_id,
            question_id=record.question_id,
            feedback_id=record.feedback_id,
            feedback_sha256=record.fingerprint(),
            target_version_id=record.target_version_id,
            correlation_id=record.correlation_id,
            events=(event,),
        )

    def bind_decision(
        self,
        decision: FeedbackDecision,
        event: AuditLineageEvent,
    ) -> "AuditLineage":
        """Atomically bind a saved decision and its audit event."""
        if self.decision_id is not None:
            raise ValueError("audit lineage already has a decision")
        if decision.feedback_id != self.feedback_id:
            raise ValueError("decision does not reference lineage feedback")
        if decision.target_version_id != self.target_version_id:
            raise ValueError("decision targets a different plan version")
        if event.event_type != "feedback_decided":
            raise ValueError("decision binding requires feedback_decided event")
        if event.subject_id != decision.decision_id:
            raise ValueError("decision event subject does not match decision")
        if event.payload_sha256 != decision.fingerprint():
            raise ValueError("decision event payload hash does not match decision")

        payload = self.model_dump(mode="json")
        payload["decision_id"] = decision.decision_id
        payload["decision_disposition"] = decision.disposition
        payload["decision_sha256"] = decision.fingerprint()
        payload["events"] = [
            *payload["events"],
            event.model_dump(mode="json"),
        ]
        return AuditLineage.model_validate(payload)

    def append(self, event: AuditLineageEvent) -> "AuditLineage":
        """Return a validated copy with one new event; never mutate history."""
        payload = self.model_dump(mode="json")
        linked_field = {
            "feedback_decided": "decision_id",
            "revision_generated": "resulting_version_id",
            "validation_completed": "validation_report_id",
        }.get(event.event_type)
        if linked_field is not None:
            existing = payload.get(linked_field)
            if existing is not None and existing != event.subject_id:
                raise ValueError(
                    f"{event.event_type} conflicts with {linked_field}"
                )
            payload[linked_field] = event.subject_id
        if event.event_type == "revision_generated":
            payload["revision_diff_sha256"] = event.payload_sha256
        if event.event_type == "issue_closed":
            payload["issue_ids"] = [
                *payload["issue_ids"],
                *(
                    []
                    if event.subject_id in payload["issue_ids"]
                    else [event.subject_id]
                ),
            ]
        payload["events"] = [
            *payload["events"],
            event.model_dump(mode="json"),
        ]
        return AuditLineage.model_validate(payload)


__all__ = [
    "AuditLineage",
    "AuditLineageEvent",
    "FeedbackDecision",
    "FeedbackRecord",
    "FeedbackSource",
    "GateFinding",
    "GateResult",
    "HumanFeedbackDirective",
    "RevisionIssueSnapshot",
    "Severity",
    "ValidationContext",
    "ValidationReport",
]
