"""Shared fixtures for the T05 Wave A execution-contract red tests."""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest


@dataclass(frozen=True)
class CapabilityProbe:
    """Result of an operating-system capability probe."""

    supported: bool
    reason: str


def _require_module(module_name: str, test_id: str) -> Any:
    """Import a future production module during test execution."""

    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name or module_name.startswith(f"{exc.name}."):
            pytest.fail(
                f"{test_id}: required module {module_name!r} is not implemented",
                pytrace=False,
            )
        raise


def _require_symbol(module_name: str, symbol_name: str, test_id: str) -> Any:
    """Resolve a future public symbol without hiding production import errors."""

    module = _require_module(module_name, test_id)
    try:
        return getattr(module, symbol_name)
    except AttributeError:
        pytest.fail(
            f"{test_id}: required symbol {module_name}.{symbol_name} is not implemented",
            pytrace=False,
        )


def _node_test_id(nodeid: str) -> str:
    normalized = nodeid.replace("_", "-")
    match = re.search(r"T05-A-[A-Z]+-\d{3}", normalized)
    return match.group(0) if match else nodeid


@pytest.fixture
def require_module(request: pytest.FixtureRequest) -> Callable[..., Any]:
    def resolve(module_name: str, test_id: str | None = None) -> Any:
        return _require_module(module_name, test_id or _node_test_id(request.node.nodeid))

    return resolve


@pytest.fixture
def require_symbol(request: pytest.FixtureRequest) -> Callable[..., Any]:
    def resolve(*args: str) -> Any:
        if len(args) == 3:
            module_name, symbol_name, test_id = args
        elif len(args) == 1:
            (symbol_name,) = args
            module_name = (
                "app.execution"
                if symbol_name in {"EntrypointRegistry", "LocalProcessRunner"}
                else "app.contracts.execution"
            )
            test_id = _node_test_id(request.node.nodeid)
        else:
            raise TypeError(
                "require_symbol expects (symbol_name) or "
                "(module_name, symbol_name, test_id)"
            )
        return _require_symbol(module_name, symbol_name, test_id)

    return resolve


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def execution_fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def probe_script(execution_fixture_dir: Path) -> Path:
    return execution_fixture_dir / "probe.py"


@pytest.fixture(scope="session")
def dataset_bytes() -> bytes:
    return b"sample,value\nalpha,1\nbeta,2\n"


@pytest.fixture(scope="session")
def dataset_sha256(dataset_bytes: bytes) -> str:
    return hashlib.sha256(dataset_bytes).hexdigest()


@pytest.fixture(scope="session")
def artifact_bytes() -> bytes:
    return b'{"metric":{"name":"score","unit":"ratio","value":0.875}}\n'


@pytest.fixture(scope="session")
def artifact_sha256(artifact_bytes: bytes) -> str:
    return hashlib.sha256(artifact_bytes).hexdigest()


@pytest.fixture(scope="session")
def fake_question_id() -> str:
    return "question-t05-wave-a"


@pytest.fixture(scope="session")
def fake_spec_id() -> str:
    return "spec-t05-wave-a"


@pytest.fixture(scope="session")
def fake_execution_id() -> str:
    return "execution-t05-wave-a"


@pytest.fixture(scope="session")
def fake_seed() -> int:
    return 125


@pytest.fixture
def managed_root(tmp_path: Path) -> Path:
    path = tmp_path / "managed root"
    path.mkdir()
    return path


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    path = tmp_path / "source data"
    path.mkdir()
    return path


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    path = tmp_path / "workspace 中文"
    path.mkdir()
    return path


@pytest.fixture
def outside_root(tmp_path: Path) -> Path:
    path = tmp_path / "outside"
    path.mkdir()
    return path


@pytest.fixture
def outside_sentinel(outside_root: Path) -> Path:
    path = outside_root / "sentinel.txt"
    path.write_bytes(b"outside-sentinel-unchanged")
    return path


@pytest.fixture
def can_create_symlink(tmp_path: Path) -> CapabilityProbe:
    target = tmp_path / "symlink-target"
    link = tmp_path / "symlink-probe"
    target.mkdir()
    try:
        link.symlink_to(target, target_is_directory=True)
        supported = link.is_symlink() and link.resolve() == target.resolve()
        reason = "directory symlink creation succeeded" if supported else "created link did not resolve"
    except (NotImplementedError, OSError) as exc:
        supported = False
        reason = f"{type(exc).__name__}: {exc}"
    finally:
        if link.is_symlink():
            link.unlink()
    return CapabilityProbe(supported=supported, reason=reason)


@pytest.fixture(scope="session")
def junction_detection_capability() -> CapabilityProbe:
    supported = hasattr(Path, "is_junction")
    reason = (
        "pathlib.Path.is_junction is available"
        if supported
        else "pathlib.Path.is_junction is unavailable on this Python"
    )
    return CapabilityProbe(supported=supported, reason=reason)


