"""Formal 12 relevance remediation Stage A. No model Provider calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.evidence.oa_fulltext import FulltextFetchAudit  # noqa: E402
from app.evidence.relevance import Q069_NEGATIVE_ARXIV, build_relevance_spec  # noqa: E402
from app.evidence.remediation import FORMAL_12_NEW, build_seed_bundle, sha256_file, write_json  # noqa: E402
from app.formal125.formal12 import FORMAL_12_SELECTION_SHA256, _question_from_catalog  # noqa: E402
from app.formal125.hashes import sha256_canonical_json  # noqa: E402
from app.formal125.pipeline_plan import CHAT_STEPS, REVISION_STEPS  # noqa: E402

STAMP = "20260822-120516"
FAILED_ROOT = Path(r"D:\SAGE125_Local_Runs\formal_12_domain_real_20260822-014248")
OUTPUT = Path(rf"D:\SAGE125_Local_Runs\formal_12_relevance_remediation_{STAMP}")
CACHE = Path(rf"D:\SAGE125_Local_Evidence\formal_12_relevance_remediation_{STAMP}")
CANARY_ROOT = Path(rf"D:\SAGE125_Local_Runs\formal_12_q069_relevance_canary_{STAMP}")
LOCAL_CACHES = [
    Path(r"D:\SAGE125_Local_Evidence\formal_12_domain_20260822-014248"),
    Path(r"D:\SAGE125_Local_Evidence\formal_5_remediation_20260822-004714"),
    CACHE,
]


def failed_batch_reference() -> dict:
    q069 = FAILED_ROOT / "Q069"
    ref = {
        "source_batch_id": "formal_12_domain_real_20260822-014248",
        "source_output_root": str(FAILED_ROOT),
        "source_authorization_hash": "2fb50966b16fe9cdf0d17b4ec54553d6b428d128173c81e1dce9cab9230d4d14",
        "source_producer_sha": "2bd56fef31d8c15375b6c8ec249dfe7deec20a88",
        "source_snapshot_sha": "09e3fd72e07fa40d9249cdfecc0c7bcb08ffbc32",
        "source_manifest_sha256": sha256_file(FAILED_ROOT / "manifest.json"),
        "q069_result_digest": sha256_file(q069 / "result.json"),
        "q069_evidence_seed_digest": sha256_file(FAILED_ROOT / "evidence_seeds" / "Q069" / "evidence_bundle.json"),
        "q069_validation_digest": sha256_file(q069 / "validation.json"),
        "q069_provider_audit_digest": sha256_file(q069 / "provider_audit.json"),
        "provider_calls": 8,
        "project_provider_calls_after": 129,
        "canary_code": "CANARY_SYSTEMIC_FAILURE",
        "remaining_questions_not_called": True,
        "immutable": True,
        "copied_result_bodies": False,
    }
    ref["FAILED_BATCH_REFERENCE_SHA256"] = sha256_canonical_json(ref)
    return ref


def root_cause() -> dict:
    return {
        "question_id": "Q069",
        "official_question": "Is there a diffraction limit?",
        "off_topic_sources": [
            {
                "arxiv_id": "2411.00681",
                "query": "all:diffraction limit optics resolution",
                "query_function": "app.evidence.remediation._arxiv_search",
                "contains_core_concepts": False,
                "cache": True,
                "cache_key_missing_question_identity": True,
                "why_accepted": "FULLTEXT_VERIFIED and two generic keyword hits (limit/resolution) in select_quote/scan_local_arxiv_cache",
                "gate_that_should_have_rejected": "topic_relevance_independent_of_fulltext",
            },
            {
                "arxiv_id": "2307.15471",
                "query": "all:diffraction limit optics resolution",
                "query_function": "app.evidence.remediation._arxiv_search",
                "contains_core_concepts": False,
                "why_accepted": "FULLTEXT_VERIFIED plus generic token overlap; no topic gate",
                "gate_that_should_have_rejected": "topic_relevance_independent_of_fulltext",
            },
        ],
        "root_causes": [
            {
                "ROOT_CAUSE_ID": "QUERY_TOO_GENERIC",
                "FILE": "app/evidence/remediation.py",
                "FUNCTION": "_arxiv_search / QUERY_SEEDS[Q069]",
                "CURRENT_BEHAVIOR": "Unquoted all:diffraction limit optics resolution matches any paper containing those tokens separately.",
                "EXPECTED_BEHAVIOR": "Fielded queries must require the optical diffraction-limit object.",
                "AFFECTED_QUESTIONS": list(FORMAL_12_NEW),
                "SEVERITY": "P0",
                "MINIMUM_FIX": "Replace Q069 queries with ti:\"diffraction limit\" AND microscopy/optics.",
                "REGRESSION_TEST": "tests/evidence/test_topic_relevance_gate.py::test_q069_negative_arxiv_ids_are_off_topic_even_if_fulltext",
            },
            {
                "ROOT_CAUSE_ID": "CROSS_QUESTION_CACHE_COLLISION",
                "FILE": "app/evidence/remediation.py",
                "FUNCTION": "scan_local_arxiv_cache",
                "CURRENT_BEHAVIOR": "Any cached PDF with two keyword hits is reused for the current question, including Q109's 2411.00681.",
                "EXPECTED_BEHAVIOR": "Content SHA may be reused; relevance decisions must be question-bound.",
                "AFFECTED_QUESTIONS": list(FORMAL_12_NEW),
                "SEVERITY": "P0",
                "MINIMUM_FIX": "list_cached_arxiv_sources + per-question assess_candidate.",
                "REGRESSION_TEST": "tests/evidence/test_topic_relevance_gate.py::test_q069_cannot_read_other_question_relevance_cache",
            },
            {
                "ROOT_CAUSE_ID": "FULLTEXT_AVAILABILITY_ONLY_SELECTION",
                "FILE": "app/evidence/remediation.py",
                "FUNCTION": "_finalize_bundle / prepare_new_case_seeds",
                "CURRENT_BEHAVIOR": "Seed ready if FULLTEXT_VERIFIED_COUNT >= 2.",
                "EXPECTED_BEHAVIOR": "Require DIRECT_QUESTION_CORE plus a second DIRECT or SUPPORTING_MECHANISM source.",
                "AFFECTED_QUESTIONS": list(FORMAL_12_NEW),
                "SEVERITY": "P0",
                "MINIMUM_FIX": "evaluate_seed_gate",
                "REGRESSION_TEST": "tests/evidence/test_topic_relevance_gate.py::test_seed_gate_requires_direct_core_not_just_fulltext",
            },
            {
                "ROOT_CAUSE_ID": "NO_TOPIC_RELEVANCE_GATE",
                "FILE": "app/evidence/remediation.py",
                "FUNCTION": "_cards_from_arxiv_ids",
                "CURRENT_BEHAVIOR": "No DIRECT/OFF_TOPIC status. relevance_score hardcoded 0.6.",
                "EXPECTED_BEHAVIOR": "Independent topic status; OpenAlex score is discovery-only.",
                "AFFECTED_QUESTIONS": list(FORMAL_12_NEW),
                "SEVERITY": "P0",
                "MINIMUM_FIX": "app.evidence.relevance.assess_candidate",
                "REGRESSION_TEST": "tests/evidence/test_topic_relevance_gate.py::test_q069_direct_core_from_optical_diffraction_fulltext",
            },
            {
                "ROOT_CAUSE_ID": "NEGATIVE_TOPIC_NOT_FILTERED",
                "FILE": "app/evidence/remediation.py",
                "FUNCTION": "select_quote / QUESTION_KEYWORDS",
                "CURRENT_BEHAVIOR": "limit+resolution in a mutation or network paper counts as a quote.",
                "EXPECTED_BEHAVIOR": "Prohibited unrelated topics reject the candidate.",
                "AFFECTED_QUESTIONS": ["Q069"],
                "SEVERITY": "P0",
                "MINIMUM_FIX": "Q069 prohibited topics + permanent negative arXiv IDs.",
                "REGRESSION_TEST": "tests/evidence/test_topic_relevance_gate.py::test_q069_negative_arxiv_ids_are_off_topic_even_if_fulltext",
            },
        ],
        "SYSTEMIC_ROOT_CAUSE_CONFIRMED": True,
        "Q069_ROOT_CAUSES": [
            "QUERY_TOO_GENERIC",
            "CROSS_QUESTION_CACHE_COLLISION",
            "FULLTEXT_AVAILABILITY_ONLY_SELECTION",
            "NO_TOPIC_RELEVANCE_GATE",
            "NEGATIVE_TOPIC_NOT_FILTERED",
        ],
    }


def write_review(output: Path, results: dict) -> Path:
    lines = ["# Formal 12 Evidence Relevance Review", "", "Stage A only. No model Provider calls.", ""]
    for qid in FORMAL_12_NEW:
        item = results[qid]
        spec = json.loads((output / qid / "relevance-spec.json").read_text(encoding="utf-8"))
        seed = json.loads((output / qid / "evidence-seed.json").read_text(encoding="utf-8"))
        rejected = json.loads((output / qid / "rejected-sources.json").read_text(encoding="utf-8"))
        assessments = json.loads((output / qid / "candidate-relevance-assessments.json").read_text(encoding="utf-8"))
        lines += [
            f"## {qid}: {spec['original_question']}",
            "",
            f"- domain: `{spec['domain_id']}`",
            f"- research object: {spec['research_object_anchors']}",
            f"- phenomenon/relation: {spec['phenomenon_or_relation_anchors']}",
            f"- mechanism: {spec['mechanism_or_constraint_anchors']}",
            f"- queries: {spec['query_variants']}",
            f"- Seed Ready: `{item['EVIDENCE_SEED_READY']}`",
            f"- DIRECT_CORE={item['DIRECT_CORE_COUNT']} SUPPORTING={item['SUPPORTING_MECHANISM_COUNT']} OFF_TOPIC_REJECTED={item['OFF_TOPIC_REJECTED_COUNT']}",
            "",
            "### Accepted sources",
            "",
        ]
        for card in seed.get("eligible_cards") or []:
            lines += [
                f"- `{card.get('source_id')}` status={card.get('topic_relevance_status')} role={card.get('evidence_role')}",
                f"  - locator: `{card.get('locator')}`",
                f"  - quote: {card.get('quoted_text')}",
                "",
            ]
        lines += ["### Rejected sources", ""]
        for row in (rejected.get("rejected") or [])[:12]:
            lines.append(
                f"- `{row.get('arxiv_id')}` reason={row.get('reason')} status={row.get('relevance_status')}"
            )
        if qid == "Q069":
            lines += [
                "",
                "### Q069 old off-topic sources",
                "",
            ]
            for arxiv_id in Q069_NEGATIVE_ARXIV:
                match = next((row for row in assessments.get("assessments") or [] if row.get("source_id") == f"arxiv:{arxiv_id}"), None)
                lines.append(f"- arXiv:{arxiv_id} status={(match or {}).get('relevance_status')} decision={(match or {}).get('acceptance_decision')}")
        lines.append("")
    path = output / "formal_12_evidence_relevance_review.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    ref = failed_batch_reference()
    write_json(OUTPUT / "formal_12_failed_batch_reference.json", ref)
    write_json(ROOT / "docs/reproducibility/formal_125/runs/formal_12_relevance_remediation_20260822-120516/formal_12_failed_batch_reference.json", ref)
    cause = root_cause()
    write_json(OUTPUT / "q069_relevance_root_cause.json", cause)
    write_json(ROOT / "docs/reproducibility/formal_125/runs/formal_12_relevance_remediation_20260822-120516/q069_relevance_root_cause.json", cause)
    audit = FulltextFetchAudit()
    results = {}
    for qid in FORMAL_12_NEW:
        catalog = _question_from_catalog(ROOT, qid)
        print(f"SEED_START={qid}", flush=True)
        bundle = build_seed_bundle(
            question_id=qid,
            question_title=catalog["original_title"],
            cache_root=CACHE,
            output_root=OUTPUT,
            audit=audit,
            local_cache_roots=LOCAL_CACHES,
        )
        gate = bundle.get("topic_gate") or {}
        results[qid] = {
            "EVIDENCE_SEED_READY": bool(bundle.get("evidence_seed_ready")),
            "DIRECT_CORE_COUNT": gate.get("direct_core_count"),
            "SUPPORTING_MECHANISM_COUNT": gate.get("supporting_mechanism_count"),
            "OFF_TOPIC_REJECTED_COUNT": gate.get("off_topic_count"),
            "seed_hash": gate.get("seed_hash"),
            "bundle_hash": bundle.get("bundle_hash"),
            "relevance_spec_hash": bundle.get("relevance_spec_hash"),
        }
        print(
            f"SEED_DONE={qid} ready={results[qid]['EVIDENCE_SEED_READY']} "
            f"direct={results[qid]['DIRECT_CORE_COUNT']} off={results[qid]['OFF_TOPIC_REJECTED_COUNT']}",
            flush=True,
        )
    review = write_review(OUTPUT, results)
    ready_count = sum(1 for row in results.values() if row["EVIDENCE_SEED_READY"])
    min_calls = len(CHAT_STEPS)
    nominal = 11
    worst = (len(CHAT_STEPS) + len(REVISION_STEPS)) * 2
    summary = {
        "STAGE_A_PROVIDER_CALLS": 0,
        "BAILIAN_CALLS": 0,
        "EMBEDDING_PROVIDER_CALLS": 0,
        "RERANK_PROVIDER_CALLS": 0,
        "DEEP_RESEARCH_CALLS": 0,
        "OPENROUTER_CALLS": 0,
        "PROJECT_PROVIDER_CALLS_CURRENT": 129,
        "LITERATURE_DISCOVERY_REQUESTS": audit.discovery_requests,
        "FULLTEXT_FETCH_REQUESTS": audit.fetch_requests,
        "FULLTEXT_FETCH_SUCCEEDED": audit.fetch_succeeded,
        "FULLTEXT_FETCH_FAILED": audit.fetch_failed,
        "NEW_CASE_EVIDENCE_SEED_READY_COUNT": ready_count,
        "FAILED_BATCH_REFERENCE_SHA256": ref["FAILED_BATCH_REFERENCE_SHA256"],
        "FORMAL_12_SELECTION_SHA256": FORMAL_12_SELECTION_SHA256,
        "SYSTEMIC_ROOT_CAUSE_CONFIRMED": True,
        "questions": results,
        "Q069_CANARY_MIN_PROVIDER_CALLS": min_calls,
        "Q069_CANARY_NOMINAL_PROVIDER_CALLS": nominal,
        "Q069_CANARY_WORST_CASE_PROVIDER_CALLS": worst,
        "Q069_CANARY_NOMINAL_INPUT_TOKENS": 59971,
        "Q069_CANARY_NOMINAL_OUTPUT_TOKENS": 11255,
        "Q069_CANARY_WORST_CASE_INPUT_TOKENS": 109038,
        "Q069_CANARY_WORST_CASE_OUTPUT_TOKENS": 20464,
        "Q069_CANARY_ESTIMATED_DURATION": "3-6 minutes serial",
        "ESTIMATED_COST_STATUS": "UNKNOWN",
        "NEW_CANARY_OUTPUT_ROOT": str(CANARY_ROOT),
        "review_report": str(review),
    }
    write_json(OUTPUT / "stage_a_summary.json", summary)
    write_json(ROOT / "docs/reproducibility/formal_125/runs/formal_12_relevance_remediation_20260822-120516/stage_a_summary.json", summary)
    print(json.dumps({"ready_count": ready_count, "discovery": audit.discovery_requests, "fetch_ok": audit.fetch_succeeded}, ensure_ascii=False))
    return 0 if ready_count == 10 else 2


if __name__ == "__main__":
    raise SystemExit(main())
