"""Offline Formal 12 stage A tests. No provider calls."""

from __future__ import annotations

import json
from pathlib import Path

from app.evidence.eligibility import SourceEligibility
from app.evidence.oa_fulltext import FulltextFetchAudit
from app.evidence.remediation import build_seed_bundle, scan_local_arxiv_cache
from app.formal125.formal12 import (
    AUTHORIZATION_TEXT,
    CANARY_QUESTION_ID,
    EXPECTED_LOCKS,
    FORMAL_12_CASE_IDS,
    FORMAL_12_SELECTION_SHA256,
    PROJECT_PROVIDER_CALLS_BEFORE_FORMAL_12,
    build_lock_bundle,
    compute_budget,
    evaluate_canary,
    evaluate_reuse_eligibility,
    plan_only_rehearsal,
)
from app.formal125.readonly_display import latest_domains, latest_formal_run


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_authorization_text_is_exact() -> None:
    assert AUTHORIZATION_TEXT == "AUTHORIZE_FORMAL_12_DOMAIN_REAL_RUN=YES"
    assert AUTHORIZATION_TEXT != "继续"
    assert PROJECT_PROVIDER_CALLS_BEFORE_FORMAL_12 == 121


def test_frozen_twelve_order_and_selection_hash() -> None:
    selection = json.loads(
        (REPO_ROOT / "docs/reproducibility/formal_125/formal_12_domain_selection_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert selection["question_ids"] == list(FORMAL_12_CASE_IDS)
    assert selection["selection_sha256"] == FORMAL_12_SELECTION_SHA256
    assert CANARY_QUESTION_ID == "Q069"
    assert FORMAL_12_CASE_IDS[1] == "Q069"


def test_lock_bundle_uses_attempt2_v2_not_preflight_v1() -> None:
    bundle = build_lock_bundle(REPO_ROOT)
    for key, expected in EXPECTED_LOCKS.items():
        assert bundle[key] == expected
    assert bundle["PROMPT_LOCK_SHA256"] != "5b12d88b01fc18278dc2d90087caf374e8be0a0ab57eb567c37a2b7121d4e8d2"


def test_reuse_eligibility_q001_q107() -> None:
    locks = build_lock_bundle(REPO_ROOT)
    q001 = evaluate_reuse_eligibility(REPO_ROOT, "Q001", locks)
    q107 = evaluate_reuse_eligibility(REPO_ROOT, "Q107", locks)
    assert q001["eligible"] is True, q001["failed_checks"]
    assert q107["eligible"] is True, q107["failed_checks"]
    assert q001["reused_without_new_provider_call"] is True
    assert q001["immutable_source"] is True


def test_budget_is_not_twelve_times_eleven() -> None:
    budget = compute_budget(10)
    assert budget["FORMAL_12_MIN_PROVIDER_CALLS"] == 80
    assert budget["FORMAL_12_NOMINAL_PROVIDER_CALLS"] == 110
    assert budget["FORMAL_12_WORST_CASE_PROVIDER_CALLS"] == 200
    assert budget["FORMAL_12_NOMINAL_PROVIDER_CALLS"] != 12 * 11
    assert budget["ESTIMATED_COST_STATUS"] == "UNKNOWN"
    assert budget["max_concurrency"] == 1
    reused_zero = compute_budget(12)
    assert reused_zero["FORMAL_12_NOMINAL_PROVIDER_CALLS"] == 132


def test_seed_bundle_uses_existing_oa_pipeline(tmp_path: Path, monkeypatch) -> None:
    pages = [{"page": 1, "text": "Diffraction limit optics resolution Abbe criterion for imaging systems. " * 8}]

    def fake_search(query: str, max_results: int, audit: FulltextFetchAudit) -> list[str]:
        audit.discovery_requests += 1
        return ["2401.00001", "2401.00002"]

    def fake_fetch(*, arxiv_id: str, cache_root: Path, audit: FulltextFetchAudit) -> dict:
        audit.fetch_requests += 1
        audit.fetch_succeeded += 1
        return {
            "eligibility": SourceEligibility.FULLTEXT_VERIFIED.value,
            "arxiv_id": arxiv_id,
            "url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "content_sha256": "a" * 64 if arxiv_id.endswith("1") else "b" * 64,
            "cache_dir": str(tmp_path / arxiv_id),
            "pages": pages,
        }

    monkeypatch.setattr("app.evidence.remediation._arxiv_search", fake_search)
    monkeypatch.setattr("app.evidence.remediation.fetch_arxiv_pdf", fake_fetch)
    audit = FulltextFetchAudit()
    bundle = build_seed_bundle(
        question_id="Q069",
        question_title="Is there a diffraction limit?",
        cache_root=tmp_path / "cache",
        output_root=tmp_path / "out",
        audit=audit,
        local_cache_roots=[],
    )
    assert bundle["evidence_seed_ready"] is True
    assert bundle["fulltext_verified_source_count"] >= 2
    assert bundle["unknown_evidence_id_count"] == 0
    assert bundle["booklet_evidence_count"] == 0
    assert all(item.startswith("EV-Q069-") for item in bundle["allowed_evidence_ids"])
    assert audit.discovery_requests >= 1


def test_local_cache_scan_requires_keyword_overlap(tmp_path: Path) -> None:
    item = tmp_path / "aa" / "digest"
    item.mkdir(parents=True)
    (item / "source_manifest.json").write_text(
        json.dumps({"source_id": "arxiv:1234.5678"}),
        encoding="utf-8",
    )
    (item / "parsed_text.json").write_text("prime numbers cryptography zeta function", encoding="utf-8")
    assert scan_local_arxiv_cache([tmp_path], ["diffraction", "optics", "Abbe"]) == []
    assert scan_local_arxiv_cache([tmp_path], ["prime", "cryptography", "zeta"]) == ["1234.5678"]


def test_plan_only_rehearsal_has_no_provider_and_no_q028(tmp_path: Path) -> None:
    for question_id in FORMAL_12_CASE_IDS:
        payload = {
            "allowed_evidence_ids": [f"EV-{question_id}-aaaaaaaaaaaaaaaaaaaaaaaa"],
            "bundle_hash": "c" * 64,
            "fulltext_verified_source_count": 2,
        }
        path = tmp_path / question_id
        path.mkdir()
        (path / "evidence_bundle.json").write_text(json.dumps(payload), encoding="utf-8")
    locks = build_lock_bundle(REPO_ROOT)
    report = plan_only_rehearsal(REPO_ROOT, tmp_path, locks)
    assert report["provider_calls_in_stage_a"] == 0
    assert report["OPENROUTER_ROUTE_COUNT"] == 0
    assert report["MOCK_ROUTE_COUNT"] == 0
    assert report["HARDCODED_CASE_LEAK_COUNT"] == 0
    assert report["CROSS_QUESTION_PROMPT_LEAK_COUNT"] == 0
    assert report["CROSS_QUESTION_EVIDENCE_LEAK_COUNT"] == 0


def test_canary_stops_on_unknown_id(tmp_path: Path) -> None:
    question_dir = tmp_path / "Q069"
    question_dir.mkdir()
    (question_dir / "evidence_bundle.json").write_text(
        json.dumps({"allowed_evidence_ids": ["EV-Q069-aaaaaaaaaaaaaaaaaaaaaaaa"], "bundle_hash": "d" * 64}),
        encoding="utf-8",
    )
    (question_dir / "evidence_cards.json").write_text("[]", encoding="utf-8")
    (question_dir / "result.json").write_text(
        json.dumps({"generated_hypotheses": [{"supporting_evidence_ids": ["Q028_booklet"]}]}),
        encoding="utf-8",
    )
    (question_dir / "validation.json").write_text(json.dumps({"p0_count": 1}), encoding="utf-8")
    (question_dir / "package_manifest.json").write_text(json.dumps({"status": "partial"}), encoding="utf-8")
    report = evaluate_canary(question_dir)
    assert report["continue_remaining_new_cases"] is False
    assert report["canary_code"] == "CANARY_SYSTEMIC_FAILURE"


def test_readonly_display_hides_secrets() -> None:
    payload = latest_formal_run()
    text = json.dumps(payload)
    assert "DASHSCOPE_API_KEY" not in text
    assert "sk-" not in text
    domains = latest_domains()
    assert domains["count"] == 12
