"""
tests/test_artifacts_manifest.py — artifacts 清单与调用审计文件测试（十一）。

覆盖：mock 运行后 artifacts_manifest.json 与 llm_call_audit.json 存在且字段完整
（run_id / question_id / mode / files / missing_files）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.workflow.pipeline import run_pipeline_with_state

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "true")


def test_artifacts_manifest_written():
    """artifacts_manifest.json 存在且含 run_id/question_id/mode/files。"""
    _, state = run_pipeline_with_state("Q001", mock_mode=True)
    manifest_path = Path(os.environ["SAGE_TEST_EXPORT_DIR"]) / state.run_id / "artifacts_manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == state.run_id
    assert manifest["question_id"] == "Q001"
    assert manifest["mode"] == "mock"
    names = {f["name"] for f in manifest["files"]}
    for expected in ("report.json", "report.md", "evidence_cards.json", "llm_call_audit.json"):
        assert expected in names, f"manifest.files 缺少 {expected}"


def test_llm_call_audit_written_with_summary():
    """llm_call_audit.json 存在且含 summary 与 records。"""
    _, state = run_pipeline_with_state("Q001", mock_mode=True)
    audit_path = Path(os.environ["SAGE_TEST_EXPORT_DIR"]) / state.run_id / "llm_call_audit.json"
    assert audit_path.exists()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert "summary" in audit and "records" in audit
    assert audit["run_mode"] == "mock"
    assert audit["summary"]["mock_call_count"] > 0


def test_run_browser_manifest_lists_files():
    """run_browser.get_artifacts_manifest 返回文件清单。"""
    _, state = run_pipeline_with_state("Q001", mock_mode=True)
    from app.ui.run_browser import get_artifacts_manifest

    manifest = get_artifacts_manifest(state.run_id)
    assert manifest["exists"] is True
    names = {f["name"] for f in manifest["files"]}
    assert "llm_call_audit.json" in names
    assert "artifacts_manifest.json" in names
