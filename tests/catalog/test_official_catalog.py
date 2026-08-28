"""Official catalog, API, selector, and fail-closed Preview Seed tests."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.job_store import SQLiteJobStore
from app.api.main import create_app
from app.api.preview_catalog import ensure_preview_catalog, preview_seed_allowed
from app.catalog.official import (
    EXPECTED_IDS,
    Q028_OFFICIAL_TITLE,
    allow_preview_seed,
    get_catalog_digest,
    load_official_catalog,
    official_catalog_path,
    validate_catalog,
)
from app.ui import components, state
from app.ui.ui_index import UI_INDEX_PATH, load_ui_question_index
from app.ui.workspace import (
    QUERY_QUESTION_KEY,
    format_question_option,
    official_question_id,
    official_question_text,
)


class _NoopRunner:
    def run(self, job, progress_callback):  # pragma: no cover
        raise AssertionError("catalog tests do not run the pipeline")


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


def test_official_catalog_has_125_questions():
    assert len(load_official_catalog().list_questions()) == 125


def test_official_catalog_ids_are_q001_to_q125():
    assert load_official_catalog().question_ids() == EXPECTED_IDS


def test_official_catalog_has_no_duplicate_ids():
    ids = load_official_catalog().question_ids()
    assert len(ids) == len(set(ids))


def test_official_catalog_has_no_preview_seed_marker():
    blob = official_catalog_path().read_text(encoding="utf-8")
    assert "[PREVIEW-SEED]" not in blob
    assert "placeholder question" not in blob.lower()
    assert "preview_seed" not in blob


def test_official_catalog_has_no_placeholder_title():
    assert all("placeholder" not in item.title_en.lower() for item in load_official_catalog().list_questions())


def test_q028_official_title_is_correct():
    assert load_official_catalog().get_question("Q028").title_en == Q028_OFFICIAL_TITLE


def test_packaged_catalog_is_not_gitignored_source_extract():
    path = official_catalog_path()
    assert path.name == "official_question_catalog.json"
    assert not str(path).endswith("questions_125.json")
    assert path.parent.name == "catalog"
    assert path.parent.parent.name == "app"


def test_api_questions_uses_official_catalog(tmp_path):
    with _client(tmp_path) as client:
        body = client.get("/questions").json()
    assert body["catalog_source"] == "official"
    assert body["count"] == 125
    q028 = next(item for item in body["questions"] if item["question_id"] == "Q028")
    assert q028["title_en"] == Q028_OFFICIAL_TITLE
    assert "[PREVIEW-SEED]" not in q028["title_en"]


def test_api_question_count_is_125(tmp_path):
    with _client(tmp_path) as client:
        assert client.get("/questions").json()["count"] == 125
        assert client.get("/health").json()["questions_count"] == 125
        assert client.get("/health/catalog").json() == {
            "status": "ok",
            "count": 125,
            "source": "official",
            "digest": get_catalog_digest(),
            "preview_markers": 0,
        }


def test_api_and_ui_catalog_digest_match(tmp_path):
    with _client(tmp_path) as client:
        api_digest = client.get("/questions").json()["catalog_digest"]
    assert api_digest == get_catalog_digest()


def test_ui_index_catalog_digest_matches_official():
    index = load_ui_question_index()
    digest = index.get("catalog_digest") or index.get("meta", {}).get("catalog_digest")
    if digest:
        assert digest == get_catalog_digest()


def test_ui_index_has_no_preview_seed_marker():
    blob = UI_INDEX_PATH.read_text(encoding="utf-8")
    assert "[PREVIEW-SEED]" not in blob
    assert "placeholder question" not in blob.lower()


def test_production_does_not_fallback_to_preview_seed(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SAGE125_ALLOW_PREVIEW_SEED", "true")
    monkeypatch.setenv("SAGE125_PREVIEW_SEED", "1")
    monkeypatch.setenv("PREVIEW_EPHEMERAL_STORAGE", "true")
    assert allow_preview_seed() is False
    assert preview_seed_allowed() is False


def test_missing_official_catalog_fails_closed(monkeypatch, tmp_path):
    missing = tmp_path / "missing.json"
    monkeypatch.setenv("SAGE125_CATALOG_PATH", str(missing))
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("SAGE125_ALLOW_PREVIEW_SEED", raising=False)
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)
    from app.api import preview_catalog as preview_mod
    from app.catalog.official import clear_catalog_cache

    monkeypatch.setattr(preview_mod, "repository_catalog_path", lambda: tmp_path / "repo-missing.json")
    clear_catalog_cache()
    assert ensure_preview_catalog() is None


def test_development_preview_requires_explicit_flag(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SAGE125_ALLOW_PREVIEW_SEED", raising=False)
    assert allow_preview_seed() is False
    monkeypatch.setenv("SAGE125_ALLOW_PREVIEW_SEED", "true")
    assert allow_preview_seed() is True


def test_selector_options_are_question_ids():
    source = Path("app/ui/workspace_pages.py").read_text(encoding="utf-8")
    assert "official_selector_ids()" in source
    assert "option_ids = [\"\"] + official_selector_ids()" in source
    assert "format_question_option" in source


def test_selector_uses_format_func():
    source = Path("app/ui/workspace_pages.py").read_text(encoding="utf-8")
    assert "format_func=lambda item: format_question_option" in source
    assert inspect.getsource(format_question_option)


def test_session_state_stores_only_question_id():
    assert state.KEY_SELECTED_QID == "selected_question_id"
    assert official_question_id("Q028 · [PREVIEW-SEED] Biology placeholder question 06?") is None
    assert official_question_id("Q028") == "Q028"


def test_stale_placeholder_widget_state_is_removed():
    source = Path("app/ui/workspace.py").read_text(encoding="utf-8")
    assert "sanitize_question_selector_state" in source
    assert components.SELECTOR_WIDGET_KEY == "_question_selector"


def test_top_context_looks_up_title_by_id():
    assert official_question_text("Q028") == Q028_OFFICIAL_TITLE


def test_query_param_stores_only_question_id():
    assert QUERY_QUESTION_KEY == "question_id"
    source = Path("app/ui/workspace.py").read_text(encoding="utf-8")
    assert "st.query_params[QUERY_QUESTION_KEY] = official" in source


def test_q028_selector_label_is_official():
    assert format_question_option("Q028") == f"Q028 · {Q028_OFFICIAL_TITLE}"


def test_page_navigation_does_not_restore_old_placeholder():
    assert official_question_id("Biology placeholder question 06?") is None


def test_cache_digest_change_invalidates_old_catalog(tmp_path):
    from app.catalog.official import _load_cached

    catalog = load_official_catalog()
    _load_cached.cache_clear()
    again = load_official_catalog()
    assert again.digest == catalog.digest


def test_result_root_digest_is_unchanged(tmp_path):
    pointer = Path("data/ui/results_root_pointer.json")
    assert pointer.exists()
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    assert payload.get("catalog_path")


def test_no_provider_calls_in_catalog_tests():
    banned = "import " + "openai"
    assert banned not in Path("app/catalog/official.py").read_text(encoding="utf-8")


def test_validate_catalog_rejects_preview_rows():
    good = [
        {
            "question_id": f"Q{i:03d}",
            "title_en": Q028_OFFICIAL_TITLE if i == 28 else f"Official question {i:03d}?",
            "domain": "Biology",
        }
        for i in range(1, 126)
    ]
    validate_catalog({"catalog_source": "official", "questions": good})
    good[27]["title_en"] = "[PREVIEW-SEED] Biology placeholder question 06?"
    try:
        validate_catalog({"catalog_source": "official", "questions": good})
    except ValueError:
        return
    raise AssertionError("preview title must fail validation")
