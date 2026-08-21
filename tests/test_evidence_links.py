"""Safe canonical evidence links and metadata-only quality checks."""

from __future__ import annotations

from app.core.evidence_links import canonical_evidence_link
from app.ui import components
from app.workflow.quality_gates import check_evidence_grounding, check_reference_integrity


def test_canonical_doi_arxiv_and_openalex_links():
    doi = canonical_evidence_link({
        "source_type": "crossref",
        "doi": "10.3389/fimmu.2022.899657",
    })
    assert doi and doi.url == "https://doi.org/10.3389/fimmu.2022.899657"

    arxiv = canonical_evidence_link({
        "source_type": "arxiv",
        "url": "http://arxiv.org/abs/2404.18731v3",
    })
    assert arxiv and arxiv.url == "https://arxiv.org/abs/2404.18731v3"

    arxiv_pdf = canonical_evidence_link({
        "source_type": "arxiv",
        "url": "https://arxiv.org/pdf/1510.03465.pdf",
    })
    assert arxiv_pdf and arxiv_pdf.url == "https://arxiv.org/abs/1510.03465"

    arxiv_old = canonical_evidence_link({
        "source_type": "arxiv",
        "url": "https://arxiv.org/pdf/hep-ph/9705325.pdf",
    })
    assert arxiv_old and arxiv_old.url == "https://arxiv.org/abs/hep-ph/9705325"


    openalex = canonical_evidence_link({
        "source_type": "openalex",
        "id": "https://openalex.org/W4280513190",
    })
    assert openalex and openalex.url == "https://openalex.org/W4280513190"


def test_untrusted_or_spoofed_urls_never_become_links():
    cases = [
        {"source_type": "deep_research", "doi": "10.1000/looks-real", "url": "https://doi.org/10.1000/looks-real"},
        {"source_type": "arxiv", "url": "javascript:alert(1)"},
        {"source_type": "arxiv", "url": "https://arxiv.org.evil.example/abs/2404.18731"},
        {"source_type": "openalex", "url": "https://openalex.org.evil.example/W123"},
        {"source_type": "crossref", "doi": '10.1234/<script>alert(1)</script>'},
        {"source_type": "crossref", "doi": "10.1234/good", "reliability_note": "mock_for_testing"},
    ]
    assert all(canonical_evidence_link(card) is None for card in cases)


def test_ui_link_has_safe_new_tab_attributes_and_ignores_raw_url():
    html = components._evidence_reference_html({
        "source_type": "crossref",
        "doi": "10.1177/09636897221148771",
        "url": "javascript:alert(1)",
    })
    assert 'href="https://doi.org/10.1177/09636897221148771"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer nofollow"' in html
    assert "javascript:" not in html


def test_metadata_title_cannot_ground_hypothesis_or_fact():
    card = {
        "id": "W1",
        "source_type": "openalex",
        "title": "A real title",
        "quoted_text": "A real title",
        "doi": "10.1000/real",
        "url": "https://openalex.org/W1",
        "relevance_score": 0.5,
    }
    plan = {"references": [card], "generated_hypotheses": []}
    result = check_evidence_grounding(
        plan,
        [card],
        hypothesis_generation={"hypotheses": [{"supporting_evidence_ids": ["W1"]}]},
        evidence_extraction={"established_facts": [{"evidence_ids": ["W1"]}]},
    )
    assert result["passed"] is False
    assert any("元数据标题" in error for error in result["errors"])


def test_reference_metadata_must_match_retrieved_card():
    original = {
        "id": "W4280513190",
        "source_type": "openalex",
        "title": "Original title",
        "quoted_text": "Original title",
        "doi": "10.3389/fimmu.2022.899657",
        "url": "https://openalex.org/W4280513190",
        "reliability_note": "openalex_metadata",
    }
    altered = {**original, "doi": "10.1000/rewritten"}
    result = check_reference_integrity({"references": [altered]}, [original])
    assert result["passed"] is False
    assert any("与 EvidenceCard 不一致" in error for error in result["errors"])

