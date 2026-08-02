"""Atomic checkpoint persistence and compatibility-only resume."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ValidationError

from app.batch.errors import BatchRunnerError
from app.contracts.batch import (
    BatchJob,
    CheckpointRecord,
    ResumePolicy,
)


def write_model_atomically(path: Path, model: BaseModel) -> None:
    """Persist one Pydantic model without exposing partial JSON to readers."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f"{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(model.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def write_checkpoint(path: Path, checkpoint: CheckpointRecord) -> None:
    write_model_atomically(Path(path), checkpoint)


def read_checkpoint(path: Path) -> CheckpointRecord:
    source = Path(path)
    if not source.is_file():
        raise BatchRunnerError(
            "CHECKPOINT_NOT_FOUND",
            f"Checkpoint does not exist: {source}",
        )
    try:
        return CheckpointRecord.model_validate_json(
            source.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValidationError, ValueError) as exc:
        raise BatchRunnerError(
            "CHECKPOINT_INVALID",
            f"Checkpoint is not valid: {source}",
        ) from exc


def resume_job(
    checkpoint: CheckpointRecord,
    expected_job: BatchJob,
    policy: ResumePolicy,
) -> BatchJob:
    if not policy.enabled:
        raise BatchRunnerError("RESUME_DISABLED", "Resume policy is disabled")
    if checkpoint.batch_id != expected_job.batch_id:
        raise BatchRunnerError(
            "CHECKPOINT_BATCH_MISMATCH",
            "Checkpoint batch_id does not match the requested job",
        )
    if checkpoint.question_id != expected_job.question_id:
        raise BatchRunnerError(
            "CHECKPOINT_QUESTION_MISMATCH",
            "Checkpoint question_id does not match the requested job",
        )
    if (
        policy.require_source_hash_match
        and checkpoint.source_hash != expected_job.source_hash
    ):
        raise BatchRunnerError(
            "STALE_CHECKPOINT_SOURCE_HASH",
            "Checkpoint source_hash does not match the current source",
        )
    if (
        policy.require_input_hash_match
        and checkpoint.input_hash != expected_job.input_hash
    ):
        raise BatchRunnerError(
            "STALE_CHECKPOINT_INPUT_HASH",
            "Checkpoint input_hash does not match the current question",
        )

    route_mismatch = (
        checkpoint.route_id != expected_job.model_route.route_id
        or checkpoint.provider != expected_job.model_route.provider
        or checkpoint.model != expected_job.model_route.model
    )
    if policy.require_model_route_match and route_mismatch:
        raise BatchRunnerError(
            "STALE_CHECKPOINT_MODEL_ROUTE",
            "Checkpoint model route does not match the current job",
        )
    if (
        policy.require_prompt_hash_match
        and checkpoint.prompt_hash != expected_job.model_route.prompt_hash
    ):
        raise BatchRunnerError(
            "STALE_CHECKPOINT_PROMPT_HASH",
            "Checkpoint prompt_hash does not match the current job",
        )

    version_mismatch = (
        (
            policy.require_schema_version_match
            and checkpoint.schema_version != expected_job.schema_version
        )
        or (
            policy.require_model_version_match
            and checkpoint.model_version
            != expected_job.model_route.model_version
        )
        or (
            policy.require_prompt_version_match
            and checkpoint.prompt_version
            != expected_job.model_route.prompt_version
        )
    )
    if version_mismatch:
        raise BatchRunnerError(
            "STALE_CHECKPOINT_VERSION",
            "Checkpoint schema, model, or prompt version is stale",
        )
    return checkpoint.job.model_copy(deep=True)
