"""Red tests for runner-attested execution truthfulness."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
from pydantic import ValidationError


def _model(
    require_symbol: Callable[[str, str, str], Any],
    symbol_name: str,
    test_id: str,
) -> Any:
    return require_symbol("app.contracts.execution", symbol_name, test_id)


def _make_spec(
    require_symbol: Callable[[str, str, str], Any],
    test_id: str,
    execution_spec_payload: Callable[..., dict[str, Any]],
    **overrides: Any,
) -> Any:
    execution_spec = _model(require_symbol, "ExecutionSpec", test_id)
    return execution_spec.model_validate(execution_spec_payload(**overrides))


def _make_runner(
    require_symbol: Callable[[str, str, str], Any],
    test_id: str,
    probe_script: Path,
    managed_root: Path,
    *,
    entrypoint_class: str = "test",
    allowed_environment: tuple[str, ...] = (),
    dataset_resolver: Callable[[Any], Path] | None = None,
    dependency_version_provider: Callable[[tuple[str, ...]], dict[str, str]] | None = None,
    git_provenance_provider: Callable[[], dict[str, Any]] | None = None,
    cleanup: Callable[[Path], None] | None = None,
) -> Any:
    registry_type = require_symbol("app.execution", "EntrypointRegistry", test_id)
    runner_type = require_symbol("app.execution", "LocalProcessRunner", test_id)
    registry = registry_type()
    registry.register_python(
        "probe",
        probe_script,
        entrypoint_class=entrypoint_class,
        allowed_environment=allowed_environment,
    )
    return runner_type(
        registry=registry,
        managed_root=managed_root,
        dataset_resolver=dataset_resolver,
        dependency_version_provider=dependency_version_provider,
        git_provenance_provider=git_provenance_provider,
        cleanup=cleanup,
    )


def _assert_not_actual(result: Any) -> None:
    assert result.actual_execution is False
    assert result.runner_verified is False


def test_T05_A_INTEGRITY_001_planned_is_unverified(
    require_symbol: Callable[[str, str, str], Any],
    execution_result_payload: Callable[..., dict[str, Any]],
) -> None:
    """T05-A-INTEGRITY-001: planned results never claim a process or attestation."""

    test_id = "T05-A-INTEGRITY-001"
    execution_result = _model(require_symbol, "ExecutionResult", test_id)
    result = execution_result.model_validate(execution_result_payload())
    assert result.process_started is False
    _assert_not_actual(result)


def test_T05_A_INTEGRITY_002_dry_run_never_becomes_actual(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-002: dry-run success starts no process or observed metric."""

    test_id = "T05-A-INTEGRITY-002"
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="dry_run",
        argv=["fail", "--code", "9"],
    )
    runner = _make_runner(require_symbol, test_id, probe_script, managed_root)
    result = runner.run(spec)
    assert result.status == "succeeded"
    assert result.process_started is False
    assert result.metrics == []
    _assert_not_actual(result)


