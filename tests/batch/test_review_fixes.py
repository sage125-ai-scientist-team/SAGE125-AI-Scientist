from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError


SYNTHETIC_SOURCE = (
    Path(__file__).parent / "fixtures" / "questions_125.synthetic.json"
)


def _modules() -> tuple[Any, Any, Any]:
    import app.batch.checkpoint as checkpoint
    import app.batch.runner as runner
    import app.contracts.batch as contract

    return contract, runner, checkpoint


def _dry_run(tmp_path: Path, batch_id: str = "review-fix") -> Any:
    contract, runner, _ = _modules()
    return runner.BatchRunner(tmp_path).dry_run(
        SYNTHETIC_SOURCE,
        batch_id=batch_id,
        source_kind=contract.SourceKind.SYNTHETIC,
    )


def test_batch_failure_is_isolated_and_remaining_124_jobs_continue(
    tmp_path: Path,
) -> None:
    contract, runner, _ = _modules()
    manifest = _dry_run(tmp_path)
    processed_ids: list[str] = []

    def processor(job: Any) -> Any:
        processed_ids.append(job.question_id)
        if job.question_id == "Q063":
            raise RuntimeError("synthetic injected single-job failure")
        return job.model_copy(
            update={"status": contract.JobStatus.CHECKPOINTED}
        )

    updated = runner.BatchRunner(tmp_path).run_isolated(
        manifest,
        processor,
    )

    assert processed_ids == [f"Q{number:03d}" for number in range(1, 126)]
    assert updated.total == 125
    assert updated.status_counts == {"checkpointed": 124, "failed": 1}
    failed = next(job for job in updated.jobs if job.question_id == "Q063")
    assert failed.status is contract.JobStatus.FAILED
    assert failed.attempt == 1
    assert failed.failures[0].error_code == "JOB_EXECUTION_FAILED"
    assert "synthetic injected single-job failure" in failed.failures[0].message
    assert all(
        job.status is contract.JobStatus.CHECKPOINTED
        for job in updated.jobs
        if job.question_id != "Q063"
    )


def test_resume_rejects_stale_source_hash(tmp_path: Path) -> None:
    _, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    restored = checkpoint.read_checkpoint(
        tmp_path / "review-fix" / "checkpoints" / "Q001.json"
    )
    changed_job = manifest.jobs[0].model_copy(
        update={"source_hash": "f" * 64}
    )

    with pytest.raises(checkpoint.BatchRunnerError) as raised:
        checkpoint.resume_job(
            restored,
            changed_job,
            manifest.resume_policy,
        )

    assert raised.value.error_code == "STALE_CHECKPOINT_SOURCE_HASH"


def test_resume_rejects_checkpoint_from_another_question(
    tmp_path: Path,
) -> None:
    _, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    restored = checkpoint.read_checkpoint(
        tmp_path / "review-fix" / "checkpoints" / "Q001.json"
    )

    with pytest.raises(checkpoint.BatchRunnerError) as raised:
        checkpoint.resume_job(
            restored,
            manifest.jobs[1],
            manifest.resume_policy,
        )

    assert raised.value.error_code == "CHECKPOINT_QUESTION_MISMATCH"


def test_resume_rejects_changed_model_route(tmp_path: Path) -> None:
    _, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    restored = checkpoint.read_checkpoint(
        tmp_path / "review-fix" / "checkpoints" / "Q001.json"
    )
    changed_route = manifest.jobs[0].model_route.model_copy(
        update={"route_id": "different-route"}
    )
    changed_job = manifest.jobs[0].model_copy(
        update={"model_route": changed_route}
    )

    with pytest.raises(checkpoint.BatchRunnerError) as raised:
        checkpoint.resume_job(
            restored,
            changed_job,
            manifest.resume_policy,
        )

    assert raised.value.error_code == "STALE_CHECKPOINT_MODEL_ROUTE"


def test_resume_rejects_changed_prompt_hash(tmp_path: Path) -> None:
    _, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    restored = checkpoint.read_checkpoint(
        tmp_path / "review-fix" / "checkpoints" / "Q001.json"
    )
    changed_route = manifest.jobs[0].model_route.model_copy(
        update={"prompt_hash": "f" * 64}
    )
    changed_job = manifest.jobs[0].model_copy(
        update={"model_route": changed_route}
    )

    with pytest.raises(checkpoint.BatchRunnerError) as raised:
        checkpoint.resume_job(
            restored,
            changed_job,
            manifest.resume_policy,
        )

    assert raised.value.error_code == "STALE_CHECKPOINT_PROMPT_HASH"


def test_corrupt_checkpoint_json_fails_closed(tmp_path: Path) -> None:
    _, _, checkpoint = _modules()
    corrupt = tmp_path / "corrupt-checkpoint.json"
    corrupt.write_text('{"checkpoint_version":', encoding="utf-8")

    with pytest.raises(checkpoint.BatchRunnerError) as raised:
        checkpoint.read_checkpoint(corrupt)

    assert raised.value.error_code == "CHECKPOINT_INVALID"


