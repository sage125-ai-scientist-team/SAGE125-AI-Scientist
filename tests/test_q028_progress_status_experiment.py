"""Q028 进度刷新、研究状态/运行次数、真实实验失败回退。"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.ui import state, workspace
from app.ui.progress import normalize_progress


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_model_progress_is_page_level_fragment() -> None:
    src = _read("app/ui/workspace_pages.py")
    questions = src.split("def page_questions", 1)[1].split("def _live_ctx", 1)[0]
    hub = src.split("def render_question_action_hub", 1)[1].split(
        "def _render_compact_job_status", 1
    )[0]
    progress = src.split("def _render_model_progress", 1)[1].split(
        "def _run_count_for_question", 1
    )[0]
    ctx = src.split("def _ctx", 1)[1].split("def _switches", 1)[0]
    assert "_render_model_progress(include_kpis=False)" in ctx
    assert "render_page_job_surface" not in ctx
    assert "_render_model_progress()" in questions
    assert "_render_status_kpis(ctx)" not in questions
    assert "_render_model_progress" not in hub
    assert "_render_status_kpis" not in hub
    assert '@st.fragment(run_every="2s")' in src.split("def _render_model_progress", 1)[0][-80:]
    assert "KEY_SELECTED_QID" in progress
    assert "_render_status_kpis" in progress
    assert "slot = st.empty()" not in progress
    assert "st.empty()" in progress


def test_run_count_kpi_is_numeric() -> None:
    src = _read("app/ui/workspace_pages.py")
    assert "def _run_count_for_question" in src
    assert "collect_visible_jobs" in src
    assert '运行次数</div><div class="ws-kpi-value">{run_count}' in src
    assert '运行次数</div><div class="ws-kpi-value">{len(runs) if runs else "—"}' not in src


def test_initializing_stage_maps_to_preparing() -> None:
    snapshot = normalize_progress({"stage": "initializing", "percent": 2, "status": "running"})
    assert snapshot.stage == "preparing"
    assert snapshot.percent == 2


def test_draft_plan_is_formed_not_partial() -> None:
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        label, kind = workspace.research_status(
            {
                "qid": "Q028",
                "plan": {"validation_status": "draft"},
                "result": {"run_id": "run-1", "evidence_cards": [{}, {}, {}]},
            }
        )
        assert label == "已形成计划"
        assert kind == "info"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_validated_plan_is_complete() -> None:
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        label, kind = workspace.research_status(
            {
                "qid": "Q028",
                "plan": {"validation_status": "validated"},
                "result": {"run_id": "run-1"},
            }
        )
        assert label == "已完成"
        assert kind == "success"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_experiment_http_timeout_covers_download_and_run() -> None:
    src = _read("app/ui/api_client.py")
    assert "timeout=max(_short_timeout_seconds(), 180)" in src


def test_demo_run_has_inprocess_fallback() -> None:
    src = _read("app/execution/q028_demo_run.py")
    assert "_inprocess_baseline_summary" in src
    assert "run_baseline" in src
    assert "_failed_experiment_payload" in src


def test_progress_card_hides_previous_question_after_switch() -> None:
    from app.ui.job_state import select_progress_card_job

    done = {
        "job_id": "job-q028",
        "question_id": "Q028",
        "status": "waiting_feedback",
        "updated_at": "2026-08-28T11:00:00Z",
    }
    job, bound, show_terminal = select_progress_card_job(
        "Q028", [done], bound_qid="Q028", show_terminal=True
    )
    assert job is not None
    assert job["job_id"] == "job-q028"
    assert bound == "Q028"
    assert show_terminal is True

    job, bound, show_terminal = select_progress_card_job(
        "Q059", [done], bound_qid=bound, show_terminal=show_terminal
    )
    assert job is None
    assert bound == "Q059"
    assert show_terminal is False


def test_progress_card_appears_only_after_current_question_starts() -> None:
    from app.ui.job_state import select_progress_card_job

    running = {
        "job_id": "job-q059",
        "question_id": "Q059",
        "status": "running",
        "updated_at": "2026-08-28T11:05:00Z",
    }
    job, bound, show_terminal = select_progress_card_job(
        "Q059", [running], bound_qid="Q059", show_terminal=False
    )
    assert job is not None
    assert job["job_id"] == "job-q059"
    assert bound == "Q059"
    assert show_terminal is True


def test_progress_keeps_pointer_job_without_question_id() -> None:
    from app.ui.job_state import select_progress_card_job

    running = {
        "job_id": "job-q028",
        "status": "running",
        "updated_at": "2026-08-28T11:06:00Z",
    }
    job, bound, show_terminal = select_progress_card_job(
        "Q028", [running], bound_qid="Q028", show_terminal=True
    )
    assert job is not None
    assert job["job_id"] == "job-q028"
    assert bound == "Q028"
    assert show_terminal is True
