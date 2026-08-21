"""Phase A evidence remediation runner. No model provider calls."""

from __future__ import annotations

import json
from pathlib import Path

from app.evidence.remediation import (
    FORMAL_5,
    build_question_bundle,
    freeze_attempt1_references,
    write_json,
    write_root_cause_report,
)
from app.evidence.oa_fulltext import FulltextFetchAudit
from app.formal125.hashes import sha256_canonical_json
from app.formal125.preflight import (
    build_evidence_policy,
    build_gate_policy,
    build_output_contract,
    build_prompt_lock,
)

STAMP = "20260822-004714"
OUTPUT_ROOT = Path(rf"D:\SAGE125_Local_Runs\formal_5_evidence_remediation_{STAMP}")
CACHE_ROOT = Path(rf"D:\SAGE125_Local_Evidence\formal_5_remediation_{STAMP}")
WORKTREE = Path(r"D:\SAGE125_Local_Worktrees\formal_5_evidence_remediation_20260822-004714")
LOCK_DIR = WORKTREE / "docs" / "reproducibility" / "formal_125"


def _write_lock_v2() -> dict[str, str]:
    previous_prompt = json.loads((LOCK_DIR / "formal_125_prompt.lock.json").read_text(encoding="utf-8"))
    previous_evidence = json.loads((LOCK_DIR / "formal_125_evidence_policy.lock.json").read_text(encoding="utf-8"))
    previous_gate = json.loads((LOCK_DIR / "formal_125_gate_policy.lock.json").read_text(encoding="utf-8"))
    previous_output = json.loads((LOCK_DIR / "formal_125_output_contract.lock.json").read_text(encoding="utf-8"))
    prompt = build_prompt_lock()
    prompt["lock_version"] = "formal125.prompt.v2"
    prompt["previous_hash"] = previous_prompt.get("prompt_lock_sha256")
    prompt["change_reason"] = "Forbid unknown Evidence IDs and question-source citations in COMMON_SCIENTIST_RULES."
    prompt["backward_compatibility"] = False
    prompt["invalidated_checkpoints"] = ["formal_5_real_20260821-153708"]
    prompt["prompt_lock_sha256"] = sha256_canonical_json(
        {key: value for key, value in prompt.items() if key != "prompt_lock_sha256"}
    )
    evidence = build_evidence_policy()
    evidence.update(
        {
            "lock_version": "formal125.evidence.v2",
            "formal_evidence_mode": "oa_fulltext_verified_plus_abstract_verified",
            "scholarly_evidence": ["FULLTEXT_VERIFIED", "ABSTRACT_VERIFIED"],
            "discovery_only": ["openalex_metadata", "crossref_metadata", "doi_landing"],
            "cannot_support_scientific_facts": [
                "booklet",
                "mock",
                "synthetic",
                "unquoted metadata",
                "title-only",
                "doi-only",
                "METADATA_ONLY",
                "QUESTION_SOURCE",
                "FETCH_FAILED",
                "LICENSE_RESTRICTED",
            ],
            "minimum_fulltext_sources_per_question": 2,
            "unknown_evidence_id_policy": "fail_closed_at_parse_no_fuzzy_repair",
            "previous_hash": previous_evidence.get("evidence_policy_sha256"),
            "change_reason": "Metadata discovery cannot enter fact EvidenceCards; OA fulltext required.",
            "backward_compatibility": False,
            "invalidated_checkpoints": ["formal_5_real_20260821-153708"],
        }
    )
    evidence["evidence_policy_sha256"] = sha256_canonical_json(
        {key: value for key, value in evidence.items() if key != "evidence_policy_sha256"}
    )
    gate = build_gate_policy()
    gate["lock_version"] = "formal125.gate.v2"
    extra_gates = [
        "unknown_evidence_id",
        "metadata_only_not_fact",
        "fulltext_locator_required",
        "booklet_id_forbidden",
    ]
    gate["gates"] = list(gate.get("gates") or []) + extra_gates
    gate["gate_count"] = len(gate["gates"])
    gate["previous_hash"] = previous_gate.get("gate_policy_sha256")
    gate["change_reason"] = "Parse-time unknown ID guard and metadata-only fact ban."
    gate["backward_compatibility"] = False
    gate["invalidated_checkpoints"] = ["formal_5_real_20260821-153708"]
    gate["gate_policy_sha256"] = sha256_canonical_json(
        {key: value for key, value in gate.items() if key != "gate_policy_sha256"}
    )
    output = dict(previous_output)
    output["lock_version"] = "formal125.output-contract.v2"
    extra_files = [
        "attempt_lineage.json",
        "previous_attempt_reference.json",
        "claim_coverage_matrix.json",
        "source_access_audit.json",
        "unknown_evidence_id_report.json",
    ]
    files = list(output.get("required_files") or [])
    for name in extra_files:
        if name not in files:
            files.append(name)
    output["required_files"] = files
    output["required_file_count_per_question"] = len(files)
    output["previous_hash"] = previous_output.get("output_contract_sha256")
    output["change_reason"] = "Attempt 2 lineage and coverage artifacts."
    output["backward_compatibility"] = False
    output["invalidated_checkpoints"] = ["formal_5_real_20260821-153708"]
    output["output_contract_sha256"] = sha256_canonical_json(
        {key: value for key, value in output.items() if key != "output_contract_sha256"}
    )
    write_json(LOCK_DIR / "formal_125_prompt.lock.v2.json", prompt)
    write_json(LOCK_DIR / "formal_125_evidence_policy.lock.v2.json", evidence)
    write_json(LOCK_DIR / "formal_125_gate_policy.lock.v2.json", gate)
    write_json(LOCK_DIR / "formal_125_output_contract.lock.v2.json", output)
    return {
        "prompt": prompt["prompt_lock_sha256"],
        "evidence": evidence["evidence_policy_sha256"],
        "gate": gate["gate_policy_sha256"],
        "output": output["output_contract_sha256"],
        "model": json.loads((LOCK_DIR / "formal_125_model.lock.json").read_text(encoding="utf-8")).get(
            "model_lock_sha256"
        ),
    }


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    refs = freeze_attempt1_references(OUTPUT_ROOT)
    write_root_cause_report(OUTPUT_ROOT / "evidence_root_cause_report.json")
    audit = FulltextFetchAudit()
    bundles = []
    for question_id in FORMAL_5:
        bundles.append(
            build_question_bundle(
                question_id=question_id,
                cache_root=CACHE_ROOT,
                output_root=OUTPUT_ROOT,
                audit=audit,
            )
        )
    locks = _write_lock_v2()
    ready = sum(1 for item in bundles if item.get("evidence_bundle_ready"))
    summary = {
        "stamp": STAMP,
        "attempt1_reference_count": len(refs),
        "attempt1_immutability_status": "FROZEN_BY_REFERENCE",
        "evidence_bundle_ready_count": ready,
        "fulltext_verified_source_total": sum(item.get("fulltext_verified_source_count") or 0 for item in bundles),
        "eligible_evidence_total": sum(item.get("eligible_evidence_count") or 0 for item in bundles),
        "uncovered_claim_total": sum(item.get("uncovered_claim_count") or 0 for item in bundles),
        "unknown_evidence_id_count": sum(item.get("unknown_id_count") or 0 for item in bundles),
        "metadata_only_used_as_fact_count": sum(item.get("metadata_only_used_as_fact_count") or 0 for item in bundles),
        "booklet_evidence_count": sum(item.get("booklet_evidence_count") or 0 for item in bundles),
        "questions": {
            item["question_id"]: {
                "fulltext_verified_source_count": item.get("fulltext_verified_source_count"),
                "eligible_evidence_count": item.get("eligible_evidence_count"),
                "uncovered_claim_count": item.get("uncovered_claim_count"),
                "unknown_id_count": item.get("unknown_id_count"),
                "evidence_bundle_ready": item.get("evidence_bundle_ready"),
                "bundle_hash": item.get("bundle_hash"),
            }
            for item in bundles
        },
        "locks": locks,
        "literature_audit": audit.snapshot(),
        "budget": {
            "min_calls": 45,
            "nominal_calls": 55,
            "worst_case_calls": 80,
            "nominal_input_tokens": 319000,
            "nominal_output_tokens": 59500,
            "worst_input_tokens": 480000,
            "worst_output_tokens": 90000,
            "estimated_duration": "15-25min",
            "estimated_cost_status": "UNKNOWN",
            "rationale": "Reuse query parser/planner outputs conceptually; rerun extractor, hypotheses, designer, reviewer, optional V2, writer, validator. Skip embedding/rerank/DeepResearch when frozen bundle is injected.",
        },
        "project_provider_calls_current": 66,
        "stage_a_provider_calls": 0,
    }
    write_json(OUTPUT_ROOT / "phase_a_summary.json", summary)
    print(json.dumps({"ready": ready, "output": str(OUTPUT_ROOT)}, ensure_ascii=False))
    return 0 if ready == 5 else 2


if __name__ == "__main__":
    raise SystemExit(main())
