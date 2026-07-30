"""Red tests for T05 Wave A path and execution-boundary security."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _validate(model_type: type[Any], payload: Mapping[str, Any]) -> Any:
    return model_type.model_validate(dict(payload))


def _assert_validation_error(model_type: type[Any], payload: Mapping[str, Any]) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _validate(model_type, payload)


def _runner(
    require_symbol: Any,
    test_id: str,
    *,
    probe_script: Path,
    managed_root: Path,
    dataset_resolver: Any = None,
) -> Any:
    registry_type = require_symbol(
        "app.execution",
        "EntrypointRegistry",
        test_id,
    )
    runner_type = require_symbol(
        "app.execution",
        "LocalProcessRunner",
        test_id,
    )
    registry = registry_type()
    registry.register_python(
        "probe",
        probe_script,
        entrypoint_class="test",
        allowed_environment=(),
    )
    return runner_type(
        registry=registry,
        managed_root=managed_root,
        dataset_resolver=dataset_resolver,
        dependency_version_provider=None,
        git_provenance_provider=None,
        cleanup=None,
    )


def _assert_result_failure(
    result: Any,
    *,
    status: str,
    code: str,
    process_started: bool,
) -> None:
    assert _enum_value(result.status) == status
    assert result.error is not None
    assert _enum_value(result.error.code) == code
    assert result.process_started is process_started
    assert result.actual_execution is False


def _leaf_strings(value: Any) -> Iterable[str]:
    if hasattr(value, "model_dump"):
        yield from _leaf_strings(value.model_dump(mode="python"))
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _leaf_strings(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _leaf_strings(item)
    elif isinstance(value, str):
        yield value


@pytest.mark.parametrize(
    "unsafe_path",
    [
        pytest.param("/tmp/a", id="posix"),
        pytest.param(r"\absolute", id="windows-rooted"),
        pytest.param(r"C:\absolute", id="windows-c-drive"),
        pytest.param("D:/absolute", id="windows-d-drive"),
    ],
)
def test_t05_a_path_001_rejects_cross_platform_absolute_artifact_paths(
    require_symbol: Any,
    artifact_requirement_payload: Any,
    unsafe_path: str,
) -> None:
    """T05-A-PATH-001: absolute paths are invalid on every host platform."""

    artifact_requirement = require_symbol(
        "app.contracts.execution",
        "ArtifactRequirement",
        "T05-A-PATH-001",
    )
    _assert_validation_error(
        artifact_requirement,
        artifact_requirement_payload(relative_path=unsafe_path),
    )


@pytest.mark.parametrize(
    "unsafe_path",
    [
        pytest.param("../escape.json", id="parent"),
        pytest.param("artifacts/../../escape.json", id="nested-parent"),
        pytest.param(r"artifacts\..\escape.json", id="windows-parent"),
        pytest.param(r"artifacts/..\../escape.json", id="mixed-separators"),
        pytest.param("artifacts/%2e%2e/escape.json", id="encoded-dots"),
        pytest.param("artifacts/%2E%2E%2Fescape.json", id="encoded-separator"),
        pytest.param("artifacts/%252e%252e%252fescape.json", id="double-encoded"),
    ],
)
def test_t05_a_path_002_rejects_plain_and_encoded_traversal(
    require_symbol: Any,
    artifact_requirement_payload: Any,
    unsafe_path: str,
) -> None:
    """T05-A-PATH-002: traversal is rejected before filesystem access."""

    artifact_requirement = require_symbol(
        "app.contracts.execution",
        "ArtifactRequirement",
        "T05-A-PATH-002",
    )
    _assert_validation_error(
        artifact_requirement,
        artifact_requirement_payload(relative_path=unsafe_path),
    )


def test_t05_a_path_003_runner_rejects_model_constructed_outside_escape(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    probe_script: Path,
    managed_root: Path,
    outside_sentinel: Path,
) -> None:
    """T05-A-PATH-003: the runner rechecks a caller-bypassed artifact path."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-PATH-003",
    )
    artifact_requirement = require_symbol(
        "app.contracts.execution",
        "ArtifactRequirement",
        "T05-A-PATH-003",
    )
    valid_spec = _validate(execution_spec, execution_spec_payload())
    forged_requirement = artifact_requirement.model_construct(
        **artifact_requirement_payload(
            relative_path="../../outside/sentinel.txt",
            expected_sha256=None,
        )
    )
    forged_spec = valid_spec.model_copy(
        update={"required_artifacts": [forged_requirement]}
    )
    sentinel_before = outside_sentinel.read_bytes()

    result = _runner(
        require_symbol,
        "T05-A-PATH-003",
        probe_script=probe_script,
        managed_root=managed_root,
    ).run(forged_spec)

    _assert_result_failure(
        result,
        status="rejected",
        code="path_escape",
        process_started=False,
    )
    assert outside_sentinel.read_bytes() == sentinel_before


