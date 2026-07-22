"""
tests/test_run_modes.py — 运行模式规则测试（九）。

覆盖：
    - mock 模式不调用真实 Qwen（state.run_mode=mock，qwen_call_count=0）；
    - real 模式（monkeypatch 注入 client）调用 Qwen（qwen_call_count>0）；
    - real 模式失败不 fallback mock（抛错）；
    - PipelineState.run_mode 徽标正确。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.base import AgentOutputError
from app.core.call_audit import summarize_calls
from app.core.schemas import PipelineState, QuestionItem

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"


class _FakeClient:
    """伪造 chat client（成功或失败）。"""

    def __init__(self, fail=False):
        self.fail = fail
        self.last_request_id = "req-xyz987654"
        self.last_usage = {"input_tokens": 5, "output_tokens": 8, "total_tokens": 13}

    def chat_json(self, messages, model, temperature=0.1):
        if self.fail:
            raise RuntimeError("timeout")
        return {
            "domain": "Mathematical Sciences", "core_question": "prime",
            "keywords": ["prime"], "entities": ["e"], "question_type": "theoretical_proof",
            "scientific_boundary": "b", "what_not_to_claim": ["x"],
            "suspected_domain_mismatch": False, "domain_confidence": 0.9,
        }


def _state() -> PipelineState:
    q = QuestionItem(id="Q001", domain="Mathematical Sciences", question="What makes prime numbers so special?")
    return PipelineState(run_id="rm-test", selected_question=q)


@pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")
def test_mock_mode_run_mode_and_no_qwen(monkeypatch):
    """mock 模式：run_mode=mock，无真实 Qwen 调用。"""
    monkeypatch.setenv("MOCK_LLM", "true")
    from app.workflow.pipeline import run_pipeline_with_state

    _, state = run_pipeline_with_state("Q001", mock_mode=True)
    assert state.run_mode == "mock"
    assert summarize_calls(state.llm_calls)["qwen_call_count"] == 0


def test_real_mode_invokes_qwen(monkeypatch):
    """real 模式（注入 client）：记录真实 Qwen 调用。"""
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from app.agents.query_planner import QueryPlannerAgent
    from app.agents.question_parser import QuestionParserAgent

    state = _state()
    QuestionParserAgent(chat_client=_FakeClient()).run(
        {"question_item": state.selected_question.model_dump()}, state, 0
    )
    assert summarize_calls(state.llm_calls)["qwen_call_count"] >= 1


def test_real_mode_failure_raises(monkeypatch):
    """real 模式调用失败：抛错，不静默 fallback mock。"""
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from app.agents.question_parser import QuestionParserAgent

    state = _state()
    with pytest.raises(AgentOutputError):
        QuestionParserAgent(chat_client=_FakeClient(fail=True)).run(
            {"question_item": state.selected_question.model_dump()}, state, 0
        )
