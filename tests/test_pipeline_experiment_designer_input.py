# -*- coding: utf-8 -*-
"""
tests/test_pipeline_experiment_designer_input.py — 验证真实模式 Agent 输入上下文完整。

Mock 测试只传 question_item 也能通过（build_mock 会补全字段）；
真实 Qwen 需要 hypothesis + evidence，否则易回显 question_item 导致 Pydantic 校验失败。
"""

from __future__ import annotations

from app.core.schemas import PipelineState, QuestionItem
from app.workflow.mock_outputs import build_mock_evidence_cards
from app.workflow.pipeline import _experiment_designer_input, _reviewer_input

QDICT = {
    "id": "Q001",
    "domain": "Mathematical Sciences",
    "question": "Are the prime numbers scattered randomly?",
    "source_page": 1,
    "booklet_excerpt": "prime excerpt",
    "metadata": {"confidence": 0.9},
}


def _filled_state() -> PipelineState:
    """构造含假设与证据的 PipelineState。"""
    state = PipelineState(run_id="ctx-test", selected_question=QuestionItem(**QDICT))
    state.parsed_question = {"question_type": "theoretical_exploration", "core_question": QDICT["question"]}
    state.evidence_extraction = {"established_facts": [{"fact": "f1", "evidence_ids": ["E1"]}]}
    state.hypothesis_generation = {
        "hypotheses": [
            {
                "hypothesis": "H1",
                "mechanism": "M1",
                "falsifiable_prediction": "P1",
                "required_observations": ["O1"],
                "risk_of_being_wrong": "R1",
                "supporting_evidence_ids": ["E1"],
                "contradicted_by_evidence_ids": [],
                "novelty_score": 0.7,
                "falsifiability_score": 0.8,
                "feasibility_score": 0.6,
                "evidence_support_score": 0.5,
                "overall_score": 0.65,
            }
        ],
        "recommended_hypothesis_index": 0,
        "selection_reason": "best",
        "rejected_directions": [],
    }
    state.experiment_design = {
        "technical_details": "td",
        "datasets": {"source": "s", "target": "t"},
        "methods": "m",
        "experiments": {"baselines": ["b1"], "metrics": ["m1"]},
        "results": "pending",
        "reproducibility_checklist": [],
        "execution_metadata": {"actual_execution": False},
    }
    from app.core.schemas import EvidenceCard

    state.retrieved_evidence = [EvidenceCard(**c) for c in build_mock_evidence_cards(QDICT)]
    return state


def test_experiment_designer_input_includes_hypothesis_and_evidence():
    """ExperimentDesigner 输入必须含 recommended_hypothesis 与 evidence_catalog。"""
    state = _filled_state()
    payload = _experiment_designer_input(state, QDICT)
    assert payload.get("recommended_hypothesis", {}).get("hypothesis") == "H1"
    assert payload.get("evidence_extraction")
    assert len(payload.get("evidence_catalog") or []) >= 1
    assert payload.get("question_type") == "theoretical_exploration"


def test_reviewer_input_includes_experiment_design():
    """ScientificReviewer 输入必须含 experiment_design 与假设上下文。"""
    state = _filled_state()
    payload = _reviewer_input(state, QDICT)
    assert payload.get("experiment_design", {}).get("technical_details") == "td"
    assert payload.get("recommended_hypothesis", {}).get("hypothesis") == "H1"
    assert len(payload.get("evidence_catalog") or []) >= 1


def test_experiment_designer_messages_exclude_question_item():
    """ExperimentDesigner.build_messages 不应把 question_item 发给 LLM。"""
    from app.agents.experiment_designer import ExperimentDesignerAgent

    agent = ExperimentDesignerAgent()
    msgs = agent.build_messages(_experiment_designer_input(_filled_state(), QDICT))
    user_content = msgs[1]["content"]
    assert "question_item" not in user_content
    assert "recommended_hypothesis" in user_content
