"""Thread-safe, source-safe Wave B validation metrics aggregation."""

from __future__ import annotations

from collections import Counter
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.validation import ValidationContext, ValidationReport


class ValidationMetricBucket(BaseModel):
    """Metrics for exactly one question and one immutable plan version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str
    version_id: str
    validations: int = Field(ge=0)
    passed_validations: int = Field(ge=0)
    blocked_validations: int = Field(ge=0)
    evaluated_gates: int = Field(ge=0)
    passed_gates: int = Field(ge=0)
    gate_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    findings_by_code: dict[str, int]
    findings_by_severity: dict[str, int]
    tracked_revision_issues: int = Field(ge=0)
    resolved_revision_issues: int = Field(ge=0)
    revision_closure_rate: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_counts(self) -> "ValidationMetricBucket":
        if self.passed_validations + self.blocked_validations != self.validations:
            raise ValueError("validation outcome counts must equal validations")
        if self.passed_gates > self.evaluated_gates:
            raise ValueError("passed_gates cannot exceed evaluated_gates")
        if self.resolved_revision_issues > self.tracked_revision_issues:
            raise ValueError("resolved issues cannot exceed tracked issues")
        if any(value < 0 for value in self.findings_by_code.values()):
            raise ValueError("finding counts cannot be negative")
        if any(value < 0 for value in self.findings_by_severity.values()):
            raise ValueError("severity counts cannot be negative")
        return self


class ValidationMetricsSnapshot(BaseModel):
    """Deterministically ordered, JSON-round-trip-safe metrics payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    buckets: tuple[ValidationMetricBucket, ...] = ()


class _MutableBucket:
    def __init__(self, question_id: str, version_id: str) -> None:
        self.question_id = question_id
        self.version_id = version_id
        self.validations = 0
        self.passed_validations = 0
        self.blocked_validations = 0
        self.evaluated_gates = 0
        self.passed_gates = 0
        self.findings_by_code: Counter[str] = Counter()
        self.findings_by_severity: Counter[str] = Counter()
        self.tracked_revision_issues = 0
        self.resolved_revision_issues = 0

    def freeze(self) -> ValidationMetricBucket:
        gate_rate = (
            self.passed_gates / self.evaluated_gates
            if self.evaluated_gates
            else None
        )
        closure_rate = (
            self.resolved_revision_issues / self.tracked_revision_issues
            if self.tracked_revision_issues
            else None
        )
        return ValidationMetricBucket(
            question_id=self.question_id,
            version_id=self.version_id,
            validations=self.validations,
            passed_validations=self.passed_validations,
            blocked_validations=self.blocked_validations,
            evaluated_gates=self.evaluated_gates,
            passed_gates=self.passed_gates,
            gate_pass_rate=gate_rate,
            findings_by_code=dict(sorted(self.findings_by_code.items())),
            findings_by_severity=dict(
                sorted(self.findings_by_severity.items())
            ),
            tracked_revision_issues=self.tracked_revision_issues,
            resolved_revision_issues=self.resolved_revision_issues,
            revision_closure_rate=closure_rate,
        )


class ValidationMetricsCollector:
    """Aggregate reports idempotently without retaining raw feedback text."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._buckets: dict[tuple[str, str], _MutableBucket] = {}
        self._seen_reports: set[str] = set()

    def record(
        self,
        context: ValidationContext,
        report: ValidationReport,
    ) -> None:
        """Record a report once after verifying its context binding."""
        if report.validation_id != context.validation_id:
            raise ValueError("report validation_id does not match context")
        if report.version_id != context.version_id:
            raise ValueError("report version_id does not match context")
        if report.validation_context_sha256 != context.fingerprint():
            raise ValueError("report is not bound to this validation context")
        question_id = str(context.question_item["id"])
        key = (question_id, context.version_id)
        with self._lock:
            if report.report_id in self._seen_reports:
                return
            self._seen_reports.add(report.report_id)
            bucket = self._buckets.setdefault(
                key, _MutableBucket(question_id, context.version_id)
            )
            bucket.validations += 1
            if report.passed:
                bucket.passed_validations += 1
            else:
                bucket.blocked_validations += 1
            bucket.evaluated_gates += len(report.gate_results)
            bucket.passed_gates += sum(
                result.passed for result in report.gate_results
            )
            for result in report.gate_results:
                for finding in result.findings:
                    bucket.findings_by_code[finding.code] += 1
                    bucket.findings_by_severity[finding.severity.value] += 1
            bucket.tracked_revision_issues += len(report.revision_issues)
            bucket.resolved_revision_issues += sum(
                issue.status == "resolved" for issue in report.revision_issues
            )

    def snapshot(self) -> ValidationMetricsSnapshot:
        """Return buckets sorted by question and version for stable JSON."""
        with self._lock:
            buckets = tuple(
                self._buckets[key].freeze()
                for key in sorted(self._buckets)
            )
        return ValidationMetricsSnapshot(buckets=buckets)


__all__ = [
    "ValidationMetricBucket",
    "ValidationMetricsCollector",
    "ValidationMetricsSnapshot",
]
