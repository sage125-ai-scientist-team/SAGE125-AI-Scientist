"""Wave B tests for complete artifacts and deterministic quality gates."""

from __future__ import annotations

from datetime import datetime, timezone

from app.contracts.validation import (
    HumanFeedbackDirective,
    Severity,
    ValidationContext,
)
from app.quality import (
    DefaultQualityGateRunner,
    build_default_quality_gates,
)
from app.validation import DefaultValidationService


NOW = datetime(2026, 8, 3, 13, 0, tzinfo=timezone.utc)


def _evidence_card() -> dict:
    return {
        "id": "EV-003",
        "source_type": "local",
        "title": "A verified mechanism study",
        "authors": ["Researcher"],
        "year": 2024,
        "url": None,
        "doi": None,
        "quoted_text": "The intervention changed the measured mechanism.",
        "summary": "Evidence for the proposed test.",
        "relevance_score": 0.9,
        "reliability_note": "locally verified source",
    }


def _context(
    *,
    version: int = 1,
    actual_execution: bool = False,
    human_feedback: HumanFeedbackDirective | None = None,
    revision_metadata: dict | None = None,
) -> ValidationContext:
    run_id = "run-wave-b"
    version_id = f"{run_id}:v{version}"
    question = "How can feedback improve the next research plan?"
    card = _evidence_card()
    plan = {
        "run_id": run_id,
        "version_id": version_id,
        "question_id": "Q003",
        "input_question": question,
        "actual_execution": actual_execution,
        "references": [dict(card)],
        "generated_hypotheses": [
            {
                "hypothesis": "A stricter threshold improves falsifiability.",
                "supporting_evidence_ids": ["EV-003"],
                "contradicted_by_evidence_ids": [],
            }
        ],
        "datasets": {"source": "verified input", "target": "held-out set"},
        "experiments": {
            "baselines": ["baseline-a", "baseline-b"],
            "metrics": ["error", "coverage", "stability"],
        },
        "reproducibility_checklist": ["pin inputs", "record seed"],
        "results": "待执行验证实验；目前不报告量化结果。",
        "validation_status": "ready_for_validation",
    }
    metadata = {
        "run_id": run_id,
        "version_id": version_id,
        "question_id": "Q003",
        "actual_execution": actual_execution,
        "mode": "actual" if actual_execution else "mock",
    }
    if revision_metadata is not None:
        metadata["revision_metadata"] = revision_metadata
    return ValidationContext(
        validation_id=f"validation-wave-b-v{version}",
        run_id=run_id,
        version_id=version_id,
        research_plan=plan,
        evidence_cards=(card,),
        agent_trace=(
            {
                "event_id": "trace-001",
                "run_id": run_id,
                "version_id": version_id,
                "question_id": "Q003",
                "step_index": 1,
                "agent_name": "report_writer",
                "model_name": "qwen3.6-plus",
                "status": "completed",
                "prompt_hash": "a" * 64,
                "mock": not actual_execution,
                "errors": [],
            },
        ),
        execution_metadata=metadata,
        question_item={
            "id": "Q003",
            "question": question,
            "run_id": run_id,
            "version_id": version_id,
        },
        human_feedback=human_feedback,
    )


def test_default_gate_order_is_frozen_and_unique() -> None:
    runner = DefaultQualityGateRunner(build_default_quality_gates())

    assert [gate.gate_id for gate in runner.gates] == [
        "artifact-presence",
        "evidence_grounding",
        "results_integrity",
        "research_plan_schema",
        "model_compliance",
        "reference_integrity",
        "execution-truth",
        "agent-trace",
        "human-feedback-propagation",
    ]


def test_complete_unexecuted_artifacts_pass_all_default_gates() -> None:
    context = _context()
    results = DefaultQualityGateRunner().run(context)

    assert len(results) == 9
    assert all(result.passed for result in results)
    report = DefaultValidationService(
        DefaultQualityGateRunner(), clock=lambda: NOW
    ).validate(context)
    assert report.validation_status == "passed"
    assert report.recommended_plan_status == "ready_for_validation"


