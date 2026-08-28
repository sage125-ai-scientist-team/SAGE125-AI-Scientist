# -*- coding: utf-8 -*-
"""信息架构合并：概览并入科学问题，单一权威选题器。"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.ui import components, job_state, state, workspace

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_sidebar_has_no_overview_entry():
    src = _read("app/ui/streamlit_app.py")
    assert '"研究工作区": [questions, evidence, hypotheses, plan]' in src
    assert '"研究工作区": [overview, questions' not in src


def test_sidebar_has_single_question_entry():
    src = _read("app/ui/streamlit_app.py")
    assert src.count('title="科学问题"') == 1
    assert '"研究工作区": [questions,' in src


def test_workspace_default_page_is_questions():
    src = _read("app/ui/workspace_pages.py")
    assert 'workspace_page=_HOOKS["page_questions"]' in src
    assert 'workspace_page=_HOOKS["page_overview"]' not in src


def test_top_context_has_no_selectbox():
    src = _read("app/ui/workspace.py")
    header = src.split("def render_workspace_header", 1)[1].split("def render_unselected_guide", 1)[0]
    assert "st.selectbox" not in header
    assert "ws_question_switcher" not in src


def test_top_context_is_readonly():
    src = _read("app/ui/workspace.py")
    assert "question-context-readonly" in src
    assert "尚未选择科学问题" in src
    assert "workspace-context" in src


def test_only_one_authoritative_question_selector():
    pages = _read("app/ui/workspace_pages.py")
    assert pages.count("SELECTOR_WIDGET_KEY") >= 1
    assert pages.count("ws_question_switcher") == 0


def test_selector_uses_fixed_widget_key():
    assert components.SELECTOR_WIDGET_KEY == "_question_selector"
    assert components.QUESTION_CHOICE_WIDGET_KEY == "_question_selector"


def test_selected_question_persists_across_pages():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        state.select_question("Q039", "为什么我们停止生长？")
        assert state.get(state.KEY_SELECTED_QID) == "Q039"
        workspace.bootstrap  # 切页只读指针，不把选题清空
        assert state.get(state.KEY_SELECTED_QID) == "Q039"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_official_question_id_accepts_q001_q125():
    assert workspace.official_question_id("Q039") == "Q039"
    assert workspace.official_question_id("q028") == "Q028"
    assert workspace.official_question_id("Q126") is None
    assert workspace.official_question_id("Q000") is None
    assert workspace.official_question_id("not-a-question") is None


def test_invalid_query_question_is_rejected():
    assert workspace.official_question_id("Q999") is None
    assert workspace.official_question_id(["bad"]) is None


def test_query_param_restores_question_when_session_empty(monkeypatch):
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    questions = [{"id": "Q039", "question": "为什么我们停止生长？"}]

    class _QP(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    qp = _QP(question_id="Q039")
    try:
        state.init_state()
        monkeypatch.setattr(st, "query_params", qp, raising=False)
        workspace.apply_query_question(questions)
        assert state.get(state.KEY_SELECTED_QID) == "Q039"
        state.select_question("Q028", "other")
        qp["question_id"] = "Q039"
        workspace.apply_query_question(questions)
        assert state.get(state.KEY_SELECTED_QID) == "Q028"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_query_param_restores_real_mode_after_refresh(monkeypatch):
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]

    class _QP(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    qp = _QP()
    try:
        state.init_state()
        assert state.current_mode() == "mock"
        monkeypatch.setattr(st, "query_params", qp, raising=False)
        workspace.apply_query_mode(fallback="real")
        assert state.current_mode() == "real"
        workspace.persist_query_mode("real")
        assert qp.get("mode") == "real"
        st.session_state = {}  # type: ignore[assignment]
        state.init_state()
        monkeypatch.setattr(st, "query_params", qp, raising=False)
        workspace.apply_query_mode()
        assert state.current_mode() == "real"
        assert st.session_state.get(components.MODE_WIDGET_KEY) == "real"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_stale_fallback_widget_does_not_reset_real_mode(monkeypatch):
    """离开设置页后，未挂载的备用 selectbox key 不得把真实运行盖回演示。"""
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]

    class _QP(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    qp = _QP()
    try:
        state.init_state()
        monkeypatch.setattr(st, "query_params", qp, raising=False)
        workspace.persist_query_mode("real")
        st.session_state.pop(components.MODE_WIDGET_KEY, None)
        st.session_state[components.MODE_WIDGET_FALLBACK_KEY] = "mock"
        workspace.apply_query_mode(fallback="mock")
        workspace.persist_query_mode()
        assert state.current_mode() == "real"
        assert qp.get("mode") == "real"
        assert st.session_state.get(components.MODE_WIDGET_FALLBACK_KEY) == "real"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_explicit_mock_is_not_overwritten_by_job_fallback(monkeypatch):
    """用户明确选了演示后，旧 Job 的 real 不得改回。"""
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        workspace.persist_query_mode("mock")
        st.session_state.pop(components.MODE_WIDGET_KEY, None)
        workspace.apply_query_mode(fallback="real")
        assert state.current_mode() == "mock"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_mode_widget_is_not_overwritten_by_stale_query(monkeypatch):
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]

    class _QP(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    qp = _QP(mode="mock")
    try:
        state.init_state()
        st.session_state[components.MODE_WIDGET_KEY] = "real"
        monkeypatch.setattr(st, "query_params", qp, raising=False)
        workspace.apply_query_mode(fallback="mock")
        assert state.current_mode() == "real"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_select_question_button_scrolls_to_picker():
    src = _read("app/ui/workspace.py")
    assert "request_scroll" in src
    assert "question-picker" in src
    assert "st.switch_page(go_questions)" not in src.split("def render_unselected_guide", 1)[1][:800]


def test_selecting_question_scrolls_to_overview():
    src = _read("app/ui/workspace_pages.py")
    assert 'request_scroll("research-overview")' not in src


def test_selecting_q039_updates_top_context():
    src = _read("app/ui/workspace.py")
    assert "context_value = f\"{qid} · {title}\"" in src or "qid} · {title}" in src


def test_top_context_does_not_duplicate_q039():
    header = _read("app/ui/workspace.py").split("def render_workspace_header", 1)[1].split("def render_unselected_guide", 1)[0]
    assert "ws-qid" not in header


def test_quick_example_uses_authoritative_selector_state():
    src = _read("app/ui/workspace.py")
    assert "SELECTOR_WIDGET_KEY" in src
    assert "queue_question_selection" in _read("app/ui/streamlit_app.py")


def test_domain_chart_only_changes_filter():
    src = _read("app/ui/workspace_pages.py")
    assert "QUESTION_DOMAIN_WIDGET_KEY" in src
    assert "select_question" not in src.split("def _render_domain_catalog", 1)[1].split("def _ui_index_mtime", 1)[0]


def test_old_overview_route_redirects():
    src = _read("app/ui/workspace_pages.py")
    block = src.split("def page_overview", 1)[1].split("def page_questions", 1)[0]
    assert "st.switch_page(_HOOKS[\"page_questions\"])" in block
    assert "_render_research_overview" not in block
    nav = _read("app/ui/streamlit_app.py")
    assert '"兼容": [legacy, overview]' in nav


def test_overview_features_preserved():
    src = _read("app/ui/workspace_pages.py")
    for token in (
        "当前研究计划概览",
        "生成研究计划",
        "开始文献调研",
        "运行受控演示",
        "查看历史运行",
        "ov_gen",
        "ov_mock",
        "最新研究动态",
    ):
        assert token in src, token
    parity = _read("docs/ui/OVERVIEW_QUESTION_FEATURE_PARITY.md")
    assert "LOST_OVERVIEW_FEATURE_COUNT | 0" in parity


def test_question_selection_does_not_start_job():
    src = _read("app/ui/workspace_pages.py")
    picker = src.split("def _render_picker_panel", 1)[1].split("def _render_quick_actions", 1)[0]
    assert "submit_or_reuse_job" not in picker
    assert "process_run_triggers" not in picker


def test_question_selection_does_not_cancel_job():
    src = _read("app/ui/state.py")
    assert "不得取消或删除任何 Job" in src


def test_switching_question_does_not_delete_other_active_jobs():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        job_state.set_active_job_id("Q039", job_state.JOB_TYPE_FULL, "job-039")
        state.select_question("Q039", "aging")
        job_state.set_active_job_id("Q028", job_state.JOB_TYPE_FULL, "job-028")
        state.select_question("Q028", "cancer")
        assert job_state.get_pointer_job_id("Q039", job_state.JOB_TYPE_FULL) == "job-039"
        assert job_state.get_pointer_job_id("Q028", job_state.JOB_TYPE_FULL) == "job-028"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_returning_question_restores_original_job():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        job_state.set_active_job_id("Q039", job_state.JOB_TYPE_FULL, "job-039")
        state.select_question("Q028", "cancer")
        state.select_question("Q039", "aging")
        assert job_state.get_pointer_job_id("Q039", job_state.JOB_TYPE_FULL) == "job-039"
        assert state.get(state.KEY_SELECTED_QID) == "Q039"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_question_picker_fragment_does_not_full_rerun():
    src = _read("app/ui/workspace_pages.py")
    assert "@st.fragment" in src
    assert "def render_question_action_hub" in src


def test_question_index_cache_is_used():
    src = _read("app/ui/workspace.py")
    assert "@st.cache_data" in src
    assert "def load_question_index" in src
    assert "def load_question_summary" in src
    assert "def load_domain_distribution" in src


def test_thirty_page_navigation_cycles_preserve_selection():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        state.select_question("Q039", "为什么我们停止生长？")
        for _ in range(30):
            assert state.get(state.KEY_SELECTED_QID) == "Q039"
        assert state.get(state.KEY_SELECTED_QID) == "Q039"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_no_real_provider_calls_in_ui_tests():
    src = _read("app/ui/workspace_pages.py") + _read("app/ui/workspace.py")
    assert "submit_or_reuse_job" not in src.split("def _render_picker_panel", 1)[-1].split("def _render_quick_actions", 1)[0]
    assert "api_client.run_experiment" not in src
    assert "FRONTEND_RUN_VIA_API=1" not in src


def test_legacy_overview_not_in_primary_nav():
    src = _read("app/ui/streamlit_app.py")
    primary = src.split('"研究工作区":', 1)[1].split('"数据与运行"', 1)[0]
    assert "overview" not in primary


def test_root_cause_and_parity_docs_exist():
    assert (ROOT / "docs/ui/OVERVIEW_QUESTION_MERGE_ROOT_CAUSE.md").exists()
    assert (ROOT / "docs/ui/OVERVIEW_QUESTION_FEATURE_PARITY.md").exists()
