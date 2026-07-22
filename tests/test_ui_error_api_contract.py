# -*- coding: utf-8 -*-
"""tests/test_ui_error_api_contract.py — UI 层 errors.xxx 调用与 errors.py 定义一致。"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import app.ui.errors as errors_mod

UI_DIR = Path(__file__).resolve().parents[1] / "app" / "ui"


def _extract_errors_calls(path: Path) -> set[str]:
    """从 Python 源码提取 errors.xxx 调用名。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "errors":
                names.add(node.func.attr)
    return names


def test_all_errors_calls_exist_in_errors_module():
    """app/ui/*.py 中 errors.xxx 均存在于 errors.py。"""
    all_calls: set[str] = set()
    for py in UI_DIR.glob("*.py"):
        if py.name == "errors.py":
            continue
        all_calls |= _extract_errors_calls(py)
    for name in all_calls:
        assert hasattr(errors_mod, name), f"errors.{name} 未在 errors.py 定义"


def test_main_ui_no_st_exception():
    """主 UI 文件禁止直接 st.exception（Developer Diagnostics 除外）。"""
    for fname in ("streamlit_app.py", "components.py"):
        src = (UI_DIR / fname).read_text(encoding="utf-8")
        assert "st.exception" not in src, f"{fname} 不应直接 st.exception"