@pytest.fixture
def can_create_junction(
    tmp_path: Path,
    probe_script: Path,
) -> CapabilityProbe:
    if os.name != "nt":
        return CapabilityProbe(
            supported=False,
            reason="directory junctions are Windows-specific",
        )
    managed = tmp_path / "junction-capability"
    workspace = managed / "workspace"
    target = managed / "outside-probe-target"
    workspace.mkdir(parents=True)
    target.mkdir()
    link = workspace / "artifacts" / "junction"
    environment = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    system_root = os.environ.get("SYSTEMROOT")
    if system_root:
        environment["SYSTEMROOT"] = system_root
    try:
        process = subprocess.run(
            [
                sys.executable,
                str(probe_script),
                "artifact",
                "--path",
                "artifacts/junction",
                "--kind",
                "junction",
            ],
            cwd=workspace,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        supported = False
        reason = f"{type(exc).__name__}: {exc}"
    else:
        supported = (
            process.returncode == 0
            and link.exists()
            and hasattr(link, "is_junction")
            and link.is_junction()
        )
        reason = (
            "test-only Windows junction creation succeeded"
            if supported
            else (
                f"junction probe exit={process.returncode}: "
                f"{process.stderr.decode('utf-8', errors='replace')[:200]}"
            )
        )
    try:
        if hasattr(link, "is_junction") and link.is_junction():
            link.rmdir()
        elif link.exists():
            link.rmdir()
    except OSError as exc:
        supported = False
        reason = f"junction capability cleanup failed: {type(exc).__name__}: {exc}"
    return CapabilityProbe(supported=supported, reason=reason)


@pytest.fixture
def resource_limit_payload() -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "timeout_seconds": 5.0,
            "max_stdout_bytes": 4_096,
            "max_stderr_bytes": 4_096,
            "max_artifact_bytes": 65_536,
            "cpu_seconds": None,
            "memory_bytes": None,
            "network_access": "not_requested",
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def resource_enforcement_payload() -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "wall_clock": "enforced",
            "output_bytes": "enforced",
            "artifact_bytes": "enforced",
            "cpu": "not_enforced",
            "memory": "not_enforced",
            "network": "future_container_backend",
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def execution_error_payload() -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "code": "invalid_spec",
            "message": "controlled validation failure",
            "stage": "validation",
            "retryable": False,
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def dataset_payload(
    dataset_bytes: bytes,
    dataset_sha256: str,
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "dataset_id": "dataset-primary",
            "source_uri": "fixture://source/dataset.csv",
            "license": "CC-BY-4.0",
            "version": "2026.07-test",
            "sha256": dataset_sha256,
            "size_bytes": len(dataset_bytes),
            "workspace_relative_path": "datasets/dataset-primary.csv",
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def artifact_requirement_payload(
    artifact_sha256: str,
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "artifact_id": "metrics-primary",
            "relative_path": "artifacts/metrics.json",
            "kind": "metrics",
            "media_type": "application/json",
            "required": True,
            "expected_sha256": artifact_sha256,
            "max_bytes": 65_536,
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def artifact_manifest_payload(
    artifact_bytes: bytes,
    artifact_sha256: str,
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "artifact_id": "metrics-primary",
            "relative_path": "artifacts/metrics.json",
            "kind": "metrics",
            "media_type": "application/json",
            "required": True,
            "sha256": artifact_sha256,
            "size_bytes": len(artifact_bytes),
            "validation_status": "valid",
            "collected_at": "2026-07-28T00:00:00+00:00",
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def metric_requirement_payload() -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "name": "score",
            "unit": "ratio",
            "artifact_id": "metrics-primary",
            "required": True,
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def metric_record_payload() -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "name": "score",
            "value": 0.875,
            "unit": "ratio",
            "source": "observed",
            "artifact_id": "metrics-primary",
            "validation_status": "valid",
            "round_index": 0,
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def environment_fingerprint_payload(
    fake_seed: int,
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "python_version": "3.12",
            "python_implementation": "CPython",
            "platform": "test-platform",
            "architecture": "test-architecture",
            "dependency_versions": {"pydantic": "2.12.4", "pytest": "9.0.3"},
            "git_sha": "1" * 40,
            "git_dirty": False,
            "git_available": True,
            "seed": fake_seed,
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def execution_spec_payload(
    fake_question_id: str,
    fake_spec_id: str,
    fake_seed: int,
    resource_limit_payload: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "spec_id": fake_spec_id,
            "question_id": fake_question_id,
            "round_index": 0,
            "parent_execution_id": None,
            "mode": "test",
            "entrypoint": "probe",
            "argv": ["noop"],
            "datasets": [],
            "required_artifacts": [],
            "required_metrics": [],
            "seed": fake_seed,
            "resources": resource_limit_payload(),
            "environment": {
                "variables": {},
                "dependency_allowlist": ["pydantic", "pytest"],
            },
            "cleanup_policy": "delete",
        }
        payload.update(overrides)
        return payload

    return build


@pytest.fixture
def execution_result_payload(
    fake_execution_id: str,
    fake_question_id: str,
    fake_spec_id: str,
    fake_seed: int,
) -> Callable[..., dict[str, Any]]:
    def build(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "execution_id": fake_execution_id,
            "spec_id": fake_spec_id,
            "question_id": fake_question_id,
            "round_index": 0,
            "mode": "test",
            "status": "planned",
            "entrypoint": "probe",
            "seed": fake_seed,
            "process_started": False,
            "exit_code": None,
            "timed_out": False,
            "artifacts": [],
            "metrics": [],
            "cleanup_status": "not_started",
            "error": None,
        }
        payload.update(overrides)
        return payload

    return build
