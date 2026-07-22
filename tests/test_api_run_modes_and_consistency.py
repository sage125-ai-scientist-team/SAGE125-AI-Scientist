"""
tests/test_api_run_modes_and_consistency.py — API 运行模式与一致性测试（十）。

覆盖：
    - POST /runs mode=mock：返回 question_id / plan_question_id==Q001 /
      llm_call_summary（qwen=0, mock>0）/ artifacts；
    - POST /runs mode=real 且未配置百炼：返回 400（不 fallback mock）；
    - GET /runs/{run_id}/llm-calls：返回脱敏摘要；
    - GET /runs：条目含 mode 字段；
    - /health 与 /diagnostics 不泄露 Key。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


@pytest.fixture()
def client(monkeypatch):
    """构造 FastAPI TestClient（mock 模式）。"""
    from fastapi.testclient import TestClient

    from app.api.main import app

    return TestClient(app)


def test_post_runs_mock_consistency(client):
    """mock 运行：question_id 一致、无真实 Qwen 调用。"""
    resp = client.post("/runs", json={"question_id": "Q001", "mode": "mock"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["question_id"] == "Q001"
    assert data["plan_question_id"] == "Q001"
    assert data["plan"]["input_question"].lower().find("prime") >= 0
    summary = data["llm_call_summary"]
    assert summary["qwen_call_count"] == 0
    assert summary["mock_call_count"] > 0
    # 响应不含 API Key。
    assert "sk-" not in json.dumps(data, ensure_ascii=False)


def test_post_runs_real_without_key_returns_400(client, monkeypatch):
    """real 模式未配置百炼时应 400，不 fallback mock。"""
    import app.api.routes as routes

    class _Stub:
        qwen_configured = False

    monkeypatch.setattr(routes, "get_settings", lambda: _Stub())
    resp = client.post("/runs", json={"question_id": "Q001", "mode": "real"})
    assert resp.status_code == 400


def test_llm_calls_endpoint(client):
    """/runs/{id}/llm-calls 返回脱敏审计摘要。"""
    run_id = client.post("/runs", json={"question_id": "Q001", "mode": "mock"}).json()["run_id"]
    resp = client.get(f"/runs/{run_id}/llm-calls")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is True
    assert "summary" in data
    assert "sk-" not in json.dumps(data, ensure_ascii=False)


def test_runs_list_has_mode(client):
    """/runs 列表条目含 mode 字段。"""
    client.post("/runs", json={"question_id": "Q001", "mode": "mock"})
    resp = client.get("/runs", params={"limit": 5})
    assert resp.status_code == 200
    runs = resp.json()["runs"]
    assert runs, "应有历史运行"
    assert "mode" in runs[0]
    assert "qwen_call_count" in runs[0]


def test_health_and_diagnostics_no_key_leak(client):
    """/health 与 /diagnostics 不泄露 API Key。"""
    h = client.get("/health")
    d = client.get("/diagnostics")
    assert h.status_code == 200 and d.status_code == 200
    assert "sk-" not in json.dumps(h.json(), ensure_ascii=False)
    assert "sk-" not in json.dumps(d.json(), ensure_ascii=False)
    # diagnostics 含主题与 submission 检查字段。
    assert "theme_config_exists" in d.json()
    assert "no_submission_artifacts" in d.json()
