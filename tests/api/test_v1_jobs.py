"""T08 API v1 异步 Job 骨架测试。"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import JobCreateRequest, JobStatus
from app.api.job_queue import (
    CompletionEvidence,
    InProcessJobQueue,
    JobRunResult,
    PipelineJobRunner,
    QueueCapacityError,
)
from app.api.job_store import (
    IdempotencyConflict,
    InvalidTransition,
    SQLiteJobStore,
)
from app.api.main import create_app


def _request(question_id: str = "Q001", mode: str = "mock") -> JobCreateRequest:
    return JobCreateRequest(question_id=question_id, mode=mode)


def _wait_for_status(store: SQLiteJobStore, job_id: str, expected: set[str], timeout: float = 3) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = store.get_job(job_id).status
        if status in expected:
            return status
        time.sleep(0.01)
    return store.get_job(job_id).status


def test_sqlite_store_persists_idempotency_and_events(tmp_path):
    db_path = tmp_path / "jobs.sqlite3"
    store = SQLiteJobStore(db_path)
    store.initialize()

    first, reused = store.create_job(
        request=_request(),
        correlation_id="corr-1",
        idempotency_key="same-key",
    )
    assert reused is False
    same, reused = store.create_job(
        request=_request(),
        correlation_id="corr-2",
        idempotency_key="same-key",
    )
    assert reused is True
    assert same.job_id == first.job_id

    with pytest.raises(IdempotencyConflict):
        store.create_job(
            request=_request(question_id="Q002"),
            correlation_id="corr-3",
            idempotency_key="same-key",
        )

    reopened = SQLiteJobStore(db_path)
    reopened.initialize()
    assert reopened.get_job(first.job_id).question_id == "Q001"
    assert reopened.list_events(first.job_id)[0]["to_status"] == "queued"
    assert b"same-key" not in db_path.read_bytes()


def test_store_rejects_and_audits_illegal_transition(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    job, _ = store.create_job(request=_request(), correlation_id="corr")
    store.transition(job.job_id, JobStatus.FAILED, actor="test", source="test")

    with pytest.raises(InvalidTransition):
        store.transition(job.job_id, JobStatus.RUNNING, actor="test", source="test")

    rejected = store.list_events(job.job_id)[-1]
    assert rejected["event_type"] == "transition_rejected"
    assert rejected["details"]["requested_status"] == "running"


def test_sqlite_store_keeps_five_concurrent_jobs_isolated(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()

    def create(index: int):
        return store.create_job(
            request=_request(f"Q00{index}"),
            correlation_id=f"corr-{index}",
            idempotency_key=f"key-{index}",
        )[0]

    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = list(pool.map(create, range(1, 6)))

    assert len({job.job_id for job in jobs}) == 5
    assert len(store.list_jobs(limit=10)) == 5
    assert {job.question_id for job in jobs} == {
        "Q001",
        "Q002",
        "Q003",
        "Q004",
        "Q005",
    }


class _SuccessfulRunner:
    def run(self, job, progress_callback):
        progress_callback({"stage": "retrieval", "status": "running"})
        return JobRunResult(
            upstream_run_id="upstream-run-1",
            completion_evidence=CompletionEvidence(
                required_artifacts_present=True,
                quality_gate_passed=True,
                blocking_issues_closed=True,
                truth_status_explicit=True,
                traceable_and_serializable=True,
            ),
        )


class _UnverifiedSuccessfulRunner:
    def run(self, job, progress_callback):
        progress_callback({"stage": "artifacts", "status": "running"})
        return JobRunResult(upstream_run_id="upstream-run-unverified")


class _LegacyStringRunner:
    def run(self, job, progress_callback):
        return "upstream-run-legacy"


class _BlockingRunner:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, job, progress_callback):
        self.started.set()
        self.release.wait(timeout=3)
        return JobRunResult(upstream_run_id=f"run-{job.job_id}")


class _MissingSourceRunner:
    def run(self, job, progress_callback):
        raise FileNotFoundError("/private/project/data/questions.json is missing")


@pytest.mark.parametrize(
    "missing_requirement",
    [
        "required_artifacts_present",
        "quality_gate_passed",
        "blocking_issues_closed",
        "truth_status_explicit",
        "traceable_and_serializable",
    ],
)
def test_completion_evidence_requires_every_guard(missing_requirement):
    checks = {
        "required_artifacts_present": True,
        "quality_gate_passed": True,
        "blocking_issues_closed": True,
        "truth_status_explicit": True,
        "traceable_and_serializable": True,
    }
    checks[missing_requirement] = False

    evidence = CompletionEvidence(**checks)

    assert evidence.allows_completion is False
    assert evidence.missing_requirements == (missing_requirement,)


def test_pipeline_runner_does_not_infer_completion_without_owner_contract(
    tmp_path,
    monkeypatch,
):
    from app.workflow import pipeline

    monkeypatch.setattr(
        pipeline,
        "run_pipeline_with_state",
        lambda **kwargs: (object(), SimpleNamespace(run_id="upstream-run-guarded")),
    )
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    job, _ = store.create_job(request=_request(), correlation_id="corr")

    result = PipelineJobRunner().run(job, lambda payload: None)

    assert result.upstream_run_id == "upstream-run-guarded"
    assert result.completion_evidence is None
    assert result.completion_verified is False


def test_queue_runs_job_and_persists_upstream_run_id(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    queue = InProcessJobQueue(store, _SuccessfulRunner(), capacity=5, worker_count=1)
    queue.start()
    try:
        job, _ = store.create_job(request=_request(), correlation_id="corr")
        queue.submit(job.job_id)
        assert _wait_for_status(store, job.job_id, {"completed"}) == "completed"
        completed = store.get_job(job.job_id)
        assert completed.stage == "completed"
        assert completed.upstream_run_id == "upstream-run-1"
    finally:
        queue.stop()


def test_queue_does_not_complete_without_explicit_completion_evidence(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    queue = InProcessJobQueue(
        store,
        _UnverifiedSuccessfulRunner(),
        capacity=2,
        worker_count=1,
    )
    queue.start()
    try:
        job, _ = store.create_job(request=_request(), correlation_id="corr")
        queue.submit(job.job_id)

        assert (
            _wait_for_status(store, job.job_id, {"waiting_feedback"})
            == "waiting_feedback"
        )
        waiting = store.get_job(job.job_id)
        assert waiting.stage == "awaiting_completion_verification"
        assert waiting.upstream_run_id == "upstream-run-unverified"
        assert waiting.finished_at is None
    finally:
        queue.stop()


def test_legacy_string_runner_is_unverified_instead_of_completed(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    queue = InProcessJobQueue(store, _LegacyStringRunner(), capacity=2)
    queue.start()
    try:
        job, _ = store.create_job(request=_request(), correlation_id="corr")
        queue.submit(job.job_id)

        assert (
            _wait_for_status(store, job.job_id, {"waiting_feedback"})
            == "waiting_feedback"
        )
        waiting = store.get_job(job.job_id)
        assert waiting.upstream_run_id == "upstream-run-legacy"
        assert waiting.stage == "awaiting_completion_verification"
    finally:
        queue.stop()


def test_queue_keeps_five_jobs_isolated(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    queue = InProcessJobQueue(store, _SuccessfulRunner(), capacity=5, worker_count=1)
    queue.start()
    try:
        jobs = [
            store.create_job(
                request=_request(f"Q00{index}"),
                correlation_id=f"corr-{index}",
            )[0]
            for index in range(1, 6)
        ]
        for job in jobs:
            queue.submit(job.job_id)
        for job in jobs:
            assert _wait_for_status(store, job.job_id, {"completed"}) == "completed"
        assert {
            store.get_job(job.job_id).question_id for job in jobs
        } == {"Q001", "Q002", "Q003", "Q004", "Q005"}
    finally:
        queue.stop()


def test_queue_maps_failure_to_stable_sanitized_error(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    queue = InProcessJobQueue(store, _MissingSourceRunner(), capacity=2)
    queue.start()
    try:
        job, _ = store.create_job(request=_request(), correlation_id="corr")
        queue.submit(job.job_id)
        assert _wait_for_status(store, job.job_id, {"failed"}) == "failed"
        failed = store.get_job(job.job_id)
        assert failed.error_code == "QUESTION_SOURCE_MISSING"
        assert failed.retryable is False
        assert str(tmp_path) not in (failed.error_message or "")
    finally:
        queue.stop()


def test_queue_is_bounded_without_losing_job_state(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    runner = _BlockingRunner()
    queue = InProcessJobQueue(store, runner, capacity=1, worker_count=1)
    queue.start()
    try:
        first, _ = store.create_job(request=_request("Q001"), correlation_id="c1")
        second, _ = store.create_job(request=_request("Q002"), correlation_id="c2")
        third, _ = store.create_job(request=_request("Q003"), correlation_id="c3")
        queue.submit(first.job_id)
        assert runner.started.wait(timeout=1)
        queue.submit(second.job_id)
        with pytest.raises(QueueCapacityError):
            queue.submit(third.job_id)
        assert store.get_job(third.job_id).status == "queued"
    finally:
        runner.release.set()
        queue.stop()


def test_recovery_requeues_mock_and_fails_orphaned_real_job(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    mock_job, _ = store.create_job(request=_request("Q001", "mock"), correlation_id="c1")
    real_job, _ = store.create_job(request=_request("Q002", "real"), correlation_id="c2")
    store.begin_attempt(mock_job.job_id)
    store.begin_attempt(real_job.job_id)

    recovered = store.recover_interrupted_jobs()

    assert mock_job.job_id in recovered
    assert store.get_job(mock_job.job_id).status == "queued"
    failed_real = store.get_job(real_job.job_id)
    assert failed_real.status == "failed"
    assert failed_real.error_code == "PROCESS_RESTARTED_UNSAFE_TO_RETRY"


def test_v1_job_api_is_non_blocking_idempotent_and_correlated(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    runner = _BlockingRunner()
    app = create_app(job_store=store, job_runner=runner, queue_capacity=5)

    with TestClient(app) as client:
        started = time.monotonic()
        response = client.post(
            "/api/v1/jobs",
            headers={"Idempotency-Key": "job-key", "X-Correlation-ID": "corr-client"},
            json=_request().model_dump(),
        )
        elapsed = time.monotonic() - started

        assert response.status_code == 202
        assert elapsed < 0.5
        body = response.json()
        assert body["status"] == "queued"
        assert body["correlation_id"] == "corr-client"
        assert response.headers["X-Correlation-ID"] == "corr-client"

        repeated = client.post(
            "/api/v1/jobs",
            headers={"Idempotency-Key": "job-key"},
            json=_request().model_dump(),
        )
        assert repeated.status_code == 202
        assert repeated.json()["job_id"] == body["job_id"]
        assert repeated.json()["reused"] is True
        assert store.get_job(body["job_id"]).correlation_id == "corr-client"

        status_response = client.get(f"/api/v1/jobs/{body['job_id']}")
        assert status_response.status_code == 200
        assert status_response.json()["job_id"] == body["job_id"]
        assert "upstream_run_id" in status_response.json()

        listing = client.get("/api/v1/jobs", params={"question_id": "Q001"})
        assert listing.status_code == 200
        assert listing.json()["items"][0]["job_id"] == body["job_id"]

        runner.release.set()


def test_v1_status_exposes_unverified_completion_as_waiting(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    app = create_app(job_store=store, job_runner=_UnverifiedSuccessfulRunner())

    with TestClient(app) as client:
        accepted = client.post("/api/v1/jobs", json=_request().model_dump())
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]
        assert (
            _wait_for_status(store, job_id, {"waiting_feedback"})
            == "waiting_feedback"
        )

        response = client.get(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "waiting_feedback"
        assert body["stage"] == "awaiting_completion_verification"
        assert body["upstream_run_id"] == "upstream-run-unverified"
        assert body["finished_at"] is None


def test_v1_queue_capacity_and_validation_errors_are_structured(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    runner = _BlockingRunner()
    app = create_app(
        job_store=store,
        job_runner=runner,
        queue_capacity=1,
        worker_count=1,
    )
    with TestClient(app) as client:
        first = client.post("/api/v1/jobs", json=_request("Q001").model_dump())
        assert first.status_code == 202
        assert runner.started.wait(timeout=1)
        second = client.post("/api/v1/jobs", json=_request("Q002").model_dump())
        assert second.status_code == 202
        rejected = client.post("/api/v1/jobs", json=_request("Q003").model_dump())
        assert rejected.status_code == 503
        assert rejected.json()["code"] == "QUEUE_CAPACITY_EXCEEDED"
        rejected_job = store.get_job(rejected.json()["details"]["job_id"])
        assert rejected_job.status == "failed"
        assert rejected_job.retryable is True

        invalid = client.post("/api/v1/jobs", json={"question_id": ""})
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "VALIDATION_ERROR"
        runner.release.set()


def test_v1_errors_use_stable_envelope_and_openapi_exposes_contracts(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    app = create_app(job_store=store, job_runner=_SuccessfulRunner())

    with TestClient(app) as client:
        missing = client.get(
            "/api/v1/jobs/not-found",
            headers={"X-Correlation-ID": "corr-missing"},
        )
        assert missing.status_code == 404
        assert missing.json() == {
            "code": "JOB_NOT_FOUND",
            "message": "任务不存在。",
            "details": {"job_id": "not-found"},
            "correlation_id": "corr-missing",
            "retryable": False,
        }

        invalid = client.get(
            "/api/v1/jobs/not-found",
            headers={"X-Correlation-ID": "contains spaces"},
        )
        assert invalid.status_code == 400
        assert invalid.json()["code"] == "INVALID_CORRELATION_ID"

        schema = client.get("/openapi.json").json()
        assert "/api/v1/jobs" in schema["paths"]
        assert "/api/v1/jobs/{job_id}" in schema["paths"]
        assert schema["paths"]["/runs"]["post"]["deprecated"] is True
        serialized = json.dumps(schema)
        for contract in (
            "Artifact",
            "Version",
            "VersionDiff",
            "FeedbackCreateRequest",
        ):
            assert contract in serialized
        for path, path_item in schema["paths"].items():
            if not path.startswith("/api/v1"):
                continue
            for method, operation in path_item.items():
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue
                for response in operation["responses"].values():
                    media = response.get("content", {}).get("application/json", {})
                    assert media.get("example") or media.get("examples"), (
                        f"{method.upper()} {path} 缺少响应示例"
                    )


def test_future_owner_routes_are_explicitly_unavailable(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    app = create_app(job_store=store, job_runner=_SuccessfulRunner())
    with TestClient(app) as client:
        created = client.post("/api/v1/jobs", json=_request().model_dump()).json()
        response = client.get(
            f"/api/v1/jobs/{created['job_id']}/artifacts",
            headers={"X-Correlation-ID": "future-contract"},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "UPSTREAM_CONTRACT_UNAVAILABLE"
        assert response.json()["details"]["availability"] == "unavailable"


def test_v1_unhandled_errors_do_not_leak_internal_details(tmp_path):
    class BrokenStore(SQLiteJobStore):
        def recover_interrupted_jobs(self):
            return []

        def list_jobs(self, **kwargs):
            raise RuntimeError("/private/secret/path token-test-secret-value")

    store = BrokenStore(tmp_path / "jobs.sqlite3")
    app = create_app(job_store=store, job_runner=_SuccessfulRunner())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/jobs",
            headers={"X-Correlation-ID": "internal-error"},
        )
        assert response.status_code == 500
        assert response.json() == {
            "code": "INTERNAL_ERROR",
            "message": "服务发生未预期错误。",
            "details": {},
            "correlation_id": "internal-error",
            "retryable": False,
        }
        assert "secret" not in response.text
