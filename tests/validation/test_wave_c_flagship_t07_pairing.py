"""Wave C checks for the actual Q028 receipt and the T07 gate boundary.

The T05 receipt is actual scientific-execution evidence, but it is not a
native T03 ``AgentTrace`` bundle.  The tests therefore keep two claims
separate: the receipt must fail closed when its adapter trace is explicitly a
fixture, while a contract-only context proves that T07 can consume frozen T03
``GateResult`` objects without schema translation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.batch.completion_gate import aggregate_completion_report
from app.contracts.validation import ValidationContext
from app.quality import DefaultQualityGateRunner
from app.validation import DefaultValidationService


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)
QUESTION = "Will it be possible to cure all cancers?"
Q028_RECEIPT = ROOT / "docs" / "modules" / "T05" / "round1" / "execution_result.json"
Q028_RECEIPT_SHA256 = "c780df9f1504f60855faac4226f55dd972ba30631bbb47306727720c5e83cde4"
PAIRING_EVIDENCE = (
    ROOT
    / "docs"
    / "modules"
    / "T03"
    / "examples"
    / "wave_c_flagship_t07_pairing_results.json"
)


def _actual_q028_execution() -> dict:
    receipt_bytes = Q028_RECEIPT.read_bytes()
    assert hashlib.sha256(receipt_bytes).hexdigest() == Q028_RECEIPT_SHA256
    return json.loads(receipt_bytes.decode("utf-8"))


def _q028_context() -> ValidationContext:
    execution = _actual_q028_execution()
    assert execution["question_id"] == "Q028"
    assert execution["actual_execution"] is True
    run_id = "run-wave-c-q028-flagship"
    version_id = f"{run_id}:v1"
    card = {
        "id": "EV-Q028-WDBC",
        "source_type": "local",
        "title": "Verified WDBC diagnostic-classification execution",
        "authors": ["T05 execution owner"],
        "year": 2026,
        "url": None,
        "doi": None,
        "quoted_text": (
            "The frozen WDBC run reports observed balanced accuracy and "
            "malignant recall for one diagnostic-classification task."
        ),
        "summary": (
            "This evidence is scoped to the frozen WDBC classification run "
            "and is not evidence that all cancers can be cured."
        ),
        "relevance_score": 0.9,
        "reliability_note": "actual T05 receipt; no all-cancer extrapolation",
    }
    return ValidationContext(
        validation_id="validation-wave-c-q028-flagship",
        run_id=run_id,
        version_id=version_id,
        research_plan={
            "run_id": run_id,
            "version_id": version_id,
            "question_id": "Q028",
            "input_question": QUESTION,
            "actual_execution": True,
            "references": [dict(card)],
            "generated_hypotheses": [
                {
                    "hypothesis": (
                        "A frozen diagnostic-classification baseline can be "
                        "measured without making a treatment claim."
                    ),
                    "supporting_evidence_ids": ["EV-Q028-WDBC"],
                    "contradicted_by_evidence_ids": [],
                }
            ],
            "datasets": {
                "source": "UCI WDBC pinned dataset",
                "target": "frozen held-out diagnostic labels",
            },
            "experiments": {
                "baselines": ["frozen logistic baseline"],
                "metrics": ["balanced_accuracy", "malignant_recall"],
            },
            "reproducibility_checklist": [
                "verify dataset SHA-256",
                "verify seed 125",
                "verify artifact checksums",
            ],
            "results": (
                "Observed WDBC classification metrics are bound to the T05 "
                "execution receipt; no treatment or all-cancer claim is made."
            ),
            "validation_status": "validated",
        },
        evidence_cards=(card,),
        agent_trace=(
            {
                "event_id": "trace-wave-c-q028-001",
                "run_id": run_id,
                "version_id": version_id,
                "question_id": "Q028",
                "step_index": 1,
                "agent_name": "t03_q028_receipt_adapter_fixture",
                "model_name": "qwen3.7-max",
                "status": "completed",
                "prompt_hash": "a" * 64,
                "mock": True,
                "errors": [],
            },
        ),
        execution_metadata={
            "run_id": run_id,
            "version_id": version_id,
            "question_id": "Q028",
            "actual_execution": True,
            "mode": "actual",
            "adapter_mode": "constructed_contract_fixture",
            "receipt_path": "docs/modules/T05/round1/execution_result.json",
            "receipt_sha256": Q028_RECEIPT_SHA256,
            "execution_result": execution,
        },
        question_item={
            "id": "Q028",
            "question": QUESTION,
            "run_id": run_id,
            "version_id": version_id,
        },
    )


def _t03_runner(context: ValidationContext):
    """Direct boundary probe; deliberately bypass the legacy T07 adapter."""

    return tuple(DefaultQualityGateRunner().run(context))


def _q028_contract_boundary_context() -> ValidationContext:
    payload = _q028_context().model_dump(mode="json")
    payload["validation_id"] = "validation-wave-c-q028-contract-boundary"
    payload["research_plan"]["actual_execution"] = False
    payload["research_plan"]["validation_status"] = "ready_for_validation"
    payload["research_plan"]["results"] = (
        "待执行验证实验；contract-boundary fixture 不声明科学结果。"
    )
    payload["execution_metadata"]["actual_execution"] = False
    payload["execution_metadata"]["mode"] = "contract_fixture"
    payload["execution_metadata"].pop("execution_result")
    payload["execution_metadata"].pop("receipt_path")
    payload["execution_metadata"].pop("receipt_sha256")
    return ValidationContext.model_validate(payload)


def test_actual_q028_receipt_without_native_t03_trace_fails_closed() -> None:
    context = _q028_context()
    report = DefaultValidationService(
        DefaultQualityGateRunner(), clock=lambda: NOW
    ).validate(context)

    assert len(report.gate_results) == 9
    assert report.validation_status == "blocked"
    assert report.recommended_plan_status == "draft"
    assert "ACTUAL_EXECUTION_HAS_UNTRUSTED_TRACE" in {
        finding.code
        for gate in report.gate_results
        for finding in gate.findings
    }


def test_t07_aggregate_consumes_t03_results_without_schema_translation() -> None:
    context = _q028_contract_boundary_context()
    report = aggregate_completion_report(
        context,
        _t03_runner(context),
        (),
        created_at=NOW,
    )

    assert report.validation_status == "passed"
    assert report.recommended_plan_status == "validated"
    assert len(report.gate_results) == 10  # T07 local gate + nine T03 gates.


def test_t03_blocker_remains_blocking_in_t07_aggregate() -> None:
    payload = _q028_contract_boundary_context().model_dump(mode="json")
    payload["evidence_cards"] = []
    context = ValidationContext.model_validate(payload)
    t03_results = _t03_runner(context)

    assert any(result.is_blocking for result in t03_results)
    report = aggregate_completion_report(
        context,
        t03_results,
        (),
        created_at=NOW,
    )

    assert report.validation_status == "blocked"
    assert report.recommended_plan_status == "draft"
    assert not report.passed


def test_pairing_evidence_keeps_actual_fixture_and_live_claims_separate() -> None:
    evidence = json.loads(PAIRING_EVIDENCE.read_text(encoding="utf-8"))

    assert evidence["q028_receipt"]["sha256"] == Q028_RECEIPT_SHA256
    assert evidence["q028_receipt"]["actual_execution"] is True
    assert evidence["q028_t03_audit"]["validation_status"] == "blocked"
    assert evidence["q028_t03_audit"]["native_t03_agent_trace_present"] is False
    assert evidence["t07_boundary_probe"]["contract_fixture_passed"] is True
    assert evidence["t07_boundary_probe"]["missing_evidence_blocked"] is True
    assert evidence["t07_boundary_probe"]["default_adapter_exercised"] is False
    assert evidence["live_batch_executed"] is False
