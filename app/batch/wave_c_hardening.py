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
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any, Final

from app.batch.actual_call_audit import ActualCallAudit, validate_actual_call_audit
from app.batch.delivery_index import DeliveryIndex, validate_delivery_index
from app.batch.errors import BatchRunnerError
from app.batch.fingerprint import (
    build_output_fingerprint,
    evaluate_cross_question_similarity,
)
from app.batch.output_validation import compute_file_sha256
from app.contracts.batch import REQUIRED_ARTIFACTS
from app.contracts.validation import GateResult


WAVE_C_VALIDATION_VERSION: Final[str] = "t07.wave-c-validation.v1"
WAVE_C_PAUSE_VERSION: Final[str] = "t07.wave-c-pause.v1"
WAVE_C_PAUSE_RELEASE_VERSION: Final[str] = "t07.wave-c-pause-release.v1"
WAVE_C_SAMPLE_VERSION: Final[str] = "t07.wave-c-sample.v1"
WAVE_C_TRUSTED_RECEIPTS_VERSION: Final[str] = (
    "t07.wave-c-trusted-receipts.v1"
)
EXPECTED_QUESTION_IDS: Final[tuple[str, ...]] = tuple(
    f"Q{number:03d}" for number in range(1, 126)
)
EXPECTED_QUESTION_SET: Final[frozenset[str]] = frozenset(EXPECTED_QUESTION_IDS)
SUPPLEMENTAL_ACTUAL_ARTIFACT: Final[str] = "llm_call_audit.json"
PAUSE_REQUEST_NAME: Final[str] = "pause_request.json"
SHA1: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")
SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
TRUSTED_RECEIPT_ARTIFACTS: Final[frozenset[str]] = frozenset(
    {
        *REQUIRED_ARTIFACTS,
        SUPPLEMENTAL_ACTUAL_ARTIFACT,
        "artifact_manifest.json",
        "checkpoint.json",
        "completion_decision.json",
        "quality_gate_results.json",
        "validation_report.json",
    }
)
TRUSTED_EVIDENCE_SOURCE_TYPES: Final[frozenset[str]] = frozenset(
    {"paper", "web", "dataset"}
)
MINIMUM_FINAL_PDF_BYTES: Final[int] = 256


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
    trusted_receipts_sha256: str | None = None
    trusted_receipts_verified: bool = False

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
            "trusted_receipts_sha256": self.trusted_receipts_sha256,
            "trusted_receipts_verified": self.trusted_receipts_verified,
        }


@dataclass(frozen=True, slots=True)
class _ValidatedQuestionContent:
    question_id: str
    title: str
    abstract: str
    hypothesis: str
    evidence_ids: tuple[str, ...]


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

    structural.extend(_status_structure_errors(manifest, index))

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


def _status_structure_errors(
    manifest: Mapping[str, Any],
    index: DeliveryIndex | None,
) -> tuple[str, ...]:
    errors: list[str] = []
    if index is not None:
        ids = tuple(record.question_id for record in index.records)
        if ids != EXPECTED_QUESTION_IDS:
            errors.append("WAVE_C_STATUS_QUESTION_SET_MISMATCH")
        if any(
            record.status != "completed" or not record.completed
            for record in index.records
        ):
            errors.append("WAVE_C_STATUS_INDEX_QUESTION_MISMATCH")
    if not manifest or index is None:
        return tuple(errors)

    if manifest.get("freeze_id") != index.batch_id or (
        "batch_id" in manifest and manifest.get("batch_id") != index.batch_id
    ):
        errors.append("WAVE_C_STATUS_MANIFEST_INDEX_MISMATCH")
    if (
        manifest.get("question_order") != list(EXPECTED_QUESTION_IDS)
        or manifest.get("selected_question_ids") != list(EXPECTED_QUESTION_IDS)
    ):
        errors.append("WAVE_C_STATUS_QUESTION_SET_MISMATCH")

    questions = manifest.get("questions")
    if not isinstance(questions, list) or len(questions) != len(
        EXPECTED_QUESTION_IDS
    ):
        errors.append("WAVE_C_STATUS_MANIFEST_QUESTION_MISMATCH")
    else:
        question_ids = [
            item.get("question_id") if isinstance(item, Mapping) else None
            for item in questions
        ]
        if question_ids != list(EXPECTED_QUESTION_IDS) or any(
            not isinstance(item, Mapping)
            or item.get("status") != "completed"
            or item.get("completed") is not True
            for item in questions
        ):
            errors.append("WAVE_C_STATUS_MANIFEST_QUESTION_MISMATCH")
    if manifest.get("status") != "completed":
        errors.append("WAVE_C_STATUS_MANIFEST_QUESTION_MISMATCH")
    return tuple(errors)