def test_t05_a_path_004_rejects_artifact_symlink(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    probe_script: Path,
    managed_root: Path,
    can_create_symlink: Any,
) -> None:
    """T05-A-PATH-004: a produced symlink cannot become an artifact."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-PATH-004",
    )
    if not can_create_symlink.supported:
        pytest.skip(
            "T05-A-PATH-004: symlink capability probe failed: "
            f"{can_create_symlink.reason}"
        )
    outside_target = managed_root / "outside-probe-target"
    outside_target.write_bytes(b"outside-target-unchanged")
    outside_before = outside_target.read_bytes()

    spec = _validate(
        execution_spec,
        execution_spec_payload(
            argv=[
                "artifact",
                "--path",
                "artifacts/metrics.json",
                "--kind",
                "directory-symlink",
            ],
            required_artifacts=[
                artifact_requirement_payload(expected_sha256=None)
            ],
        ),
    )

    result = _runner(
        require_symbol,
        "T05-A-PATH-004",
        probe_script=probe_script,
        managed_root=managed_root,
    ).run(spec)

    _assert_result_failure(
        result,
        status="failed",
        code="symlink_escape",
        process_started=True,
    )
    assert outside_target.read_bytes() == outside_before


def test_t05_a_path_004_rejects_artifact_junction(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    probe_script: Path,
    managed_root: Path,
    request: pytest.FixtureRequest,
) -> None:
    """T05-A-PATH-004: a Windows junction cannot become an artifact."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-PATH-004",
    )
    capability = request.getfixturevalue("can_create_junction")
    if not capability.supported:
        pytest.skip(
            "T05-A-PATH-004: junction capability probe failed: "
            f"{capability.reason}"
        )
    outside_target = managed_root / "outside-probe-target"
    outside_target.mkdir()
    outside_sentinel = outside_target / "sentinel.bin"
    outside_sentinel.write_bytes(b"outside-junction-target-unchanged")
    outside_before = outside_sentinel.read_bytes()

    spec = _validate(
        execution_spec,
        execution_spec_payload(
            argv=[
                "artifact",
                "--path",
                "artifacts/metrics.json",
                "--kind",
                "junction",
            ],
            required_artifacts=[
                artifact_requirement_payload(expected_sha256=None)
            ],
        ),
    )

    result = _runner(
        require_symbol,
        "T05-A-PATH-004",
        probe_script=probe_script,
        managed_root=managed_root,
    ).run(spec)

    _assert_result_failure(
        result,
        status="failed",
        code="symlink_escape",
        process_started=True,
    )
    assert outside_sentinel.read_bytes() == outside_before


