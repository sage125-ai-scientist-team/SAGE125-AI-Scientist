"""Wave B validation metrics stay scoped, stable, and source-safe."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.contracts.validation import (
    GateFinding,
    GateResult,
    RevisionIssueSnapshot,
    Severity,
    ValidationContext,
    ValidationReport,
)
from app.validation import (
    ValidationMetricsCollector,
    ValidationMetricsSnapshot,
)


NOW = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)
EXAMPLES = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "modules"
    / "T03"
    / "examples"
)


def _context(question_id: str, version: int) -> ValidationContext:
    run_id = f"run-{question_id.lower()}"
    question = f"Question text for {question_id}?"
    return ValidationContext(
        validation_id=f"validation-{question_id}-{version}",
        run_id=run_id,
        version_id=f"{run_id}:v{version}",
        research_plan={
            "question_id": question_id,
            "input_question": question,
            "actual_execution": False,
        },
        evidence_cards=({"id": f"EV-{question_id}"},),
        agent_trace=({"run_id": run_id, "status": "completed"},),
        execution_metadata={"actual_execution": False},
        question_item={"id": question_id, "question": question},
        revision_issues=(
            RevisionIssueSnapshot(
                issue_id=f"resolved-{question_id}",
                status="resolved",
                severity=Severity.P1,
                opened_in_version=1,
                closed_in_version=version,
                resolution_note="Verified in the new plan version.",
            ),
            RevisionIssueSnapshot(
                issue_id=f"open-{question_id}",
                status="open",
                severity=Severity.P2,
                opened_in_version=1,
            ),
        ),
    )


def _report(context: ValidationContext) -> ValidationReport:
    finding = GateFinding(
        code="TRACE_WARNING",
        message="A non-blocking trace warning.",
        severity=Severity.P2,
    )
    gates = (
        GateResult(
            gate_id="presence",
            passed=True,
            severity=Severity.P3,
            score=1.0,
        ),
        GateResult(
            gate_id="trace",
            passed=True,
            severity=Severity.P2,
            findings=(finding,),
            warnings=(finding.message,),
            score=0.8,
        ),
    )
    return ValidationReport.from_context(
        context,
        report_id=f"report-{context.validation_id}",
        validation_status="passed",
        recommended_plan_status="ready_for_validation",
        gate_results=gates,
        created_at=NOW,
    )


def test_metrics_are_grouped_by_question_and_version() -> None:
    collector = ValidationMetricsCollector()
    contexts = [_context("Q010", 2), _context("Q009", 2)]
    for context in reversed(contexts):
        collector.record(context, _report(context))

    snapshot = collector.snapshot()

    assert [(b.question_id, b.version_id) for b in snapshot.buckets] == [
        ("Q009", "run-q009:v2"),
        ("Q010", "run-q010:v2"),
    ]
    for bucket in snapshot.buckets:
        assert bucket.gate_pass_rate == 1.0
        assert bucket.findings_by_code == {"TRACE_WARNING": 1}
        assert bucket.revision_closure_rate == 0.5


def test_recording_same_report_twice_is_idempotent() -> None:
    collector = ValidationMetricsCollector()
    context = _context("Q011", 2)
    report = _report(context)

    collector.record(context, report)
    collector.record(context, report)

    bucket = collector.snapshot().buckets[0]
    assert bucket.validations == 1
    assert bucket.evaluated_gates == 2


def test_metrics_payload_round_trips_without_raw_feedback() -> None:
    collector = ValidationMetricsCollector()
    context = _context("Q012", 2)
    collector.record(context, _report(context))

    encoded = collector.snapshot().model_dump_json()
    restored = ValidationMetricsSnapshot.model_validate_json(encoded)

    assert restored == collector.snapshot()
    assert "feedback" not in encoded.casefold()


def test_documented_wave_b_metrics_payload_matches_public_schema() -> None:
    payload = (EXAMPLES / "wave_b_e2e_metrics.json").read_text(
        encoding="utf-8"
    )

    snapshot = ValidationMetricsSnapshot.model_validate_json(payload)

    assert snapshot.buckets[0].gate_pass_rate == 1.0
    assert snapshot.buckets[0].revision_closure_rate == 1.0
