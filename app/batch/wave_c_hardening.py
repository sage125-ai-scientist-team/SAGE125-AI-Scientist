"""Offline Wave C monitoring and final-package validation.

This module never calls a model provider.  It treats the delivery index and
the files it names as untrusted input, validates every aggregate and digest,
and refuses to label a batch final unless all 125 production questions are
completed with traceable artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any, Final

from app.batch.actual_call_audit import ActualCallAudit, validate_actual_call_audit
from app.batch.delivery_index import DeliveryIndex, validate_delivery_index
from app.batch.errors import BatchRunnerError
from app.batch.output_validation import compute_file_sha256
from app.contracts.batch import REQUIRED_ARTIFACTS


WAVE_C_VALIDATION_VERSION: Final[str] = "t07.wave-c-validation.v1"
WAVE_C_PAUSE_VERSION: Final[str] = "t07.wave-c-pause.v1"
WAVE_C_PAUSE_RELEASE_VERSION: Final[str] = "t07.wave-c-pause-release.v1"
WAVE_C_SAMPLE_VERSION: Final[str] = "t07.wave-c-sample.v1"
EXPECTED_QUESTION_IDS: Final[tuple[str, ...]] = tuple(
    f"Q{number:03d}" for number in range(1, 126)
)
EXPECTED_QUESTION_SET: Final[frozenset[str]] = frozenset(EXPECTED_QUESTION_IDS)
SUPPLEMENTAL_ACTUAL_ARTIFACT: Final[str] = "llm_call_audit.json"
PAUSE_REQUEST_NAME: Final[str] = "pause_request.json"
SHA1: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class WaveCValidationIssue:
    error_code: str
    message: str
    question_id: str | None = None
    artifact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "question_id": self.question_id,
            "artifact": self.artifact,
        }


@dataclass(frozen=True, slots=True)
class WaveCStatusSnapshot:
    batch_id: str | None
    total: int
    completed: int
    status_counts: dict[str, int]
    provider_calls: int
    tokens_used: int
    paused: bool
    resumable_question_ids: tuple[str, ...]
    structural_error_codes: tuple[str, ...]

    @property
    def ready_for_finalization(self) -> bool:
        return (
            self.total == 125
            and self.completed == 125
            and not self.paused
            and not self.resumable_question_ids
            and not self.structural_error_codes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total": self.total,
            "completed": self.completed,
            "status_counts": dict(self.status_counts),
            "provider_calls": self.provider_calls,
            "tokens_used": self.tokens_used,
            "paused": self.paused,
            "resumable_question_ids": list(self.resumable_question_ids),
            "structural_error_codes": list(self.structural_error_codes),
            "ready_for_finalization": self.ready_for_finalization,
        }


@dataclass(frozen=True, slots=True)
class WaveCPackageValidation:
    batch_id: str | None
    code_sha: str | None
    status: WaveCStatusSnapshot
    issues: tuple[WaveCValidationIssue, ...]
    checksum_entries: tuple[tuple[str, str], ...]
    sample_question_ids: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.issues and self.status.ready_for_finalization

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": WAVE_C_VALIDATION_VERSION,
            "batch_id": self.batch_id,
            "code_sha": self.code_sha,
            "passed": self.passed,
            "status": self.status.to_dict(),
            "issues": [issue.to_dict() for issue in self.issues],
            "checksum_count": len(self.checksum_entries),
            "sample_question_ids": list(self.sample_question_ids),
        }


def is_pause_requested(batch_root: str | Path) -> bool:
    """Return whether an explicit, valid pause request exists."""

    root = _safe_root(batch_root, require_exists=False)
    marker = root / PAUSE_REQUEST_NAME
    if not marker.exists():
        return False
    payload = _load_json_object(marker, "PAUSE_REQUEST_INVALID")
    required = {"schema_version", "requested_at", "requested_by", "reason"}
    if payload.get("schema_version") != WAVE_C_PAUSE_VERSION:
        raise BatchRunnerError(
            "PAUSE_REQUEST_INVALID",
            "pause request schema version is invalid",
        )
    if set(payload) != required:
        raise BatchRunnerError(
            "PAUSE_REQUEST_INVALID",
            "pause request fields are invalid",
        )
    for name in ("requested_by", "reason"):
        if not isinstance(payload[name], str) or not payload[name].strip():
            raise BatchRunnerError(
                "PAUSE_REQUEST_INVALID",
                f"pause request {name} must not be empty",
            )
    _parse_timestamp(payload["requested_at"], "PAUSE_REQUEST_INVALID")
    return True


def request_pause(
    batch_root: str | Path,
    *,
    requested_by: str,
    reason: str,
) -> Path:
    """Atomically request a stop before the next question starts."""

    root = _safe_root(batch_root, require_exists=True)
    actor = requested_by.strip()
    explanation = reason.strip()
    if not actor or not explanation:
        raise BatchRunnerError(
            "PAUSE_REQUEST_INVALID",
            "requested_by and reason must not be empty",
        )
    target = root / PAUSE_REQUEST_NAME
    if target.exists():
        if is_pause_requested(root):
            return target
        raise BatchRunnerError(
            "PAUSE_REQUEST_INVALID",
            "existing pause request is invalid",
        )
    payload = {
        "schema_version": WAVE_C_PAUSE_VERSION,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": actor,
        "reason": explanation,
    }
    _write_json_atomically(target, payload)
    return target


def release_pause(
    batch_root: str | Path,
    *,
    released_by: str,
    expected_pause_sha256: str,
) -> Path:
    """Archive an exact pause request before allowing a resumed job."""

    root = _safe_root(batch_root, require_exists=True)
    actor = released_by.strip()
    if not actor or not re.fullmatch(r"[0-9a-f]{64}", expected_pause_sha256):
        raise BatchRunnerError(
            "PAUSE_RELEASE_INVALID",
            "released_by and an exact lowercase pause SHA-256 are required",
        )
    marker = root / PAUSE_REQUEST_NAME
    if not is_pause_requested(root):
        raise BatchRunnerError("PAUSE_REQUEST_MISSING", "no pause request exists")
    raw = marker.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_pause_sha256:
        raise BatchRunnerError(
            "PAUSE_REQUEST_HASH_MISMATCH",
            "pause request changed after operator acknowledgement",
        )
    request_payload = _load_json_object(marker, "PAUSE_REQUEST_INVALID")
    history = root / "pause_history"
    if history.is_symlink():
        raise BatchRunnerError(
            "PAUSE_RELEASE_INVALID",
            "pause history cannot be a symlink",
        )
    history.mkdir(exist_ok=True)
    receipt = history / f"{digest}.json"
    _write_json_atomically(
        receipt,
        {
            "schema_version": WAVE_C_PAUSE_RELEASE_VERSION,
            "pause_request_sha256": digest,
            "released_at": datetime.now(timezone.utc).isoformat(),
            "released_by": actor,
            "pause_request": request_payload,
        },
    )
    marker.unlink()
    return receipt


def inspect_wave_c_status(batch_root: str | Path) -> WaveCStatusSnapshot:
    """Read a partial or complete batch without changing it."""

    root = _safe_root(batch_root, require_exists=True)
    structural: list[str] = []
    manifest: dict[str, Any] = {}
    index: DeliveryIndex | None = None
    try:
        manifest = _load_json_object(root / "manifest.json", "FORMAL_MANIFEST_INVALID")
    except BatchRunnerError as exc:
        structural.append(exc.error_code)
    try:
        index = _load_delivery_index(root)
    except BatchRunnerError as exc:
        structural.append(exc.error_code)

    records = () if index is None else index.records
    status_counts = dict(Counter(record.status for record in records))
    resumable = tuple(
        sorted(record.question_id for record in records if not record.completed)
    )
    provider_calls = manifest.get("provider_calls", 0)
    if type(provider_calls) is not int or provider_calls < 0:
        structural.append("FORMAL_PROVIDER_CALL_COUNT_INVALID")
        provider_calls = 0
    try:
        paused = is_pause_requested(root)
    except BatchRunnerError as exc:
        structural.append(exc.error_code)
        paused = True
    return WaveCStatusSnapshot(
        batch_id=None if index is None else index.batch_id,
        total=len(records),
        completed=sum(record.completed for record in records),
        status_counts=dict(sorted(status_counts.items())),
        provider_calls=provider_calls,
        tokens_used=sum(record.tokens_used for record in records),
        paused=paused,
        resumable_question_ids=resumable,
        structural_error_codes=tuple(sorted(set(structural))),
    )


def validate_wave_c_package(
    batch_root: str | Path,
    *,
    expected_code_sha: str | None = None,
) -> WaveCPackageValidation:
    """Validate a complete, non-Mock 125-question package fail-closed."""

    root = _safe_root(batch_root, require_exists=True)
    issues: list[WaveCValidationIssue] = []
    manifest: dict[str, Any] = {}
    index: DeliveryIndex | None = None
    try:
        manifest = _load_json_object(root / "manifest.json", "FORMAL_MANIFEST_INVALID")
    except BatchRunnerError as exc:
        issues.append(_issue(exc))
    try:
        index = _load_delivery_index(root, validate_files=True)
    except BatchRunnerError as exc:
        issues.append(_issue(exc))

    code_sha = manifest.get("code_sha") if manifest else None
    if not isinstance(code_sha, str) or not SHA1.fullmatch(code_sha):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_CODE_SHA_INVALID",
                "manifest code_sha must be a full lowercase Git SHA",
            )
        )
        code_sha = None
    if expected_code_sha is not None and code_sha != expected_code_sha:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_CODE_SHA_MISMATCH",
                "manifest code_sha does not match the requested provenance",
            )
        )
    _validate_manifest(manifest, issues)

    checksums: list[tuple[str, str]] = []
    if index is not None:
        _validate_index_records(root, index, issues, checksums)
    status = inspect_wave_c_status(root)
    for error_code in status.structural_error_codes:
        if not any(issue.error_code == error_code for issue in issues):
            issues.append(
                WaveCValidationIssue(error_code, "batch status is structurally invalid")
            )

    for name in ("manifest.json", "delivery_index.json"):
        target = root / name
        if target.is_file() and not target.is_symlink():
            checksums.append((name, compute_file_sha256(target)))
    checksums = sorted(set(checksums))
    sample = (
        build_manual_sample_plan(index.batch_id, EXPECTED_QUESTION_IDS)
        if index is not None and set(record.question_id for record in index.records)
        == EXPECTED_QUESTION_SET
        else ()
    )
    return WaveCPackageValidation(
        batch_id=None if index is None else index.batch_id,
        code_sha=code_sha,
        status=status,
        issues=tuple(_dedupe_issues(issues)),
        checksum_entries=tuple(checksums),
        sample_question_ids=sample,
    )


def build_manual_sample_plan(
    batch_id: str,
    question_ids: tuple[str, ...] = EXPECTED_QUESTION_IDS,
    *,
    sample_size: int = 24,
) -> tuple[str, ...]:
    """Select a deterministic audit sample without asserting human approval."""

    if not batch_id.strip() or sample_size < 1 or sample_size > len(question_ids):
        raise ValueError("sample plan inputs are invalid")
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("sample question IDs must be unique")
    ranked = sorted(
        question_ids,
        key=lambda question_id: hashlib.sha256(
            f"{WAVE_C_SAMPLE_VERSION}:{batch_id}:{question_id}".encode("utf-8")
        ).hexdigest(),
    )
    return tuple(sorted(ranked[:sample_size]))


def write_validation_receipts(
    output_root: str | Path,
    validation: WaveCPackageValidation,
) -> tuple[Path, Path, Path]:
    """Write deterministic validation receipts; never claim human sign-off."""

    root = _safe_root(output_root, require_exists=True)
    status_path = root / "wave_c_validation.json"
    checksums_path = root / "checksums.sha256"
    sample_path = root / "manual_sample_24.json"
    _write_json_atomically(status_path, validation.to_dict())
    checksum_text = "".join(
        f"{digest}  {path}\n" for path, digest in validation.checksum_entries
    )
    _write_text_atomically(checksums_path, checksum_text)
    _write_json_atomically(
        sample_path,
        {
            "schema_version": WAVE_C_SAMPLE_VERSION,
            "batch_id": validation.batch_id,
            "review_status": "pending_human_review",
            "question_ids": list(validation.sample_question_ids),
        },
    )
    return status_path, checksums_path, sample_path


def _validate_manifest(
    manifest: dict[str, Any],
    issues: list[WaveCValidationIssue],
) -> None:
    if not manifest:
        return
    exact = {
        "execute": True,
        "mock": False,
        "fallback": False,
        "status": "completed",
    }
    for name, expected in exact.items():
        if manifest.get(name) != expected:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_MANIFEST_NOT_FINAL",
                    f"manifest {name} must equal {expected!r}",
                )
            )
    selected = manifest.get("selected_question_ids")
    order = manifest.get("question_order")
    if selected != list(EXPECTED_QUESTION_IDS) or order != list(EXPECTED_QUESTION_IDS):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_QUESTION_SET_MISMATCH",
                "manifest must freeze Q001 through Q125 in order",
            )
        )
    questions = manifest.get("questions")
    if not isinstance(questions, list) or len(questions) != 125:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_MANIFEST_TOTAL_MISMATCH",
                "manifest must contain exactly 125 question receipts",
            )
        )
    else:
        ids = [item.get("question_id") for item in questions if isinstance(item, dict)]
        if ids != list(EXPECTED_QUESTION_IDS) or any(
            item.get("completed") is not True or item.get("status") != "completed"
            for item in questions
            if isinstance(item, dict)
        ):
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_MANIFEST_QUESTION_INVALID",
                    "manifest questions must be ordered and completed",
                )
            )
    calls = manifest.get("provider_calls")
    if type(calls) is not int or calls < 125:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_PROVIDER_AUDIT_INCOMPLETE",
                "formal package must record at least one provider call per question",
            )
        )


def _validate_index_records(
    root: Path,
    index: DeliveryIndex,
    issues: list[WaveCValidationIssue],
    checksums: list[tuple[str, str]],
) -> None:
    ids = tuple(record.question_id for record in index.records)
    if index.total != 125 or index.completed != 125 or set(ids) != EXPECTED_QUESTION_SET:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_DELIVERY_TOTAL_MISMATCH",
                "delivery index must contain 125/125 unique completed questions",
            )
        )
    question_dirs = {
        item.name
        for item in root.iterdir()
        if item.is_dir() and re.fullmatch(r"Q\d{3}", item.name)
    }
    if question_dirs != EXPECTED_QUESTION_SET:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_DIRECTORY_SET_MISMATCH",
                "batch root must contain exactly Q001 through Q125 directories",
            )
        )

    required = set(REQUIRED_ARTIFACTS) | {SUPPLEMENTAL_ACTUAL_ARTIFACT}
    for record in index.records:
        if (
            not record.completed
            or not record.actual
            or record.mock
            or record.synthetic
            or record.validation_status != "passed"
            or record.failure_code is not None
        ):
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_RECORD_NOT_FINAL",
                    "delivery record is not completed actual production output",
                    question_id=record.question_id,
                )
            )
        names = {artifact.name for artifact in record.artifacts}
        missing = sorted(required - names)
        if missing:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_ARTIFACT_SET_INCOMPLETE",
                    f"required artifacts are missing: {missing}",
                    question_id=record.question_id,
                )
            )
        for artifact in record.artifacts:
            checksums.append((artifact.path, artifact.sha256))
            if artifact.name == SUPPLEMENTAL_ACTUAL_ARTIFACT:
                _validate_call_audit(root, record, artifact.path, issues)
        _validate_question_sidecars(root, record, index.batch_id, issues, checksums)


def _validate_call_audit(
    root: Path,
    record: Any,
    relative_path: str,
    issues: list[WaveCValidationIssue],
) -> None:
    try:
        pure = PurePosixPath(relative_path.replace("\\", "/"))
        target = root.joinpath(*pure.parts)
        audit = ActualCallAudit.from_json(target.read_text(encoding="utf-8"))
        validate_actual_call_audit(
            audit,
            budget_mode=record.budget_mode or "token_and_cost",
        )
        if audit.provider != record.provider or audit.model != record.model:
            raise BatchRunnerError(
                "CALL_AUDIT_IDENTITY_MISMATCH",
                "call audit provider/model does not match delivery record",
            )
        if audit.total_tokens != record.tokens_used:
            raise BatchRunnerError(
                "CALL_AUDIT_TOKEN_MISMATCH",
                "call audit tokens do not match delivery record",
            )
    except (OSError, UnicodeError, TypeError, ValueError, BatchRunnerError) as exc:
        error_code = (
            exc.error_code
            if isinstance(exc, BatchRunnerError)
            else "LLM_CALL_AUDIT_INVALID"
        )
        issues.append(
            WaveCValidationIssue(
                error_code,
                "llm_call_audit.json is invalid or inconsistent",
                question_id=record.question_id,
                artifact=SUPPLEMENTAL_ACTUAL_ARTIFACT,
            )
        )


def _validate_question_sidecars(
    root: Path,
    record: Any,
    batch_id: str,
    issues: list[WaveCValidationIssue],
    checksums: list[tuple[str, str]],
) -> None:
    question_id = record.question_id
    question_root = root / question_id
    expected = {
        "checkpoint.json": ("status", "completed"),
        "completion_decision.json": ("completed", True),
        "artifact_manifest.json": ("validation_status", "passed"),
    }
    for name, (field, value) in expected.items():
        target = question_root / name
        try:
            payload = _load_json_object(target, "WAVE_C_SIDECAR_INVALID")
        except BatchRunnerError as exc:
            issues.append(
                WaveCValidationIssue(
                    exc.error_code,
                    str(exc),
                    question_id=question_id,
                    artifact=name,
                )
            )
            continue
        if payload.get(field) != value:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_SIDECAR_INVALID",
                    f"{name} does not prove successful completion",
                    question_id=question_id,
                    artifact=name,
                )
            )
        payload_question = payload.get("question_id")
        payload_batch = payload.get("batch_id")
        if payload_question not in {None, question_id} or payload_batch not in {None, batch_id}:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_SIDECAR_IDENTITY_MISMATCH",
                    f"{name} identity does not match its question",
                    question_id=question_id,
                    artifact=name,
                )
            )
        if name == "artifact_manifest.json":
            manifest_payload = {
                "batch_id": payload.get("batch_id"),
                "question_id": payload.get("question_id"),
                "output_contract_version": payload.get("output_contract_version"),
                "validation_status": payload.get("validation_status"),
                "artifacts": payload.get("artifacts"),
            }
            expected_artifacts = [artifact.to_dict() for artifact in record.artifacts]
            digest = hashlib.sha256(_canonical_json(manifest_payload)).hexdigest()
            if (
                payload.get("batch_id") != batch_id
                or payload.get("question_id") != question_id
                or payload.get("artifacts") != expected_artifacts
                or payload.get("manifest_sha256") != digest
            ):
                issues.append(
                    WaveCValidationIssue(
                        "WAVE_C_ARTIFACT_MANIFEST_MISMATCH",
                        "artifact manifest does not match delivery artifacts",
                        question_id=question_id,
                        artifact=name,
                    )
                )
        checksums.append(
            (PurePosixPath(question_id, name).as_posix(), compute_file_sha256(target))
        )


def _load_delivery_index(
    root: Path,
    *,
    validate_files: bool = False,
) -> DeliveryIndex:
    target = root / "delivery_index.json"
    if target.is_symlink() or not target.is_file():
        raise BatchRunnerError(
            "DELIVERY_INDEX_MISSING",
            "delivery_index.json is missing or not a regular file",
        )
    try:
        index = DeliveryIndex.from_json(target.read_text(encoding="utf-8"))
        validate_delivery_index(index, artifact_root=root if validate_files else None)
        return index
    except BatchRunnerError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise BatchRunnerError(
            "DELIVERY_INDEX_JSON_INVALID",
            "delivery index cannot be read",
        ) from exc


def _safe_root(value: str | Path, *, require_exists: bool) -> Path:
    root = Path(value)
    if root.is_symlink():
        raise BatchRunnerError("WAVE_C_ROOT_INVALID", "batch root cannot be a symlink")
    if require_exists and not root.is_dir():
        raise BatchRunnerError("WAVE_C_ROOT_INVALID", "batch root must be a directory")
    return root


def _load_json_object(path: Path, error_code: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BatchRunnerError(error_code, f"JSON file is missing: {path.name}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise BatchRunnerError(error_code, f"JSON file has a UTF-8 BOM: {path.name}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(error_code, f"JSON file is invalid: {path.name}") from exc
    if not isinstance(payload, dict):
        raise BatchRunnerError(error_code, f"JSON file must be an object: {path.name}")
    return payload


def _parse_timestamp(value: Any, error_code: str) -> datetime:
    if not isinstance(value, str):
        raise BatchRunnerError(error_code, "timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BatchRunnerError(error_code, "timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BatchRunnerError(error_code, "timestamp must include a timezone")
    return parsed


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _write_text_atomically(path, text)


def _write_text_atomically(path: Path, text: str) -> None:
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f"{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _issue(exc: BatchRunnerError) -> WaveCValidationIssue:
    return WaveCValidationIssue(exc.error_code, str(exc))


def _dedupe_issues(
    issues: list[WaveCValidationIssue],
) -> list[WaveCValidationIssue]:
    unique: list[WaveCValidationIssue] = []
    seen: set[tuple[str, str, str | None, str | None]] = set()
    for issue in issues:
        key = (issue.error_code, issue.message, issue.question_id, issue.artifact)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return unique


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
