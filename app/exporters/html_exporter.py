"""
app.exporters.html_exporter —— 基于 Jinja2 的 HTML 导出（适配 WeasyPrint 转 PDF）。

autoescape 全程开启，所有用户输入/模型输出/证据文本进入 HTML 前自动转义；
print.css 以内联方式注入，不使用外部 CDN、不加载外部图片、不含 API Key。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.logging import get_logger

# 模块级日志器。
logger = get_logger("exporters.html")

# 模板目录与 print.css。
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_PRINT_CSS_PATH = _TEMPLATES_DIR / "print.css"

# 无真实实验时的 pending 句子片段。
_PENDING_MARK = "待执行验证实验"


def _env() -> Environment:
    """构造启用 autoescape 的 Jinja2 环境。"""
    # select_autoescape 对 html/xml/j2 模板自动转义，防注入。
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(default=True, enabled_extensions=("html", "j2", "html.j2")),
    )


def _print_css() -> str:
    """读取 print.css 内容（供内联注入）。"""
    return _PRINT_CSS_PATH.read_text(encoding="utf-8") if _PRINT_CSS_PATH.exists() else ""


def _as_dict(obj: Any) -> Any:
    """将 pydantic 对象/嵌套结构转为 dict（供模板访问）。"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj


def export_research_plan_html(plan: Any, evidence_cards: list, agent_trace: list, output_path: Path, run_id: str = "") -> Path:
    """
    将 ResearchPlan 渲染为学术排版 HTML。

    参数：
        plan:           ResearchPlan 对象或 dict。
        evidence_cards: 证据列表（当前模板主要用 plan.references）。
        agent_trace:    Agent 追踪（预留）。
        output_path:    目标 HTML 路径。
        run_id:         运行 ID（写入页眉页脚）。

    返回：
        写入的文件路径。
    """
    p = _as_dict(plan)
    pending = (not p.get("actual_execution")) or (_PENDING_MARK in (p.get("results") or ""))
    html = _env().get_template("research_plan.html.j2").render(
        plan=p, run_id=run_id, print_css=_print_css(), pending=pending
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("已导出 HTML：%s", output_path.name)
    return output_path


def export_batch_summary_html(batch_summary: dict, output_path: Path) -> Path:
    """
    将 125 批量运行的 ResearchPlan 结果总览渲染为 HTML（仅运行结果摘要，非参赛提交文档）。

    参数：
        batch_summary: 批量总览 dict。
        output_path:   目标 HTML 路径。

    返回：
        写入的文件路径。
    """
    html = _env().get_template("batch_summary.html.j2").render(summary=batch_summary, print_css=_print_css())
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("已导出 batch summary HTML：%s", output_path.name)
    return output_path
