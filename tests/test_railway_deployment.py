"""Deployment contracts for Railway staging and server-only Bailian access."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.config import Settings
from app.rag.library_manager import LibraryManager
from app.ui import api_client
from scripts.start_railway_api import railway_port


ROOT = Path(__file__).resolve().parents[1]


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_bailian_configuration_rejects_missing_padded_and_placeholder_values():
    missing = _settings(DASHSCOPE_API_KEY="", WORKSPACE_ID="")
    padded = _settings(DASHSCOPE_API_KEY=" key-with-spaces ", WORKSPACE_ID="workspace")
    placeholder = _settings(DASHSCOPE_API_KEY="YOUR_KEY", WORKSPACE_ID="placeholder")

    assert not missing.bailian.configured
    assert not padded.bailian.configured
    assert not placeholder.bailian.configured
    assert missing.dashscope_base_url == ""
    assert placeholder.dashscope_base_url == ""


def test_bailian_configuration_is_server_derived_and_safe_to_summarize():
    settings = _settings(
        DASHSCOPE_API_KEY="test-key-not-a-real-secret",
        WORKSPACE_ID="test-workspace",
        DASHSCOPE_REGION="cn-beijing",
    )

    assert settings.bailian.configured
    assert settings.bailian.provider == "bailian"
    assert settings.bailian.chat_model == "qwen3.7-plus"
    assert settings.bailian.embedding_model == "text-embedding-v4"
    assert settings.dashscope_base_url.endswith(".cn-beijing.maas.aliyuncs.com/compatible-mode/v1")

    summary_blob = json.dumps(settings.safe_summary(), ensure_ascii=False)
    assert "test-key-not-a-real-secret" not in summary_blob
    assert "test-workspace" not in summary_blob
    assert ".maas.aliyuncs.com" not in summary_blob


def test_health_exposes_only_bailian_configuration_state(monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes, "get_settings", lambda: _settings())
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "sage125-api"
    assert body["bailian"] == {"configured": False, "status": "unavailable"}
    blob = json.dumps(body)
    assert "workspace_id" not in blob.lower()
    assert "base_url" not in blob.lower()


def test_real_run_without_bailian_is_service_unavailable(monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes, "get_settings", lambda: _settings())
    response = TestClient(app).post(
        "/runs",
        json={
            "question_id": "Q001",
            "mode": "real",
            "use_local_rag": False,
            "use_deep_research": False,
            "use_open_literature": False,
        },
    )
    assert response.status_code == 503


def test_api_only_ui_never_runs_pipeline_inprocess(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    monkeypatch.setattr(api_client, "api_available", lambda: False)
    monkeypatch.setattr(
        api_client,
        "_start_run_inprocess",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("in-process fallback")),
    )

    result = api_client.start_run("Q001", "", {}, mode="real")

    assert result["status"] == "failed"
    assert result["error_type"] == "api_unavailable"


def test_library_manager_uses_configured_data_root(tmp_path):
    settings = _settings(
        DATA_DIR=str(tmp_path),
        LIBRARY_MIN_FREE_MB=0,
        LIBRARY_MIN_FREE_PERCENT=0,
    )
    manager = LibraryManager(settings=settings)

    assert manager.uploads_dir == tmp_path / "raw" / "uploads"
    assert manager.index_config.data_root == tmp_path


def test_railway_config_and_entrypoint_contracts(monkeypatch):
    api_cfg = tomllib.loads((ROOT / "railway-api.toml").read_text(encoding="utf-8"))
    ui_cfg = tomllib.loads((ROOT / "railway-ui.toml").read_text(encoding="utf-8"))

    assert api_cfg["build"]["builder"] == "RAILPACK"
    assert api_cfg["deploy"]["healthcheckPath"] == "/health"
    assert ui_cfg["deploy"]["healthcheckPath"] == "/_stcore/health"
    assert "start_railway_api.py" in api_cfg["deploy"]["startCommand"]
    assert "start_railway_ui.py" in ui_cfg["deploy"]["startCommand"]

    monkeypatch.setenv("PORT", "4321")
    assert railway_port() == 4321


def test_ci_covers_integration_and_main_pushes_and_pull_requests():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "push:\n    branches:\n      - integration/2026-08-10\n      - main" in workflow
    pull_request_section = workflow.split("pull_request:", 1)[1].split("permissions:", 1)[0]
    assert "- integration/2026-08-10" in pull_request_section
    assert "- main" in pull_request_section


def test_gitattributes_has_no_utf8_bom():
    assert not (ROOT / ".gitattributes").read_bytes().startswith(b"\xef\xbb\xbf")
