"""Read-only Formal 12 display payloads. No secrets, no provider calls."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.formal125.catalog import T09_DOMAIN_REPRESENTATIVES
from app.formal125.formal12 import FORMAL_12_CASE_IDS, STAMP, load_readonly_snapshot

DEFAULT_OUTPUT_ROOT = Path(rf"D:\SAGE125_Local_Runs\formal_12_domain_real_{STAMP}")


def resolve_output_root() -> Path:
    configured = os.environ.get("SAGE_FORMAL_12_OUTPUT_ROOT", "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_OUTPUT_ROOT


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def latest_formal_run() -> dict[str, Any]:
    root = resolve_output_root()
    summary = load_readonly_snapshot(root)
    return {
        "output_root": str(root),
        "exists": root.exists(),
        "producer_sha": summary.get("FORMAL_12_PRODUCER_COMMIT_SHA") or summary.get("FORMAL_12_BASE_SHA"),
        "lock_sha": (summary.get("locks") or {}),
        "FORMAL_125_REAL_RUN_READY": bool(summary.get("FORMAL_125_REAL_RUN_READY")),
        "stage_a_status": summary.get("FORMAL_12_STAGE_A_STATUS"),
        "reused_verified_case_ids": summary.get("REUSED_VERIFIED_CASE_IDS") or [],
        "new_actual_case_ids": summary.get("NEW_ACTUAL_CASE_IDS") or [],
        "project_provider_calls_current": summary.get("PROJECT_PROVIDER_CALLS_CURRENT"),
        "secrets_included": False,
    }


def latest_domains() -> dict[str, Any]:
    mapping = [
        {"question_id": qid, "t09_domain_id": domain, "booklet_domain": booklet}
        for qid, domain, booklet in T09_DOMAIN_REPRESENTATIVES
    ]
    return {"count": len(mapping), "domains": mapping}


def latest_questions() -> dict[str, Any]:
    root = resolve_output_root()
    summary = load_readonly_snapshot(root)
    seeds = summary.get("seed_results") or {}
    reused = set(summary.get("REUSED_VERIFIED_CASE_IDS") or [])
    items = []
    for question_id in FORMAL_12_CASE_IDS:
        question_dir = root / question_id
        validation = _load(question_dir / "validation.json") or {}
        manifest = _load(question_dir / "package_manifest.json") or {}
        seed = seeds.get(question_id) or {}
        items.append(
            {
                "question_id": question_id,
                "execution_mode": "REUSED_VERIFIED_FORMAL_RESULT" if question_id in reused else "NEW_ACTUAL",
                "status": manifest.get("status") or ("seed_ready" if seed.get("EVIDENCE_SEED_READY") else "pending"),
                "evidence_count": seed.get("ELIGIBLE_EVIDENCE_COUNT") or len(_load(question_dir / "evidence_cards.json") or []),
                "fulltext_sources": seed.get("FULLTEXT_VERIFIED_COUNT") or 0,
                "provider_calls": 0 if question_id in reused else manifest.get("provider_calls"),
                "p0": validation.get("p0_count"),
                "p1": validation.get("p1_count"),
                "pdf_present": (question_dir / "result.pdf").is_file(),
                "manual_review": bool(validation.get("manual_review_required")),
                "output_path": str(question_dir),
            }
        )
    return {"count": len(items), "questions": items}


def latest_question(question_id: str) -> dict[str, Any]:
    payload = latest_questions()
    for item in payload["questions"]:
        if item["question_id"] == question_id:
            return item
    return {"question_id": question_id, "status": "not_in_formal_12"}
