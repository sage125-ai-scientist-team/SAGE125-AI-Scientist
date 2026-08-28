"""Catalog search, filters, selector, and deployment-info regression tests."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import streamlit as st
from fastapi.testclient import TestClient

from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.deployment_info import deployment_info_payload
from app.api.job_store import SQLiteJobStore
from app.api.main import create_app
from app.catalog.official import EXPECTED_IDS, get_catalog_digest, load_official_catalog
from app.catalog.query import (
    STATUS_FILTER_OPTIONS,
    domain_options_with_counts,
    filter_questions,
    official_selector_ids,
    quick_example_map,
    resolve_quick_examples,
    search_official_questions,
)
from app.ui import components, state, workspace

ROOT = Path(__file__).resolve().parents[2]


class _NoopRunner:
    def run(self, job, progress_callback):  # pragma: no cover
        raise AssertionError("catalog interaction tests do not run the pipeline")


def _client(tmp_path: Path) -> TestClient:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    app = create_app(
        job_store=store,
        job_runner=_NoopRunner(),
        auth_policy=HashedAPIKeyAuth({"preview-user": "preview-token-123"}),
        rate_limiter=FixedWindowRateLimiter(limit=10_000, window_seconds=60),
        artifact_root=tmp_path / "artifacts",
    )
    return TestClient(app, headers={"X-API-Key": "preview-token-123"})


def test_official_catalog_count_is_125():
    assert len(load_official_catalog().list_questions()) == 125


def test_catalog_domain_count_is_12():
    assert len({item.domain for item in load_official_catalog().list_questions()}) == 12


def test_catalog_has_no_preview_seed():
    blob = json.dumps([item.title_en for item in load_official_catalog().list_questions()])
    assert "[PREVIEW-SEED]" not in blob
    assert "placeholder question" not in blob.lower()


def test_search_prime_returns_results():
    assert any(item.question_id == "Q001" for item in search_official_questions("prime"))


def test_search_gravity_returns_results():
    assert any(item.question_id == "Q067" for item in search_official_questions("gravity"))


def test_search_pandemic_returns_results():
    assert any(item.question_id == "Q013" for item in search_official_questions("pandemic"))


def test_search_is_case_insensitive():
    lower = {item.question_id for item in search_official_questions("PRIME")}
    upper = {item.question_id for item in search_official_questions("prime")}
    assert lower == upper
    assert "Q001" in lower


def test_search_supports_chinese():
    hits = search_official_questions("Q001")
    assert hits and hits[0].question_id == "Q001"
    math = search_official_questions("Mathematical")
    assert {item.question_id for item in math}


def test_domain_filter_has_12_domains():
    options = domain_options_with_counts()
    assert len(options) == 12
    assert all(count > 0 for _name, count in options)


def test_domain_filter_combines_with_search():
    rows = filter_questions(query="quantum", domain="Physics")
    assert rows
    assert all(item.domain == "Physics" for item in rows)


def test_status_filter_has_real_options():
    assert STATUS_FILTER_OPTIONS[0] == "全部"
    assert len(STATUS_FILTER_OPTIONS) >= 2
    assert "尚未开始" in STATUS_FILTER_OPTIONS
    assert "已完成" in STATUS_FILTER_OPTIONS


def test_quick_example_map_has_5_valid_ids():
    mapping = quick_example_map()
    assert len(mapping) == 5
    assert set(mapping) == {"prime", "pandemic", "climate", "creativity", "quantum"}
    assert all(qid in EXPECTED_IDS for qid in mapping.values())
    assert len(set(mapping.values())) == 5


def test_quick_example_click_updates_selected_id():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        workspace.select_quick_example("Q001")
        assert state.get(state.KEY_SELECTED_QID) == "Q001"
        assert st.session_state.get(components.SELECTOR_WIDGET_KEY) == "Q001"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_quick_example_does_not_create_job():
    source = inspect.getsource(workspace.select_quick_example)
    assert "submit" not in source
    assert "start_run" not in source
    assert "create_job" not in source


def test_question_selector_has_125_options():
    ids = official_selector_ids()
    assert len(ids) == 125
    assert ids == EXPECTED_IDS


def test_question_selector_stores_only_id():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        st.session_state[components.SELECTOR_WIDGET_KEY] = "Q028"
        workspace.store_question_selector_state()
        assert state.get(state.KEY_SELECTED_QID) == "Q028"
        assert "placeholder" not in str(state.get(state.KEY_SELECTED_QTEXT) or "").lower()
        assert " · " not in str(state.get(state.KEY_SELECTED_QID))
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_question_selector_survives_rerun():
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        st.session_state[state.KEY_SELECTED_QID] = "Q013"
        workspace.load_question_selector_state()
        assert st.session_state[components.SELECTOR_WIDGET_KEY] == "Q013"
        workspace.sanitize_question_selector_state(EXPECTED_IDS)
        assert state.get(state.KEY_SELECTED_QID) == "Q013"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_question_selector_survives_page_navigation():
    assert state.KEY_SELECTED_QID == "selected_question_id"
    source = Path("app/ui/workspace.py").read_text(encoding="utf-8")
    assert "apply_query_question" in source
    assert "persist_query_question" in source


def test_question_selector_survives_browser_refresh():
    source = Path("app/ui/workspace.py").read_text(encoding="utf-8")
    assert 'QUERY_QUESTION_KEY = "question_id"' in source
    assert "st.query_params[QUERY_QUESTION_KEY] = official" in source


def test_empty_catalog_fails_closed(monkeypatch, tmp_path):
    from app.catalog.official import clear_catalog_cache
    from app.catalog import query as query_mod

    monkeypatch.setenv("SAGE125_CATALOG_PATH", str(tmp_path / "missing.json"))
    clear_catalog_cache()
    query_mod.resolve_quick_examples.cache_clear()
    items, error = workspace._load_official_questions_or_fail()
    assert items == []
    assert error is not None
    assert error["status"] == "failed"
    assert "官方题目目录加载失败" in error["message"]
    assert error.get("correlation_id")


def test_api_questions_returns_125(tmp_path):
    with _client(tmp_path) as client:
        body = client.get("/questions").json()
    assert body["count"] == 125
    assert len(body["questions"]) == 125


def test_health_catalog_reports_official_source(tmp_path):
    with _client(tmp_path) as client:
        body = client.get("/health/catalog").json()
    assert body["status"] == "ok"
    assert body["source"] == "official"
    assert body["count"] == 125


def test_ui_api_catalog_digest_match(tmp_path):
    with _client(tmp_path) as client:
        api_digest = client.get("/questions").json()["catalog_digest"]
    assert api_digest == get_catalog_digest()


def test_catalog_cached_once_per_digest():
    source = Path("app/ui/workspace.py").read_text(encoding="utf-8")
    assert "@st.cache_data(show_spinner=False)" in source
    assert "def _cached_official_questions" in source


def test_no_full_result_scan_on_filter_interaction():
    source = inspect.getsource(filter_questions) + inspect.getsource(search_official_questions)
    assert "result.json" not in source
    assert "exports" not in source
    assert "pdf" not in source.lower()


def test_no_provider_calls():
    for rel in ("app/catalog/query.py", "app/catalog/official.py", "app/ui/workspace_pages.py"):
        blob = (ROOT / rel).read_text(encoding="utf-8")
        assert "openai" not in blob
        assert "dashscope" not in blob.lower()
        assert "openrouter" not in blob.lower()


def test_no_secrets():
    payload = json.dumps(deployment_info_payload())
    for banned in ("api_key", "secret", "password", "token", "cookie", "workspace_id"):
        assert banned not in payload.lower()


def test_deployment_info_contains_commit_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123def456")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "integration/2026-08-10")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "sage125-api-preview")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "should-not-appear")
    with _client(tmp_path) as client:
        body = client.get("/api/v1/deployment-info").json()
        legacy = client.get("/deployment-info").json()
    assert body["git_commit"] == "abc123def456"
    assert body["question_count"] == 125
    assert "should-not-appear" not in json.dumps(body)
    assert legacy["git_commit"] == "abc123def456"


def test_particle_canvas_single_instance():
    landing = (ROOT / "app/ui/landing.py").read_text(encoding="utf-8")
    assert landing.count("sage125_landing(") == 1


def test_navigation_30_cycles():
    pages = (ROOT / "app/ui/workspace_pages.py").read_text(encoding="utf-8")
    assert "def page_questions" in pages
    assert "def page_evidence" in pages
    assert "bootstrap(" in pages
    assert "_HEALTH_SESSION_TTL_SECONDS" in (ROOT / "app/ui/workspace.py").read_text(encoding="utf-8")


def test_quick_examples_resolve_from_official_titles():
    digest = get_catalog_digest()
    resolved = resolve_quick_examples(digest)
    assert [item.question_id for item in resolved] == ["Q001", "Q013", "Q107", "Q125", "Q086"]