@pytest.mark.parametrize(
    "unsafe_path",
    [
        pytest.param(r"C:relative\metrics.json", id="drive-relative"),
        pytest.param(r"C:\outside\metrics.json", id="drive-absolute"),
        pytest.param(r"\rooted\metrics.json", id="root-relative"),
        pytest.param(r"\\server\share\metrics.json", id="unc"),
        pytest.param(r"\\?\C:\outside\metrics.json", id="device-namespace"),
        pytest.param(r"\Device\HarddiskVolume1\metrics.json", id="nt-device"),
        pytest.param(r"artifacts\metrics.json:secret", id="alternate-stream"),
        pytest.param("artifacts/metrics.json:secret", id="posix-alternate-stream"),
        pytest.param("artifacts/NUL:stream", id="posix-reserved-nul-stream"),
        pytest.param(r"c:\MiXeD\metrics.json", id="mixed-case-drive"),
        pytest.param(r"artifacts\metrics.json. ", id="trailing-dot-space"),
        pytest.param(r"artifacts\NUL", id="reserved-nul"),
        pytest.param(r"artifacts\CON.txt", id="reserved-con"),
        pytest.param(r"artifacts\COM1.json", id="reserved-com1"),
        pytest.param("artifacts/NUL", id="posix-reserved-nul"),
        pytest.param("artifacts/CON.txt", id="posix-reserved-con"),
        pytest.param("artifacts/COM1.json", id="posix-reserved-com1"),
    ],
)
def test_t05_a_path_005_rejects_pure_windows_dangerous_paths_on_all_hosts(
    require_symbol: Any,
    artifact_requirement_payload: Any,
    unsafe_path: str,
) -> None:
    """T05-A-PATH-005: Windows path hazards are rejected even on POSIX."""

    windows_path = PureWindowsPath(unsafe_path)
    assert str(windows_path)
    artifact_requirement = require_symbol(
        "app.contracts.execution",
        "ArtifactRequirement",
        "T05-A-PATH-005",
    )
    _assert_validation_error(
        artifact_requirement,
        artifact_requirement_payload(relative_path=unsafe_path),
    )