def validate_wave_c_package(
    batch_root: str | Path,
    *,
    expected_code_sha: str | None = None,
    trusted_receipts_path: str | Path | None = None,
    expected_trusted_receipts_sha256: str | None = None,
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

    trusted_questions, trusted_digest, trusted_verified = (
        _load_trusted_receipts(
            root,
            trusted_receipts_path,
            expected_trusted_receipts_sha256,
            batch_id=None if index is None else index.batch_id,
            code_sha=code_sha,
            issues=issues,
        )
    )

    checksums: list[tuple[str, str]] = []
    contents: list[_ValidatedQuestionContent] = []
    if index is not None:
        contents = _validate_index_records(
            root,
            index,
            issues,
            checksums,
            trusted_questions,
        )
        _validate_cross_question_content(contents, issues)
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
        trusted_receipts_sha256=trusted_digest,
        trusted_receipts_verified=trusted_verified,
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


def _load_trusted_receipts(
    batch_root: Path,
    path: str | Path | None,
    expected_sha256: str | None,
    *,
    batch_id: str | None,
    code_sha: str | None,
    issues: list[WaveCValidationIssue],
) -> tuple[dict[str, Mapping[str, Any]], str | None, bool]:
    issue_count = len(issues)
    if path is None or expected_sha256 is None:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPTS_REQUIRED",
                "an external trusted receipt set and operator-supplied SHA-256 are required",
            )
        )
        return {}, None, False
    if not isinstance(expected_sha256, str) or not SHA256.fullmatch(
        expected_sha256
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPTS_HASH_INVALID",
                "trusted receipt SHA-256 must be lowercase hexadecimal",
            )
        )
        return {}, None, False

    candidate = Path(path)
    resolved = candidate.resolve(strict=False)
    if (
        candidate.is_symlink()
        or not candidate.is_file()
        or _is_within(resolved, batch_root.resolve(strict=False))
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPTS_PATH_INVALID",
                "trusted receipts must be a regular file outside the candidate package",
            )
        )
        return {}, None, False
    raw = candidate.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPTS_HASH_MISMATCH",
                "trusted receipts do not match the operator-supplied SHA-256",
            )
        )
        return {}, digest, False
    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPTS_INVALID",
                "trusted receipts must be UTF-8 without BOM",
            )
        )
        return {}, digest, False
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        payload = None
    if not isinstance(payload, Mapping):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPTS_INVALID",
                "trusted receipts must be a JSON object",
            )
        )
        return {}, digest, False

    if (
        payload.get("schema_version") != WAVE_C_TRUSTED_RECEIPTS_VERSION
        or payload.get("batch_id") != batch_id
        or payload.get("code_sha") != code_sha
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPTS_IDENTITY_MISMATCH",
                "trusted receipt version, batch, or code identity is inconsistent",
            )
        )
    for name, field in (
        ("manifest.json", "manifest_sha256"),
        ("delivery_index.json", "delivery_index_sha256"),
    ):
        target = batch_root / name
        expected = payload.get(field)
        if (
            not isinstance(expected, str)
            or not SHA256.fullmatch(expected)
            or not target.is_file()
            or target.is_symlink()
            or compute_file_sha256(target) != expected
        ):
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_TRUSTED_RECEIPTS_ROOT_HASH_MISMATCH",
                    f"trusted receipt does not bind {name}",
                    artifact=name,
                )
            )

    raw_questions = payload.get("questions")
    trusted: dict[str, Mapping[str, Any]] = {}
    if not isinstance(raw_questions, list) or len(raw_questions) != len(
        EXPECTED_QUESTION_IDS
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPTS_QUESTION_SET_INVALID",
                "trusted receipts must contain exactly Q001 through Q125",
            )
        )
    else:
        for expected_question_id, raw_question in zip(
            EXPECTED_QUESTION_IDS,
            raw_questions,
            strict=True,
        ):
            if not isinstance(raw_question, Mapping):
                issues.append(
                    WaveCValidationIssue(
                        "WAVE_C_TRUSTED_RECEIPTS_QUESTION_INVALID",
                        "trusted question receipt must be an object",
                        question_id=expected_question_id,
                    )
                )
                continue
            question_id = raw_question.get("question_id")
            source_hash = raw_question.get("source_hash")
            input_hash = raw_question.get("input_hash")
            question_text_sha256 = raw_question.get("question_text_sha256")
            artifacts = raw_question.get("artifact_sha256")
            valid = (
                question_id == expected_question_id
                and isinstance(source_hash, str)
                and SHA256.fullmatch(source_hash) is not None
                and isinstance(input_hash, str)
                and SHA256.fullmatch(input_hash) is not None
                and isinstance(question_text_sha256, str)
                and SHA256.fullmatch(question_text_sha256) is not None
                and isinstance(artifacts, Mapping)
                and set(artifacts) == TRUSTED_RECEIPT_ARTIFACTS
                and all(
                    isinstance(value, str) and SHA256.fullmatch(value)
                    for value in artifacts.values()
                )
            )
            if not valid:
                issues.append(
                    WaveCValidationIssue(
                        "WAVE_C_TRUSTED_RECEIPTS_QUESTION_INVALID",
                        "trusted question receipt identity or hashes are invalid",
                        question_id=expected_question_id,
                    )
                )
                continue
            trusted[expected_question_id] = raw_question

    verified = len(issues) == issue_count
    return trusted, digest, verified


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
    trusted_questions: Mapping[str, Mapping[str, Any]],
) -> list[_ValidatedQuestionContent]:
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
    contents: list[_ValidatedQuestionContent] = []
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
        contents.append(
            _validate_question_content(
                root,
                record,
                trusted_questions.get(record.question_id),
                issues,
                checksums,
            )
        )
    return contents


