"""Versioned data contracts for controlled execution.

This module defines contracts only. The separate ``app.execution`` package
implements the controlled local runner. Importing this module does not start a
process, create a workspace, read provenance, or claim sandboxing.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal
from urllib.parse import parse_qsl, unquote, urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationInfo,
    field_validator,
    model_validator,
)

SchemaVersion = Literal["1.0"]
ExecutionMode = Literal["actual", "dry_run", "mock", "test"]
ExecutionStatus = Literal[
    "planned",
    "rejected",
    "running",
    "succeeded",
    "failed",
    "timed_out",
    "cancelled",
]
CapabilityState = Literal[
    "enforced",
    "not_enforced",
    "unsupported",
    "future_container_backend",
]
CleanupStatus = Literal["not_started", "succeeded", "failed", "preserved"]
CleanupPolicy = Literal["delete", "preserve"]
MetricSource = Literal["observed", "expected", "default", "mock", "test"]
DatasetValidationStatus = Literal["declared", "validated", "invalid"]
ArtifactValidationStatus = Literal[
    "pending",
    "valid",
    "missing",
    "invalid",
    "checksum_mismatch",
]
MetricValidationStatus = Literal["pending", "valid", "missing", "invalid"]
NetworkAccess = Literal["not_requested", "allow", "deny"]
ArtifactKind = Literal[
    "metrics",
    "raw",
    "report",
    "log",
    "plot",
    "table",
    "model",
]
EntrypointClass = Literal["scientific", "test"]
ExecutionFailureCode = Literal[
    "invalid_spec",
    "policy_rejected",
    "capability_unsupported",
    "entrypoint_not_allowed",
    "path_invalid",
    "path_escape",
    "symlink_escape",
    "dataset_invalid",
    "dependency_missing",
    "spawn_failed",
    "nonzero_exit",
    "timeout",
    "artifact_missing",
    "artifact_invalid",
    "checksum_mismatch",
    "metric_invalid",
    "provenance_incomplete",
    "cleanup_failed",
    "cancelled",
    "internal_error",
]

__all__ = [
    "ArtifactKind",
    "ArtifactManifest",
    "ArtifactRequirement",
    "ArtifactValidationStatus",
    "CapabilityState",
    "CleanupPolicy",
    "CleanupStatus",
    "DatasetManifest",
    "DatasetValidationStatus",
    "EntrypointClass",
    "EnvironmentFingerprint",
    "ExecutionError",
    "ExecutionFailureCode",
    "ExecutionMode",
    "ExecutionResult",
    "ExecutionSpec",
    "ExecutionStatus",
    "LegacyExecutionMetadataAdapter",
    "MetricRecord",
    "MetricRequirement",
    "MetricSource",
    "MetricValidationStatus",
    "NetworkAccess",
    "ResourceLimitEnforcement",
    "ResourceLimitRequest",
    "SchemaVersion",
]


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_GIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_URI_SCHEME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*\Z")
_DRIVE_PREFIX_PATTERN = re.compile(r"[A-Za-z]:")
_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
    *(f"com{index}" for index in ("¹", "²", "³")),
    *(f"lpt{index}" for index in ("¹", "²", "³")),
}
_SOURCE_URI_SCHEMES = {
    "az",
    "azure",
    "doi",
    "fixture",
    "gs",
    "hf",
    "http",
    "https",
    "ipfs",
    "s3",
    "urn",
}
_AUTHORITY_URI_SCHEMES = {
    "az",
    "azure",
    "fixture",
    "gs",
    "hf",
    "http",
    "https",
    "ipfs",
    "s3",
}
_SECRET_QUERY_KEYS = {
    "access_token",
    "authorization",
    "api_key",
    "apikey",
    "credential",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
    "x_amz_signature",
}
_RUNNER_ATTESTATION = object()
_RUNNER_CONTEXT_KEY = "runner_attestation"

_NonNegativeStrictInt = Annotated[StrictInt, Field(ge=0)]
_PositiveStrictInt = Annotated[StrictInt, Field(gt=0)]


def _validate_nonblank_text(
    value: object,
    *,
    label: str,
    max_length: int = 1_024,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    if "\x00" in value:
        raise ValueError(f"{label} contains a forbidden character")
    if not value.strip():
        raise ValueError(f"{label} must not be blank")
    if len(value) > max_length:
        raise ValueError(f"{label} is too long")
    return value


def _validate_identifier(value: object, *, label: str) -> str:
    return _validate_nonblank_text(value, label=label, max_length=256)


def _validate_sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be a canonical SHA-256 value")
    return value


def _validate_git_sha(value: object) -> str:
    if not isinstance(value, str) or _GIT_SHA_PATTERN.fullmatch(value) is None:
        raise ValueError("git_sha must be a canonical 40-character commit SHA")
    return value


def _decoded_path_forms(value: str) -> tuple[str, ...]:
    forms = [value]
    current = value
    for _ in range(len(value) + 1):
        decoded = unquote(current)
        if decoded == current:
            return tuple(forms)
        forms.append(decoded)
        current = decoded
    raise ValueError("path encoding does not reach a stable representation")


def _validate_one_relative_path_form(value: str) -> None:
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("path contains a forbidden control character")
    if value.startswith(("/", "\\")):
        raise ValueError("path must remain relative")
    if _DRIVE_PREFIX_PATTERN.match(value):
        raise ValueError("drive-qualified paths are forbidden")

    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        raise ValueError("path must remain relative")

    segments = normalized.split("/")
    if not segments or any(segment == "" for segment in segments):
        raise ValueError("empty path segments are forbidden")
    for segment in segments:
        if segment in {".", ".."}:
            raise ValueError("path traversal is forbidden")
        if ":" in segment:
            raise ValueError("alternate data streams are forbidden")
        if segment.endswith((" ", ".")):
            raise ValueError("dangerous trailing path characters are forbidden")
        base_name = segment.split(".", 1)[0].casefold()
        if base_name in _WINDOWS_RESERVED_NAMES:
            raise ValueError("reserved device names are forbidden")


def _validate_relative_path(value: object, *, label: str) -> str:
    path = _validate_nonblank_text(value, label=label, max_length=1_024)
    for form in _decoded_path_forms(path):
        _validate_one_relative_path_form(form)
    return path


def _normalize_query_key(value: str) -> str:
    current = value
    for _ in range(len(value) + 1):
        decoded = unquote(current)
        if decoded == current:
            normalized = current.casefold().replace("-", "_").replace(".", "_")
            return normalized.split("[", 1)[0]
        current = decoded
    raise ValueError("query key encoding does not reach a stable representation")


def _is_secret_query_key(value: str) -> bool:
    normalized = _normalize_query_key(value)
    return normalized in _SECRET_QUERY_KEYS or normalized.endswith(
        (
            "_access_token",
            "_api_key",
            "_credential",
            "_password",
            "_secret",
            "_signature",
            "_token",
        )
    )


def _decoded_uri_forms(value: str) -> tuple[str, ...]:
    forms = [value]
    current = value
    for _ in range(len(value) + 1):
        decoded = unquote(current)
        if decoded == current:
            return tuple(forms)
        forms.append(decoded)
        current = decoded
    raise ValueError("URI encoding does not reach a stable representation")


def _inspect_safe_uri_form(uri: str, *, label: str) -> None:
    if "\x00" in uri or any(
        character in uri for character in ("\r", "\n", "\t")
    ):
        raise ValueError(f"{label} contains a forbidden control character")
    if uri != uri.strip() or uri.startswith(("/", "\\")):
        raise ValueError(f"{label} must not contain a host path")
    if _DRIVE_PREFIX_PATTERN.match(uri):
        raise ValueError(f"{label} must not contain a drive path")
    try:
        parsed = urlsplit(uri)
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid URI") from exc
    scheme = parsed.scheme.casefold()
    if (
        not parsed.scheme
        or _URI_SCHEME_PATTERN.fullmatch(parsed.scheme) is None
        or scheme not in _SOURCE_URI_SCHEMES
    ):
        raise ValueError(f"{label} must use a safe explicit URI scheme")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{label} must not contain user information")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError(f"{label} contains an invalid port") from exc
    if scheme in _AUTHORITY_URI_SCHEMES and (
        parsed.hostname is None
        or any(character.isspace() for character in parsed.netloc)
    ):
        raise ValueError(f"{label} requires a valid authority")
    if scheme in {"doi", "urn"} and not parsed.path:
        raise ValueError(f"{label} requires a resource identifier")
    if ";" in parsed.query or ";" in parsed.fragment:
        raise ValueError(f"{label} cannot use ambiguous query separators")
    try:
        query_items = parse_qsl(parsed.query, keep_blank_values=True)
        fragment_queries = [parsed.fragment]
        if "?" in parsed.fragment:
            fragment_queries.append(parsed.fragment.split("?", 1)[1])
        fragment_items = [
            item
            for fragment_query in fragment_queries
            for item in parse_qsl(fragment_query, keep_blank_values=True)
        ]
    except ValueError as exc:
        raise ValueError(f"{label} contains an invalid query") from exc
    if any(_is_secret_query_key(key) for key, _value in query_items):
        raise ValueError(f"{label} must not contain secret query parameters")
    if any(_is_secret_query_key(key) for key, _value in fragment_items):
        raise ValueError(f"{label} must not contain secret fragment parameters")


def _validate_safe_uri(value: object, *, label: str) -> str:
    uri = _validate_nonblank_text(value, label=label, max_length=2_048)
    for form in _decoded_uri_forms(uri):
        _inspect_safe_uri_form(form, label=label)
    return uri


def _validate_safe_workspace_uri(value: object) -> str:
    uri = _validate_nonblank_text(value, label="workspace_uri", max_length=1_024)
    if uri != uri.strip() or "%" in uri or "\x00" in uri:
        raise ValueError("workspace_uri must be a canonical opaque identifier")
    if re.fullmatch(
        r"workspace://[A-Za-z0-9][A-Za-z0-9._-]*"
        r"(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*",
        uri,
    ) is None:
        raise ValueError("workspace_uri must use the workspace scheme")
    return uri


def _parse_aware_datetime(value: str, *, label: str) -> datetime:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


def _validate_timestamp(value: object, *, label: str) -> str:
    timestamp = _validate_nonblank_text(value, label=label, max_length=128)
    _parse_aware_datetime(timestamp, label=label)
    return timestamp


def _validate_finite_number(
    value: object,
    *,
    label: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{label} must be positive")
    if nonnegative and value < 0:
        raise ValueError(f"{label} must be nonnegative")
    return value


def _looks_like_host_path(value: str) -> bool:
    for form in _decoded_uri_forms(value):
        if form != form.strip():
            return True
        normalized = form.replace("\\", "/")
        if (
            normalized.startswith("/")
            or _DRIVE_PREFIX_PATTERN.match(form) is not None
            or form.casefold().startswith("file:")
        ):
            return True
    return False


class _ExecutionContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        allow_inf_nan=False,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ResourceLimitRequest(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    timeout_seconds: float = Field(default=300.0, le=86_400)
    max_stdout_bytes: _PositiveStrictInt = Field(
        default=1_048_576,
        le=1_073_741_824,
    )
    max_stderr_bytes: _PositiveStrictInt = Field(
        default=1_048_576,
        le=1_073_741_824,
    )
    max_artifact_bytes: _PositiveStrictInt = Field(
        default=104_857_600,
        le=1_099_511_627_776,
    )
    cpu_seconds: float | None = Field(default=None, le=86_400)
    memory_bytes: _PositiveStrictInt | None = Field(
        default=None,
        le=1_099_511_627_776,
    )
    network_access: NetworkAccess = "not_requested"

    @field_validator("timeout_seconds", "cpu_seconds", mode="before")
    @classmethod
    def _validate_positive_seconds(cls, value: object) -> object:
        if value is None:
            return value
        return _validate_finite_number(value, label="seconds", positive=True)


class ResourceLimitEnforcement(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    wall_clock: CapabilityState
    output_bytes: CapabilityState
    artifact_bytes: CapabilityState
    cpu: CapabilityState
    memory: CapabilityState
    network: CapabilityState


class ExecutionError(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    code: ExecutionFailureCode
    message: str
    stage: str
    retryable: StrictBool

    @field_validator("message", mode="before")
    @classmethod
    def _validate_message(cls, value: object) -> str:
        return _validate_nonblank_text(value, label="message", max_length=4_096)

    @field_validator("stage", mode="before")
    @classmethod
    def _validate_stage(cls, value: object) -> str:
        return _validate_identifier(value, label="stage")


class DatasetManifest(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    dataset_id: str
    source_uri: str
    license: str
    version: str
    sha256: str
    size_bytes: _NonNegativeStrictInt
    workspace_relative_path: str

    @field_validator("dataset_id", mode="before")
    @classmethod
    def _validate_dataset_id(cls, value: object) -> str:
        return _validate_identifier(value, label="dataset_id")

    @field_validator("source_uri", mode="before")
    @classmethod
    def _validate_source_uri(cls, value: object) -> str:
        return _validate_safe_uri(value, label="source_uri")

    @field_validator("license", "version", mode="before")
    @classmethod
    def _validate_provenance_text(cls, value: object, info: ValidationInfo) -> str:
        return _validate_nonblank_text(value, label=info.field_name, max_length=512)

    @field_validator("sha256", mode="before")
    @classmethod
    def _validate_digest(cls, value: object) -> str:
        return _validate_sha256(value, label="sha256")

    @field_validator("workspace_relative_path", mode="before")
    @classmethod
    def _validate_workspace_path(cls, value: object) -> str:
        return _validate_relative_path(value, label="workspace_relative_path")


class ArtifactRequirement(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    artifact_id: str
    relative_path: str
    kind: ArtifactKind
    media_type: str
    required: StrictBool
    expected_sha256: str | None = None
    max_bytes: _PositiveStrictInt | None = None

    @field_validator("artifact_id", mode="before")
    @classmethod
    def _validate_artifact_id(cls, value: object) -> str:
        return _validate_identifier(value, label="artifact_id")

    @field_validator("relative_path", mode="before")
    @classmethod
    def _validate_artifact_path(cls, value: object) -> str:
        return _validate_relative_path(value, label="relative_path")

    @field_validator("media_type", mode="before")
    @classmethod
    def _validate_media_type(cls, value: object) -> str:
        return _validate_nonblank_text(value, label="media_type", max_length=256)

    @field_validator("expected_sha256", mode="before")
    @classmethod
    def _validate_expected_digest(cls, value: object) -> object:
        if value is None:
            return value
        return _validate_sha256(value, label="expected_sha256")


class ArtifactManifest(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    artifact_id: str
    relative_path: str
    kind: ArtifactKind
    media_type: str
    required: StrictBool
    sha256: str | None = None
    size_bytes: _NonNegativeStrictInt | None = None
    validation_status: ArtifactValidationStatus
    collected_at: str | None = None

    @field_validator("artifact_id", mode="before")
    @classmethod
    def _validate_artifact_id(cls, value: object) -> str:
        return _validate_identifier(value, label="artifact_id")

    @field_validator("relative_path", mode="before")
    @classmethod
    def _validate_artifact_path(cls, value: object) -> str:
        return _validate_relative_path(value, label="relative_path")

    @field_validator("media_type", mode="before")
    @classmethod
    def _validate_media_type(cls, value: object) -> str:
        return _validate_nonblank_text(value, label="media_type", max_length=256)

    @field_validator("sha256", mode="before")
    @classmethod
    def _validate_digest(cls, value: object) -> object:
        if value is None:
            return value
        return _validate_sha256(value, label="sha256")

    @field_validator("collected_at", mode="before")
    @classmethod
    def _validate_collected_at(cls, value: object) -> object:
        if value is None:
            return value
        return _validate_timestamp(value, label="collected_at")

    @model_validator(mode="after")
    def _validate_evidence_state(self) -> "ArtifactManifest":
        evidence = (self.sha256, self.size_bytes, self.collected_at)
        if self.validation_status == "valid" and any(item is None for item in evidence):
            raise ValueError(
                "valid artifacts require checksum, size, and collection time"
            )
        if self.validation_status == "missing" and any(
            item is not None for item in evidence
        ):
            raise ValueError("missing artifacts cannot carry integrity evidence")
        return self


class MetricRequirement(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    name: str
    unit: str
    artifact_id: str
    required: StrictBool

    @field_validator("name", "artifact_id", mode="before")
    @classmethod
    def _validate_ids(cls, value: object, info: ValidationInfo) -> str:
        return _validate_identifier(value, label=info.field_name)

    @field_validator("unit", mode="before")
    @classmethod
    def _validate_unit(cls, value: object) -> str:
        return _validate_nonblank_text(value, label="unit", max_length=256)


class MetricRecord(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    name: str
    value: float = Field(allow_inf_nan=False)
    unit: str
    source: MetricSource
    artifact_id: str
    validation_status: MetricValidationStatus
    round_index: _NonNegativeStrictInt

    @field_validator("name", "artifact_id", mode="before")
    @classmethod
    def _validate_ids(cls, value: object, info: ValidationInfo) -> str:
        return _validate_identifier(value, label=info.field_name)

    @field_validator("unit", mode="before")
    @classmethod
    def _validate_unit(cls, value: object) -> str:
        return _validate_nonblank_text(value, label="unit", max_length=256)

    @field_validator("value", mode="before")
    @classmethod
    def _validate_metric_value(cls, value: object) -> int | float:
        return _validate_finite_number(value, label="value")


class EnvironmentFingerprint(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    python_version: str
    python_implementation: str
    platform: str
    architecture: str
    dependency_versions: dict[str, str] = Field(default_factory=dict)
    git_sha: str | None = None
    git_dirty: StrictBool
    git_available: StrictBool
    seed: _NonNegativeStrictInt

    @field_validator(
        "python_version",
        "python_implementation",
        "platform",
        "architecture",
        mode="before",
    )
    @classmethod
    def _validate_platform_text(cls, value: object, info: ValidationInfo) -> str:
        return _validate_nonblank_text(value, label=info.field_name, max_length=512)

    @field_validator("dependency_versions", mode="before")
    @classmethod
    def _validate_dependency_versions(cls, value: object) -> dict[str, str]:
        if not isinstance(value, Mapping):
            raise ValueError("dependency_versions must be a mapping")
        normalized: dict[str, str] = {}
        for raw_name, raw_version in value.items():
            name = _validate_identifier(raw_name, label="dependency name")
            version = _validate_nonblank_text(
                raw_version,
                label="dependency version",
                max_length=512,
            )
            if _looks_like_host_path(version):
                raise ValueError("dependency versions cannot contain host paths")
            normalized[name] = version
        return dict(sorted(normalized.items()))

    @model_validator(mode="after")
    def _validate_git_provenance(self) -> "EnvironmentFingerprint":
        if self.git_available:
            if self.git_sha is None:
                raise ValueError("available Git provenance requires git_sha")
            _validate_git_sha(self.git_sha)
        elif self.git_sha is not None:
            raise ValueError("unavailable Git provenance cannot carry git_sha")
        return self


class _ExecutionEnvironment(_ExecutionContractModel):
    variables: dict[str, str] = Field(default_factory=dict)
    dependency_allowlist: list[str] = Field(default_factory=list)

    @field_validator("variables", mode="before")
    @classmethod
    def _validate_variables(cls, value: object) -> dict[str, str]:
        if not isinstance(value, Mapping):
            raise ValueError("variables must be a mapping")
        normalized: dict[str, str] = {}
        for raw_name, raw_value in value.items():
            name = _validate_identifier(raw_name, label="environment variable name")
            if not isinstance(raw_value, str):
                raise ValueError("environment variable values must be strings")
            if "\x00" in raw_value:
                raise ValueError("environment variable values cannot contain NUL")
            normalized[name] = raw_value
        return dict(sorted(normalized.items()))

    @field_validator("dependency_allowlist", mode="before")
    @classmethod
    def _validate_allowlist(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("dependency_allowlist must be a list")
        names = [
            _validate_identifier(item, label="dependency allowlist entry")
            for item in value
        ]
        if len(names) != len(set(names)):
            raise ValueError("dependency_allowlist entries must be unique")
        return sorted(names)


class ExecutionSpec(_ExecutionContractModel):
    schema_version: SchemaVersion = "1.0"
    spec_id: str
    question_id: str
    round_index: _NonNegativeStrictInt
    parent_execution_id: str | None = None
    mode: ExecutionMode
    entrypoint: str
    argv: list[str] = Field(default_factory=list)
    datasets: list[DatasetManifest] = Field(default_factory=list)
    required_artifacts: list[ArtifactRequirement] = Field(default_factory=list)
    required_metrics: list[MetricRequirement] = Field(default_factory=list)
    seed: _NonNegativeStrictInt
    resources: ResourceLimitRequest
    environment: _ExecutionEnvironment
    cleanup_policy: CleanupPolicy

    @field_validator("spec_id", "question_id", "entrypoint", mode="before")
    @classmethod
    def _validate_ids(cls, value: object, info: ValidationInfo) -> str:
        return _validate_identifier(value, label=info.field_name)

    @field_validator("parent_execution_id", mode="before")
    @classmethod
    def _validate_parent_id(cls, value: object) -> object:
        if value is None:
            return value
        return _validate_identifier(value, label="parent_execution_id")

    @field_validator("argv", mode="before")
    @classmethod
    def _validate_argv(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("argv must be a list")
        if not all(isinstance(item, str) for item in value):
            raise ValueError("argv items must be strings")
        if any("\x00" in item for item in value):
            raise ValueError("argv items cannot contain NUL")
        return list(value)

    @model_validator(mode="after")
    def _validate_declarations(self) -> "ExecutionSpec":
        dataset_ids = [item.dataset_id for item in self.datasets]
        artifact_ids = [item.artifact_id for item in self.required_artifacts]
        metric_names = [item.name for item in self.required_metrics]
        if len(dataset_ids) != len(set(dataset_ids)):
            raise ValueError("dataset_id values must be unique")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("artifact_id values must be unique")
        if len(metric_names) != len(set(metric_names)):
            raise ValueError("metric names must be unique")
        artifact_id_set = set(artifact_ids)
        if any(
            metric.artifact_id not in artifact_id_set
            for metric in self.required_metrics
        ):
            raise ValueError("metrics must reference declared artifacts")
        return self


class ExecutionResult(_ExecutionContractModel):
    """Persisted execution evidence with a fail-closed runner trust boundary."""

    _TRUTH_FIELDS: ClassVar[tuple[str, ...]] = (
        "runner_verified",
        "datasets_validated",
        "artifacts_validated",
        "metrics_validated",
        "provenance_complete",
        "scientific_result_usable",
        "actual_execution",
    )
    _RUNNER_EVIDENCE_FIELDS: ClassVar[tuple[str, ...]] = (
        "resource_enforcement",
    )

    schema_version: SchemaVersion = "1.0"
    execution_id: str
    spec_id: str
    question_id: str
    round_index: _NonNegativeStrictInt
    parent_execution_id: str | None = None
    mode: ExecutionMode
    status: ExecutionStatus
    entrypoint: str
    entrypoint_class: EntrypointClass | None = None
    seed: _NonNegativeStrictInt
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = Field(default=None, allow_inf_nan=False)
    process_started: StrictBool
    exit_code: StrictInt | None = None
    timed_out: StrictBool
    process_reaped: StrictBool = False
    process_alive_after_cleanup: StrictBool = False
    stdout: str = ""
    stderr: str = ""
    stdout_bytes: _NonNegativeStrictInt = 0
    stderr_bytes: _NonNegativeStrictInt = 0
    stdout_truncated: StrictBool = False
    stderr_truncated: StrictBool = False
    workspace_uri: str | None = None
    datasets: list[DatasetManifest] = Field(default_factory=list)
    artifacts: list[ArtifactManifest] = Field(default_factory=list)
    metrics: list[MetricRecord] = Field(default_factory=list)
    cleanup_status: CleanupStatus
    resource_enforcement: ResourceLimitEnforcement | None = None
    environment_fingerprint: EnvironmentFingerprint | None = None
    warnings: list[str] = Field(default_factory=list)
    error: ExecutionError | None = None
    runner_verified: StrictBool = False
    datasets_validated: StrictBool = False
    artifacts_validated: StrictBool = False
    metrics_validated: StrictBool = False
    provenance_complete: StrictBool = False
    scientific_result_usable: StrictBool = False
    actual_execution: StrictBool = False

    @model_validator(mode="before")
    @classmethod
    def _protect_runner_truth(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> object:
        if not isinstance(value, Mapping):
            return value
        trusted = (
            info.context is not None
            and info.context.get(_RUNNER_CONTEXT_KEY) is _RUNNER_ATTESTATION
        )
        if not trusted:
            for field_name in cls._TRUTH_FIELDS:
                if field_name in value and value[field_name] is not False:
                    raise ValueError("runner-owned truth cannot be caller supplied")
            for field_name in cls._RUNNER_EVIDENCE_FIELDS:
                if field_name in value and value[field_name] is not None:
                    raise ValueError(
                        "runner-owned evidence cannot be caller supplied"
                    )
        return value

    @field_validator(
        "execution_id",
        "spec_id",
        "question_id",
        "entrypoint",
        mode="before",
    )
    @classmethod
    def _validate_ids(cls, value: object, info: ValidationInfo) -> str:
        return _validate_identifier(value, label=info.field_name)

    @field_validator("parent_execution_id", mode="before")
    @classmethod
    def _validate_parent_id(cls, value: object) -> object:
        if value is None:
            return value
        return _validate_identifier(value, label="parent_execution_id")

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def _validate_times(cls, value: object, info: ValidationInfo) -> object:
        if value is None:
            return value
        return _validate_timestamp(value, label=info.field_name)

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def _validate_duration(cls, value: object) -> object:
        if value is None:
            return value
        return _validate_finite_number(
            value,
            label="duration_seconds",
            nonnegative=True,
        )

    @field_validator("stdout", "stderr", mode="before")
    @classmethod
    def _validate_stream_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("captured streams must be strings")
        return value

    @field_validator("workspace_uri", mode="before")
    @classmethod
    def _validate_workspace_uri(cls, value: object) -> object:
        if value is None:
            return value
        return _validate_safe_workspace_uri(value)

    @field_validator("warnings", mode="before")
    @classmethod
    def _validate_warnings(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("warnings must be a list")
        return [
            _validate_nonblank_text(item, label="warning", max_length=1_024)
            for item in value
        ]

    @model_validator(mode="after")
    def _validate_result_state(self, info: ValidationInfo) -> "ExecutionResult":
        object.__setattr__(
            self,
            "artifacts",
            sorted(self.artifacts, key=lambda item: item.artifact_id),
        )
        object.__setattr__(
            self,
            "metrics",
            sorted(self.metrics, key=lambda item: item.name),
        )
        self._validate_result_collections()
        self._validate_result_timing()
        self._validate_status_invariants()

        trusted = (
            info.context is not None
            and info.context.get(_RUNNER_CONTEXT_KEY) is _RUNNER_ATTESTATION
        )
        if not trusted:
            for field_name in self._TRUTH_FIELDS:
                object.__setattr__(self, field_name, False)
            for field_name in self._RUNNER_EVIDENCE_FIELDS:
                object.__setattr__(self, field_name, None)
            return self

        self._clamp_runner_evidence()
        actual = self._has_complete_actual_evidence()
        object.__setattr__(self, "runner_verified", actual)
        object.__setattr__(self, "actual_execution", actual)
        return self

    def _clamp_runner_evidence(self) -> None:
        valid_artifact_ids = {
            artifact.artifact_id
            for artifact in self.artifacts
            if artifact.validation_status == "valid"
        }
        if self.datasets_validated and not self.datasets:
            object.__setattr__(self, "datasets_validated", False)
        if self.artifacts_validated and (
            not self.artifacts or len(valid_artifact_ids) != len(self.artifacts)
        ):
            object.__setattr__(self, "artifacts_validated", False)
        if self.metrics_validated and (
            not self.metrics
            or any(
                metric.validation_status != "valid"
                or metric.artifact_id not in valid_artifact_ids
                for metric in self.metrics
            )
        ):
            object.__setattr__(self, "metrics_validated", False)
        fingerprint = self.environment_fingerprint
        if self.provenance_complete and (
            fingerprint is None
            or not fingerprint.git_available
            or fingerprint.git_dirty
            or fingerprint.git_sha is None
        ):
            object.__setattr__(self, "provenance_complete", False)
        if (
            self.scientific_result_usable
            and not self._has_usable_scientific_evidence()
        ):
            object.__setattr__(self, "scientific_result_usable", False)

    def _validate_result_collections(self) -> None:
        dataset_ids = [dataset.dataset_id for dataset in self.datasets]
        artifact_ids = [artifact.artifact_id for artifact in self.artifacts]
        metric_names = [metric.name for metric in self.metrics]
        if len(dataset_ids) != len(set(dataset_ids)):
            raise ValueError("dataset_id values must be unique")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("artifact_id values must be unique")
        if len(metric_names) != len(set(metric_names)):
            raise ValueError("metric names must be unique")
        artifact_id_set = set(artifact_ids)
        if any(metric.artifact_id not in artifact_id_set for metric in self.metrics):
            raise ValueError("metrics must reference collected artifacts")
        if any(metric.round_index != self.round_index for metric in self.metrics):
            raise ValueError("metric round_index must match the result")
        if (
            self.environment_fingerprint is not None
            and self.environment_fingerprint.seed != self.seed
        ):
            raise ValueError("environment seed must match the result")

    def _validate_result_timing(self) -> None:
        if self.started_at is not None and self.finished_at is not None:
            started = _parse_aware_datetime(self.started_at, label="started_at")
            finished = _parse_aware_datetime(self.finished_at, label="finished_at")
            if finished < started:
                raise ValueError("finished_at cannot precede started_at")
        if self.status == "running" and self.finished_at is not None:
            raise ValueError("running results cannot have finished_at")

    def _validate_status_invariants(self) -> None:
        if self.status == "planned":
            if self.process_started or self.exit_code is not None or self.timed_out:
                raise ValueError("planned results cannot contain process outcomes")
        elif self.status == "rejected":
            if self.process_started or self.exit_code is not None or self.timed_out:
                raise ValueError("rejected results cannot contain process outcomes")
        elif self.status == "running":
            if not self.process_started or self.exit_code is not None or self.timed_out:
                raise ValueError("running results require an active process state")
        elif self.status == "succeeded":
            if self.timed_out or self.error is not None:
                raise ValueError("succeeded results cannot contain an execution error")
            if self.mode in {"actual", "test"}:
                if not self.process_started or self.exit_code != 0:
                    raise ValueError("process-backed success requires exit code zero")
            elif self.process_started or self.exit_code is not None:
                raise ValueError("non-process success cannot contain process outcomes")
        elif self.status == "failed":
            if self.error is None:
                raise ValueError("failed results require a structured error")
        elif self.status == "timed_out":
            if (
                not self.process_started
                or not self.timed_out
                or self.error is None
                or self.error.code != "timeout"
            ):
                raise ValueError("timed-out results require timeout evidence")

        if self.status != "timed_out" and self.timed_out:
            raise ValueError("timed_out is only valid with timed_out status")
        if self.exit_code is not None and not self.process_started:
            raise ValueError("exit_code requires a started process")
        if self.process_reaped and not self.process_started:
            raise ValueError("only a started process can be reaped")
        if self.process_alive_after_cleanup and (
            not self.process_started or self.process_reaped
        ):
            raise ValueError("process lifecycle evidence is contradictory")
        if self.status == "succeeded" and self.exit_code not in {None, 0}:
            raise ValueError("nonzero exit codes cannot succeed")
        if self.cleanup_status == "failed" and self.status == "succeeded":
            raise ValueError("cleanup failure cannot be reported as success")
        if self.mode in {"dry_run", "mock"} and self.process_started:
            raise ValueError("dry-run and mock modes cannot start a process")
        observed_metrics = [
            metric for metric in self.metrics if metric.source == "observed"
        ]
        if self.mode in {"dry_run", "mock"} and observed_metrics:
            raise ValueError("dry-run and mock results cannot contain observations")
        if self.status in {"failed", "timed_out"} and observed_metrics:
            raise ValueError("failed results cannot publish observed metrics")
        if self.status == "succeeded" and any(
            artifact.required and artifact.validation_status != "valid"
            for artifact in self.artifacts
        ):
            raise ValueError("success cannot omit a required artifact")
        if self.error is not None and self.error.code in {
            "artifact_missing",
            "checksum_mismatch",
            "cleanup_failed",
        } and self.status == "succeeded":
            raise ValueError("integrity failures cannot be reported as success")

    def _has_complete_actual_evidence(self) -> bool:
        # Scheme B derives actual_execution from the complete attested evidence
        # chain; it is never accepted as a caller-selected fact.
        return (
            self.scientific_result_usable
            and self._has_usable_scientific_evidence()
        )

    def _has_usable_scientific_evidence(self) -> bool:
        fingerprint = self.environment_fingerprint
        if (
            self.mode != "actual"
            or self.entrypoint_class != "scientific"
            or self.status != "succeeded"
            or not self.process_started
            or self.exit_code != 0
            or self.timed_out
            or self.error is not None
            or not self.process_reaped
            or self.process_alive_after_cleanup
            or not self.datasets_validated
            or not self.artifacts_validated
            or not self.metrics_validated
            or not self.provenance_complete
            or self.cleanup_status not in {"succeeded", "preserved"}
            or fingerprint is None
            or not fingerprint.git_available
            or fingerprint.git_dirty
            or fingerprint.git_sha is None
            or not self.datasets
            or not self.artifacts
            or not self.metrics
        ):
            return False
        valid_artifact_ids = {
            artifact.artifact_id
            for artifact in self.artifacts
            if artifact.validation_status == "valid"
        }
        return (
            len(valid_artifact_ids) == len(self.artifacts)
            and all(
                metric.source == "observed"
                and metric.validation_status == "valid"
                and metric.artifact_id in valid_artifact_ids
                for metric in self.metrics
            )
        )

    @classmethod
    def model_validate_untrusted(
        cls,
        payload: object,
    ) -> "ExecutionResult":
        """Validate caller data without restoring runner attestation."""

        if isinstance(payload, cls):
            payload = payload.model_dump(mode="python")
        elif isinstance(payload, Mapping):
            payload = dict(payload)
        return cls.model_validate(payload)

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> "ExecutionResult":
        """Return a revalidated copy without preserving runner attestation."""

        del deep
        updates = {} if update is None else dict(update)
        for field_name in self._TRUTH_FIELDS:
            if field_name in updates and updates[field_name] is not False:
                raise ValueError("runner-owned truth cannot be caller supplied")
        for field_name in self._RUNNER_EVIDENCE_FIELDS:
            if field_name in updates and updates[field_name] is not None:
                raise ValueError(
                    "runner-owned evidence cannot be caller supplied"
                )

        payload = self.model_dump(mode="python")
        payload.update(updates)
        for field_name in self._TRUTH_FIELDS:
            payload[field_name] = False
        for field_name in self._RUNNER_EVIDENCE_FIELDS:
            payload[field_name] = None
        return type(self).model_validate_untrusted(payload)

    @classmethod
    def model_construct(
        cls,
        _fields_set: set[str] | None = None,
        **values: Any,
    ) -> "ExecutionResult":
        """Construct only fail-closed untrusted results without validation."""

        for field_name in cls._TRUTH_FIELDS:
            if field_name in values and values[field_name] is not False:
                raise ValueError("runner-owned truth cannot be caller supplied")
        for field_name in cls._RUNNER_EVIDENCE_FIELDS:
            if field_name in values and values[field_name] is not None:
                raise ValueError(
                    "runner-owned evidence cannot be caller supplied"
                )

        payload = dict(values)
        for field_name in cls._TRUTH_FIELDS:
            payload[field_name] = False
        for field_name in cls._RUNNER_EVIDENCE_FIELDS:
            payload[field_name] = None
        return super().model_construct(_fields_set=_fields_set, **payload)

    @classmethod
    def _from_runner(
        cls,
        payload: Mapping[str, Any],
        *,
        attestation: object | None = None,
    ) -> "ExecutionResult":
        """Build a result through the module-private runner attestation path."""

        if attestation is not _RUNNER_ATTESTATION:
            raise ValueError("runner attestation is invalid")
        return cls.model_validate(
            dict(payload),
            context={_RUNNER_CONTEXT_KEY: _RUNNER_ATTESTATION},
        )


@dataclass(frozen=True, slots=True)
class _LegacyExecutionNormalization:
    legacy_claim: bool | None
    canonical_actual_execution: bool
    warning: str | None
    error: str | None


class LegacyExecutionMetadataAdapter:
    """Fail-closed adapter for the historical truthiness-prone metadata field."""

    @staticmethod
    def normalize(metadata: Mapping[str, object]) -> _LegacyExecutionNormalization:
        if not isinstance(metadata, Mapping):
            return _LegacyExecutionNormalization(
                legacy_claim=None,
                canonical_actual_execution=False,
                warning=None,
                error="legacy_actual_execution_invalid",
            )
        if "actual_execution" not in metadata:
            return _LegacyExecutionNormalization(
                legacy_claim=None,
                canonical_actual_execution=False,
                warning="legacy_missing",
                error=None,
            )

        value = metadata["actual_execution"]
        if value is None:
            return _LegacyExecutionNormalization(
                legacy_claim=None,
                canonical_actual_execution=False,
                warning="legacy_null",
                error=None,
            )
        if value is True or (type(value) is int and value == 1):
            return _LegacyExecutionNormalization(
                legacy_claim=True,
                canonical_actual_execution=False,
                warning="legacy_unverified_true",
                error=None,
            )
        if value is False or (type(value) is int and value == 0):
            return _LegacyExecutionNormalization(
                legacy_claim=False,
                canonical_actual_execution=False,
                warning=None,
                error=None,
            )
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized == "":
                return _LegacyExecutionNormalization(
                    legacy_claim=None,
                    canonical_actual_execution=False,
                    warning="legacy_empty",
                    error=None,
                )
            if normalized in {"true", "1"}:
                return _LegacyExecutionNormalization(
                    legacy_claim=True,
                    canonical_actual_execution=False,
                    warning="legacy_unverified_true",
                    error=None,
                )
            if normalized in {"false", "0"}:
                return _LegacyExecutionNormalization(
                    legacy_claim=False,
                    canonical_actual_execution=False,
                    warning=None,
                    error=None,
                )
        return _LegacyExecutionNormalization(
            legacy_claim=None,
            canonical_actual_execution=False,
            warning=None,
            error="legacy_actual_execution_invalid",
        )
