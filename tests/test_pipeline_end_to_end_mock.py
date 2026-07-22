"""
tests/test_pipeline_end_to_end_mock.py — mock 端到端 pipeline 测试。

覆盖：run_pipeline 跑通、生成 ResearchPlan 与全部 artifacts、
validation_status 不为 validated、results 含 pending 句子。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.core.schemas import ResearchPlan
from app.workflow.pipeline import run_pipeline_with_state

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    """启用 MOCK_LLM。"""
    monkeypatch.setenv("MOCK_LLM", "true")


def _first_qid() -> str:
    """取第一个问题 ID。"""
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))[0]["id"]


def test_end_to_end_mock():
    """mock 端到端应生成合规 ResearchPlan 与 artifacts。"""
    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)
    # 类型与关键不变量。
    assert isinstance(plan, ResearchPlan)
    assert plan.validation_status != "validated"
    assert "待执行验证实验" in plan.results

    # artifacts 齐全。
    run_dir = Path(os.environ["SAGE_TEST_EXPORT_DIR"]) / state.run_id
    for name in ["report.json", "evidence_cards.json", "agent_trace.json", "context_pack.json", "quality_gates.json"]:
        assert (run_dir / name).exists(), f"缺少 {name}"
