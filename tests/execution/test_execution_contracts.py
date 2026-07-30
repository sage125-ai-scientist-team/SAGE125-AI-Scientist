"""T05 Wave A public execution-contract red tests.

These tests intentionally avoid importing ``app.contracts.execution`` at module
import time.  Every contract symbol is resolved inside its test through the
``require_symbol`` fixture so an absent module or symbol is reported as a clear
pytest failure rather than a collection error.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError


_SCHEMA_VERSION = "1.0"
_CONTRACT_MODULE = "app.contracts.execution"
_LEGACY_CASES_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "legacy_execution_metadata.json"
)


def _json_round_trip(model_cls: type, payload: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Validate, JSON-serialize, and revalidate a Pydantic v2 contract."""
    model = model_cls.model_validate(payload)
    dumped = model.model_dump(mode="json")
    wire_payload = json.loads(
        json.dumps(dumped, ensure_ascii=False, sort_keys=True)
    )
    restored = model_cls.model_validate(wire_payload)
    assert restored == model
    assert restored.model_dump(mode="json") == dumped
    return model, dumped


def _load_legacy_cases() -> list[dict[str, Any]]:
    """Load the stable legacy-normalization vectors without importing app code."""
    payload = json.loads(_LEGACY_CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("legacy execution metadata fixture must contain a JSON list")
    return payload


def _public_value(value: Any, field: str) -> Any:
    """Read a normalization result that may be Pydantic or attribute-based."""
    if isinstance(value, Mapping):
        return value.get(field)
    return getattr(value, field)


_LEGACY_CASES = _load_legacy_cases()


def test_t05_a_contract_001_execution_spec_round_trip(
    require_symbol,
    execution_spec_payload,
    artifact_requirement_payload,
):
    """T05-A-CONTRACT-001: ExecutionSpec has a lossless JSON round-trip."""
    execution_spec = require_symbol(
        _CONTRACT_MODULE,
        "ExecutionSpec",
        "T05-A-CONTRACT-001",
    )
    payload = execution_spec_payload(
        required_artifacts=[artifact_requirement_payload()]
    )

    _model, dumped = _json_round_trip(execution_spec, payload)

    assert dumped["schema_version"] == _SCHEMA_VERSION
    assert dumped["spec_id"] == payload["spec_id"]
    assert dumped["question_id"] == payload["question_id"]
    assert dumped["round_index"] == payload["round_index"]
    assert dumped["seed"] == payload["seed"]
    assert dumped["resources"] == payload["resources"]
    assert dumped["required_artifacts"] == payload["required_artifacts"]
    assert dumped["mode"] in {"actual", "dry_run", "mock", "test"}
    assert isinstance(dumped["argv"], list)


def test_t05_a_contract_002_execution_result_round_trip(
    require_symbol,
    execution_result_payload,
):
    """T05-A-CONTRACT-002: ExecutionResult persists all derived truth fields."""
    execution_result = require_symbol(
        _CONTRACT_MODULE,
        "ExecutionResult",
        "T05-A-CONTRACT-002",
    )
    payload = execution_result_payload()

    model, dumped = _json_round_trip(execution_result, payload)

    assert dumped["schema_version"] == _SCHEMA_VERSION
    assert dumped["execution_id"] == payload["execution_id"]
    for field in (
        "runner_verified",
        "actual_execution",
        "artifacts_validated",
        "metrics_validated",
        "scientific_result_usable",
    ):
        assert field not in payload, f"{field} must not be caller supplied"
        assert field in dumped, f"{field} must be serialized"
        assert isinstance(dumped[field], bool)
        assert dumped[field] is False
    with pytest.raises(ValidationError):
        model.actual_execution = True


def test_t05_a_contract_003_dataset_manifest_round_trip(
    require_symbol,
    dataset_payload,
):
    """T05-A-CONTRACT-003: DatasetManifest provenance survives JSON round-trip."""
    dataset_manifest = require_symbol(
        _CONTRACT_MODULE,
        "DatasetManifest",
        "T05-A-CONTRACT-003",
    )
    payload = dataset_payload()

    _model, dumped = _json_round_trip(dataset_manifest, payload)

    assert dumped["schema_version"] == _SCHEMA_VERSION
    assert dumped["dataset_id"] == payload["dataset_id"]
    assert dumped["source_uri"] == payload["source_uri"]
    assert dumped["license"] == payload["license"]
    assert dumped["version"] == payload["version"]
    assert dumped["sha256"] == payload["sha256"]
    assert dumped["size_bytes"] == payload["size_bytes"]


def test_t05_a_contract_004_artifact_manifest_round_trip(
    require_symbol,
    artifact_manifest_payload,
):
    """T05-A-CONTRACT-004: ArtifactManifest remains a durable JSON contract."""
    artifact_manifest = require_symbol(
        _CONTRACT_MODULE,
        "ArtifactManifest",
        "T05-A-CONTRACT-004",
    )
    payload = artifact_manifest_payload()

    _model, dumped = _json_round_trip(artifact_manifest, payload)

    assert dumped["schema_version"] == _SCHEMA_VERSION
    assert dumped["artifact_id"] == payload["artifact_id"]
    assert dumped["relative_path"] == payload["relative_path"]
    assert dumped["kind"] == payload["kind"]
    assert dumped["media_type"] == payload["media_type"]
    assert dumped["required"] is payload["required"]
    assert dumped["sha256"] == payload["sha256"]
    assert dumped["size_bytes"] == payload["size_bytes"]
    assert dumped["validation_status"] == payload["validation_status"]
    assert dumped["collected_at"] == payload["collected_at"]


@pytest.mark.parametrize(
    ("symbol_name", "payload_fixture_name"),
    [
        ("ExecutionSpec", "execution_spec_payload"),
        ("ExecutionResult", "execution_result_payload"),
        ("DatasetManifest", "dataset_payload"),
        ("ArtifactRequirement", "artifact_requirement_payload"),
        ("ArtifactManifest", "artifact_manifest_payload"),
        ("MetricRequirement", "metric_requirement_payload"),
        ("MetricRecord", "metric_record_payload"),
        ("ResourceLimitRequest", "resource_limit_payload"),
        ("ResourceLimitEnforcement", "resource_enforcement_payload"),
        ("EnvironmentFingerprint", "environment_fingerprint_payload"),
        ("ExecutionError", "execution_error_payload"),
    ],
    ids=[
        "execution-spec",
        "execution-result",
        "dataset-manifest",
        "artifact-requirement",
        "artifact-manifest",
        "metric-requirement",
        "metric-record",
        "resource-limit-request",
        "resource-limit-enforcement",
        "environment-fingerprint",
        "execution-error",
    ],
)
def test_t05_a_contract_005_schema_version_extra_forbid_and_frozen(
    require_symbol,
    request,
    symbol_name,
    payload_fixture_name,
):
    """T05-A-CONTRACT-005: v1 contracts are versioned, closed, and immutable."""
    model_cls = require_symbol(
        _CONTRACT_MODULE,
        symbol_name,
        "T05-A-CONTRACT-005",
    )
    payload_factory = request.getfixturevalue(payload_fixture_name)
    payload = payload_factory()
    model = model_cls.model_validate(payload)

    assert model.schema_version == _SCHEMA_VERSION
    assert model.model_dump(mode="json")["schema_version"] == _SCHEMA_VERSION

    default_version = dict(payload)
    default_version.pop("schema_version")
    assert (
        model_cls.model_validate(default_version).schema_version
        == _SCHEMA_VERSION
    )

    wrong_version = dict(payload)
    wrong_version["schema_version"] = "9.9"
    with pytest.raises(ValidationError):
        model_cls.model_validate(wrong_version)

    unexpected = dict(payload)
    unexpected["unexpected_t05_field"] = "must be rejected"
    with pytest.raises(ValidationError) as extra_error:
        model_cls.model_validate(unexpected)
    assert "extra_forbidden" in {
        item["type"] for item in extra_error.value.errors()
    }

    with pytest.raises(ValidationError) as frozen_error:
        model.schema_version = "9.9"
    assert "frozen_instance" in {
        item["type"] for item in frozen_error.value.errors()
    }


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param(
            {"status": "not-a-status"},
            id="unknown-status",
        ),
        pytest.param(
            {
                "status": "planned",
                "process_started": True,
                "exit_code": None,
                "timed_out": False,
            },
            id="planned-process-started",
        ),
        pytest.param(
            {
                "status": "rejected",
                "process_started": True,
                "exit_code": None,
                "timed_out": False,
            },
            id="rejected-process-started",
        ),
        pytest.param(
            {
                "mode": "actual",
                "status": "succeeded",
                "process_started": False,
                "exit_code": 0,
                "timed_out": False,
            },
            id="succeeded-process-not-started",
        ),
        pytest.param(
            {
                "mode": "actual",
                "status": "succeeded",
                "process_started": True,
                "exit_code": 7,
                "timed_out": False,
            },
            id="succeeded-nonzero-exit",
        ),
        pytest.param(
            {
                "mode": "actual",
                "status": "succeeded",
                "process_started": True,
                "exit_code": 0,
                "timed_out": True,
            },
            id="succeeded-timed-out",
        ),
        pytest.param(
            {
                "mode": "actual",
                "status": "timed_out",
                "process_started": True,
                "exit_code": None,
                "timed_out": False,
            },
            id="timed-out-flag-false",
        ),
        pytest.param(
            {
                "mode": "actual",
                "status": "running",
                "process_started": True,
                "exit_code": 0,
                "timed_out": False,
            },
            id="running-has-exit-code",
        ),
    ],
)
def test_t05_a_contract_006_execution_result_rejects_invalid_state_combinations(
    require_symbol,
    execution_result_payload,
    overrides,
):
    """T05-A-CONTRACT-006: impossible execution states fail validation."""
    execution_result = require_symbol(
        _CONTRACT_MODULE,
        "ExecutionResult",
        "T05-A-CONTRACT-006",
    )
    payload = execution_result_payload(**overrides)

    with pytest.raises(ValidationError):
        execution_result.model_validate(payload)


