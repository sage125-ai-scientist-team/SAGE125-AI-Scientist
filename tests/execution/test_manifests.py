"""Red tests for execution manifests, provenance, and deterministic evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import pytest


_MISSING = object()


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _model_dump(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _error_code(error: Any) -> str | None:
    if error is None:
        return None
    if isinstance(error, dict):
        return error.get("code")
    return getattr(error, "code", None)


def _registered_runner(
    registry_type: Any,
    runner_type: Any,
    *,
    probe_script: Path,
    managed_root: Path,
    entrypoint_class: str = "test",
    dataset_resolver: Callable[[Any], Path] | None = None,
    dependency_version_provider: (
        Callable[[tuple[str, ...]], dict[str, str]] | None
    ) = None,
    git_provenance_provider: Callable[[], dict[str, Any]] | None = None,
) -> Any:
    registry = registry_type()
    registry.register_python(
        "probe",
        probe_script,
        entrypoint_class=entrypoint_class,
        allowed_environment=(),
    )
    return runner_type(
        registry=registry,
        managed_root=managed_root,
        dataset_resolver=dataset_resolver,
        dependency_version_provider=dependency_version_provider,
        git_provenance_provider=git_provenance_provider,
        cleanup=None,
    )


@pytest.mark.parametrize(
    (
        "symbol_name",
        "payload_fixture_name",
        "bytes_fixture_name",
        "sha_fixture_name",
    ),
    [
        pytest.param(
            "DatasetManifest",
            "dataset_payload",
            "dataset_bytes",
            "dataset_sha256",
            id="dataset-real-bytes-sha256",
        ),
        pytest.param(
            "ArtifactManifest",
            "artifact_manifest_payload",
            "artifact_bytes",
            "artifact_sha256",
            id="artifact-real-bytes-sha256",
        ),
    ],
)
def test_T05_A_PROV_001_manifest_checksum_and_size_match_real_fixture_bytes(
    require_symbol: Callable[..., Any],
    request: pytest.FixtureRequest,
    symbol_name: str,
    payload_fixture_name: str,
    bytes_fixture_name: str,
    sha_fixture_name: str,
) -> None:
    """T05-A-PROV-001: manifest integrity fields describe real fixture bytes."""

    model_type = require_symbol(symbol_name)
    payload_factory = request.getfixturevalue(payload_fixture_name)
    fixture_bytes = request.getfixturevalue(bytes_fixture_name)
    fixture_sha256 = request.getfixturevalue(sha_fixture_name)

    manifest = model_type.model_validate(payload_factory())

    assert fixture_sha256 == hashlib.sha256(fixture_bytes).hexdigest()
    assert manifest.sha256 == fixture_sha256
    assert manifest.size_bytes == len(fixture_bytes)


def test_T05_A_PROV_001_actual_rejects_dataset_bytes_mismatch(
    require_symbol: Callable[..., Any],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    source_root: Path,
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-PROV-001: actual mode validates source bytes before spawning."""

    dataset_manifest_type = require_symbol("DatasetManifest")
    artifact_requirement_type = require_symbol("ArtifactRequirement")
    metric_requirement_type = require_symbol("MetricRequirement")
    execution_spec_type = require_symbol("ExecutionSpec")
    registry_type = require_symbol("EntrypointRegistry")
    runner_type = require_symbol("LocalProcessRunner")
    source = source_root / "tampered-dataset.csv"
    source.write_bytes(dataset_bytes + b"tampered")
    dataset = dataset_manifest_type.model_validate(dataset_payload())
    artifact_requirement = artifact_requirement_type.model_validate(
        artifact_requirement_payload()
    )
    metric_requirement = metric_requirement_type.model_validate(
        metric_requirement_payload()
    )
    spec = execution_spec_type.model_validate(
        execution_spec_payload(
            mode="actual",
            datasets=[_model_dump(dataset)],
            required_artifacts=[_model_dump(artifact_requirement)],
            required_metrics=[_model_dump(metric_requirement)],
        )
    )
    runner = _registered_runner(
        registry_type,
        runner_type,
        probe_script=probe_script,
        managed_root=managed_root,
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

    assert _enum_value(result.status) in {"rejected", "failed"}
    assert _error_code(result.error) == "dataset_invalid"
    assert result.process_started is False
    assert result.datasets_validated is False
    assert result.actual_execution is False


def test_T05_A_PROV_002_mutating_workspace_copy_does_not_change_source_dataset(
    require_symbol: Callable[..., Any],
    dataset_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    dataset_sha256: str,
    source_root: Path,
    managed_root: Path,
    probe_script: Path,
    execution_spec_payload: Callable[..., dict[str, Any]],
) -> None:
    """T05-A-PROV-002: runner copies datasets before a process may mutate them."""

    dataset_manifest_type = require_symbol("DatasetManifest")
    execution_spec_type = require_symbol("ExecutionSpec")
    registry_type = require_symbol("EntrypointRegistry")
    runner_type = require_symbol("LocalProcessRunner")

    source = source_root / "dataset-primary.csv"
    source.write_bytes(dataset_bytes)
    source_before = source.read_bytes()
    resolver_calls: list[str] = []

    def resolve_dataset(manifest: Any) -> Path:
        resolver_calls.append(manifest.dataset_id)
        return source

    dataset = dataset_manifest_type.model_validate(dataset_payload())
    runner = _registered_runner(
        registry_type,
        runner_type,
        probe_script=probe_script,
        managed_root=managed_root,
        dataset_resolver=resolve_dataset,
        dependency_version_provider=lambda _names: {},
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    )
    spec = execution_spec_type.model_validate(
        execution_spec_payload(
            argv=[
                "mutate-copy",
                dataset.workspace_relative_path,
                "--append-text",
                "workspace-only mutation",
            ],
            datasets=[_model_dump(dataset)],
            environment={"variables": {}, "dependency_allowlist": []},
        )
    )

    result = runner.run(spec)

    assert _enum_value(result.status) == "succeeded"
    assert result.process_started is True
    assert resolver_calls == [dataset.dataset_id]
    assert source.read_bytes() == source_before == dataset_bytes
    assert hashlib.sha256(source.read_bytes()).hexdigest() == dataset_sha256


def test_T05_A_PROV_003_runner_captures_seed_in_result_and_environment(
    require_symbol: Callable[..., Any],
    fake_seed: int,
    managed_root: Path,
    probe_script: Path,
    execution_spec_payload: Callable[..., dict[str, Any]],
) -> None:
    """T05-A-PROV-003: the requested seed is retained in runner evidence."""

    execution_spec_type = require_symbol("ExecutionSpec")
    registry_type = require_symbol("EntrypointRegistry")
    runner_type = require_symbol("LocalProcessRunner")
    runner = _registered_runner(
        registry_type,
        runner_type,
        probe_script=probe_script,
        managed_root=managed_root,
        dependency_version_provider=lambda _names: {},
        git_provenance_provider=lambda: {
            "commit_sha": "2" * 40,
            "dirty": False,
            "available": True,
        },
    )
    spec = execution_spec_type.model_validate(
        execution_spec_payload(
            seed=fake_seed,
            environment={"variables": {}, "dependency_allowlist": []},
        )
    )

    result = runner.run(spec)

    assert _enum_value(result.status) == "succeeded"
    assert spec.seed == fake_seed
    assert result.seed == fake_seed
    assert result.environment_fingerprint.seed == fake_seed


def test_T05_A_PROV_004_dependency_provider_is_allowlisted_and_stably_sorted(
    require_symbol: Callable[..., Any],
    managed_root: Path,
    probe_script: Path,
    execution_spec_payload: Callable[..., dict[str, Any]],
) -> None:
    """T05-A-PROV-004: only sorted allowlisted dependency versions are recorded."""

    execution_spec_type = require_symbol("ExecutionSpec")
    registry_type = require_symbol("EntrypointRegistry")
    runner_type = require_symbol("LocalProcessRunner")
    provider_calls: list[tuple[str, ...]] = []

    def provide_versions(names: tuple[str, ...]) -> dict[str, str]:
        provider_calls.append(names)
        return {
            "pytest": "9.0.3",
            "not-allowlisted": "999.0",
            "pydantic": "2.12.4",
        }

    runner = _registered_runner(
        registry_type,
        runner_type,
        probe_script=probe_script,
        managed_root=managed_root,
        dependency_version_provider=provide_versions,
        git_provenance_provider=lambda: {
            "commit_sha": "3" * 40,
            "dirty": False,
            "available": True,
        },
    )
    spec = execution_spec_type.model_validate(
        execution_spec_payload(
            environment={
                "variables": {},
                "dependency_allowlist": ["pytest", "pydantic"],
            }
        )
    )

    result = runner.run(spec)
    versions = result.environment_fingerprint.dependency_versions

    assert _enum_value(result.status) == "succeeded"
    assert provider_calls == [("pydantic", "pytest")]
    assert versions == {"pydantic": "2.12.4", "pytest": "9.0.3"}
    assert list(versions) == ["pydantic", "pytest"]


@pytest.mark.parametrize(
    "provider_case",
    [
        pytest.param("raises", id="dependency-provider-raises"),
        pytest.param("missing", id="dependency-provider-missing-package"),
        pytest.param("invalid", id="dependency-provider-invalid-version"),
    ],
)
def test_T05_A_PROV_004_actual_requires_complete_dependency_versions(
    require_symbol: Callable[..., Any],
    managed_root: Path,
    source_root: Path,
    probe_script: Path,
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    provider_case: str,
) -> None:
    """T05-A-PROV-004: dependency provenance failures fail actual closed."""

    dataset_manifest_type = require_symbol("DatasetManifest")
    artifact_requirement_type = require_symbol("ArtifactRequirement")
    metric_requirement_type = require_symbol("MetricRequirement")
    execution_spec_type = require_symbol("ExecutionSpec")
    registry_type = require_symbol("EntrypointRegistry")
    runner_type = require_symbol("LocalProcessRunner")
    source = source_root / "dataset-primary.csv"
    source.write_bytes(dataset_bytes)
    dataset = dataset_manifest_type.model_validate(dataset_payload())
    artifact_requirement = artifact_requirement_type.model_validate(
        artifact_requirement_payload()
    )
    metric_requirement = metric_requirement_type.model_validate(
        metric_requirement_payload()
    )

    def provide_versions(_names: tuple[str, ...]) -> dict[str, str]:
        if provider_case == "raises":
            raise LookupError("controlled dependency lookup failure")
        if provider_case == "missing":
            return {"pydantic": "2.12.4"}
        return {"pydantic": "2.12.4", "pytest": ""}

    runner = _registered_runner(
        registry_type,
        runner_type,
        probe_script=probe_script,
        managed_root=managed_root,
        entrypoint_class="scientific",
        dataset_resolver=lambda _manifest: source,
        dependency_version_provider=provide_versions,
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    )
    spec = execution_spec_type.model_validate(
        execution_spec_payload(
            mode="actual",
            datasets=[_model_dump(dataset)],
            required_artifacts=[_model_dump(artifact_requirement)],
            required_metrics=[_model_dump(metric_requirement)],
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
            environment={
                "variables": {},
                "dependency_allowlist": ["pydantic", "pytest"],
            },
        )
    )

    result = runner.run(spec)

    assert _enum_value(result.status) == "failed"
    assert _error_code(result.error) == "dependency_missing"
    assert result.provenance_complete is False
    assert result.actual_execution is False


@pytest.mark.parametrize(
    ("provenance", "expected_status", "expected_actual", "expected_error"),
    [
        pytest.param(
            {
                "commit_sha": "a" * 40,
                "dirty": False,
                "available": True,
            },
            "succeeded",
            True,
            None,
            id="git-clean-valid-sha",
        ),
        pytest.param(
            {
                "commit_sha": "b" * 40,
                "dirty": True,
                "available": True,
            },
            "failed",
            False,
            "provenance_incomplete",
            id="git-dirty",
        ),
        pytest.param(
            {
                "commit_sha": None,
                "dirty": False,
                "available": False,
            },
            "failed",
            False,
            "provenance_incomplete",
            id="git-unavailable",
        ),
        pytest.param(
            {
                "commit_sha": "not-a-valid-git-sha",
                "dirty": False,
                "available": True,
            },
            "failed",
            False,
            "provenance_incomplete",
            id="git-invalid-sha",
        ),
        pytest.param(
            {
                "commit_sha": "c" * 40,
                "available": True,
            },
            "failed",
            False,
            "provenance_incomplete",
            id="git-missing-dirty",
        ),
        pytest.param(
            {
                "commit_sha": "d" * 40,
                "dirty": "false",
                "available": True,
            },
            "failed",
            False,
            "provenance_incomplete",
            id="git-nonstrict-dirty",
        ),
        pytest.param(
            "raises",
            "failed",
            False,
            "provenance_incomplete",
            id="git-provider-raises",
        ),
    ],
)
def test_T05_A_PROV_005_actual_execution_requires_clean_valid_git_provenance(
    require_symbol: Callable[..., Any],
    managed_root: Path,
    source_root: Path,
    probe_script: Path,
    execution_spec_payload: Callable[..., dict[str, Any]],
    dataset_payload: Callable[..., dict[str, Any]],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    dataset_bytes: bytes,
    provenance: dict[str, Any] | str,
    expected_status: str,
    expected_actual: bool,
    expected_error: str | None,
) -> None:
    """T05-A-PROV-005: actual evidence requires available, clean Git provenance."""

    dataset_manifest_type = require_symbol("DatasetManifest")
    artifact_requirement_type = require_symbol("ArtifactRequirement")
    metric_requirement_type = require_symbol("MetricRequirement")
    execution_spec_type = require_symbol("ExecutionSpec")
    registry_type = require_symbol("EntrypointRegistry")
    runner_type = require_symbol("LocalProcessRunner")
    source = source_root / "dataset-primary.csv"
    source.write_bytes(dataset_bytes)
    dataset = dataset_manifest_type.model_validate(dataset_payload())
    artifact_requirement = artifact_requirement_type.model_validate(
        artifact_requirement_payload()
    )
    metric_requirement = metric_requirement_type.model_validate(
        metric_requirement_payload()
    )

    def provide_git() -> dict[str, Any]:
        if provenance == "raises":
            raise LookupError("controlled Git provenance failure")
        return dict(provenance)

    runner = _registered_runner(
        registry_type,
        runner_type,
        probe_script=probe_script,
        managed_root=managed_root,
        entrypoint_class="scientific",
        dataset_resolver=lambda _manifest: source,
        dependency_version_provider=lambda _names: {},
        git_provenance_provider=provide_git,
    )
    spec = execution_spec_type.model_validate(
        execution_spec_payload(
            mode="actual",
            datasets=[_model_dump(dataset)],
            required_artifacts=[_model_dump(artifact_requirement)],
            required_metrics=[_model_dump(metric_requirement)],
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
            environment={"variables": {}, "dependency_allowlist": []},
        )
    )

    result = runner.run(spec)

    assert _enum_value(result.status) == expected_status
    assert result.actual_execution is expected_actual
    assert result.runner_verified is expected_actual
    assert _error_code(result.error) == expected_error
    if expected_actual:
        assert isinstance(provenance, dict)
        fingerprint = result.environment_fingerprint
        assert fingerprint.git_sha == provenance["commit_sha"]
        assert fingerprint.git_dirty is False
        assert fingerprint.git_available is True
        assert result.provenance_complete is True
    else:
        assert result.provenance_complete is False


def test_T05_A_PROV_006_execution_result_sorts_artifacts_by_artifact_id(
    require_symbol: Callable[..., Any],
    artifact_manifest_payload: Callable[..., dict[str, Any]],
    environment_fingerprint_payload: Callable[..., dict[str, Any]],
    execution_result_payload: Callable[..., dict[str, Any]],
) -> None:
    """T05-A-PROV-006: artifact order is deterministic in public results."""

    artifact_manifest_type = require_symbol("ArtifactManifest")
    environment_fingerprint_type = require_symbol("EnvironmentFingerprint")
    execution_result_type = require_symbol("ExecutionResult")
    artifact_zeta = artifact_manifest_type.model_validate(
        artifact_manifest_payload(
            artifact_id="artifact-zeta",
            relative_path="artifacts/zeta.json",
        )
    )
    artifact_alpha = artifact_manifest_type.model_validate(
        artifact_manifest_payload(
            artifact_id="artifact-alpha",
            relative_path="artifacts/alpha.json",
        )
    )
    fingerprint = environment_fingerprint_type.model_validate(
        environment_fingerprint_payload()
    )

    result = execution_result_type.model_validate(
        execution_result_payload(
            status="succeeded",
            process_started=True,
            exit_code=0,
            artifacts=[
                _model_dump(artifact_zeta),
                _model_dump(artifact_alpha),
            ],
            cleanup_status="succeeded",
            environment_fingerprint=_model_dump(fingerprint),
        )
    )

    dumped = _model_dump(result)
    assert [item["artifact_id"] for item in dumped["artifacts"]] == [
        "artifact-alpha",
        "artifact-zeta",
    ]
    for artifact in dumped["artifacts"]:
        assert artifact["relative_path"].startswith("artifacts/")
        assert artifact["kind"] == "metrics"
        assert artifact["media_type"] == "application/json"
        assert len(artifact["sha256"]) == 64
        assert artifact["size_bytes"] > 0


@pytest.mark.parametrize(
    "source_uri",
    [
        pytest.param(_MISSING, id="source-absent"),
        pytest.param(None, id="source-null"),
        pytest.param("", id="source-empty"),
        pytest.param("   ", id="source-whitespace"),
    ],
)
def test_T05_A_MANIFEST_001_dataset_requires_nonblank_source_uri(
    require_symbol: Callable[..., Any],
    dataset_payload: Callable[..., dict[str, Any]],
    execution_spec_payload: Callable[..., dict[str, Any]],
    source_uri: Any,
) -> None:
    """T05-A-MANIFEST-001: datasets require an explicit nonblank source URI."""

    dataset_manifest_type = require_symbol("DatasetManifest")
    execution_spec_type = require_symbol("ExecutionSpec")
    payload = dataset_payload()
    if source_uri is _MISSING:
        payload.pop("source_uri")
    else:
        payload["source_uri"] = source_uri

    with pytest.raises(ValueError):
        dataset_manifest_type.model_validate(payload)
    with pytest.raises(ValueError):
        execution_spec_type.model_validate(
            execution_spec_payload(mode="actual", datasets=[payload])
        )


@pytest.mark.parametrize(
    "license_value",
    [
        pytest.param(_MISSING, id="license-absent"),
        pytest.param(None, id="license-null"),
        pytest.param("", id="license-empty"),
        pytest.param("   ", id="license-whitespace"),
    ],
)
def test_T05_A_MANIFEST_002_dataset_requires_nonblank_license(
    require_symbol: Callable[..., Any],
    dataset_payload: Callable[..., dict[str, Any]],
    execution_spec_payload: Callable[..., dict[str, Any]],
    license_value: Any,
) -> None:
    """T05-A-MANIFEST-002: datasets require explicit license evidence."""

    dataset_manifest_type = require_symbol("DatasetManifest")
    execution_spec_type = require_symbol("ExecutionSpec")
    payload = dataset_payload()
    if license_value is _MISSING:
        payload.pop("license")
    else:
        payload["license"] = license_value

    with pytest.raises(ValueError):
        dataset_manifest_type.model_validate(payload)
    with pytest.raises(ValueError):
        execution_spec_type.model_validate(
            execution_spec_payload(mode="actual", datasets=[payload])
        )


@pytest.mark.parametrize(
    "version",
    [
        pytest.param(_MISSING, id="version-absent"),
        pytest.param(None, id="version-null"),
        pytest.param("", id="version-empty"),
        pytest.param("   ", id="version-whitespace"),
    ],
)
def test_T05_A_MANIFEST_003_dataset_requires_nonblank_version(
    require_symbol: Callable[..., Any],
    dataset_payload: Callable[..., dict[str, Any]],
    execution_spec_payload: Callable[..., dict[str, Any]],
    version: Any,
) -> None:
    """T05-A-MANIFEST-003: datasets require an explicit version identifier."""

    dataset_manifest_type = require_symbol("DatasetManifest")
    execution_spec_type = require_symbol("ExecutionSpec")
    payload = dataset_payload()
    if version is _MISSING:
        payload.pop("version")
    else:
        payload["version"] = version

    with pytest.raises(ValueError):
        dataset_manifest_type.model_validate(payload)
    with pytest.raises(ValueError):
        execution_spec_type.model_validate(
            execution_spec_payload(mode="actual", datasets=[payload])
        )


@pytest.mark.parametrize(
    "sha256",
    [
        pytest.param(_MISSING, id="sha-absent"),
        pytest.param(None, id="sha-null"),
        pytest.param("f" * 63, id="sha-too-short"),
        pytest.param("f" * 65, id="sha-too-long"),
        pytest.param("A" * 64, id="sha-uppercase"),
        pytest.param("g" * 64, id="sha-nonhex"),
    ],
)
def test_T05_A_MANIFEST_004_dataset_requires_canonical_sha256(
    require_symbol: Callable[..., Any],
    dataset_payload: Callable[..., dict[str, Any]],
    execution_spec_payload: Callable[..., dict[str, Any]],
    sha256: Any,
) -> None:
    """T05-A-MANIFEST-004: dataset SHA-256 is exactly 64 lowercase hex."""

    dataset_manifest_type = require_symbol("DatasetManifest")
    execution_spec_type = require_symbol("ExecutionSpec")
    payload = dataset_payload()
    if sha256 is _MISSING:
        payload.pop("sha256")
    else:
        payload["sha256"] = sha256

    with pytest.raises(ValueError):
        dataset_manifest_type.model_validate(payload)
    with pytest.raises(ValueError):
        execution_spec_type.model_validate(
            execution_spec_payload(mode="actual", datasets=[payload])
        )


@pytest.mark.parametrize(
    "source_uri",
    [
        pytest.param(
            "https://alice@example.test/data.csv",
            id="uri-userinfo-username",
        ),
        pytest.param(
            "https://alice:secret@example.test/data.csv",
            id="uri-userinfo-password",
        ),
        pytest.param(
            "s3://access-key:secret@example-bucket/data.csv",
            id="uri-userinfo-object-store",
        ),
    ],
)
def test_T05_A_MANIFEST_005_dataset_uri_rejects_embedded_credentials(
    require_symbol: Callable[..., Any],
    dataset_payload: Callable[..., dict[str, Any]],
    source_uri: str,
) -> None:
    """T05-A-MANIFEST-005: source URIs cannot carry userinfo credentials."""

    dataset_manifest_type = require_symbol("DatasetManifest")

    with pytest.raises(ValueError):
        dataset_manifest_type.model_validate(
            dataset_payload(source_uri=source_uri)
        )


@pytest.mark.parametrize(
    "source_uri",
    [
        pytest.param(
            "https://example.test/data.csv?token=secret",
            id="query-token",
        ),
        pytest.param(
            "https://example.test/data.csv?api_key=secret",
            id="query-api-key",
        ),
        pytest.param(
            "https://example.test/data.csv?sig=secret",
            id="query-signature-short",
        ),
        pytest.param(
            "https://example.test/data.csv?X-Amz-Signature=deadbeef",
            id="query-aws-signature",
        ),
        pytest.param(
            "https://example.test/data.csv?password=secret",
            id="query-password",
        ),
    ],
)
def test_T05_A_MANIFEST_006_dataset_uri_rejects_secret_query_parameters(
    require_symbol: Callable[..., Any],
    dataset_payload: Callable[..., dict[str, Any]],
    source_uri: str,
) -> None:
    """T05-A-MANIFEST-006: source URI query strings cannot contain secrets."""

    dataset_manifest_type = require_symbol("DatasetManifest")

    with pytest.raises(ValueError):
        dataset_manifest_type.model_validate(
            dataset_payload(source_uri=source_uri)
        )


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"sha256": "f" * 63}, id="artifact-sha-too-short"),
        pytest.param({"sha256": "A" * 64}, id="artifact-sha-uppercase"),
        pytest.param({"sha256": "g" * 64}, id="artifact-sha-nonhex"),
        pytest.param({"size_bytes": -1}, id="artifact-negative-size"),
        pytest.param(
            {"validation_status": "definitely-not-valid"},
            id="artifact-invalid-validation-status",
        ),
    ],
)
def test_T05_A_MANIFEST_007_artifact_manifest_rejects_invalid_integrity_data(
    require_symbol: Callable[..., Any],
    artifact_manifest_payload: Callable[..., dict[str, Any]],
    overrides: dict[str, Any],
) -> None:
    """T05-A-MANIFEST-007: artifact integrity metadata is strict."""

    artifact_manifest_type = require_symbol("ArtifactManifest")

    with pytest.raises(ValueError):
        artifact_manifest_type.model_validate(
            artifact_manifest_payload(**overrides)
        )


