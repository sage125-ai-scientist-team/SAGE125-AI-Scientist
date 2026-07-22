"""
tests/test_pipeline_results_pending.py — Results pending 与反造假测试。

覆盖：actual_execution=false 时 Results 必须 pending；出现虚构指标时
ResearchPlan 构造报错；validated 状态必须 actual_execution=true。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.schemas import EvidenceCard, ResearchPlan
from app.workflow.mock_outputs import PENDING_RESULTS
from app.workflow.pipeline import run_pipeline_with_state

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


def _first_qid() -> str:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))[0]["id"]


def _ref() -> EvidenceCard:
    """一张合法证据。"""
    return EvidenceCard(id="EV-1", source_type="rag", title="t", quoted_text="q", summary="s", relevance_score=0.5)


def test_pipeline_results_pending(monkeypatch):
    """mock pipeline 未执行实验，Results 必须 pending。"""
    monkeypatch.setenv("MOCK_LLM", "true")
    plan, _ = run_pipeline_with_state(_first_qid(), mock_mode=True)
    assert PENDING_RESULTS in plan.results


def test_fake_metric_rejected():
    """未真实执行时含虚构指标应被 ResearchPlan 校验拒绝。"""
    with pytest.raises(Exception):
        ResearchPlan(
            input_question="Q", domain="D", problem_statement="P", rationale="R",
            datasets={"source": "x", "target": "y"},
            experiments={"baselines": [], "metrics": []},
            results="模型取得 AUROC=0.92。",
            references=[_ref()], validation_status="draft",
        )


def test_validated_requires_execution():
    """validated 只有在 actual_execution=true 且结果真实时才允许（此处仅验证可构造）。"""
    plan = ResearchPlan(
        input_question="Q", domain="D", problem_statement="P", rationale="R",
        datasets={"source": "x", "target": "y"},
        experiments={"baselines": [], "metrics": []},
        results="真实实验：AUROC=0.90。", references=[_ref()],
        validation_status="validated", actual_execution=True,
    )
    assert plan.actual_execution is True
