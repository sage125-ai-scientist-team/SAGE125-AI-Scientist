"""
app.exporters.markdown_exporter —— ResearchPlan 的 Markdown 导出。

将 ResearchPlan（对象或 dict）渲染为结构化 Markdown 文件，用于答辩与提交。

反造假约束：
    - 不改写 EvidenceCard.quoted_text；
    - DOI/URL 不存在写 "Not available"，绝不伪造；
    - mock 证据显示 mock_for_testing；
    - 无真实实验时 Results 保持 pending 说明；
    - 不写入完整本地路径或 API Key。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

# 模块级日志器。
logger = get_logger("exporters.markdown")

# 无真实实验时的标准 pending 句子。
PENDING_RESULTS = (
    "当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。"
)


def _as_dict(plan: Any) -> dict:
    """将 ResearchPlan 对象或 dict 统一为 dict。"""
    return plan.model_dump() if hasattr(plan, "model_dump") else dict(plan)


def _fmt(value: Any) -> str:
    """将任意值格式化为 Markdown 友好字符串。"""
    # dict/list 用缩进 JSON 展示。
    if isinstance(value, (dict, list)):
        return "\n\n```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```\n"
    return "" if value is None else str(value)


def render_research_plan_markdown(plan: Any) -> str:
    """
    将 ResearchPlan 渲染为 Markdown 字符串。

    参数：
        plan: ResearchPlan 对象或 dict。

    返回：
        Markdown 文本。
    """
    p = _as_dict(plan)
    lines: list[str] = []
    add = lines.append

    # 标题与基础信息。
    add(f"# {p.get('paper_title') or p.get('input_question') or 'Research Plan'}\n")
    add("## Input Question")
    add(_fmt(p.get("input_question")) + "\n")
    add("## Domain")
    add(_fmt(p.get("domain")) + "\n")
    add("## Validation Status")
    add(_fmt(p.get("validation_status")) + "\n")
    add("## Problem Statement")
    add(_fmt(p.get("problem_statement")) + "\n")
    add("## Rationale")
    add(_fmt(p.get("rationale")) + "\n")

    # 假设。
    add("## Generated Hypotheses\n")
    for i, h in enumerate(p.get("generated_hypotheses", []) or [], start=1):
        add(f"### Hypothesis {i}")
        add(f"- **Hypothesis**: {_fmt(h.get('hypothesis'))}")
        add(f"- **Mechanism**: {_fmt(h.get('mechanism'))}")
        add(f"- **Falsifiable Prediction**: {_fmt(h.get('falsifiable_prediction'))}")
        obs = "；".join(h.get("required_observations", []) or [])
        add(f"- **Required Observations**: {obs}")
        add(f"- **Risk of Being Wrong**: {_fmt(h.get('risk_of_being_wrong'))}\n")

    # 技术细节与数据集。
    add("## Technical Details")
    add(_fmt(p.get("technical_details")) + "\n")
    datasets = p.get("datasets", {}) or {}
    add("## Datasets")
    add("### Source")
    add(_fmt(datasets.get("source")) + "\n")
    add("### Target")
    add(_fmt(datasets.get("target")) + "\n")

    # 摘要与方法。
    add("## Paper Abstract")
    add(_fmt(p.get("paper_abstract")) + "\n")
    add("## Methods")
    add(_fmt(p.get("methods")) + "\n")

    # 实验。
    experiments = p.get("experiments", {}) or {}
    add("## Experiments")
    add("### Baselines")
    add(_fmt(experiments.get("baselines")) + "\n")
    add("### Metrics")
    add(_fmt(experiments.get("metrics")) + "\n")
    add("### Ablation")
    add(_fmt(experiments.get("ablation")) + "\n")
    add("### Validation Protocol")
    add(_fmt(experiments.get("validation_protocol")) + "\n")

    # 结果（pending 保持）。
    add("## Results")
    results = p.get("results", "") or ""
    if not p.get("actual_execution") and PENDING_RESULTS not in results:
        # 兜底：无真实执行时确保 pending。
        results = PENDING_RESULTS
    add(_fmt(results) + "\n")

    # 参考文献（来自 EvidenceCards）。
    add("## References")
    refs = p.get("references", []) or []
    if refs:
        for r in refs:
            rd = r if isinstance(r, dict) else (r.model_dump() if hasattr(r, "model_dump") else {})
            doi = rd.get("doi") or "Not available"
            url = rd.get("url") or "Not available"
            authors = ", ".join(rd.get("authors", []) or []) or "Not available"
            mock = " [mock_for_testing]" if "mock_for_testing" in (rd.get("reliability_note") or "") else ""
            add(f"- **{rd.get('id')}**{mock} · {rd.get('source_type')} · {rd.get('title')}")
            add(f"  - authors: {authors} · year: {rd.get('year') or 'Not available'}")
            add(f"  - url: {url} · doi: {doi}")
            add(f"  - reliability_note: {rd.get('reliability_note') or ''}")
    else:
        add("- references 待检索/待验证。")
    add("")

    # 评审 / 修订 / 可复现。
    add("## Reviewer Comments")
    for c in p.get("reviewer_comments", []) or []:
        add(f"- {c}")
    add("")
    add("## Revision History")
    for c in p.get("revision_history", []) or []:
        add(f"- {c}")
    add("")
    add("## Reproducibility Checklist")
    for c in p.get("reproducibility_checklist", []) or []:
        add(f"- {c}")
    add("")

    return "\n".join(lines) + "\n"


def export_research_plan_markdown(plan: Any, output_path: Path) -> Path:
    """
    将 ResearchPlan 导出为 Markdown 文件。

    参数：
        plan:        ResearchPlan 对象或 dict。
        output_path: 目标文件路径。

    返回：
        实际写入的文件路径。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_research_plan_markdown(plan), encoding="utf-8")
    logger.info("已导出 Markdown：%s", output_path.name)
    return output_path


# ---- 向后兼容别名（供旧调用/artifacts 探测使用）----

def render_markdown(plan: Any) -> str:
    """向后兼容别名：渲染 ResearchPlan 为 Markdown 字符串。"""
    return render_research_plan_markdown(plan)


def export_markdown(plan: Any, out_path: str | Path) -> Path:
    """向后兼容别名：导出 ResearchPlan 为 Markdown 文件。"""
    return export_research_plan_markdown(plan, Path(out_path))
