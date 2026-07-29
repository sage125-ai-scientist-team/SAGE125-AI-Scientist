from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


SYNTHETIC_SOURCE = (
    Path(__file__).parent / "fixtures" / "questions_125.synthetic.json"
)


def _modules() -> tuple[Any, Any, Any]:
    import app.batch.checkpoint as checkpoint
    import app.batch.runner as runner
    import app.contracts.batch as contract

    return contract, runner, checkpoint


def _dry_run(tmp_path: Path, provider: Any = None) -> Any:
    contract, runner, _ = _modules()
    return runner.BatchRunner(tmp_path, provider=provider).dry_run(
        SYNTHETIC_SOURCE,
        batch_id="day2-test",
        source_kind=contract.SourceKind.SYNTHETIC,
    )


def test_synthetic_fixture_is_explicitly_marked_and_has_q001_to_q125() -> None:
    payload = json.loads(SYNTHETIC_SOURCE.read_text(encoding="utf-8"))
    question_ids = [record["question_id"] for record in payload["questions"]]

    assert payload["synthetic"] is True
    assert question_ids == [f"Q{number:03d}" for number in range(1, 126)]
    assert all(
        record["question"].startswith("Synthetic contract question ")
        for record in payload["questions"]
    )


def test_dry_run_creates_exactly_125_planned_jobs(tmp_path: Path) -> None:
    contract, _, _ = _modules()
    manifest = _dry_run(tmp_path)

    assert len(manifest.jobs) == 125
    assert manifest.dry_run is True
    assert all(job.status is contract.JobStatus.QUEUED for job in manifest.jobs)
    assert all(
        job.result_kind is contract.ResultKind.PLANNED for job in manifest.jobs
    )
    assert sum(job.budget.tokens_used for job in manifest.jobs) == 0


def test_every_dry_run_job_has_a_unique_workspace(tmp_path: Path) -> None:
    manifest = _dry_run(tmp_path)

    assert len({job.workspace for job in manifest.jobs}) == 125


def test_every_dry_run_job_has_a_unique_context_id(tmp_path: Path) -> None:
    manifest = _dry_run(tmp_path)

    assert len({job.context_id for job in manifest.jobs}) == 125


def test_every_dry_run_job_has_a_unique_cache_namespace(
    tmp_path: Path,
) -> None:
    manifest = _dry_run(tmp_path)

    assert len({job.cache_namespace for job in manifest.jobs}) == 125


def test_dry_run_never_invokes_model_provider(tmp_path: Path) -> None:
    def forbidden_provider_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("dry-run invoked model provider")

    manifest = _dry_run(tmp_path, provider=forbidden_provider_call)

    assert len(manifest.jobs) == 125
    assert all(job.result_kind.value == "planned" for job in manifest.jobs)


def test_retry_policy_enforces_hard_attempt_limit() -> None:
    contract, runner, _ = _modules()
    job = contract.BatchJob(
        batch_id="retry-test",
        question_id="Q001",
        input_hash="c" * 64,
        workspace="retry-test/Q001/workspace",
        context_id="ctx:retry-test:Q001:cccccccccccccccc",
        cache_namespace="cache:retry-test:Q001:cccccccccccccccc",
        retry_policy=contract.RetryPolicy(max_attempts=3),
    )

    for expected_attempt in (1, 2):
        job = runner.register_failure(
            job,
            error_code="TRANSIENT_FAILURE",
            message="synthetic transient failure",
            retryable=True,
        )
        assert job.attempt == expected_attempt
        assert job.status is contract.JobStatus.RETRY_WAIT

    job = runner.register_failure(
        job,
        error_code="TRANSIENT_FAILURE",
        message="synthetic terminal failure",
        retryable=True,
    )
    assert job.attempt == 3
    assert job.status is contract.JobStatus.FAILED

    with pytest.raises(runner.BatchRunnerError) as raised:
        runner.register_failure(
            job,
            error_code="TRANSIENT_FAILURE",
            message="must not become a fourth attempt",
            retryable=True,
        )
    assert raised.value.error_code == "RETRY_LIMIT_EXCEEDED"


