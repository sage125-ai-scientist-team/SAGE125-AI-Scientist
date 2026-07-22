"""
tests/test_researchplan_viewer.py — ResearchPlan 展示稳健性测试（P0-5 / 七）。

以源码结构 + 纯逻辑方式校验（不启动 streamlit 运行时）：
    - 无 plan 时走 render_empty_state；
    - 展示前做选题-报告一致性校验（streamlit_app 使用 is_run_consistent + 阻断）；
    - JSON tab 默认折叠（expanded=False）；
    - 导出中心用 make_widget_key，无重复弱 key；
    - errors 模块提供 render_user_error / render_report_mismatch。
"""

from __future__ import annotations

from pathlib import Path

from app.ui import components, errors

ROOT = Path(__file__).resolve().parents[1]


def test_viewer_functions_exist():
    """关键展示函数存在。"""
    for fn in ("render_research_plan_tabs", "render_empty_state", "render_developer_diagnostics",
               "render_qwen_invocation_summary"):
        assert hasattr(components, fn), f"缺少组件函数：{fn}"


def test_empty_state_used_for_no_plan():
    """无 plan 时 render_research_plan_tabs 调用 render_empty_state。"""
    src = (ROOT / "app" / "ui" / "components.py").read_text(encoding="utf-8")
    # 函数体内含 not plan -> render_empty_state 分支。
    assert "if not plan:" in src
    assert "render_empty_state" in src


def test_json_tab_collapsed_by_default():
    """JSON 展开默认折叠。"""
    src = (ROOT / "app" / "ui" / "components.py").read_text(encoding="utf-8")
    assert 'expanded=False' in src


def test_streamlit_app_uses_consistency_guard():
    """streamlit_app 使用一致性校验并在不一致时阻断展示。"""
    app = (ROOT / "app" / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "is_run_consistent" in app
    assert "report_mismatch" in app


def test_errors_module_api():
    """errors 模块提供用户级错误与不一致阻断函数。"""
    assert hasattr(errors, "render_user_error")
    assert hasattr(errors, "render_report_mismatch")


def test_export_center_uses_key_factory():
    """导出中心使用 make_widget_key 生成下载按钮 key。"""
    src = (ROOT / "app" / "ui" / "components.py").read_text(encoding="utf-8")
    assert "make_widget_key(\"download\", run_id, fname, i)" in src
