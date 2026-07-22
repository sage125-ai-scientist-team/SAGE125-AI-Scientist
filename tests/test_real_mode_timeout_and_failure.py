# -*- coding: utf-8 -*-
"""tests/test_real_mode_timeout_and_failure.py — 真实模式 timeout 与失败策略。"""

from __future__ import annotations

from unittest.mock import patch

from app.ui import api_client


def test_api_client_real_timeout_at_least_900():
    """real mode HTTP timeout >= 900。"""
    assert api_client._run_timeout_seconds("real", use_deep_research=False) >= 900


def test_api_client_deepresearch_timeout_at_least_1200():
    """DeepResearch enabled timeout >= 1200。"""
    assert api_client._run_timeout_seconds("real", use_deep_research=True) >= 1200


def test_mock_timeout_120():
    """mock mode timeout 为 120。"""
    assert api_client._run_timeout_seconds("mock") == 120


def test_real_qwen_failure_no_mock_fallback(monkeypatch):
    """real mode Qwen 失败不 fallback mock。"""
    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.setenv("FRONTEND_RUN_VIA_API", "0")
    monkeypatch.setattr(
        api_client,
        "run_preflight",
        lambda *a, **k: {"ok": True, "errors": [], "warnings": [], "fix_commands": []},
    )

    def _boom(**kwargs):
        raise RuntimeError("qwen chat failed")

    with patch("app.workflow.pipeline.run_pipeline_with_state", side_effect=_boom):
        result = api_client.start_run("Q001", "", {"use_local_rag": False, "use_deep_research": False}, mode="real")
    assert result.get("status") == "failed"
    assert result.get("mode") == "real" or result.get("mock") is False


def test_timeout_error_type():
    """超时错误标记 read_timeout。"""
    with patch.object(api_client, "api_available", return_value=True):
        with patch.object(api_client, "_prefer_inprocess_run", return_value=False):
            with patch.object(api_client, "recover_run_after_timeout", return_value=None):
                with patch("requests.post", side_effect=api_client.requests.exceptions.ReadTimeout()):
                    result = api_client.start_run(
                        "Q001", "", {"use_local_rag": False, "use_deep_research": False}, mode="real"
                    )
    assert result.get("error_type") == "read_timeout"
