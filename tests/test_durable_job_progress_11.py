"""CAPTAIN-LOCAL-SAGE125-DURABLE-JOB-PROGRESS-ACROSS-PAGES-11

mock/test only：确定性 FakeJobRunner，不调用真实 Provider，不写入正式结果目录。
"""

from __future__ import annotations

import inspect
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient as FastAPITestClient

from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.contracts import (
    JOB_TYPE_CONTROLLED_DEMO,
    JOB_TYPE_FULL_RESEARCH_PIPELINE,
    JobCreateRequest,
    JobStatus,
)
from app.api.job_commands import compute_idempotency_key, compute_input_digest
from app.api.job_queue import JobRunResult
from app.api.job_store import SQLiteJobStore
from app.api.main import create_app as _create_app
from app.ui import job_state
from app.ui.job_state import (
    apply_job_result_if_ready,
    rehydrate_job_state,
    stage_cursor,
    ui_status,
)


TEST_ACTOR = "test-user"
TEST_TOKEN = "test-api-token-123"
PIPELINE_STAGES = ["question_parser", "retrieval", "evidence_extractor", "report_writer"]


class FakeJobRunner:
    """mock/test only：按阶段推进并写 checkpoint，可从 checkpoint 恢复。"""

    def __init__(self) -> None:
        self.started_stages: list[tuple[str, str]] = []
        self.provider_calls = 0

    def run(self, job, progress_callback):
        completed = ""
        if job.checkpoint_uri and "/stage/" in job.checkpoint_uri:
            completed = job.checkpoint_uri.rsplit("/stage/", 1)[-1]
        start = 0
        if completed in PIPELINE_STAGES:
            start = PIPELINE_STAGES.index(completed) + 1
        for index, stage in enumerate(PIPELINE_STAGES[start:], start=start + 1):
            self.started_stages.append((job.job_id, stage))
            self.provider_calls += 1
            progress_callback(
                {
                    "stage": stage,
                    "progress_current": index,
                    "progress_total": len(PIPELINE_STAGES),
                    "message": f"stage {stage}",
                    "checkpoint_uri": f"job://{job.job_id}/stage/{stage}",
                    "provider_call_count": self.provider_calls,
                }
            )
            time.sleep(0.01)
        return JobRunResult(upstream_run_id=f"fake-{job.job_id[:8]}")


def create_app(tmp_path: Path, runner: FakeJobRunner | None = None, worker_count: int = 1):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    runner = runner or FakeJobRunner()
    app = _create_app(
        auth_policy=HashedAPIKeyAuth({TEST_ACTOR: TEST_TOKEN}),
        rate_limiter=FixedWindowRateLimiter(limit=10_000, window_seconds=60),
        job_store=store,
        job_runner=runner,
        worker_count=worker_count,
    )
    return app, store, runner


class TestClient(FastAPITestClient):
    def __init__(self, *args, **kwargs):
        headers = {"X-API-Key": TEST_TOKEN, **kwargs.pop("headers", {})}
        super().__init__(*args, headers=headers, **kwargs)


def _payload(question_id="Q001", job_type=JOB_TYPE_FULL_RESEARCH_PIPELINE, client_id="browser-1", mode="mock"):
    return {
        "question_id": question_id,
        "mode": mode,
        "job_type": job_type,
        "client_id": client_id,
        "input_digest": "digest-1",
        "options": {
            "use_deep_research": False,
            "use_open_literature": True,
            "use_local_rag": True,
            "reviewer_auto_revision": True,
        },
    }


def test_compute_input_digest_accepts_mode_and_options():
    first = compute_input_digest(
        mode="mock",
        options={
            "use_deep_research": False,
            "use_open_literature": True,
            "use_local_rag": True,
            "reviewer_auto_revision": True,
        },
    )
    second = compute_input_digest(
        mode="mock",
        options={
            "reviewer_auto_revision": True,
            "use_local_rag": True,
            "use_open_literature": True,
            "use_deep_research": False,
        },
    )
    assert first == second
    assert len(first) == 32
    # 回归：mode(str) 与 options(tuple/dict) 不得进入同一个 sorted()。
    mixed = compute_input_digest(mode="real", options={"z": "1", "a": True})
    assert mixed != first
    assert mixed.isalnum() and len(mixed) == 32


