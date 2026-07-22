"""
tests/test_question_report_consistency.py — 选题-报告一致性测试（P0-1）。

覆盖：
    - 选择 Q001 运行 mock，plan.input_question 含 prime、question_id==Q001；
    - 标题不含 pandemic / zoonotic / spillover；
    - 不同问题生成不同（领域相关）标题，pandemic 内容不污染 Q001；
    - 前端 state 的选题切换会清空 active run；报告-选题不一致会被判定。
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
    """启用 MOCK_LLM。"""
    monkeypatch.setenv("MOCK_LLM", "true")


def test_q001_plan_is_prime_not_pandemic():
    """Q001 运行结果应属于质数主题，且 question_id 一致。"""
    plan, state = run_pipeline_with_state("Q001", mock_mode=True)
    assert plan.question_id == "Q001"
    assert "prime" in plan.input_question.lower()
    blob = json.dumps(plan.model_dump(), ensure_ascii=False).lower()
    for bad in ("pandemic", "zoonotic", "spillover"):
        assert bad not in blob, f"Q001 报告不应出现 {bad}"


def test_different_questions_yield_different_titles():
    """不同问题应产生不同的领域相关标题（无 pandemic 污染）。"""
    p1, _ = run_pipeline_with_state("Q001", mock_mode=True)
    p2, _ = run_pipeline_with_state("Q002", mock_mode=True)
    assert p1.paper_title != p2.paper_title
    assert p1.question_id == "Q001" and p2.question_id == "Q002"


def test_state_switch_clears_run_and_consistency():
    """前端 state：切题清空 run；一致性判定正确。"""
    from app.ui import state

    class _FakeSession(dict):
        pass

    import app.ui.state as state_mod
    import streamlit as st

    # 用普通 dict 模拟 session_state（避免依赖 streamlit 运行时）。
    fake = _FakeSession()
    original = st.session_state
    try:
        st.session_state = fake  # type: ignore[assignment]
        state.init_state()
        state.select_question("Q001", "What makes prime numbers so special?")
        state.set_run_result({"run_id": "r1", "plan": {"question_id": "Q001"}}, question_id="Q001")
        assert state.is_run_consistent() is True
        # 切换到 Q002 应清空 active run。
        state.select_question("Q002", "Will the Navier-Stokes problem ever be solved?")
        assert state.active_run_id() is None
        # 人为制造不一致：run 属于 Q001，但当前选中 Q002。
        state.set_run_result({"run_id": "r2", "plan": {"question_id": "Q001"}}, question_id="Q001")
        assert state.is_run_consistent() is False
    finally:
        st.session_state = original  # type: ignore[assignment]
