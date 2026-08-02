"""Deterministic delivery index for validated Wave B outputs."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final

from app.batch.errors import BatchRunnerError
from app.batch.output_validation import (
    ArtifactFileRecord,
    ArtifactManifest,
    ArtifactValidationResult,
    compute_file_sha256,
)
from app.contracts.batch import (
    REQUIRED_ARTIFACTS,
    BatchJob,
    JobStatus,
    ResultKind,
    SourceKind,
)


DELIVERY_INDEX_VERSION: Final[str] = "t07.delivery-index.v1"
SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class QuestionDeliveryRecord:
    batch_id: str
    question_id: str
    status: str
    source_hash: str
    input_hash: str
    output_contract_version: str
    route_id: str
    provider: str
    model: str
    model_version: str
    prompt_version: str
    prompt_hash: str | None
    schema_version: str
    artifacts: tuple[ArtifactFileRecord, ...]
    input_tokens: int
    output_tokens: int
    tokens_used: int
    duration_seconds: float
    attempts: int
    failure_code: str | None
    validation_status: str
    validation_error_codes: tuple[str, ...]
    result_kind: str
    actual: bool
    mock: bool
    synthetic: bool
    completed: bool

    def __post_init__(self) -> None:
        required_text = (
            "batch_id",
            "question_id",
            "status",
            "output_contract_version",
            "route_id",
            "provider",
            "model",
            "model_version",
            "prompt_version",
            "schema_version",
            "validation_status",
            "result_kind",
        )
        if any(not getattr(self, field_name).strip() for field_name in required_text):
            raise ValueError("delivery text fields must not be empty")
        if not SHA256.fullmatch(self.source_hash):
            raise ValueError("source_hash must be lowercase SHA-256")
        if not SHA256.fullmatch(self.input_hash):
            raise ValueError("input_hash must be lowercase SHA-256")
        if self.prompt_hash is not None and not SHA256.fullmatch(self.prompt_hash):
            raise ValueError("prompt_hash must be lowercase SHA-256 or null")
        if min(self.input_tokens, self.output_tokens, self.tokens_used) < 0:
            raise ValueError("token counts must be non-negative")
        if self.duration_seconds < 0 or self.attempts < 0:
            raise ValueError("duration and attempts must be non-negative")
        if self.validation_status not in {"passed", "failed"}:
            raise ValueError("validation_status must be passed or failed")
        if (self.validation_status == "passed") == bool(
            self.validation_error_codes
        ):
            raise ValueError("validation status must be derived from error codes")
        if self.actual != (self.result_kind == ResultKind.ACTUAL.value):
            raise ValueError("actual must be derived from result_kind")
        if self.mock != (self.result_kind == ResultKind.MOCK.value):
            raise ValueError("mock must be derived from result_kind")

        artifact_names = [artifact.name for artifact in self.artifacts]
        if len(artifact_names) != len(set(artifact_names)):
            raise ValueError("artifacts contains duplicate names")
        for artifact in self.artifacts:
            pure = PurePosixPath(artifact.path.replace("\\", "/"))
            if (
                PurePosixPath(artifact.path).is_absolute()
                or PureWindowsPath(artifact.path).is_absolute()
                or ".." in pure.parts
                or not pure.parts
                or pure.parts[0] != self.question_id
            ):
                raise ValueError("artifact paths must be question-scoped")

        artifact_set_complete = set(REQUIRED_ARTIFACTS).issubset(artifact_names)
        expected_completed = (
            self.status == JobStatus.COMPLETED.value
            and self.actual
            and not self.mock
            and not self.synthetic
            and self.validation_status == "passed"
            and artifact_set_complete
            and self.prompt_hash is not None
            and self.provider != "none"
            and self.model != "none"
        )
        if self.completed != expected_completed:
            raise ValueError(
                "completed must be derived from valid actual artifacts"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "question_id": self.question_id,
            "status": self.status,
            "source_hash": self.source_hash,
            "input_hash": self.input_hash,
            "output_contract_version": self.output_contract_version,
            "route_id": self.route_id,
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "schema_version": self.schema_version,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens_used": self.tokens_used,
            "duration_seconds": self.duration_seconds,
            "attempts": self.attempts,
            "failure_code": self.failure_code,
            "validation_status": self.validation_status,
            "validation_error_codes": list(self.validation_error_codes),
            "result_kind": self.result_kind,
            "actual": self.actual,
            "mock": self.mock,
            "synthetic": self.synthetic,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QuestionDeliveryRecord":
        try:
            return cls(
                batch_id=str(value["batch_id"]),
                question_id=str(value["question_id"]),
                status=str(value["status"]),
                source_hash=str(value["source_hash"]),
                input_hash=str(value["input_hash"]),
                output_contract_version=str(value["output_contract_version"]),
                route_id=str(value["route_id"]),
                provider=str(value["provider"]),
                model=str(value["model"]),
                model_version=str(value["model_version"]),
                prompt_version=str(value["prompt_version"]),
                prompt_hash=(
                    None
                    if value.get("prompt_hash") is None
                    else str(value["prompt_hash"])
                ),
                schema_version=str(value["schema_version"]),
                artifacts=tuple(
                    ArtifactFileRecord.from_dict(item)
                    for item in value.get("artifacts", [])
                ),
                input_tokens=int(value["input_tokens"]),
                output_tokens=int(value["output_tokens"]),
                tokens_used=int(value["tokens_used"]),
                duration_seconds=float(value["duration_seconds"]),
                attempts=int(value["attempts"]),
                failure_code=(
                    None
                    if value.get("failure_code") is None
                    else str(value["failure_code"])
                ),
                validation_status=str(value["validation_status"]),
                validation_error_codes=tuple(
                    str(item)
                    for item in value.get("validation_error_codes", [])
                ),
                result_kind=str(value["result_kind"]),
                actual=bool(value["actual"]),
                mock=bool(value["mock"]),
                synthetic=bool(value["synthetic"]),
                completed=bool(value["completed"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BatchRunnerError(
                "DELIVERY_RECORD_INVALID",
                "delivery record is not valid",
            ) from exc


@dataclass(frozen=True, slots=True)
class DeliveryIndex:
    index_version: str
    batch_id: str
    records: tuple[QuestionDeliveryRecord, ...]
    total: int
    status_counts: Mapping[str, int]
    completed: int
    index_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index_version": self.index_version,
            "batch_id": self.batch_id,
            "records": [record.to_dict() for record in self.records],
            "total": self.total,
            "status_counts": dict(self.status_counts),
            "completed": self.completed,
            "index_sha256": self.index_sha256,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "DeliveryIndex":
        try:
            raw = json.loads(payload)
            if not isinstance(raw, dict):
                raise TypeError("delivery index must be an object")
            index = cls(
                index_version=str(raw["index_version"]),
                batch_id=str(raw["batch_id"]),
                records=tuple(
                    QuestionDeliveryRecord.from_dict(item)
                    for item in raw.get("records", [])
                ),
                total=int(raw["total"]),
                status_counts={
                    str(key): int(value)
                    for key, value in dict(raw["status_counts"]).items()
                },
                completed=int(raw["completed"]),
                index_sha256=str(raw["index_sha256"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BatchRunnerError(
                "DELIVERY_INDEX_JSON_INVALID",
                "delivery index JSON is not valid",
            ) from exc
        validate_delivery_index(index)
        return index


def build_question_delivery_record(
    job: BatchJob,
    source_kind: SourceKind | str,
    validation_result: ArtifactValidationResult,
    artifact_manifest: ArtifactManifest | None,
    *,
    output_contract_version: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    duration_seconds: float = 0.0,
) -> QuestionDeliveryRecord:
    """Derive one record; no caller-supplied completed flag is accepted."""

    if not isinstance(job, BatchJob):
        raise TypeError("job must be a BatchJob")
    if not isinstance(validation_result, ArtifactValidationResult):
        raise TypeError("validation_result must be ArtifactValidationResult")
    source = _enum_value(source_kind)
    status = _enum_value(job.status)
    result_kind = _enum_value(job.result_kind)
    artifacts: tuple[ArtifactFileRecord, ...] = ()
    if artifact_manifest is not None:
        if (
            artifact_manifest.batch_id != job.batch_id
            or artifact_manifest.question_id != job.question_id
            or artifact_manifest.validation_status
            != validation_result.validation_status
        ):
            raise BatchRunnerError(
                "DELIVERY_ARTIFACT_IDENTITY_MISMATCH",
                "artifact manifest does not match job validation identity",
            )
        artifacts = artifact_manifest.artifacts

    artifact_set_complete = set(REQUIRED_ARTIFACTS).issubset(
        artifact.name for artifact in artifacts
    )
    actual = result_kind == ResultKind.ACTUAL.value
    mock = result_kind == ResultKind.MOCK.value
    synthetic = source == SourceKind.SYNTHETIC.value
    completed = (
        status == JobStatus.COMPLETED.value
        and actual
        and not mock
        and not synthetic
        and validation_result.passed
        and artifact_set_complete
        and job.model_route.prompt_hash is not None
        and job.model_route.provider != "none"
        and job.model_route.model != "none"
    )
    failure_code = job.failures[-1].error_code if job.failures else None
    version = (
        artifact_manifest.output_contract_version
        if artifact_manifest is not None
        else output_contract_version or job.schema_version
    )
    return QuestionDeliveryRecord(
        batch_id=job.batch_id,
        question_id=job.question_id,
        status=status,
        source_hash=job.source_hash,
        input_hash=job.input_hash,
        output_contract_version=version,
        route_id=job.model_route.route_id,
        provider=job.model_route.provider,
        model=job.model_route.model,
        model_version=job.model_route.model_version,
        prompt_version=job.model_route.prompt_version,
        prompt_hash=job.model_route.prompt_hash,
        schema_version=job.schema_version,
        artifacts=artifacts,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tokens_used=job.budget.tokens_used,
        duration_seconds=float(duration_seconds),
        attempts=job.attempt,
        failure_code=failure_code,
        validation_status=validation_result.validation_status,
        validation_error_codes=validation_result.error_codes,
        result_kind=result_kind,
        actual=actual,
        mock=mock,
        synthetic=synthetic,
        completed=completed,
    )


def build_delivery_index(
    batch_id: str,
    records: Sequence[QuestionDeliveryRecord],
    *,
    index_version: str = DELIVERY_INDEX_VERSION,
) -> DeliveryIndex:
    """Sort records and derive every aggregate plus a canonical checksum."""

    if not isinstance(batch_id, str) or not batch_id.strip():
        raise BatchRunnerError(
            "DELIVERY_BATCH_INVALID",
            "delivery batch_id must not be empty",
        )
    if not isinstance(index_version, str) or not index_version.strip():
        raise BatchRunnerError(
            "DELIVERY_VERSION_INVALID",
            "delivery index_version must not be empty",
        )
    ordered = tuple(sorted(records, key=lambda record: record.question_id))
    if not all(isinstance(record, QuestionDeliveryRecord) for record in ordered):
        raise TypeError("records must contain QuestionDeliveryRecord values")
    _validate_record_identity(batch_id, ordered)
    total = len(ordered)
    status_counts = dict(
        sorted(Counter(record.status for record in ordered).items())
    )
    completed = sum(record.completed for record in ordered)
    checksum = compute_delivery_index_sha256(
        batch_id,
        ordered,
        index_version=index_version,
    )
    index = DeliveryIndex(
        index_version=index_version,
        batch_id=batch_id,
        records=ordered,
        total=total,
        status_counts=status_counts,
        completed=completed,
        index_sha256=checksum,
    )
    validate_delivery_index(index)
    return index


def compute_delivery_index_sha256(
    batch_id: str,
    records: Sequence[QuestionDeliveryRecord],
    *,
    index_version: str = DELIVERY_INDEX_VERSION,
) -> str:
    """Hash canonical content that intentionally excludes index_sha256."""

    ordered = tuple(sorted(records, key=lambda record: record.question_id))
    _validate_record_identity(batch_id, ordered)
    payload = _checksum_payload(index_version, batch_id, ordered)
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def validate_delivery_index(
    index: DeliveryIndex,
    *,
    artifact_root: str | Path | None = None,
) -> None:
    """Reject aggregate, checksum, identity, and physical-hash mismatches."""

    if not isinstance(index, DeliveryIndex):
        raise TypeError("index must be DeliveryIndex")
    _validate_record_identity(index.batch_id, index.records)
    expected = _checksum_payload(
        index.index_version,
        index.batch_id,
        index.records,
    )
    if index.total != expected["total"]:
        raise BatchRunnerError(
            "DELIVERY_TOTAL_MISMATCH",
            "total must be derived from records",
        )
    if dict(index.status_counts) != expected["status_counts"]:
        raise BatchRunnerError(
            "DELIVERY_STATUS_COUNTS_MISMATCH",
            "status_counts must be derived from records",
        )
    if index.completed != expected["completed"]:
        raise BatchRunnerError(
            "DELIVERY_COMPLETED_MISMATCH",
            "completed must be derived from validated records",
        )
    expected_checksum = hashlib.sha256(_canonical_json(expected)).hexdigest()
    if index.index_sha256 != expected_checksum:
        raise BatchRunnerError(
            "DELIVERY_CHECKSUM_MISMATCH",
            "index checksum does not match non-self-referential content",
        )

    if artifact_root is not None:
        root = Path(artifact_root).resolve(strict=False)
        if root.is_symlink():
            raise BatchRunnerError(
                "DELIVERY_ARTIFACT_PATH_INVALID",
                "artifact root cannot be a symlink",
            )
        for record in index.records:
            for artifact in record.artifacts:
                pure = PurePosixPath(artifact.path.replace("\\", "/"))
                if (
                    PurePosixPath(artifact.path).is_absolute()
                    or PureWindowsPath(artifact.path).is_absolute()
                    or ".." in pure.parts
                    or not pure.parts
                    or pure.parts[0] != record.question_id
                ):
                    raise BatchRunnerError(
                        "DELIVERY_ARTIFACT_PATH_INVALID",
                        f"Invalid artifact path: {artifact.path}",
                    )
                target = root.joinpath(*pure.parts)
                if target.is_symlink() or not target.is_file():
                    raise BatchRunnerError(
                        "DELIVERY_ARTIFACT_MISSING",
                        f"Indexed artifact is not a regular file: {target}",
                    )
                resolved = target.resolve(strict=True)
                if not _is_within(resolved, root):
                    raise BatchRunnerError(
                        "DELIVERY_ARTIFACT_PATH_INVALID",
                        f"Indexed artifact escapes its root: {target}",
                    )
                if compute_file_sha256(target) != artifact.sha256:
                    raise BatchRunnerError(
                        "DELIVERY_ARTIFACT_HASH_MISMATCH",
                        f"Artifact hash mismatch: {target}",
                    )


def _validate_record_identity(
    batch_id: str,
    records: Sequence[QuestionDeliveryRecord],
) -> None:
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, QuestionDeliveryRecord):
            raise TypeError("records must contain QuestionDeliveryRecord values")
        if record.batch_id != batch_id:
            raise BatchRunnerError(
                "DELIVERY_BATCH_MISMATCH",
                "record batch_id does not match delivery index",
            )
        if record.question_id in seen:
            raise BatchRunnerError(
                "DELIVERY_DUPLICATE_QUESTION_ID",
                f"Duplicate question_id: {record.question_id}",
            )
        seen.add(record.question_id)


def _checksum_payload(
    index_version: str,
    batch_id: str,
    records: Sequence[QuestionDeliveryRecord],
) -> dict[str, Any]:
    ordered = tuple(sorted(records, key=lambda record: record.question_id))
    return {
        "index_version": index_version,
        "batch_id": batch_id,
        "records": [record.to_dict() for record in ordered],
        "total": len(ordered),
        "status_counts": dict(
            sorted(Counter(record.status for record in ordered).items())
        ),
        "completed": sum(record.completed for record in ordered),
    }


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((candidate, parent)) == os.path.commonpath(
            (parent, parent)
        )
    except ValueError:
        return False
