"""Physical artifact validation around the frozen Wave A output contract."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from app.batch.errors import BatchRunnerError
from app.batch.output_layout import (
    QuestionOutputPaths,
    list_required_artifact_paths,
    validate_output_path_boundary,
)
from app.contracts.batch import (
    REQUIRED_ARTIFACTS,
    STANDARD_OUTPUT_FIELDS,
    BatchJob,
    JobStatus,
    ResultKind,
    SourceKind,
)


ValidationStatus = Literal["passed", "failed"]
SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ArtifactValidationIssue:
    error_code: str
    artifact: str | None
    message: str

    def __post_init__(self) -> None:
        if not self.error_code.strip() or not self.message.strip():
            raise ValueError("validation issue code and message must not be empty")


@dataclass(frozen=True, slots=True)
class ArtifactFileRecord:
    name: str
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.name or not self.path:
            raise ValueError("artifact name and path must not be empty")
        if not SHA256.fullmatch(self.sha256):
            raise ValueError("artifact sha256 must be lowercase SHA-256")
        if self.size_bytes <= 0:
            raise ValueError("artifact size_bytes must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArtifactFileRecord":
        return cls(
            name=str(value["name"]),
            path=str(value["path"]),
            sha256=str(value["sha256"]),
            size_bytes=int(value["size_bytes"]),
        )


@dataclass(frozen=True, slots=True)
class ArtifactValidationResult:
    validation_status: ValidationStatus
    issues: tuple[ArtifactValidationIssue, ...]
    artifacts: tuple[ArtifactFileRecord, ...]

    def __post_init__(self) -> None:
        expected = "failed" if self.issues else "passed"
        if self.validation_status != expected:
            raise ValueError("validation_status must be derived from issues")

    @property
    def passed(self) -> bool:
        return self.validation_status == "passed"

    @property
    def error_codes(self) -> tuple[str, ...]:
        return tuple(issue.error_code for issue in self.issues)


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Non-self-referential manifest for required and frozen extra artifacts."""

    batch_id: str
    question_id: str
    output_contract_version: str
    validation_status: ValidationStatus
    artifacts: tuple[ArtifactFileRecord, ...]
    manifest_sha256: str

    def __post_init__(self) -> None:
        if not self.batch_id or not self.question_id:
            raise ValueError("artifact manifest identity must not be empty")
        if not self.output_contract_version:
            raise ValueError("output_contract_version must not be empty")
        if not SHA256.fullmatch(self.manifest_sha256):
            raise ValueError("manifest_sha256 must be lowercase SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "question_id": self.question_id,
            "output_contract_version": self.output_contract_version,
            "validation_status": self.validation_status,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "manifest_sha256": self.manifest_sha256,
        }


def compute_file_sha256(path: str | Path) -> str:
    """Hash one existing non-empty regular file without following symlinks."""

    candidate = Path(path)
    issue = _inspect_required_file(candidate, candidate.name)
    if issue is not None:
        raise BatchRunnerError(issue.error_code, issue.message)
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_json_artifact(
    path: str | Path,
    expected_top_type: type[dict[str, Any]] | type[list[Any]],
) -> dict[str, Any] | list[Any]:
    """Parse UTF-8 JSON and require the declared top-level container type."""

    if expected_top_type not in {dict, list}:
        raise TypeError("expected_top_type must be dict or list")
    candidate = Path(path)
    issue = _inspect_required_file(candidate, candidate.name)
    if issue is not None:
        raise BatchRunnerError(issue.error_code, issue.message)
    try:
        with candidate.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "ARTIFACT_JSON_INVALID",
            f"Invalid UTF-8 JSON artifact: {candidate}",
        ) from exc
    if not isinstance(value, expected_top_type):
        raise BatchRunnerError(
            "ARTIFACT_JSON_INVALID",
            (
                f"{candidate.name} must contain a top-level "
                f"{expected_top_type.__name__}"
            ),
        )
    return value


