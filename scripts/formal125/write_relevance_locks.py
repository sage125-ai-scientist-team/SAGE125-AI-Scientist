"""Write v3 evidence/gate/batch locks and the relevance policy lock."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.formal125.hashes import sha256_canonical_json, write_json  # noqa: E402


def _with_hash(payload: dict, key: str) -> dict:
    payload[key] = sha256_canonical_json({name: value for name, value in payload.items() if name != key})
    return payload


def main() -> None:
    dest = ROOT / "docs/reproducibility/formal_125"
    relevance = _with_hash(
        {
            "lock_version": "formal125.evidence.relevance.v1",
            "source_verification_independent_of_topic": True,
            "topic_statuses": [
                "DIRECT_QUESTION_CORE",
                "SUPPORTING_MECHANISM",
                "METHOD_RELEVANT",
                "CONTEXT_ONLY",
                "OFF_TOPIC",
                "UNVERIFIED_RELEVANCE",
            ],
            "eligible_topic_statuses": ["DIRECT_QUESTION_CORE", "SUPPORTING_MECHANISM"],
            "fulltext_verified_off_topic_rejected": True,
            "metadata_only_direct_core_not_fact": True,
            "openalex_relevance_score_not_authoritative": True,
            "citation_count_not_authoritative": True,
            "generic_token_overlap_not_sufficient": True,
            "q069_permanent_negatives": ["arxiv:2411.00681", "arxiv:2307.15471"],
            "cache_key_includes": [
                "question_id",
                "question_hash",
                "domain_id",
                "query_spec_hash",
                "relevance_spec_hash",
                "evidence_policy_hash",
                "source_content_sha256",
            ],
            "content_parse_cache_may_cross_question": True,
            "relevance_decision_must_not_cross_question": True,
            "seed_ready_requires": [
                "two_distinct_fulltext_sources",
                "at_least_one_direct_question_core",
                "second_direct_or_supporting_mechanism",
                "quote_and_locator",
                "no_off_topic_eligible",
            ],
        },
        "relevance_policy_sha256",
    )
    write_json(dest / "formal_125_evidence_relevance_policy.lock.v1.json", relevance)

    evidence_v3 = _with_hash(
        {
            "lock_version": "formal125.evidence.v3",
            "inherits": "formal125.evidence.v2",
            "previous_hash": "d33c440d95559b3b11c694948a2627995b267f1b92d648429510a73a2b6940bb",
            "formal_evidence_mode": "oa_fulltext_verified_and_topic_relevant",
            "source_statuses": [
                "FULLTEXT_VERIFIED",
                "ABSTRACT_VERIFIED",
                "METADATA_ONLY",
                "QUESTION_SOURCE",
                "FETCH_FAILED",
                "LICENSE_RESTRICTED",
            ],
            "topic_relevance_required_for_eligibility": True,
            "minimum_fulltext_sources_per_question": 2,
            "minimum_direct_question_core": 1,
            "method_relevant_alone_not_ready": True,
            "context_only_not_counted": True,
            "off_topic_not_eligible": True,
            "unknown_evidence_id_policy": "fail_closed_at_parse_no_fuzzy_repair",
            "locator_required": True,
            "change_reason": "Fulltext availability is not topic relevance.",
            "backward_compatibility": False,
            "invalidated_checkpoints": ["formal_12_domain_real_20260822-014248"],
        },
        "evidence_policy_sha256",
    )
    write_json(dest / "formal_125_evidence_policy.lock.v3.json", evidence_v3)

    gate_v3 = _with_hash(
        {
            "lock_version": "formal125.gate.v3",
            "previous_hash": "ef241a57b019b143ba212bc3b3531e14be1b29e21040dd263f239639c1f29521",
            "inherits": "formal125.gate.v2",
            "added_gates": [
                "topic_relevance_independent_of_fulltext",
                "off_topic_fulltext_rejected",
                "question_bound_relevance_cache",
                "content_bearing_similarity_only",
                "q069_negative_arxiv_regression",
            ],
            "p0_fail_closed": True,
            "p1_fail_closed": True,
            "change_reason": "Canary failed because off-topic fulltext entered the seed.",
            "backward_compatibility": False,
            "invalidated_checkpoints": ["formal_12_domain_real_20260822-014248"],
        },
        "gate_policy_sha256",
    )
    write_json(dest / "formal_125_gate_policy.lock.v3.json", gate_v3)

    batch_v2 = _with_hash(
        {
            "lock_version": "formal125.batch.v2",
            "previous_hash": "aa1e7cc2d1799956eb014018a03e7cd58424eef67017da0d434d708b3a0fbac1",
            "canary_question_id": "Q069",
            "canary_stop_on_systemic_p0": True,
            "canary_does_not_auto_continue_remaining_nine": True,
            "blocked_shell_similarity_not_scientific_leak": True,
            "content_bearing_flag_required": True,
            "max_concurrency": 1,
            "change_reason": "Separate Q069 canary rerun from remaining nine questions.",
            "backward_compatibility": False,
            "invalidated_checkpoints": ["formal_12_domain_real_20260822-014248"],
        },
        "batch_policy_sha256",
    )
    write_json(dest / "formal_125_batch_policy.lock.v2.json", batch_v2)
    print("relevance", relevance["relevance_policy_sha256"])
    print("evidence_v3", evidence_v3["evidence_policy_sha256"])
    print("gate_v3", gate_v3["gate_policy_sha256"])
    print("batch_v2", batch_v2["batch_policy_sha256"])


if __name__ == "__main__":
    main()
