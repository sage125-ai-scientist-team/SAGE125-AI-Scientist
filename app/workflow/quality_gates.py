"""
app.workflow.quality_gates —— 质量门（证据、Results、Schema、模型合规、引用完整性）。

每个质量门返回统一结构：{"passed": bool, "errors": [], "warnings": [], "score": 0-1}。
run_all_quality_gates 汇总所有门的结果，供 SchemaValidator 与 pipeline 做保守判定。
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import FORBIDDEN_MODEL_KEYWORDS
from app.core.evidence_links import canonical_evidence_link
from app.core.logging import get_logger

# 模块级日志器。
logger = get_logger("workflow.quality_gates")

# 虚构量化指标检测（与 schemas 保持一致的语义）。
_FAKE_METRIC_PATTERN = re.compile(
    r"(auroc|auprc|auc|accuracy|acc|f1|precision|recall|dice|iou|bleu|rouge|mae|rmse|r2)"
    r"\s*[=:：]?\s*(0?\.\d+|\d{1,3}\s*%|\d\.\d+)",
    re.IGNORECASE,
)
# 标准 pending 句子关键片段。
_PENDING_MARK = "待执行验证实验"
# DOI 基本格式。
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")


def _as_dict(plan: Any) -> dict:
    """将 ResearchPlan 对象或 dict 统一为 dict。"""
    return plan.model_dump() if hasattr(plan, "model_dump") else dict(plan)


def _card_dump(card: Any) -> dict:
    """将 EvidenceCard 对象或 dict 统一为 dict。"""
    return card.model_dump() if hasattr(card, "model_dump") else dict(card)


def _is_metadata_only(card: dict) -> bool:
    """OpenAlex/Crossref title-only records are metadata, not quoted evidence."""

    source = str(card.get("source_type") or "").lower()
    title = " ".join(str(card.get("title") or "").split()).casefold()
    quoted = " ".join(str(card.get("quoted_text") or "").split()).casefold()
    return source in {"openalex", "crossref"} and bool(title) and quoted == title


def _is_question_source(card: dict) -> bool:
    """题目册仅用于定义问题，禁止作为研究证据或参考文献。"""
    source = str(card.get("source_type") or "").strip().lower()
    title = str(card.get("title") or "").strip().lower()
    note = str(card.get("reliability_note") or "").strip().lower()
    return (
        source == "booklet"
        or "source_role=question_source" in note
        or "sjtu-booklet.pdf" in title
        or "sjtu-booklet.pdf" in note
    )


def check_evidence_grounding(
    plan: Any,
    evidence_cards: list,
    hypothesis_generation: dict | None = None,
    evidence_extraction: dict | None = None,
) -> dict:
    """
    检查证据落地：references 是否来自 EvidenceCards；假设是否有支撑证据。

    参数：
        plan:           ResearchPlan（对象或 dict）。
        evidence_cards: 证据卡列表。

    返回：
        质量门结果 dict。
    """
    p = _as_dict(plan)
    errors: list[str] = []
    warnings: list[str] = []
    # 已知证据 ID 集合。
    card_map = {_card_dump(c).get("id"): _card_dump(c) for c in evidence_cards}
    known_ids = set(card_map)
    for evidence_id, card in card_map.items():
        if _is_question_source(card):
            errors.append(f"evidence {evidence_id} 来自 sjtu-booklet.pdf；题源不能作为研究证据。")
    # references 的 id 必须来自证据集合。
    ref_ids = [(_card_dump(r).get("id")) for r in p.get("references", [])]
    for rid in ref_ids:
        if rid not in known_ids:
            errors.append(f"reference {rid} 不在 EvidenceCards 中。")
    # 每个候选假设必须保留明确的支撑证据链接；不再只检查报告级 references。
    hyps = (hypothesis_generation or {}).get("hypotheses") or p.get("generated_hypotheses", [])
    for idx, hyp in enumerate(hyps, start=1):
        h = hyp if isinstance(hyp, dict) else _card_dump(hyp)
        support = list(h.get("supporting_evidence_ids") or [])
        contradicted = list(h.get("contradicted_by_evidence_ids") or [])
        if not support:
            errors.append(f"hypothesis {idx} 缺少 supporting_evidence_ids。")
        for eid in support + contradicted:
            if eid not in known_ids:
                errors.append(f"hypothesis {idx} 引用了不存在的 evidence_id：{eid}")
        for eid in support:
            card = card_map.get(eid, {})
            if not (card.get("quoted_text") or "").strip():
                errors.append(f"hypothesis {idx} 的支撑证据 {eid} 缺少可核验原文。")
            elif _is_metadata_only(card):
                errors.append(f"hypothesis {idx} 的支撑证据 {eid} 仅含文献元数据标题，不能充当原文证据。")
            if float(card.get("relevance_score") or 0) < 0.25:
                warnings.append(f"hypothesis {idx} 的支撑证据 {eid} 相关性偏低。")

    # 事实层的 evidence_ids 同样必须落在证据池内。
    extraction = evidence_extraction or {}
    for bucket in ("established_facts", "disputed_points"):
        for idx, fact in enumerate(extraction.get(bucket, []) or [], start=1):
            ids = list((fact or {}).get("evidence_ids") or [])
            if bucket == "established_facts" and not ids:
                errors.append(f"{bucket} {idx} 缺少 evidence_ids。")
            for eid in ids:
                if eid not in known_ids:
                    errors.append(f"{bucket} {idx} 引用了不存在的 evidence_id：{eid}")
                elif _is_metadata_only(card_map.get(eid, {})):
                    errors.append(f"{bucket} {idx} 使用的 {eid} 仅含元数据标题，不能证明该事实。")
    if not p.get("references"):
        warnings.append("references 为空（可能为 needs_data）。")
    # 评分：无错误且有引用则高分。
    score = 1.0 if not errors and p.get("references") else (0.5 if not errors else 0.0)
    return {"passed": not errors, "errors": errors, "warnings": warnings, "score": score}


def check_results_integrity(plan: Any) -> dict:
    """
    检查 Results 完整性：未执行时必须 pending，且不得出现虚构指标。

    参数：
        plan: ResearchPlan（对象或 dict）。

    返回：
        质量门结果 dict。
    """
    p = _as_dict(plan)
    errors: list[str] = []
    warnings: list[str] = []
    results = p.get("results", "") or ""
    actual = bool(p.get("actual_execution"))
    # 未真实执行时：必须 pending，且不得含虚构指标。
    if not actual:
        if _PENDING_MARK not in results:
            errors.append("未真实执行但 Results 未标注 pending。")
        m = _FAKE_METRIC_PATTERN.search(results)
        if m:
            errors.append(f"Results 含疑似虚构指标：{m.group(0)}")
    # 声称 validated 但无执行元数据。
    if p.get("validation_status") == "validated" and not actual:
        errors.append("validation_status=validated 但 actual_execution 非真。")
    score = 1.0 if not errors else 0.0
    return {"passed": not errors, "errors": errors, "warnings": warnings, "score": score}


def check_research_plan_schema(plan: Any) -> dict:
    """
    检查结构完整性：datasets(source/target)、experiments(baselines/metrics)、
    references、reproducibility_checklist。

    参数：
        plan: ResearchPlan（对象或 dict）。

    返回：
        质量门结果 dict。
    """
    p = _as_dict(plan)
    errors: list[str] = []
    warnings: list[str] = []
    datasets = p.get("datasets", {}) or {}
    experiments = p.get("experiments", {}) or {}
    # datasets 必须含 source 与 target。
    for k in ("source", "target"):
        if k not in datasets:
            errors.append(f"datasets 缺少 {k}。")
    # experiments 必须含 baselines 与 metrics。
    for k in ("baselines", "metrics"):
        if k not in experiments:
            errors.append(f"experiments 缺少 {k}。")
    # reproducibility_checklist 建议非空。
    if not p.get("reproducibility_checklist"):
        warnings.append("reproducibility_checklist 为空。")
    score = 1.0 if not errors else max(0.0, 1.0 - 0.25 * len(errors))
    return {"passed": not errors, "errors": errors, "warnings": warnings, "score": score}


def check_model_compliance(agent_trace: list) -> dict:
    """
    检查模型合规：所有生成模型必须为 Qwen；禁止非千问模型名。

    参数：
        agent_trace: AgentTraceEvent dict 列表。

    返回：
        质量门结果 dict。
    """
    errors: list[str] = []
    warnings: list[str] = []
    for ev in agent_trace:
        model = (ev.get("model_name") or "").lower()
        # 命中禁用关键字即违规。
        if any(k in model for k in FORBIDDEN_MODEL_KEYWORDS):
            errors.append(f"检测到非千问模型：{ev.get('model_name')}（agent={ev.get('agent_name')}）")
        # 生成模型必须以 qwen 开头。
        elif model and not model.startswith("qwen"):
            errors.append(f"非 Qwen 生成模型：{ev.get('model_name')}")
    score = 1.0 if not errors else 0.0
    return {"passed": not errors, "errors": errors, "warnings": warnings, "score": score}


def check_reference_integrity(plan: Any, evidence_cards: list) -> dict:
    """
    检查引用完整性：DOI 格式、URL 不伪造、title 非空、mock 证据标记。

    参数：
        plan:           ResearchPlan（对象或 dict）。
        evidence_cards: 证据卡列表。

    返回：
        质量门结果 dict。
    """
    p = _as_dict(plan)
    errors: list[str] = []
    warnings: list[str] = []
    card_map = {_card_dump(card).get("id"): _card_dump(card) for card in evidence_cards}
    for ref in p.get("references", []):
        r = _card_dump(ref)
        if _is_question_source(r):
            errors.append(f"reference {r.get('id')} 来自 sjtu-booklet.pdf；题源不能作为参考文献。")
        # 标题不得为空。
        if not (r.get("title") or "").strip():
            errors.append("存在空标题的 reference。")
        # DOI 若存在需合法。
        doi = r.get("doi")
        if doi and not _DOI_PATTERN.match(str(doi).strip()):
            errors.append(f"非法 DOI：{doi}")
        # ReportWriter may choose evidence IDs, but it may not rewrite the
        # source metadata behind an existing ID.
        original = card_map.get(r.get("id"))
        if original:
            for field in ("source_type", "title", "doi", "url"):
                if (r.get(field) or None) != (original.get(field) or None):
                    errors.append(f"reference {r.get('id')} 的 {field} 与 EvidenceCard 不一致。")
        source = str(r.get("source_type") or "").lower()
        if source in {"arxiv", "openalex", "crossref"} and (r.get("doi") or r.get("url")):
            if canonical_evidence_link(r) is None:
                errors.append(f"reference {r.get('id')} 的外部标识未通过安全校验。")
        if _is_metadata_only(r):
            warnings.append(f"reference {r.get('id')} 仅为元数据记录；需打开原文核验内容。")
        # mock 证据仅告警（提示不可作为真实结论）。
        if "mock_for_testing" in (r.get("reliability_note") or ""):
            warnings.append(f"reference {r.get('id')} 为 mock 证据（不可作为真实结论）。")
    score = 1.0 if not errors else 0.0
    return {"passed": not errors, "errors": errors, "warnings": warnings, "score": score}


def run_all_quality_gates(
    plan: Any,
    evidence_cards: list,
    agent_trace: list,
    *,
    hypothesis_generation: dict | None = None,
    evidence_extraction: dict | None = None,
) -> dict:
    """
    运行全部质量门并汇总。

    参数：
        plan:           ResearchPlan（对象或 dict）。
        evidence_cards: 证据卡列表。
        agent_trace:    AgentTraceEvent dict 列表。

    返回：
        {"passed": bool, "gates": {name: result}, "errors":[], "warnings":[]}
    """
    gates = {
        "evidence_grounding": check_evidence_grounding(
            plan,
            evidence_cards,
            hypothesis_generation=hypothesis_generation,
            evidence_extraction=evidence_extraction,
        ),
        "results_integrity": check_results_integrity(plan),
        "research_plan_schema": check_research_plan_schema(plan),
        "model_compliance": check_model_compliance(agent_trace),
        "reference_integrity": check_reference_integrity(plan, evidence_cards),
    }
    # 汇总所有错误与警告。
    all_errors = [e for g in gates.values() for e in g["errors"]]
    all_warnings = [w for g in gates.values() for w in g["warnings"]]
    passed = all(g["passed"] for g in gates.values())
    return {"passed": passed, "gates": gates, "errors": all_errors, "warnings": all_warnings}
