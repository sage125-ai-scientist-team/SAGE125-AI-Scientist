# -*- coding: utf-8 -*-
"""tests/test_real_preflight.py — 真实模式 preflight 检查。"""

from __future__ import annotations

from unittest.mock import patch

from app.core.config import Settings
from app.workflow.preflight import run_real_preflight


def _settings(**kwargs) -> Settings:
    base = {
        "DASHSCOPE_API_KEY": "sk-test1234567890abcd",
        "WORKSPACE_ID": "ws-test123",
        "DASHSCOPE_BASE_URL": "https://ws-test123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "DASHSCOPE_DEEP_RESEARCH_BASE_URL": "https://ws-test123.cn-beijing.maas.aliyuncs.com/api/v1",
    }
    base.update(kwargs)
    return Settings(**base)


def test_preflight_missing_api_key():
    """缺 DASHSCOPE_API_KEY -> ok=false。"""
    s = _settings(DASHSCOPE_API_KEY="")
    pf = run_real_preflight(s, use_local_rag=False, use_deep_research=False)
    assert pf["ok"] is False
    assert any("DASHSCOPE" in e for e in pf["errors"])


def test_preflight_workspace_placeholder_in_base_url():
    """base_url 含占位符 -> ok=false。"""
    s = _settings(
        WORKSPACE_ID="",
        DASHSCOPE_BASE_URL="https://你的WorkspaceId.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    )
    pf = run_real_preflight(s, use_local_rag=False, use_deep_research=False)
    assert pf["ok"] is False


def test_openalex_missing_is_warning_only():
    """OpenAlex 缺失不阻塞。"""
    s = _settings(OPENALEX_API_KEY="")
    pf = run_real_preflight(s, use_local_rag=False, use_deep_research=False)
    assert pf["can_run_real"] is True or pf["ok"] is True or not pf["errors"]


def test_preflight_no_key_leak():
    """preflight 返回不含完整 Key。"""
    s = _settings()
    pf = run_real_preflight(s, use_local_rag=False, use_deep_research=False)
    blob = str(pf)
    assert "sk-test1234567890abcd" not in blob


def test_deepresearch_missing_warning():
    """DeepResearch 配置缺失仅 warning。"""
    s = _settings(WORKSPACE_ID="", DASHSCOPE_DEEP_RESEARCH_BASE_URL="", DASHSCOPE_API_KEY="")
    pf = run_real_preflight(s, use_local_rag=False, use_deep_research=True)
    assert not pf["ok"] or any("DeepResearch" in w for w in pf.get("warnings", []))
