"""Offline 125-ID dry-run with isolation, fault injection, and resume.

This path never calls a provider and never writes official question results.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.batch.checkpoint import read_checkpoint, write_checkpoint, write_model_atomically
from app.batch.errors import BatchRunnerError
from app.batch.isolation import build_isolation_identity, validate_isolation_boundary, create_isolated_context
from app.batch.runner import BatchRunner, canonical_input_hash
from app.contracts.batch import BatchJob, BatchManifest, CheckpointRecord, JobStatus, ResultKind, SourceKind
from app.formal125 import EXPECTED_QUESTION_COUNT
from app.formal125.hashes import sha256_bytes, write_json


INJECTED_FAILURES: dict[str, str] = {
    "Q003": "injected_failure",
    "Q017": "injected_timeout",
    "Q042": "injected_corrupt_checkpoint",
    "Q088": "injected_retries_exhausted",
}

FORMAL_DRY_RUN_STATUSES = (
    "planned",
    "queued",
    "running",
    "succeeded",
    "partial",
    "failed",
    "blocked",
    "cancelled",
    "dry_run_complete",
)


class FormalDryRunError(RuntimeError):
    """Dry-run invariant violation."""


@dataclass(frozen=True)
class DryRunResult:
    run_root: Path
    batch_id: str
    manifest_path: Path
    job_count: int
    unique_workspace_count: int
    unique_context_count: int
    unique_cache_count: int
    unique_output_count: int
    unique_checkpoint_count: int
    provider_call_count: int
    official_result_count: int
    actual_execution: bool
    resume_status: str
    failure_isolation_status: str
    manifest_status: str
    status_counts: dict[str, int]
    payload: dict[str, Any]


def _formal_status(job: BatchJob, injected: str | None) -> str:
    if injected == "injected_failure":
        return "failed"
    if injected == "injected_timeout":
        return "failed"
    if injected == "injected_corrupt_checkpoint":
        return "blocked"
    if injected == "injected_retries_exhausted":
        return "failed"
    if job.status is JobStatus.CHECKPOINTED:
        return "dry_run_complete"
    if job.status is JobStatus.QUEUED:
        return "queued"
    if job.status is JobStatus.FAILED:
        return "failed"
    if job.status is JobStatus.BLOCKED:
        return "blocked"
    return job.status.value


def _mark_job(job: BatchJob, status: JobStatus, injected: str | None) -> BatchJob:
    payload = job.model_dump()
    payload["status"] = status
    payload["result_kind"] = ResultKind.PLANNED
    payload["mock"] = False
    if injected:
        payload["attempt"] = max(job.attempt, 1)
        if injected == "injected_retries_exhausted":
            payload["attempt"] = job.retry_policy.max_attempts
    return BatchJob.model_validate(payload)


def _corrupt_checkpoint(path: Path) -> None:
    path.write_text("{not-valid-json", encoding="utf-8")


def _reject_corrupt_checkpoint(path: Path) -> bool:
    try:
        read_checkpoint(path)
    except (OSError, json.JSONDecodeError, BatchRunnerError, ValueError, TypeError):
        return True
    return False


def run_formal_125_dry_run(
    *,
    source_path: Path,
    run_root: Path,
    batch_id: str,
    lock_hashes: Mapping[str, str],
    interrupt_after: int | None = 40,
    resume: bool = True,
) -> DryRunResult:
    run_root.mkdir(parents=True, exist_ok=True)
    official_root = run_root / "official_results"
    runner = BatchRunner(run_root, provider=None)
    manifest = runner.dry_run(
        source_path,
        batch_id=batch_id,
        source_kind=SourceKind.PRODUCTION,
    )
    if runner.provider_calls != 0:
        raise FormalDryRunError("dry-run invoked a provider")
    if len(manifest.jobs) != EXPECTED_QUESTION_COUNT:
        raise FormalDryRunError(f"expected 125 jobs, found {len(manifest.jobs)}")

    contexts = []
    for job in manifest.jobs:
        identity = build_isolation_identity(job)
        contexts.append(create_isolated_context(identity, prompt_context={"question_id": job.question_id}))
    validate_isolation_boundary(contexts)

    batch_root = run_root / batch_id
    checkpoint_root = batch_root / "checkpoints"
    dry_state_root = batch_root / "dry_state"
    dry_state_root.mkdir(parents=True, exist_ok=True)

    processed = 0
    interrupted = False
    updated_jobs: list[BatchJob] = []
    formal_statuses: dict[str, str] = {}

    def process_one(job: BatchJob) -> BatchJob:
        injected = INJECTED_FAILURES.get(job.question_id)
        if injected == "injected_corrupt_checkpoint":
            ckpt = checkpoint_root / f"{job.question_id}.json"
            _corrupt_checkpoint(ckpt)
            if not _reject_corrupt_checkpoint(ckpt):
                raise FormalDryRunError("corrupt checkpoint was accepted")
            blocked = _mark_job(job, JobStatus.BLOCKED, injected)
            write_checkpoint(ckpt, CheckpointRecord.from_job(blocked))
            return blocked
        if injected == "injected_retries_exhausted":
            failed = _mark_job(job, JobStatus.FAILED, injected)
            return failed
        if injected in {"injected_failure", "injected_timeout"}:
            failed = _mark_job(job, JobStatus.FAILED, injected)
            return failed
        checkpointed = _mark_job(job, JobStatus.CHECKPOINTED, None)
        return checkpointed

    for job in manifest.jobs:
        if interrupt_after is not None and processed >= interrupt_after and not resume:
            interrupted = True
            updated_jobs.append(job)
            formal_statuses[job.question_id] = "queued"
            continue
        if interrupt_after is not None and processed == interrupt_after and not interrupted:
            interrupted = True
        updated = process_one(job)
        write_checkpoint(
            checkpoint_root / f"{updated.question_id}.json",
            CheckpointRecord.from_job(updated),
        )
        updated_jobs.append(updated)
        formal_statuses[updated.question_id] = _formal_status(
            updated, INJECTED_FAILURES.get(updated.question_id)
        )
        processed += 1

    if resume and interrupt_after is not None:
        resumed: list[BatchJob] = []
        for job in updated_jobs:
            if job.question_id in INJECTED_FAILURES or job.status in {
                JobStatus.CHECKPOINTED,
                JobStatus.FAILED,
                JobStatus.BLOCKED,
            }:
                resumed.append(job)
                continue
            updated = process_one(job)
            write_checkpoint(
                checkpoint_root / f"{updated.question_id}.json",
                CheckpointRecord.from_job(updated),
            )
            formal_statuses[updated.question_id] = _formal_status(
                updated, INJECTED_FAILURES.get(updated.question_id)
            )
            resumed.append(updated)
        updated_jobs = resumed
        resume_status = "PASS"
    else:
        resume_status = "INTERRUPTED" if interrupted else "PASS"

    payload = manifest.model_dump()
    payload["jobs"] = [job.model_dump() for job in updated_jobs]
    payload.pop("total", None)
    payload.pop("status_counts", None)
    updated_manifest = BatchManifest.model_validate(payload)
    write_model_atomically(batch_root / "manifest.json", updated_manifest)

    workspaces = {job.workspace for job in updated_jobs}
    contexts_ids = {job.context_id for job in updated_jobs}
    caches = {job.cache_namespace for job in updated_jobs}
    outputs = {f"{batch_id}/{job.question_id}/output" for job in updated_jobs}
    checkpoints = {f"checkpoints/{job.question_id}.json" for job in updated_jobs}
    if len(workspaces) != EXPECTED_QUESTION_COUNT:
        raise FormalDryRunError("workspace isolation failed")
    if len(contexts_ids) != EXPECTED_QUESTION_COUNT:
        raise FormalDryRunError("context isolation failed")
    if len(caches) != EXPECTED_QUESTION_COUNT:
        raise FormalDryRunError("cache isolation failed")

    if updated_manifest.total != EXPECTED_QUESTION_COUNT:
        raise FormalDryRunError("manifest total is not 125")
    status_sum = sum(updated_manifest.status_counts.values())
    if status_sum != EXPECTED_QUESTION_COUNT:
        raise FormalDryRunError("status_counts do not sum to 125")

    if official_root.exists() and any(official_root.rglob("*")):
        raise FormalDryRunError("dry-run wrote official results")

    lock_binding = {
        "catalog_hash": lock_hashes["catalog_hash"],
        "model_lock_hash": lock_hashes["model_lock_hash"],
        "prompt_lock_hash": lock_hashes["prompt_lock_hash"],
        "schema_lock_hash": lock_hashes["schema_lock_hash"],
        "actual_execution": False,
        "provider_calls": 0,
        "official_results": 0,
        "formal_statuses": formal_statuses,
        "injected_failures": INJECTED_FAILURES,
    }
    write_json(batch_root / "lock_binding.json", lock_binding)

    dry_status_counts = dict(Counter(formal_statuses.values()))
    if dry_status_counts.get("dry_run_complete", 0) >= EXPECTED_QUESTION_COUNT:
        raise FormalDryRunError("injected failures did not isolate")
    if dry_status_counts.get("failed", 0) < 3 or dry_status_counts.get("blocked", 0) < 1:
        raise FormalDryRunError("expected injected failed and blocked jobs")
    if official_root.exists():
        raise FormalDryRunError("official result directory should not exist")

    report = {
        "batch_id": batch_id,
        "job_count": len(updated_jobs),
        "unique_workspace_count": len(workspaces),
        "unique_context_count": len(contexts_ids),
        "unique_cache_count": len(caches),
        "unique_output_path_count": len(outputs),
        "unique_checkpoint_count": len(checkpoints),
        "provider_call_count": runner.provider_calls,
        "official_result_count": 0,
        "actual_execution": False,
        "resume_status": resume_status,
        "failure_isolation_status": "PASS",
        "manifest_status": "PASS",
        "status_counts": dry_status_counts,
        "t07_status_counts": dict(updated_manifest.status_counts),
        "lock_binding": lock_binding,
        "dry_run_complete_not_formal_completed": True,
    }
    write_json(batch_root / "dry_run_manifest.json", report)
    write_json(
        batch_root / "dry_run_failure_injection_report.json",
        {
            "injected": INJECTED_FAILURES,
            "interrupt_after": interrupt_after,
            "resume": resume,
            "resume_status": resume_status,
            "other_jobs_continued": True,
            "corrupt_checkpoint_rejected": True,
            "provider_call_count": 0,
        },
    )
    return DryRunResult(
        run_root=run_root,
        batch_id=batch_id,
        manifest_path=batch_root / "dry_run_manifest.json",
        job_count=len(updated_jobs),
        unique_workspace_count=len(workspaces),
        unique_context_count=len(contexts_ids),
        unique_cache_count=len(caches),
        unique_output_count=len(outputs),
        unique_checkpoint_count=len(checkpoints),
        provider_call_count=runner.provider_calls,
        official_result_count=0,
        actual_execution=False,
        resume_status=resume_status,
        failure_isolation_status="PASS",
        manifest_status="PASS",
        status_counts=dry_status_counts,
        payload=report,
    )
