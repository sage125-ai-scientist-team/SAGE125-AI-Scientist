"""
tests/test_agents_mock.py — 各 Agent 在 MOCK_LLM 下的单元测试。

覆盖：每个 Agent 单独 run 输出符合对应 Pydantic schema；模型均为千问；
不泄露 API Key。
"""

from __future__ import annotations

import pytest

from app.core.agent_schemas import (
    EvidenceExtractionResult,
    ExperimentDesignResult,
    HypothesisGenerationResult,
    ParsedQuestionResult,
    QueryPlanResult,
    ReviewResult,
    ValidationResult,
)
from app.core.config import assert_qwen_model
from app.core.schemas import EvidenceCard, PipelineState, QuestionItem
from app.workflow.mock_outputs import build_mock_evidence_cards

# 演示问题 dict。
QDICT = {
    "id": "Q001", "domain": "Medicine & Health", "question": "Can we predict the next pandemic?",
    "source_page": 10, "booklet_excerpt": "pandemic prediction excerpt", "metadata": {"confidence": 0.9},
}


def _state() -> PipelineState:
    """构造带 mock 证据的 PipelineState。"""
    state = PipelineState(run_id="test-run", selected_question=QuestionItem(**QDICT))
    state.retrieved_evidence = [EvidenceCard(**c) for c in build_mock_evidence_cards(QDICT)]
    return state


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    """所有用例默认启用 MOCK_LLM。"""
    monkeypatch.setenv("MOCK_LLM", "true")


def test_question_parser():
    """QuestionParser 输出符合 ParsedQuestionResult，模型为快速千问。"""
    from app.agents import QuestionParserAgent

    agent = QuestionParserAgent()
    assert agent.model_name.startswith("qwen")
    out = agent.run({"question_item": QDICT}, _state())
    ParsedQuestionResult(**out)  # 不抛异常即合规


def test_query_planner():
    """QueryPlanner 输出符合 QueryPlanResult。"""
    from app.agents import QueryPlannerAgent

    out = QueryPlannerAgent().run({"question_item": QDICT}, _state())
    result = QueryPlanResult(**out)
    assert len(result.queries) >= 3


def test_evidence_extractor():
    """EvidenceExtractor 输出符合 schema，且事实绑定 evidence_ids。"""
    from app.agents import EvidenceExtractorAgent

    state = _state()
    out = EvidenceExtractorAgent().run({"question_item": QDICT}, state)
    result = EvidenceExtractionResult(**out)
    # established_facts 每条必须有 evidence_ids。
    for f in result.established_facts:
        assert f.evidence_ids


def test_hypothesis_generator():
    """HypothesisGenerator 输出 2-3 个候选。"""
    from app.agents import HypothesisGeneratorAgent

    out = HypothesisGeneratorAgent().run({"question_item": QDICT}, _state())
    result = HypothesisGenerationResult(**out)
    assert 2 <= len(result.hypotheses) <= 3


def test_experiment_designer_pending():
    """ExperimentDesigner 未执行时 Results 为 pending，含 source/target 与 baselines/metrics。"""
    from app.agents import ExperimentDesignerAgent

    out = ExperimentDesignerAgent().run({"question_item": QDICT}, _state())
    result = ExperimentDesignResult(**out)
    assert "source" in result.datasets and "target" in result.datasets
    assert "baselines" in result.experiments and "metrics" in result.experiments
    assert result.execution_metadata.get("actual_execution") is False
    assert "待执行验证实验" in result.results


def test_reviewer_and_validator():
    """Reviewer / Validator 输出符合各自 schema。"""
    from app.agents import SchemaValidatorAgent, ScientificReviewerAgent

    ReviewResult(**ScientificReviewerAgent().run({"question_item": QDICT}, _state()))
    ValidationResult(**SchemaValidatorAgent().run({"question_item": QDICT}, _state()))


def test_all_agent_models_are_qwen():
    """所有 Agent 的模型名均为千问。"""
    from app.agents import (
        DeepResearchAgent, EvidenceExtractorAgent, ExperimentDesignerAgent,
        HypothesisGeneratorAgent, QueryPlannerAgent, QuestionParserAgent,
        ReportWriterAgent, SchemaValidatorAgent, ScientificReviewerAgent, SupervisorAgent,
    )
    agents = [
        QuestionParserAgent(), QueryPlannerAgent(), EvidenceExtractorAgent(),
        HypothesisGeneratorAgent(), ExperimentDesignerAgent(), ScientificReviewerAgent(),
        ReportWriterAgent(), SchemaValidatorAgent(), DeepResearchAgent(), SupervisorAgent(),
    ]
    for a in agents:
        # 每个模型名都必须通过千问校验。
        assert assert_qwen_model(a.model_name) == a.model_name
