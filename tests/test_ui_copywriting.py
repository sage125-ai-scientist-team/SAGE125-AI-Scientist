# -*- coding: utf-8 -*-
"""tests/test_ui_copywriting.py — UI 文案规范（无错误/mock 文案）。"""

from __future__ import annotations

from pathlib import Path

UI_DIR = Path(__file__).resolve().parents[1] / "app" / "ui"


def test_no_bad_copywriting_in_ui():
    """禁止「嘲讽 API」等错误文案；Mock 按钮应为模拟演示。"""
    bad = ["嘲讽", "清流", "Mock API: 连接"]
    for py in UI_DIR.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        for token in bad:
            assert token not in text, f"{py.name} 含错误文案: {token}"


def test_run_mock_button_label():
    """Mock 按钮文案为「运行模拟演示」。"""
    src = (UI_DIR / "components.py").read_text(encoding="utf-8")
    assert "运行模拟演示" in src


def test_clear_button_label():
    """清空按钮文案正确。"""
    src = (UI_DIR / "streamlit_app.py").read_text(encoding="utf-8")
    assert "清空当前结果" in src


def test_render_preview_does_not_claim_permanent_local_storage():
    components = (UI_DIR / "components.py").read_text(encoding="utf-8")
    streamlit_app = (UI_DIR / "streamlit_app.py").read_text(encoding="utf-8")

    assert "永久保存在项目本地" not in components
    assert "仅保存在当前临时 API 实例" in components
    assert "当前预览使用临时存储" in streamlit_app