def validate_question_identity(
    job: BatchJob,
    result_json: Mapping[str, Any] | None,
    evidence_cards_json: list[Any] | None,
    agent_trace_json: Mapping[str, Any] | None,
) -> tuple[ArtifactValidationIssue, ...]:
    """Bind every JSON record to the current job snapshot."""

    if not isinstance(job, BatchJob):
        raise TypeError("job must be a BatchJob")
    issues: list[ArtifactValidationIssue] = []
    if result_json is not None:
        issues.extend(_identity_issues(job, result_json, "result.json"))

    if evidence_cards_json is not None:
        seen_evidence_ids: set[str] = set()
        for index, raw_card in enumerate(evidence_cards_json):
            label = f"evidence_cards.json[{index}]"
            if not isinstance(raw_card, Mapping):
                issues.append(
                    ArtifactValidationIssue(
                        "ARTIFACT_JSON_INVALID",
                        "evidence_cards.json",
                        f"{label} must be an object",
                    )
                )
                continue
            issues.extend(_identity_issues(job, raw_card, label))
            evidence_id = raw_card.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                issues.append(
                    ArtifactValidationIssue(
                        "ARTIFACT_JSON_INVALID",
                        "evidence_cards.json",
                        f"{label} requires a non-empty evidence_id",
                    )
                )
            elif evidence_id in seen_evidence_ids:
                issues.append(
                    ArtifactValidationIssue(
                        "ARTIFACT_JSON_INVALID",
                        "evidence_cards.json",
                        f"Duplicate evidence_id in one question: {evidence_id}",
                    )
                )
            else:
                seen_evidence_ids.add(evidence_id)
            if not _source_is_auditable(raw_card.get("source")):
                issues.append(
                    ArtifactValidationIssue(
                        "ARTIFACT_JSON_INVALID",
                        "evidence_cards.json",
                        f"{label} requires auditable source kind and reference",
                    )
                )

    if agent_trace_json is not None:
        issues.extend(
            _identity_issues(job, agent_trace_json, "agent_trace.json")
        )
    return tuple(issues)


