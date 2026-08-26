# -*- coding: utf-8 -*-
"""首页统计：一次计算、重复读取。

权威口径见 CAPTAIN-LOCAL-SAGE125-HOMEPAGE-COMPLETE-FIX-09 §4–§6。
本模块不硬编码 125/50/100%，不读取旧 candidate，不在每次进入首页扫描 125 题。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ui.results_root import EXPECTED_QUESTION_IDS, ResultsRootResolution, resolve_results_root

SCHEMA_VERSION = "sage125-ui-summary-v3"
UI_SUMMARY_PATH = Path(__file__).resolve().parents[2] / "data" / "ui" / "ui_summary.json"

_NOTE_PAIR = re.compile(r"([A-Za-z0-9_]+)=([^;]+)")
_CROSS_Q = re.compile(r"Q(\d{3})")
_QUALIFIED_VERIFY = {
    "fulltext_verified",
    "verified",
    "pass",
    "passed",
    "validated",
    "ok",
    "eligible",
}
_REJECT_SOURCE_TYPES = {"metadata_only", "question_source"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_note(note: str) -> dict[str, str]:
    return {key.strip(): value.strip() for key, value in _NOTE_PAIR.findall(note or "")}


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _file_listing_digest(root: Path) -> str:
    lines: list[str] = []
    for qid in EXPECTED_QUESTION_IDS:
        qdir = root / qid
        for name in ("evidence_cards.json", "result.json"):
            path = qdir / name
            try:
                stat = path.stat()
                lines.append(f"{qid}/{name}:{int(stat.st_mtime_ns)}:{stat.st_size}")
            except OSError:
                lines.append(f"{qid}/{name}:missing")
    return _sha256_text("\n".join(lines))


def _catalog_digest(catalog_path: Path) -> str:
    try:
        return _sha256_text(catalog_path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def _manifest_digest(manifest_path: Path | None) -> str:
    if not manifest_path or not manifest_path.exists():
        return ""
    try:
        return _sha256_text(manifest_path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def _card_id(card: dict[str, Any]) -> str:
    return str(card.get("evidence_id") or card.get("id") or "").strip()


def _card_quote(card: dict[str, Any]) -> str:
    return str(card.get("quote") or card.get("quoted_text") or "").strip()


def _card_locator(card: dict[str, Any], note: dict[str, str]) -> Any:
    if _nonempty(card.get("locator")):
        return card.get("locator")
    return note.get("locator")


def _card_sha(card: dict[str, Any], note: dict[str, str]) -> str:
    return str(card.get("content_sha256") or note.get("content_sha256") or "").strip()


def _verification_ok(card: dict[str, Any], note: dict[str, str]) -> bool:
    raw = str(
        card.get("source_verification_status")
        or card.get("eligibility_status")
        or note.get("eligibility_status")
        or note.get("source_verification_status")
        or ""
    ).strip().lower()
    if not raw:
        return False
    return raw.replace(" ", "_") in _QUALIFIED_VERIFY


def _off_topic(card: dict[str, Any]) -> bool:
    status = str(card.get("topic_relevance_status") or card.get("relevance_status") or "").strip().upper()
    return status == "OFF_TOPIC"


def _metadata_or_question_source(card: dict[str, Any]) -> bool:
    source_type = str(card.get("source_type") or "").strip().lower()
    kind = str(card.get("evidence_kind") or card.get("kind") or "").strip().lower()
    flags = {str(item).strip().upper() for item in (card.get("flags") or [])}
    if "METADATA_ONLY" in flags or "QUESTION_SOURCE" in flags:
        return True
    return source_type in _REJECT_SOURCE_TYPES or kind in _REJECT_SOURCE_TYPES


def _cross_question(card_id: str, question_id: str) -> bool:
    matches = {f"Q{item}" for item in _CROSS_Q.findall(card_id.upper())}
    return bool(matches) and question_id.upper() not in matches


def is_traceable_evidence_card(card: dict[str, Any], question_id: str) -> bool:
    if not isinstance(card, dict):
        return False
    note = _parse_note(str(card.get("reliability_note") or ""))
    evidence_id = _card_id(card)
    card_qid = str(card.get("question_id") or question_id).strip().upper()
    source_id = str(card.get("source_id") or card.get("doi") or card.get("url") or "").strip()
    title = str(card.get("title") or "").strip()
    quote = _card_quote(card)
    locator = _card_locator(card, note)
    doi = str(card.get("doi") or "").strip()
    url = str(card.get("url") or "").strip()
    sha = _card_sha(card, note)
    if not evidence_id or not source_id or not title or not quote or not locator or not sha:
        return False
    if card_qid != question_id.upper():
        return False
    if not doi and not url:
        return False
    if not _verification_ok(card, note):
        return False
    if _off_topic(card) or _metadata_or_question_source(card):
        return False
    if _cross_question(evidence_id, question_id):
        return False
    return True


def _plan_complete(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict):
        return False
    objective = result.get("problem_statement") or result.get("paper_title") or result.get("research_objective")
    method = result.get("methods") or result.get("technical_details") or result.get("method")
    data = result.get("datasets") or result.get("data") or result.get("materials")
    hyps = result.get("generated_hypotheses") or result.get("hypotheses") or []
    has_prediction = False
    has_support = False
    has_falsify = False
    if isinstance(hyps, list):
        for hyp in hyps:
            if not isinstance(hyp, dict):
                continue
            if _nonempty(hyp.get("falsifiable_prediction") or hyp.get("testable_prediction")):
                has_prediction = True
                has_falsify = True
            if _nonempty(hyp.get("supporting_evidence_ids") or hyp.get("support_condition")):
                has_support = True
            if _nonempty(hyp.get("contradicted_by_evidence_ids") or hyp.get("refutation_condition")):
                has_falsify = True
    return all([_nonempty(objective), _nonempty(method), _nonempty(data), has_prediction, has_support, has_falsify])


def _collect_links(result: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    if not isinstance(result, dict):
        return ids
    hyps = result.get("generated_hypotheses") or result.get("hypotheses") or []
    if isinstance(hyps, list):
        for hyp in hyps:
            if not isinstance(hyp, dict):
                continue
            for key in ("supporting_evidence_ids", "evidence_ids"):
                values = hyp.get(key) or []
                if isinstance(values, list):
                    ids.extend(str(item).strip() for item in values if str(item).strip())
    for key in ("claim_evidence_links", "evidence_links"):
        links = result.get(key) or []
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict):
                    eid = str(link.get("evidence_id") or link.get("id") or "").strip()
                    if eid:
                        ids.append(eid)
                elif str(link).strip():
                    ids.append(str(link).strip())
    references = result.get("references") or []
    if isinstance(references, list):
        for ref in references:
            if isinstance(ref, dict):
                eid = str(ref.get("id") or ref.get("evidence_id") or "").strip()
                if eid:
                    ids.append(eid)
    plan = result.get("research_plan") or {}
    if isinstance(plan, dict):
        for key in ("evidence_ids", "supporting_evidence_ids"):
            values = plan.get(key) or []
            if isinstance(values, list):
                ids.extend(str(item).strip() for item in values if str(item).strip())
    claims = result.get("claims") or result.get("factual_claims") or []
    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            for key in ("evidence_ids", "supporting_evidence_ids"):
                values = claim.get(key) or []
                if isinstance(values, list):
                    ids.extend(str(item).strip() for item in values if str(item).strip())
    datasets = result.get("datasets") or {}
    if isinstance(datasets, dict):
        source = datasets.get("source") or []
        if isinstance(source, list):
            for item in source:
                if isinstance(item, dict):
                    eid = str(item.get("id") or item.get("evidence_id") or "").strip()
                    if eid:
                        ids.append(eid)
    return ids


def compute_ui_summary(resolution: ResultsRootResolution | None = None) -> dict[str, Any]:
    resolved = resolution or resolve_results_root()
    catalog_digest = _catalog_digest(resolved.catalog_path)
    manifest_digest = _manifest_digest(resolved.manifest_path)
    if not resolved.intact or resolved.results_root is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "results_root": str(resolved.results_root) if resolved.results_root else None,
            "results_root_digest": "",
            "catalog_digest": catalog_digest,
            "manifest_digest": manifest_digest,
            "status": "source_invalid",
            "error": resolved.error or "数据源未通过完整性校验",
            "missing_question_ids": resolved.missing_question_ids,
            "official_question_count": len(set(resolved.catalog_ids)) or None,
            "traceable_evidence_count": None,
            "traceable_evidence_question_count": None,
            "invalid_evidence_card_count": None,
            "research_plan_count": None,
            "total_supporting_evidence_links": None,
            "resolved_supporting_evidence_links": None,
            "unresolved_supporting_evidence_links": None,
            "evidence_link_coverage": None,
            "evidence_link_coverage_status": "error",
        }

    root = resolved.results_root
    files_digest = _file_listing_digest(root)
    seen_evidence: set[tuple[str, str]] = set()
    questions_with_evidence: set[str] = set()
    invalid_cards = 0
    plan_count = 0
    total_links = 0
    resolved_links = 0

    for qid in EXPECTED_QUESTION_IDS:
        cards_raw = _read_json(root / qid / "evidence_cards.json")
        cards = cards_raw if isinstance(cards_raw, list) else []
        valid_ids: set[str] = set()
        for card in cards:
            if not isinstance(card, dict):
                invalid_cards += 1
                continue
            eid = _card_id(card)
            if is_traceable_evidence_card(card, qid):
                key = (qid, eid)
                if key not in seen_evidence:
                    seen_evidence.add(key)
                    questions_with_evidence.add(qid)
                    valid_ids.add(eid)
            else:
                invalid_cards += 1

        result = _read_json(root / qid / "result.json")
        if isinstance(result, dict) and _plan_complete(result):
            plan_count += 1
        for eid in _collect_links(result if isinstance(result, dict) else {}):
            total_links += 1
            if eid in valid_ids:
                resolved_links += 1

    if total_links == 0:
        coverage = None
        coverage_status = "unavailable"
    else:
        coverage = round(100.0 * resolved_links / total_links, 1)
        coverage_status = "calculated"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "results_root": str(root),
        "results_root_digest": files_digest,
        "catalog_digest": catalog_digest,
        "manifest_digest": manifest_digest,
        "status": "calculated",
        "error": None,
        "missing_question_ids": [],
            "official_question_count": len(set(resolved.catalog_ids)),
        "traceable_evidence_count": len(seen_evidence),
        "traceable_evidence_question_count": len(questions_with_evidence),
        "invalid_evidence_card_count": invalid_cards,
        "research_plan_count": plan_count,
        "total_supporting_evidence_links": total_links,
        "resolved_supporting_evidence_links": resolved_links,
        "unresolved_supporting_evidence_links": total_links - resolved_links,
        "evidence_link_coverage": coverage,
        "evidence_link_coverage_status": coverage_status,
    }


def _needs_rebuild(existing: dict[str, Any], resolved: ResultsRootResolution) -> bool:
    if existing.get("schema_version") != SCHEMA_VERSION:
        return True
    if existing.get("results_root") != (str(resolved.results_root) if resolved.results_root else None):
        return True
    if existing.get("manifest_digest") != _manifest_digest(resolved.manifest_path):
        return True
    if existing.get("catalog_digest") != _catalog_digest(resolved.catalog_path):
        return True
    return False


def load_or_build_ui_summary(*, force: bool = False) -> dict[str, Any]:
    resolved = resolve_results_root()
    if UI_SUMMARY_PATH.exists() and not force:
        existing = _read_json(UI_SUMMARY_PATH)
        if isinstance(existing, dict) and not _needs_rebuild(existing, resolved):
            return existing
    summary = compute_ui_summary(resolved)
    UI_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    UI_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
