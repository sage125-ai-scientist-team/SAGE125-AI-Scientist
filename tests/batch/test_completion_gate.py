"""T01/T03 adapter and the only formal-completion decision for T07-WB5."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.batch.actual_call_audit import ActualCallAudit
from app.batch.completion_gate import (
    CompletionGateInput,
    CompletionGateIssue,
    build_actual_validation_context,
    evaluate_question_completion,
    save_completion_gate_result,
)
from app.batch.delivery_index import (
    QuestionDeliveryRecord,
    build_delivery_index,
)
from app.batch.output_validation import ArtifactFileRecord, ArtifactManifest
from app.contracts.batch import REQUIRED_ARTIFACTS
from app.contracts.validation import GateFinding, GateResult, Severity


NOW = datetime(2026, 8, 3, 1, 2, tzinfo=timezone.utc)
AUDIT_NAME = "llm_call_audit.json"


def _passed_gate(gate_id: str) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        passed=True,
        severity=Severity.P3,
        score=1.0,
    )


def _failed_gate(gate_id: str) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        passed=False,
        severity=Severity.P1,
        findings=(
            GateFinding(
                code="BLOCKED",
                message="failed for test",
                severity=Severity.P1,
            ),
        ),
        errors=("failed for test",),
        score=0.0,
    )


def _artifacts(*, include_audit: bool = True, omit: str | None = None):
    names = list(REQUIRED_ARTIFACTS)
    if include_audit:
        names.append(AUDIT_NAME)
    return tuple(
        ArtifactFileRecord(
            name=name,
            path=f"Q001/{name}",
            sha256=(
                hashlib.sha256(_audit().to_json().encode("utf-8")).hexdigest()
                if name == AUDIT_NAME
                else hashlib.sha256(name.encode()).hexdigest()
            ),
            size_bytes=10,
        )
        for name in names
        if name != omit
    )


def _manifest(*, include_audit: bool = True, omit: str | None = None):
    artifacts = _artifacts(include_audit=include_audit, omit=omit)
    payload = {
        "batch_id": "batch-five",
        "question_id": "Q001",
        "output_contract_version": "t07.batch.v1",
        "validation_status": "passed",
        "artifacts": [
            artifact.to_dict()
            for artifact in sorted(artifacts, key=lambda item: item.name)
        ],
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return ArtifactManifest(
        batch_id="batch-five",
        question_id="Q001",
        output_contract_version="t07.batch.v1",
        validation_status="passed",
        artifacts=artifacts,
        manifest_sha256=digest,
    )


def _delivery(manifest: ArtifactManifest):
    record = QuestionDeliveryRecord(
        batch_id="batch-five",
        question_id="Q001",
        status="gates_pending",
        source_hash="a" * 64,
        input_hash="b" * 64,
        output_contract_version="t07.batch.v1",
        route_id="t07-wb5-bailian-qwen-stack-v1",
        provider="bailian",
        model="qwen3.7-max",
        model_version="qwen-stack-20260803-v1",
        prompt_version="sage125-agent-prompts-20260803-v1",
        prompt_hash="c" * 64,
        schema_version="t07.batch.v1",
        artifacts=manifest.artifacts,
        input_tokens=100,
        output_tokens=20,
        tokens_used=120,
        duration_seconds=1.0,
        attempts=1,
        failure_code=None,
        validation_status="passed",
        validation_error_codes=(),
        result_kind="actual",
        actual=True,
        mock=False,
        synthetic=False,
        completed=False,
    )
    return build_delivery_index("batch-five", (record,))


def _audit(**updates) -> ActualCallAudit:
    payload = {
        "provider": "bailian",
        "model": "qwen3.7-max",
        "route_tier": "strong",
        "request_timestamp": NOW,
        "sanitized_request_id": "req_sha256:" + "d" * 64,
        "static_prompt_version": "sage125-agent-prompts-20260803-v1",
        "static_prompt_hash": "c" * 64,
        "dynamic_prompt_hash": "f" * 64,
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "estimated_cost_usd": Decimal("0.001"),
        "settled_cost_usd": None,
        "retry_attempt": 1,
        "fallback": False,
        "price_snapshot_version": "prices-v1",
    }
    payload.update(updates)
    return ActualCallAudit(**payload)


def _input(**updates) -> CompletionGateInput:
    manifest = updates.pop("artifact_manifest", _manifest())
    delivery = updates.pop("delivery_index", _delivery(manifest))
    payload = {
        "batch_id": "batch-five",
        "question_id": "Q001",
        "question": "How can this mechanism be tested?",
        "domain": "biology",
        "run_id": "run-five-q001",
        "version_id": "run-five-q001:v1",
        "source_hash": "a" * 64,
        "input_hash": "b" * 64,
        "research_plan": {
            "question_id": "Q001",
            "input_question": "How can this mechanism be tested?",
            "actual_execution": True,
            "references": [{"id": "EV-001"}],
        },
        "evidence_cards": ({"id": "EV-001", "title": "Evidence"},),
        "agent_trace": (
            {
                "run_id": "run-five-q001",
                "agent_name": "report_writer",
                "status": "success",
            },
        ),
        "execution_metadata": {
            "actual_execution": True,
            "mode": "actual",
        },
        "question_item": {
            "id": "Q001",
            "question": "How can this mechanism be tested?",
            "domain": "biology",
            "batch_id": "batch-five",
            "run_id": "run-five-q001",
            "version_id": "run-five-q001:v1",
            "source_hash": "a" * 64,
            "input_hash": "b" * 64,
        },
        "evidence_bundle": object(),
        "claims": (),
        "artifact_manifest": manifest,
        "delivery_index": delivery,
        "call_audit": _audit(),
        "source_kind": "production",
        "source_provenance_verified": True,
        "frozen_question_verified": True,
        "budgets_verified": True,
        "created_at": NOW,
    }
    payload.update(updates)
    return CompletionGateInput(**payload)


def _evaluate(value: CompletionGateInput, *, t01=None, t03=None):
    return evaluate_question_completion(
        value,
        t01_runner=t01 or (lambda *_: _passed_gate("t01-evidence-precheck")),
        t03_runner=t03 or (lambda *_: (_passed_gate("t03-quality"),)),
    )


def test_all_twenty_conditions_are_required_for_completed() -> None:
    result = _evaluate(_input())

    assert result.completed
    assert result.status == "completed"
    assert len(result.conditions) == 20
    assert all(result.conditions.values())
    assert result.validation_report.passed


def test_actual_context_is_rebuilt_with_t03_model_validate() -> None:
    context = build_actual_validation_context(_input())

    assert context.research_plan["actual_execution"] is True
    assert context.execution_metadata["actual_execution"] is True
    assert context.question_item["id"] == "Q001"


def test_mock_context_cannot_masquerade_as_actual() -> None:
    value = _input(
        research_plan={
            "question_id": "Q001",
            "input_question": "How can this mechanism be tested?",
            "actual_execution": False,
        },
        execution_metadata={"actual_execution": False, "mode": "mock"},
    )

    with pytest.raises(ValueError, match="actual_execution"):
        build_actual_validation_context(value)


def test_mismatched_actual_execution_is_rejected_by_real_contract() -> None:
    value = _input(execution_metadata={"actual_execution": False})

    with pytest.raises((ValueError, ValidationError), match="actual_execution"):
        build_actual_validation_context(value)


def test_t01_precheck_failure_blocks_completed() -> None:
    result = _evaluate(_input(), t01=lambda *_: _failed_gate("t01"))

    assert not result.completed
    assert result.status == "gates_pending"
    assert "T01_GATE_FAILED" in result.error_codes


def test_any_t03_gate_failure_blocks_completed() -> None:
    result = _evaluate(
        _input(),
        t03=lambda *_: (_passed_gate("t03-a"), _failed_gate("t03-b")),
    )

    assert not result.completed
    assert "T03_GATE_FAILED" in result.error_codes


def test_unclosed_p0_or_p1_blocks_completed() -> None:
    value = _input(
        open_issues=(
            CompletionGateIssue("OPEN_P1", "must be closed", Severity.P1),
        )
    )

    result = _evaluate(value)

    assert not result.completed
    assert "OPEN_P0_P1" in result.error_codes


def test_missing_llm_call_audit_blocks_completed() -> None:
    result = _evaluate(_input(call_audit=None))

    assert not result.completed
    assert "LLM_CALL_AUDIT_MISSING" in result.error_codes


@pytest.mark.parametrize("missing", REQUIRED_ARTIFACTS)
def test_any_one_of_five_minimum_artifacts_missing_blocks(missing: str) -> None:
    manifest = _manifest(omit=missing)
    value = _input(artifact_manifest=manifest, delivery_index=_delivery(manifest))

    result = _evaluate(value)

    assert not result.completed
    assert "REQUIRED_ARTIFACT_MISSING" in result.error_codes


def test_fallback_audit_blocks_completed() -> None:
    result = _evaluate(_input(call_audit=_audit(fallback=True)))

    assert not result.completed
    assert "FALLBACK_NOT_ALLOWED" in result.error_codes


def test_unknown_cost_blocks_completed() -> None:
    result = _evaluate(
        _input(
            call_audit=_audit(
                estimated_cost_usd=None,
                settled_cost_usd=None,
            )
        )
    )

    assert not result.completed
    assert "UNKNOWN_COST" in result.error_codes


def test_delivery_index_hash_mismatch_blocks_completed() -> None:
    value = _input()
    forged = replace(value.delivery_index, index_sha256="0" * 64)

    result = _evaluate(replace(value, delivery_index=forged))

    assert not result.completed
    assert "DELIVERY_CHECKSUM_MISMATCH" in result.error_codes


def test_validation_report_gate_results_and_decision_are_saved(
    tmp_path: Path,
) -> None:
    result = _evaluate(_input())

    report_path, gates_path, decision_path = save_completion_gate_result(
        result,
        tmp_path / "Q001",
    )

    assert (
        json.loads(report_path.read_text(encoding="utf-8"))[
            "validation_status"
        ]
        == "passed"
    )
    assert len(json.loads(gates_path.read_text(encoding="utf-8"))) == 3
    assert json.loads(decision_path.read_text(encoding="utf-8"))["completed"] is True