def validate_required_artifacts(
    job: BatchJob,
    paths: QuestionOutputPaths,
) -> ArtifactValidationResult:
    """Validate contract completeness and all five physical artifacts."""

    if not isinstance(job, BatchJob):
        raise TypeError("job must be a BatchJob")
    if not isinstance(paths, QuestionOutputPaths):
        raise TypeError("paths must be QuestionOutputPaths")
    issues: list[ArtifactValidationIssue] = []
    records: list[ArtifactFileRecord] = []
    parsed_json: dict[str, dict[str, Any] | list[Any]] = {}

    if paths.question_id != job.question_id:
        issues.append(
            ArtifactValidationIssue(
                "ARTIFACT_QUESTION_MISMATCH",
                None,
                "QuestionOutputPaths belongs to another question",
            )
        )

    missing_fields = job.output_contract.missing_fields()
    missing_contract_artifacts = job.output_contract.missing_artifacts()
    if missing_fields or missing_contract_artifacts:
        issues.append(
            ArtifactValidationIssue(
                "OUTPUT_CONTRACT_INCOMPLETE",
                None,
                (
                    f"missing_fields={missing_fields}; "
                    f"missing_artifacts={missing_contract_artifacts}"
                ),
            )
        )

    for artifact_name, artifact_path in zip(
        REQUIRED_ARTIFACTS,
        list_required_artifact_paths(paths),
        strict=True,
    ):
        relative = PurePosixPath(job.question_id, artifact_name).as_posix()
        try:
            bounded = validate_output_path_boundary(
                paths.batch_root,
                job.question_id,
                relative,
            )
        except BatchRunnerError as exc:
            issues.append(
                ArtifactValidationIssue(
                    exc.error_code,
                    artifact_name,
                    str(exc),
                )
            )
            continue
        if artifact_path.absolute() != bounded.absolute():
            issues.append(
                ArtifactValidationIssue(
                    "OUTPUT_PATH_INVALID",
                    artifact_name,
                    "Artifact path differs from deterministic layout",
                )
            )
            continue
        declared = job.output_contract.artifacts.get(artifact_name)
        if declared is not None and not _declared_path_is_owned(
            declared,
            job.batch_id,
            job.question_id,
            artifact_name,
        ):
            issues.append(
                ArtifactValidationIssue(
                    "OUTPUT_PATH_INVALID",
                    artifact_name,
                    "OutputContract artifact path is not question-scoped",
                )
            )

        issue = _inspect_required_file(artifact_path, artifact_name)
        if issue is not None:
            issues.append(issue)
            continue
        if artifact_name == "report.pdf":
            with artifact_path.open("rb") as stream:
                if stream.read(5) != b"%PDF-":
                    issues.append(
                        ArtifactValidationIssue(
                            "PDF_SIGNATURE_INVALID",
                            artifact_name,
                            "report.pdf does not begin with a PDF signature",
                        )
                    )
        elif artifact_name == "result.json":
            parsed = _capture_json(artifact_path, dict, issues)
            if parsed is not None:
                parsed_json[artifact_name] = parsed
        elif artifact_name == "evidence_cards.json":
            parsed = _capture_json(artifact_path, list, issues)
            if parsed is not None:
                parsed_json[artifact_name] = parsed
        elif artifact_name == "agent_trace.json":
            parsed = _capture_json(artifact_path, dict, issues)
            if parsed is not None:
                parsed_json[artifact_name] = parsed

        records.append(
            ArtifactFileRecord(
                name=artifact_name,
                path=relative,
                sha256=compute_file_sha256(artifact_path),
                size_bytes=artifact_path.stat().st_size,
            )
        )

    issues.extend(
        validate_question_identity(
            job,
            _as_mapping(parsed_json.get("result.json")),
            _as_list(parsed_json.get("evidence_cards.json")),
            _as_mapping(parsed_json.get("agent_trace.json")),
        )
    )
    issues.extend(
        _validate_result_fields(
            job,
            _as_mapping(parsed_json.get("result.json")),
        )
    )
    return _result(issues, records)


def validate_actual_completion(
    job: BatchJob,
    source_kind: SourceKind | str,
    validation_result: ArtifactValidationResult,
) -> ArtifactValidationResult:
    """Require completed/actual/non-Mock/production and valid artifacts."""

    if not isinstance(job, BatchJob):
        raise TypeError("job must be a BatchJob")
    if not isinstance(validation_result, ArtifactValidationResult):
        raise TypeError("validation_result must be ArtifactValidationResult")
    issues = list(validation_result.issues)
    valid = (
        _enum_value(job.status) == JobStatus.COMPLETED.value
        and _enum_value(job.result_kind) == ResultKind.ACTUAL.value
        and not job.mock
        and _enum_value(source_kind) == SourceKind.PRODUCTION.value
        and validation_result.passed
    )
    if not valid:
        issues.append(
            ArtifactValidationIssue(
                "ACTUAL_STATUS_INVALID",
                None,
                (
                    "completion requires completed/actual, non-Mock, "
                    "production, fully validated output"
                ),
            )
        )
    return _result(issues, list(validation_result.artifacts))


