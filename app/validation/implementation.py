"""Fail-closed Wave B implementation of the complete-context validator."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from app.contracts.validation import (
    GateFinding,
    GateResult,
    Severity,
    ValidationContext,
    ValidationReport,
)
from app.quality.service import QualityGateRunner

from .metrics import ValidationMetricsCollector


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _internal_failure_gate(code: str, message: str) -> GateResult:
    """Return a stable blocker without exposing an exception or input data."""
    finding = GateFinding(
        code=code,
        message=message,
        severity=Severity.P0,
        closure_status="open",
        path="validation",
    )
    return GateResult(
        gate_id="validation-internal-safety",
        passed=False,
        severity=Severity.P0,
        findings=(finding,),
        errors=(message,),
        score=0.0,
    )


def _needs_data(results: Sequence[GateResult]) -> bool:
    data_codes = {
        "EMPTY_EVIDENCE_CARDS",
        "MISSING_EVIDENCE_CARDS",
        "UNKNOWN_EVIDENCE_REFERENCE",
        "LEGACY_EVIDENCE_ERROR",
    }
    return any(
        finding.code in data_codes
        or finding.code.startswith("MISSING_EVIDENCE")
        or finding.code.startswith("UNKNOWN_REFERENCE")
        for result in results
        for finding in result.findings
        if finding.is_blocking
    )


class DefaultValidationService:
    """Evaluate every gate and derive one conservative validation report.

    The service catches runner failures and converts them to a P0 result.  A
    validator outage can therefore never be mistaken for a successful check.
    """

    def __init__(
        self,
        runner: QualityGateRunner,
        *,
        clock: Clock = _utc_now,
        metrics: ValidationMetricsCollector | None = None,
    ) -> None:
        self._runner = runner
        self._clock = clock
        self._metrics = metrics

    def validate(self, context: ValidationContext) -> ValidationReport:
        """Validate an immutable snapshot and return a hash-bound report."""
        snapshot = ValidationContext.model_validate_json(
            context.model_dump_json()
        )
        try:
            gate_results = tuple(
                GateResult.model_validate_json(result.model_dump_json())
                for result in self._runner.run(snapshot)
            )
            if not gate_results:
                gate_results = (
                    _internal_failure_gate(
                        "NO_QUALITY_GATES",
                        "Validation cannot pass because no quality gates ran.",
                    ),
                )
            gate_ids = [result.gate_id for result in gate_results]
            if len(gate_ids) != len(set(gate_ids)):
                raise ValueError("quality gate IDs must be unique")
        except Exception:  # fail closed at the application boundary
            gate_results = (
                _internal_failure_gate(
                    "VALIDATION_RUNNER_ERROR",
                    "Validation could not safely complete.",
                ),
            )

        has_blocker = any(result.is_blocking for result in gate_results) or any(
            issue.is_blocking for issue in snapshot.revision_issues
        )
        validation_status = "blocked" if has_blocker else "passed"
        if has_blocker:
            recommended_status = (
                "needs_data" if _needs_data(gate_results) else "draft"
            )
        elif snapshot.research_plan["actual_execution"] is True:
            recommended_status = "validated"
        else:
            recommended_status = "ready_for_validation"

        created_at = self._clock()
        report_identity = {
            "context_sha256": snapshot.fingerprint(),
            "created_at": created_at.isoformat(),
            "gate_results": [
                result.model_dump(mode="json") for result in gate_results
            ],
        }
        digest = hashlib.sha256(
            json.dumps(
                report_identity,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:24]
        report = ValidationReport.from_context(
            snapshot,
            report_id=f"validation-report-{digest}",
            validation_status=validation_status,
            recommended_plan_status=recommended_status,
            gate_results=gate_results,
            created_at=created_at,
        )
        if self._metrics is not None:
            self._metrics.record(snapshot, report)
        return report


__all__ = ["DefaultValidationService"]
