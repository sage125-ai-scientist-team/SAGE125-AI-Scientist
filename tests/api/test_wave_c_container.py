"""Wave C container contract and persistent health dependency tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.job_store import SQLiteJobStore
from app.api.main import create_app


ROOT = Path(__file__).resolve().parents[2]


class _NoopRunner:
    """Keep health tests independent of the scientific workflow."""

    def run(self, job, progress_callback):  # pragma: no cover - never queued
        raise AssertionError("health tests do not run jobs")


def test_dockerfile_uses_allowlisted_copy_and_non_root_runtime() -> None:
    """Keep secrets and repository-local state out of the runtime image."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    instructions = "\n".join(
        line
        for line in dockerfile.splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "FROM python:3.12-slim-bookworm" in dockerfile
    assert "COPY requirements.txt ./requirements.txt" in dockerfile
    assert "COPY --chown=10001:10001 app ./app" in dockerfile
    assert "COPY --chown=10001:10001 scripts ./scripts" in dockerfile
    # frontend/ 已删除；正式 Streamlit 入口迁移至 app/ui/streamlit_app.py，
    # 随 `COPY app ./app` 一起进入镜像，不再需要单独的 frontend COPY 指令。
    assert "COPY --chown=10001:10001 frontend ./frontend" not in dockerfile
    assert "COPY . " not in instructions
    assert "COPY .\n" not in instructions
    assert "USER 10001:10001" in dockerfile
    assert ".env" not in instructions
    assert "DASHSCOPE_API_KEY" not in instructions
    assert "SAGE_API_KEYS_JSON" not in instructions


def test_dockerignore_denies_everything_except_runtime_allowlist() -> None:
    """Ensure .env is excluded from the build context, not merely uncopied."""
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    lines = {
        line.strip()
        for line in dockerignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "**" in lines
    assert "!Dockerfile" in lines
    assert "!requirements.txt" in lines
    assert "!app/**" in lines
    assert "!frontend/**" in lines
    assert "!scripts/**" in lines
    assert not any(line.startswith("!.env") for line in lines)
    assert not any(line.startswith("!data") for line in lines)
    assert not any(line.startswith("!exports") for line in lines)
    assert not any(line.startswith("!tests") for line in lines)


def test_compose_binds_persistent_stores_and_hardened_b4_services() -> None:
    """Require persistent API state and the API-only Streamlit entrypoint."""
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    # 正式 Streamlit 入口已从 frontend/streamlit_app.py 迁移至
    # app/ui/streamlit_app.py（科学首页 + 工作区导航），frontend/ 已删除。
    assert "app/ui/streamlit_app.py" in compose
    assert "frontend/streamlit_app.py" not in compose
    assert 'user: "10001:10001"' in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose and "- ALL" in compose
    assert "condition: service_healthy" in compose
    assert "/var/lib/sage125/exports" in compose
    assert "/opt/sage125/data" in compose
    assert "/var/lib/sage125/multimodal" in compose
    assert "sage125-exports:" in compose
    assert "sage125-data:" in compose
    assert "sage125-multimodal:" in compose
    assert 'body.get("status") == "ok"' in compose
    assert '"job_store", "artifact_registry", "artifact_storage"' in compose
    assert "/_stcore/health" in compose
    assert "env_file:" not in compose
    assert "local-demo-key-change-me" in compose
    assert "local-isolation-key-change-me" in compose


def test_health_probes_real_job_and_artifact_storage(
    tmp_path,
    monkeypatch,
) -> None:
    """Report available only after both SQLite and artifact roots are usable."""
    from app.api import routes

    monkeypatch.setattr(routes, "_questions_count", lambda: 125)
    monkeypatch.setattr(routes, "_rag_index_status", lambda: "ready")
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    application = create_app(
        job_store=store,
        job_runner=_NoopRunner(),
        auth_policy=HashedAPIKeyAuth(
            {"health-user": "health-test-token"}
        ),
        rate_limiter=FixedWindowRateLimiter(
            limit=100,
            window_seconds=60,
        ),
        artifact_root=tmp_path / "artifacts",
    )

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["storage"]["persistent"] is True
    assert body["dependencies"] == {
        "job_store": "available",
        "artifact_registry": "available",
        "artifact_storage": "available",
    }
