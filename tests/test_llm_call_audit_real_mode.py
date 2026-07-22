# -*- coding: utf-8 -*-
"""tests/test_llm_call_audit_real_mode.py — 真实模式 LLM 审计。"""

from __future__ import annotations

from app.core.call_audit import LLMCallRecord, summarize_calls


def test_real_qwen_calls_counted():
    """monkeypatch 风格 record：real_qwen_calls > 0，mock_calls == 0。"""
    records = [
        LLMCallRecord(agent_name="question_parser", provider="bailian_qwen", mock=False, status="success").finalize().model_dump(),
        LLMCallRecord(agent_name="deep_research", provider="dashscope_deepresearch", mock=False, status="success").finalize().model_dump(),
    ]
    summary = summarize_calls(records)
    assert summary["real_qwen_calls"] >= 2
    assert summary["mock_calls"] == 0
    assert summary["deepresearch_calls"] == 1


def test_audit_summary_no_key():
    """llm_call_audit 摘要不含 sk- Key。"""
    records = [
        LLMCallRecord(agent_name="x", provider="bailian_qwen", mock=False, request_id="chatcmpl-secret123").finalize().model_dump(),
    ]
    summary = summarize_calls(records)
    blob = str(summary)
    assert "secret123" not in blob
