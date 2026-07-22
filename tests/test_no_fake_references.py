"""
tests/test_no_fake_references.py — 反造假与仅千问约束测试。

覆盖：
    1. assert_qwen_model 拒绝非千问模型、放行千问与向量/重排序白名单；
    2. 未真实执行时，results 中的虚构量化指标应被拦截；
    3. 无来源标识的证据（无 DOI/URL）仍可构造，但可通过字段审计。
"""

from __future__ import annotations

import pytest

from app.core.config import assert_qwen_model
from app.core.schemas import EvidenceCard, ResearchPlan

# 明确应被拒绝的非千问生成模型样本。
FORBIDDEN_MODELS = [
    "gpt-4o",
    "o3-mini",
    "claude-3.5-sonnet",
    "gemini-1.5-pro",
    "deepseek-chat",
    "kimi-k2",
    "glm-4",
    "minimax-abab",
]


def test_forbidden_models_rejected():
    """所有非千问生成模型样本均应抛出 ValueError。"""
    for model in FORBIDDEN_MODELS:
        with pytest.raises(ValueError):
            assert_qwen_model(model)


def test_qwen_and_whitelist_allowed():
    """千问模型与向量/重排序白名单应被放行。"""
    # 千问生成/深度研究模型。
    assert assert_qwen_model("qwen3.7-max") == "qwen3.7-max"
    assert assert_qwen_model("qwen-deep-research") == "qwen-deep-research"
    # 向量与重排序白名单。
    assert assert_qwen_model("text-embedding-v4") == "text-embedding-v4"
    assert assert_qwen_model("qwen3-rerank") == "qwen3-rerank"


def _valid_reference() -> EvidenceCard:
    """构造一条合法引用，供研究计划用例复用。"""
    return EvidenceCard(
        id="ev1",
        source_type="crossref",
        title="示例",
        quoted_text="片段",
        summary="摘要",
        relevance_score=0.7,
        doi="10.1000/abc999",
    )


def test_fake_metric_blocked_without_execution():
    """未标注 actual_execution 时，results 含虚构指标应被拦截。"""
    # results 出现 AUROC=0.92，而 actual_execution 默认 False。
    with pytest.raises(ValueError):
        ResearchPlan(
            input_question="Q",
            domain="D",
            problem_statement="P",
            rationale="R",
            datasets={"source": "x", "target": "y"},
            experiments={"baselines": [], "metrics": ["AUROC"]},
            results="模型取得 AUROC=0.92 的优异表现。",
            references=[_valid_reference()],
            validation_status="draft",
        )


def test_fake_metric_allowed_with_execution():
    """当 actual_execution=True 时，results 允许出现真实实验指标。"""
    # 真实执行后允许写具体数值。
    plan = ResearchPlan(
        input_question="Q",
        domain="D",
        problem_statement="P",
        rationale="R",
        datasets={"source": "x", "target": "y"},
        experiments={"baselines": [], "metrics": ["AUROC"]},
        results="真实实验中 AUROC=0.92。",
        references=[_valid_reference()],
        validation_status="validated",
        actual_execution=True,
    )
    assert plan.actual_execution is True
