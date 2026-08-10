"""Wave B3 artifact registry, security, and canonical exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api.artifact_registry import ArtifactIntegrityError, SQLiteArtifactRegistry
from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.contracts import JobCreateRequest, JobStatus
from app.api.job_store import SQLiteJobStore
from app.api.main import create_app
from app.export.canonical import CanonicalReport, StaticCanonicalReportSource


FIXTURES = Path(__file__).with_name("fixtures")
OWNER_TOKEN = "owner-test-token"
OTHER_TOKEN = "other-test-token"
OWNER_HEADERS = {"X-API-Key": OWNER_TOKEN}
OTHER_HEADERS = {"X-API-Key": OTHER_TOKEN}


class _NoopRunner:
    def run(self, job, progress_callback):  # pragma: no cover - not executed
        raise AssertionError("artifact tests must not execute the pipeline")


def _report(job_id: str = "job-owner-1") -> CanonicalReport:
    payload = json.loads(
        (FIXTURES / "canonical_report.json").read_text(encoding="utf-8")
    )
    payload["job_id"] = job_id
    return CanonicalReport.model_validate(payload)


def _app(tmp_path, *, rate_limit: int = 100):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    registry = SQLiteArtifactRegistry(
        tmp_path / "artifacts.sqlite3",
        root=tmp_path / "artifact-files",
    )
    auth = HashedAPIKeyAuth(
        {"owner-user": OWNER_TOKEN, "other-user": OTHER_TOKEN}
    )
    limiter = FixedWindowRateLimiter(limit=rate_limit, window_seconds=60)
    report_source = StaticCanonicalReportSource(
        {"run-owner-1": _report()}
    )
    app = create_app(
        job_store=store,
        job_runner=_NoopRunner(),
        auth_policy=auth,
        rate_limiter=limiter,
        artifact_registry=registry,
        canonical_report_source=report_source,
        artifact_root=tmp_path / "artifact-files",
    )
    return app, store, registry


def _job(store: SQLiteJobStore):
    record, _ = store.create_job(
        request=JobCreateRequest(question_id="Q001", mode="real"),
        correlation_id="corr-artifact-1",
        requested_by="owner-user",
    )
    return store.transition(
        record.job_id,
        JobStatus.RUNNING,
        stage="reporting",
        actor="test",
        source="fixture",
        upstream_run_id="run-owner-1",
        increment_attempt=True,
    )


def test_v1_requires_authentication_and_rate_limits_by_actor(tmp_path):
    app, _store, _registry = _app(tmp_path, rate_limit=1)
    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/questions")
        first = client.get("/api/v1/questions", headers=OWNER_HEADERS)
        limited = client.get("/api/v1/questions", headers=OWNER_HEADERS)

    assert unauthorized.status_code == 401
    assert unauthorized.json()["code"] == "AUTHENTICATION_REQUIRED"
    assert first.status_code in {200, 503}
    assert limited.status_code == 429
    assert limited.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert limited.headers["Retry-After"] == "60"

    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["APIKeyHeader"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    assert schema["paths"]["/api/v1/jobs/{job_id}/exports"]["post"][
        "security"
    ] == [{"APIKeyHeader": []}]


def test_v1_rejects_oversized_json_before_parsing(tmp_path):
    app, _store, _registry = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/jobs",
            headers={**OWNER_HEADERS, "Content-Type": "application/json"},
            content=b'{' + b'"padding":"' + b'x' * 70_000 + b'"}',
        )

    assert response.status_code == 413
    assert response.json()["code"] == "REQUEST_BODY_TOO_LARGE"


def test_export_registers_three_consistent_formats_and_safe_downloads(tmp_path):
    app, store, registry = _app(tmp_path)
    with TestClient(app) as client:
        job = _job(store)
        response = client.post(
            f"/api/v1/jobs/{job.job_id}/exports",
            headers={**OWNER_HEADERS, "Idempotency-Key": "export-all-1"},
            json={"formats": ["json", "markdown", "pdf"]},
        )
        listing = client.get(
            f"/api/v1/jobs/{job.job_id}/artifacts",
            headers=OWNER_HEADERS,
        )

        assert response.status_code == 201
        assert listing.status_code == 200
        items = listing.json()["items"]
        assert {item["artifact_type"] for item in items} == {
            "canonical_report_json",
            "canonical_report_markdown",
            "canonical_report_pdf",
        }
        assert all(item["sha256"] and item["size_bytes"] for item in items)
        assert all("/private/" not in json.dumps(item) for item in items)

        bodies = {}
        for item in items:
            downloaded = client.get(item["download_url"], headers=OWNER_HEADERS)
            assert downloaded.status_code == 200
            bodies[item["artifact_type"]] = downloaded.content

        forbidden = client.get(items[0]["download_url"], headers=OTHER_HEADERS)
        assert forbidden.status_code == 403

    json_report = json.loads(bodies["canonical_report_json"])
    markdown = bodies["canonical_report_markdown"].decode("utf-8")
    pdf_path = tmp_path / "downloaded.pdf"
    pdf_path.write_bytes(bodies["canonical_report_pdf"])
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf_path).pages)
    fingerprint = json_report["content_sha256"]
    assert fingerprint in markdown
    assert fingerprint in pdf_text
    assert json_report["truth_status"] == "planned"
    assert json_report["title"] in markdown
    assert json_report["title"] in pdf_text
    assert json_report["evidence"][0]["evidence_id"] in markdown
    assert json_report["evidence"][0]["evidence_id"] in pdf_text
    assert json_report["version_id"] in markdown
    assert json_report["version_id"] in pdf_text
    assert "ACTUAL EXECUTION: NO" in markdown
    assert "ACTUAL EXECUTION: NO" in pdf_text

    registered = registry.list_for_job(job.job_id, actor_id="owner-user")
    assert len(registered) == 3


def test_report_projection_exposes_gate_execution_and_multimodal_without_export(tmp_path):
    app, store, _registry = _app(tmp_path)
    with TestClient(app) as client:
        job = _job(store)
        response = client.get(
            f"/api/v1/jobs/{job.job_id}/report",
            headers=OWNER_HEADERS,
        )
        forbidden = client.get(
            f"/api/v1/jobs/{job.job_id}/report",
            headers=OTHER_HEADERS,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["gates"][0]["gate_id"] == "scientific-truth"
    assert payload["execution"]["actual_execution"] is False
    assert payload["multimodal"][0]["bbox"] == [10.0, 20.0, 200.0, 160.0]
    assert forbidden.status_code == 403


def test_export_is_idempotent_and_registry_detects_tampering(tmp_path):
    app, store, registry = _app(tmp_path)
    with TestClient(app) as client:
        job = _job(store)
        first = client.post(
            f"/api/v1/jobs/{job.job_id}/exports",
            headers={**OWNER_HEADERS, "Idempotency-Key": "same-export"},
            json={"formats": ["json"]},
        )
        second = client.post(
            f"/api/v1/jobs/{job.job_id}/exports",
            headers={**OWNER_HEADERS, "Idempotency-Key": "same-export"},
            json={"formats": ["json"]},
        )
        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["items"][0]["artifact_id"] == second.json()["items"][0]["artifact_id"]

        conflict = client.post(
            f"/api/v1/jobs/{job.job_id}/exports",
            headers={**OWNER_HEADERS, "Idempotency-Key": "same-export"},
            json={"formats": ["pdf"]},
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"

        record = registry.list_for_job(job.job_id, actor_id="owner-user")[0]
        path = registry.resolve_for_download(record.artifact_id, actor_id="owner-user")
        path.write_bytes(b"tampered")
        with pytest.raises(ArtifactIntegrityError):
            registry.resolve_for_download(record.artifact_id, actor_id="owner-user")
        rejected = client.get(
            first.json()["items"][0]["download_url"],
            headers=OWNER_HEADERS,
        )
        assert rejected.status_code == 409
        assert rejected.json()["code"] == "ARTIFACT_INTEGRITY_FAILED"
        assert b"same-export" not in registry.path.read_bytes()


def test_registry_rejects_paths_outside_root(tmp_path):
    registry = SQLiteArtifactRegistry(
        tmp_path / "artifacts.sqlite3",
        root=tmp_path / "safe-root",
    )
    registry.initialize()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact root"):
        registry.register_file(
            artifact_id="artifact-outside",
            job_id="job-1",
            question_id="Q001",
            actor_id="owner-user",
            name="report.json",
            artifact_type="canonical_report_json",
            media_type="application/json",
            truth_status="planned",
            path=outside,
        )
