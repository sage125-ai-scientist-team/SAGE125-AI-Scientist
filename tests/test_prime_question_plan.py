"""
tests/test_prime_question_plan.py — Q001（质数）领域相关 mock 计划测试。

覆盖：Q001 的 mock ResearchPlan 标题含 prime/质数/素数，不含 pandemic/zoonotic/
spillover；domain 为 Mathematical Sciences；technical_details 含 prime/statistics/
factorization/cryptography 中至少两个；results 为 pending。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.workflow import mock_outputs

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


def _q(qid: str) -> dict:
    """按 ID 取问题 dict。"""
    for item in json.loads(QUESTIONS.read_text(encoding="utf-8")):
        if item["id"] == qid:
            return item
    raise AssertionError(f"未找到问题 {qid}")


def test_prime_plan_is_domain_relevant():
    """Q001 mock plan 应是质数/密码学主题，绝不 pandemic。"""
    q = _q("Q001")
    plan = mock_outputs.research_plan(q, mock_outputs.MOCK_EVIDENCE_IDS)
    title = plan["paper_title"].lower()
    assert any(k in title for k in ("prime", "质数", "素数")), f"标题应含质数主题：{plan['paper_title']}"
    forbidden = ("pandemic", "zoonotic", "spillover", "动物源", "外溢")
    blob = json.dumps(plan, ensure_ascii=False).lower()
    for bad in forbidden:
        assert bad.lower() not in blob, f"Q001 计划不应出现 pandemic 主题词：{bad}"


def test_prime_plan_domain_and_details():
    """domain 为数学，technical_details 含至少两个关键术语。"""
    q = _q("Q001")
    plan = mock_outputs.research_plan(q, mock_outputs.MOCK_EVIDENCE_IDS)
    assert plan["domain"] == "Mathematical Sciences"
    td = plan["technical_details"].lower()
    hits = sum(1 for k in ("prime", "statistics", "factoriz", "cryptograph") if k in td)
    assert hits >= 2, f"technical_details 至少含两个关键术语，实际命中 {hits}"


def test_prime_plan_results_pending():
    """results 必须为 pending，不含真实指标数值。"""
    q = _q("Q001")
    plan = mock_outputs.research_plan(q, mock_outputs.MOCK_EVIDENCE_IDS)
    assert "待执行验证实验" in plan["results"]


def test_prime_plan_question_id_bound():
    """mock research_plan 应带 question_id。"""
    q = _q("Q001")
    plan = mock_outputs.research_plan(q, mock_outputs.MOCK_EVIDENCE_IDS)
    assert plan["question_id"] == "Q001"
