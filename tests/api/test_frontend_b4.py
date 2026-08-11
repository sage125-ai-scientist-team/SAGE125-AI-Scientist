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


def _install_full_contract_stub(monkeypatch) -> None:
    now = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(B4APIClient, "jobs", lambda self, limit=20: {"items": []})
    monkeypatch.setattr(
        B4APIClient,
        "questions",
        lambda self, **filters: {
            "items": [
                {
                    "question_id": "Q001",
                    "domain": "materials science",
                    "question": "How can catalyst stability improve?",
                }
            ],
            "count": 1,
            "total": 1,
            "availability": "available",
        },
    )
    monkeypatch.setattr(
        B4APIClient,
        "job",
        lambda self, job_id: {
            "job_id": job_id,
            "question_id": "Q001",
            "status": "waiting_feedback",
            "stage": "awaiting_feedback",
            "attempt": 1,
            "max_attempts": 2,
            "updated_at": now,
            "retry": {"retryable": False},
            "timeout": {"deadline_at": None},
        },
    )
    monkeypatch.setattr(
        B4APIClient,
        "evidence",
        lambda self, job_id: {
            "job_id": job_id,
            "bundle_id": "bundle-1",
            "truncated": False,
            "items": [
                {
                    "evidence_id": "ev-1",
                    "title": "Catalyst evidence",
                    "quoted_text": "Catalyst A retained activity.",
                    "locator": {"page": 7, "section": "Results"},
                    "authors": ["Owner"],
                    "year": 2026,
                    "verification_status": "valid",
                    "relations": [
                        {
                            "relation": "supports",
                            "confidence": 0.4,
                        }
                    ],
                }
            ],
        },
    )
    versions = [
        {
            "ordinal": 1,
            "version_id": "run-1:v1",
            "parent_version_id": None,
            "validation_status": "needs_revision",
            "stop_reason": None,
            "scores": {"falsifiability": 0.4},
            "reviewer_issues": [
                {
                    "issue_id": "issue-1",
                    "severity": "N/A",
                    "closure_status": "open",
                    "summary": "Add a threshold.",
                }
            ],
        },
        {
            "ordinal": 2,
            "version_id": "run-1:v2",
            "parent_version_id": "run-1:v1",
            "validation_status": "validated",
            "stop_reason": "quality_gate_passed",
            "scores": {"falsifiability": 0.9},
            "reviewer_issues": [],
        },
    ]
    monkeypatch.setattr(
        B4APIClient,
        "versions",
        lambda self, job_id: {"job_id": job_id, "items": versions},
    )
    monkeypatch.setattr(
        B4APIClient,
        "version_diff",
        lambda self, job_id, **kwargs: {
            "job_id": job_id,
            "changes": [{"summary": "Added threshold."}],
            **kwargs,
        },
    )
    monkeypatch.setattr(
        B4APIClient,
        "feedback",
        lambda self, job_id, feedback_id: {
            "feedback_id": feedback_id,
            "status": "accepted",
            "resulting_version_id": "run-1:v2",
        },
    )
    monkeypatch.setattr(
        B4APIClient,
        "report",
        lambda self, job_id: {
            "job_id": job_id,
            "truth_status": "planned",
            "content_sha256": "a" * 64,
            "gates": [
                {
                    "gate_id": "gate-1",
                    "passed": False,
                    "findings": [{"code": "OWNER_WAIT"}],
                }
            ],
            "execution": {
                "availability": "unavailable",
                "status": "planned",
                "actual_execution": False,
                "metrics": [],
                "warnings": ["owner read port unavailable"],
            },
            "multimodal": [
                {
                    "artifact_id": "mm-1",
                    "source": "source-1",
                    "page": 2,
                    "bbox": [0.1, 0.2, 0.3, 0.4],
                    "units": ["K"],
                    "confidence": 0.5,
                    "validation_status": "needs_review",
                }
            ],
        },
    )
    monkeypatch.setattr(
        B4APIClient,
        "artifacts",
        lambda self, job_id: {
            "job_id": job_id,
            "items": [
                {
                    "artifact_id": "artifact-1",
                    "name": "report.json",
                    "artifact_type": "report",
                    "truth_status": "planned",
                    "size_bytes": 128,
                    "sha256": "b" * 64,
                }
            ],
        },
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


def test_frontend_contract_stub_renders_every_closed_loop_panel(monkeypatch):
    monkeypatch.setenv("SAGE_UI_API_KEY", "frontend-test-token")
    _install_full_contract_stub(monkeypatch)
    app = AppTest.from_file("frontend/streamlit_app.py")
    app.query_params["job_id"] = "job-1"
    app.query_params["feedback_id"] = "feedback-1"

    app.run(timeout=10)
    assert not app.exception
    assert any("低置信度证据" in item.value for item in app.warning)
    assert any("Catalyst A retained activity" in item.value for item in app.markdown)

    app.radio[0].set_value("Reviewer · 版本 · Diff").run(timeout=10)
    assert not app.exception
    assert any("run-1:v2" in item.value for item in app.markdown)
    assert any("issue-1" in item.value for item in app.markdown)

    app.radio[0].set_value("反馈 · 决策 · 新版本").run(timeout=10)
    assert not app.exception
    assert any("新版本：run-1:v2" in item.value for item in app.success)

    app.radio[0].set_value("Gate · 执行 · 多模态").run(timeout=10)
    assert not app.exception
    assert any("gate-1: blocked" in item.value for item in app.error)
    assert any("NOT ACTUAL" in item.value for item in app.markdown)
    assert any("mm-1: 低置信度" in item.value for item in app.warning)

    app.radio[0].set_value("导出").run(timeout=10)
    assert not app.exception
    assert any("report.json" in str(item.value) for item in app.markdown)


def test_frontend_client_has_no_filesystem_or_pipeline_fallback():
    source = Path("frontend/api_client.py").read_text(encoding="utf-8")
    assert "pathlib" not in source
    assert "app.workflow" not in source
    assert "read_text(" not in source
