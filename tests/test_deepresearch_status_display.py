# -*- coding: utf-8 -*-
"""tests/test_deepresearch_status_display.py — DeepResearch 配置与运行状态分离。"""

from __future__ import annotations

import inspect

from app.ui import components


def test_render_system_status_accepts_llm_summary():
    """render_system_status 支持 llm_summary 参数（配置 vs 本次运行）。"""
    sig = inspect.signature(components.render_system_status)
    assert "llm_summary" in sig.parameters


def test_qwen_invocation_summary_mentions_deepresearch_run():
    """render_qwen_invocation_summary 区分 DeepResearch 本次运行。"""
    src = inspect.getsource(components.render_qwen_invocation_summary)
    assert "DeepResearch 本次" in src
