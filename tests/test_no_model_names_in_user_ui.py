"""
tests/test_no_model_names_in_user_ui.py — 主界面不暴露模型代号测试（P0-2 / 十三）。

覆盖：
    - components.py 用户主界面渲染函数不出现具体模型代号；
    - streamlit_app.py 不出现具体模型代号；
    - Developer Diagnostics 函数存在，且通过动态 health.models 展示（不写死代号）；
    - README 允许出现模型名（技术配置章节）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 禁止出现在用户主界面源码中的具体模型代号。
MODEL_CODES = ["qwen3.7-plus", "qwen3.6-flash", "qwen3.7-max", "qwen-deep-research",
               "text-embedding-v4", "qwen3-rerank"]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_components_main_ui_has_no_model_codes():
    """components.py 不应出现具体模型代号（Developer Diagnostics 用动态 health.models）。"""
    src = _read("app/ui/components.py")
    for code in MODEL_CODES:
        assert code not in src, f"components.py 主界面不应出现模型代号：{code}"


def test_streamlit_app_has_no_model_codes():
    """streamlit_app.py 不应出现具体模型代号。"""
    src = _read("app/ui/streamlit_app.py")
    for code in MODEL_CODES:
        assert code not in src, f"streamlit_app.py 不应出现模型代号：{code}"


def test_developer_diagnostics_exists():
    """Developer Diagnostics 面板函数存在且默认折叠。"""
    src = _read("app/ui/components.py")
    assert "def render_developer_diagnostics" in src
    assert "Developer Diagnostics" in src
    # 面板应默认折叠。
    assert re.search(r"expander\([^\)]*expanded=False", src)


def test_readme_may_mention_models():
    """README 技术章节允许出现模型名（不做禁止）。"""
    readme = _read("README.md")
    assert "qwen" in readme.lower()
