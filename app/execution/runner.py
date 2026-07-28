"""Controlled local Python process runner.

This module provides a deliberately small local backend for trusted,
pre-registered Python entrypoints.  It validates and copies declared inputs,
uses bounded pipe readers, verifies allowlisted artifacts and metrics, and
constructs runner-attested results.  It is not a malicious-code sandbox.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Literal

from pydantic import ValidationError

from app.contracts.execution import (
    ArtifactManifest,
    ArtifactRequirement,
    EnvironmentFingerprint,
    ExecutionError,
    ExecutionFailureCode,
    ExecutionResult,
    ExecutionSpec,
    MetricRecord,
    MetricRequirement,
    ResourceLimitEnforcement,
)

from .provenance import (
    DependencyProvenanceError,
    DependencyVersionProvider,
    GitProvenanceError,
    GitProvenanceProvider,
    build_environment_fingerprint,
)
from .registry import EntrypointRegistry
from .security import (
    BoundedPipeBuffer,
    PipeCapture,
    SecurityViolation,
    build_minimal_environment,
    copy_verified_file,
    create_unique_workspace,
    drain_pipe,
    ensure_regular_file,
    ensure_secure_directory,
    ensure_secure_root,
    file_sha256,
    is_secret_environment_name,
    read_verified_bytes,
    redact_text,
    safe_cleanup_workspace,
    secure_relative_path,
)

__all__ = ["LocalProcessRunner"]


_TERMINATE_GRACE_SECONDS = 0.5
_FINAL_WAIT_SECONDS = 5.0
_READER_JOIN_SECONDS = 5.0
_MAX_METRIC_DOCUMENT_BYTES = 1_048_576
_TRUSTED_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_ResultStatus = Literal["planned", "rejected", "succeeded", "failed", "timed_out"]
_CleanupCallable = Callable[[Path], None]
_DatasetResolver = Callable[[Any], Path]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resource_enforcement(state: _RunState) -> ResourceLimitEnforcement:
    return ResourceLimitEnforcement(
        wall_clock=(
            "not_enforced"
            if state.process_alive_after_cleanup
            else "enforced"
        ),
        output_bytes="enforced",
        artifact_bytes="enforced",
        cpu="not_enforced",
        memory="not_enforced",
        network="future_container_backend",
    )


@dataclass(frozen=True, slots=True)
class _CollectedArtifact:
    manifest: ArtifactManifest
    path: Path


@dataclass(slots=True)
class _RunState:
    spec: ExecutionSpec
    execution_id: str
    started_at: str
    started_monotonic: float
    status: _ResultStatus = "planned"
    entrypoint_class: str | None = None
    entrypoint_script_path: Path | None = None
    workspace: Path | None = None
    workspace_uri: str | None = None
    process_started: bool = False
    exit_code: int | None = None
    timed_out: bool = False
    process_reaped: bool = False
    process_alive_after_cleanup: bool = False
    stdout: str = ""
    stderr: str = ""
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    datasets: list[Any] = field(default_factory=list)
    artifacts: list[ArtifactManifest] = field(default_factory=list)
    collected_artifacts: dict[str, _CollectedArtifact] = field(
        default_factory=dict
    )
    metrics: list[MetricRecord] = field(default_factory=list)
    cleanup_status: str = "not_started"
    environment_fingerprint: EnvironmentFingerprint | None = None
    warnings: list[str] = field(default_factory=list)
    error: ExecutionError | None = None
    datasets_validated: bool = False
    artifacts_validated: bool = False
    metrics_validated: bool = False
    provenance_complete: bool = False
    scientific_result_usable: bool = False


def _validation_failure_code(error: ValidationError) -> ExecutionFailureCode:
    for detail in error.errors(include_input=False, include_url=False):
        location = {str(item) for item in detail.get("loc", ())}
        if location & {"relative_path", "workspace_relative_path"}:
            return "path_escape"
    return "invalid_spec"


def _set_failure(
    state: _RunState,
    *,
    status: Literal["rejected", "failed", "timed_out"],
    code: ExecutionFailureCode,
    stage: str,
    message: str,
    retryable: bool = False,
) -> None:
    state.status = status
    state.timed_out = status == "timed_out"
    state.error = ExecutionError(
        code=code,
        message=message,
        stage=stage,
        retryable=retryable,
    )
    state.metrics = []
    state.metrics_validated = False
    state.provenance_complete = False
    state.scientific_result_usable = False


def _reader_thread(
    stream: BinaryIO,
    buffer: BoundedPipeBuffer,
    name: str,
) -> threading.Thread:
    thread = threading.Thread(
        target=drain_pipe,
        args=(stream, buffer),
        name=name,
        daemon=True,
    )
    thread.start()
    return thread


def _join_capture(
    thread: threading.Thread,
    buffer: BoundedPipeBuffer,
) -> PipeCapture:
    thread.join(timeout=_READER_JOIN_SECONDS)
    capture = buffer.snapshot()
    if thread.is_alive():
        return capture
    if not capture.finished:
        buffer.finish("reader did not finish")
        capture = buffer.snapshot()
    return capture


def _json_object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


class LocalProcessRunner:
    """Run trusted registered Python entrypoints in isolated workspaces."""

    def __init__(
        self,
        *,
        registry: EntrypointRegistry,
        managed_root: str | os.PathLike[str],
        dataset_resolver: _DatasetResolver | None = None,
        dependency_version_provider: DependencyVersionProvider | None = None,
        git_provenance_provider: GitProvenanceProvider | None = None,
        cleanup: _CleanupCallable | None = None,
    ) -> None:
        if not isinstance(registry, EntrypointRegistry):
            raise TypeError("registry must be an EntrypointRegistry")
        if dataset_resolver is not None and not callable(dataset_resolver):
            raise TypeError("dataset_resolver must be callable")
        if (
            dependency_version_provider is not None
            and not callable(dependency_version_provider)
        ):
            raise TypeError("dependency_version_provider must be callable")
        if git_provenance_provider is not None and not callable(
            git_provenance_provider
        ):
            raise TypeError("git_provenance_provider must be callable")
        if cleanup is not None and not callable(cleanup):
            raise TypeError("cleanup must be callable")

        self._registry = registry
        self._managed_root = ensure_secure_root(
            managed_root,
            create=True,
            stage="workspace",
        )
        self._dataset_resolver = dataset_resolver
        self._dependency_version_provider = dependency_version_provider
        self._git_provenance_provider = git_provenance_provider
        self._cleanup = cleanup

    def run(self, spec: ExecutionSpec) -> ExecutionResult:
        """Execute one immutable specification and return validated evidence."""

        if not isinstance(spec, ExecutionSpec):
            raise TypeError("spec must be an ExecutionSpec")

        state = _RunState(
            spec=spec,
            execution_id=f"execution-{uuid.uuid4().hex}",
            started_at=_utc_now(),
            started_monotonic=time.monotonic(),
        )

        try:
            validated_spec = ExecutionSpec.model_validate(
                spec.model_dump(mode="python")
            )
        except ValidationError as exc:
            _set_failure(
                state,
                status="rejected",
                code=_validation_failure_code(exc),
                stage="validation",
                message="execution specification failed runner validation",
            )
            return self._finalize(state)
        state.spec = validated_spec

        try:
            registration = self._registry.resolve(validated_spec.entrypoint)
        except (KeyError, ValueError):
            _set_failure(
                state,
                status="rejected",
                code="entrypoint_not_allowed",
                stage="policy",
                message="entrypoint is not registered for controlled execution",
            )
            return self._finalize(state)
        state.entrypoint_class = registration.entrypoint_class
        state.entrypoint_script_path = registration.script_path

        if (
            validated_spec.mode == "actual"
            and registration.entrypoint_class != "scientific"
        ):
            _set_failure(
                state,
                status="rejected",
                code="entrypoint_not_allowed",
                stage="policy",
                message="entrypoint class is not allowed for actual execution",
            )
            return self._finalize(state)

        try:
            ensure_regular_file(
                registration.script_path,
                containment_root=(
                    _TRUSTED_REPOSITORY_ROOT
                    if validated_spec.mode == "actual"
                    else None
                ),
                stage="policy",
                invalid_code="entrypoint_not_allowed",
            )
        except SecurityViolation as exc:
            _set_failure(
                state,
                status="rejected",
                code=exc.code,
                stage=exc.stage,
                message="registered entrypoint failed its runtime policy check",
            )
            return self._finalize(state)

        if validated_spec.mode in {"dry_run", "mock"}:
            state.status = "succeeded"
            return self._finalize(state)

        try:
            workspace = create_unique_workspace(
                self._managed_root,
                prefix="run-",
            )
            state.workspace = workspace
            state.workspace_uri = f"workspace://{state.execution_id}"
            input_directory = ensure_secure_directory(
                workspace,
                "input",
                stage="workspace",
            )
            # The unique workspace root is the execution working directory.
            # Keeping cwd one level below managed_root also lets runtime
            # containment tests exercise a real parent-boundary escape.
            working_directory = workspace
            ensure_secure_directory(workspace, "output", stage="workspace")
            ensure_secure_directory(workspace, "tmp", stage="workspace")
        except SecurityViolation as exc:
            _set_failure(
                state,
                status="rejected",
                code=exc.code,
                stage=exc.stage,
                message=str(exc),
            )
            return self._finalize(state)

        if not self._stage_datasets(
            state,
            input_directory=input_directory,
            working_directory=working_directory,
        ):
            return self._finalize(state)
        if not self._validate_artifact_destinations(
            state,
            working_directory=working_directory,
        ):
            return self._finalize(state)

        try:
            child_environment = build_minimal_environment(
                workspace,
                registration.allowed_environment,
                validated_spec.environment.variables,
            )
        except SecurityViolation as exc:
            _set_failure(
                state,
                status="rejected",
                code=exc.code,
                stage=exc.stage,
                message=str(exc),
            )
            return self._finalize(state)

        command = [
            str(registration.executable),
            *registration.interpreter_arguments,
            str(registration.script_path),
            *validated_spec.argv,
        ]
        self._execute_process(
            state,
            command=command,
            working_directory=working_directory,
            child_environment=child_environment,
            sensitive_paths=(
                self._managed_root.parent,
                self._managed_root,
                workspace,
                registration.executable,
                registration.script_path,
            ),
        )
        if state.status != "succeeded":
            return self._finalize(state)

        if not self._collect_artifacts(
            state,
            working_directory=working_directory,
        ):
            return self._finalize(state)

        if not self._collect_metrics(state):
            return self._finalize(state)

        if not self._collect_provenance(state):
            return self._finalize(state)

        state.scientific_result_usable = (
            validated_spec.mode == "actual"
            and registration.entrypoint_class == "scientific"
            and state.process_started
            and state.process_reaped
            and not state.process_alive_after_cleanup
            and state.exit_code == 0
            and state.datasets_validated
            and state.artifacts_validated
            and state.metrics_validated
            and state.provenance_complete
        )
        return self._finalize(state)

    def _stage_datasets(
        self,
        state: _RunState,
        *,
        input_directory: Path,
        working_directory: Path,
    ) -> bool:
        spec = state.spec
        if not spec.datasets:
            state.datasets_validated = False
            return True
        if self._dataset_resolver is None:
            _set_failure(
                state,
                status="rejected",
                code="dataset_invalid",
                stage="dataset",
                message="dataset resolver is unavailable",
            )
            return False

        staged_manifests: list[Any] = []
        for manifest in spec.datasets:
            try:
                source = self._dataset_resolver(manifest)
                input_copy = copy_verified_file(
                    source,
                    input_directory,
                    manifest.workspace_relative_path,
                    expected_sha256=manifest.sha256,
                    expected_size=manifest.size_bytes,
                    stage="dataset",
                )
                working_copy = copy_verified_file(
                    input_copy.path,
                    working_directory,
                    manifest.workspace_relative_path,
                    expected_sha256=manifest.sha256,
                    expected_size=manifest.size_bytes,
                    stage="dataset",
                )
            except SecurityViolation as exc:
                _set_failure(
                    state,
                    status="rejected",
                    code=exc.code,
                    stage=exc.stage,
                    message=str(exc),
                )
                return False
            except Exception:
                _set_failure(
                    state,
                    status="rejected",
                    code="dataset_invalid",
                    stage="dataset",
                    message="dataset resolver or staging failed",
                )
                return False

            if (
                input_copy.sha256 != manifest.sha256
                or input_copy.size_bytes != manifest.size_bytes
                or working_copy.sha256 != manifest.sha256
                or working_copy.size_bytes != manifest.size_bytes
            ):
                _set_failure(
                    state,
                    status="rejected",
                    code="dataset_invalid",
                    stage="dataset",
                    message="workspace dataset copy failed integrity validation",
                )
                return False
            staged_manifests.append(manifest)

        state.datasets = staged_manifests
        state.datasets_validated = (
            len(staged_manifests) == len(spec.datasets)
            and bool(staged_manifests)
        )
        return state.datasets_validated

    @staticmethod
    def _validate_artifact_destinations(
        state: _RunState,
        *,
        working_directory: Path,
    ) -> bool:
        dataset_paths = {
            item.workspace_relative_path.replace("\\", "/").casefold()
            for item in state.spec.datasets
        }
        artifact_paths: set[str] = set()
        for requirement in state.spec.required_artifacts:
            normalized = requirement.relative_path.replace(
                "\\",
                "/",
            ).casefold()
            if normalized in dataset_paths or normalized in artifact_paths:
                _set_failure(
                    state,
                    status="rejected",
                    code="artifact_invalid",
                    stage="artifact",
                    message=(
                        "artifact destinations must be unique and separate "
                        "from staged inputs"
                    ),
                )
                return False
            artifact_paths.add(normalized)
            try:
                destination = secure_relative_path(
                    working_directory,
                    requirement.relative_path,
                    stage="artifact",
                )
            except SecurityViolation as exc:
                _set_failure(
                    state,
                    status="rejected",
                    code=exc.code,
                    stage=exc.stage,
                    message=str(exc),
                )
                return False
            if os.path.lexists(destination):
                _set_failure(
                    state,
                    status="rejected",
                    code="artifact_invalid",
                    stage="artifact",
                    message="artifact destination exists before process start",
                )
                return False
        return True

    def _execute_process(
        self,
        state: _RunState,
        *,
        command: list[str],
        working_directory: Path,
        child_environment: Mapping[str, str],
        sensitive_paths: tuple[Path, ...],
    ) -> None:
        spec = state.spec
        stdout_buffer = BoundedPipeBuffer(spec.resources.max_stdout_bytes)
        stderr_buffer = BoundedPipeBuffer(spec.resources.max_stderr_bytes)
        process: subprocess.Popen[bytes] | None = None
        stdout_thread: threading.Thread | None = None
        stderr_thread: threading.Thread | None = None
        normal_wait_completed = False

        try:
            process = subprocess.Popen(
                command,
                cwd=working_directory,
                env=dict(child_environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                bufsize=0,
                shell=False,
            )
            state.process_started = True
            if process.stdout is None or process.stderr is None:
                raise OSError("process pipes are unavailable")
            stdout_thread = _reader_thread(
                process.stdout,
                stdout_buffer,
                f"execution-stdout-{state.execution_id}",
            )
            stderr_thread = _reader_thread(
                process.stderr,
                stderr_buffer,
                f"execution-stderr-{state.execution_id}",
            )
            try:
                process.wait(timeout=spec.resources.timeout_seconds)
                normal_wait_completed = True
            except subprocess.TimeoutExpired:
                state.timed_out = True
                try:
                    process.terminate()
                except OSError:
                    pass
                try:
                    process.wait(timeout=_TERMINATE_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except OSError:
                        pass
                    try:
                        process.wait(timeout=_FINAL_WAIT_SECONDS)
                    except subprocess.TimeoutExpired:
                        pass
        except OSError:
            if not state.process_started:
                _set_failure(
                    state,
                    status="failed",
                    code="spawn_failed",
                    stage="spawn",
                    message="registered process could not be started",
                    retryable=True,
                )
            else:
                _set_failure(
                    state,
                    status="failed",
                    code="internal_error",
                    stage="process",
                    message="process stream setup failed",
                )
        finally:
            if process is not None and state.process_started:
                if process.poll() is None:
                    try:
                        process.kill()
                    except OSError:
                        pass
                    try:
                        process.wait(timeout=_FINAL_WAIT_SECONDS)
                    except subprocess.TimeoutExpired:
                        pass
                state.exit_code = process.returncode
                state.process_reaped = process.returncode is not None
                state.process_alive_after_cleanup = process.returncode is None
                if state.process_alive_after_cleanup:
                    for pipe in (process.stdout, process.stderr):
                        if pipe is not None:
                            try:
                                pipe.close()
                            except OSError:
                                pass

            if stdout_thread is not None:
                stdout_capture = _join_capture(
                    stdout_thread,
                    stdout_buffer,
                )
            else:
                stdout_buffer.finish()
                stdout_capture = stdout_buffer.snapshot()
            if stderr_thread is not None:
                stderr_capture = _join_capture(
                    stderr_thread,
                    stderr_buffer,
                )
            else:
                stderr_buffer.finish()
                stderr_capture = stderr_buffer.snapshot()

        secrets = tuple(
            value
            for name, value in state.spec.environment.variables.items()
            if is_secret_environment_name(name)
        )
        state.stdout = (
            ""
            if (
                stdout_capture.truncated
                or not stdout_capture.finished
                or stdout_capture.error is not None
            )
            else redact_text(
                stdout_capture.text,
                secrets=secrets,
                sensitive_paths=sensitive_paths,
            )
        )
        state.stderr = (
            ""
            if (
                stderr_capture.truncated
                or not stderr_capture.finished
                or stderr_capture.error is not None
            )
            else redact_text(
                stderr_capture.text,
                secrets=secrets,
                sensitive_paths=sensitive_paths,
            )
        )
        state.stdout_bytes = stdout_capture.total_bytes
        state.stderr_bytes = stderr_capture.total_bytes
        state.stdout_truncated = stdout_capture.truncated
        state.stderr_truncated = stderr_capture.truncated

        if not state.process_started:
            return
        if state.timed_out and not state.process_reaped:
            _set_failure(
                state,
                status="failed",
                code="internal_error",
                stage="process",
                message="timed-out process could not be reaped",
            )
            return
        if state.timed_out:
            _set_failure(
                state,
                status="timed_out",
                code="timeout",
                stage="process",
                message="registered process exceeded its wall-clock limit",
                retryable=True,
            )
            return
        if state.error is not None:
            return
        if (
            stdout_capture.error is not None
            or stderr_capture.error is not None
            or not stdout_capture.finished
            or not stderr_capture.finished
        ):
            _set_failure(
                state,
                status="failed",
                code="internal_error",
                stage="process",
                message="process output could not be drained completely",
            )
            return
        if not normal_wait_completed or not state.process_reaped:
            _set_failure(
                state,
                status="failed",
                code="internal_error",
                stage="process",
                message="registered process could not be reaped",
            )
            return
        if state.exit_code != 0:
            _set_failure(
                state,
                status="failed",
                code="nonzero_exit",
                stage="process",
                message="registered process exited with a nonzero status",
            )
            return
        state.status = "succeeded"

    def _collect_artifacts(
        self,
        state: _RunState,
        *,
        working_directory: Path,
    ) -> bool:
        requirements = sorted(
            state.spec.required_artifacts,
            key=lambda item: item.artifact_id,
        )
        if not requirements:
            state.artifacts_validated = False
            return True

        collected: list[ArtifactManifest] = []
        collected_bytes = 0
        for requirement in requirements:
            collected_at = _utc_now()
            try:
                artifact_path = secure_relative_path(
                    working_directory,
                    requirement.relative_path,
                    must_exist=True,
                    require_file=True,
                    stage="artifact",
                    missing_code="artifact_missing",
                    invalid_code="artifact_invalid",
                )
            except SecurityViolation as exc:
                if exc.code == "artifact_missing" and not requirement.required:
                    continue
                collected.append(
                    self._invalid_artifact_manifest(
                        requirement,
                        status=(
                            "missing"
                            if exc.code == "artifact_missing"
                            else "invalid"
                        ),
                    )
                )
                _set_failure(
                    state,
                    status="failed",
                    code=exc.code,
                    stage=exc.stage,
                    message=str(exc),
                )
                state.artifacts = collected
                return False

            remaining_run_bytes = (
                state.spec.resources.max_artifact_bytes - collected_bytes
            )
            per_artifact_limit = requirement.max_bytes
            hash_limit = remaining_run_bytes
            if per_artifact_limit is not None:
                hash_limit = min(hash_limit, per_artifact_limit)
            try:
                digest = file_sha256(
                    artifact_path,
                    max_bytes=hash_limit,
                    containment_root=working_directory,
                    stage="artifact",
                    invalid_code="artifact_invalid",
                )
            except SecurityViolation as exc:
                collected.append(
                    self._invalid_artifact_manifest(
                        requirement,
                        status="invalid",
                    )
                )
                _set_failure(
                    state,
                    status="failed",
                    code=exc.code,
                    stage=exc.stage,
                    message=str(exc),
                )
                state.artifacts = collected
                return False

            collected_bytes += digest.size_bytes
            if (
                requirement.expected_sha256 is not None
                and digest.sha256 != requirement.expected_sha256
            ):
                mismatch = ArtifactManifest(
                    artifact_id=requirement.artifact_id,
                    relative_path=requirement.relative_path,
                    kind=requirement.kind,
                    media_type=requirement.media_type,
                    required=requirement.required,
                    sha256=digest.sha256,
                    size_bytes=digest.size_bytes,
                    validation_status="checksum_mismatch",
                    collected_at=collected_at,
                )
                collected.append(mismatch)
                _set_failure(
                    state,
                    status="failed",
                    code="checksum_mismatch",
                    stage="artifact",
                    message="artifact checksum does not match its requirement",
                )
                state.artifacts = collected
                return False

            manifest = ArtifactManifest(
                artifact_id=requirement.artifact_id,
                relative_path=requirement.relative_path,
                kind=requirement.kind,
                media_type=requirement.media_type,
                required=requirement.required,
                sha256=digest.sha256,
                size_bytes=digest.size_bytes,
                validation_status="valid",
                collected_at=collected_at,
            )
            collected.append(manifest)
            state.collected_artifacts[requirement.artifact_id] = (
                _CollectedArtifact(manifest=manifest, path=artifact_path)
            )

        state.artifacts = collected
        state.artifacts_validated = (
            bool(requirements)
            and len(collected) == len(requirements)
            and all(item.validation_status == "valid" for item in collected)
        )
        return state.artifacts_validated

    @staticmethod
    def _invalid_artifact_manifest(
        requirement: ArtifactRequirement,
        *,
        status: Literal["missing", "invalid"],
    ) -> ArtifactManifest:
        return ArtifactManifest(
            artifact_id=requirement.artifact_id,
            relative_path=requirement.relative_path,
            kind=requirement.kind,
            media_type=requirement.media_type,
            required=requirement.required,
            sha256=None,
            size_bytes=None,
            validation_status=status,
            collected_at=None,
        )

    def _collect_metrics(self, state: _RunState) -> bool:
        requirements = sorted(
            state.spec.required_metrics,
            key=lambda item: item.name,
        )
        if not requirements:
            state.metrics_validated = False
            if state.spec.mode == "actual":
                _set_failure(
                    state,
                    status="failed",
                    code="metric_invalid",
                    stage="metric",
                    message="actual execution requires declared observed metrics",
                )
                return False
            return True

        records: list[MetricRecord] = []
        for requirement in requirements:
            collected = state.collected_artifacts.get(requirement.artifact_id)
            if (
                collected is None
                or collected.manifest.validation_status != "valid"
            ):
                if not requirement.required:
                    continue
                _set_failure(
                    state,
                    status="failed",
                    code="metric_invalid",
                    stage="metric",
                    message="required metric has no valid source artifact",
                )
                return False
            try:
                metric_payload = self._read_metric_payload(
                    collected,
                    requirement=requirement,
                    containment_root=state.workspace,
                )
                record = self._metric_record(
                    requirement,
                    payload=metric_payload,
                    round_index=state.spec.round_index,
                )
            except (OSError, UnicodeError, ValueError, SecurityViolation):
                _set_failure(
                    state,
                    status="failed",
                    code="metric_invalid",
                    stage="metric",
                    message="metric artifact is invalid",
                )
                return False
            records.append(record)

        state.metrics = records
        state.metrics_validated = (
            bool(requirements)
            and len(records) == len(requirements)
            and all(item.validation_status == "valid" for item in records)
        )
        if not state.metrics_validated:
            _set_failure(
                state,
                status="failed",
                code="metric_invalid",
                stage="metric",
                message="declared metric evidence is incomplete",
            )
            return False
        return True

    @staticmethod
    def _read_metric_payload(
        collected: _CollectedArtifact,
        *,
        requirement: MetricRequirement,
        containment_root: Path | None,
    ) -> Mapping[str, Any]:
        manifest = collected.manifest
        if (
            manifest.sha256 is None
            or manifest.size_bytes is None
            or containment_root is None
        ):
            raise ValueError("metric artifact lacks integrity evidence")
        document = read_verified_bytes(
            collected.path,
            expected_sha256=manifest.sha256,
            expected_size=manifest.size_bytes,
            max_bytes=_MAX_METRIC_DOCUMENT_BYTES,
            containment_root=containment_root,
            stage="metric",
            invalid_code="metric_invalid",
        )
        parsed = json.loads(
            document.decode("utf-8", errors="strict"),
            object_pairs_hook=_json_object_without_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non-finite JSON number")
            ),
        )
        if not isinstance(parsed, Mapping):
            raise ValueError("metric document must be an object")
        payload = parsed.get("metric")
        if not isinstance(payload, Mapping):
            raise ValueError("metric document must contain one metric object")
        if payload.get("name") != requirement.name:
            raise ValueError("metric name does not match its requirement")
        return payload

    @staticmethod
    def _metric_record(
        requirement: MetricRequirement,
        *,
        payload: Mapping[str, Any],
        round_index: int,
    ) -> MetricRecord:
        unit = payload.get("unit")
        value = payload.get("value")
        source = payload.get("source", "observed")
        if unit != requirement.unit:
            raise ValueError("metric unit does not match its requirement")
        if type(value) not in {int, float} or not math.isfinite(value):
            raise ValueError("metric value must be a finite number")
        if source != "observed":
            raise ValueError("only observed metrics are accepted")
        return MetricRecord(
            name=requirement.name,
            value=float(value),
            unit=requirement.unit,
            source="observed",
            artifact_id=requirement.artifact_id,
            validation_status="valid",
            round_index=round_index,
        )

    def _collect_provenance(self, state: _RunState) -> bool:
        try:
            fingerprint = build_environment_fingerprint(
                state.spec.seed,
                state.spec.environment.dependency_allowlist,
                dependency_version_provider=self._dependency_version_provider,
                git_provenance_provider=self._git_provenance_provider,
                repository_root=_TRUSTED_REPOSITORY_ROOT,
                required_tracked_path=state.entrypoint_script_path,
            )
        except DependencyProvenanceError:
            _set_failure(
                state,
                status="failed",
                code="dependency_missing",
                stage="provenance",
                message="dependency provenance is incomplete",
            )
            return False
        except GitProvenanceError:
            _set_failure(
                state,
                status="failed",
                code="provenance_incomplete",
                stage="provenance",
                message="Git provenance is invalid or incomplete",
            )
            return False
        except (ValidationError, ValueError):
            _set_failure(
                state,
                status="failed",
                code="provenance_incomplete",
                stage="provenance",
                message="environment provenance is invalid or incomplete",
            )
            return False

        state.environment_fingerprint = fingerprint
        state.provenance_complete = (
            fingerprint.git_available
            and fingerprint.git_sha is not None
            and not fingerprint.git_dirty
        )
        if state.spec.mode == "actual" and not state.provenance_complete:
            _set_failure(
                state,
                status="failed",
                code="provenance_incomplete",
                stage="provenance",
                message="actual execution requires clean Git provenance",
            )
            return False
        return True

    def _finalize(self, state: _RunState) -> ExecutionResult:
        if state.workspace is not None:
            if state.process_alive_after_cleanup:
                state.cleanup_status = "preserved"
                state.warnings.append(
                    "workspace retained because process reaping was incomplete"
                )
            elif state.spec.cleanup_policy == "preserve":
                state.cleanup_status = "preserved"
            else:
                try:
                    if self._cleanup is None:
                        safe_cleanup_workspace(
                            self._managed_root,
                            state.workspace,
                        )
                    else:
                        self._cleanup(state.workspace)
                    if os.path.lexists(state.workspace):
                        raise OSError(
                            "cleanup returned before removing the workspace"
                        )
                except Exception:
                    state.cleanup_status = "failed"
                    _set_failure(
                        state,
                        status="failed",
                        code="cleanup_failed",
                        stage="cleanup",
                        message="workspace cleanup failed",
                    )
                else:
                    state.cleanup_status = "succeeded"

        if state.status in {"failed", "timed_out", "rejected"}:
            state.metrics = []
            state.metrics_validated = False
            state.scientific_result_usable = False

        finished_at = _utc_now()
        duration_seconds = max(
            0.0,
            time.monotonic() - state.started_monotonic,
        )
        sensitive_paths: tuple[Path, ...] = (
            self._managed_root.parent,
            self._managed_root,
            *(() if state.workspace is None else (state.workspace,)),
        )
        secrets = tuple(
            value
            for name, value in state.spec.environment.variables.items()
            if is_secret_environment_name(name)
        )
        stdout = redact_text(
            state.stdout,
            secrets=secrets,
            sensitive_paths=sensitive_paths,
        )
        stderr = redact_text(
            state.stderr,
            secrets=secrets,
            sensitive_paths=sensitive_paths,
        )
        warnings = [
            redact_text(
                warning,
                secrets=secrets,
                sensitive_paths=sensitive_paths,
            )
            for warning in state.warnings
        ]
        error_payload: dict[str, Any] | None = None
        if state.error is not None:
            error_payload = state.error.model_dump(mode="python")
            error_payload["message"] = redact_text(
                state.error.message,
                secrets=secrets,
                sensitive_paths=sensitive_paths,
            )

        return ExecutionResult._from_runner(
            {
                "schema_version": "1.0",
                "execution_id": state.execution_id,
                "spec_id": state.spec.spec_id,
                "question_id": state.spec.question_id,
                "round_index": state.spec.round_index,
                "parent_execution_id": state.spec.parent_execution_id,
                "mode": state.spec.mode,
                "status": state.status,
                "entrypoint": state.spec.entrypoint,
                "entrypoint_class": state.entrypoint_class,
                "seed": state.spec.seed,
                "started_at": state.started_at,
                "finished_at": finished_at,
                "duration_seconds": duration_seconds,
                "process_started": state.process_started,
                "exit_code": state.exit_code,
                "timed_out": state.timed_out,
                "process_reaped": state.process_reaped,
                "process_alive_after_cleanup": (
                    state.process_alive_after_cleanup
                ),
                "stdout": stdout,
                "stderr": stderr,
                "stdout_bytes": state.stdout_bytes,
                "stderr_bytes": state.stderr_bytes,
                "stdout_truncated": state.stdout_truncated,
                "stderr_truncated": state.stderr_truncated,
                "workspace_uri": state.workspace_uri,
                "datasets": state.datasets,
                "artifacts": state.artifacts,
                "metrics": state.metrics,
                "cleanup_status": state.cleanup_status,
                "resource_enforcement": _resource_enforcement(state),
                "environment_fingerprint": state.environment_fingerprint,
                "warnings": warnings,
                "error": error_payload,
                "runner_verified": False,
                "datasets_validated": state.datasets_validated,
                "artifacts_validated": state.artifacts_validated,
                "metrics_validated": state.metrics_validated,
                "provenance_complete": state.provenance_complete,
                "scientific_result_usable": (
                    state.scientific_result_usable
                ),
                "actual_execution": False,
            }
        )