def test_terminal_job_rejects_additional_failure_registration() -> None:
    contract, runner, _ = _modules()
    job = contract.BatchJob(
        batch_id="terminal-test",
        question_id="Q001",
        input_hash="d" * 64,
        workspace="terminal-test/Q001/workspace",
        context_id="ctx:terminal-test:Q001:dddddddddddddddd",
        cache_namespace="cache:terminal-test:Q001:dddddddddddddddd",
    )
    failed_job = runner.register_failure(
        job,
        error_code="NON_RETRYABLE_FAILURE",
        message="synthetic terminal failure",
        retryable=False,
    )
    assert failed_job.status is contract.JobStatus.FAILED

    with pytest.raises(runner.BatchRunnerError) as raised:
        runner.register_failure(
            failed_job,
            error_code="LATE_FAILURE",
            message="must not mutate a terminal job",
            retryable=True,
        )

    assert raised.value.error_code == "JOB_TERMINAL"


def test_missing_production_source_has_stable_error_code(
    tmp_path: Path,
) -> None:
    contract, runner, _ = _modules()
    missing = tmp_path / "questions_125.json"

    with pytest.raises(runner.BatchRunnerError) as raised:
        runner.BatchRunner(tmp_path).dry_run(
            missing,
            batch_id="missing-production",
            source_kind=contract.SourceKind.PRODUCTION,
        )

    assert raised.value.error_code == "QUESTION_SOURCE_NOT_FOUND"


def test_unmarked_synthetic_source_is_rejected(tmp_path: Path) -> None:
    contract, runner, _ = _modules()
    unmarked = tmp_path / "unmarked.json"
    unmarked.write_text(
        json.dumps({"questions": [{"question_id": "Q001"}]}),
        encoding="utf-8",
    )

    with pytest.raises(runner.BatchRunnerError) as raised:
        runner.BatchRunner(tmp_path).dry_run(
            unmarked,
            batch_id="unmarked",
            source_kind=contract.SourceKind.SYNTHETIC,
        )

    assert raised.value.error_code == "SYNTHETIC_SOURCE_NOT_MARKED"


def test_synthetic_source_cannot_masquerade_as_production(
    tmp_path: Path,
) -> None:
    contract, runner, _ = _modules()

    with pytest.raises(runner.BatchRunnerError) as raised:
        runner.BatchRunner(tmp_path).dry_run(
            SYNTHETIC_SOURCE,
            batch_id="source-kind-mismatch",
            source_kind=contract.SourceKind.PRODUCTION,
        )

    assert raised.value.error_code == "SOURCE_KIND_MISMATCH"


def test_dry_run_writes_readable_checkpoint_and_manifest(
    tmp_path: Path,
) -> None:
    _, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    checkpoint_path = (
        tmp_path / "day2-test" / "checkpoints" / "Q001.json"
    )
    manifest_path = tmp_path / "day2-test" / "manifest.json"

    restored = checkpoint.read_checkpoint(checkpoint_path)

    assert restored.job == manifest.jobs[0]
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["dry_run"] is True
    assert not list((tmp_path / "day2-test").rglob("*.tmp"))


def test_resume_rejects_stale_input_hash(tmp_path: Path) -> None:
    _, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    restored = checkpoint.read_checkpoint(
        tmp_path / "day2-test" / "checkpoints" / "Q001.json"
    )
    changed_job = manifest.jobs[0].model_copy(
        update={"input_hash": "f" * 64}
    )

    with pytest.raises(checkpoint.BatchRunnerError) as raised:
        checkpoint.resume_job(
            restored,
            changed_job,
            manifest.resume_policy,
        )

    assert raised.value.error_code == "STALE_CHECKPOINT_INPUT_HASH"


def test_resume_rejects_changed_model_version(tmp_path: Path) -> None:
    _, _, checkpoint = _modules()
    manifest = _dry_run(tmp_path)
    restored = checkpoint.read_checkpoint(
        tmp_path / "day2-test" / "checkpoints" / "Q001.json"
    )
    changed_route = manifest.jobs[0].model_route.model_copy(
        update={"model_version": "different-version"}
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

    assert raised.value.error_code == "STALE_CHECKPOINT_VERSION"
