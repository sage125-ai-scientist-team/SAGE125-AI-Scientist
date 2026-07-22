# -*- coding: utf-8 -*-
"""tests/test_run_response_contract.py — RunResponse 结构契约。"""

from __future__ import annotations

from app.core.run_response import RunResponse, failed_run_response


def test_run_response_fields():
    """RunResponse 含约定字段。"""
    r = RunResponse(question_id="Q001", mode="real", status="failed", message="test")
    d = r.to_api_dict()
    for key in ("run_id", "question_id", "mode", "status", "plan", "errors", "warnings", "llm_call_summary", "message"):
        assert key in d


def test_failed_run_response_no_plan():
    """失败响应 plan 为 None。"""
    r = failed_run_response("Q001", "real", ["boom"])
    assert r.plan is None
    assert r.status == "failed"


def test_completed_has_plan_field():
    """completed 响应可含 plan。"""
    r = RunResponse(question_id="Q001", mode="mock", status="completed", plan={"question_id": "Q001"})
    assert r.plan is not None