def _validate_call_audit(
    root: Path,
    record: Any,
    relative_path: str,
    issues: list[WaveCValidationIssue],
) -> None:
    try:
        if record.budget_mode != "token_only":
            raise BatchRunnerError(
                "WAVE_C_BUDGET_MODE_INVALID",
                "delivery record must declare the frozen token_only budget mode",
            )
        pure = PurePosixPath(relative_path.replace("\\", "/"))
        target = root.joinpath(*pure.parts)
        audit = ActualCallAudit.from_json(target.read_text(encoding="utf-8"))
        validate_actual_call_audit(
            audit,
            budget_mode="token_only",
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


def _validate_question_content(
    root: Path,
    record: Any,
    trusted: Mapping[str, Any] | None,
    issues: list[WaveCValidationIssue],
    checksums: list[tuple[str, str]],
) -> _ValidatedQuestionContent:
    question_id = record.question_id
    question_root = root / question_id
    _validate_trusted_artifact_bindings(
        question_root,
        record,
        trusted,
        issues,
        checksums,
    )
    _validate_report_pdf(question_root / "report.pdf", question_id, issues)

    try:
        result = _load_json_object(
            question_root / "result.json",
            "WAVE_C_RESULT_CONTENT_INVALID",
        )
    except BatchRunnerError as exc:
        issues.append(
            WaveCValidationIssue(
                exc.error_code,
                str(exc),
                question_id=question_id,
                artifact="result.json",
            )
        )
        result = {}
    try:
        cards = _load_json_array(
            question_root / "evidence_cards.json",
            "WAVE_C_EVIDENCE_INVALID",
        )
    except BatchRunnerError as exc:
        issues.append(
            WaveCValidationIssue(
                exc.error_code,
                str(exc),
                question_id=question_id,
                artifact="evidence_cards.json",
            )
        )
        cards = []

    if (
        result.get("batch_id") != record.batch_id
        or result.get("question_id") != question_id
        or result.get("source_hash") != record.source_hash
        or result.get("input_hash") != record.input_hash
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_RESULT_IDENTITY_MISMATCH",
                "result.json identity does not match the delivery record",
                question_id=question_id,
                artifact="result.json",
            )
        )

    fields = result.get("fields")
    fields = fields if isinstance(fields, Mapping) else {}
    title = _nonempty_text(fields.get("Title"))
    abstract = _nonempty_text(fields.get("Abstract"))
    plan = result.get("research_plan")
    plan = plan if isinstance(plan, Mapping) else {}
    question_text = _nonempty_text(plan.get("input_question"))
    if (
        plan.get("question_id") != question_id
        or plan.get("actual_execution") is not True
        or not question_text
        or not title
        or not abstract
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_RESULT_CONTENT_INVALID",
                "result must bind the question text and non-empty actual output",
                question_id=question_id,
                artifact="result.json",
            )
        )
    if trusted is not None:
        expected_question_hash = trusted.get("question_text_sha256")
        actual_question_hash = hashlib.sha256(
            question_text.encode("utf-8")
        ).hexdigest()
        if expected_question_hash != actual_question_hash:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_QUESTION_TEXT_MISMATCH",
                    "question text does not match the trusted execution receipt",
                    question_id=question_id,
                    artifact="result.json",
                )
            )

    evidence_ids, card_by_id = _validate_evidence_cards(
        cards,
        record,
        issues,
    )
    hypothesis = _validate_hypothesis_and_references(
        plan,
        card_by_id,
        question_id,
        issues,
    )
    _validate_quality_gate_receipts(question_root, question_id, issues)
    return _ValidatedQuestionContent(
        question_id=question_id,
        title=title,
        abstract=abstract,
        hypothesis=hypothesis,
        evidence_ids=evidence_ids,
    )


