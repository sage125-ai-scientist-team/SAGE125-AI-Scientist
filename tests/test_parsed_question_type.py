"""
tests/test_parsed_question_type.py — ParsedQuestionResult.question_type 契约。

覆盖：Q028 正式类型 narrowed_falsifiable_subproblem 必须通过校验；
未知类型回落到 general_scientific_unknown，避免 question_parser 在第 1 阶段崩溃。
不调用任何真实模型。
"""

from __future__ import annotations

from app.agents.prompts import QUESTION_PARSER_PROMPT
from app.core.agent_schemas import (
    QUESTION_TYPES,
    UNKNOWN_QUESTION_TYPE,
    ParsedQuestionResult,
)
from app.core.schemas import EvidenceCard, PipelineState, QuestionItem
from app.workflow.mock_outputs import build_mock_evidence_cards, parsed_question

Q028 = {
    "id": "Q028",
    "domain": "Biology",
    "question": "Will it be possible to cure all cancers?",
    "source_page": 15,
    "booklet_excerpt": "cancer booklet excerpt",
    "metadata": {"confidence": 0.9},
}

_MINIMAL = {
    "domain": "Biology",
    "core_question": "Can WDBC features classify malignancy?",
    "keywords": ["WDBC"],
    "entities": ["UCI"],
    "scientific_boundary": "classification only",
    "what_not_to_claim": ["cure all cancers"],
}


def test_prompt_allowlist_includes_narrowed_type() -> None:
    """QuestionParser prompt 必须列出 Q028 正式类型，避免模型发明非法标签。"""
    assert "narrowed_falsifiable_subproblem" in QUESTION_PARSER_PROMPT
    for item in QUESTION_TYPES:
        assert item in QUESTION_PARSER_PROMPT


def test_q028_mock_validates_as_narrowed_type() -> None:
    """Q028 mock 包输出必须原样通过 ParsedQuestionResult。"""
    out = parsed_question(Q028)
    result = ParsedQuestionResult(**out)
    assert result.question_type == "narrowed_falsifiable_subproblem"


def test_question_parser_accepts_q028_mock(monkeypatch) -> None:
    """QuestionParserAgent 在 MOCK_LLM 下解析 Q028 不得抛 AgentOutputError。"""
    monkeypatch.setenv("MOCK_LLM", "true")
    from app.agents import QuestionParserAgent

    state = PipelineState(run_id="q028-type", selected_question=QuestionItem(**Q028))
    state.retrieved_evidence = [EvidenceCard(**c) for c in build_mock_evidence_cards(Q028)]
    agent = QuestionParserAgent()
    result = ParsedQuestionResult(**agent.run({"question_item": Q028}, state))
    assert result.question_type == "narrowed_falsifiable_subproblem"


def test_official_types_remain_accepted() -> None:
    """既有官方类型不得被归一化改写。"""
    for item in QUESTION_TYPES:
        result = ParsedQuestionResult(**{**_MINIMAL, "question_type": item})
        assert result.question_type == item


def test_unknown_question_type_coerces_to_unknown() -> None:
    """模型再发明标签时回落，而不是让流水线在 question_parser 失败。"""
    result = ParsedQuestionResult(**{**_MINIMAL, "question_type": "made_up_label"})
    assert result.question_type == UNKNOWN_QUESTION_TYPE


def test_blank_question_type_coerces_to_unknown() -> None:
    """空类型同样回落，避免 literal_error 中断运行。"""
    result = ParsedQuestionResult(**{**_MINIMAL, "question_type": "  "})
    assert result.question_type == UNKNOWN_QUESTION_TYPE
