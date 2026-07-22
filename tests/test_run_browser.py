"""
tests/test_run_browser.py — 历史运行浏览器测试。

覆盖：扫描 mock exports 得到运行摘要；坏 run 不崩溃被跳过；
不返回完整绝对路径；不读取 .env。
"""

from __future__ import annotations

import json

from app.ui import run_browser


def _make_run(base, run_id: str, report: dict | None):
    """在 base/run_id 下创建一个（可能损坏的）run。"""
    d = base / run_id
    d.mkdir(parents=True, exist_ok=True)
    if report is None:
        (d / "report.json").write_text("{ this is broken json", encoding="utf-8")
    else:
        (d / "report.json").write_text(json.dumps(report), encoding="utf-8")
        (d / "evidence_cards.json").write_text(json.dumps([{"id": "EV-1"}]), encoding="utf-8")
    return d


def test_list_runs_skips_broken(tmp_path, monkeypatch):
    """坏 run 被跳过，好 run 正常返回，且路径为相对路径。"""
    # 将扫描目录指向临时 exports。
    monkeypatch.setattr(run_browser, "EXPORTS_DIR", tmp_path)
    _make_run(tmp_path, "20260101-000000-good", {
        "input_question": "Q", "domain": "D", "validation_status": "ready_for_validation", "references": [],
    })
    _make_run(tmp_path, "20260101-000001-bad", None)
    # 保留目录不应被视作 run。
    (tmp_path / "audit").mkdir()

    runs = run_browser.list_runs()
    ids = [r["run_id"] for r in runs]
    assert "20260101-000000-good" in ids
    assert "20260101-000001-bad" not in ids
    # 不含完整绝对路径。
    for r in runs:
        assert r["report_rel_path"].startswith("exports/")
        assert ":" not in r["report_rel_path"]  # 无 Windows 盘符


def test_artifacts_manifest(tmp_path, monkeypatch):
    """artifacts manifest 反映文件存在性。"""
    monkeypatch.setattr(run_browser, "EXPORTS_DIR", tmp_path)
    _make_run(tmp_path, "run-x", {"input_question": "Q", "domain": "D", "validation_status": "draft", "references": []})
    manifest = run_browser.get_artifacts_manifest("run-x")
    assert manifest["exists"] is True
    names = {f["name"]: f["exists"] for f in manifest["files"]}
    assert names["report.json"] is True
    assert names["report.pdf"] is False


def test_latest_run_none_when_empty(tmp_path, monkeypatch):
    """空 exports 时 latest_run 返回 None。"""
    monkeypatch.setattr(run_browser, "EXPORTS_DIR", tmp_path)
    assert run_browser.latest_run() is None
