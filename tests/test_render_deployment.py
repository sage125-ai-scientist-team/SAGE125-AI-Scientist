"""Deployment contracts for the Render preview and server-only Bailian access."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.config import Settings
from app.rag.library_manager import LibraryManager
from app.ui import api_client
from scripts.start_api import service_port as api_port
from scripts.start_ui import service_port as ui_port


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


def test_health_exposes_only_bailian_and_ephemeral_storage_state(monkeypatch):
    from app.api import routes

    monkeypatch.setattr(
        routes,
        "get_settings",
        lambda: _settings(PREVIEW_EPHEMERAL_STORAGE=True),
    )
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "sage125-api"
    assert body["bailian"] == {"configured": False, "status": "unavailable"}
    assert body["storage"] == {"mode": "ephemeral", "persistent": False}
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


def test_render_ui_health_probe_allows_cold_start(monkeypatch):
    monkeypatch.setenv("FRONTEND_API_WAKE_TIMEOUT_SECONDS", "75")
    observed = {}

    class Response:
        status_code = 200

    def fake_get(url, *, timeout):
        observed.update({"url": url, "timeout": timeout})
        return Response()

    monkeypatch.setattr(api_client.requests, "get", fake_get)

    assert api_client.api_available()
    assert observed["url"].endswith("/health")
    assert observed["timeout"] == 75


def test_api_only_ingest_posts_directly_without_health_gate(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    monkeypatch.setenv("FRONTEND_API_SHORT_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("FRONTEND_INGEST_TIMEOUT_SECONDS", "900")
    monkeypatch.setattr(api_client, "get_library_status", lambda: {"status": "empty"})
    monkeypatch.setattr(
        api_client,
        "api_available",
        lambda: (_ for _ in ()).throw(AssertionError("health gate must not run")),
    )
    observed = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "ok", "files": ["paper.txt"], "chunks_added": 1}

    def fake_post(url, *, files, timeout):
        observed.update({"url": url, "files": files, "timeout": timeout})
        return Response()

    monkeypatch.setattr(api_client.requests, "post", fake_post)

    result = api_client.ingest_files([("paper.txt", b"evidence")])

    assert result["status"] == "ok"
    assert observed["url"].endswith("/ingest")
    assert observed["timeout"] == (10, 900)


def test_api_only_ingest_timeout_is_not_retried_or_reported_as_definite_loss(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    monkeypatch.setattr(api_client, "get_library_status", lambda: {"status": "empty"})
    calls = []

    def timeout_post(*args, **kwargs):
        calls.append((args, kwargs))
        raise api_client.requests.Timeout("expected test timeout")

    monkeypatch.setattr(api_client.requests, "post", timeout_post)

    result = api_client.ingest_files([("paper.txt", b"evidence")])

    assert len(calls) == 1
    assert result["status"] == "failed"
    assert result["error_type"] == "ingest_result_unconfirmed"
    assert "刷新文献清单" in result["message"]


def test_library_manager_uses_configured_data_root(tmp_path):
    settings = _settings(
        DATA_DIR=str(tmp_path),
        LIBRARY_MIN_FREE_MB=0,
        LIBRARY_MIN_FREE_PERCENT=0,
    )
    manager = LibraryManager(settings=settings)

    assert manager.uploads_dir == tmp_path / "raw" / "uploads"
    assert manager.index_config.data_root == tmp_path


def test_render_blueprint_and_entrypoint_contracts(monkeypatch):
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "generation: off" in blueprint
    assert "name: SAGE125-AI-Scientist-Preview" in blueprint
    assert "name: preview" in blueprint
    assert "name: sage125-api-preview" in blueprint
    assert "name: sage125-ui-preview" in blueprint
    assert blueprint.count("repo: https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist") == 2
    assert blueprint.count("branch: integration/2026-08-10") == 2
    assert blueprint.count("plan: free") == 2
    assert blueprint.count("region: singapore") == 2
    assert blueprint.count("autoDeployTrigger: checksPass") == 2
    assert "startCommand: python -m scripts.start_api" in blueprint
    assert "startCommand: python -m scripts.start_ui" in blueprint
    assert "healthCheckPath: /health" in blueprint
    assert "healthCheckPath: /_stcore/health" in blueprint
    assert "FRONTEND_API_SHORT_TIMEOUT_SECONDS" in blueprint
    assert "FRONTEND_API_WAKE_TIMEOUT_SECONDS" in blueprint
    assert "FRONTEND_INGEST_TIMEOUT_SECONDS" in blueprint
    assert "DASHSCOPE_API_KEY" not in blueprint
    assert "WORKSPACE_ID" not in blueprint
    assert "domains:" not in blueprint

    monkeypatch.setenv("PORT", "4321")
    assert api_port() == 4321
    assert ui_port() == 4321


def test_hosted_ui_hides_internal_error_details():
    start_ui = (ROOT / "scripts" / "start_ui.py").read_text(encoding="utf-8")

    assert '"--client.showErrorDetails"' in start_ui
    assert '"false"' in start_ui


def test_ci_covers_integration_and_main_pushes_and_pull_requests():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "push:\n    branches:\n      - integration/2026-08-10\n      - main" in workflow
    pull_request_section = workflow.split("pull_request:", 1)[1].split("permissions:", 1)[0]
    assert "- integration/2026-08-10" in pull_request_section
    assert "- main" in pull_request_section


def test_gitattributes_has_no_utf8_bom():
    assert not (ROOT / ".gitattributes").read_bytes().startswith(b"\xef\xbb\xbf")
