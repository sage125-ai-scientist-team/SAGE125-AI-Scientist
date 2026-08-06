"""Wave B derived per-question delivery-index tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from app.batch.errors import BatchRunnerError
from app.contracts.batch import (
    REQUIRED_ARTIFACTS,
    STANDARD_OUTPUT_FIELDS,
    BatchBudget,
    BatchJob,
    JobStatus,
    ModelRoute,
    OutputContract,
    ResultKind,
    SourceKind,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "five_question_outputs.synthetic.json"
)


def _apis():
    import app.batch.delivery_index as delivery_index
    import app.batch.output_validation as output_validation

    return delivery_index, output_validation


def _artifact_records(question_id: str):
    _, validation = _apis()
    return tuple(
        validation.ArtifactFileRecord(
            name=name,
            path=f"{question_id}/{name}",
            sha256=hashlib.sha256(
                f"{question_id}:{name}".encode("utf-8")
            ).hexdigest(),
            size_bytes=100 + index,
        )
        for index, name in enumerate(REQUIRED_ARTIFACTS)
    )


def _record(
    question_id: str,
    *,
    status: str = "completed",
    validation_status: str = "passed",
    failure_code: str | None = None,
    artifacts=None,
    actual: bool = True,
    mock: bool = False,
    synthetic: bool = False,
):
    delivery, _ = _apis()
    normalized_artifacts = (
        _artifact_records(question_id) if artifacts is None else artifacts
    )
    return delivery.QuestionDeliveryRecord(
        batch_id="batch-five",
        question_id=question_id,
        status=status,
        source_hash="a" * 64,
        input_hash=hashlib.sha256(question_id.encode("utf-8")).hexdigest(),
        output_contract_version="t07.batch.v1",
        route_id="formal-test-route",
        provider="test-provider",
        model="test-model",
        model_version="test-model-v1",
        prompt_version="test-prompt-v1",
        prompt_hash="b" * 64,
        schema_version="t07.batch.v1",
        artifacts=normalized_artifacts,
        input_tokens=10,
        output_tokens=20,
        tokens_used=30,
        duration_seconds=1.25,
        attempts=1,
        failure_code=failure_code,
        validation_status=validation_status,
        validation_error_codes=(
            ()
            if validation_status == "passed"
            else ("REQUIRED_ARTIFACT_MISSING",)
        ),
        result_kind="actual" if actual else "mock",
        actual=actual,
        mock=mock,
        synthetic=synthetic,
        completed=(
            status == "completed"
            and validation_status == "passed"
            and actual
            and not mock
            and not synthetic
            and {artifact.name for artifact in normalized_artifacts}
            == set(REQUIRED_ARTIFACTS)
        ),
    )


def _five_records():
    return tuple(_record(f"Q{number:03d}") for number in range(1, 6))


def _job(question_id: str = "Q001") -> BatchJob:
    artifacts = {
        name: f"batch-five/{question_id}/{name}"
        for name in REQUIRED_ARTIFACTS
    }
    return BatchJob(
        batch_id="batch-five",
        question_id=question_id,
        source_hash="a" * 64,
        input_hash="b" * 64,
        workspace=f"batch-five/{question_id}/workspace",
        context_id=f"ctx:batch-five:{question_id}:bbbbbbbbbbbbbbbb",
        cache_namespace=f"cache:batch-five:{question_id}:bbbbbbbbbbbbbbbb",
        status=JobStatus.COMPLETED,
        result_kind=ResultKind.ACTUAL,
        attempt=1,
        budget=BatchBudget(token_limit=30, tokens_used=30),
        model_route=ModelRoute(
            route_id="formal-test-route",
            provider="test-provider",
            model="test-model",
            model_version="test-model-v1",
            prompt_version="test-prompt-v1",
            prompt_hash="c" * 64,
        ),
        output_contract=OutputContract(
            fields={
                name: f"Synthetic value for {name}"
                for name in STANDARD_OUTPUT_FIELDS
            },
            artifacts=artifacts,
        ),
    )


def test_five_question_fixture_is_explicitly_non_actual() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert payload["synthetic"] is True
    assert payload["mock"] is True
    assert payload["formal_run"] is False
    assert payload["actual_execution"] is False
    assert payload["model_provider_called"] is False
    assert payload["authoritative_source_verified"] is False
    assert len(payload["records"]) == 5
    assert all(
        record["declared_result_kind"] == "mock"
        for record in payload["records"]
    )


def test_builds_five_question_delivery_index() -> None:
    index = _apis()[0].build_delivery_index("batch-five", _five_records())

    assert len(index.records) == 5
    assert [record.question_id for record in index.records] == [
        "Q001",
        "Q002",
        "Q003",
        "Q004",
        "Q005",
    ]


def test_total_completed_and_status_counts_are_derived() -> None:
    records = list(_five_records())
    records[-1] = _record(
        "Q005",
        status="failed",
        validation_status="failed",
        failure_code="SYNTHETIC_FAILURE",
        artifacts=(),
    )

    index = _apis()[0].build_delivery_index("batch-five", records)

    assert index.total == len(index.records) == 5
    assert index.status_counts == {"completed": 4, "failed": 1}
    assert index.completed == sum(record.completed for record in index.records) == 4


def test_duplicate_question_id_is_rejected() -> None:
    with pytest.raises(BatchRunnerError) as captured:
        _apis()[0].build_delivery_index(
            "batch-five",
            [_record("Q001"), _record("Q001")],
        )

    assert captured.value.error_code == "DELIVERY_DUPLICATE_QUESTION_ID"


def test_missing_file_validation_is_not_counted_completed() -> None:
    delivery, validation = _apis()
    failed_validation = validation.ArtifactValidationResult(
        validation_status="failed",
        issues=(
            validation.ArtifactValidationIssue(
                "REQUIRED_ARTIFACT_MISSING",
                "report.pdf",
                "synthetic missing file",
            ),
        ),
        artifacts=(),
    )

    record = delivery.build_question_delivery_record(
        _job(),
        SourceKind.PRODUCTION,
        failed_validation,
        None,
        input_tokens=10,
        output_tokens=20,
        duration_seconds=1.25,
    )
    index = delivery.build_delivery_index("batch-five", [record])

    assert index.total == 1
    assert index.completed == 0
    assert index.records[0].status == "completed"
    assert index.records[0].validation_status == "failed"


def test_question_delivery_record_derives_provenance_and_completion() -> None:
    delivery, validation = _apis()
    artifacts = _artifact_records("Q001")
    passed = validation.ArtifactValidationResult(
        validation_status="passed",
        issues=(),
        artifacts=artifacts,
    )
    manifest = validation.ArtifactManifest(
        batch_id="batch-five",
        question_id="Q001",
        output_contract_version="t07.batch.v1",
        validation_status="passed",
        artifacts=artifacts,
        manifest_sha256="d" * 64,
    )

    record = delivery.build_question_delivery_record(
        _job(),
        SourceKind.PRODUCTION,
        passed,
        manifest,
        input_tokens=10,
        output_tokens=20,
        duration_seconds=1.25,
    )

    assert record.completed is True
    assert record.actual is True
    assert record.mock is False
    assert record.synthetic is False
    assert record.tokens_used == 30
    assert record.input_tokens == 10
    assert record.output_tokens == 20
    assert record.model_version == "test-model-v1"
    assert record.prompt_version == "test-prompt-v1"
    assert record.schema_version == "t07.batch.v1"


def test_delivery_index_json_round_trip() -> None:
    delivery = _apis()[0]
    index = delivery.build_delivery_index("batch-five", _five_records())

    restored = delivery.DeliveryIndex.from_json(index.to_json())

    assert restored == index
    assert restored.index_sha256 == index.index_sha256


def test_v2_token_only_delivery_uses_null_cost_and_explicit_policy() -> None:
    delivery = _apis()[0]
    record = replace(
        _record("Q001"),
        output_contract_version="t07.batch.v2",
        schema_version="t07.batch.v2",
        budget_policy_version="t07.budget.token-only.v2",
        budget_mode="token_only",
        cost_accounting_required=False,
        price_snapshot_required=False,
        captain_waiver_reference="captain-option-b-approved-2026-08-07",
        estimated_cost_usd=None,
        settled_cost_usd=None,
    )

    payload = delivery.build_delivery_index("batch-five", (record,)).to_dict()
    delivered = payload["records"][0]

    assert delivered["budget_policy_version"] == "t07.budget.token-only.v2"
    assert delivered["budget_mode"] == "token_only"
    assert delivered["cost_accounting_required"] is False
    assert delivered["price_snapshot_required"] is False
    assert delivered["estimated_cost_usd"] is None
    assert delivered["settled_cost_usd"] is None
    assert "not_evaluated" not in json.dumps(payload)


def test_v2_token_only_delivery_rejects_zero_or_sentinel_cost() -> None:
    record = replace(
        _record("Q001"),
        budget_policy_version="t07.budget.token-only.v2",
        budget_mode="token_only",
        cost_accounting_required=False,
        price_snapshot_required=False,
        captain_waiver_reference="captain-option-b-approved-2026-08-07",
    )

    with pytest.raises(ValueError):
        replace(record, estimated_cost_usd=Decimal("0"))
    with pytest.raises(ValueError):
        replace(record, settled_cost_usd="not_evaluated")


def test_checksum_is_deterministic_order_independent_and_not_self_referential() -> None:
    delivery = _apis()[0]
    records = _five_records()

    forward = delivery.compute_delivery_index_sha256("batch-five", records)
    reverse = delivery.compute_delivery_index_sha256(
        "batch-five",
        tuple(reversed(records)),
    )

    assert forward == reverse
    assert forward == delivery.build_delivery_index(
        "batch-five",
        records,
    ).index_sha256


def test_tampered_derived_total_is_rejected() -> None:
    delivery = _apis()[0]
    index = delivery.build_delivery_index("batch-five", _five_records())
    forged = replace(index, total=999)

    with pytest.raises(BatchRunnerError) as captured:
        delivery.validate_delivery_index(forged)

    assert captured.value.error_code == "DELIVERY_TOTAL_MISMATCH"


def test_artifact_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    delivery = _apis()[0]
    question_root = tmp_path / "Q001"
    question_root.mkdir()
    artifact_records = []
    validation = _apis()[1]
    for name in REQUIRED_ARTIFACTS:
        target = question_root / name
        target.write_bytes(f"synthetic:{name}".encode("utf-8"))
        digest = validation.compute_file_sha256(target)
        if name == "report.md":
            digest = "f" * 64
        artifact_records.append(
            validation.ArtifactFileRecord(
                name=name,
                path=f"Q001/{name}",
                sha256=digest,
                size_bytes=target.stat().st_size,
            )
        )
    index = delivery.build_delivery_index(
        "batch-five",
        [_record("Q001", artifacts=tuple(artifact_records))],
    )

    with pytest.raises(BatchRunnerError) as captured:
        delivery.validate_delivery_index(index, artifact_root=tmp_path)

    assert captured.value.error_code == "DELIVERY_ARTIFACT_HASH_MISMATCH"


def test_one_failed_question_does_not_remove_other_records() -> None:
    records = list(_five_records())
    records[2] = _record(
        "Q003",
        status="failed",
        validation_status="failed",
        failure_code="SYNTHETIC_FAILURE",
        artifacts=(),
    )

    index = _apis()[0].build_delivery_index("batch-five", records)

    assert index.total == 5
    assert index.completed == 4
    assert {record.question_id for record in index.records} == {
        "Q001",
        "Q002",
        "Q003",
        "Q004",
        "Q005",
    }
    assert next(
        record.failure_code
        for record in index.records
        if record.question_id == "Q003"
    ) == "SYNTHETIC_FAILURE"
