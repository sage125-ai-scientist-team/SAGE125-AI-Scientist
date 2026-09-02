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


def test_http_run_unwraps_fastapi_detail_errors(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    monkeypatch.setattr(api_client, "api_available", lambda: True)

    class Response:
        status_code = 503
        headers = {"content-type": "application/json"}
        text = ""

        @staticmethod
        def json():
            return {
                "detail": {
                    "status": "failed",
                    "message": "preflight 未通过",
                    "errors": ["百炼连通性检查失败：网络超时"],
                    "preflight": {"ok": False},
                }
            }

    monkeypatch.setattr(api_client.requests, "post", lambda *args, **kwargs: Response())

    result = api_client.start_run("Q001", "", {"use_deep_research": False}, mode="real")

    assert result["status"] == "failed"
    assert result["error_type"] == "preflight_failed"
    assert "百炼连通性检查失败" in result["errors"][0]


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


def test_api_only_preflight_banner_keeps_short_timeout(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    monkeypatch.setenv("FRONTEND_API_SHORT_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("FRONTEND_API_WAKE_TIMEOUT_SECONDS", "75")
    observed = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True, "errors": [], "warnings": []}

    def fake_get(url, *, params=None, timeout=None):
        observed.append({"url": url, "timeout": timeout, "params": params})
        return Response()

    monkeypatch.setattr(api_client.requests, "get", fake_get)

    result = api_client.run_preflight(True, True)

    assert result["ok"] is True
    preflight_calls = [item for item in observed if str(item["url"]).endswith("/preflight")]
    assert len(preflight_calls) == 1
    assert preflight_calls[0]["timeout"] == 10


def test_api_only_preflight_wakes_and_retries_timeout(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    monkeypatch.setenv("FRONTEND_API_SHORT_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("FRONTEND_API_WAKE_TIMEOUT_SECONDS", "75")
    monkeypatch.setattr(api_client.time, "sleep", lambda _seconds: None)
    observed = []

    class OkResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True, "errors": [], "warnings": []}

    def fake_get(url, *, params=None, timeout=None):
        observed.append({"url": url, "timeout": timeout})
        if str(url).endswith("/preflight") and sum(
            1 for item in observed if str(item["url"]).endswith("/preflight")
        ) == 1:
            raise api_client.requests.Timeout("cold start")
        return OkResponse()

    monkeypatch.setattr(api_client.requests, "get", fake_get)

    result = api_client.run_preflight(True, True, allow_wake=True)

    assert result["ok"] is True
    preflight_calls = [item for item in observed if str(item["url"]).endswith("/preflight")]
    assert len(preflight_calls) == 2
    assert all(item["timeout"] == 75 for item in preflight_calls)
    assert any(str(item["url"]).endswith("/health") for item in observed)


def test_api_only_preflight_surfaces_http_errors(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")

    class Response:
        status_code = 503

        @staticmethod
        def json():
            return {"ok": False, "errors": ["百炼未配置"], "warnings": []}

    monkeypatch.setattr(
        api_client.requests,
        "get",
        lambda url, *, params=None, timeout=None: Response(),
    )

    result = api_client.run_preflight(True, False)

    assert result["ok"] is False
    assert "百炼未配置" in result["errors"]


def test_api_only_preflight_retries_429_then_succeeds(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    monkeypatch.setattr(api_client.time, "sleep", lambda _seconds: None)
    observed = []

    class Limited:
        status_code = 429
        headers = {"Retry-After": "1"}

        @staticmethod
        def json():
            return {"code": "RATE_LIMIT_EXCEEDED", "message": "请求频率超过限制，请稍后重试。"}

    class OkResponse:
        status_code = 200
        headers = {}

        @staticmethod
        def json():
            return {"ok": True, "errors": [], "warnings": []}

    def fake_get(url, *, params=None, timeout=None):
        observed.append(str(url))
        if str(url).endswith("/preflight") and sum(
            1 for item in observed if item.endswith("/preflight")
        ) == 1:
            return Limited()
        return OkResponse()

    monkeypatch.setattr(api_client.requests, "get", fake_get)

    result = api_client.run_preflight(True, True, allow_wake=True)

    assert result["ok"] is True
    assert sum(1 for item in observed if item.endswith("/preflight")) == 2


def test_api_only_preflight_429_falls_back_to_health(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    monkeypatch.setattr(api_client.time, "sleep", lambda _seconds: None)

    class Limited:
        status_code = 429
        headers = {"Retry-After": "1"}

        @staticmethod
        def json():
            return {"code": "RATE_LIMIT_EXCEEDED", "message": "请求频率超过限制，请稍后重试。"}

    class HealthOk:
        status_code = 200
        headers = {}

        @staticmethod
        def json():
            return {
                "status": "ok",
                "service": "sage125-api",
                "qwen_config_loaded": True,
                "bailian": {"configured": True, "status": "available"},
                "questions_count": 125,
            }

    def fake_get(url, *, params=None, timeout=None):
        if str(url).endswith("/preflight"):
            return Limited()
        return HealthOk()

    monkeypatch.setattr(api_client.requests, "get", fake_get)

    result = api_client.run_preflight(True, True, allow_wake=True)

    assert result["ok"] is True
    assert result.get("recovered_from_transient") is True
    assert "HTTP 429" not in " ".join(result.get("errors") or [])


def test_api_only_preflight_banner_429_is_nonblocking(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")

    class Limited:
        status_code = 429
        headers = {}

        @staticmethod
        def json():
            return {"code": "RATE_LIMIT_EXCEEDED", "message": "请求频率超过限制，请稍后重试。"}

    monkeypatch.setattr(
        api_client.requests,
        "get",
        lambda url, *, params=None, timeout=None: Limited(),
    )

    result = api_client.run_preflight(True, True)

    assert result["ok"] is True
    assert result.get("deferred") is True
    assert "HTTP 429" not in " ".join(result.get("errors") or [])


def test_real_start_preflight_allows_hosted_wake():
    src = (ROOT / "app/ui/streamlit_app.py").read_text(encoding="utf-8")
    trigger = src.split("def process_run_triggers", 1)[1].split("if trigger_latest", 1)[0]
    assert "allow_wake=True" in trigger
    assert "正在检查并唤醒 sage125-api" in trigger
    assert "服务正在恢复" in trigger
    assert "瞬时 429" in trigger


def test_create_job_retries_429(monkeypatch):
    monkeypatch.setattr(api_client.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(api_client, "api_available", lambda: True)
    monkeypatch.setattr(api_client, "refresh_api_available", lambda: True)
    calls = {"n": 0}

    class Limited:
        status_code = 429
        headers = {"Retry-After": "1"}

        @staticmethod
        def json():
            return {"code": "RATE_LIMIT_EXCEEDED", "message": "请求频率超过限制，请稍后重试。"}

    class Accepted:
        status_code = 202
        headers = {}

        @staticmethod
        def json():
            return {"job_id": "job-retry", "created": True}

    class Session:
        @staticmethod
        def post(*args, **kwargs):
            calls["n"] += 1
            return Limited() if calls["n"] < 3 else Accepted()

    monkeypatch.setattr(api_client, "_http_session", lambda: Session())

    result = api_client.create_job(
        question_id="Q019",
        mode="real",
        job_type="full",
        client_id="client-1",
        input_digest="digest",
        idempotency_key="key",
    )

    assert result["job_id"] == "job-retry"
    assert calls["n"] == 3


def test_create_job_refreshes_stale_health_before_failing(monkeypatch):
    probes = {"n": 0}

    def fake_available() -> bool:
        probes["n"] += 1
        return probes["n"] >= 2

    class Response:
        status_code = 202

        @staticmethod
        def json():
            return {"job_id": "job-wake", "created": True}

    class Session:
        @staticmethod
        def post(*args, **kwargs):
            return Response()

    monkeypatch.setattr(api_client, "api_available", fake_available)
    monkeypatch.setattr(api_client, "_http_session", lambda: Session())

    result = api_client.create_job(
        question_id="Q106",
        mode="real",
        job_type="full",
        client_id="client-1",
        input_digest="digest",
        idempotency_key="key",
    )

    assert result["job_id"] == "job-wake"
    assert probes["n"] == 2


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
    assert blueprint.count("autoDeployTrigger: off") == 2
    assert "autoDeployTrigger: checksPass" not in blueprint
    assert "autoDeployTrigger: commit" not in blueprint
    assert "startCommand: python -m scripts.start_api" in blueprint
    assert "startCommand: python -m scripts.start_ui" in blueprint
    assert "healthCheckPath: /health" in blueprint
    assert "healthCheckPath: /_stcore/health" in blueprint
    assert "FRONTEND_API_BASE_URL" in blueprint
    assert "FRONTEND_API_SHORT_TIMEOUT_SECONDS" in blueprint
    assert "FRONTEND_API_WAKE_TIMEOUT_SECONDS" in blueprint
    assert "FRONTEND_INGEST_TIMEOUT_SECONDS" in blueprint
    assert "SAGE125_PREVIEW_SEED" in blueprint
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


def test_api_entrypoint_bootstraps_preview_questions():
    """
    API 启动入口必须在 uvicorn 前尝试引导 questions_125.json。

    返回：
        None；源码契约失败即测试失败。
    """
    start_api = (ROOT / "scripts" / "start_api.py").read_text(encoding="utf-8")
    assert "ensure_preview_questions" in start_api
    assert "ensure_preview_catalog" in start_api
    assert "allow_preview_seed" in start_api
    assert "_preview_seed_allowed" in start_api


def test_ci_covers_integration_and_main_pushes_and_pull_requests():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "push:\n    branches:\n      - integration/2026-08-10\n      - main" in workflow
    pull_request_section = workflow.split("pull_request:", 1)[1].split("permissions:", 1)[0]
    assert "- integration/2026-08-10" in pull_request_section
    assert "- main" in pull_request_section
    assert "preview-deploy:" in workflow
    assert "github.event_name == 'push' && github.ref == 'refs/heads/integration/2026-08-10'" in workflow
    assert "needs: [lint, type, unit, integration, coverage, security, build]" in workflow
    assert "secrets.RENDER_API_KEY" in workflow
    assert "srv-d9pe8jm417fc73dnnirg" in workflow
    assert "srv-d9pe8jm417fc73dnnisg" in workflow
    assert "https://api.render.com/v1/services/${id}/deploys" in workflow


def test_gitattributes_has_no_utf8_bom():
    assert not (ROOT / ".gitattributes").read_bytes().startswith(b"\xef\xbb\xbf")


def test_read_local_file_uses_api_when_local_copy_is_missing(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    api_client._clear_remote_run_file_cache()
    monkeypatch.setattr(api_client, "local_file_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api_client, "api_available", lambda: True)
    observed = {}

    class Response:
        status_code = 200
        content = b'{"hypotheses": []}'

    class Session:
        @staticmethod
        def get(url, timeout=None):
            observed["url"] = url
            observed["timeout"] = timeout
            return Response()

    monkeypatch.setattr(api_client, "_http_session", lambda: Session())

    content = api_client.read_local_file("run-remote", "report.json")

    assert content == b'{"hypotheses": []}'
    assert observed["url"].endswith("/runs/run-remote/files/report.json")
    assert observed["timeout"] == 10


def test_read_local_file_stays_unavailable_when_api_missing(monkeypatch):
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "1")
    api_client._clear_remote_run_file_cache()
    monkeypatch.setattr(api_client, "local_file_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api_client, "api_available", lambda: False)

    def fail_fetch(*_args, **_kwargs):
        raise AssertionError("must not invent export bytes")

    monkeypatch.setattr(api_client, "_fetch_remote_run_file", fail_fetch)

    assert api_client.read_local_file("run-remote", "report.json") is None
    assert api_client.read_local_file("run-remote", "../secret.env") is None
    assert api_client.read_local_file("run-remote", "not_an_artifact.bin") is None