def _validate_trusted_artifact_bindings(
    question_root: Path,
    record: Any,
    trusted: Mapping[str, Any] | None,
    issues: list[WaveCValidationIssue],
    checksums: list[tuple[str, str]],
) -> None:
    if trusted is None:
        return
    question_id = record.question_id
    if (
        trusted.get("source_hash") != record.source_hash
        or trusted.get("input_hash") != record.input_hash
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_TRUSTED_RECEIPT_INPUT_MISMATCH",
                "trusted source/input hash does not match the delivery record",
                question_id=question_id,
            )
        )
    artifacts = trusted.get("artifact_sha256")
    if not isinstance(artifacts, Mapping):
        return
    for name in sorted(TRUSTED_RECEIPT_ARTIFACTS):
        target = question_root / name
        expected = artifacts.get(name)
        valid = (
            isinstance(expected, str)
            and SHA256.fullmatch(expected) is not None
            and target.is_file()
            and not target.is_symlink()
            and compute_file_sha256(target) == expected
        )
        if not valid:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_TRUSTED_ARTIFACT_HASH_MISMATCH",
                    f"trusted receipt does not bind {name}",
                    question_id=question_id,
                    artifact=name,
                )
            )
        elif target.is_file():
            checksums.append(
                (PurePosixPath(question_id, name).as_posix(), expected)
            )


def _validate_report_pdf(
    path: Path,
    question_id: str,
    issues: list[WaveCValidationIssue],
) -> None:
    try:
        payload = path.read_bytes()
    except OSError:
        payload = b""
    valid = (
        len(payload) >= MINIMUM_FINAL_PDF_BYTES
        and payload.startswith(b"%PDF-")
        and payload.rstrip().endswith(b"%%EOF")
        and re.search(br"/Type\s*/Page\b", payload) is not None
    )
    if not valid:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_REPORT_PDF_INVALID",
                "report.pdf is an empty or structurally minimal shell",
                question_id=question_id,
                artifact="report.pdf",
            )
        )


def _validate_evidence_cards(
    cards: list[Any],
    record: Any,
    issues: list[WaveCValidationIssue],
) -> tuple[tuple[str, ...], dict[str, Mapping[str, Any]]]:
    question_id = record.question_id
    if not cards:
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_EVIDENCE_EMPTY",
                "formal actual output requires non-empty trusted evidence",
                question_id=question_id,
                artifact="evidence_cards.json",
            )
        )
        return (), {}
    identifiers: list[str] = []
    by_id: dict[str, Mapping[str, Any]] = {}
    for card in cards:
        if not isinstance(card, Mapping):
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_EVIDENCE_INVALID",
                    "every evidence card must be an object",
                    question_id=question_id,
                    artifact="evidence_cards.json",
                )
            )
            continue
        evidence_id = _nonempty_text(card.get("evidence_id"))
        quoted_text = _nonempty_text(card.get("quoted_text"))
        title = _nonempty_text(card.get("title"))
        source_id = _nonempty_text(card.get("source_id"))
        source_type = _nonempty_text(card.get("source_type"))
        content_hash = _nonempty_text(card.get("content_hash"))
        source_content_hash = _nonempty_text(card.get("source_content_hash"))
        locator = card.get("locator")
        quote_hash = hashlib.sha256(quoted_text.encode("utf-8")).hexdigest()
        valid = (
            evidence_id
            and card.get("id") == evidence_id
            and evidence_id not in by_id
            and card.get("question_id") == question_id
            and card.get("batch_id") in {None, record.batch_id}
            and source_id
            and source_type in TRUSTED_EVIDENCE_SOURCE_TYPES
            and quoted_text
            and title
            and _normalized_text(quoted_text) != _normalized_text(title)
            and isinstance(locator, Mapping)
            and bool(locator)
            and bool(
                _nonempty_text(
                    locator.get("document") or locator.get("document_id")
                )
            )
            and content_hash == f"sha256:{quote_hash}"
            and SHA256.fullmatch(source_content_hash) is not None
        )
        if not valid:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_EVIDENCE_INVALID",
                    "evidence quote, locator, source, hash, or identity is invalid",
                    question_id=question_id,
                    artifact="evidence_cards.json",
                )
            )
            continue
        identifiers.append(evidence_id)
        by_id[evidence_id] = card
    return tuple(identifiers), by_id


