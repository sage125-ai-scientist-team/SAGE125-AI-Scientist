# -*- coding: utf-8 -*-
"""tests/test_ui_errors_contract.py — app.ui.errors 函数契约与脱敏。"""

from __future__ import annotations

import inspect

from app.ui import errors


def fake_sk_token() -> str:
    """构造只用于 UI 脱敏测试的假 Key。"""
    return "sk-" + ("x" * 32)


def test_errors_module_has_required_functions():
    """errors 模块必须导出全部约定函数。"""
    required = [
        "render_user_error",
        "run_failed",
        "api_disconnected",
        "qwen_not_configured",
        "rag_missing",
        "report_mismatch",
        "render_report_mismatch",
        "missing_artifact",
        "unexpected_error",
        "safe_exception_text",
        "mask_sensitive_text",
    ]
    for name in required:
        assert hasattr(errors, name), f"missing {name}"
        assert callable(getattr(errors, name))


def test_run_failed_callable_no_attribute_error():
    """run_failed 可调用且不抛 AttributeError。"""
    errors.run_failed("test failure", run_id="run-test-001")


def test_api_disconnected_callable():
    """api_disconnected 可调用。"""
    errors.api_disconnected(api_base_url="http://localhost:8000")


def test_qwen_not_configured_callable():
    """qwen_not_configured 可调用。"""
    errors.qwen_not_configured()


def test_mask_sensitive_text_hides_sk_key():
    """mask_sensitive_text 隐藏 sk- 长串。"""
    fake_key = fake_sk_token()
    raw = f"error with {fake_key} token"
    masked = errors.mask_sensitive_text(raw)
    assert fake_key not in masked
    assert "MASKED" in masked or "****" in masked


def test_safe_exception_text_no_dashscope_key():
    """错误详情不泄露 DASHSCOPE_API_KEY 值。"""
    fake_key = fake_sk_token()
    text = errors.safe_exception_text(f"DASHSCOPE_API_KEY={fake_key}")
    assert fake_key not in text
