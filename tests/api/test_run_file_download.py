"""Allowlisted run artifact download for preview UI export."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.main import app


def test_run_file_download_serves_existing_allowlisted_file(tmp_path, monkeypatch):
    from app.api import routes

    run_id = "run-export-ok"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    payload = b"# research plan\n"
    (run_dir / "report.md").write_bytes(payload)
    monkeypatch.setattr(routes, "_exports_dir", lambda: tmp_path)

    response = TestClient(app).get(f"/runs/{run_id}/files/report.md")

    assert response.status_code == 200
    assert response.content == payload
    assert "text/markdown" in response.headers.get("content-type", "")


def test_run_file_download_404_when_file_or_run_missing(tmp_path, monkeypatch):
    from app.api import routes

    run_dir = tmp_path / "run-export-partial"
    run_dir.mkdir()
    (run_dir / "report.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(routes, "_exports_dir", lambda: tmp_path)
    client = TestClient(app)

    missing_file = client.get("/runs/run-export-partial/files/report.pdf")
    missing_run = client.get("/runs/run-export-absent/files/report.md")

    assert missing_file.status_code == 404
    assert missing_run.status_code == 404


def test_run_file_download_rejects_unknown_and_path_escape(tmp_path, monkeypatch):
    from app.api import routes

    run_id = "run-export-safe"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "report.md").write_text("# ok\n", encoding="utf-8")
    secret = tmp_path / "secret.env"
    secret.write_text("DASHSCOPE_API_KEY=should-not-leak\n", encoding="utf-8")
    monkeypatch.setattr(routes, "_exports_dir", lambda: tmp_path)
    client = TestClient(app)

    unknown = client.get(f"/runs/{run_id}/files/secret.env")
    escaped = client.get(f"/runs/{run_id}/files/..%2Fsecret.env")
    routed_away = client.get(f"/runs/{run_id}/files/../secret.env")

    assert unknown.status_code == 400
    assert escaped.status_code in {400, 404}
    assert routed_away.status_code in {400, 404}
    assert "should-not-leak" not in unknown.text
    assert "should-not-leak" not in escaped.text
    assert "should-not-leak" not in routed_away.text
    assert "DASHSCOPE_API_KEY" not in unknown.text
    assert "DASHSCOPE_API_KEY" not in escaped.text
    assert "DASHSCOPE_API_KEY" not in routed_away.text

    with pytest.raises(HTTPException) as exc_info:
        routes._safe_export_file(run_id, "../secret.env")
    assert exc_info.value.status_code == 400
