# -*- coding: utf-8 -*-
"""选题区位于快速操作正上方，同一页面级组件树内启用操作。"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.ui import components, job_state, state, workspace

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_question_picker_precedes_quick_actions():
    src = _read("app/ui/workspace_pages.py")
    assert src.index('id="question-picker"') < src.index('id="quick-actions"')
    assert src.index("_render_picker_panel") < src.index("_render_quick_actions")


def test_domain_distribution_follows_quick_actions():
    src = _read("app/ui/workspace_pages.py")
    page = src.split("def page_questions", 1)[1].split("def _live_ctx", 1)[0]
    assert page.index("render_question_action_hub") < page.index("_render_dynamics_fragment")
    assert page.index("_render_dynamics_fragment") < page.index("_render_domain_catalog")


def test_question_details_do_not_interrupt_picker_and_actions():
    src = _read("app/ui/workspace_pages.py")
    hub = src.split("def render_question_action_hub", 1)[1].split("def _render_compact_job_status", 1)[0]
    assert "_render_question_detail_card" not in hub
    assert "查看题目详情" in src.split("def _render_question_detail_expander", 1)[1]


def test_unselected_picker_is_expanded():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        assert workspace.picker_is_expanded() is True
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_selected_picker_is_compact():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        state.select_question("Q039", "Why do we stop growing?")
        st.session_state[components.PICKER_EXPANDED_KEY] = False
        assert workspace.picker_is_expanded() is False
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_selecting_question_collapses_picker():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        st.session_state[BOOT := workspace.BOOT_QUESTIONS] = [
            {"id": "Q039", "question": "Why do we stop growing?"}
        ]
        st.session_state[components.SELECTOR_WIDGET_KEY] = "Q039"
        workspace.store_question_selector_state()
        assert state.get(state.KEY_SELECTED_QID) == "Q039"
        assert st.session_state.get(components.PICKER_EXPANDED_KEY) is False
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_change_question_expands_picker():
    src = _read("app/ui/workspace_pages.py")
    assert 'key="change_question"' in src
    assert "PICKER_EXPANDED_KEY] = True" in src


def test_quick_actions_disabled_without_question():
    src = _read("app/ui/job_state.py")
    block = src.split("def render_job_action_button", 1)[1]
    assert "disabled=True" in block
    assert "请先选择一个科学问题" in block


def test_quick_actions_enabled_with_question():
    src = _read("app/ui/job_state.py")
    block = src.split("def render_job_action_button", 1)[1].split("def collect_visible_jobs", 1)[0]
    assert "if not question_id:" in block
    assert "rehydrate_job_state" in block


def test_history_action_enabled_without_question():
    src = _read("app/ui/workspace_pages.py")
    actions = src.split("def _render_quick_actions", 1)[1].split("def _render_research_plan_overview", 1)[0]
    assert 'key="ov_hist"' in actions
    assert "disabled" not in actions.split("ov_hist")[0][-80:]


def test_selecting_question_does_not_scroll_to_top():
    src = _read("app/ui/workspace_pages.py")
    assert 'request_scroll("research-overview")' not in src
    store = _read("app/ui/workspace.py")
    assert "st.rerun" not in store.split("def store_question_selector_state", 1)[1].split("def picker_is_expanded", 1)[0]


def test_selecting_question_does_not_start_job():
    src = _read("app/ui/workspace.py")
    cb = src.split("def store_question_selector_state", 1)[1].split("def picker_is_expanded", 1)[0]
    assert "submit_or_reuse_job" not in cb
    assert "process_run_triggers" not in cb


def test_question_and_actions_share_hub():
    src = _read("app/ui/workspace_pages.py")
    hub = src.split("def render_question_action_hub", 1)[1].split("def _render_compact_job_status", 1)[0]
    assert "_render_picker_panel" in hub
    assert "_render_quick_actions" in hub
    assert "render_workspace_header" in hub


def test_selection_does_not_rerun_from_selector_callback():
    src = _read("app/ui/workspace.py")
    cb = src.split("def store_question_selector_state", 1)[1].split("def picker_is_expanded", 1)[0]
    assert "st.rerun" not in cb
    pages = _read("app/ui/workspace_pages.py")
    picker = pages.split("def _render_picker_panel", 1)[1].split("def _render_quick_actions", 1)[0]
    assert "st.rerun()" in picker
    assert 'scope="fragment"' not in picker


def test_quick_actions_use_single_page_tree():
    src = _read("app/ui/workspace_pages.py")
    assert "@st.fragment" not in src.split("def render_question_action_hub", 1)[0][-80:]
    hub = src.split("def render_question_action_hub", 1)[1].split("def _render_research_plan_overview", 1)[0]
    assert "_render_quick_actions" in hub
    assert "st.empty()" not in hub
    assert 'key="question-action-hub"' in hub
    assert "question-action-hub-{qid}" not in hub


def test_selected_question_persists_across_pages():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        state.select_question("Q039", "aging")
        assert state.get(state.KEY_SELECTED_QID) == "Q039"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_active_job_restores_after_selection():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        job_state.set_active_job_id("Q039", job_state.JOB_TYPE_FULL, "job-039")
        state.select_question("Q028", "cancer")
        state.select_question("Q039", "aging")
        assert job_state.get_pointer_job_id("Q039", job_state.JOB_TYPE_FULL) == "job-039"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_switching_question_preserves_other_jobs():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        job_state.set_active_job_id("Q039", job_state.JOB_TYPE_FULL, "job-039")
        job_state.set_active_job_id("Q028", job_state.JOB_TYPE_FULL, "job-028")
        state.select_question("Q028", "cancer")
        assert job_state.get_pointer_job_id("Q039", job_state.JOB_TYPE_FULL) == "job-039"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_page_1440_shows_picker_and_all_actions():
    css = _read("app/ui/style.css")
    assert "max-height: 172px" in css
    assert "selected-question-bar" in css
    src = _read("app/ui/workspace_pages.py")
    assert 'id="question-picker"' in src
    assert 'id="quick-actions"' in src


def test_page_1366_shows_picker_and_action_cards():
    css = _read("app/ui/style.css")
    assert "min-height: 72px" in css
    assert "max-height: 88px" in css


def test_domain_chart_cached():
    src = _read("app/ui/workspace.py")
    assert "def load_domain_chart" in src
    assert "@st.cache_data" in src


def test_full_125_scan_not_triggered_by_selection():
    src = _read("app/ui/workspace.py")
    cb = src.split("def store_question_selector_state", 1)[1].split("def picker_is_expanded", 1)[0]
    assert "build_ui_question_index" not in cb
    assert "list_runs" not in cb


def test_no_real_provider_calls_in_layout_tests():
    src = _read("app/ui/workspace_pages.py")
    assert "api_client.run_experiment" not in src
    assert "FRONTEND_RUN_VIA_API=1" not in src