def _validate_hypothesis_and_references(
    plan: Mapping[str, Any],
    cards: Mapping[str, Mapping[str, Any]],
    question_id: str,
    issues: list[WaveCValidationIssue],
) -> str:
    hypotheses = plan.get("generated_hypotheses")
    references = plan.get("reference_ids")
    reference_ids = (
        tuple(item.strip() for item in references)
        if isinstance(references, list)
        and all(isinstance(item, str) and item.strip() for item in references)
        else ()
    )
    valid_references = (
        isinstance(references, list)
        and bool(reference_ids)
        and len(reference_ids) == len(set(reference_ids))
        and set(reference_ids) <= set(cards)
    )
    hypothesis_texts: list[str] = []
    supporting_ids: set[str] = set()
    valid_hypotheses = isinstance(hypotheses, list) and bool(hypotheses)
    if valid_hypotheses:
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, Mapping):
                valid_hypotheses = False
                continue
            text = _nonempty_text(hypothesis.get("hypothesis"))
            raw_supporting = hypothesis.get("supporting_evidence_ids")
            supporting = (
                tuple(item.strip() for item in raw_supporting)
                if isinstance(raw_supporting, list)
                and all(
                    isinstance(item, str) and item.strip()
                    for item in raw_supporting
                )
                else ()
            )
            raw_contradicted = hypothesis.get(
                "contradicted_by_evidence_ids",
                [],
            )
            contradicted = (
                tuple(item.strip() for item in raw_contradicted)
                if isinstance(raw_contradicted, list)
                and all(
                    isinstance(item, str) and item.strip()
                    for item in raw_contradicted
                )
                else None
            )
            if (
                not text
                or not supporting
                or len(supporting) != len(set(supporting))
                or not set(supporting) <= set(cards)
                or contradicted is None
                or len(contradicted) != len(set(contradicted))
                or not set(contradicted) <= set(cards)
            ):
                valid_hypotheses = False
            hypothesis_texts.append(text)
            supporting_ids.update(supporting)
    if not valid_hypotheses or not valid_references or not supporting_ids <= set(
        reference_ids
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_EVIDENCE_BINDING_INVALID",
                "hypotheses and references must bind only known evidence IDs",
                question_id=question_id,
                artifact="result.json",
            )
        )

    raw_references = plan.get("references")
    reference_map: dict[str, Mapping[str, Any]] = {}
    if isinstance(raw_references, list):
        for item in raw_references:
            if isinstance(item, Mapping):
                identifier = _nonempty_text(item.get("id") or item.get("evidence_id"))
                if identifier:
                    reference_map[identifier] = item
    protected = ("source_id", "source_type", "quoted_text", "locator", "content_hash")
    if set(reference_map) != set(reference_ids) or any(
        any(reference_map[identifier].get(field) != cards[identifier].get(field) for field in protected)
        for identifier in reference_ids
        if identifier in reference_map and identifier in cards
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_REFERENCE_INTEGRITY_INVALID",
                "references must preserve trusted evidence provenance",
                question_id=question_id,
                artifact="result.json",
            )
        )
    return " ".join(item for item in hypothesis_texts if item)


