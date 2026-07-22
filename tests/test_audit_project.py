"""
tests/test_audit_project.py — 审计脚本测试。

覆盖：audit 可运行且当前项目通过；检测正则对 secret/假指标/非千问模型生效；
openai SDK import 不触发；_audit_plan 对 fake metric 与空引用 ready 触发 critical。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_project import (
    _FAKE_METRIC,
    _NON_QWEN_MODEL,
    _OPENAI_ENDPOINT,
    _SECRET_PATTERNS,
    _audit_plan,
    audit,
)


def fake_sk_token() -> str:
    """构造只用于测试的假 Key，避免在源码中保留连续凭证形状。"""
    return "sk-" + ("x" * 32)


def test_audit_runs_and_passes():
    """当前项目审计应通过（critical=0）。"""
    result = audit()
    assert result["passed"] is True, result["critical"]


def test_secret_regex():
    """长 sk- 串应被识别为疑似 Key。"""
    assert any(p.search(f"token {fake_sk_token()}") for p in _SECRET_PATTERNS)
    # 短的测试假值不触发（<16）。
    assert not any(p.search("sk-1234567890") for p in _SECRET_PATTERNS)


def test_non_qwen_model_regex():
    """model= 非千问模型触发；openai import 不触发。"""
    assert _NON_QWEN_MODEL.search('model="gpt-4o"')
    assert _NON_QWEN_MODEL.search("model='claude-3.5'")
    assert not _NON_QWEN_MODEL.search("import openai")
    assert not _NON_QWEN_MODEL.search('model="qwen3.7-max"')


def test_openai_endpoint_regex():
    """OpenAI 官方 endpoint 触发。"""
    assert _OPENAI_ENDPOINT.search("https://api.openai.com/v1")


def test_fake_metric_regex():
    """虚构指标触发。"""
    assert _FAKE_METRIC.search("AUROC=0.92")
    assert _FAKE_METRIC.search("accuracy = 95%")


def test_audit_plan_detects_issues(tmp_path):
    """_audit_plan 对假指标与空引用 ready 触发 critical。"""
    critical: list = []
    warnings: list = []
    bad_plan = {
        "references": [], "actual_execution": False,
        "results": "模型取得 AUROC=0.92 的优异表现。", "validation_status": "ready_for_validation",
    }
    _audit_plan(bad_plan, tmp_path / "report.json", critical, warnings)
    # 应至少产生 2 条 critical（假指标 + 空引用 ready）。
    assert len(critical) >= 2


def test_audit_plan_clean(tmp_path):
    """干净 plan 不触发 critical。"""
    critical: list = []
    warnings: list = []
    good_plan = {
        "references": [{"id": "EV-1", "source_type": "rag", "reliability_note": "mock_for_testing"}],
        "actual_execution": False,
        "results": "当前状态：待执行验证实验。", "validation_status": "ready_for_validation",
    }
    _audit_plan(good_plan, tmp_path / "report.json", critical, warnings)
    assert critical == []
