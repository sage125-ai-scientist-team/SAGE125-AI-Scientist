# -*- coding: utf-8 -*-
"""
tests/test_streamlit_run_guards.py — 前端运行触发防静默守卫。

覆盖：
    - streamlit_app 在无 questions / 无 qid 时调用 errors.questions_missing /
      errors.question_not_selected；
    - Demo Preset 在空题库或未命中时同样显式报错；
    - errors 新函数可调用且文案含修复命令。
"""

from __future__ import annotations

from pathlib import Path

from app.ui import errors

ROOT = Path(__file__).resolve().parents[1]
APP_SRC = (ROOT / "app" / "ui" / "streamlit_app.py").read_text(encoding="utf-8")


def test_streamlit_source_guards_missing_questions_and_qid():
    """
    源码必须在 trigger_generate/mock 路径显式处理空题库与未选题。

    返回：
        None；断言失败即表示静默失败回归。
    """
    assert "errors.questions_missing" in APP_SRC
    assert "errors.question_not_selected" in APP_SRC
    assert "if trigger_generate or trigger_mock:" in APP_SRC
    assert "if not questions:" in APP_SRC
    assert "elif not qid:" in APP_SRC


def test_demo_preset_guards_present():
    """
    Demo Preset 按钮在空题库或未命中时必须走错误卡，而不是静默。

    返回：
        None。
    """
    assert 'Demo Preset「{label}」需要先加载问题清单' in APP_SRC or "questions_missing" in APP_SRC
    assert "未命中任何问题" in APP_SRC


def test_questions_missing_and_not_selected_callable():
    """
    新错误卡函数应可直接调用，且修复命令包含 bootstrap / extract。

    返回：
        None。
    """
    errors.questions_missing(details="unit-test")
    errors.question_not_selected(details="unit-test")
    src = Path(errors.__file__).read_text(encoding="utf-8")
    assert "bootstrap_preview_data.py" in src
    assert "extract_125_questions.py" in src