@pytest.mark.parametrize(
    ("missing_field", "representation"),
    [
        pytest.param("sha256", "absent", id="valid-artifact-absent-sha256"),
        pytest.param("sha256", "null", id="valid-artifact-null-sha256"),
        pytest.param("size_bytes", "absent", id="valid-artifact-absent-size"),
        pytest.param("size_bytes", "null", id="valid-artifact-null-size"),
        pytest.param(
            "collected_at",
            "absent",
            id="valid-artifact-absent-collected-at",
        ),
        pytest.param(
            "collected_at",
            "null",
            id="valid-artifact-null-collected-at",
        ),
    ],
)
def test_T05_A_MANIFEST_007_valid_artifact_requires_complete_evidence(
    require_symbol: Callable[..., Any],
    artifact_manifest_payload: Callable[..., dict[str, Any]],
    missing_field: str,
    representation: str,
) -> None:
    """T05-A-MANIFEST-007: valid artifacts require checksum, size, and time."""

    artifact_manifest_type = require_symbol("ArtifactManifest")
    payload = artifact_manifest_payload()
    if representation == "absent":
        payload.pop(missing_field)
    else:
        payload[missing_field] = None
    with pytest.raises(ValueError):
        artifact_manifest_type.model_validate(payload)


@pytest.mark.parametrize(
    ("forged_field", "forged_value"),
    [
        pytest.param("sha256", "0" * 64, id="missing-artifact-fake-checksum"),
        pytest.param("size_bytes", 0, id="missing-artifact-fake-size"),
    ],
)
def test_T05_A_MANIFEST_008_missing_artifact_cannot_carry_fake_checksum(
    require_symbol: Callable[..., Any],
    artifact_manifest_payload: Callable[..., dict[str, Any]],
    forged_field: str,
    forged_value: Any,
) -> None:
    """T05-A-MANIFEST-008: missing artifacts never carry invented integrity."""

    artifact_manifest_type = require_symbol("ArtifactManifest")
    missing = artifact_manifest_type.model_validate(
        artifact_manifest_payload(
            validation_status="missing",
            sha256=None,
            size_bytes=None,
            collected_at=None,
        )
    )
    assert missing.sha256 is None
    assert missing.size_bytes is None
    forged_payload = artifact_manifest_payload(
        validation_status="missing",
        sha256=None,
        size_bytes=None,
        collected_at=None,
    )
    forged_payload[forged_field] = forged_value
    with pytest.raises(ValueError):
        artifact_manifest_type.model_validate(forged_payload)