@pytest.mark.parametrize(
    "derived_field",
    [
        "runner_verified",
        "actual_execution",
        "artifacts_validated",
        "metrics_validated",
        "scientific_result_usable",
    ],
    ids=[
        "runner-verified",
        "actual-execution",
        "artifacts-validated",
        "metrics-validated",
        "scientific-result-usable",
    ],
)
def test_t05_a_contract_006_execution_result_rejects_caller_derived_truth(
    require_symbol,
    execution_result_payload,
    derived_field,
):
    """T05-A-CONTRACT-006: callers cannot inject runner-owned truth fields."""
    execution_result = require_symbol(
        _CONTRACT_MODULE,
        "ExecutionResult",
        "T05-A-CONTRACT-006",
    )
    payload = execution_result_payload()
    payload[derived_field] = True

    with pytest.raises(ValidationError):
        execution_result.model_validate_untrusted(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"spec_id": ""}, id="empty-spec-id"),
        pytest.param({"entrypoint": ""}, id="empty-entrypoint"),
        pytest.param({"argv": "--not-an-argv-list"}, id="argv-is-string"),
        pytest.param({"seed": -1}, id="negative-seed"),
        pytest.param({"mode": "production"}, id="unknown-mode"),
    ],
)
def test_t05_a_contract_006_execution_spec_rejects_invalid_inputs(
    require_symbol,
    execution_spec_payload,
    overrides,
):
    """T05-A-CONTRACT-006: malformed execution requests fail closed."""
    execution_spec = require_symbol(
        _CONTRACT_MODULE,
        "ExecutionSpec",
        "T05-A-CONTRACT-006",
    )
    payload = execution_spec_payload(**overrides)

    with pytest.raises(ValidationError):
        execution_spec.model_validate(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"dataset_id": ""}, id="empty-dataset-id"),
        pytest.param({"source_uri": ""}, id="empty-source-uri"),
        pytest.param({"license": ""}, id="empty-license"),
        pytest.param({"version": ""}, id="empty-version"),
        pytest.param({"sha256": "a" * 63}, id="short-sha256"),
        pytest.param({"sha256": "A" * 64}, id="uppercase-sha256"),
        pytest.param({"size_bytes": -1}, id="negative-size"),
    ],
)
def test_t05_a_contract_006_dataset_manifest_rejects_incomplete_provenance(
    require_symbol,
    dataset_payload,
    overrides,
):
    """T05-A-CONTRACT-006: dataset provenance cannot be empty or malformed."""
    dataset_manifest = require_symbol(
        _CONTRACT_MODULE,
        "DatasetManifest",
        "T05-A-CONTRACT-006",
    )
    payload = dataset_payload(**overrides)

    with pytest.raises(ValidationError):
        dataset_manifest.model_validate(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param(
            {"relative_path": "../outside/result.json"},
            id="parent-traversal",
        ),
        pytest.param(
            {"relative_path": r"..\outside\result.json"},
            id="windows-parent-traversal",
        ),
        pytest.param(
            {"relative_path": "/outside/result.json"},
            id="posix-absolute",
        ),
        pytest.param(
            {"relative_path": r"C:\outside\result.json"},
            id="windows-drive-absolute",
        ),
        pytest.param({"artifact_id": ""}, id="empty-artifact-id"),
        pytest.param({"max_bytes": 0}, id="zero-max-bytes"),
        pytest.param(
            {"expected_sha256": "not-a-sha256"},
            id="malformed-expected-sha256",
        ),
    ],
)
def test_t05_a_contract_006_artifact_requirement_rejects_unsafe_declarations(
    require_symbol,
    artifact_requirement_payload,
    overrides,
):
    """T05-A-CONTRACT-006: required artifacts remain workspace-relative."""
    artifact_requirement = require_symbol(
        _CONTRACT_MODULE,
        "ArtifactRequirement",
        "T05-A-CONTRACT-006",
    )
    payload = artifact_requirement_payload(**overrides)

    with pytest.raises(ValidationError):
        artifact_requirement.model_validate(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param(
            {"relative_path": "../outside/result.json"},
            id="parent-traversal",
        ),
        pytest.param({"sha256": "a" * 63}, id="short-sha256"),
        pytest.param({"sha256": "A" * 64}, id="uppercase-sha256"),
        pytest.param({"size_bytes": -1}, id="negative-size"),
        pytest.param(
            {"validation_status": "unchecked"},
            id="unknown-validation-status",
        ),
        pytest.param(
            {"collected_at": "2026-07-28T00:00:00"},
            id="naive-collected-at",
        ),
    ],
)
def test_t05_a_contract_006_artifact_manifest_rejects_invalid_evidence(
    require_symbol,
    artifact_manifest_payload,
    overrides,
):
    """T05-A-CONTRACT-006: collected artifacts require valid evidence fields."""
    artifact_manifest = require_symbol(
        _CONTRACT_MODULE,
        "ArtifactManifest",
        "T05-A-CONTRACT-006",
    )
    payload = artifact_manifest_payload(**overrides)

    with pytest.raises(ValidationError):
        artifact_manifest.model_validate(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"timeout_seconds": 0}, id="zero-timeout"),
        pytest.param({"max_stdout_bytes": 0}, id="zero-stdout-limit"),
        pytest.param({"max_stderr_bytes": 0}, id="zero-stderr-limit"),
        pytest.param({"max_artifact_bytes": 0}, id="zero-artifact-limit"),
        pytest.param({"cpu_seconds": -1}, id="negative-cpu-limit"),
        pytest.param({"memory_bytes": -1}, id="negative-memory-limit"),
    ],
)
def test_t05_a_contract_006_resource_limits_reject_nonpositive_values(
    require_symbol,
    resource_limit_payload,
    overrides,
):
    """T05-A-CONTRACT-006: requested limits must be positive when present."""
    resource_limit_request = require_symbol(
        _CONTRACT_MODULE,
        "ResourceLimitRequest",
        "T05-A-CONTRACT-006",
    )
    payload = resource_limit_payload(**overrides)

    with pytest.raises(ValidationError):
        resource_limit_request.model_validate(payload)


@pytest.mark.parametrize(
    "legacy_case",
    _LEGACY_CASES,
    ids=[case["case_id"] for case in _LEGACY_CASES],
)
def test_t05_a_contract_007_legacy_execution_metadata_normalization(
    require_symbol,
    legacy_case,
):
    """T05-A-CONTRACT-007: 17 legacy values normalize without bool(value)."""
    adapter = require_symbol(
        _CONTRACT_MODULE,
        "LegacyExecutionMetadataAdapter",
        "T05-A-CONTRACT-007",
    )
    metadata = legacy_case["input"]
    before = json.loads(json.dumps(metadata, ensure_ascii=False))

    normalized = adapter.normalize(metadata)

    assert metadata == before, "legacy normalization must not mutate caller data"
    assert (
        _public_value(normalized, "legacy_claim")
        is legacy_case["expected_legacy_claim"]
    )
    assert (
        _public_value(normalized, "canonical_actual_execution")
        is legacy_case["expected_canonical_actual_execution"]
    )
    assert _public_value(normalized, "warning") == legacy_case["expected_warning"]
    assert _public_value(normalized, "error") == legacy_case["expected_error"]
    assert _public_value(normalized, "canonical_actual_execution") is False