def build_artifact_manifest(
    job: BatchJob,
    paths: QuestionOutputPaths,
    validation_result: ArtifactValidationResult,
    *,
    output_contract_version: str | None = None,
    supplemental_artifact_paths: Mapping[str, str | Path] | None = None,
) -> ArtifactManifest:
    """Package real file metadata while excluding the manifest's own hash.

    The five Wave B files remain mandatory. WB5 may add the separately frozen
    ``llm_call_audit.json``; it is validated, hashed, and carried into the
    delivery index through the manifest instead of changing the base contract.
    """

    if paths.question_id != job.question_id or not validation_result.passed:
        raise BatchRunnerError(
            "OUTPUT_CONTRACT_INCOMPLETE",
            "Cannot build artifact manifest from failed validation",
        )
    names = {artifact.name for artifact in validation_result.artifacts}
    if names != set(REQUIRED_ARTIFACTS):
        raise BatchRunnerError(
            "OUTPUT_CONTRACT_INCOMPLETE",
            "Artifact manifest requires exactly the five required artifacts",
        )
    version = output_contract_version or job.schema_version
    artifacts = list(validation_result.artifacts)
    for name, raw_path in (supplemental_artifact_paths or {}).items():
        if name in REQUIRED_ARTIFACTS or name != "llm_call_audit.json":
            raise BatchRunnerError(
                "OUTPUT_PATH_INVALID",
                f"Unsupported or duplicate supplemental artifact: {name}",
            )
        candidate = Path(raw_path)
        issue = _inspect_required_file(candidate, name)
        if issue is not None:
            raise BatchRunnerError(issue.error_code, issue.message)
        question_root = paths.question_root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        if candidate.is_symlink() or not _is_within(resolved, question_root):
            raise BatchRunnerError(
                "OUTPUT_PATH_INVALID",
                "supplemental artifact must be a regular question-scoped file",
            )
        from app.batch.actual_call_audit import (  # avoid an import cycle
            ActualCallAudit,
            validate_actual_call_audit,
        )

        try:
            audit = ActualCallAudit.from_json(candidate.read_text(encoding="utf-8"))
            validate_actual_call_audit(audit)
        except (OSError, UnicodeError, BatchRunnerError) as exc:
            raise BatchRunnerError(
                "LLM_CALL_AUDIT_INVALID",
                "supplemental llm_call_audit.json is not valid",
            ) from exc
        artifacts.append(
            ArtifactFileRecord(
                name=name,
                path=PurePosixPath(job.question_id, name).as_posix(),
                sha256=compute_file_sha256(candidate),
                size_bytes=candidate.stat().st_size,
            )
        )
    ordered = tuple(sorted(artifacts, key=lambda item: item.name))
    payload = {
        "batch_id": job.batch_id,
        "question_id": job.question_id,
        "output_contract_version": version,
        "validation_status": validation_result.validation_status,
        "artifacts": [artifact.to_dict() for artifact in ordered],
    }
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    return ArtifactManifest(
        batch_id=job.batch_id,
        question_id=job.question_id,
        output_contract_version=version,
        validation_status=validation_result.validation_status,
        artifacts=ordered,
        manifest_sha256=digest,
    )


def _identity_issues(
    job: BatchJob,
    value: Mapping[str, Any],
    label: str,
) -> list[ArtifactValidationIssue]:
    issues: list[ArtifactValidationIssue] = []
    if value.get("question_id") != job.question_id:
        issues.append(
            ArtifactValidationIssue(
                "ARTIFACT_QUESTION_MISMATCH",
                label.split("[", 1)[0],
                f"{label} question_id does not match the current job",
            )
        )
    if value.get("batch_id") != job.batch_id:
        issues.append(
            ArtifactValidationIssue(
                "ARTIFACT_BATCH_MISMATCH",
                label.split("[", 1)[0],
                f"{label} batch_id does not match the current job",
            )
        )
    expected = {
        "attempt": job.attempt,
        "source_hash": job.source_hash,
        "input_hash": job.input_hash,
        "status": _enum_value(job.status),
    }
    mismatches = [
        field_name
        for field_name, expected_value in expected.items()
        if value.get(field_name) != expected_value
    ]
    if mismatches:
        issues.append(
            ArtifactValidationIssue(
                "ARTIFACT_PROVENANCE_MISMATCH",
                label.split("[", 1)[0],
                f"{label} provenance mismatch: {mismatches}",
            )
        )
    return issues


