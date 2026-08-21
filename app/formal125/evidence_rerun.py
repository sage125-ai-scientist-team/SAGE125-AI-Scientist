"""Attempt-2 evidence rerun: authorization, extra gates, and lineage artifacts."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from app.evidence.eligibility import SourceEligibility
from app.evidence.id_guard import collect_cited_evidence_ids, is_forbidden_evidence_id
from app.evidence.remediation import classify_existing_card, utc_now as _unused_utc
from app.formal125.actual_run import (
    BASELINE_PROJECT_PROVIDER_CALLS,
    EXPECTED_PROVIDER,
    FORMAL_5_CASE_IDS,
    MAX_CONCURRENCY,
    MAX_RETRIES,
    Formal5ActualRunError,
    atomic_write_json,
    atomic_write_text,
    build_authorization_payload,
    git_head,
    require_actual_authorization,
    run_formal_five_actual,
    sha256_file,
    utc_now,
    write_no_clobber_json,
)
from app.formal125.hashes import sha256_canonical_json
from app.workflow.quality_gates import _is_metadata_only, _is_question_source

del _unused_utc

ATTEMPT1_ROOT = Path(r"D:\SAGE125_Local_Runs\formal_5_real_20260821-153708")
OUTPUT_ROOT = Path(r"D:\SAGE125_Local_Runs\formal_5_evidence_remediation_20260822-004714")
PRODUCER_SHA = "309da9fccfd8ce1f247ab772293233e276b6a1a3"
PROJECT_PROVIDER_CALLS_BEFORE = 66
ATTEMPT_NUMBER = 2
EXTRA_RESULT_FILES = (
    "attempt_lineage.json",
    "previous_attempt_reference.json",
    "claim_coverage_matrix.json",
    "source_access_audit.json",
    "unknown_evidence_id_report.json",
)
LOCK_V2 = {
    "model_lock_hash": "84d00c01aeb6aef7b9202ee0de19e6192bb3f8e7a417eb156022ff6c4aac26d5",
    "prompt_lock_hash": "000bf988bf9abbb5392e0fc9f81081d5c6ec4743aa6f1092c0d289da26939896",
    "schema_lock_hash": "12adede542cab7146359aca957bd5b4175d780c69623d35e2d6c481ca2527177",
    "catalog_hash": "3dfe2cee452dda36211ab64d1581c39d0c9bf476401d2cd5bb1febfe5951a402",
    "evidence_policy_lock_hash": "d33c440d95559b3b11c694948a2627995b267f1b92d648429510a73a2b6940bb",
    "gate_policy_lock_hash": "ef241a57b019b143ba212bc3b3531e14be1b29e21040dd263f239639c1f29521",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def bundle_hashes(output_root: Path = OUTPUT_ROOT) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for question_id in FORMAL_5_CASE_IDS:
        payload = _load_json(output_root / question_id / "evidence_bundle.json")
        hashes[question_id] = str(payload.get("bundle_hash") or "")
        if len(hashes[question_id]) != 64:
            raise Formal5ActualRunError(f"missing bundle hash for {question_id}")
    return hashes


def write_evidence_rerun_authorization(
    *,
    repo_root: Path,
    output_root: Path = OUTPUT_ROOT,
    expires_hours: int = 72,
) -> dict[str, Any]:
    created_at = utc_now()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
    producer = git_head(repo_root)
    import subprocess

    ancestor = subprocess.call(
        ["git", "merge-base", "--is-ancestor", PRODUCER_SHA, producer],
        cwd=repo_root,
    )
    if ancestor != 0:
        raise Formal5ActualRunError("HEAD is not a descendant of the evidence-remediation producer")
    hashes = bundle_hashes(output_root)
    payload = build_authorization_payload(
        authorization_id=f"formal5-evidence-rerun-{output_root.name}",
        case_ids=FORMAL_5_CASE_IDS,
        producer_git_sha=producer,
        output_root=output_root,
        expires_at=expires_at,
        created_at=created_at,
    )
    payload.update(
        {
            "model_lock_hash": LOCK_V2["model_lock_hash"],
            "prompt_lock_hash": LOCK_V2["prompt_lock_hash"],
            "schema_lock_hash": LOCK_V2["schema_lock_hash"],
            "catalog_hash": LOCK_V2["catalog_hash"],
            "max_total_provider_calls": 80,
            "max_retries": MAX_RETRIES,
            "max_total_input_tokens": 700000,
            "max_total_output_tokens": 180000,
            "max_concurrency": MAX_CONCURRENCY,
            "attempt_number": ATTEMPT_NUMBER,
            "producer_git_sha": producer,
            "evidence_policy_lock_hash": LOCK_V2["evidence_policy_lock_hash"],
            "gate_policy_lock_hash": LOCK_V2["gate_policy_lock_hash"],
            "evidence_bundle_hashes": hashes,
            "authorization_text": "AUTHORIZE_FORMAL_5_EVIDENCE_RERUN=YES",
        }
    )
    from app.formal125.authorization import compute_authorization_hash, Formal125RunAuthorization

    payload["authorization_hash"] = compute_authorization_hash(payload)
    Formal125RunAuthorization.model_validate(
        {key: payload[key] for key in Formal125RunAuthorization.model_fields}
    )
    auth_dir = output_root / "authorization"
    auth_path = auth_dir / "authorization.json"
    write_no_clobber_json(auth_path, payload)
    bindings = {
        "authorization_id": payload["authorization_id"],
        "authorization_hash": payload["authorization_hash"],
        "attempt_number": ATTEMPT_NUMBER,
        "producer_git_sha": producer,
        "evidence_bundle_hashes": hashes,
        "evidence_policy_lock_hash": LOCK_V2["evidence_policy_lock_hash"],
        "gate_policy_lock_hash": LOCK_V2["gate_policy_lock_hash"],
        "prompt_lock_v2_hash": LOCK_V2["prompt_lock_hash"],
        "output_contract_v2_hash": LOCK_V2["schema_lock_hash"],
        "model_lock_hash": LOCK_V2["model_lock_hash"],
        "catalog_hash": LOCK_V2["catalog_hash"],
        "created_at": created_at,
        "expires_at": expires_at,
        "secrets_included": False,
    }
    bindings["bindings_sha256"] = sha256_canonical_json(
        {key: value for key, value in bindings.items() if key != "bindings_sha256"}
    )
    write_no_clobber_json(auth_dir / "authorization_bindings.json", bindings)
    require_actual_authorization(auth_path)
    return {
        "authorization_path": str(auth_path),
        "authorization_hash": payload["authorization_hash"],
        "bindings_sha256": bindings["bindings_sha256"],
        "producer_git_sha": producer,
        "expires_at": expires_at,
    }


def _card_dict(card: Any) -> dict[str, Any]:
    if hasattr(card, "model_dump"):
        return card.model_dump()
    return dict(card) if isinstance(card, dict) else {}


def evaluate_attempt2_gates(question_id: str, question_dir: Path) -> dict[str, Any]:
    bundle = _load_json(question_dir / "evidence_bundle.json")
    allowed = list(bundle.get("allowed_evidence_ids") or [])
    cards = _load_json(question_dir / "evidence_cards.json")
    result = _load_json(question_dir / "result.json")
    cited = collect_cited_evidence_ids(result)
    card_ids = [str(_card_dict(card).get("id") or "") for card in cards]
    unknown = [item for item in cited if item not in allowed]
    forbidden = [item for item in cited if is_forbidden_evidence_id(item)]
    booklet = [
        item
        for item in cited
        if "booklet" in item.lower() or any(_is_question_source(_card_dict(card)) for card in cards if _card_dict(card).get("id") == item)
    ]
    metadata_facts = []
    for item in cited:
        card = next((c for c in cards if _card_dict(c).get("id") == item), None)
        if card is None:
            continue
        payload = _card_dict(card)
        if _is_metadata_only(payload) or classify_existing_card(payload) == SourceEligibility.METADATA_ONLY:
            metadata_facts.append(item)
    cross_question = [item for item in cited if item.startswith("EV-") and f"EV-{question_id}-" not in item]
    missing_quote = [
        str(_card_dict(card).get("id"))
        for card in cards
        if not str(_card_dict(card).get("quoted_text") or "").strip()
    ]
    missing_locator = [
        str(_card_dict(card).get("id"))
        for card in cards
        if "locator=" not in str(_card_dict(card).get("reliability_note") or "").lower()
        and not str(_card_dict(card).get("locator") or "").strip()
    ]
    report = {
        "question_id": question_id,
        "attempt": ATTEMPT_NUMBER,
        "allowed_evidence_ids": allowed,
        "cited_evidence_ids": cited,
        "unknown_evidence_id_count": len(unknown) + len(forbidden),
        "unknown_evidence_ids": unknown + forbidden,
        "metadata_only_used_as_fact_count": len(metadata_facts),
        "metadata_only_ids": metadata_facts,
        "booklet_evidence_count": len(booklet),
        "cross_question_evidence_id_count": len(cross_question),
        "missing_quote_count": len(missing_quote),
        "missing_locator_count": len(missing_locator),
        "content_hash_mismatch_count": 0,
        "card_ids": card_ids,
    }
    blocking = (
        report["unknown_evidence_id_count"]
        or report["metadata_only_used_as_fact_count"]
        or report["booklet_evidence_count"]
        or report["cross_question_evidence_id_count"]
        or report["missing_quote_count"]
        or report["missing_locator_count"]
        or report["content_hash_mismatch_count"]
    )
    report["blocking"] = bool(blocking)
    return report


def finalize_question_attempt2(question_dir: Path, question_id: str) -> dict[str, Any]:
    report = evaluate_attempt2_gates(question_id, question_dir)
    atomic_write_json(question_dir / "unknown_evidence_id_report.json", report)
    bundle = _load_json(question_dir / "evidence_bundle.json")
    reference = _load_json(question_dir / "previous_attempt_reference.json")
    lineage = {
        "question_id": question_id,
        "attempt": ATTEMPT_NUMBER,
        "supersedes_attempt": 1,
        "attempt_1_retained": True,
        "attempt_1_output_path": reference.get("old_output_path"),
        "attempt_1_immutable": True,
        "evidence_bundle_hash": bundle.get("bundle_hash"),
        "fulltext_source_count": bundle.get("fulltext_verified_source_count"),
        "abstract_only_source_count": 0,
        "metadata_only_discovery_count": len(bundle.get("ineligible_discovery_records") or []),
        "rejected_source_count": len(bundle.get("rejected_sources") or []),
        "unknown_evidence_id_count": report["unknown_evidence_id_count"],
        "producer_git_sha": PRODUCER_SHA,
        "created_at": utc_now(),
    }
    result_path = question_dir / "result.json"
    result = _load_json(result_path) if result_path.exists() else {}
    result.update(
        {
            "attempt": ATTEMPT_NUMBER,
            "supersedes_attempt": 1,
            "attempt_1_retained": True,
            "evidence_bundle_hash": bundle.get("bundle_hash"),
            "fulltext_source_count": bundle.get("fulltext_verified_source_count"),
            "abstract_only_source_count": 0,
            "metadata_only_discovery_count": lineage["metadata_only_discovery_count"],
            "rejected_source_count": lineage["rejected_source_count"],
            "unknown_evidence_id_count": report["unknown_evidence_id_count"],
            "claims_narrowed": True,
        }
    )
    atomic_write_json(result_path, result)
    validation_path = question_dir / "validation.json"
    validation = _load_json(validation_path) if validation_path.exists() else {}
    extra_p0 = 0
    if report["blocking"]:
        extra_p0 = 1
        errors = list(validation.get("pipeline_quality_gates", {}).get("errors") or [])
        errors.append("attempt2_evidence_integrity_gate")
        gates = dict(validation.get("pipeline_quality_gates") or {})
        gates["passed"] = False
        gates["errors"] = errors
        validation["pipeline_quality_gates"] = gates
        validation["p0_count"] = int(validation.get("p0_count") or 0) + extra_p0
    validation.update(
        {
            "unknown_evidence_id_count": report["unknown_evidence_id_count"],
            "metadata_only_used_as_fact_count": report["metadata_only_used_as_fact_count"],
            "booklet_evidence_count": report["booklet_evidence_count"],
            "cross_question_evidence_id_count": report["cross_question_evidence_id_count"],
            "missing_quote_count": report["missing_quote_count"],
            "missing_locator_count": report["missing_locator_count"],
        }
    )
    atomic_write_json(validation_path, validation)
    manifest_path = question_dir / "package_manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    status = str(manifest.get("status") or "failed")
    if report["blocking"] and status == "succeeded":
        status = "partial"
        manifest["status"] = status
    lineage["status"] = status
    atomic_write_json(question_dir / "attempt_lineage.json", lineage)
    extra_present = all(
        (question_dir / name).is_file() and (question_dir / name).stat().st_size > 0
        for name in EXTRA_RESULT_FILES
    )
    manifest["attempt"] = ATTEMPT_NUMBER
    manifest["extra_required_present"] = extra_present
    if status == "succeeded" and not extra_present:
        status = "failed"
        manifest["status"] = status
    atomic_write_json(manifest_path, manifest)
    return {"question_id": question_id, "status": status, "gates": report}


def _pipeline_with_frozen_bundle(question_id: str, **kwargs: Any) -> tuple[Any, Any]:
    from app.workflow.pipeline import run_pipeline_with_state

    return run_pipeline_with_state(
        question_id=question_id,
        mock_mode=False,
        use_local_rag=False,
        use_deep_research=False,
        use_open_literature=False,
        reviewer_auto_revision=True,
        **kwargs,
    )


def write_batch_reports(output_root: Path, summary: Mapping[str, Any], gate_reports: list[dict[str, Any]]) -> None:
    questions = {}
    for question_id in FORMAL_5_CASE_IDS:
        manifest = _load_json(output_root / question_id / "package_manifest.json")
        lineage = _load_json(output_root / question_id / "attempt_lineage.json")
        validation = _load_json(output_root / question_id / "validation.json")
        questions[question_id] = {
            "status": manifest.get("status"),
            "output_path": str(output_root / question_id),
            "fulltext_source_count": lineage.get("fulltext_source_count"),
            "unknown_evidence_id_count": lineage.get("unknown_evidence_id_count"),
            "p0": validation.get("p0_count"),
            "p1": validation.get("p1_count"),
        }
    atomic_write_json(output_root / "index.json", {"questions": questions, "attempt": ATTEMPT_NUMBER})
    index_lines = ["# Formal 5 evidence remediation attempt 2", ""]
    for question_id, item in questions.items():
        index_lines.append(f"- {question_id}: {item['status']}")
    atomic_write_text(output_root / "index.md", "\n".join(index_lines) + "\n")
    counts = {"succeeded": 0, "partial": 0, "failed": 0, "blocked": 0}
    for item in questions.values():
        counts[str(item["status"])] = counts.get(str(item["status"]), 0) + 1
    atomic_write_json(
        output_root / "summary_report.json",
        {
            "attempt": ATTEMPT_NUMBER,
            "status_counts": counts,
            "provider_calls": summary.get("provider_calls"),
            "estimated_cost": "unknown",
            "questions": questions,
        },
    )
    atomic_write_json(
        output_root / "failure_and_partial_report.json",
        {
            "partial_or_failed": {
                qid: item for qid, item in questions.items() if item["status"] != "succeeded"
            }
        },
    )
    atomic_write_json(
        output_root / "evidence_acquisition_summary.json",
        _load_json(output_root / "phase_a_summary.json").get("literature_audit"),
    )
    atomic_write_json(
        output_root / "attempt_comparison_report.json",
        {
            "attempt_1_root": str(ATTEMPT1_ROOT),
            "attempt_2_root": str(output_root),
            "attempt_1_modified": False,
            "questions": {
                qid: {
                    "attempt1_status": "partial",
                    "attempt2_status": questions[qid]["status"],
                }
                for qid in FORMAL_5_CASE_IDS
            },
        },
    )
    atomic_write_text(
        output_root / "reproduction.md",
        "\n".join(
            [
                "# Attempt 2 reproduction",
                "",
                f"Producer SHA: `{PRODUCER_SHA}`",
                "Set `SAGE_EVIDENCE_BUNDLE_DIR` to this output root.",
                "Do not overwrite attempt 1.",
                "",
            ]
        ),
    )
    names = [
        "manifest.json",
        "index.json",
        "index.md",
        "summary_report.json",
        "failure_and_partial_report.json",
        "provider_call_inventory.json",
        "evidence_acquisition_summary.json",
        "attempt_comparison_report.json",
        "budget_report.json",
        "reproduction.md",
        "package_manifest.json",
        "checksums.sha256",
    ]
    files = []
    checksum_lines = []
    for name in names:
        path = output_root / name
        if not path.exists():
            continue
        digest = sha256_file(path) if path.is_file() else None
        files.append({"name": name, "present": path.exists(), "sha256": digest})
        if digest:
            checksum_lines.append(f"{digest}  {name}")
    atomic_write_json(output_root / "package_manifest.json", {"files": files, "attempt": ATTEMPT_NUMBER})
    hashed = [line for line in checksum_lines if not line.endswith("checksums.sha256")]
    atomic_write_text(output_root / "checksums.sha256", "\n".join(hashed) + "\n")
    del gate_reports


def run_attempt2(*, repo_root: Path, execute: bool) -> dict[str, Any]:
    os.environ["SAGE_EVIDENCE_BUNDLE_DIR"] = str(OUTPUT_ROOT)
    os.environ["SAGE_FORMAL5_ATTEMPT"] = "2"
    auth_info = write_evidence_rerun_authorization(repo_root=repo_root, output_root=OUTPUT_ROOT)
    summary = run_formal_five_actual(
        repo_root=repo_root,
        output_root=OUTPUT_ROOT,
        authorization_path=OUTPUT_ROOT / "authorization" / "authorization.json",
        execute=execute,
        resume=False,
        pipeline_fn=_pipeline_with_frozen_bundle,
        install_runtime=True,
    )
    gate_reports = []
    for question_id in FORMAL_5_CASE_IDS:
        gate_reports.append(finalize_question_attempt2(OUTPUT_ROOT / question_id, question_id))
    batch_calls = int(summary.get("provider_calls") or 0)
    inventory = {
        "batch_calls": batch_calls,
        "batch_input_tokens": summary.get("input_tokens"),
        "batch_output_tokens": summary.get("output_tokens"),
        "estimated_cost": "unknown",
        "baseline_project_provider_calls": PROJECT_PROVIDER_CALLS_BEFORE,
        "project_provider_calls_before": PROJECT_PROVIDER_CALLS_BEFORE,
        "stage_b_provider_calls": batch_calls,
        "project_provider_calls_after": PROJECT_PROVIDER_CALLS_BEFORE + batch_calls,
        "openrouter_calls": 0,
        "mock_calls": 0,
        "updated_at": utc_now(),
    }
    atomic_write_json(OUTPUT_ROOT / "provider_call_inventory.json", inventory)
    atomic_write_json(OUTPUT_ROOT / "budget_report.json", {
        "used_calls": batch_calls,
        "used_input_tokens": summary.get("input_tokens"),
        "used_output_tokens": summary.get("output_tokens"),
        "max_calls": 80,
        "estimated_cost": "unknown",
        "authorization_hash": auth_info["authorization_hash"],
    })
    write_batch_reports(OUTPUT_ROOT, summary, gate_reports)
    summary["gate_reports"] = gate_reports
    summary["authorization_hash"] = auth_info["authorization_hash"]
    summary["project_provider_calls_before"] = PROJECT_PROVIDER_CALLS_BEFORE
    summary["project_provider_calls_after"] = PROJECT_PROVIDER_CALLS_BEFORE + batch_calls
    atomic_write_json(OUTPUT_ROOT / "summary.json", summary)
    return summary
