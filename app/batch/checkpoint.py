"""Atomic checkpoint persistence and compatibility-only resume."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ValidationError

from app.batch.errors import BatchRunnerError
from app.contracts.batch import (
    BatchJob,
    BatchJobV2,
    CheckpointRecord,
    CheckpointRecordV2,
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


def write_checkpoint(
    path: Path,
    checkpoint: CheckpointRecord | CheckpointRecordV2,
) -> None:
    write_model_atomically(Path(path), checkpoint)


def read_checkpoint(path: Path) -> CheckpointRecord | CheckpointRecordV2:
    source = Path(path)
    if not source.is_file():
        raise BatchRunnerError(
            "CHECKPOINT_NOT_FOUND",
            f"Checkpoint does not exist: {source}",
        )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("checkpoint must be an object")
        checkpoint_version = payload.get("checkpoint_version")
        if checkpoint_version == "t07.checkpoint.v2":
            return CheckpointRecordV2.model_validate(payload)
        return CheckpointRecord.model_validate(payload)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TypeError,
        ValidationError,
        ValueError,
    ) as exc:
        raise BatchRunnerError(
            "CHECKPOINT_INVALID",
            f"Checkpoint is not valid: {source}",
        ) from exc


def resume_job(
    checkpoint: CheckpointRecord | CheckpointRecordV2,
    expected_job: BatchJob | BatchJobV2,
    policy: ResumePolicy,
) -> BatchJob | BatchJobV2:
    if not policy.enabled:
        raise BatchRunnerError("RESUME_DISABLED", "Resume policy is disabled")
    checkpoint_is_v2 = isinstance(checkpoint, CheckpointRecordV2)
    expected_is_v2 = isinstance(expected_job, BatchJobV2)
    if checkpoint_is_v2 != expected_is_v2:
        raise BatchRunnerError(
            "CHECKPOINT_SCHEMA_MISMATCH",
            "v1 checkpoints cannot resume v2 jobs and v2 checkpoints cannot resume v1 jobs",
        )
    if checkpoint_is_v2 and expected_is_v2:
        assert isinstance(checkpoint, CheckpointRecordV2)
        assert isinstance(expected_job, BatchJobV2)
        if (
            checkpoint.budget_policy_version
            != expected_job.budget_policy.version
            or checkpoint.budget_mode is not expected_job.budget_policy.mode
            or checkpoint.captain_waiver_reference
            != expected_job.budget_policy.captain_waiver_reference
        ):
            raise BatchRunnerError(
                "BUDGET_POLICY_MISMATCH",
                "checkpoint budget policy does not match the approved v2 job",
            )
        if checkpoint.freeze_id != expected_job.freeze_id:
            raise BatchRunnerError(
                "CHECKPOINT_FREEZE_MISMATCH",
                "checkpoint freeze ID does not match the requested v2 job",
            )
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
