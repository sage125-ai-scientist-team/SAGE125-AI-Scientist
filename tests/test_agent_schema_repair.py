# -*- coding: utf-8 -*-
"""
tests/test_agent_schema_repair.py — BaseAgent schema 聚焦与 repair 行为。
"""

from __future__ import annotations

import pytest

from app.agents.base import AgentOutputError, BaseAgent
from app.core.agent_schemas import ExperimentDesignResult
from app.workflow.mock_outputs import PENDING_RESULTS


class _RepairableAgent(BaseAgent):
    """用于测试 validate_output repair 的最小 Agent。"""

    name = "repair_test"
    output_schema = ExperimentDesignResult

    def build_mock(self, input_data, state):
        return {}


def _valid_exp_dict() -> dict:
    """返回可通过 ExperimentDesignResult 校验的最小 dict。"""
    return {
        "technical_details": "prime distribution analysis",
        "datasets": {"source": "OEIS primes", "target": "gap statistics"},
        "methods": "Monte Carlo gap test",
        "experiments": {
            "baselines": ["uniform random", "Poisson"],
            "metrics": ["KS", "entropy", "autocorr"],
            "ablation": "remove small primes",
            "validation_protocol": "hold-out decade",
        },
        "results": PENDING_RESULTS,
        "reproducibility_checklist": ["seed fixed"],
        "execution_metadata": {"actual_execution": False},
    }


def test_focus_schema_fields_strips_question_item_echo():
    """_focus_schema_fields 应丢弃 question_item 等输入回显键。"""
    agent = _RepairableAgent()
    echoed = {"question_item": {"id": "Q001"}, **_valid_exp_dict()}
    focused = agent._focus_schema_fields(echoed, ExperimentDesignResult)
    assert "question_item" not in focused
    assert focused["technical_details"] == "prime distribution analysis"


def test_validate_output_accepts_focused_fields():
    """完整 schema 字段应直接通过校验。"""
    agent = _RepairableAgent()
    model = agent.validate_output(_valid_exp_dict(), ExperimentDesignResult)
    assert model.technical_details.startswith("prime")


def test_validate_output_repairs_incomplete_json(monkeypatch):
    """真实模式下校验失败应触发一次 LLM repair。"""
    monkeypatch.delenv("MOCK_LLM", raising=False)
    agent = _RepairableAgent()
    incomplete = {"question_item": {"id": "Q001", "question": "test"}}

    def _fake_repair(messages, temperature=0.0, json_mode=True):
        return _valid_exp_dict()

    monkeypatch.setattr(agent, "call_llm", _fake_repair)
    model = agent.validate_output(incomplete, ExperimentDesignResult)
    assert model.methods == "Monte Carlo gap test"


def test_validate_output_raises_when_repair_fails(monkeypatch):
    """repair 仍失败时应抛出 AgentOutputError。"""
    monkeypatch.delenv("MOCK_LLM", raising=False)
    agent = _RepairableAgent()

    def _bad_repair(messages, temperature=0.0, json_mode=True):
        return {"question_item": {"id": "Q001"}}

    monkeypatch.setattr(agent, "call_llm", _bad_repair)
    with pytest.raises(AgentOutputError):
        agent.validate_output({"question_item": {"id": "Q001"}}, ExperimentDesignResult)