def _inspect_required_file(
    path: Path,
    artifact_name: str,
) -> ArtifactValidationIssue | None:
    if path.is_symlink():
        return ArtifactValidationIssue(
            "ARTIFACT_SYMLINK_REJECTED",
            artifact_name,
            f"Symlink artifact rejected: {path}",
        )
    if not path.exists():
        return ArtifactValidationIssue(
            "REQUIRED_ARTIFACT_MISSING",
            artifact_name,
            f"Required artifact is missing: {path}",
        )
    if not path.is_file():
        return ArtifactValidationIssue(
            "OUTPUT_PATH_INVALID",
            artifact_name,
            f"Artifact target is not a regular file: {path}",
        )
    if path.stat().st_size == 0:
        return ArtifactValidationIssue(
            "ARTIFACT_EMPTY",
            artifact_name,
            f"Artifact is empty: {path}",
        )
    return None


def _capture_json(
    path: Path,
    expected_type: type[dict[str, Any]] | type[list[Any]],
    issues: list[ArtifactValidationIssue],
) -> dict[str, Any] | list[Any] | None:
    try:
        return validate_json_artifact(path, expected_type)
    except BatchRunnerError as exc:
        issues.append(
            ArtifactValidationIssue(
                exc.error_code,
                path.name,
                str(exc),
            )
        )
        return None


def _declared_path_is_owned(
    declared: str,
    batch_id: str,
    question_id: str,
    artifact_name: str,
) -> bool:
    if PurePosixPath(declared).is_absolute() or PureWindowsPath(
        declared
    ).is_absolute():
        return False
    normalized = PurePosixPath(declared.replace("\\", "/"))
    expected = PurePosixPath(batch_id, question_id, artifact_name)
    return normalized == expected and ".." not in normalized.parts


def _source_is_auditable(source: Any) -> bool:
    if not isinstance(source, Mapping):
        return False
    kind = source.get("kind") or source.get("type")
    reference = (
        source.get("reference")
        or source.get("uri")
        or source.get("url")
        or source.get("doi")
        or source.get("id")
    )
    return (
        isinstance(kind, str)
        and bool(kind.strip())
        and isinstance(reference, str)
        and bool(reference.strip())
    )


def _validate_result_fields(
    job: BatchJob,
    result_json: Mapping[str, Any] | None,
) -> tuple[ArtifactValidationIssue, ...]:
    if result_json is None:
        return ()
    fields = result_json.get("fields")
    if not isinstance(fields, Mapping):
        return (
            ArtifactValidationIssue(
                "OUTPUT_CONTRACT_INCOMPLETE",
                "result.json",
                "result.json requires an object containing standard fields",
            ),
        )
    missing = [
        name
        for name in STANDARD_OUTPUT_FIELDS
        if name not in fields
        or fields[name] is None
        or (isinstance(fields[name], str) and not fields[name].strip())
    ]
    mismatched = [
        name
        for name in STANDARD_OUTPUT_FIELDS
        if name in fields
        and name in job.output_contract.fields
        and fields[name] != job.output_contract.fields[name]
    ]
    if not missing and not mismatched:
        return ()
    return (
        ArtifactValidationIssue(
            "OUTPUT_CONTRACT_INCOMPLETE",
            "result.json",
            f"missing_standard_fields={missing}; mismatched_fields={mismatched}",
        ),
    )


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _as_list(value: Any) -> list[Any] | None:
    return value if isinstance(value, list) else None


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _result(
    issues: list[ArtifactValidationIssue],
    artifacts: list[ArtifactFileRecord],
) -> ArtifactValidationResult:
    unique: list[ArtifactValidationIssue] = []
    seen: set[tuple[str, str | None, str]] = set()
    for issue in issues:
        key = (issue.error_code, issue.artifact, issue.message)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return ArtifactValidationResult(
        validation_status="failed" if unique else "passed",
        issues=tuple(unique),
        artifacts=tuple(artifacts),
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True
