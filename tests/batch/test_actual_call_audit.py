"""Actual-call audit, frozen pricing, and two-level budget tests."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.batch.actual_call_audit import (
    ActualCallAudit,
    BudgetLedger,
    PriceSnapshot,
    compute_estimated_cost,
    validate_actual_call_audit,
)
from app.batch.errors import BatchRunnerError
from app.batch.output_layout import (
    build_question_output_paths,
    create_question_output_directory,
)
from app.batch.output_validation import (
    ArtifactFileRecord,
    ArtifactValidationResult,
    build_artifact_manifest,
)
from app.contracts.batch import REQUIRED_ARTIFACTS, BatchJob


NOW = datetime(2026, 8, 3, 1, 2, tzinfo=timezone.utc)


def _snapshot() -> PriceSnapshot:
    return PriceSnapshot.from_mapping(
        {
            "version": "prices-20260803-v1",
            "source": "operator-supplied-provider-price-table",
            "obtained_at": NOW.isoformat(),
            "models": {
                "qwen3.7-max": {
                    "input_per_million_usd": "1.00",
                    "output_per_million_usd": "2.00",
                }
            },
        }
    )


def _audit(**updates) -> ActualCallAudit:
    payload = {
        "provider": "bailian",
        "model": "qwen3.7-max",
        "route_tier": "strong",
        "request_timestamp": NOW,
        "sanitized_request_id": "req_sha256:" + "a" * 64,
        "static_prompt_version": "sage125-agent-prompts-20260803-v1",
        "static_prompt_hash": "b" * 64,
        "dynamic_prompt_hash": "c" * 64,
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "estimated_cost_usd": Decimal("0.00014"),
        "settled_cost_usd": None,
        "retry_attempt": 1,
        "fallback": False,
        "price_snapshot_version": "prices-20260803-v1",
    }
    payload.update(updates)
    return ActualCallAudit(**payload)


def test_actual_audit_round_trip_contains_no_raw_request_or_secret() -> None:
    audit = _audit()
    restored = ActualCallAudit.from_json(audit.to_json())

    assert restored == audit
    assert "Authorization" not in audit.to_json()
    assert "must-never" not in audit.to_json()


def test_fallback_true_fails_actual_completion_audit() -> None:
    with pytest.raises(BatchRunnerError) as captured:
        validate_actual_call_audit(_audit(fallback=True))

    assert captured.value.error_code == "FALLBACK_NOT_ALLOWED"


def test_unknown_cost_cannot_continue_as_zero() -> None:
    with pytest.raises(BatchRunnerError) as captured:
        validate_actual_call_audit(
            _audit(estimated_cost_usd=None, settled_cost_usd=None)
        )

    assert captured.value.error_code == "UNKNOWN_COST"


def test_price_snapshot_uses_decimal_and_rejects_unknown_model() -> None:
    assert compute_estimated_cost(_snapshot(), "qwen3.7-max", 100, 20) == Decimal(
        "0.0001400"
    )

    with pytest.raises(BatchRunnerError) as captured:
        compute_estimated_cost(_snapshot(), "unfrozen-model", 1, 1)

    assert captured.value.error_code == "UNKNOWN_COST"


def test_retry_usage_accumulates_but_resume_is_idempotent() -> None:
    ledger = BudgetLedger(
        per_question_token_limit=200000,
        per_question_cost_limit_usd=Decimal("3.00"),
        batch_token_limit=1000000,
        batch_cost_limit_usd=Decimal("15.00"),
        max_output_tokens_per_call=8192,
    )
    first = _audit()
    retry = _audit(
        sanitized_request_id="req_sha256:" + "d" * 64,
        retry_attempt=2,
    )

    assert ledger.record_call("Q001", first) is True
    assert ledger.record_call("Q001", first) is False
    assert ledger.record_call("Q001", retry) is True
    assert ledger.question_tokens("Q001") == 240
    assert ledger.batch_tokens == 240


def test_both_question_and_batch_budget_are_checked_before_next_call() -> None:
    ledger = BudgetLedger(
        per_question_token_limit=100,
        per_question_cost_limit_usd=Decimal("0.01"),
        batch_token_limit=100,
        batch_cost_limit_usd=Decimal("0.01"),
        max_output_tokens_per_call=20,
    )

    with pytest.raises(BatchRunnerError) as captured:
        ledger.require_capacity(
            "Q001",
            planned_input_tokens=90,
            planned_output_tokens=20,
            estimated_cost_usd=Decimal("0.001"),
        )

    assert captured.value.error_code == "BUDGET_EXHAUSTED"


def test_missing_estimated_cost_fails_pre_call_budget_check() -> None:
    ledger = BudgetLedger(
        per_question_token_limit=200000,
        per_question_cost_limit_usd=Decimal("3.00"),
        batch_token_limit=1000000,
        batch_cost_limit_usd=Decimal("15.00"),
        max_output_tokens_per_call=8192,
    )

    with pytest.raises(BatchRunnerError) as captured:
        ledger.require_capacity(
            "Q001",
            planned_input_tokens=1,
            planned_output_tokens=1,
            estimated_cost_usd=None,
        )

    assert captured.value.error_code == "UNKNOWN_COST"


def test_call_audit_is_registered_in_manifest_and_can_flow_to_index(
    tmp_path: Path,
) -> None:
    paths = build_question_output_paths(tmp_path / "batch-five", "Q001")
    create_question_output_directory(paths)
    job = BatchJob(
        batch_id="batch-five",
        question_id="Q001",
        source_hash="a" * 64,
        input_hash="b" * 64,
        workspace="batch-five/Q001/workspace",
        context_id="ctx:batch-five:Q001:test",
        cache_namespace="cache:batch-five:Q001:test",
    )
    artifacts = tuple(
        ArtifactFileRecord(
            name=name,
            path=f"Q001/{name}",
            sha256=hashlib.sha256(name.encode()).hexdigest(),
            size_bytes=1,
        )
        for name in REQUIRED_ARTIFACTS
    )
    validation = ArtifactValidationResult("passed", (), artifacts)
    audit_path = paths.question_root / "llm_call_audit.json"
    audit_path.write_text(_audit().to_json(), encoding="utf-8")

    manifest = build_artifact_manifest(
        job,
        paths,
        validation,
        supplemental_artifact_paths={"llm_call_audit.json": audit_path},
    )

    assert {artifact.name for artifact in manifest.artifacts} == {
        *REQUIRED_ARTIFACTS,
        "llm_call_audit.json",
    }