def test_t05_a_path_006_concurrent_runs_have_isolated_workspaces(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-PATH-006: concurrent executions cannot share artifact state."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-PATH-006",
    )
    runner = _runner(
        require_symbol,
        "T05-A-PATH-006",
        probe_script=probe_script,
        managed_root=managed_root,
    )

    content = "same-spec-isolated-output"
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    spec = _validate(
        execution_spec,
        execution_spec_payload(
            spec_id="same-concurrent-spec",
            argv=[
                "artifact",
                "--path",
                "artifacts/result.txt",
                "--content",
                content,
            ],
            required_artifacts=[
                artifact_requirement_payload(
                    artifact_id="same-artifact",
                    relative_path="artifacts/result.txt",
                    kind="raw",
                    media_type="text/plain",
                    expected_sha256=expected_hash,
                )
            ],
            cleanup_policy="preserve",
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(runner.run, spec) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]

    assert all(_enum_value(result.status) == "succeeded" for result in results)
    assert len({result.execution_id for result in results}) == 2
    assert len({result.workspace_uri for result in results}) == 2
    for result in results:
        workspace_uri = str(result.workspace_uri)
        normalized_uri = workspace_uri.replace("\\", "/").casefold()
        assert workspace_uri
        assert not normalized_uri.startswith("file:")
        for private_root in (managed_root.parent.resolve(), managed_root.resolve()):
            assert private_root.as_posix().casefold() not in normalized_uri
    assert all(
        len(result.artifacts) == 1
        and result.artifacts[0].artifact_id == "same-artifact"
        and result.artifacts[0].sha256 == expected_hash
        for result in results
    )
    preserved_outputs = sorted(managed_root.rglob("artifacts/result.txt"))
    assert len(preserved_outputs) == 2
    assert len({path.parent.parent.resolve() for path in preserved_outputs}) == 2
    assert all(path.read_text(encoding="utf-8") == content for path in preserved_outputs)


def test_t05_a_security_001_rejects_symlinked_dataset_source(
    require_symbol: Any,
    execution_spec_payload: Any,
    dataset_payload: Any,
    dataset_bytes: bytes,
    probe_script: Path,
    managed_root: Path,
    source_root: Path,
    outside_root: Path,
    outside_sentinel: Path,
    can_create_symlink: Any,
) -> None:
    """T05-A-SECURITY-001: source symlinks are rejected before copying."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-SECURITY-001",
    )
    if not can_create_symlink.supported:
        pytest.skip(
            "T05-A-SECURITY-001: symlink capability probe failed: "
            f"{can_create_symlink.reason}"
        )

    outside_dataset = outside_root / "dataset.csv"
    outside_dataset.write_bytes(dataset_bytes)
    linked_source = source_root / "dataset.csv"
    linked_source.symlink_to(outside_dataset)
    dataset_before = outside_dataset.read_bytes()
    sentinel_before = outside_sentinel.read_bytes()
    spec = _validate(
        execution_spec,
        execution_spec_payload(
            datasets=[
                dataset_payload(
                    workspace_relative_path="datasets/dataset-primary.csv"
                )
            ]
        ),
    )

    result = _runner(
        require_symbol,
        "T05-A-SECURITY-001",
        probe_script=probe_script,
        managed_root=managed_root,
        dataset_resolver=lambda _manifest: linked_source,
    ).run(spec)

    _assert_result_failure(
        result,
        status="rejected",
        code="symlink_escape",
        process_started=False,
    )
    assert outside_dataset.read_bytes() == dataset_before
    assert outside_sentinel.read_bytes() == sentinel_before


def test_t05_a_security_002_rejects_nonregular_artifact(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-SECURITY-002: an artifact must be a regular file."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-SECURITY-002",
    )
    spec = _validate(
        execution_spec,
        execution_spec_payload(
            argv=[
                "artifact",
                "--path",
                "artifacts/metrics.json",
                "--kind",
                "directory",
            ],
            required_artifacts=[
                artifact_requirement_payload(expected_sha256=None)
            ],
        ),
    )

    result = _runner(
        require_symbol,
        "T05-A-SECURITY-002",
        probe_script=probe_script,
        managed_root=managed_root,
    ).run(spec)

    _assert_result_failure(
        result,
        status="failed",
        code="artifact_invalid",
        process_started=True,
    )


@pytest.mark.parametrize(
    ("artifact_limit", "run_limit"),
    [
        pytest.param(8, 128, id="per-artifact-limit"),
        pytest.param(128, 32, id="run-artifact-limit"),
    ],
)
def test_t05_a_security_003_rejects_oversized_artifact(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    resource_limit_payload: Any,
    probe_script: Path,
    managed_root: Path,
    artifact_limit: int,
    run_limit: int,
) -> None:
    """T05-A-SECURITY-003: both per-artifact and run byte caps are enforced."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-SECURITY-003",
    )
    spec = _validate(
        execution_spec,
        execution_spec_payload(
            argv=[
                "artifact",
                "--path",
                "artifacts/metrics.json",
                "--content",
                "0123456789abcdef",
                "--repeat",
                "4",
            ],
            required_artifacts=[
                artifact_requirement_payload(
                    expected_sha256=None,
                    max_bytes=artifact_limit,
                )
            ],
            resources=resource_limit_payload(max_artifact_bytes=run_limit),
        ),
    )

    result = _runner(
        require_symbol,
        "T05-A-SECURITY-003",
        probe_script=probe_script,
        managed_root=managed_root,
    ).run(spec)

    _assert_result_failure(
        result,
        status="failed",
        code="artifact_invalid",
        process_started=True,
    )


def test_t05_a_security_004_rejects_nul_in_artifact_path(
    require_symbol: Any,
    artifact_requirement_payload: Any,
) -> None:
    """T05-A-SECURITY-004: embedded NUL is rejected by the contract."""

    artifact_requirement = require_symbol(
        "app.contracts.execution",
        "ArtifactRequirement",
        "T05-A-SECURITY-004",
    )
    _assert_validation_error(
        artifact_requirement,
        artifact_requirement_payload(
            relative_path="artifacts/\x00metrics.json"
        ),
    )


def test_t05_a_security_005_rejects_empty_artifact_path(
    require_symbol: Any,
    artifact_requirement_payload: Any,
) -> None:
    """T05-A-SECURITY-005: an empty artifact path is invalid."""

    artifact_requirement = require_symbol(
        "app.contracts.execution",
        "ArtifactRequirement",
        "T05-A-SECURITY-005",
    )
    _assert_validation_error(
        artifact_requirement,
        artifact_requirement_payload(relative_path=""),
    )