def test_batch_job_json_round_trip() -> None:
    contract, _, _ = _modules()
    job = contract.BatchJob(
        batch_id="round-trip",
        question_id="Q001",
        source_hash="a" * 64,
        input_hash="b" * 64,
        workspace="round-trip/Q001/workspace",
        context_id="ctx:round-trip:Q001:bbbbbbbbbbbbbbbb",
        cache_namespace="cache:round-trip:Q001:bbbbbbbbbbbbbbbb",
    )

    restored = contract.BatchJob.model_validate_json(job.model_dump_json())

    assert restored == job


def test_checkpoint_record_json_round_trip(tmp_path: Path) -> None:
    contract, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    record = contract.CheckpointRecord.from_job(manifest.jobs[0])

    restored = contract.CheckpointRecord.model_validate_json(
        record.model_dump_json()
    )
    persisted = checkpoint.read_checkpoint(
        tmp_path / "review-fix" / "checkpoints" / "Q001.json"
    )

    assert restored == record
    assert persisted.job == record.job
    assert persisted.checkpoint_version == record.checkpoint_version


def test_synthetic_manifest_rejects_completed_actual_job() -> None:
    contract, _, _ = _modules()
    fields = {
        name: f"Synthetic value for {name}"
        for name in contract.STANDARD_OUTPUT_FIELDS
    }
    artifacts = {
        name: f"synthetic-formal/Q001/{name}"
        for name in contract.REQUIRED_ARTIFACTS
    }
    route = contract.ModelRoute(
        route_id="formal-route",
        provider="synthetic-provider",
        model="synthetic-model",
        model_version="synthetic-model-v1",
        prompt_version="synthetic-prompt-v1",
        prompt_hash="c" * 64,
    )
    job = contract.BatchJob(
        batch_id="synthetic-formal",
        question_id="Q001",
        source_hash="a" * 64,
        input_hash="b" * 64,
        workspace="synthetic-formal/Q001/workspace",
        context_id="ctx:synthetic-formal:Q001:bbbbbbbbbbbbbbbb",
        cache_namespace="cache:synthetic-formal:Q001:bbbbbbbbbbbbbbbb",
        status=contract.JobStatus.COMPLETED,
        result_kind=contract.ResultKind.ACTUAL,
        model_route=route,
        output_contract=contract.OutputContract(
            fields=fields,
            artifacts=artifacts,
        ),
    )

    with pytest.raises(
        ValidationError,
        match="synthetic manifest cannot contain completed actual jobs",
    ):
        contract.BatchManifest(
            batch_id="synthetic-formal",
            source_kind=contract.SourceKind.SYNTHETIC,
            source_path="tests/batch/fixtures/synthetic.json",
            source_hash="a" * 64,
            dry_run=False,
            model_route=route,
            jobs=[job],
        )


def test_manifest_derives_total_and_status_counts(tmp_path: Path) -> None:
    manifest = _dry_run(tmp_path)

    assert manifest.total == len(manifest.jobs) == 125
    assert manifest.status_counts == {"queued": 125}
    payload = json.loads(manifest.model_dump_json())
    assert payload["total"] == len(payload["jobs"])
    assert payload["status_counts"] == {"queued": 125}


def test_manifest_rejects_inconsistent_serialized_counts(
    tmp_path: Path,
) -> None:
    contract, _, _ = _modules()
    manifest = _dry_run(tmp_path)
    payload = manifest.model_dump()
    payload["total"] = 124
    payload["status_counts"] = {"queued": 124}

    with pytest.raises(
        ValidationError,
        match="manifest total does not match jobs",
    ):
        contract.BatchManifest.model_validate(payload)


def test_atomic_write_failure_preserves_previous_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    target = tmp_path / "review-fix" / "checkpoints" / "Q001.json"
    original = target.read_bytes()
    record = contract.CheckpointRecord.from_job(manifest.jobs[0])

    def fail_replace(source: Any, destination: Any) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(checkpoint.os, "replace", fail_replace)

    with pytest.raises(OSError, match="synthetic replace failure"):
        checkpoint.write_checkpoint(target, record)

    assert target.read_bytes() == original
    assert not list(target.parent.glob("*.tmp"))


def test_existing_report_file_does_not_mark_dry_run_job_completed(
    tmp_path: Path,
) -> None:
    contract, _, checkpoint = _modules()
    report = tmp_path / "review-fix" / "Q001" / "report.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"status": "completed"}', encoding="utf-8")

    manifest = _dry_run(tmp_path)
    restored = checkpoint.read_checkpoint(
        tmp_path / "review-fix" / "checkpoints" / "Q001.json"
    )

    assert manifest.jobs[0].status is contract.JobStatus.QUEUED
    assert restored.status is contract.JobStatus.QUEUED
    assert restored.job.result_kind is contract.ResultKind.PLANNED


def test_batch_id_path_traversal_is_rejected(tmp_path: Path) -> None:
    contract, runner, _ = _modules()

    with pytest.raises(runner.BatchRunnerError) as raised:
        runner.BatchRunner(tmp_path).dry_run(
            SYNTHETIC_SOURCE,
            batch_id="../evil",
            source_kind=contract.SourceKind.SYNTHETIC,
        )

    assert raised.value.error_code == "BATCH_ID_INVALID"
