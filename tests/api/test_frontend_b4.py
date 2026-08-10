"""Wave B4 API-only frontend client and state semantics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from frontend.api_client import APIClientError, B4APIClient
from frontend.view_models import ViewState, classify_job_view, confidence_state


def _client(handler) -> B4APIClient:
    transport = httpx.MockTransport(handler)
    return B4APIClient(
        base_url="http://api.test",
        api_key="frontend-test-token",
        transport=transport,
    )


def test_frontend_client_uses_only_v1_http_contracts_and_propagates_auth():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/v1/questions":
            return httpx.Response(
                200,
                json={"items": [], "count": 0, "total": 0, "availability": "available"},
            )
        if request.url.path == "/api/v1/jobs/job-1/report":
            return httpx.Response(200, json={"job_id": "job-1", "gates": []})
        if request.url.path == "/api/v1/jobs/job-1/artifacts/art-1/download":
            return httpx.Response(200, content=b"report")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _client(handler)
    assert client.questions()["items"] == []
    assert client.report("job-1")["gates"] == []
    assert client.download("job-1", "art-1") == b"report"
    assert {request.headers["X-API-Key"] for request in calls} == {
        "frontend-test-token"
    }
    assert all(request.url.path.startswith("/api/v1/") for request in calls)


def test_frontend_client_maps_structured_errors_without_leaking_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "code": "FORBIDDEN",
                "message": "无权访问该任务。",
                "details": {},
                "correlation_id": "corr-1",
                "retryable": False,
            },
        )

    client = _client(handler)
    with pytest.raises(APIClientError) as caught:
        client.job("job-private")

    assert caught.value.status_code == 403
    assert caught.value.code == "FORBIDDEN"
    assert "frontend-test-token" not in str(caught.value)
    caught.value.__traceback__ = caught.value.__traceback__


def test_view_state_covers_initial_loading_failure_timeout_forbidden_and_stale():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    assert classify_job_view(None).state is ViewState.INITIAL
    assert classify_job_view(None, loading=True).state is ViewState.LOADING
    assert classify_job_view(None, error=APIClientError(403, "FORBIDDEN", "no")).state is ViewState.FORBIDDEN
    assert classify_job_view({"status": "failed"}).state is ViewState.FAILED
    assert classify_job_view({"status": "timed_out"}).state is ViewState.TIMED_OUT
    stale = classify_job_view(
        {
            "status": "running",
            "updated_at": (now - timedelta(minutes=5)).isoformat(),
        },
        now=now,
        stale_after_seconds=60,
    )
    assert stale.state is ViewState.STALE
    assert stale.retryable is True


def test_view_state_preserves_empty_unavailable_and_low_confidence():
    unavailable = classify_job_view(
        None,
        error=APIClientError(
            503,
            "UPSTREAM_CONTRACT_UNAVAILABLE",
            "owner unavailable",
            retryable=True,
        ),
    )
    assert unavailable.state is ViewState.UNAVAILABLE
    assert unavailable.retryable is True
    assert confidence_state(None) is ViewState.EMPTY
    assert confidence_state(0.49) is ViewState.LOW_CONFIDENCE
    assert confidence_state(0.91) is ViewState.SUCCESS


def test_frontend_export_and_feedback_mutations_send_idempotency_keys():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/feedback"):
            return httpx.Response(202, json={"feedback_id": "feedback-1"})
        if request.url.path.endswith("/exports"):
            return httpx.Response(201, json={"job_id": "job-1", "items": []})
        raise AssertionError(request.url.path)

    client = _client(handler)
    client.submit_feedback(
        "job-1",
        target_version_id="v1",
        feedback="请补充证据。",
        idempotency_key="feedback-idempotency",
    )
    client.create_export(
        "job-1",
        formats=["json", "pdf"],
        idempotency_key="export-idempotency",
    )

    assert [request.headers["Idempotency-Key"] for request in calls] == [
        "feedback-idempotency",
        "export-idempotency",
    ]


def test_frontend_initial_state_is_fail_closed_without_api_key(monkeypatch):
    monkeypatch.delenv("SAGE_UI_API_KEY", raising=False)
    app = AppTest.from_file("frontend/streamlit_app.py").run(timeout=10)

    assert not app.exception
    assert any("未配置 SAGE_UI_API_KEY" in item.value for item in app.error)


def test_frontend_rejects_invalid_timeout_configuration(monkeypatch):
    monkeypatch.setenv("SAGE_UI_API_KEY", "frontend-test-token")
    monkeypatch.setenv("SAGE_UI_TIMEOUT_SECONDS", "unbounded")
    app = AppTest.from_file("frontend/streamlit_app.py").run(timeout=10)

    assert not app.exception
    assert any("必须是数字" in item.value for item in app.error)


def test_frontend_client_has_no_filesystem_or_pipeline_fallback():
    source = Path("frontend/api_client.py").read_text(encoding="utf-8")
    assert "pathlib" not in source
    assert "app.workflow" not in source
    assert "read_text(" not in source