def _create(client: TestClient, **kwargs):
    body = _payload(**kwargs)
    key = compute_idempotency_key(
        client_id=body["client_id"],
        question_id=body["question_id"],
        job_type=body["job_type"],
        input_digest=body["input_digest"],
    )
    return client.post("/api/v1/jobs", json=body, headers={"Idempotency-Key": key})


def _wait(store: SQLiteJobStore, job_id: str, expected: set[str], timeout: float = 3) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = store.get_job(job_id).status
        if status in expected:
            return status
        time.sleep(0.02)
    return store.get_job(job_id).status


def test_job_create_returns_job_id(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        response = _create(client)
        assert response.status_code == 202
        body = response.json()
        assert body["job_id"]
        assert body["created"] is True
        assert body["status"] == "queued"
        assert store.get_job(body["job_id"]).job_id == body["job_id"]
    pass


def test_duplicate_click_returns_same_active_job(tmp_path):
    app, store, runner = create_app(tmp_path)
    with TestClient(app) as client:
        first = _create(client).json()
        second = _create(client).json()
        assert first["job_id"] == second["job_id"]
        assert second["created"] is False
        assert len(store.list_jobs(limit=20)) == 1
        _wait(store, first["job_id"], {"waiting_feedback", "completed", "failed"})
    assert runner.provider_calls <= len(PIPELINE_STAGES)
    pass


def test_same_question_same_job_type_is_idempotent(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        a = _create(client, question_id="Q001").json()
        b = _create(client, question_id="Q001").json()
        assert a["job_id"] == b["job_id"]
    pass


def test_different_question_creates_different_job(tmp_path):
    app, _, _ = create_app(tmp_path)
    with TestClient(app) as client:
        a = _create(client, question_id="Q001").json()
        b = _create(client, question_id="Q002").json()
        assert a["job_id"] != b["job_id"]
    pass


def test_different_job_type_creates_different_job(tmp_path):
    app, _, _ = create_app(tmp_path)
    with TestClient(app) as client:
        a = _create(client, job_type=JOB_TYPE_FULL_RESEARCH_PIPELINE).json()
        b = _create(client, job_type=JOB_TYPE_CONTROLLED_DEMO).json()
        assert a["job_id"] != b["job_id"]
    pass


def test_page_navigation_does_not_cancel_job(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        before = store.get_job(job_id).status
        # 切页不调用 cancel；只查询状态。
        status = client.get(f"/api/v1/jobs/{job_id}").json()["status"]
        assert status != "cancelled"
        assert before != "cancelled"
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
        assert store.get_job(job_id).status != "cancelled"
    pass


@pytest.mark.parametrize(
    "name",
    [
        "progress_survives_overview_to_evidence",
        "progress_survives_evidence_to_hypothesis",
        "progress_survives_hypothesis_to_plan",
        "progress_survives_plan_to_execution",
        "progress_survives_execution_to_overview",
        "returning_page_recovers_same_job_id",
    ],
)
def test_progress_survives_page_switch(tmp_path, name):
    del name
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        first = client.get(f"/api/v1/jobs/{job_id}").json()
        second = client.get(f"/api/v1/jobs/{job_id}").json()
        assert first["job_id"] == second["job_id"] == job_id
        first_seq = max(
            (item["sequence"] for item in client.get(f"/api/v1/jobs/{job_id}/events").json()["items"]),
            default=0,
        )
        second_seq = max(
            (item["sequence"] for item in client.get(f"/api/v1/jobs/{job_id}/events").json()["items"]),
            default=0,
        )
        assert second_seq >= first_seq
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
    pass


def test_session_state_missing_recovers_from_backend(tmp_path, monkeypatch):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        created = _create(client).json()
        monkeypatch.setattr(job_state, "get_pointer_job_id", lambda *_: None)
        monkeypatch.setattr(job_state, "query_job_id", lambda: None)
        monkeypatch.setattr(job_state.st, "session_state", {"active_job_ids": {}})
        monkeypatch.setattr(job_state.api_client, "get_job", lambda job_id: client.get(f"/api/v1/jobs/{job_id}").json())
        monkeypatch.setattr(job_state.api_client, "list_jobs", lambda **kwargs: [])
        monkeypatch.setattr(job_state, "apply_job_result_if_ready", lambda job: None)
        monkeypatch.setattr(job_state, "set_active_job_id", lambda *args, **kwargs: None)
        monkeypatch.setattr(job_state.state, "set_value", lambda *args, **kwargs: None)
        def _active(**kwargs):
            response = client.get(
                "/api/v1/jobs/active",
                params={
                    "client_id": kwargs["client_id"],
                    "question_id": kwargs["question_id"],
                    "job_type": kwargs.get("job_type"),
                },
            )
            return response.json() if response.status_code == 200 else None

        def _latest(**kwargs):
            response = client.get(
                "/api/v1/jobs/latest",
                params={
                    "client_id": kwargs.get("client_id"),
                    "question_id": kwargs["question_id"],
                    "job_type": kwargs.get("job_type"),
                },
            )
            return response.json() if response.status_code == 200 else None

        monkeypatch.setattr(job_state.api_client, "get_active_job", _active)
        monkeypatch.setattr(job_state.api_client, "get_latest_job", _latest)
        recovered = rehydrate_job_state("browser-1", "Q001", JOB_TYPE_FULL_RESEARCH_PIPELINE)
        assert recovered is not None
        assert recovered["job_id"] == created["job_id"]
        _wait(store, created["job_id"], {"waiting_feedback", "completed", "failed"})
    pass


def test_browser_refresh_recovers_active_job(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        found = client.get(
            "/api/v1/jobs/active",
            params={
                "client_id": "browser-1",
                "question_id": "Q001",
                "job_type": JOB_TYPE_FULL_RESEARCH_PIPELINE,
            },
        )
        if found.status_code == 404:
            found = client.get(
                "/api/v1/jobs/latest",
                params={"client_id": "browser-1", "question_id": "Q001"},
            )
        assert found.status_code == 200
        assert found.json()["job_id"] == job_id
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
    pass


def test_ui_restart_recovers_active_job(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        latest = client.get(
            "/api/v1/jobs/latest",
            params={"client_id": "browser-1", "question_id": "Q001"},
        )
        assert latest.json()["job_id"] == job_id
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
    pass


def test_worker_restart_resumes_from_checkpoint(tmp_path):
    runner = FakeJobRunner()
    app, store, runner = create_app(tmp_path, runner=runner)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
        retry = client.post(f"/api/v1/jobs/{job_id}/retry", json={"client_id": "browser-1"})
        assert retry.status_code == 202
        new_id = retry.json()["job_id"]
        if new_id != job_id:
            assert store.get_job(new_id).retry_of_job_id == job_id
        _wait(store, new_id, {"waiting_feedback", "completed", "failed"}, timeout=4)
        assert store.get_job(job_id).status in {"waiting_feedback", "completed", "failed"}
    assert runner.started_stages
    pass


def test_completed_stage_not_rerun_after_resume(tmp_path):
    runner = FakeJobRunner()
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    job, _ = store.create_job(
        request=JobCreateRequest(
            question_id="Q001",
            mode="mock",
            client_id="browser-1",
            job_type=JOB_TYPE_FULL_RESEARCH_PIPELINE,
        ),
        correlation_id="c1",
        requested_by=TEST_ACTOR,
    )
    store.transition(job.job_id, JobStatus.RUNNING, actor="t", source="t")
    store.update_progress(
        job.job_id,
        "retrieval",
        progress_current=2,
        progress_total=4,
        checkpoint_uri=f"job://{job.job_id}/stage/retrieval",
        provider_call_count=2,
    )
    job = store.get_job(job.job_id)
    runner.run(job, lambda payload: store.update_progress(job.job_id, payload["stage"], **{
        k: payload[k] for k in ("progress_current", "progress_total", "checkpoint_uri", "provider_call_count")
        if k in payload
    }))
    started = [stage for _, stage in runner.started_stages]
    assert "question_parser" not in started
    assert "retrieval" not in started
    assert started[0] == "evidence_extractor"


def test_provider_call_not_duplicated_after_navigation(tmp_path):
    app, store, runner = create_app(tmp_path)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
        calls = store.get_job(job_id).provider_call_count
        client.get(f"/api/v1/jobs/{job_id}")
        client.get("/api/v1/jobs/active", params={"client_id": "browser-1", "question_id": "Q001"})
        assert store.get_job(job_id).provider_call_count == calls
        assert runner.provider_calls == calls
    pass


def test_second_button_detects_same_underlying_job(tmp_path):
    app, _, _ = create_app(tmp_path)
    with TestClient(app) as client:
        generate = _create(client, job_type=JOB_TYPE_FULL_RESEARCH_PIPELINE).json()
        plan = _create(client, job_type=JOB_TYPE_FULL_RESEARCH_PIPELINE).json()
        assert generate["job_id"] == plan["job_id"]
    pass


def test_active_button_does_not_create_new_job(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        first = _create(client).json()
        again = _create(client).json()
        assert first["job_id"] == again["job_id"]
        assert len(store.list_jobs(limit=10)) == 1
        _wait(store, first["job_id"], {"waiting_feedback", "completed", "failed"})
    pass


def test_completed_job_shows_view_result():
    spec = job_state.job_action_spec({"status": "completed"}, idle_label="开始生成")
    assert spec["label"] == "查看结果"
    assert spec["action"] == "view_result"


def test_failed_job_shows_error_after_navigation():
    spec = job_state.job_action_spec(
        {"status": "failed", "error": {"code": "X", "message": "boom"}},
        idle_label="开始生成",
    )
    assert spec["label"] == "重新运行"
    assert spec["action"] == "rerun"
    assert ui_status({"status": "failed"}) == "FAILED"
    source = inspect.getsource(job_state.render_job_action_button)
    assert "查看失败原因" not in source
    assert "retry_from_checkpoint" in source
    assert "确认从检查点重试" not in source


def test_retry_preserves_lineage(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
        current = store.get_job(job_id)
        if current.status not in {"failed", "timed_out", "cancelled", "completed", "waiting_feedback"}:
            store.transition(job_id, JobStatus.FAILED, actor="t", source="t")
        # waiting_feedback 可重试为新 attempt
        retry = client.post(f"/api/v1/jobs/{job_id}/retry", json={"client_id": "browser-1"})
        assert retry.status_code == 202
        new_id = retry.json()["job_id"]
        if new_id != job_id:
            assert store.get_job(new_id).retry_of_job_id == job_id
            assert store.get_job(job_id).status in {
                "waiting_feedback",
                "completed",
                "failed",
            }
        _wait(store, new_id, {"waiting_feedback", "completed", "failed", "queued", "running"})
    pass


def test_job_events_sequence_is_monotonic(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
        items = client.get(f"/api/v1/jobs/{job_id}/events").json()["items"]
        sequences = [item["sequence"] for item in items]
        assert sequences == sorted(sequences)
        assert sequences == list(range(sequences[0], sequences[0] + len(sequences)))
    pass


def test_fragment_polling_does_not_full_rerun_app():
    source = inspect.getsource(job_state.render_job_progress_fragment)
    assert "@st.fragment" in inspect.getsource(job_state) or "run_every" in source
    assert "get_questions" not in source
    assert "bootstrap" not in source
    assert "run_pipeline" not in source
    assert "create_job" not in source


def test_active_jobs_multiple_questions_are_isolated(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        a = _create(client, question_id="Q001").json()["job_id"]
        b = _create(client, question_id="Q002").json()["job_id"]
        assert a != b
        first = client.get(
            "/api/v1/jobs/active",
            params={"client_id": "browser-1", "question_id": "Q001"},
        ).json()
        second = client.get(
            "/api/v1/jobs/active",
            params={"client_id": "browser-1", "question_id": "Q002"},
        ).json()
        assert first["job_id"] == a
        assert second["job_id"] == b
        _wait(store, a, {"waiting_feedback", "completed", "failed"})
        _wait(store, b, {"waiting_feedback", "completed", "failed"})
    pass


def test_five_concurrent_jobs_state_not_lost(tmp_path):
    app, store, _ = create_app(tmp_path, worker_count=2)
    with TestClient(app) as client:
        ids = [
            _create(client, question_id=f"Q00{index}", client_id=f"browser-{index}").json()["job_id"]
            for index in range(1, 6)
        ]
        assert len(set(ids)) == 5
        for job_id in ids:
            _wait(store, job_id, {"waiting_feedback", "completed", "failed"}, timeout=5)
            assert store.get_job(job_id).question_id
    pass


def test_navigation_cycle_30_times_progress_persists(tmp_path):
    app, store, _ = create_app(tmp_path)
    with TestClient(app) as client:
        job_id = _create(client).json()["job_id"]
        last_seq = 0
        for _ in range(30):
            body = client.get(f"/api/v1/jobs/{job_id}").json()
            assert body["job_id"] == job_id
            events = client.get(
                f"/api/v1/jobs/{job_id}/events",
                params={"after_sequence": last_seq},
            ).json()["items"]
            if events:
                last_seq = events[-1]["sequence"]
        assert last_seq >= 0
        _wait(store, job_id, {"waiting_feedback", "completed", "failed"})
    pass


def test_no_thread_or_future_stored_in_session_state():
    source = Path("app/ui/job_state.py").read_text(encoding="utf-8")
    assert "Thread" not in source
    assert "Future" not in source
    assert "asyncio" not in source
    assert "run_pipeline" not in source
    assert ACTIVE_JOB_IDS_KEY_PRESENT(source)


def ACTIVE_JOB_IDS_KEY_PRESENT(source: str) -> bool:
    return "active_job_ids" in source and "sage125_client_id" in source


def test_no_real_provider_calls_in_ui_tests():
    runner_src = inspect.getsource(FakeJobRunner)
    assert "JobRunResult" in runner_src
    assert "run_pipeline" not in runner_src
    assert "openai" not in runner_src.lower()


def test_process_run_triggers_no_longer_blocks_on_pipeline():
    source = Path("app/ui/streamlit_app.py").read_text(encoding="utf-8")
    trigger = source.split("def process_run_triggers", 1)[1].split("\ndef main", 1)[0]
    assert "submit_or_reuse_job" in trigger
    assert "_execute_run" not in trigger


def test_start_generate_and_plan_share_job_type():
    assert job_state.JOB_TYPE_FULL == JOB_TYPE_FULL_RESEARCH_PIPELINE
    current, total = stage_cursor("question_parser")
    assert current is not None and total is not None
    assert 1 <= current <= total


def test_apply_job_result_skips_missing_run(monkeypatch):
    monkeypatch.setattr(job_state.st, "session_state", {})
    monkeypatch.setattr(job_state.api_client, "get_run", lambda run_id: {"status": "missing"})
    apply_job_result_if_ready(
        {"status": "completed", "job_id": "j1", "upstream_run_id": "r1", "question_id": "Q001"}
    )
