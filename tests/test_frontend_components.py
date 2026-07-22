"""
tests/test_frontend_components.py — 前端组件模块测试。

覆盖：components 可导入；关键 render 函数存在；esc 转义正确；
mock_for_testing 徽标逻辑与 empty state 逻辑存在。
"""

from __future__ import annotations

from pathlib import Path

from app.ui import components


def test_components_import_and_functions():
    """关键组件函数应存在。"""
    for fn in ["esc", "load_css", "render_hero", "render_first_run_wizard", "render_run_browser",
               "render_empty_state", "render_researchplan_export_center", "render_research_plan_tabs",
               "render_agent_pipeline", "render_evidence_wall"]:
        assert hasattr(components, fn), f"缺少组件函数：{fn}"


def test_esc_escapes():
    """esc 应转义 HTML 危险字符。"""
    assert components.esc("<script>") == "&lt;script&gt;"
    assert components.esc(None) == ""


def test_mock_and_empty_state_logic_present():
    """组件源码含 mock_for_testing 徽标与 empty state 逻辑。"""
    src = (Path(__file__).resolve().parents[1] / "app" / "ui" / "components.py").read_text(encoding="utf-8")
    assert "mock_for_testing" in src
    assert "render_empty_state" in src


def test_mock_data_module():
    """mock_data 提供带 mock_for_testing 标记的预览证据。"""
    from app.ui import mock_data

    cards = mock_data.mock_evidence_preview()
    assert cards and all(mock_data.MOCK_TAG in c["reliability_note"] for c in cards)
    assert all(c["doi"] is None and c["url"] is None for c in cards)
