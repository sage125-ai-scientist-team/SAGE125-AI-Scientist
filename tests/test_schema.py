"""
tests/test_schema.py — 数据模型单元测试。

覆盖：
    - QuestionItem / EvidenceCard 基本构造；
    - EvidenceCard DOI 格式校验；
    - ResearchPlan 的 datasets/experiments 结构约束；
    - references 非空规则与 needs_data 例外；
    - PipelineState 构造。
"""

from __future__ import annotations

import pytest

from app.core.schemas import (
    EvidenceCard,
    PipelineState,
    QuestionItem,
    ResearchPlan,
    ScientificHypothesis,
)


def _valid_evidence() -> EvidenceCard:
    """构造一条合法的证据卡片，供多个用例复用。"""
    # 带合法 DOI 与必填字段。
    return EvidenceCard(
        id="ev1",
        source_type="crossref",
        title="示例论文",
        quoted_text="原文片段",
        summary="摘要",
        relevance_score=0.8,
        doi="10.1000/xyz123",
    )


def test_question_item_construction():
    """QuestionItem 应能构造并保留可空字段。"""
    # 仅填必填字段，source_page/booklet_excerpt 允许为空。
    q = QuestionItem(id="Q001", domain="物理", question="宇宙由什么构成？")
    assert q.id == "Q001"
    assert q.source_page is None


def test_evidence_invalid_doi_rejected():
    """非法 DOI 应触发校验错误。"""
    # DOI 不符合 10.xxxx/xxx 格式。
    with pytest.raises(Exception):
        EvidenceCard(
            id="ev",
            source_type="arxiv",
            title="t",
            quoted_text="q",
            summary="s",
            relevance_score=0.5,
            doi="not-a-doi",
        )


def test_research_plan_requires_dataset_keys():
    """datasets 缺少 source/target 时应报错。"""
    # experiments 合法但 datasets 缺 key。
    with pytest.raises(Exception):
        ResearchPlan(
            input_question="Q",
            domain="D",
            problem_statement="P",
            rationale="R",
            datasets={"source": "x"},  # 缺 target
            experiments={"baselines": [], "metrics": []},
            references=[_valid_evidence()],
            validation_status="draft",
        )


def test_research_plan_requires_experiment_keys():
    """experiments 缺少 baselines/metrics 时应报错。"""
    with pytest.raises(Exception):
        ResearchPlan(
            input_question="Q",
            domain="D",
            problem_statement="P",
            rationale="R",
            datasets={"source": "x", "target": "y"},
            experiments={"baselines": []},  # 缺 metrics
            references=[_valid_evidence()],
            validation_status="draft",
        )


def test_research_plan_empty_references_needs_data_ok():
    """needs_data 且 results 标注待检索/待验证时，references 可为空。"""
    # 合法：needs_data + results 含“待检索”。
    plan = ResearchPlan(
        input_question="Q",
        domain="D",
        problem_statement="P",
        rationale="R",
        datasets={"source": "x", "target": "y"},
        experiments={"baselines": [], "metrics": []},
        results="相关证据待检索/待验证。",
        references=[],
        validation_status="needs_data",
    )
    assert plan.validation_status == "needs_data"


def test_research_plan_empty_references_draft_fails():
    """draft 状态下 references 为空应报错。"""
    with pytest.raises(Exception):
        ResearchPlan(
            input_question="Q",
            domain="D",
            problem_statement="P",
            rationale="R",
            datasets={"source": "x", "target": "y"},
            experiments={"baselines": [], "metrics": []},
            references=[],
            validation_status="draft",
        )


def test_pipeline_state_construction():
    """PipelineState 应能构造并保留选中的问题。"""
    q = QuestionItem(id="Q001", domain="生物", question="生命如何起源？")
    state = PipelineState(run_id="run-1", selected_question=q)
    assert state.run_id == "run-1"
    assert state.selected_question.id == "Q001"
    assert state.errors == []


def test_scientific_hypothesis_construction():
    """ScientificHypothesis 必填字段应正确保存。"""
    h = ScientificHypothesis(
        hypothesis="H",
        mechanism="M",
        falsifiable_prediction="P",
        risk_of_being_wrong="R",
    )
    assert h.required_observations == []
