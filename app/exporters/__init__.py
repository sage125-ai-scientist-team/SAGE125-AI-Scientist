"""
app.exporters —— 运行结果（ResearchPlan）导出子包。

定位：导出**当前运行**的《科学假设与研究计划》报告，供人在回路查看与留存；
不负责生成参赛技术方案 PDF/PPT 或演示视频（那些由团队人工整理）。

    - markdown_exporter : ResearchPlan -> Markdown。
    - html_exporter     : ResearchPlan / 批量摘要 -> HTML（Jinja2 + print.css）。
    - pdf_exporter      : HTML/Markdown -> PDF（WeasyPrint 优先，ReportLab 兜底，CJK 探测）。
"""

from app.exporters.markdown_exporter import (
    export_research_plan_markdown,
    render_research_plan_markdown,
)

# 对外导出的稳定符号。
__all__ = [
    "export_research_plan_markdown",
    "render_research_plan_markdown",
]
