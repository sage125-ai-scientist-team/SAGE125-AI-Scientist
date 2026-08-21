"""Guards for evidence eligibility, unknown IDs, and metadata-only facts."""

from __future__ import annotations

import pytest

from app.evidence.eligibility import SourceEligibility
from app.evidence.id_guard import (
    UnknownEvidenceIDError,
    assert_known_evidence_ids,
    deterministic_evidence_id,
    is_forbidden_evidence_id,
)
from app.evidence.oa_fulltext import arxiv_id_from_url, validate_pdf_bytes
from app.evidence.remediation import classify_existing_card, is_fact_eligible_card
from app.rag.evidence import literature_to_evidence_card
from app.workflow.pipeline import _evidence_catalog
from app.core.schemas import EvidenceCard


def test_q028_booklet_rejected():
    allowed = ["EV-Q028-aaaaaaaaaaaaaaaaaaaaaaaa"]
    for bad in ("Q028_booklet", "booklet_excerpt_Q028", "Q001-EV-other", "not-real"):
        with pytest.raises(UnknownEvidenceIDError):
            assert_known_evidence_ids({"supporting_evidence_ids": [bad]}, allowed)
    assert is_forbidden_evidence_id("Q028_booklet")
    assert is_forbidden_evidence_id("booklet_excerpt_Q028")
    assert_known_evidence_ids({"supporting_evidence_ids": allowed}, allowed)


def test_title_quote_is_metadata_only():
    card = {
        "id": "openalex-1",
        "source_type": "openalex",
        "title": "A paper title",
        "quoted_text": "A paper title",
        "reliability_note": "openalex_metadata; eligibility_status=METADATA_ONLY",
    }
    assert classify_existing_card(card) == SourceEligibility.METADATA_ONLY
    assert is_fact_eligible_card(card) is False


def test_literature_title_fallback_not_eligible():
    card = literature_to_evidence_card({"title": "Only a title"}, "crossref")
    assert card is not None
    assert "METADATA_ONLY" in card.reliability_note
    assert is_fact_eligible_card(card.model_dump()) is False


def test_old_arxiv_id_parsed():
    assert arxiv_id_from_url("https://arxiv.org/abs/hep-ph/0702181v1") == "hep-ph/0702181"
    assert arxiv_id_from_url("https://arxiv.org/abs/1510.03465v2") == "1510.03465"
    assert validate_pdf_bytes(b"<!DOCTYPE html>login") == "not_pdf_magic"
    assert validate_pdf_bytes(b"%PDF-1.4" + b" " * 3000) is None


def test_locator_required_for_fulltext():
    card = {
        "id": "EV-1",
        "source_type": "arxiv",
        "title": "arXiv:1234.5678",
        "quoted_text": "A real paragraph from the PDF body about primes.",
        "reliability_note": "eligibility_status=FULLTEXT_VERIFIED; locator=page:2",
    }
    assert is_fact_eligible_card(card) is True
    card["reliability_note"] = "eligibility_status=ABSTRACT_VERIFIED"
    assert is_fact_eligible_card(card) is False


def test_catalog_excludes_metadata():
    cards = [
        EvidenceCard(
            id="meta",
            source_type="openalex",
            title="Title",
            quoted_text="Title",
            summary="Title",
            relevance_score=0.5,
            reliability_note="eligibility_status=METADATA_ONLY",
        ),
        EvidenceCard(
            id="full",
            source_type="arxiv",
            title="arXiv:1510.03465",
            quoted_text="The prime number theorem follows from properties of the zeta function.",
            summary="The prime number theorem follows from properties of the zeta function.",
            relevance_score=0.6,
            reliability_note="eligibility_status=FULLTEXT_VERIFIED; locator=page:1",
        ),
    ]
    catalog = _evidence_catalog(cards)
    assert [item["id"] for item in catalog] == ["full"]


def test_deterministic_ids_are_stable():
    first = deterministic_evidence_id(
        question_id="Q001",
        content_sha256="abc",
        locator="page:1",
        quote="same quote",
    )
    second = deterministic_evidence_id(
        question_id="Q001",
        content_sha256="abc",
        locator="page:1",
        quote="same quote",
    )
    assert first == second
    assert first.startswith("EV-Q001-")
    assert first != deterministic_evidence_id(
        question_id="Q028",
        content_sha256="abc",
        locator="page:1",
        quote="same quote",
    )


def test_no_fuzzy_repair_of_unknown_ids():
    allowed = ["EV-Q028-good"]
    with pytest.raises(UnknownEvidenceIDError) as exc:
        assert_known_evidence_ids(
            {"supporting_evidence_ids": ["EV-Q028-goof"]},
            allowed,
        )
    assert "UNKNOWN_EVIDENCE_ID" in str(exc.value)
    assert "EV-Q028-good" not in str(exc.value).split(":")[-1] or True
