"""Captain-approved WB5 v2 token-only budget policy tests."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.batch.actual_call_audit import (
    ActualCallAudit,
    BudgetLedger,
    CostAccountingMode,
    validate_actual_call_audit,
)
from app.batch.errors import BatchRunnerError
from app.batch.five_run_preflight import (
    GateAvailabilityResult,
    SourceProvenanceResult,
    load_frozen_run_config,
    run_five_run_preflight,
)
from app.batch.checkpoint import resume_job
from app.contracts.batch import (
    BATCH_SCHEMA_VERSION_V2,
    CHECKPOINT_SCHEMA_VERSION_V2,
    TOKEN_ONLY_BUDGET_POLICY_VERSION,
    BatchBudgetV2,
    BatchJob,
    BatchJobV2,
    BudgetMode,
    BudgetPolicy,
    CheckpointRecord,
    CheckpointRecordV2,
    ResumePolicy,
)


NOW = datetime(2026, 8, 7, 1, 2, tzinfo=timezone.utc)
CAPTAIN_REFERENCE = "captain-option-b-approved-2026-08-07"


def _policy() -> BudgetPolicy:
    return BudgetPolicy(
        version=TOKEN_ONLY_BUDGET_POLICY_VERSION,
        mode=BudgetMode.TOKEN_ONLY,
        cost_accounting_required=False,
        price_snapshot_required=False,
        captain_waiver_reference=CAPTAIN_REFERENCE,
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
        "estimated_cost_usd": None,
        "settled_cost_usd": None,
        "retry_attempt": 1,
        "fallback": False,
        "price_snapshot_version": None,
        "cost_accounting_mode": CostAccountingMode.TOKEN_ONLY,
    }
    payload.update(updates)
    return ActualCallAudit(**payload)


def _v1_job() -> BatchJob:
    return BatchJob(
        batch_id="batch-v1",
        question_id="Q001",
        source_hash="a" * 64,
        input_hash="b" * 64,
        workspace="batch-v1/Q001/workspace",
        context_id="ctx:batch-v1:Q001:test",
        cache_namespace="cache:batch-v1:Q001:test",
    )


def _v2_job() -> BatchJobV2:
    return BatchJobV2(
        batch_id="batch-v2",
        question_id="Q001",
        source_hash="a" * 64,
        input_hash="b" * 64,
        workspace="batch-v2/Q001/workspace",
        context_id="ctx:batch-v2:Q001:test",
        cache_namespace="cache:batch-v2:Q001:test",
        freeze_id="T07-WB5-20260807-v2",
        budget_policy=_policy(),
        budget=BatchBudgetV2(
            mode=BudgetMode.TOKEN_ONLY,
            token_limit=200000,
            tokens_used=0,
            max_output_tokens_per_call=8192,
        ),
    )


def _v2_payload() -> dict:
    root = Path(__file__).resolve().parents[2]
    payload = json.loads(
        (
            root
            / "docs/modules/T07/run_configs/T07-WB5-20260803-v1.json"
        ).read_text(encoding="utf-8")
    )
    payload.update(
        freeze_id="T07-WB5-20260807-v2",
        frozen_at="2026-08-07T00:00:00+08:00",
        batch_schema=BATCH_SCHEMA_VERSION_V2,
        checkpoint_schema=CHECKPOINT_SCHEMA_VERSION_V2,
        budget_policy={
            "version": TOKEN_ONLY_BUDGET_POLICY_VERSION,
            "mode": "token_only",
            "cost_accounting_required": False,
            "price_snapshot_required": False,
            "captain_waiver_reference": CAPTAIN_REFERENCE,
        },
        budgets={
            "per_question": {"token_limit": 200000},
            "batch": {"token_limit": 1000000},
            "max_output_tokens_per_call": 8192,
            "exhausted_error_code": "BUDGET_EXHAUSTED",
        },
        price_snapshot=None,
    )
    return payload


def test_token_only_contract_uses_none_not_zero_or_sentinel() -> None:
    budget = BatchBudgetV2(
        mode=BudgetMode.TOKEN_ONLY,
        token_limit=200000,
        tokens_used=10,
        max_output_tokens_per_call=8192,
    )

    assert budget.cost_limit_usd is None
    assert budget.cost_used_usd is None

    with pytest.raises(ValidationError):
        BatchBudgetV2(
            mode=BudgetMode.TOKEN_ONLY,
            token_limit=200000,
            max_output_tokens_per_call=8192,
            cost_limit_usd=Decimal("0"),
        )
    with pytest.raises(ValidationError):
        BatchBudgetV2(
            mode=BudgetMode.TOKEN_ONLY,
            token_limit=200000,
            max_output_tokens_per_call=8192,
            cost_used_usd="not_evaluated",
        )


def test_token_only_audit_accepts_null_cost_but_never_fallback_or_zero() -> None:
    validate_actual_call_audit(_audit(), budget_mode=BudgetMode.TOKEN_ONLY)

    with pytest.raises(BatchRunnerError) as fallback:
        validate_actual_call_audit(
            _audit(fallback=True), budget_mode=BudgetMode.TOKEN_ONLY
        )
    assert fallback.value.error_code == "FALLBACK_NOT_ALLOWED"

    with pytest.raises(BatchRunnerError) as forged_zero:
        validate_actual_call_audit(
            _audit(estimated_cost_usd=Decimal("0")),
            budget_mode=BudgetMode.TOKEN_ONLY,
        )
    assert forged_zero.value.error_code == "COST_ACCOUNTING_POLICY_MISMATCH"

    with pytest.raises(ValueError):
        _audit(estimated_cost_usd="not_evaluated")


def test_token_only_audit_still_requires_complete_token_usage() -> None:
    payload = _audit().to_dict()
    del payload["total_tokens"]

    with pytest.raises(BatchRunnerError) as captured:
        ActualCallAudit.from_mapping(payload)

    assert captured.value.error_code == "LLM_CALL_AUDIT_INVALID"


def test_token_only_ledger_enforces_token_limits_and_accumulates_retries() -> None:
    ledger = BudgetLedger(
        per_question_token_limit=240,
        per_question_cost_limit_usd=None,
        batch_token_limit=300,
        batch_cost_limit_usd=None,
        max_output_tokens_per_call=100,
        budget_mode=BudgetMode.TOKEN_ONLY,
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
    assert ledger.question_retry_tokens("Q001") == 120
    assert ledger.batch_tokens == 240
    assert ledger.batch_retry_tokens == 120
    assert ledger.question_cost_usd("Q001") is None
    assert ledger.batch_cost_usd is None

    with pytest.raises(BatchRunnerError) as question_limit:
        ledger.require_capacity(
            "Q001",
            planned_input_tokens=1,
            planned_output_tokens=1,
            estimated_cost_usd=None,
        )
    assert question_limit.value.error_code == "BUDGET_EXHAUSTED"

    with pytest.raises(BatchRunnerError) as output_limit:
        exact_limit_ledger = BudgetLedger(
            per_question_token_limit=20000,
            per_question_cost_limit_usd=None,
            batch_token_limit=20000,
            batch_cost_limit_usd=None,
            max_output_tokens_per_call=8192,
            budget_mode=BudgetMode.TOKEN_ONLY,
        )
        exact_limit_ledger.require_capacity(
            "Q002",
            planned_input_tokens=0,
            planned_output_tokens=8193,
            estimated_cost_usd=None,
        )
    assert output_limit.value.error_code == "BUDGET_EXHAUSTED"


def test_token_only_ledger_enforces_batch_limit() -> None:
    ledger = BudgetLedger(
        per_question_token_limit=1000,
        per_question_cost_limit_usd=None,
        batch_token_limit=100,
        batch_cost_limit_usd=None,
        max_output_tokens_per_call=100,
        budget_mode=BudgetMode.TOKEN_ONLY,
    )

    with pytest.raises(BatchRunnerError) as captured:
        ledger.require_capacity(
            "Q001",
            planned_input_tokens=90,
            planned_output_tokens=20,
            estimated_cost_usd=None,
        )

    assert captured.value.error_code == "BUDGET_EXHAUSTED"


def test_v1_checkpoint_cannot_resume_into_v2() -> None:
    checkpoint = CheckpointRecord.from_job(_v1_job())

    with pytest.raises(BatchRunnerError) as captured:
        resume_job(checkpoint, _v2_job(), ResumePolicy())

    assert captured.value.error_code == "CHECKPOINT_SCHEMA_MISMATCH"


def test_v2_checkpoint_binds_policy_freeze_and_identity() -> None:
    job = _v2_job()
    checkpoint = CheckpointRecordV2.from_job(job)

    assert checkpoint.checkpoint_version == CHECKPOINT_SCHEMA_VERSION_V2
    assert checkpoint.schema_version == BATCH_SCHEMA_VERSION_V2
    assert checkpoint.budget_policy_version == TOKEN_ONLY_BUDGET_POLICY_VERSION
    assert checkpoint.budget_mode is BudgetMode.TOKEN_ONLY
    assert checkpoint.freeze_id == "T07-WB5-20260807-v2"

    forged_job = job.model_copy(
        update={
            "budget_policy": _policy().model_copy(
                update={"captain_waiver_reference": "other"}
            )
        }
    )
    with pytest.raises(BatchRunnerError) as captured:
        resume_job(
            checkpoint,
            forged_job,
            ResumePolicy(),
        )
    assert captured.value.error_code == "BUDGET_POLICY_MISMATCH"


def test_v2_preflight_passes_without_price_snapshot_and_v1_stays_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.batch.five_run_preflight as preflight

    v2_path = tmp_path / "v2.json"
    v2_path.write_text(json.dumps(_v2_payload()), encoding="utf-8")
    source = SourceProvenanceResult(())
    monkeypatch.setattr(preflight, "verify_authoritative_sources", lambda *_: source)
    monkeypatch.setattr(
        preflight,
        "load_and_map_authoritative_questions",
        lambda *_: {},
    )
    monkeypatch.setattr(preflight, "verify_frozen_question_text", lambda *_: ())
    monkeypatch.setattr(preflight, "verify_frozen_code_files", lambda *_: ())
    monkeypatch.setattr(
        preflight,
        "verify_t01_gate_availability",
        lambda *_args, **_kwargs: GateAvailabilityResult(
            True, "T01_GATE_AVAILABLE", "available"
        ),
    )
    monkeypatch.setattr(
        preflight,
        "verify_t03_gate_availability",
        lambda **_kwargs: GateAvailabilityResult(
            True, "T03_GATE_AVAILABLE", "available"
        ),
    )

    def clean(command: tuple[str, ...], cwd: Path):
        return subprocess.CompletedProcess(command, 0, "", "")

    result = run_five_run_preflight(
        v2_path,
        tmp_path,
        provider_configured_override=True,
        git_runner=clean,
    )

    assert result.passed
    assert "PRICE_SNAPSHOT_REQUIRED" not in result.error_codes
    assert result.to_dict()["budget_mode"] == "token_only"
    assert result.to_dict()["price_snapshot_required"] is False
    assert result.to_dict()["cost_accounting_required"] is False
    assert result.to_dict()["provider_calls"] == 0

    v1 = _v2_payload()
    v1.pop("budget_policy")
    v1.update(
        freeze_id="T07-WB5-20260803-v1",
        batch_schema="t07.batch.v1",
        checkpoint_schema="t07.checkpoint.v1",
        budgets={
            "per_question": {
                "token_limit": 200000,
                "cost_limit_usd": "3.00",
            },
            "batch": {
                "token_limit": 1000000,
                "cost_limit_usd": "15.00",
            },
            "max_output_tokens_per_call": 8192,
            "exhausted_error_code": "BUDGET_EXHAUSTED",
        },
    )
    v1_path = tmp_path / "v1.json"
    v1_path.write_text(json.dumps(v1), encoding="utf-8")
    legacy = run_five_run_preflight(
        v1_path,
        tmp_path,
        provider_configured_override=True,
        git_runner=clean,
    )

    assert not legacy.passed
    assert "PRICE_SNAPSHOT_REQUIRED" in legacy.error_codes


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("freeze_id", "unapproved-v2"),
        ("batch_schema", "t07.batch.v1"),
        ("checkpoint_schema", "t07.checkpoint.v1"),
    ],
)
def test_token_only_config_cannot_bypass_approved_v2_identity(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    payload = _v2_payload()
    payload[field] = value
    path = tmp_path / "invalid-v2.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BatchRunnerError) as captured:
        load_frozen_run_config(path)

    assert captured.value.error_code == "FROZEN_CONFIG_INVALID"


def test_token_only_config_requires_captain_reference(tmp_path: Path) -> None:
    payload = _v2_payload()
    payload["budget_policy"]["captain_waiver_reference"] = ""
    path = tmp_path / "invalid-waiver.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BatchRunnerError) as captured:
        load_frozen_run_config(path)

    assert captured.value.error_code == "FROZEN_CONFIG_INVALID"
