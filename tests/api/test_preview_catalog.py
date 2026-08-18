"""T08 DATA_DIR preview catalog tests for the Render Wave B questions=0 bug."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.job_store import SQLiteJobStore
from app.api.main import create_app
from app.api.preview_catalog import (
    catalog_is_usable,
    ensure_preview_catalog,
    resolve_runtime_questions_path,
    writable_catalog_path,
    write_preview_catalog,
)
from app.core.config import get_settings


class _NoopRunner:
    """Preview catalog tests must not start the scientific pipeline."""

    def run(self, job, progress_callback):  # pragma: no cover - never queued
        raise AssertionError("preview catalog tests do not run the pipeline")


def _clear_settings() -> None:
    """Drop cached Settings so DATA_DIR changes are visible."""
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_settings_cache():
    """Prevent preview DATA_DIR / ephemeral flags from leaking into later tests."""
    _clear_settings()
    yield
    _clear_settings()


def test_resolve_prefers_explicit_data_dir_even_when_missing(tmp_path, monkeypatch):
    """
    显式 DATA_DIR 必须指向可写区，即使文件尚未生成。

    参数：
        tmp_path: pytest 临时目录。
        monkeypatch: 环境隔离。
    """
    data_root = tmp_path / "render-data"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)
    _clear_settings()

    path = resolve_runtime_questions_path()

    assert path == data_root / "processed" / "questions_125.json"
    assert path == writable_catalog_path()
    assert not path.exists()


def test_write_preview_catalog_marks_seed_and_stays_out_of_repo(tmp_path, monkeypatch):
    """
    Preview seed 必须写入 DATA_DIR，并带 preview_seed 标记。

    参数：
        tmp_path: pytest 临时目录。
        monkeypatch: 环境隔离。
    """
    data_root = tmp_path / "render-data"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)
    _clear_settings()
    target = writable_catalog_path()

    written = write_preview_catalog(target)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert written == target
    assert catalog_is_usable(written)
    assert len(payload) == 125
    assert all(item.get("preview_seed") is True for item in payload)
    assert all(item.get("label_tier") == "preview_seed" for item in payload)
    repo_catalog = Path(__file__).resolve().parents[2] / "data" / "processed" / "questions_125.json"
    if repo_catalog.exists():
        assert written.resolve() != repo_catalog.resolve()


def test_ensure_preview_catalog_is_noop_outside_preview(tmp_path, monkeypatch):
    """
    非 preview 进程不得偷偷写入 seed。

    参数：
        tmp_path: pytest 临时目录。
        monkeypatch: 环境隔离。
    """
    data_root = tmp_path / "dev-data"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.delenv("SAGE125_PREVIEW_SEED", raising=False)
    monkeypatch.delenv("PREVIEW_EPHEMERAL_STORAGE", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)
    _clear_settings()

    result = ensure_preview_catalog()

    assert result is None
    assert not (data_root / "processed" / "questions_125.json").exists()


def test_ensure_preview_catalog_writes_data_dir_and_exports_env(tmp_path, monkeypatch):
    """
    Preview 启动必须把 SAGE_QUESTIONS_PATH 指到 DATA_DIR 文件。

    参数：
        tmp_path: pytest 临时目录。
        monkeypatch: 环境隔离。
    """
    data_root = tmp_path / "preview-data"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_EPHEMERAL_STORAGE", "true")
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)
    _clear_settings()

    result = ensure_preview_catalog()

    assert result == data_root / "processed" / "questions_125.json"
    assert result is not None and result.exists()
    assert Path(os.environ["SAGE_QUESTIONS_PATH"]) == result


def test_health_and_questions_read_data_dir_catalog(tmp_path, monkeypatch):
    """
    /health 与 /questions 必须读 DATA_DIR 题库，而不是只读仓库树。

    参数：
        tmp_path: pytest 临时目录。
        monkeypatch: 环境隔离。
    """
    data_root = tmp_path / "preview-data"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.setenv("PREVIEW_EPHEMERAL_STORAGE", "true")
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)
    _clear_settings()
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    app = create_app(
        job_store=store,
        job_runner=_NoopRunner(),
        auth_policy=HashedAPIKeyAuth({"preview-user": "preview-token-123"}),
        rate_limiter=FixedWindowRateLimiter(limit=10_000, window_seconds=60),
        artifact_root=tmp_path / "artifacts",
    )

    with TestClient(app, headers={"X-API-Key": "preview-token-123"}) as client:
        health = client.get("/health")
        questions = client.get("/questions")
        v1 = client.get("/api/v1/questions", params={"limit": 5})

    assert health.status_code == 200
    assert health.json()["questions_count"] == 125
    assert questions.status_code == 200
    assert questions.json()["count"] == 125
    assert v1.status_code == 200
    assert v1.json()["count"] == 5
    assert v1.json()["total"] == 125
    assert (data_root / "processed" / "questions_125.json").exists()
