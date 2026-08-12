"""Wave B1 owner-contract read ports and API projections."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient as FastAPITestClient

from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.contracts import JobCreateRequest, JobStatus
from app.api.job_store import SQLiteJobStore
from app.api.main import create_app
from app.api.upstream import FixtureOwnerContractAdapter, OwnerIdentityMismatch


FIXTURES = Path(__file__).with_name("fixtures")
TEST_ACTOR = "test-user"
TEST_TOKEN = "test-api-token-123"


class _NoopRunner:
    def run(self, job, progress_callback):  # pragma: no cover - queue is not used
        raise AssertionError("read model tests must not execute the pipeline")


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _adapter() -> FixtureOwnerContractAdapter:
    return FixtureOwnerContractAdapter.from_payloads(
        questions=_load("question_items.json"),
        evidence_by_identity={
            ("run-owner-1", "Q001"): _load("evidence_bundle.json")
        },
        versions_by_identity={
            ("run-owner-1", "Q001"): _load("plan_versions.json")
        },
        diffs_by_identity={
            (
                "run-owner-1",
                "Q001",
                "run-owner-1:v1",
                "run-owner-1:v2",
            ): _load("version_diff.json")
        },
    )


def _client(tmp_path, adapter=None):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    app = create_app(
        job_store=store,
        job_runner=_NoopRunner(),
        upstream_read_port=adapter or _adapter(),
        auth_policy=HashedAPIKeyAuth({TEST_ACTOR: TEST_TOKEN}),
        rate_limiter=FixedWindowRateLimiter(limit=10_000, window_seconds=60),
    )
    return FastAPITestClient(app, headers={"X-API-Key": TEST_TOKEN}), store


def _job(
    store: SQLiteJobStore,
    *,
    upstream_run_id: str | None = "run-owner-1",
    question_id: str = "Q001",
):
    record, _ = store.create_job(
        request=JobCreateRequest(question_id=question_id, mode="real"),
        correlation_id="corr-read-1",
        requested_by=TEST_ACTOR,
    )
    if upstream_run_id:
        record = store.transition(
            record.job_id,
            JobStatus.RUNNING,
            stage="research",
            actor="test",
            source="fixture",
            upstream_run_id=upstream_run_id,
            increment_attempt=True,
        )
    return record


def test_owner_contract_fixtures_validate_at_adapter_boundary():
    adapter = _adapter()

    assert [record.item.id for record in adapter.list_questions()] == ["Q001", "Q002"]
    assert adapter.get_evidence_bundle(
        run_id="run-owner-1", question_id="Q001"
    ).evidences[0].locator == {
        "page": 7,
        "section": "Results",
    }
    versions = adapter.list_plan_versions(
        run_id="run-owner-1",
        question_id="Q001",
    )
    assert [item.version_id for item in versions] == [
        "run-owner-1:v1",
        "run-owner-1:v2",
    ]


def test_question_adapter_rejects_conflicting_owner_identity():
    question = _load("question_items.json")[0]
    question["question_id"] = "Q999"

    with pytest.raises(ValueError, match="question_id does not match"):
        FixtureOwnerContractAdapter.from_payloads(
            questions=[question],
            evidence_by_identity={},
            versions_by_identity={},
            diffs_by_identity={},
        )


def test_evidence_adapter_rejects_cross_question_identity():
    adapter = _adapter()

    with pytest.raises(OwnerIdentityMismatch, match="T01 EvidenceBundle"):
        adapter.get_evidence_bundle(run_id="run-owner-1", question_id="Q002")


def test_t02_adapter_rejects_cross_question_identity():
    adapter = _adapter()

    with pytest.raises(
        OwnerIdentityMismatch,
        match="T02 PlanVersion/IssueClosure",
    ):
        adapter.list_plan_versions(
            run_id="run-owner-1",
            question_id="Q002",
        )
    with pytest.raises(
        OwnerIdentityMismatch,
        match="T02 structured version diff",
    ):
        adapter.get_version_diff(
            run_id="run-owner-1",
            question_id="Q002",
            from_version_id="run-owner-1:v1",
            to_version_id="run-owner-1:v2",
        )


def test_questions_read_api_supports_owner_fields_and_filters(tmp_path):
    client, _store = _client(tmp_path)
    with client:
        response = client.get(
            "/api/v1/questions",
            params={"domain": "materials science", "limit": 1},
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "question_id": "Q001",
                "domain": "materials science",
                "question": "How can a stable catalyst be designed for reaction X?",
                "source_page": 12,
                "source_excerpt": "Design a stable catalyst for reaction X.",
                "status": "unavailable",
                "status_reason": "T07 question status was not supplied.",
            }
        ],
        "count": 1,
        "total": 1,
        "availability": "partial",
    }


def test_evidence_api_preserves_quote_locator_relation_and_provenance(tmp_path):
    client, store = _client(tmp_path)
    with client:
        job = _job(store)
        response = client.get(f"/api/v1/jobs/{job.job_id}/evidence")

    assert response.status_code == 200
    body = response.json()
    assert body["bundle_id"] == "bundle-run-owner-1"
    assert body["availability"] == "available"
    assert body["items"][0]["quoted_text"].startswith("Catalyst A")
    assert body["items"][0]["locator"] == {"page": 7, "section": "Results"}
    assert body["items"][0]["content_hash"] == "sha256:owner-evidence-001"
    assert body["items"][0]["relations"] == [
        {
            "claim_id": "claim-001",
            "relation": "supports",
            "confidence": 0.91,
            "validation_status": "valid",
        }
    ]


def test_evidence_api_fails_closed_on_cross_question_identity(tmp_path):
    client, store = _client(tmp_path)
    with client:
        job = _job(store, question_id="Q002")
        response = client.get(f"/api/v1/jobs/{job.job_id}/evidence")

    assert response.status_code == 409
    assert response.json()["code"] == "UPSTREAM_IDENTITY_MISMATCH"
    assert response.json()["retryable"] is False


def test_versions_and_owner_supplied_diff_are_projected_without_inference(tmp_path):
    client, store = _client(tmp_path)
    with client:
        job = _job(store)
        versions = client.get(f"/api/v1/jobs/{job.job_id}/versions")
        diff = client.get(
            f"/api/v1/jobs/{job.job_id}/versions/diff",
            params={
                "from_version_id": "run-owner-1:v1",
                "to_version_id": "run-owner-1:v2",
            },
        )

    assert versions.status_code == 200
    assert versions.json()["items"][1]["parent_version_id"] == "run-owner-1:v1"
    assert versions.json()["items"][1]["reviewer_issues"][0]["closure_status"] == "resolved"
    assert versions.json()["items"][1]["scores"]["falsifiability"] == 0.9
    assert diff.status_code == 200
    assert diff.json()["changes"][0]["summary"] == "Added falsification threshold 0.2."
    assert diff.json()["stop_reason"] == "quality_gate_passed"


def test_versions_and_diff_fail_closed_on_cross_question_identity(tmp_path):
    client, store = _client(tmp_path)
    with client:
        job = _job(store, question_id="Q002")
        versions = client.get(f"/api/v1/jobs/{job.job_id}/versions")
        diff = client.get(
            f"/api/v1/jobs/{job.job_id}/versions/diff",
            params={
                "from_version_id": "run-owner-1:v1",
                "to_version_id": "run-owner-1:v2",
            },
        )

    assert versions.status_code == 409
    assert versions.json()["code"] == "UPSTREAM_IDENTITY_MISMATCH"
    assert diff.status_code == 409
    assert diff.json()["code"] == "UPSTREAM_IDENTITY_MISMATCH"


def test_diff_rejects_owner_payload_with_conflicting_question_identity(tmp_path):
    payload = _load("version_diff.json")
    payload["question_id"] = "Q002"
    adapter = FixtureOwnerContractAdapter.from_payloads(
        questions=_load("question_items.json"),
        evidence_by_identity={},
        versions_by_identity={},
        diffs_by_identity={
            (
                "run-owner-1",
                "Q001",
                "run-owner-1:v1",
                "run-owner-1:v2",
            ): payload
        },
    )
    client, store = _client(tmp_path, adapter=adapter)
    with client:
        job = _job(store)
        response = client.get(
            f"/api/v1/jobs/{job.job_id}/versions/diff",
            params={
                "from_version_id": "run-owner-1:v1",
                "to_version_id": "run-owner-1:v2",
            },
        )

    assert response.status_code == 409
    assert response.json()["code"] == "UPSTREAM_IDENTITY_MISMATCH"
    assert response.json()["retryable"] is False


def test_owner_read_requires_bound_upstream_run(tmp_path):
    client, store = _client(tmp_path)
    with client:
        job = _job(store, upstream_run_id=None)
        response = client.get(f"/api/v1/jobs/{job.job_id}/evidence")

    assert response.status_code == 409
    assert response.json()["code"] == "UPSTREAM_RESULT_NOT_READY"
    assert response.json()["retryable"] is True


def test_job_store_migrates_retry_timeout_columns_and_status_exposes_metadata(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                question_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                attempt INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL,
                idempotency_key_hash TEXT UNIQUE,
                request_hash TEXT NOT NULL,
                request_json TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                upstream_run_id TEXT,
                error_code TEXT,
                error_message TEXT,
                retryable INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    store = SQLiteJobStore(db_path)
    store.initialize()
    with sqlite3.connect(db_path) as connection:
        legacy_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        migrations = connection.execute(
            "SELECT version FROM api_schema_migrations ORDER BY version"
        ).fetchall()

    assert {
        "last_attempt_at",
        "next_retry_at",
        "retry_backoff_seconds",
        "timeout_seconds",
        "deadline_at",
        "timed_out_at",
    } <= legacy_columns
    assert migrations == [(2,)]

    client, store = _client(tmp_path / "api")
    with client:
        job = _job(store)
        response = client.get(f"/api/v1/jobs/{job.job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["retry"] == {
        "attempt": 1,
        "max_attempts": 1,
        "retryable": False,
        "last_attempt_at": body["retry"]["last_attempt_at"],
        "next_retry_at": None,
        "backoff_seconds": None,
    }
    assert body["retry"]["last_attempt_at"] is not None
    assert body["timeout"]["timeout_seconds"] is not None
    assert body["timeout"]["deadline_at"] is not None
    assert body["timeout"]["timed_out_at"] is None


def test_status_exposes_retry_schedule_and_timeout_timestamp(tmp_path):
    client, store = _client(tmp_path)
    with client:
        record, _ = store.create_job(
            request=JobCreateRequest(question_id="Q001", mode="mock"),
            correlation_id="corr-retry-timeout",
            requested_by=TEST_ACTOR,
        )
        record = store.transition(
            record.job_id,
            JobStatus.RUNNING,
            actor="test",
            source="fixture",
            increment_attempt=True,
        )
        record = store.transition(
            record.job_id,
            JobStatus.RETRYING,
            actor="test",
            source="fixture",
            error_code="TEMPORARY_UPSTREAM_FAILURE",
            error_message="temporary failure",
            retryable=True,
        )
        retrying = client.get(f"/api/v1/jobs/{record.job_id}").json()
        assert retrying["retry"]["retryable"] is True
        assert retrying["retry"]["backoff_seconds"] == 0
        assert retrying["retry"]["next_retry_at"] is not None

        store.transition(
            record.job_id,
            JobStatus.RUNNING,
            actor="test",
            source="fixture",
            increment_attempt=True,
        )
        store.transition(
            record.job_id,
            JobStatus.TIMED_OUT,
            actor="test",
            source="fixture",
            error_code="JOB_TIMEOUT",
            error_message="deadline exceeded",
            retryable=False,
        )
        timed_out = client.get(f"/api/v1/jobs/{record.job_id}").json()

    assert timed_out["status"] == "timed_out"
    assert timed_out["timeout"]["timed_out_at"] is not None
    assert timed_out["retry"]["next_retry_at"] is None