def test_T05_A_INTEGRITY_003_mock_metric_is_not_scientific(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-003: mock success cannot produce a usable observation."""

    test_id = "T05-A-INTEGRITY-003"
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="mock",
        argv=["noop"],
    )
    runner = _make_runner(require_symbol, test_id, probe_script, managed_root)
    result = runner.run(spec)
    assert result.status == "succeeded"
    assert all(metric.source != "observed" for metric in result.metrics)
    assert result.scientific_result_usable is False
    _assert_not_actual(result)


def test_T05_A_INTEGRITY_004_test_fixture_success_is_not_actual(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-004: a real test subprocess remains non-scientific."""

    test_id = "T05-A-INTEGRITY-004"
    spec = _make_spec(require_symbol, test_id, execution_spec_payload, mode="test")
    runner = _make_runner(require_symbol, test_id, probe_script, managed_root)
    result = runner.run(spec)
    assert result.status == "succeeded"
    assert result.exit_code == 0
    assert result.process_started is True
    _assert_not_actual(result)


def test_T05_A_INTEGRITY_004_actual_mode_rejects_test_entrypoint(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    source_root: Path,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-004: actual mode rejects a test-only registry entry."""

    test_id = "T05-A-INTEGRITY-004"
    dataset, source = _actual_dataset(
        require_symbol, test_id, source_root, dataset_bytes, dataset_payload
    )
    artifact_requirement_type = _model(
        require_symbol, "ArtifactRequirement", test_id
    )
    metric_requirement_type = _model(require_symbol, "MetricRequirement", test_id)
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="actual",
        datasets=[dataset],
        required_artifacts=[
            artifact_requirement_type.model_validate(
                artifact_requirement_payload()
            )
        ],
        required_metrics=[
            metric_requirement_type.model_validate(metric_requirement_payload())
        ],
        argv=[
            "artifact",
            "artifacts/metrics.json",
            "--metric-name",
            "score",
            "--metric-value",
            "0.875",
            "--metric-unit",
            "ratio",
        ],
    )
    result = _make_runner(
        require_symbol,
        test_id,
        probe_script,
        managed_root,
        entrypoint_class="test",
        dataset_resolver=lambda _manifest: source,
    ).run(spec)
    assert result.status == "rejected"
    assert result.error.code == "entrypoint_not_allowed"
    assert result.process_started is False
    _assert_not_actual(result)


@pytest.mark.parametrize(
    ("legacy_value", "valid", "expected_claim"),
    [
        pytest.param("false", True, False, id="T05-A-INTEGRITY-005-string-false"),
        pytest.param("0", True, False, id="T05-A-INTEGRITY-005-string-zero"),
        pytest.param("yes", False, None, id="T05-A-INTEGRITY-005-string-yes"),
        pytest.param("garbage", False, None, id="T05-A-INTEGRITY-005-garbage"),
    ],
)
def test_T05_A_INTEGRITY_005_legacy_truthiness_is_forbidden(
    require_symbol: Callable[[str, str, str], Any],
    legacy_value: str,
    valid: bool,
    expected_claim: bool | None,
) -> None:
    """T05-A-INTEGRITY-005: legacy strings use an explicit table, never bool(value)."""

    test_id = "T05-A-INTEGRITY-005"
    adapter = _model(require_symbol, "LegacyExecutionMetadataAdapter", test_id)
    normalized = adapter.normalize({"actual_execution": legacy_value})
    if not valid:
        assert normalized.legacy_claim is None
        assert normalized.canonical_actual_execution is False
        assert normalized.error == "legacy_actual_execution_invalid"
        return
    assert normalized.legacy_claim is expected_claim
    assert normalized.canonical_actual_execution is False
    assert normalized.error is None


@pytest.mark.parametrize(
    "spoofed_field",
    [
        pytest.param("actual_execution", id="T05-A-INTEGRITY-006-actual-execution"),
        pytest.param("runner_verified", id="T05-A-INTEGRITY-006-runner-verified"),
        pytest.param(
            "datasets_validated",
            id="T05-A-INTEGRITY-006-datasets-validated",
        ),
        pytest.param("artifacts_validated", id="T05-A-INTEGRITY-006-artifacts-validated"),
        pytest.param("metrics_validated", id="T05-A-INTEGRITY-006-metrics-validated"),
        pytest.param(
            "provenance_complete",
            id="T05-A-INTEGRITY-006-provenance-complete",
        ),
        pytest.param(
            "scientific_result_usable",
            id="T05-A-INTEGRITY-006-scientific-result-usable",
        ),
    ],
)
def test_T05_A_INTEGRITY_006_caller_cannot_spoof_attestation(
    require_symbol: Callable[[str, str, str], Any],
    execution_result_payload: Callable[..., dict[str, Any]],
    spoofed_field: str,
) -> None:
    """T05-A-INTEGRITY-006: caller JSON cannot set runner-owned truth fields."""

    test_id = "T05-A-INTEGRITY-006"
    execution_result = _model(require_symbol, "ExecutionResult", test_id)
    with pytest.raises(ValidationError):
        execution_result.model_validate_untrusted(
            execution_result_payload(**{spoofed_field: True})
        )


def test_T05_A_INTEGRITY_006_complete_caller_json_still_lacks_attestation(
    require_symbol: Callable[[str, str, str], Any],
    execution_result_payload: Callable[..., dict[str, Any]],
    artifact_manifest_payload: Callable[..., dict[str, Any]],
    metric_record_payload: Callable[..., dict[str, Any]],
    environment_fingerprint_payload: Callable[..., dict[str, Any]],
) -> None:
    """T05-A-INTEGRITY-006: a complete-looking JSON chain is still untrusted."""

    test_id = "T05-A-INTEGRITY-006"
    execution_result = _model(require_symbol, "ExecutionResult", test_id)
    forged = execution_result_payload(
        mode="actual",
        status="succeeded",
        process_started=True,
        exit_code=0,
        timed_out=False,
        artifacts=[artifact_manifest_payload()],
        metrics=[metric_record_payload(source="observed")],
        cleanup_status="preserved",
        environment_fingerprint=environment_fingerprint_payload(),
    )
    untrusted = execution_result.model_validate_untrusted(forged)

    assert untrusted.datasets_validated is False
    assert untrusted.artifacts_validated is False
    assert untrusted.metrics_validated is False
    assert untrusted.provenance_complete is False
    assert untrusted.scientific_result_usable is False
    assert untrusted.runner_verified is False
    assert untrusted.actual_execution is False


def test_T05_A_INTEGRITY_006_copy_and_construct_cannot_spoof_attestation(
    require_symbol: Callable[[str, str, str], Any],
    execution_result_payload: Callable[..., dict[str, Any]],
) -> None:
    """Normal Pydantic bypass APIs cannot create runner-owned truth."""

    test_id = "T05-A-INTEGRITY-006"
    execution_result = _model(require_symbol, "ExecutionResult", test_id)
    untrusted = execution_result.model_validate_untrusted(
        execution_result_payload()
    )

    with pytest.raises(ValueError, match="runner-owned truth"):
        untrusted.model_copy(
            update={"runner_verified": True, "actual_execution": True}
        )
    with pytest.raises(ValueError, match="runner-owned truth"):
        execution_result.model_construct(
            **execution_result_payload(),
            runner_verified=True,
            actual_execution=True,
        )
    with pytest.raises(ValueError, match="runner attestation"):
        execution_result._from_runner(execution_result_payload())


def test_T05_A_INTEGRITY_006_caller_cannot_spoof_resource_enforcement(
    require_symbol: Callable[[str, str, str], Any],
    execution_result_payload: Callable[..., dict[str, Any]],
    resource_enforcement_payload: Callable[..., dict[str, Any]],
) -> None:
    """Resource enforcement evidence is runner-owned and fail-closed."""

    test_id = "T05-A-INTEGRITY-006"
    execution_result = _model(require_symbol, "ExecutionResult", test_id)
    payload = execution_result_payload(
        resource_enforcement=resource_enforcement_payload()
    )

    with pytest.raises(ValidationError, match="runner-owned evidence"):
        execution_result.model_validate_untrusted(payload)
    untrusted = execution_result.model_validate_untrusted(
        execution_result_payload()
    )
    with pytest.raises(ValueError, match="runner-owned evidence"):
        untrusted.model_copy(
            update={"resource_enforcement": resource_enforcement_payload()}
        )
    with pytest.raises(ValueError, match="runner-owned evidence"):
        execution_result.model_construct(**payload)


def test_T05_A_INTEGRITY_007_nonzero_exit_is_not_actual(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    source_root: Path,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-007: nonzero subprocess exit is classified precisely."""

    test_id = "T05-A-INTEGRITY-007"
    dataset, source = _actual_dataset(
        require_symbol, test_id, source_root, dataset_bytes, dataset_payload
    )
    artifact_requirement_type = _model(
        require_symbol, "ArtifactRequirement", test_id
    )
    metric_requirement_type = _model(require_symbol, "MetricRequirement", test_id)
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="actual",
        datasets=[dataset],
        required_artifacts=[
            artifact_requirement_type.model_validate(
                artifact_requirement_payload()
            )
        ],
        required_metrics=[
            metric_requirement_type.model_validate(metric_requirement_payload())
        ],
        argv=["fail", "--code", "7"],
    )
    result = _make_runner(
        require_symbol,
        test_id,
        probe_script,
        managed_root,
        entrypoint_class="scientific",
        dataset_resolver=lambda _manifest: source,
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    ).run(spec)
    assert result.status == "failed"
    assert result.error.code == "nonzero_exit"
    assert result.exit_code == 7
    assert result.process_started is True
    _assert_not_actual(result)


def test_T05_A_INTEGRITY_008_timeout_is_not_actual(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    resource_limit_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    source_root: Path,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-008: timed-out direct children are terminated and classified."""

    test_id = "T05-A-INTEGRITY-008"
    dataset, source = _actual_dataset(
        require_symbol, test_id, source_root, dataset_bytes, dataset_payload
    )
    artifact_requirement_type = _model(
        require_symbol, "ArtifactRequirement", test_id
    )
    metric_requirement_type = _model(require_symbol, "MetricRequirement", test_id)
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="actual",
        datasets=[dataset],
        required_artifacts=[
            artifact_requirement_type.model_validate(
                artifact_requirement_payload()
            )
        ],
        required_metrics=[
            metric_requirement_type.model_validate(metric_requirement_payload())
        ],
        argv=["sleep", "--seconds", "5"],
        resources=resource_limit_payload(timeout_seconds=0.1),
    )
    result = _make_runner(
        require_symbol,
        test_id,
        probe_script,
        managed_root,
        entrypoint_class="scientific",
        dataset_resolver=lambda _manifest: source,
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    ).run(spec)
    assert result.status == "timed_out"
    assert result.error.code == "timeout"
    assert result.timed_out is True
    assert result.process_started is True
    _assert_not_actual(result)


def _actual_dataset(
    require_symbol: Callable[[str, str, str], Any],
    test_id: str,
    source_root: Path,
    dataset_bytes: bytes,
    dataset_payload: Callable[..., dict[str, Any]],
) -> tuple[Any, Path]:
    source = source_root / "dataset.csv"
    source.write_bytes(dataset_bytes)
    dataset_manifest = _model(require_symbol, "DatasetManifest", test_id)
    return dataset_manifest.model_validate(dataset_payload()), source


def test_T05_A_INTEGRITY_009_missing_required_artifact_fails(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    source_root: Path,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-009: exit zero cannot hide a missing required artifact."""

    test_id = "T05-A-INTEGRITY-009"
    dataset, source = _actual_dataset(
        require_symbol, test_id, source_root, dataset_bytes, dataset_payload
    )
    requirement_type = _model(require_symbol, "ArtifactRequirement", test_id)
    requirement = requirement_type.model_validate(artifact_requirement_payload())
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="actual",
        datasets=[dataset],
        required_artifacts=[requirement],
        argv=["noop"],
    )
    runner = _make_runner(
        require_symbol,
        test_id,
        probe_script,
        managed_root,
        entrypoint_class="scientific",
        dataset_resolver=lambda _manifest: source,
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    )
    result = runner.run(spec)
    assert result.status == "failed"
    assert result.error.code == "artifact_missing"
    _assert_not_actual(result)


def test_T05_A_INTEGRITY_010_checksum_mismatch_fails_closed(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    source_root: Path,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-010: an artifact checksum mismatch is terminal."""

    test_id = "T05-A-INTEGRITY-010"
    dataset, source = _actual_dataset(
        require_symbol, test_id, source_root, dataset_bytes, dataset_payload
    )
    requirement_type = _model(require_symbol, "ArtifactRequirement", test_id)
    requirement = requirement_type.model_validate(
        artifact_requirement_payload(expected_sha256="0" * 64)
    )
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="actual",
        datasets=[dataset],
        required_artifacts=[requirement],
        argv=[
            "artifact",
            "artifacts/metrics.json",
            "--metric-name",
            "score",
            "--metric-value",
            "0.875",
            "--metric-unit",
            "ratio",
        ],
    )
    runner = _make_runner(
        require_symbol,
        test_id,
        probe_script,
        managed_root,
        entrypoint_class="scientific",
        dataset_resolver=lambda _manifest: source,
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    )
    result = runner.run(spec)
    assert result.status == "failed"
    assert result.error.code == "checksum_mismatch"
    _assert_not_actual(result)


def test_T05_A_INTEGRITY_011_only_full_internal_evidence_is_actual(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    artifact_sha256: str,
    source_root: Path,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-011: only the complete runner evidence chain attests actual."""

    test_id = "T05-A-INTEGRITY-011"
    dataset, source = _actual_dataset(
        require_symbol, test_id, source_root, dataset_bytes, dataset_payload
    )
    artifact_requirement_type = _model(
        require_symbol, "ArtifactRequirement", test_id
    )
    metric_requirement_type = _model(require_symbol, "MetricRequirement", test_id)
    artifact_requirement = artifact_requirement_type.model_validate(
        artifact_requirement_payload()
    )
    metric_requirement = metric_requirement_type.model_validate(
        metric_requirement_payload()
    )
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="actual",
        datasets=[dataset],
        required_artifacts=[artifact_requirement],
        required_metrics=[metric_requirement],
        cleanup_policy="preserve",
        argv=[
            "artifact",
            "artifacts/metrics.json",
            "--metric-name",
            "score",
            "--metric-value",
            "0.875",
            "--metric-unit",
            "ratio",
        ],
    )
    runner = _make_runner(
        require_symbol,
        test_id,
        probe_script,
        managed_root,
        entrypoint_class="scientific",
        dataset_resolver=lambda _manifest: source,
        dependency_version_provider=lambda names: {
            name: {"pydantic": "2.12.4", "pytest": "9.0.3"}[name]
            for name in names
        },
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    )
    result = runner.run(spec)
    assert result.mode == "actual"
    assert result.status == "succeeded"
    assert result.process_started is True
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.datasets_validated is True
    assert result.artifacts_validated is True
    assert result.metrics_validated is True
    assert result.scientific_result_usable is True
    assert result.provenance_complete is True
    assert result.environment_fingerprint.git_dirty is False
    assert result.cleanup_status == "preserved"
    assert len(result.artifacts) == 1
    assert result.artifacts[0].artifact_id == "metrics-primary"
    assert result.artifacts[0].sha256 == artifact_sha256
    assert result.artifacts[0].validation_status == "valid"
    assert len(result.metrics) == 1
    assert result.metrics[0].name == "score"
    assert result.metrics[0].value == pytest.approx(0.875)
    assert result.metrics[0].unit == "ratio"
    assert result.metrics[0].source == "observed"
    assert result.metrics[0].artifact_id == "metrics-primary"
    assert result.runner_verified is True
    assert result.actual_execution is True


@pytest.mark.parametrize(
    "metric_source",
    [
        pytest.param("expected", id="T05-A-INTEGRITY-012-expected"),
        pytest.param("default", id="T05-A-INTEGRITY-012-default"),
        pytest.param("mock", id="T05-A-INTEGRITY-012-mock"),
        pytest.param("test", id="T05-A-INTEGRITY-012-test"),
    ],
)
def test_T05_A_INTEGRITY_012_nonobserved_metric_cannot_enter_actual_result(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    source_root: Path,
    probe_script: Path,
    managed_root: Path,
    metric_source: str,
) -> None:
    """T05-A-INTEGRITY-012: expected/default/mock/test metrics fail closed."""

    test_id = "T05-A-INTEGRITY-012"
    dataset, source = _actual_dataset(
        require_symbol, test_id, source_root, dataset_bytes, dataset_payload
    )
    artifact_requirement_type = _model(
        require_symbol, "ArtifactRequirement", test_id
    )
    metric_requirement_type = _model(require_symbol, "MetricRequirement", test_id)
    artifact_requirement = artifact_requirement_type.model_validate(
        artifact_requirement_payload(expected_sha256=None)
    )
    metric_requirement = metric_requirement_type.model_validate(
        metric_requirement_payload()
    )
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="actual",
        datasets=[dataset],
        required_artifacts=[artifact_requirement],
        required_metrics=[metric_requirement],
        argv=[
            "artifact",
            "artifacts/metrics.json",
            "--metric-name",
            "score",
            "--metric-value",
            "0.875",
            "--metric-unit",
            "ratio",
            "--metric-source",
            metric_source,
        ],
    )
    runner = _make_runner(
        require_symbol,
        test_id,
        probe_script,
        managed_root,
        entrypoint_class="scientific",
        dataset_resolver=lambda _manifest: source,
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    )
    result = runner.run(spec)
    assert result.status == "failed"
    assert result.error.code == "metric_invalid"
    assert result.metrics_validated is False
    assert result.actual_execution is False


def test_T05_A_INTEGRITY_013_unimplemented_resource_limits_are_not_enforced(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    resource_limit_payload: Callable[..., dict[str, Any]],
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-INTEGRITY-013: unsupported CPU/network limits are reported honestly."""

    test_id = "T05-A-INTEGRITY-013"
    spec = _make_spec(
        require_symbol,
        test_id,
        execution_spec_payload,
        mode="test",
        resources=resource_limit_payload(
            cpu_seconds=1,
            memory_bytes=1_048_576,
            network_access="deny",
        ),
    )
    result = _make_runner(
        require_symbol, test_id, probe_script, managed_root
    ).run(spec)
    assert result.resource_enforcement.cpu in {
        "not_enforced",
        "unsupported",
        "future_container_backend",
    }
    assert result.resource_enforcement.memory in {
        "not_enforced",
        "unsupported",
        "future_container_backend",
    }
    assert result.resource_enforcement.network in {
        "not_enforced",
        "unsupported",
        "future_container_backend",
    }
    _assert_not_actual(result)
