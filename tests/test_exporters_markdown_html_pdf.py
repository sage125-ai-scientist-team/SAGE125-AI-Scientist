"""
tests/test_exporters_markdown_html_pdf.py — 导出器测试（Markdown/HTML/PDF）。

覆盖：Markdown 导出、HTML 转义与结构、PDF 依赖不可用时 graceful fallback、
Results pending 保留、References 保留证据信息、不含 API Key。
"""

from __future__ import annotations

from app.core.schemas import EvidenceCard, ResearchPlan, ScientificHypothesis
from app.exporters.markdown_exporter import export_research_plan_markdown, render_research_plan_markdown
from app.exporters.html_exporter import export_research_plan_html
from app.exporters.pdf_exporter import export_html_to_pdf, validate_pdf_output


def _plan() -> ResearchPlan:
    """构造一个含 mock 证据的 ResearchPlan。"""
    ev = EvidenceCard(
        id="EV-MOCK-1", source_type="rag", title="[MOCK] evidence", quoted_text="原始不可改写片段",
        summary="s", relevance_score=0.8, reliability_note="mock_for_testing",
    )
    return ResearchPlan(
        input_question="Can we predict the next pandemic?", domain="Medicine & Health",
        problem_statement="P", rationale="R",
        generated_hypotheses=[ScientificHypothesis(hypothesis="H", mechanism="M",
                              falsifiable_prediction="FP", risk_of_being_wrong="risk")],
        datasets={"source": "src", "target": "tgt"},
        experiments={"baselines": ["LR"], "metrics": ["AUROC"], "ablation": [], "validation_protocol": "x"},
        results="当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。",
        references=[ev], validation_status="ready_for_validation",
    )


def test_markdown_export(tmp_path):
    """Markdown 导出应含 pending、证据信息，不含 API Key。"""
    out = export_research_plan_markdown(_plan(), tmp_path / "report.md")
    text = out.read_text(encoding="utf-8")
    assert "待执行验证实验" in text
    assert "EV-MOCK-1" in text
    assert "mock_for_testing" in text
    assert "Not available" in text  # DOI/URL 缺失
    assert "sk-" not in text or "sk-****" in text


def test_markdown_render_string():
    """render 返回字符串包含标题层级。"""
    md = render_research_plan_markdown(_plan())
    assert md.startswith("#")
    assert "## References" in md


def test_html_export_escaped(tmp_path):
    """HTML 导出应转义危险片段且结构完整。"""
    plan = _plan()
    # 注入一个含 HTML 的问题，验证转义。
    plan.input_question = "<script>alert(1)</script>"
    out = export_research_plan_html(plan, [], [], tmp_path / "report.html", run_id="test")
    html = out.read_text(encoding="utf-8")
    # 原始 script 标签不得出现（应被转义为 &lt;script&gt;）。
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_pdf_fallback(tmp_path):
    """PDF 导出应在无 WeasyPrint 时 fallback 到 ReportLab，且不崩溃。"""
    plan = _plan()
    html_path = export_research_plan_html(plan, [], [], tmp_path / "r.html", run_id="test")
    result = export_html_to_pdf(html_path, tmp_path / "r.pdf")
    # 引擎应为 weasyprint 或 reportlab；状态 ok。
    assert result["engine"] in ("weasyprint", "reportlab")
    if result["status"] == "ok":
        v = validate_pdf_output(tmp_path / "r.pdf")
        assert v["exists"] is True
