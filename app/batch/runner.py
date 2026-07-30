"""Deterministic, provider-free T07 Day 2 batch runner skeleton."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from app.batch.checkpoint import write_checkpoint, write_model_atomically
from app.batch.errors import BatchRunnerError
from app.contracts.batch import (
    BatchBudget,
    BatchJob,
    BatchManifest,
    CheckpointRecord,
    FailureRecord,
    JobStatus,
    ModelRoute,
    ResultKind,
    RetryPolicy,
    SourceKind,
)


EXPECTED_JOB_COUNT = 125
SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TERMINAL_JOB_STATUSES = frozenset(
    {JobStatus.BLOCKED, JobStatus.FAILED, JobStatus.COMPLETED}
)


def canonical_input_hash(record: dict[str, Any]) -> str:
    canonical = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def register_failure(
    job: BatchJob,
    *,
    error_code: str,
    message: str,
    retryable: bool,
) -> BatchJob:
    next_attempt = job.attempt + 1
    if next_attempt > job.retry_policy.max_attempts:
        raise BatchRunnerError(
            "RETRY_LIMIT_EXCEEDED",
            (
                f"Job {job.question_id} already reached "
                f"{job.retry_policy.max_attempts} attempts"
            ),
        )
    if job.status in TERMINAL_JOB_STATUSES:
        raise BatchRunnerError(
            "JOB_TERMINAL",
            (
                f"Job {job.question_id} is already terminal with status "
                f"{job.status.value}"
            ),
        )

    status = (
        JobStatus.RETRY_WAIT
        if retryable and next_attempt < job.retry_policy.max_attempts
        else JobStatus.FAILED
    )
    payload = job.model_dump()
    payload["attempt"] = next_attempt
    payload["status"] = status
    payload["failures"].append(
        FailureRecord(
            error_code=error_code,
            message=message,
            retryable=retryable,
            attempt=next_attempt,
        ).model_dump()
    )
    return BatchJob.model_validate(payload)


class BatchRunner:
    """Build and persist a dry-run queue without invoking its provider."""

    def __init__(
        self,
        run_root: str | Path,
        provider: Callable[..., Any] | None = None,
    ) -> None:
        self.run_root = Path(run_root)
        self._provider = provider
        self._provider_calls = 0

    @property
    def provider_calls(self) -> int:
        return self._provider_calls

    def dry_run(
        self,
        source_path: str | Path,
        *,
        batch_id: str,
        source_kind: SourceKind,
    ) -> BatchManifest:
        normalized_batch_id = batch_id.strip()
        if not SAFE_PATH_SEGMENT.fullmatch(normalized_batch_id):
            raise BatchRunnerError(
                "BATCH_ID_INVALID",
                "batch_id must be one safe path segment",
            )

        source = Path(source_path)
        questions, source_hash = _load_question_source(source, source_kind)
        retry_policy = RetryPolicy()
        route = ModelRoute()
        jobs = [
            _build_planned_job(
                normalized_batch_id,
                record,
                source_hash,
                retry_policy,
                route,
            )
            for record in questions
        ]

        manifest = BatchManifest(
            batch_id=normalized_batch_id,
            source_kind=source_kind,
            source_path=_display_source_path(source),
            source_hash=source_hash,
            dry_run=True,
            model_route=route,
            budget=BatchBudget(),
            retry_policy=retry_policy,
            jobs=jobs,
        )

        batch_root = self.run_root / normalized_batch_id
        checkpoint_root = batch_root / "checkpoints"
        for job in manifest.jobs:
            write_checkpoint(
                checkpoint_root / f"{job.question_id}.json",
                CheckpointRecord.from_job(job),
            )
        write_model_atomically(batch_root / "manifest.json", manifest)
        return manifest

    def run_isolated(
        self,
        manifest: BatchManifest,
        processor: Callable[[BatchJob], BatchJob],
    ) -> BatchManifest:
        """Process every non-terminal job while isolating per-job failures."""

        updated_jobs: list[BatchJob] = []
        batch_root = self.run_root / manifest.batch_id
        checkpoint_root = batch_root / "checkpoints"

        for original in manifest.jobs:
            if original.status in TERMINAL_JOB_STATUSES:
                updated = original.model_copy(deep=True)
            else:
                try:
                    candidate = processor(original.model_copy(deep=True))
                    if not isinstance(candidate, BatchJob):
                        raise BatchRunnerError(
                            "JOB_PROCESSOR_RESULT_INVALID",
                            "Job processor must return a BatchJob",
                        )
                    updated = BatchJob.model_validate(candidate.model_dump())
                    _require_same_job_identity(original, updated)
                except Exception as exc:
                    error_code = (
                        exc.error_code
                        if isinstance(exc, BatchRunnerError)
                        else "JOB_EXECUTION_FAILED"
                    )
                    message = str(exc).strip() or type(exc).__name__
                    updated = register_failure(
                        original,
                        error_code=error_code,
                        message=message,
                        retryable=False,
                    )

            write_checkpoint(
                checkpoint_root / f"{updated.question_id}.json",
                CheckpointRecord.from_job(updated),
            )
            updated_jobs.append(updated)

        payload = manifest.model_dump()
        payload["jobs"] = [job.model_dump() for job in updated_jobs]
        payload.pop("total", None)
        payload.pop("status_counts", None)
        updated_manifest = BatchManifest.model_validate(payload)
        write_model_atomically(batch_root / "manifest.json", updated_manifest)
        return updated_manifest


def _load_question_source(
    source_path: Path,
    source_kind: SourceKind,
) -> tuple[list[dict[str, Any]], str]:
    if not source_path.is_file():
        raise BatchRunnerError(
            "QUESTION_SOURCE_NOT_FOUND",
            f"Question source does not exist: {source_path}",
        )

    try:
        raw = source_path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "QUESTION_SOURCE_INVALID",
            f"Question source is not valid UTF-8 JSON: {source_path}",
        ) from exc

    if source_kind is SourceKind.SYNTHETIC:
        if (
            not isinstance(payload, dict)
            or payload.get("synthetic") is not True
        ):
            raise BatchRunnerError(
                "SYNTHETIC_SOURCE_NOT_MARKED",
                "Synthetic source must contain synthetic=true",
            )
        questions = payload.get("questions")
    else:
        if isinstance(payload, dict) and payload.get("synthetic") is True:
            raise BatchRunnerError(
                "SOURCE_KIND_MISMATCH",
                "Marked synthetic source cannot be loaded as production",
            )
        questions = payload

    if not isinstance(questions, list):
        raise BatchRunnerError(
            "QUESTION_SOURCE_INVALID",
            "Question source must provide a JSON question list",
        )
    if len(questions) != EXPECTED_JOB_COUNT:
        raise BatchRunnerError(
            "QUESTION_COUNT_INVALID",
            (
                f"Question source must contain exactly {EXPECTED_JOB_COUNT} "
                f"records, found {len(questions)}"
            ),
        )

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(questions):
        if not isinstance(record, dict):
            raise BatchRunnerError(
                "QUESTION_RECORD_INVALID",
                f"Question record at index {index} is not an object",
            )
        question_id = record.get("question_id")
        if not isinstance(question_id, str) or not SAFE_PATH_SEGMENT.fullmatch(
            question_id
        ):
            raise BatchRunnerError(
                "QUESTION_ID_INVALID",
                f"Question record at index {index} has an invalid question_id",
            )
        if question_id in seen_ids:
            raise BatchRunnerError(
                "DUPLICATE_QUESTION_ID",
                f"Duplicate question_id: {question_id}",
            )
        seen_ids.add(question_id)
        normalized.append(record)

    return normalized, hashlib.sha256(raw).hexdigest()


def _build_planned_job(
    batch_id: str,
    record: dict[str, Any],
    source_hash: str,
    retry_policy: RetryPolicy,
    route: ModelRoute,
) -> BatchJob:
    question_id = str(record["question_id"])
    input_hash = canonical_input_hash(record)
    hash_prefix = input_hash[:16]
    workspace = PurePosixPath(
        batch_id,
        question_id,
        "workspace",
    ).as_posix()
    return BatchJob(
        batch_id=batch_id,
        question_id=question_id,
        source_hash=source_hash,
        input_hash=input_hash,
        workspace=workspace,
        context_id=f"ctx:{batch_id}:{question_id}:{hash_prefix}",
        cache_namespace=f"cache:{batch_id}:{question_id}:{hash_prefix}",
        status=JobStatus.QUEUED,
        result_kind=ResultKind.PLANNED,
        mock=False,
        attempt=0,
        retry_policy=retry_policy.model_copy(deep=True),
        budget=BatchBudget(),
        model_route=route.model_copy(deep=True),
    )


def _require_same_job_identity(
    original: BatchJob,
    candidate: BatchJob,
) -> None:
    immutable_fields = (
        "schema_version",
        "batch_id",
        "question_id",
        "source_hash",
        "input_hash",
        "workspace",
        "context_id",
        "cache_namespace",
        "retry_policy",
        "model_route",
    )
    changed = [
        field_name
        for field_name in immutable_fields
        if getattr(original, field_name) != getattr(candidate, field_name)
    ]
    if changed:
        raise BatchRunnerError(
            "JOB_IDENTITY_MUTATION",
            f"Job processor changed immutable fields: {changed}",
        )


def _display_source_path(source_path: Path) -> str:
    try:
        return source_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return source_path.as_posix()
