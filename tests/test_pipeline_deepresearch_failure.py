"""
tests/test_pipeline_deepresearch_failure.py — DeepResearch 失败容错测试。

覆盖：DeepResearch 被强制失败时 pipeline 不崩溃；state.warnings 含
deep_research_failed；final plan 仍可生成，validation_status 保守（非 validated）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.workflow.pipeline import run_pipeline_with_state

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


def _first_qid() -> str:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))[0]["id"]


def test_deepresearch_failure_does_not_crash(monkeypatch):
    """DeepResearch 失败时 pipeline 继续，warning 记录，状态保守。"""
    monkeypatch.setenv("MOCK_LLM", "true")
    # 强制 DeepResearch 失败。
    monkeypatch.setenv("MOCK_DEEPRESEARCH_FAIL", "true")

    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)
    # pipeline 仍产出计划。
    assert plan is not None
    # warning 记录失败。
    assert "deep_research_failed" in state.warnings
    # 不得为 validated。
    assert plan.validation_status != "validated"
