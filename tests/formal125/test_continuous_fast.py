from __future__ import annotations

import json
from pathlib import Path

from app.evidence.relevance import GENERIC_BANNED, build_relevance_spec
from app.formal125.authorization import Formal125RunAuthorization, compute_authorization_hash
from app.formal125.continuous_fast import (
    AUTH_MAX_CALLS,
    MANUAL_REVIEW_24,
    NOMINAL_CALLS,
    REUSED_CASE_IDS,
    WORST_CASE_CALLS,
    assign_waves,
    budget_from_measured_results,
    catalog_item,
    claim_evidence_job,
    generic_template_from_catalog,
    init_queue,
    load_catalog,
    official_question_ids,
    remaining_case_ids,
    reuse_mode,
    verify_set_identity,
)


def test_set_identity_is_125_minus_15() -> None:
    identity = verify_set_identity()
    assert identity == {"TOTAL": 125, "REUSED": 15, "REMAINING": 110, "INTERSECTION": 0, "UNION": 125}
    remaining = remaining_case_ids()
    assert remaining == sorted(remaining, key=lambda item: int(item[1:]))
    assert len(remaining) == 110
    assert set(REUSED_CASE_IDS).isdisjoint(remaining)
    assert set(official_question_ids()) == set(REUSED_CASE_IDS) | set(remaining)


def test_q095_stays_genuine_partial_mode() -> None:
    assert reuse_mode("Q095") == "REUSED_VERIFIED_GENUINE_PARTIAL"
    assert reuse_mode("Q001") == "REUSED_VERIFIED_FORMAL_RESULT"
    assert "Q095" in REUSED_CASE_IDS


def test_waves_cover_110_without_gap() -> None:
    waves = assign_waves(remaining_case_ids())
    assert len(waves) == 110
    assert max(item["wave"] for item in waves) == 11
    assert min(item["wave"] for item in waves) == 1
    assert sum(1 for item in waves if item["wave_sentinel"]) == 11


def test_generic_spec_uses_official_anchors_and_avoids_banned(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    catalog = load_catalog(repo)
    item = catalog_item(catalog, "Q002")
    template = generic_template_from_catalog(item)
    from app.evidence.relevance import SPEC_TEMPLATES

    SPEC_TEMPLATES["Q002"] = template
    spec = build_relevance_spec(item)
    blob = json.dumps(spec).casefold()
    for banned in GENERIC_BANNED:
        for group in spec["research_object_anchors"]:
            assert banned not in {term.casefold() for term in group}
    assert "navier" in blob
    assert spec["query_variants"]


def test_budget_covers_nominal_and_one_retry() -> None:
    budget = budget_from_measured_results()
    assert budget["NOMINAL_CALLS"] == 1210
    assert budget["WORST_CASE_CALLS"] == 2200
    assert AUTH_MAX_CALLS == WORST_CASE_CALLS
    assert AUTH_MAX_CALLS >= NOMINAL_CALLS
    assert budget["covers_one_frozen_retry"] is True
    assert budget["estimated_cost"] == "unknown"


def test_authorization_payload_is_110_only() -> None:
    remaining = remaining_case_ids()
    payload = {
        "authorization_id": "formal125-fast-test",
        "authorized_by_role": "captain",
        "authorized_case_ids": remaining,
        "provider": "bailian",
        "model_lock_hash": "a" * 64,
        "prompt_lock_hash": "b" * 64,
        "schema_lock_hash": "c" * 64,
        "catalog_hash": "d" * 64,
        "max_total_provider_calls": AUTH_MAX_CALLS,
        "max_retries": 1,
        "max_total_input_tokens": 100,
        "max_total_output_tokens": 100,
        "max_concurrency": 4,
        "output_root": "D:/tmp",
        "expires_at": "2026-09-30T00:00:00+00:00",
    }
    payload["authorization_hash"] = compute_authorization_hash(payload)
    auth = Formal125RunAuthorization.model_validate(payload)
    assert len(auth.authorized_case_ids) == 110
    assert "Q095" not in auth.authorized_case_ids
    assert "Q001" not in auth.authorized_case_ids


def test_sqlite_claim_is_single_winner(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    catalog = load_catalog(repo)
    remaining = remaining_case_ids()[:3]
    init_queue(tmp_path, remaining, catalog)
    first = claim_evidence_job(tmp_path, "w1")
    second = claim_evidence_job(tmp_path, "w2")
    third = claim_evidence_job(tmp_path, "w3")
    fourth = claim_evidence_job(tmp_path, "w4")
    assert {first, second, third} == set(remaining)
    assert fourth is None


def test_manual_review_list_is_frozen_24() -> None:
    assert len(MANUAL_REVIEW_24) == 24
    assert MANUAL_REVIEW_24[0] == "Q001"
    assert MANUAL_REVIEW_24[-1] == "Q118"
