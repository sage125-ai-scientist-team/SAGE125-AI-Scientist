from pathlib import Path

from fastapi.testclient import TestClient

from app.formal125.frozen_demo import (
    OFFICIAL_IDS,
    PUBLIC_RUN_DENIED,
    create_demo_api,
    resolve_rc_root,
    snapshot_secret_hits,
    verify_snapshot,
)


def test_snapshot_has_125_and_no_secrets() -> None:
    root = resolve_rc_root()
    manifest = verify_snapshot(root)
    assert manifest["total"] == 125
    assert list(manifest["question_ids"]) == list(OFFICIAL_IDS)
    assert snapshot_secret_hits(root) == 0


def test_health_questions_and_statuses(monkeypatch: object) -> None:
    monkeypatch.setenv("FORMAL_125_RC_ROOT", str(resolve_rc_root()))
    client = TestClient(create_demo_api())
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["questions_count"] == 125
    assert health["ALLOW_PUBLIC_ACTUAL_RUN"] is False
    questions = client.get("/formal-runs/latest/questions").json()["questions"]
    assert len(questions) == 125
    by_id = {item["question_id"]: item for item in questions}
    assert by_id["Q001"]["status"] == "succeeded"
    assert by_id["Q095"]["status"] == "partial"
    assert by_id["Q012"]["status"] == "blocked"
    latest = client.get("/formal-runs/latest").json()
    assert "逐题独立" not in latest["manual_review_formation"]
    assert "状态映射式人工接受" in latest["manual_review_formation"]


def test_downloads_and_traversal_and_writes(monkeypatch: object) -> None:
    monkeypatch.setenv("FORMAL_125_RC_ROOT", str(resolve_rc_root()))
    client = TestClient(create_demo_api())
    pdf = client.get("/downloads/Q001/result.pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
    md = client.get("/downloads/Q001/result.md")
    assert md.status_code == 200
    js = client.get("/downloads/Q001/result.json")
    assert js.status_code == 200
    assert client.get("/downloads/Q001/../manifest.json").status_code == 404
    denied = client.post("/runs", json={"question_id": "Q001"})
    assert denied.status_code == 403
    assert PUBLIC_RUN_DENIED in denied.json()["message"]
    assert client.post("/experiments/Q028/run").status_code == 403


def test_flagship_and_openapi(monkeypatch: object) -> None:
    monkeypatch.setenv("FORMAL_125_RC_ROOT", str(resolve_rc_root()))
    client = TestClient(create_demo_api())
    flag = client.get("/formal-runs/latest/questions/Q028/flagship").json()
    assert flag["question_id"] == "Q028"
    assert "临床" in flag["disclaimer"]
    ablation = client.get("/formal-runs/latest/ablation").json()
    assert ablation["quality_gain"] is False
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_render_yaml_is_frozen_demo() -> None:
    text = Path("render.yaml").read_text(encoding="utf-8")
    assert "sage125-final-api" in text
    assert "sage125-final-ui" in text
    assert "DASHSCOPE_API_KEY" not in text
    assert "WORKSPACE_ID" not in text
    assert "ALLOW_PUBLIC_ACTUAL_RUN" in text
    assert "release/2026-sage125-final-demo" in text
    assert "127.0.0.1" not in text
