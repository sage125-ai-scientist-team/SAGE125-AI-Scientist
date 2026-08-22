"""Deterministic Formal 125 pre-review, captain decision contract, and RC helpers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.formal125 import REQUIRED_RESULT_FILES
from app.formal125.continuous_fast import MANUAL_REVIEW_24, SCIENTIFIC_PRODUCER_SHA, scan_text_for_secrets
from app.formal125.hashes import sha256_canonical_json, sha256_file
from app.formal125.actual_run import atomic_write_json


ORIGINAL_CANDIDATE = Path(r"D:\SAGE125_Local_Runs\formal_125_candidate_20260822-155218")
STAMP = "20260822-201733"
START_SHA = "6d2686916e0c12d71eb5e9f45e0cc992d8ead5d7"
PROJECT_PROVIDER_CALLS_BEFORE = 1218
MAX_NEW_PROVIDER_CALLS = 300
MAX_NEW_INPUT_TOKENS = 2_500_000
MAX_NEW_OUTPUT_TOKENS = 500_000
DECISIONS = (
    "ACCEPT_SUCCEEDED",
    "ACCEPT_GENUINE_PARTIAL",
    "ACCEPT_GENUINE_BLOCKED",
    "REQUEST_REMEDIATION",
    "SYSTEMIC_REJECT",
)
SECRET_RE = re.compile(
    r"(?i)(?:api[_-]?key|authorization|bearer|password|secret)\s*[:=]\s*\S+|sk-[A-Za-z0-9]{8,}|workspace_id\s*[:=]\s*\S+"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def official_ids() -> list[str]:
    return [f"Q{i:03d}" for i in range(1, 126)]


def load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_fingerprint(root: Path) -> str:
    payload = {}
    for qid in official_ids():
        path = root / qid / "package_manifest.json"
        payload[qid] = sha256_file(path) if path.is_file() else None
    return sha256_canonical_json(payload)


def _locator_ok(card: Mapping[str, Any]) -> bool:
    if card.get("locator"):
        return True
    note = str(card.get("reliability_note") or "")
    return "locator=" in note


def _quote_ok(card: Mapping[str, Any]) -> bool:
    return bool(str(card.get("quote") or card.get("quoted_text") or "").strip())


def pre_review_question(candidate_root: Path, catalog_item: Mapping[str, Any]) -> dict[str, Any]:
    qid = str(catalog_item["question_id"])
    qdir = candidate_root / qid
    findings: list[str] = []
    critical = 0
    high = 0
    medium = 0
    manifest = load_json(qdir / "package_manifest.json") or {}
    validation = load_json(qdir / "validation.json") or {}
    result = load_json(qdir / "result.json") or {}
    cards = load_json(qdir / "evidence_cards.json") or []
    audit = load_json(qdir / "provider_audit.json") or {}
    if not isinstance(cards, list):
        cards = []
    status = str(manifest.get("status") or "unknown")
    missing = [name for name in REQUIRED_RESULT_FILES if not (qdir / name).is_file() or (qdir / name).stat().st_size == 0]
    if missing:
        findings.append(f"missing_files:{','.join(missing)}")
        high += 1
    pdf = qdir / "result.pdf"
    pdf_ok = pdf.is_file() and pdf.read_bytes()[:4] == b"%PDF"
    if not pdf_ok:
        findings.append("pdf_not_openable")
        high += 1
    checksum_bad = 0
    for line in (qdir / "checksums.sha256").read_text(encoding="utf-8").splitlines() if (qdir / "checksums.sha256").is_file() else []:
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        path = qdir / name.strip()
        if path.is_file() and sha256_file(path) != digest:
            checksum_bad += 1
    if checksum_bad:
        findings.append(f"checksum_mismatch:{checksum_bad}")
        high += 1
    title = str(result.get("input_question") or result.get("paper_title") or "")
    official = str(catalog_item.get("original_title") or "")
    if official and title and official.casefold() not in title.casefold() and title.casefold() not in official.casefold():
        if status not in {"blocked", "failed"}:
            findings.append("title_semantic_drift")
            medium += 1
    p0 = int(validation.get("p0_count") or 0)
    p1 = int(validation.get("p1_count") or 0)
    if status == "succeeded" and (p0 or p1):
        findings.append("status_p0_p1_inconsistent")
        high += 1
    if status == "partial" and p0 == 0 and p1 == 0 and not validation.get("blocked"):
        findings.append("partial_without_p0_p1")
        medium += 1
    allowed_ids = set()
    unknown = 0
    booklet = 0
    cross = 0
    missing_quote = 0
    missing_locator = 0
    metadata_fact = 0
    for card in cards:
        eid = str(card.get("evidence_id") or card.get("id") or "")
        if eid:
            allowed_ids.add(eid)
        if eid and not eid.startswith(f"EV-{qid}-") and eid.startswith("EV-"):
            cross += 1
        if "booklet" in eid.lower() or str(card.get("source_type") or "").lower() == "booklet":
            booklet += 1
        if not _quote_ok(card):
            missing_quote += 1
        if not _locator_ok(card):
            missing_locator += 1
        if str(card.get("eligibility_status") or "") == "METADATA_ONLY":
            metadata_fact += 1
        if eid.startswith("unknown") or eid.startswith("title_only") or eid.startswith("doi_only"):
            unknown += 1
    unsupported_h = 0
    for hyp in result.get("generated_hypotheses") or []:
        if isinstance(hyp, dict) and hyp.get("hypothesis") and not (hyp.get("supporting_evidence_ids") or []):
            unsupported_h += 1
    if unknown:
        findings.append(f"unknown_evidence_id:{unknown}")
        critical += 1
    if booklet:
        findings.append(f"booklet_evidence:{booklet}")
        critical += 1
    if cross:
        findings.append(f"cross_question_evidence:{cross}")
        critical += 1
    if metadata_fact:
        findings.append(f"metadata_only_fact:{metadata_fact}")
        high += 1
    if missing_quote and status not in {"blocked", "failed"}:
        findings.append(f"missing_quote:{missing_quote}")
        high += 1
    if missing_locator and status not in {"blocked", "failed"}:
        findings.append(f"missing_locator:{missing_locator}")
        medium += 1
    if unsupported_h and status == "succeeded":
        findings.append(f"unsupported_hypothesis:{unsupported_h}")
        high += 1
    blob = ""
    for name in ("result.md", "result.json", "provider_audit.json", "validation.json"):
        path = qdir / name
        if path.is_file():
            blob += path.read_text(encoding="utf-8", errors="ignore")
    if SECRET_RE.search(blob) or scan_text_for_secrets(blob):
        findings.append("secret_pattern")
        critical += 1
    if "openrouter" in blob.lower():
        findings.append("openrouter_mention")
        high += 1
    mock_calls = int(validation.get("mock_call_count") or 0)
    if mock_calls or '"provider": "mock"' in blob.lower():
        findings.append("mock_result")
        critical += 1
    if status == "blocked" and not (manifest.get("block_code") or result.get("block_code")):
        findings.append("blocked_without_code")
        medium += 1
    max_sim = float(validation.get("max_similarity") or 0)
    if max_sim > 0.90:
        findings.append(f"similarity_over_0_90:{max_sim}")
        high += 1
    if critical:
        risk = "RISK_CRITICAL"
    elif high:
        risk = "RISK_HIGH"
    elif medium or status in {"partial", "blocked", "failed"}:
        risk = "RISK_MEDIUM" if status != "blocked" else "RISK_HIGH"
        if status == "blocked" and "blocked" not in "".join(findings):
            findings.append("blocked_status")
    else:
        risk = "RISK_LOW"
    suggested = {
        "succeeded": "ACCEPT_SUCCEEDED",
        "partial": "ACCEPT_GENUINE_PARTIAL",
        "blocked": "ACCEPT_GENUINE_BLOCKED",
        "failed": "REQUEST_REMEDIATION",
    }.get(status, "REQUEST_REMEDIATION")
    if qid == "Q095":
        suggested = "ACCEPT_GENUINE_PARTIAL"
    if critical:
        suggested = "REQUEST_REMEDIATION"
    return {
        "question_id": qid,
        "status": status,
        "risk": risk,
        "findings": findings,
        "p0_count": p0,
        "p1_count": p1,
        "pdf_ok": pdf_ok,
        "required_present": not missing,
        "unknown_evidence_id_count": unknown,
        "metadata_only_used_as_fact_count": metadata_fact,
        "booklet_evidence_count": booklet,
        "cross_question_evidence_id_count": cross,
        "missing_quote_count": missing_quote,
        "missing_locator_count": missing_locator,
        "unsupported_hypothesis_count": unsupported_h,
        "max_similarity": max_sim,
        "provider_calls": manifest.get("provider_calls") or 0,
        "block_code": manifest.get("block_code") or result.get("block_code"),
        "suggested_decision": suggested,
        "manual_reviewed": False,
        "paper_title": result.get("paper_title"),
        "official_title": official,
        "scientific_producer_sha": SCIENTIFIC_PRODUCER_SHA,
    }


def risk_sort_key(item: Mapping[str, Any]) -> tuple[int, int, str]:
    status_rank = {"blocked": 0, "failed": 0, "partial": 1, "succeeded": 2}.get(str(item.get("status")), 3)
    risk_rank = {"RISK_CRITICAL": 0, "RISK_HIGH": 1, "RISK_MEDIUM": 2, "RISK_LOW": 3}.get(str(item.get("risk")), 4)
    return (status_rank, risk_rank, str(item.get("question_id")))


def decision_hash(payload: Mapping[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "decision_hash"}
    return sha256_canonical_json(body)


def validate_decision(payload: Mapping[str, Any], *, require_reason: bool) -> None:
    if payload.get("reviewer_role") != "captain":
        raise ValueError("reviewer_role must be captain")
    if payload.get("reviewer_account") != "liuyanbo12":
        raise ValueError("reviewer_account must be liuyanbo12")
    if payload.get("decision") not in DECISIONS:
        raise ValueError("invalid decision")
    if payload.get("reviewed") is not True:
        raise ValueError("reviewed must be true")
    if require_reason and not str(payload.get("reason") or "").strip():
        raise ValueError("reason required for REQUEST_REMEDIATION or SYSTEMIC_REJECT")


def classify_partial_signature(pre: Mapping[str, Any], validation: Mapping[str, Any]) -> str:
    errors = " ".join(str(item) for item in (validation.get("pipeline_quality_gates") or {}).get("errors") or [])
    findings = " ".join(pre.get("findings") or [])
    if pre.get("status") == "blocked":
        return "GENUINE_EVIDENCE_LIMITATION"
    if "缺少 evidence_ids" in errors or "unsupported_hypothesis" in findings:
        return "MODEL_OUTPUT_VALIDATION"
    if "checksum" in findings or "pdf" in findings or "missing_files" in findings:
        return "PDF_OR_PACKAGE_ONLY"
    if "status_p0_p1" in findings:
        return "DETERMINISTIC_PARSER_FALSE_POSITIVE"
    if pre.get("status") == "partial":
        return "GENUINE_EVIDENCE_LIMITATION"
    return "UNKNOWN"
