"""Deterministic renderers driven only by ``CanonicalReport``."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

from app.export.canonical import CanonicalReport


def render_report_json(report: CanonicalReport) -> bytes:
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def render_report_markdown(report: CanonicalReport) -> bytes:
    actual = (
        "YES"
        if report.execution.actual_execution is True
        else "NO"
        if report.execution.actual_execution is False
        else "UNAVAILABLE"
    )
    lines = [
        f"# {report.title}",
        "",
        f"- Content SHA256: `{report.content_sha256}`",
        f"- Job: `{report.job_id}`",
        f"- Question: `{report.question_id}`",
        f"- Run: `{report.run_id}`",
        f"- Version: `{report.version_id or 'unavailable'}`",
        f"- Generated: `{report.generated_at.isoformat()}`",
        f"- Truth status: **{report.truth_status}**",
        f"- ACTUAL EXECUTION: {actual}",
        "",
        "## Scientific Question",
        "",
        report.question,
        "",
        f"Domain: {report.domain}",
        "",
        "## Hypotheses",
        "",
    ]
    lines.extend(f"- {item}" for item in report.hypotheses or ["N/A"])
    lines.extend(["", "## Methods", ""])
    lines.extend(f"- {item}" for item in report.methods or ["N/A"])
    lines.extend(["", "## Evidence", ""])
    if not report.evidence:
        lines.append("- N/A")
    for item in report.evidence:
        source = item.url or (f"https://doi.org/{item.doi}" if item.doi else "unavailable")
        lines.extend(
            [
                f"### {item.evidence_id}: {item.title}",
                "",
                f"> {item.quoted_text}",
                "",
                f"Locator: {item.locator}",
                f"Verification: {item.verification_status}",
                f"Confidence: {item.confidence if item.confidence is not None else 'unavailable'}",
                f"Source: {source}",
                "",
            ]
        )
    lines.extend(["## Reviewer Issues", ""])
    if not report.reviewer_issues:
        lines.append("- N/A")
    for item in report.reviewer_issues:
        lines.append(
            f"- [{item.severity}/{item.status}] {item.issue_id}: {item.summary}"
        )
        if item.resolution_note:
            lines.append(f"  - Resolution: {item.resolution_note}")
    lines.extend(["", "## Human Feedback", ""])
    if not report.feedback:
        lines.append("- N/A")
    for item in report.feedback:
        lines.append(
            f"- [{item.status}] {item.feedback_id} -> {item.target_version_id}"
        )
    lines.extend(["", "## Validation Gates", ""])
    if not report.gates:
        lines.append("- N/A")
    for gate in report.gates:
        lines.append(
            f"- {gate.gate_id}: {'passed' if gate.passed else 'blocked'} ({gate.severity})"
        )
        lines.extend(f"  - Finding: {finding}" for finding in gate.findings)
    lines.extend(
        [
            "",
            "## Execution",
            "",
            f"- Availability: {report.execution.availability}",
            f"- Status: {report.execution.status}",
            f"- Execution ID: {report.execution.execution_id or 'unavailable'}",
            f"- ACTUAL EXECUTION: {actual}",
        ]
    )
    lines.extend(f"- Metric: {item}" for item in report.execution.metrics)
    lines.extend(f"- Warning: {item}" for item in report.execution.warnings)
    lines.extend(["", "## Multimodal Validation", ""])
    if not report.multimodal:
        lines.append("- N/A")
    for item in report.multimodal:
        lines.append(
            f"- {item.artifact_id}: {item.modality}, source={item.source}, "
            f"page={item.page or 'unavailable'}, bbox={item.bbox or 'unavailable'}, "
            f"units={','.join(item.units) or 'unavailable'}, confidence={item.confidence}, "
            f"status={item.validation_status}"
        )
    lines.extend(["", "## Known Limitations", ""])
    lines.extend(f"- {item}" for item in report.known_limitations or ["N/A"])
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def render_report_pdf(report: CanonicalReport, output_path: str | Path) -> Path:
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates = [
        os.getenv("SAGE_PDF_FONT_PATH", ""),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    cjk_font = "STSong-Light"
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont("SAGE-CJK", candidate))
        except Exception:  # noqa: BLE001 - malformed optional font falls through
            continue
        cjk_font = "SAGE-CJK"
        break
    if cjk_font == "STSong-Light":
        pdfmetrics.registerFont(UnicodeCIDFont(cjk_font))
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "BodyCJK",
        parent=styles["BodyText"],
        fontName=cjk_font,
        fontSize=9,
        leading=12,
        spaceAfter=3,
    )
    ascii_body = ParagraphStyle(
        "BodyASCII", parent=body, fontName="Helvetica", fontSize=8.5, leading=11.5
    )
    title = ParagraphStyle(
        "TitleCJK",
        parent=styles["Title"],
        fontName=cjk_font,
        fontSize=18,
        leading=21,
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    heading = ParagraphStyle(
        "HeadingCJK",
        parent=styles["Heading2"],
        fontName=cjk_font,
        fontSize=12,
        leading=15,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True,
    )

    def p(text: object, style=body):
        return Paragraph(html.escape(str(text)), style)

    actual = (
        "YES"
        if report.execution.actual_execution is True
        else "NO"
        if report.execution.actual_execution is False
        else "UNAVAILABLE"
    )
    story = [
        p(report.title, title),
        p(f"Truth status: {report.truth_status}", ascii_body),
        p(f"ACTUAL EXECUTION: {actual}", ascii_body),
        p(
            f"Job {report.job_id} | Question {report.question_id} | Run {report.run_id}",
            ascii_body,
        ),
        p(f"Version: {report.version_id or 'unavailable'}", ascii_body),
        p(f"Generated: {report.generated_at.isoformat()}", ascii_body),
        Spacer(1, 4),
        p("Scientific Question", heading),
        p(report.question),
        p(f"Domain: {report.domain}", ascii_body),
        p("Hypotheses", heading),
    ]
    story.extend(p(f"- {item}") for item in report.hypotheses or ["N/A"])
    story.append(p("Methods", heading))
    story.extend(p(f"- {item}") for item in report.methods or ["N/A"])
    story.append(p("Evidence", heading))
    if not report.evidence:
        story.append(p("N/A"))
    for item in report.evidence:
        story.append(p(f"{item.evidence_id}: {item.title}", heading))
        story.append(p(item.quoted_text))
        story.append(p(f"Locator: {item.locator}", ascii_body))
        story.append(
            p(
                f"Verification: {item.verification_status} | Confidence: "
                f"{item.confidence if item.confidence is not None else 'unavailable'}",
                ascii_body,
            )
        )
        href = item.url or (f"https://doi.org/{item.doi}" if item.doi else None)
        if href:
            safe_href = html.escape(href, quote=True)
            story.append(
                Paragraph(
                    f'<link href="{safe_href}" color="blue">{safe_href}</link>',
                    ascii_body,
                )
            )
    story.append(p("Reviewer Issues", heading))
    if not report.reviewer_issues:
        story.append(p("N/A"))
    for item in report.reviewer_issues:
        story.append(p(f"[{item.severity}/{item.status}] {item.issue_id}: {item.summary}"))
        if item.resolution_note:
            story.append(p(f"Resolution: {item.resolution_note}"))
    story.append(p("Human Feedback", heading))
    if not report.feedback:
        story.append(p("N/A"))
    for item in report.feedback:
        story.append(
            p(
                f"[{item.status}] {item.feedback_id} -> {item.target_version_id}",
                ascii_body,
            )
        )
        if item.decision_reason:
            story.append(p(f"Decision: {item.decision_reason}"))
    story.append(p("Validation Gates", heading))
    if not report.gates:
        story.append(p("N/A"))
    for gate in report.gates:
        story.append(
            p(
                f"{gate.gate_id}: {'passed' if gate.passed else 'blocked'} "
                f"({gate.severity})",
                ascii_body,
            )
        )
        story.extend(p(f"Finding: {finding}") for finding in gate.findings)
    story.append(p("Execution", heading))
    story.append(p(f"Availability: {report.execution.availability}", ascii_body))
    story.append(p(f"Status: {report.execution.status}", ascii_body))
    story.append(
        p(
            f"Execution ID: {report.execution.execution_id or 'unavailable'}",
            ascii_body,
        )
    )
    story.append(p(f"ACTUAL EXECUTION: {actual}", ascii_body))
    story.extend(p(f"Metric: {item}") for item in report.execution.metrics)
    story.extend(p(f"Warning: {item}") for item in report.execution.warnings)
    story.append(p("Multimodal Validation", heading))
    if not report.multimodal:
        story.append(p("N/A"))
    for item in report.multimodal:
        story.append(
            p(
                f"{item.artifact_id}: {item.modality}; source={item.source}; "
                f"page={item.page or 'unavailable'}; bbox={item.bbox or 'unavailable'}; "
                f"units={','.join(item.units) or 'unavailable'}; confidence={item.confidence}; "
                f"status={item.validation_status}",
                ascii_body,
            )
        )
    story.append(p("Known Limitations", heading))
    story.extend(p(f"- {item}") for item in report.known_limitations or ["N/A"])

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawString(18 * mm, 10 * mm, f"Content SHA256: {report.content_sha256}")
        canvas.drawRightString(192 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=report.title,
        author="SAGE125 AI Scientist",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output