def _validate_quality_gate_receipts(
    question_root: Path,
    question_id: str,
    issues: list[WaveCValidationIssue],
) -> None:
    try:
        raw_gates = _load_json_array(
            question_root / "quality_gate_results.json",
            "WAVE_C_QUALITY_GATE_RECEIPT_INVALID",
        )
        gates = tuple(GateResult.model_validate(item) for item in raw_gates)
    except (BatchRunnerError, TypeError, ValueError):
        gates = ()
    t01 = tuple(gate for gate in gates if gate.gate_id.casefold().startswith("t01"))
    t03 = tuple(gate for gate in gates if gate.gate_id.casefold().startswith("t03"))
    if (
        len(t01) != 1
        or not t03
        or any(not gate.passed or gate.is_blocking for gate in (*t01, *t03))
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_QUALITY_GATE_RECEIPT_INVALID",
                "trusted T01 and T03 gate receipts must pass without blockers",
                question_id=question_id,
                artifact="quality_gate_results.json",
            )
        )
    try:
        decision = _load_json_object(
            question_root / "completion_decision.json",
            "WAVE_C_COMPLETION_RECEIPT_INVALID",
        )
    except BatchRunnerError:
        decision = {}
    conditions = decision.get("conditions")
    if (
        decision.get("status") != "completed"
        or decision.get("completed") is not True
        or decision.get("error_codes") != []
        or decision.get("issues") != []
        or not isinstance(conditions, Mapping)
        or conditions.get("12_t01_evidence_precheck") is not True
        or conditions.get("13_t03_quality_gates") is not True
    ):
        issues.append(
            WaveCValidationIssue(
                "WAVE_C_COMPLETION_RECEIPT_INVALID",
                "completion decision must bind passed T01 and T03 conditions",
                question_id=question_id,
                artifact="completion_decision.json",
            )
        )


def _validate_cross_question_content(
    contents: list[_ValidatedQuestionContent],
    issues: list[WaveCValidationIssue],
) -> None:
    evidence_owners: dict[str, list[str]] = {}
    exact_content: dict[str, list[str]] = {}
    fingerprints = {}
    for content in contents:
        for evidence_id in content.evidence_ids:
            evidence_owners.setdefault(evidence_id, []).append(content.question_id)
        normalized = _normalized_text(
            " ".join((content.title, content.abstract, content.hypothesis))
        )
        if normalized:
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            exact_content.setdefault(digest, []).append(content.question_id)
        fingerprints[content.question_id] = build_output_fingerprint(
            title=content.title,
            abstract=content.abstract,
            hypothesis=content.hypothesis,
        )
    for evidence_id, owners in sorted(evidence_owners.items()):
        unique = sorted(set(owners))
        if len(unique) > 1:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_CROSS_QUESTION_EVIDENCE_REUSE",
                    f"evidence ID {evidence_id} is reused by {', '.join(unique)}",
                    question_id=unique[0],
                    artifact="evidence_cards.json",
                )
            )
    for owners in exact_content.values():
        unique = sorted(set(owners))
        if len(unique) > 1:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_CROSS_QUESTION_CONTENT_REUSE",
                    f"identical output content is reused by {', '.join(unique)}",
                    question_id=unique[0],
                )
            )
    for left, right in combinations(contents, 2):
        similarity = evaluate_cross_question_similarity(
            left_question_id=left.question_id,
            left=fingerprints[left.question_id],
            right_question_id=right.question_id,
            right=fingerprints[right.question_id],
            threshold=0.90,
        )
        if similarity.compared and similarity.requires_review:
            issues.append(
                WaveCValidationIssue(
                    "WAVE_C_HIGH_CROSS_QUESTION_SIMILARITY",
                    (
                        f"{left.question_id}/{right.question_id} similarity "
                        f"{similarity.combined_score:.6f} exceeds 0.90"
                    ),
                    question_id=left.question_id,
                )
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


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((candidate, parent)) == os.path.commonpath(
            (parent, parent)
        )
    except ValueError:
        return False


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


def _load_json_array(path: Path, error_code: str) -> list[Any]:
    if path.is_symlink() or not path.is_file():
        raise BatchRunnerError(error_code, f"JSON file is missing: {path.name}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise BatchRunnerError(error_code, f"JSON file has a UTF-8 BOM: {path.name}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(error_code, f"JSON file is invalid: {path.name}") from exc
    if not isinstance(payload, list):
        raise BatchRunnerError(error_code, f"JSON file must be an array: {path.name}")
    return payload


def _nonempty_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalized_text(value: str) -> str:
    return " ".join(value.split()).casefold()


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
            prefix=".wave-c-atomic-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(_extended_windows_path(temporary), _extended_windows_path(path))
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _extended_windows_path(path: Path) -> str:
    resolved = str(path.resolve(strict=False))
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved[2:]
    return "\\\\?\\" + resolved


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