def test_T05_A_MANIFEST_009_metric_must_reference_a_collected_artifact(
    require_symbol: Callable[..., Any],
    artifact_requirement_payload: Callable[..., dict[str, Any]],
    metric_requirement_payload: Callable[..., dict[str, Any]],
    execution_spec_payload: Callable[..., dict[str, Any]],
) -> None:
    """T05-A-MANIFEST-009: an expected metric names a declared artifact."""

    artifact_requirement_type = require_symbol("ArtifactRequirement")
    metric_requirement_type = require_symbol("MetricRequirement")
    execution_spec_type = require_symbol("ExecutionSpec")
    artifact = artifact_requirement_type.model_validate(
        artifact_requirement_payload(artifact_id="declared-artifact")
    )
    metric = metric_requirement_type.model_validate(
        metric_requirement_payload(artifact_id="missing-artifact")
    )

    with pytest.raises(ValueError):
        execution_spec_type.model_validate(
            execution_spec_payload(
                required_artifacts=[_model_dump(artifact)],
                required_metrics=[_model_dump(metric)],
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(float("nan"), id="not-a-number"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
    ],
)
def test_T05_A_MANIFEST_010_metric_rejects_infinity(
    require_symbol: Callable[..., Any],
    metric_record_payload: Callable[..., dict[str, Any]],
    value: float,
) -> None:
    """T05-A-MANIFEST-010: metric values must be finite numbers."""

    metric_record_type = require_symbol("MetricRecord")

    with pytest.raises(ValueError):
        metric_record_type.model_validate(metric_record_payload(value=value))
