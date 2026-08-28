"""T08 Wave A 基础交付冒烟。

覆盖 FastAPI 健康状态、核心 API/OpenAPI 可访问性，以及 Streamlit
入口脚本的真实执行。测试不发起 LLM 或外网调用。
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.api import routes
from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.contracts import JobCreateRequest, JobStatus
from app.api.job_store import SQLiteJobStore
from app.api.main import app, create_app


PROJECT_ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def test_health_degrades_when_required_delivery_inputs_are_unavailable(monkeypatch):
    """问题清单或本地依赖不可用时不得硬编码为健康。"""
    monkeypatch.setattr(routes, "_questions_count", lambda: 0)
    monkeypatch.setattr(routes, "_rag_index_status", lambda: "unavailable")
    monkeypatch.setattr(
        routes,
        "_delivery_dependency_status",
        lambda _request: {
            "job_store": "unavailable",
            "artifact_registry": "unavailable",
            "artifact_storage": "unavailable",
        },
    )

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["questions_count"] == 0
    assert body["rag_index_status"] == "unavailable"
    assert body["dependencies"]["job_store"] == "unavailable"
    assert "sk-" not in json.dumps(body)


def test_health_is_ok_when_required_delivery_inputs_are_available(monkeypatch):
    """基础交付依赖就绪时 health 才返回 ok。"""
    monkeypatch.setattr(routes, "_questions_count", lambda: 125)
    monkeypatch.setattr(routes, "_rag_index_status", lambda: "ready")
    monkeypatch.setattr(
        routes,
        "_delivery_dependency_status",
        lambda _request: {
            "job_store": "available",
            "artifact_registry": "available",
            "artifact_storage": "available",
        },
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_core_api_and_generated_openapi_are_accessible():
    """核心只读 API 与由真实路由生成的 OpenAPI 均可访问。"""
    assert client.get("/health").status_code == 200
    assert client.get("/questions").status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/questions" in paths
    assert "/runs" in paths
    assert "/runs/{run_id}/artifacts" in paths
    assert "/runs/{run_id}/files/{file_name}" in paths


def test_streamlit_entrypoint_executes_without_exception(monkeypatch):
    """在 Mock 配置下真实执行 Streamlit 入口，防止启动即白屏。"""
    monkeypatch.setenv("MOCK_LLM", "true")

    streamlit_app = AppTest.from_file(
        str(PROJECT_ROOT / "app" / "ui" / "streamlit_app.py")
    ).run(timeout=30)

    assert not streamlit_app.exception


def test_oversized_upload_response_keeps_correlation_id():
    """multipart 解析前返回的 413 也必须可追踪。"""
    response = client.post(
        "/ingest",
        headers={
            "Content-Length": str(200 * 1024 * 1024),
            "X-Correlation-ID": "oversized-audit",
        },
    )

    assert response.status_code == 413
    assert response.headers["X-Correlation-ID"] == "oversized-audit"


def test_v1_fails_closed_when_auth_is_not_configured(monkeypatch):
    """缺少服务端 key 配置时不得匿名开放 v1。"""
    monkeypatch.delenv("SAGE_API_KEYS_JSON", raising=False)
    isolated = create_app()

    with TestClient(isolated) as isolated_client:
        response = isolated_client.get("/api/v1/questions")

    assert response.status_code == 503
    assert response.json()["code"] == "AUTH_NOT_CONFIGURED"


def test_default_production_composition_keeps_owner_report_unavailable(tmp_path):
    """默认 composition 不得从旧文件或 fixture 拼装 canonical report。"""
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    isolated = create_app(
        job_store=store,
        auth_policy=HashedAPIKeyAuth({"test-user": "test-api-token-123"}),
        rate_limiter=FixedWindowRateLimiter(limit=100, window_seconds=60),
    )

    with TestClient(
        isolated,
        headers={"X-API-Key": "test-api-token-123"},
    ) as isolated_client:
        record, _ = store.create_job(
            request=JobCreateRequest(question_id="Q001", mode="real"),
            correlation_id="corr-default-composition",
            requested_by="test-user",
        )
        store.transition(
            record.job_id,
            JobStatus.RUNNING,
            actor="test",
            source="fixture",
            upstream_run_id="run-owner-1",
            increment_attempt=True,
        )
        response = isolated_client.get(
            f"/api/v1/jobs/{record.job_id}/report"
        )

    assert response.status_code == 503
    assert response.json()["code"] == "CANONICAL_REPORT_UNAVAILABLE"
