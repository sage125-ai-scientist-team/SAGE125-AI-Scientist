from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError


def _contract() -> Any:
    import app.contracts.batch as batch_contract

    return batch_contract


def _job(contract: Any, question_id: str = "Q001", **changes: Any) -> Any:
    values = {
        "batch_id": "batch-contract-test",
        "question_id": question_id,
        "input_hash": "a" * 64,
        "workspace": f"batch-contract-test/{question_id}/workspace",
        "context_id": f"ctx:batch-contract-test:{question_id}:aaaaaaaaaaaaaaaa",
        "cache_namespace": f"cache:batch-contract-test:{question_id}:aaaaaaaaaaaaaaaa",
    }
    values.update(changes)
    return contract.BatchJob(**values)


def _manifest(contract: Any, jobs: list[Any]) -> Any:
    return contract.BatchManifest(
        batch_id="batch-contract-test",
        source_kind=contract.SourceKind.SYNTHETIC,
        source_path="tests/batch/fixtures/questions_125.synthetic.json",
        source_hash="b" * 64,
        dry_run=True,
        jobs=jobs,
    )


def test_duplicate_question_ids_are_rejected() -> None:
    contract = _contract()
    first = _job(contract)
    second = _job(
        contract,
        workspace="batch-contract-test/Q001/other-workspace",
        context_id="ctx:batch-contract-test:Q001:bbbbbbbbbbbbbbbb",
        cache_namespace="cache:batch-contract-test:Q001:bbbbbbbbbbbbbbbb",
    )

    with pytest.raises(ValidationError, match="duplicate question_id"):
        _manifest(contract, [first, second])


def test_manifest_json_round_trip_preserves_contract() -> None:
    contract = _contract()
    manifest = _manifest(contract, [_job(contract)])

    restored = contract.BatchManifest.model_validate_json(
        manifest.model_dump_json()
    )

    assert restored == manifest


def test_job_binds_all_isolation_and_provenance_fields() -> None:
    contract = _contract()
    job = _job(contract)

    assert job.question_id == "Q001"
    assert job.input_hash == "a" * 64
    assert job.workspace.endswith("/Q001/workspace")
    assert job.context_id.startswith("ctx:batch-contract-test:Q001:")
    assert job.cache_namespace.startswith("cache:batch-contract-test:Q001:")
    assert job.attempt == 0
    assert job.retry_policy.max_attempts == 3
    assert job.budget.tokens_used == 0
    assert job.model_route.route_id == "dry-run"


def test_unknown_batch_schema_version_is_rejected() -> None:
    contract = _contract()

    with pytest.raises(ValidationError):
        _job(contract, schema_version="unknown.batch.v2")


def test_unknown_checkpoint_version_is_rejected() -> None:
    contract = _contract()
    checkpoint = contract.CheckpointRecord.from_job(_job(contract))
    payload = checkpoint.model_dump()
    payload["checkpoint_version"] = "unknown.checkpoint.v2"

    with pytest.raises(ValidationError):
        contract.CheckpointRecord.model_validate(payload)


def test_retry_policy_rejects_limits_outside_hard_bounds() -> None:
    contract = _contract()

    with pytest.raises(ValidationError):
        contract.RetryPolicy(max_attempts=0)
    with pytest.raises(ValidationError):
        contract.RetryPolicy(max_attempts=11)


def test_budget_rejects_usage_above_limit() -> None:
    contract = _contract()

    with pytest.raises(ValidationError, match="token budget exceeded"):
        contract.BatchBudget(token_limit=10, tokens_used=11)


def test_failure_record_requires_stable_error_code() -> None:
    contract = _contract()

    with pytest.raises(ValidationError):
        contract.FailureRecord(
            error_code=" ",
            message="failure",
            retryable=False,
            attempt=1,
        )


def test_mock_job_cannot_be_completed() -> None:
    contract = _contract()

    with pytest.raises(ValidationError, match="Mock job cannot be completed"):
        _job(
            contract,
            status=contract.JobStatus.COMPLETED,
            result_kind=contract.ResultKind.MOCK,
            mock=True,
        )


def test_missing_required_artifacts_cannot_be_completed() -> None:
    contract = _contract()
    fields = {
        name: f"Synthetic value for {name}"
        for name in contract.STANDARD_OUTPUT_FIELDS
    }

    with pytest.raises(ValidationError, match="missing required artifacts"):
        _job(
            contract,
            status=contract.JobStatus.COMPLETED,
            result_kind=contract.ResultKind.ACTUAL,
            output_contract=contract.OutputContract(fields=fields),
        )


def test_complete_actual_job_requires_and_accepts_all_outputs() -> None:
    contract = _contract()
    fields = {
        name: f"Synthetic value for {name}"
        for name in contract.STANDARD_OUTPUT_FIELDS
    }
    artifacts = {
        name: f"batch-contract-test/Q001/{name}"
        for name in contract.REQUIRED_ARTIFACTS
    }

    job = _job(
        contract,
        status=contract.JobStatus.COMPLETED,
        result_kind=contract.ResultKind.ACTUAL,
        model_route=contract.ModelRoute(
            route_id="formal-route",
            provider="test-provider",
            model="test-model",
            model_version="test-model-v1",
            prompt_version="test-prompt-v1",
        ),
        output_contract=contract.OutputContract(
            fields=fields,
            artifacts=artifacts,
        ),
    )

    assert job.status is contract.JobStatus.COMPLETED
    assert job.result_kind is contract.ResultKind.ACTUAL
    assert job.mock is False


def test_unassigned_model_route_cannot_be_completed_actual() -> None:
    contract = _contract()
    fields = {
        name: f"Synthetic value for {name}"
        for name in contract.STANDARD_OUTPUT_FIELDS
    }
    artifacts = {
        name: f"batch-contract-test/Q001/{name}"
        for name in contract.REQUIRED_ARTIFACTS
    }

    with pytest.raises(
        ValidationError,
        match="completed job requires an assigned model route",
    ):
        _job(
            contract,
            status=contract.JobStatus.COMPLETED,
            result_kind=contract.ResultKind.ACTUAL,
            output_contract=contract.OutputContract(
                fields=fields,
                artifacts=artifacts,
            ),
        )