def test_t05_a_security_006_rejects_duplicate_artifact_ids(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
) -> None:
    """T05-A-SECURITY-006: artifact identifiers are unique within a spec."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-SECURITY-006",
    )
    _assert_validation_error(
        execution_spec,
        execution_spec_payload(
            required_artifacts=[
                artifact_requirement_payload(
                    artifact_id="duplicate-artifact",
                    relative_path="artifacts/first.json",
                ),
                artifact_requirement_payload(
                    artifact_id="duplicate-artifact",
                    relative_path="artifacts/second.json",
                ),
            ]
        ),
    )


def test_t05_a_security_007_rejects_duplicate_metric_names(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    metric_requirement_payload: Any,
) -> None:
    """T05-A-SECURITY-007: metric names are unique within a spec."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-SECURITY-007",
    )
    _assert_validation_error(
        execution_spec,
        execution_spec_payload(
            required_artifacts=[artifact_requirement_payload()],
            required_metrics=[
                metric_requirement_payload(name="duplicate-score"),
                metric_requirement_payload(
                    name="duplicate-score",
                    unit="percent",
                ),
            ],
        ),
    )


def test_t05_a_security_008_rejects_metric_with_unknown_artifact(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    metric_requirement_payload: Any,
) -> None:
    """T05-A-SECURITY-008: every metric must name a declared artifact."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-SECURITY-008",
    )
    _assert_validation_error(
        execution_spec,
        execution_spec_payload(
            required_artifacts=[artifact_requirement_payload()],
            required_metrics=[
                metric_requirement_payload(artifact_id="missing-artifact")
            ],
        ),
    )


def test_t05_a_security_009_error_does_not_disclose_tmp_absolute_path(
    require_symbol: Any,
    execution_spec_payload: Any,
    artifact_requirement_payload: Any,
    probe_script: Path,
    managed_root: Path,
) -> None:
    """T05-A-SECURITY-009: structured failures do not leak host temp paths."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-SECURITY-009",
    )
    spec = _validate(
        execution_spec,
        execution_spec_payload(
            argv=["noop"],
            required_artifacts=[
                artifact_requirement_payload(expected_sha256=None)
            ],
        ),
    )

    result = _runner(
        require_symbol,
        "T05-A-SECURITY-009",
        probe_script=probe_script,
        managed_root=managed_root,
    ).run(spec)

    _assert_result_failure(
        result,
        status="failed",
        code="artifact_missing",
        process_started=True,
    )
    serialized_text = (
        "\n".join(_leaf_strings(result))
        .replace("\\", "/")
        .casefold()
    )
    for private_root in (managed_root.parent.resolve(), managed_root.resolve()):
        normalized = private_root.as_posix().casefold()
        assert normalized not in serialized_text
        assert private_root.as_uri().casefold() not in serialized_text
    assert not str(result.workspace_uri).casefold().startswith("file:")


def test_t05_a_security_010_caller_cannot_forge_limit_enforcement(
    require_symbol: Any,
    execution_spec_payload: Any,
    resource_limit_payload: Any,
    resource_enforcement_payload: Any,
) -> None:
    """T05-A-SECURITY-010: requested limits cannot claim runner enforcement."""

    execution_spec = require_symbol(
        "app.contracts.execution",
        "ExecutionSpec",
        "T05-A-SECURITY-010",
    )
    resource_limit_request = require_symbol(
        "app.contracts.execution",
        "ResourceLimitRequest",
        "T05-A-SECURITY-010",
    )
    require_symbol(
        "app.contracts.execution",
        "ResourceLimitEnforcement",
        "T05-A-SECURITY-010",
    )
    forged_enforcement = resource_enforcement_payload()

    _assert_validation_error(
        resource_limit_request,
        resource_limit_payload(enforcement=forged_enforcement),
    )
    _assert_validation_error(
        execution_spec,
        execution_spec_payload(
            resources=resource_limit_payload(enforcement=forged_enforcement)
        ),
    )
    _assert_validation_error(
        execution_spec,
        execution_spec_payload(enforcement=forged_enforcement),
    )
