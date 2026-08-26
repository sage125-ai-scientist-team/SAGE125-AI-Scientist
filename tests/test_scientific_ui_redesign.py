# -*- coding: utf-8 -*-
"""科学首页 + 工作区重构的源码与功能等价契约。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_redesign_docs_exist():
    for rel in (
        "docs/ui/FRONTEND_FEATURE_PARITY_MATRIX.md",
        "docs/ui/OPEN_SOURCE_UI_REFERENCES.md",
        "docs/ui/UI_REDESIGN_ROLLBACK.md",
    ):
        text = _read(rel)
        assert text.strip(), rel


def test_parity_matrix_covers_required_features():
    text = _read("docs/ui/FRONTEND_FEATURE_PARITY_MATRIX.md")
    for token in (
        "F01", "F12", "F13", "F20", "F21", "F22", "F26", "F30",
        "125", "EvidenceCards", "Q028", "OpenAPI", "streamlit_app_legacy.py",
    ):
        assert token in text, token


def test_legacy_entrypoint_preserved():
    assert (ROOT / "app/ui/streamlit_app_legacy.py").exists()
    src = _read("app/ui/streamlit_app.py")
    assert "st.navigation" in src
    assert "render_legacy_workspace" in src
    assert "进入研究工作区" in _read("app/ui/landing.py")


def test_no_fake_marketing_metrics_hardcoded():
    banned = ("10,842", "2,156", "98.7%", "0.87", "1248", "65%")
    for rel in (
        "app/ui/landing.py",
        "app/ui/workspace.py",
        "app/ui/workspace_pages.py",
        "app/ui/streamlit_app.py",
    ):
        src = _read(rel)
        for token in banned:
            assert token not in src, f"{rel} 含禁止的效果图数字：{token}"


def test_no_fake_login():
    landing = _read("app/ui/landing.py")
    assert "登录" not in landing
    assert "Login" not in landing


def test_landing_has_q028_boundary():
    src = _read("app/ui/landing.py")
    assert "不构成临床验证" in src
    assert "不能外推至所有癌症" in src
