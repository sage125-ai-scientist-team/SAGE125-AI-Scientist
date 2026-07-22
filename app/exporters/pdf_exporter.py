"""
app.exporters.pdf_exporter —— PDF 导出（WeasyPrint 优先，ReportLab 兜底）。

策略：
    1. 首选 WeasyPrint：HTML/CSS -> PDF（本地资源，不访问远程）；
    2. WeasyPrint 不可用/系统依赖缺失时，回退 ReportLab 生成简化 PDF；
    3. 两者都失败返回清晰错误，但绝不让主流程崩溃。

中文字体：
    - 不打包/不分发字体文件；仅探测系统已安装 CJK 字体用于报告；
    - ReportLab 兜底使用其**内置** CID 字体 STSong-Light 渲染中文（无需外部字体文件），
      若不可用则退化为默认字体并给出 warning。
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

# 模块级日志器。
logger = get_logger("exporters.pdf")

# 各平台常见 CJK 字体文件名（用于探测报告，不用于分发）。
_CJK_FONT_HINTS = {
    "win32": ["msyh.ttc", "msyhbd.ttc", "simsun.ttc", "Deng.ttf", "Dengb.ttf", "simhei.ttf"],
    "darwin": ["PingFang.ttc", "Songti.ttc", "STHeiti Medium.ttc", "Hiragino Sans GB.ttc"],
    "linux": ["NotoSansCJK-Regular.ttc", "NotoSerifCJK-Regular.ttc", "wqy-microhei.ttc", "wqy-zenhei.ttc"],
}


def detect_system_cjk_fonts() -> list[str]:
    """
    探测系统已安装的 CJK 字体（仅返回文件名，不复制/分发字体）。

    返回：
        命中的字体文件名列表（可能为空）。
    """
    import sys

    # 依平台选择字体目录与候选名。
    platform = sys.platform
    dirs: list[Path] = []
    if platform.startswith("win"):
        dirs = [Path("C:/Windows/Fonts")]
        hints = _CJK_FONT_HINTS["win32"]
    elif platform == "darwin":
        dirs = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"]
        hints = _CJK_FONT_HINTS["darwin"]
    else:
        dirs = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts"]
        hints = _CJK_FONT_HINTS["linux"]

    found: list[str] = []
    for d in dirs:
        if not d.exists():
            continue
        # 递归匹配候选字体名（大小写不敏感）。
        existing = {p.name.lower() for p in d.rglob("*") if p.is_file()}
        for h in hints:
            if h.lower() in existing:
                found.append(h)
    return found


def _weasyprint_available() -> bool:
    """探测 WeasyPrint 是否可导入（Windows 常因 GTK 依赖缺失而不可用）。"""
    try:
        import weasyprint  # noqa: F401

        return True
    except Exception:
        return False


def _html_to_blocks(html_text: str) -> list[tuple[str, str]]:
    """
    将 HTML 粗略转换为 (kind, text) 块序列，供 ReportLab 兜底渲染。

    参数：
        html_text: HTML 字符串。

    返回：
        (kind, text) 列表，kind ∈ {h1,h2,h3,li,p}。
    """
    # 去掉 style/script 块，避免 CSS 混入正文。
    body = re.sub(r"<style[\s\S]*?</style>", "", html_text, flags=re.IGNORECASE)
    body = re.sub(r"<script[\s\S]*?</script>", "", body, flags=re.IGNORECASE)
    blocks: list[tuple[str, str]] = []
    # 按标签抽取标题/列表/单元格/段落。
    pattern = re.compile(r"<(h1|h2|h3|li|td|th|p)[^>]*>([\s\S]*?)</\1>", re.IGNORECASE)
    for m in pattern.finditer(body):
        tag = m.group(1).lower()
        # 去除内部标签并反转义实体。
        text = re.sub(r"<[^>]+>", " ", m.group(2))
        text = _html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        kind = tag if tag in ("h1", "h2", "h3", "li") else "p"
        blocks.append((kind, text))
    return blocks


def _reportlab_pdf_from_blocks(blocks: list[tuple[str, str]], pdf_path: Path, title: str = "") -> dict:
    """
    使用 ReportLab 由块序列生成简化 PDF（内置 CID 字体渲染中文）。

    参数：
        blocks:   (kind, text) 列表。
        pdf_path: 目标 PDF 路径。
        title:    文档标题。

    返回：
        结果 dict（engine/warnings/errors）。
    """
    warnings: list[str] = []
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except Exception as exc:  # reportlab 不可用
        return {"engine": "none", "warnings": warnings, "errors": [f"reportlab 不可用：{exc}"]}

    # 注册内置 CID 中文字体（无需外部字体文件）。
    cjk_font = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(cjk_font))
    except Exception:
        # 内置 CID 字体不可用时退化默认字体并告警。
        cjk_font = "Helvetica"
        warnings.append("未能注册中文 CID 字体，PDF 中文可能显示异常。请在系统安装 CJK 字体后重试。")

    # 样式。
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("body_cjk", parent=styles["BodyText"], fontName=cjk_font, fontSize=10, leading=15)
    h1 = ParagraphStyle("h1_cjk", parent=styles["Title"], fontName=cjk_font, fontSize=18, leading=22)
    h2 = ParagraphStyle("h2_cjk", parent=styles["Heading2"], fontName=cjk_font, fontSize=13, leading=18)
    h3 = ParagraphStyle("h3_cjk", parent=styles["Heading3"], fontName=cjk_font, fontSize=11, leading=16)
    style_map = {"h1": h1, "h2": h2, "h3": h3, "p": body_style, "li": body_style}

    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    flow = []
    if title:
        flow.append(Paragraph(_html.escape(title), h1))
        flow.append(Spacer(1, 6))
    for kind, text in blocks:
        prefix = "• " if kind == "li" else ""
        # reportlab Paragraph 需转义 & < > 等。
        flow.append(Paragraph(prefix + _html.escape(text), style_map.get(kind, body_style)))
        flow.append(Spacer(1, 3))
    try:
        doc.build(flow)
    except Exception as exc:
        return {"engine": "reportlab", "warnings": warnings, "errors": [f"reportlab 生成失败：{exc}"]}
    return {"engine": "reportlab", "warnings": warnings, "errors": []}


def export_html_to_pdf(html_path: Path, pdf_path: Path) -> dict:
    """
    将 HTML 导出为 PDF（WeasyPrint 优先，ReportLab 兜底）。

    参数：
        html_path: 源 HTML 路径。
        pdf_path:  目标 PDF 路径。

    返回：
        结果 dict：{"status","engine","warnings","errors","cjk_fonts"}。
    """
    html_path = Path(html_path)
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cjk_fonts = detect_system_cjk_fonts()
    warnings: list[str] = []
    if not cjk_fonts:
        warnings.append("未检测到系统 CJK 字体，PDF 中文可能显示异常（ReportLab 将使用内置 CID 字体兜底）。")

    # 1) WeasyPrint 优先。
    if _weasyprint_available():
        try:
            import weasyprint  # type: ignore

            weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))
            return {"status": "ok", "engine": "weasyprint", "warnings": warnings, "errors": [], "cjk_fonts": cjk_fonts}
        except Exception as exc:
            warnings.append(f"WeasyPrint 失败，回退 ReportLab：{exc}")

    # 2) ReportLab 兜底。
    blocks = _html_to_blocks(html_path.read_text(encoding="utf-8"))
    result = _reportlab_pdf_from_blocks(blocks, pdf_path, title="SAGE125 AI Scientist")
    status = "ok" if pdf_path.exists() and not result["errors"] else "failed"
    return {"status": status, "engine": result["engine"], "warnings": warnings + result["warnings"], "errors": result["errors"], "cjk_fonts": cjk_fonts}


def export_markdown_to_pdf(markdown_path: Path, pdf_path: Path) -> dict:
    """
    将 Markdown 导出为 PDF（先转 HTML 走 WeasyPrint，失败再 ReportLab）。

    参数：
        markdown_path: 源 Markdown 路径。
        pdf_path:      目标 PDF 路径。

    返回：
        结果 dict。
    """
    markdown_path = Path(markdown_path)
    pdf_path = Path(pdf_path)
    md_text = markdown_path.read_text(encoding="utf-8")

    # WeasyPrint 优先：md -> html -> pdf。
    if _weasyprint_available():
        try:
            import markdown as md_lib
            import weasyprint  # type: ignore

            html = f"<meta charset='utf-8'><body>{md_lib.markdown(md_text, extensions=['tables'])}</body>"
            weasyprint.HTML(string=html).write_pdf(str(pdf_path))
            return {"status": "ok", "engine": "weasyprint", "warnings": [], "errors": [], "cjk_fonts": detect_system_cjk_fonts()}
        except Exception as exc:
            logger.warning("WeasyPrint md->pdf 失败，回退 ReportLab：%s", exc)

    # ReportLab 兜底：按行解析 markdown 为块。
    blocks: list[tuple[str, str]] = []
    for line in md_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("### "):
            blocks.append(("h3", s[4:]))
        elif s.startswith("## "):
            blocks.append(("h2", s[3:]))
        elif s.startswith("# "):
            blocks.append(("h1", s[2:]))
        elif s.startswith(("- ", "* ")):
            blocks.append(("li", s[2:]))
        else:
            blocks.append(("p", s))
    result = _reportlab_pdf_from_blocks(blocks, pdf_path)
    status = "ok" if pdf_path.exists() and not result["errors"] else "failed"
    return {"status": status, "engine": result["engine"], "warnings": result["warnings"], "errors": result["errors"], "cjk_fonts": detect_system_cjk_fonts()}


def validate_pdf_output(pdf_path: Path) -> dict:
    """
    校验 PDF 产物：是否存在、大小、页数（pypdf 可用时）。

    参数：
        pdf_path: PDF 路径。

    返回：
        {"exists","file_size_bytes","page_count","warnings","errors"}。
    """
    pdf_path = Path(pdf_path)
    result: dict[str, Any] = {"exists": pdf_path.exists(), "file_size_bytes": 0, "page_count": None, "warnings": [], "errors": []}
    if not pdf_path.exists():
        result["errors"].append("PDF 不存在。")
        return result
    result["file_size_bytes"] = pdf_path.stat().st_size
    # 尝试用 pypdf 统计页数。
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        result["page_count"] = len(reader.pages)
    except Exception:
        # 无法检测页数。
        result["warnings"].append("无法检测 PDF 页数（pypdf 不可用或文件异常）。")
    return result
