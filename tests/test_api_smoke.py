"""
tests/test_api_smoke.py — API 接口 smoke（TestClient，无真实 LLM 调用）。

覆盖：/health 不含 Key；/questions 可返回；/diagnostics 可返回；
/runs 列表可返回；无 submission/technical_solution/demo_script 路由。
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health_no_key():
    """/health 返回 200 且不含明文 Key。"""
    r = client.get("/health")
    assert r.status_code == 200
    assert "sk-" not in json.dumps(r.json())
    # 含模型名。
    assert r.json()["models"]["embedding"] == "text-embedding-v4"


def test_questions():
    """/questions 返回 200。"""
    assert client.get("/questions").status_code == 200


def test_diagnostics():
    """/diagnostics 返回含 status 字段且不含 Key。"""
    r = client.get("/diagnostics")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "sk-" not in json.dumps(body)


def test_runs_list():
    """GET /runs 返回 runs 列表。"""
    r = client.get("/runs")
    assert r.status_code == 200
    assert "runs" in r.json()


def test_no_submission_routes():
    """路由表中不含 submission/technical_solution/demo_script 主流程接口。"""
    paths = [route.path for route in app.routes]
    joined = " ".join(paths)
    for token in ("submission", "technical_solution", "demo_script", "bundle"):
        assert token not in joined, f"路由仍含 {token}"
    # 保留核心导出路由。
    assert any("/export/markdown" in p for p in paths)
    assert any("/export/pdf" in p for p in paths)
