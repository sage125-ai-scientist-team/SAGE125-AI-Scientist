# -*- coding: utf-8 -*-
from app.ui.results_root import EXPECTED_QUESTION_IDS, resolve_results_root
from app.ui.ui_summary import compute_ui_summary, is_traceable_evidence_card


def test_catalog_and_results_root_are_official_125() -> None:
    resolved = resolve_results_root()
    assert set(resolved.catalog_ids) == set(EXPECTED_QUESTION_IDS)
    assert len(resolved.catalog_ids) == 125
    assert resolved.intact is True
    assert resolved.results_root is not None
    assert resolved.results_root.name == "formal_125_release_candidate_zh_paper_20260822-232920"


def test_traceable_card_requires_locator_and_hash() -> None:
    card = {
        "id": "EV-Q001-abc",
        "title": "arXiv:1",
        "quoted_text": "quote",
        "url": "https://arxiv.org/pdf/1.pdf",
        "reliability_note": "eligibility_status=FULLTEXT_VERIFIED; locator=page:1; content_sha256=abc",
    }
    assert is_traceable_evidence_card(card, "Q001") is True
    assert is_traceable_evidence_card({**card, "reliability_note": ""}, "Q001") is False


def test_compute_ui_summary_has_real_counts() -> None:
    summary = compute_ui_summary()
    assert summary["status"] == "calculated"
    assert summary["official_question_count"] == 125
    assert summary["traceable_evidence_count"] > 0
    assert summary["research_plan_count"] > 0
    assert summary["total_supporting_evidence_links"] > 0
    assert summary["resolved_supporting_evidence_links"] > 0
    assert summary["evidence_link_coverage_status"] == "calculated"
    assert summary["evidence_link_coverage"] is not None
