"""Wave B tests for fail-closed validation orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from app.contracts.validation import (
    GateFinding,
    GateResult,
    RevisionIssueSnapshot,
    Severity,
    ValidationContext,
)
from app.validation import DefaultValidationService


NOW = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


def _context(
    *,
    actual_execution: bool = False,
    issues: tuple[RevisionIssueSnapshot, ...] = (),
) -> ValidationContext:
    return ValidationContext(
        validation_id="validation-wave-b-001",
        run_id="run-wave-b",
        version_id="run-wave-b:v1",
        research_plan={
            "question_id": "Q003",
            "input_question": "How can feedback improve the next plan?",
            "actual_execution": actual_execution,
            "references": [{"id": "EV-003"}],
        },
        evidence_cards=({"id": "EV-003", "title": "Evidence"},),
        agent_trace=(
            {
                "run_id": "run-wave-b",
                "agent_name": "report_writer",
                "status": "completed",
            },
        ),
        execution_metadata={
            "actual_execution": actual_execution,
            "mode": "sandbox" if actual_execution else "mock",
        },
        question_item={
            "id": "Q003",
            "question": "How can feedback improve the next plan?",
        },
        revision_issues=issues,
    )


def _pass_gate(gate_id: str = "complete-artifacts") -> GateResult:
    return GateResult(
        gate_id=gate_id,
        passed=True,
        severity=Severity.P3,
        score=1.0,
    )


def _block_gate(code: str = "MISSING_AGENT_TRACE") -> GateResult:
    message = "A required validation artifact is missing."
    return GateResult(
        gate_id="complete-artifacts",
        passed=False,
        severity=Severity.P1,
        findings=(
            GateFinding(
                code=code,
                message=message,
                severity=Severity.P1,
                path="agent_trace",
            ),
        ),
        errors=(message,),
        score=0.0,
    )


class _Runner:
    def __init__(self, *results: GateResult) -> None:
        self.results = list(results)

    def run(self, context: ValidationContext) -> list[GateResult]:
        del context
        return list(self.results)


class _BrokenRunner:
    def run(self, context: ValidationContext) -> list[GateResult]:
        del context
        raise RuntimeError("secret internal detail must not leak")


def test_complete_unexecuted_context_passes_ready_for_validation() -> None:
    context = _context()
    before = context.model_dump_json()
    service = DefaultValidationService(_Runner(_pass_gate()), clock=lambda: NOW)

    report = service.validate(context)

    assert report.validation_status == "passed"
    assert report.recommended_plan_status == "ready_for_validation"
    assert report.validation_context_sha256 == context.fingerprint()
    assert context.model_dump_json() == before


def test_trusted_executed_context_can_be_recommended_validated() -> None:
    report = DefaultValidationService(
        _Runner(_pass_gate()), clock=lambda: NOW
    ).validate(_context(actual_execution=True))

    assert report.validation_status == "passed"
    assert report.recommended_plan_status == "validated"


def test_open_p0_or_p1_issue_can_never_pass() -> None:
    issue = RevisionIssueSnapshot(
        issue_id="issue-p1-001",
        status="open",
        severity=Severity.P1,
        opened_in_version=1,
    )
    report = DefaultValidationService(
        _Runner(_pass_gate()), clock=lambda: NOW
    ).validate(_context(issues=(issue,)))

    assert report.validation_status == "blocked"
    assert report.recommended_plan_status == "draft"


def test_blocking_gate_is_conservatively_aggregated() -> None:
    report = DefaultValidationService(
        _Runner(_pass_gate("first"), _block_gate()), clock=lambda: NOW
    ).validate(_context())

    assert report.validation_status == "blocked"
    assert not report.passed


def test_runner_exception_becomes_sanitized_p0_blocker() -> None:
    report = DefaultValidationService(
        _BrokenRunner(), clock=lambda: NOW
    ).validate(_context())

    assert report.validation_status == "blocked"
    finding = report.gate_results[0].findings[0]
    assert finding.code == "VALIDATION_RUNNER_ERROR"
    assert finding.severity is Severity.P0
    assert "secret internal detail" not in report.model_dump_json()


def test_no_gates_can_never_be_treated_as_success() -> None:
    report = DefaultValidationService(_Runner(), clock=lambda: NOW).validate(
        _context()
    )

    assert report.validation_status == "blocked"
    assert report.gate_results[0].findings[0].code == "NO_QUALITY_GATES"


def test_duplicate_gate_ids_fail_closed() -> None:
    report = DefaultValidationService(
        _Runner(_pass_gate("duplicate"), _pass_gate("duplicate")),
        clock=lambda: NOW,
    ).validate(_context())

    assert report.validation_status == "blocked"
    assert report.gate_results[0].findings[0].code == "VALIDATION_RUNNER_ERROR"


def test_report_identifier_and_gate_order_are_deterministic() -> None:
    service = DefaultValidationService(
        _Runner(_pass_gate("first"), _pass_gate("second")),
        clock=lambda: NOW,
    )
    first = service.validate(_context())
    second = service.validate(_context())

    assert first.report_id == second.report_id
    assert [gate.gate_id for gate in first.gate_results] == ["first", "second"]


def test_report_identifier_binds_gate_outcomes_not_only_gate_names() -> None:
    passing = DefaultValidationService(
        _Runner(_pass_gate("same-gate")), clock=lambda: NOW
    ).validate(_context())
    blocking_gate = _block_gate()
    blocking_gate = blocking_gate.model_copy(update={"gate_id": "same-gate"})
    blocked = DefaultValidationService(
        _Runner(blocking_gate), clock=lambda: NOW
    ).validate(_context())

    assert passing.report_id != blocked.report_id
