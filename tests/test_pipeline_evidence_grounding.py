"""
tests/test_pipeline_evidence_grounding.py — 证据落地测试。

覆盖：ResearchPlan.references 全部来自 EvidenceCards；references 非空时状态
不为 needs_data；mock 证据可追溯。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.workflow.pipeline import run_pipeline_with_state

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "true")


def _first_qid() -> str:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))[0]["id"]


def test_references_from_evidence():
    """references 的 id 必须来自 state.retrieved_evidence。"""
    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)
    evidence_ids = {e.id for e in state.retrieved_evidence}
    for ref in plan.references:
        assert ref.id in evidence_ids
    # 有证据时不应为 needs_data。
    if plan.references:
        assert plan.validation_status in ("draft", "ready_for_validation", "validated")


def test_hypotheses_have_supporting_evidence():
    """候选假设的 supporting_evidence_ids 应可在证据集合中找到。"""
    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)
    evidence_ids = {e.id for e in state.retrieved_evidence}
    hyps = (state.hypothesis_generation or {}).get("hypotheses", [])
    # 至少一个假设的支撑证据全部可追溯。
    assert any(
        h.get("supporting_evidence_ids") and all(eid in evidence_ids for eid in h["supporting_evidence_ids"])
        for h in hyps
    )
