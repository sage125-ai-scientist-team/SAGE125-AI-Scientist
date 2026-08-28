"""
tests/test_scope_core_only.py — 项目范围收敛校验。

确认参赛材料自动生成相关内容已从主流程移除，且核心 AI Scientist 能力仍在：
    - README 不把提交包/技术方案 PDF/演示视频脚本当作项目核心输出；
    - 前端不含 Submission Export Center 等措辞；
    - API 不暴露 submission/technical_solution/demo_script 主流程接口；
    - ResearchPlan 导出、run_batch_125、audit_project 仍存在；
    - 已删除的提交材料文件确实不存在。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(p: Path) -> str:
    """读取文本（不存在返回空串）。"""
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def test_readme_scope_statement():
    """README 含范围声明并区分项目功能与人工整理材料。"""
    readme = _read(ROOT / "README.md")
    assert "不是参赛材料自动生成器" in readme
    assert "项目核心功能" in readme
    assert "后续人工整理材料" in readme


def test_readme_no_submission_pipeline_commands():
    """README 不再把提交包/技术方案脚本当作项目命令。"""
    readme = _read(ROOT / "README.md")
    assert "make_submission_bundle" not in readme
    assert "build_submission_docs" not in readme
    assert "technical_solution.pdf" not in readme
    assert "demo_script_10min" not in readme


def test_frontend_no_submission_center():
    """前端源码不含 Submission Export Center / 提交包相关措辞。"""
    comp = _read(ROOT / "app" / "ui" / "components.py")
    appui = _read(ROOT / "app" / "ui" / "streamlit_app.py")
    for token in ("Submission Export Center", "technical_solution.pdf", "demo_script_10min", "submission_bundle", "赛题提交映射"):
        assert token not in comp, f"components.py 仍含 {token}"
        assert token not in appui, f"streamlit_app.py 仍含 {token}"
    # 新命名存在。
    assert "ResearchPlan Export Center" in appui or "render_researchplan_export_center" in appui


def test_api_no_submission_routes():
    """API 路由不含 submission/technical_solution/demo_script 主流程接口。"""
    routes = _read(ROOT / "app" / "api" / "routes.py")
    for token in ("/submission", "technical_solution", "demo_script", "submission_bundle", "build_submission", "make_submission"):
        assert token not in routes, f"routes.py 仍含 {token}"
    # 保留的核心导出接口仍在。
    assert "/export/markdown" in routes
    assert "/export/pdf" in routes
    assert "/runs/{run_id}/files/{file_name}" in routes


def test_core_tools_still_exist():
    """核心与可选工具脚本仍存在。"""
    assert (ROOT / "scripts" / "run_batch_125.py").exists()
    assert (ROOT / "scripts" / "audit_project.py").exists()
    assert (ROOT / "scripts" / "run_demo.py").exists()
    assert (ROOT / "scripts" / "smoke_bailian.py").exists()


def test_researchplan_export_usable():
    """ResearchPlan 导出仍可用（可导入）。"""
    from app.exporters import export_research_plan_markdown, render_research_plan_markdown  # noqa: F401

    assert callable(export_research_plan_markdown)


def test_removed_files_absent():
    """已删除的参赛材料文件确实不存在。"""
    assert not (ROOT / "scripts" / "build_submission_docs.py").exists()
    assert not (ROOT / "scripts" / "make_submission_bundle.py").exists()
    assert not (ROOT / "app" / "exporters" / "submission_exporter.py").exists()
    assert not (ROOT / "app" / "exporters" / "templates" / "technical_solution.html.j2").exists()
    assert not (ROOT / "docs" / "DEMO_SCRIPT_10MIN.md").exists()
    assert not (ROOT / "docs" / "SUBMISSION_CHECKLIST.md").exists()