def test_empty_evidence_and_trace_are_structured_blockers() -> None:
    payload = _context().model_dump(mode="json")
    payload["evidence_cards"] = []
    payload["agent_trace"] = []
    context = ValidationContext.model_validate(payload)

    results = DefaultQualityGateRunner().run(context)
    findings = [finding for result in results for finding in result.findings]

    assert any(finding.code == "MISSING_EVIDENCE_CARDS" for finding in findings)
    assert any(finding.code == "MISSING_AGENT_TRACE" for finding in findings)
    assert DefaultValidationService(
        DefaultQualityGateRunner(), clock=lambda: NOW
    ).validate(context).validation_status == "blocked"


def test_fabricated_reference_is_p0_blocked() -> None:
    payload = _context().model_dump(mode="json")
    payload["research_plan"]["references"][0]["id"] = "EV-FABRICATED"
    context = ValidationContext.model_validate(payload)

    report = DefaultValidationService(
        DefaultQualityGateRunner(), clock=lambda: NOW
    ).validate(context)

    assert report.validation_status == "blocked"
    assert any(
        finding.code in {"EVIDENCE_GROUNDING_ERROR", "REFERENCE_INTEGRITY_ERROR"}
        and finding.severity is Severity.P0
        for gate in report.gate_results
        for finding in gate.findings
    )


def test_actual_execution_without_runner_proof_fails_closed() -> None:
    context = _context(actual_execution=True)
    report = DefaultValidationService(
        DefaultQualityGateRunner(), clock=lambda: NOW
    ).validate(context)

    assert report.validation_status == "blocked"
    assert any(
        finding.code == "EXECUTION_PROOF_INCOMPLETE"
        for gate in report.gate_results
        for finding in gate.findings
    )


def test_feedback_next_version_requires_auditable_revision_receipt() -> None:
    directive = HumanFeedbackDirective(
        feedback_id="feedback-003",
        target_version_id="run-wave-b:v1",
        disposition="accepted",
        instructions=("Tighten the falsification threshold.",),
        original_feedback_sha256="f" * 64,
    )
    without_receipt = _context(version=2, human_feedback=directive)

    blocked = DefaultValidationService(
        DefaultQualityGateRunner(), clock=lambda: NOW
    ).validate(without_receipt)

    assert blocked.validation_status == "blocked"
    assert any(
        finding.code == "REVISION_METADATA_MISSING"
        for gate in blocked.gate_results
        for finding in gate.findings
    )


def test_feedback_receipt_must_match_and_can_pass_when_complete() -> None:
    directive = HumanFeedbackDirective(
        feedback_id="feedback-003",
        target_version_id="run-wave-b:v1",
        disposition="accepted",
        instructions=("Tighten the falsification threshold.",),
        original_feedback_sha256="f" * 64,
    )
    receipt = {
        "feedback_id": "feedback-003",
        "source_version_id": "run-wave-b:v1",
        "prompt_fingerprint": "a" * 64,
        "diff_hash": "d" * 64,
        "applied_instructions": ["Tighten the falsification threshold."],
    }
    context = _context(
        version=2,
        human_feedback=directive,
        revision_metadata=receipt,
    )

    report = DefaultValidationService(
        DefaultQualityGateRunner(), clock=lambda: NOW
    ).validate(context)

    assert report.validation_status == "passed"
    assert report.recommended_plan_status == "ready_for_validation"


class _ExplodingGate:
    gate_id = "exploding-gate"
    severity = Severity.P3

    def evaluate(self, context: ValidationContext):
        del context
        raise RuntimeError("untrusted detail must stay private")


def test_one_gate_exception_becomes_sanitized_p1_and_other_gates_run() -> None:
    runner = DefaultQualityGateRunner(
        (_ExplodingGate(), *build_default_quality_gates())
    )

    results = runner.run(_context())

    assert len(results) == 10
    assert results[0].passed is False
    assert results[0].findings[0].code == "GATE_EXECUTION_ERROR"
    assert results[0].findings[0].severity is Severity.P1
    assert "untrusted detail" not in results[0].model_dump_json()
    assert all(result.passed for result in results[1:])
