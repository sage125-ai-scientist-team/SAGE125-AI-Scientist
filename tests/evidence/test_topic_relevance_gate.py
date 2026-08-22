"""Topic relevance is independent of fulltext availability."""

from __future__ import annotations

from pathlib import Path

from app.evidence.relevance import (
    Q069_NEGATIVE_ARXIV,
    TOPIC_DIRECT,
    TOPIC_OFF,
    RelevanceAssessmentCache,
    assess_candidate,
    assessment_cache_key,
    build_relevance_spec,
    evaluate_seed_gate,
    is_content_bearing,
)
from app.formal125.formal12 import content_bearing_similarity_summary


def _spec(question_id: str = "Q069") -> dict:
    catalog = Path(__file__).resolve().parents[2] / "docs/reproducibility/formal_125/catalog/questions_125.lock.json"
    import json

    for item in json.loads(catalog.read_text(encoding="utf-8"))["questions"]:
        if item["question_id"] == question_id:
            return build_relevance_spec(item)
    raise AssertionError(question_id)


def test_q069_negative_arxiv_ids_are_off_topic_even_if_fulltext():
    spec = _spec("Q069")
    texts = {
        "2411.00681": "This proactive stance allows early identification of network operations and AI-based works.",
        "2307.15471": "Due to limitations in quantifying mutation burden, somatic mutations in ageing phenotypes remain unclear.",
    }
    for arxiv_id, text in texts.items():
        assessment = assess_candidate(
            spec=spec,
            source_id=f"arxiv:{arxiv_id}",
            source_content_sha256="c" * 64,
            title=f"arXiv:{arxiv_id}",
            abstract=text,
            fulltext=text * 4,
            query_origin="unit",
            discovery_rank=1,
            discovery_relevance_score=0.99,
            fulltext_available=True,
            evidence_policy_hash="formal125.evidence.v3",
        )
        assert assessment["relevance_status"] == TOPIC_OFF
        assert assessment["acceptance_decision"] == "REJECT"
        assert arxiv_id in Q069_NEGATIVE_ARXIV


def test_q069_direct_core_from_optical_diffraction_fulltext():
    spec = _spec("Q069")
    text = (
        "The diffraction limit of optical microscopy, often associated with the Abbe limit, "
        "sets the resolution of a conventional optical microscope. Super-resolution methods "
        "such as STED bypass the diffraction limit."
    )
    assessment = assess_candidate(
        spec=spec,
        source_id="arxiv:2006.14355",
        source_content_sha256="d" * 64,
        title="Super-resolution microscopy and the diffraction limit",
        abstract=text,
        fulltext=text * 3,
        query_origin="unit",
        discovery_rank=1,
        discovery_relevance_score=0.1,
        fulltext_available=True,
        evidence_policy_hash="formal125.evidence.v3",
    )
    assert assessment["relevance_status"] == TOPIC_DIRECT
    assert assessment["acceptance_decision"] == "ACCEPT"


def test_metadata_only_cannot_be_direct_core():
    spec = _spec("Q069")
    assessment = assess_candidate(
        spec=spec,
        source_id="doi:10.0/example",
        source_content_sha256="",
        title="Is there a diffraction limit in optical microscopy?",
        abstract="",
        fulltext="",
        query_origin="openalex",
        discovery_rank=1,
        discovery_relevance_score=0.95,
        fulltext_available=False,
        evidence_policy_hash="formal125.evidence.v3",
    )
    assert assessment["relevance_status"] != TOPIC_DIRECT
    assert assessment["acceptance_decision"] == "REJECT"


def test_seed_gate_requires_direct_core_not_just_fulltext():
    spec = _spec("Q069")
    off = assess_candidate(
        spec=spec,
        source_id="arxiv:2411.00681",
        source_content_sha256="a" * 64,
        title="x",
        abstract="network operations",
        fulltext="network operations " * 20,
        query_origin="unit",
        discovery_rank=1,
        discovery_relevance_score=0.8,
        fulltext_available=True,
        evidence_policy_hash="v3",
    )
    gate = evaluate_seed_gate(
        question_id="Q069",
        assessments=[off, off],
        eligible_ids=[],
        rejected_source_ids=["2411.00681"],
        spec_hash=spec["spec_hash"],
    )
    assert gate["gate_status"] == "NOT_READY"
    assert "missing_direct_question_core" in gate["blocking_reasons"]


def test_q069_cannot_read_other_question_relevance_cache():
    spec_q069 = _spec("Q069")
    spec_q109 = _spec("Q109")
    cache = RelevanceAssessmentCache()
    key = assessment_cache_key(
        question_id=spec_q109["question_id"],
        question_hash=spec_q109["question_hash"],
        domain_id=spec_q109["domain_id"],
        query_spec_hash=spec_q109["query_spec_hash"],
        relevance_spec_hash=spec_q109["spec_hash"],
        evidence_policy_hash="v3",
        source_content_sha256="e" * 64,
    )
    cache.put(key, {"question_id": "Q109", "question_hash": spec_q109["question_hash"], "relevance_status": TOPIC_DIRECT})
    assert cache.get_for_question(key, "Q069", spec_q069["question_hash"]) is None
    assert cache.get_for_question(key, "Q109", spec_q109["question_hash"]) is not None


def test_blocked_shell_similarity_is_not_content_bearing():
    blocked = {
        "status": "blocked",
        "blocked_reason": "CANARY_SYSTEMIC_FAILURE",
        "generated_hypotheses": [],
        "paper_title": "Q003 blocked by Formal 12 canary",
    }
    scientific = {
        "status": "partial",
        "generated_hypotheses": [{"hypothesis": "diffraction limit exists in far-field optics"}],
        "paper_title": "Optical diffraction",
    }
    assert is_content_bearing(blocked) is False
    assert is_content_bearing(scientific) is True
    summary = content_bearing_similarity_summary({"Q003": blocked, "Q026": blocked, "Q069": scientific})
    assert summary["blocked_template_duplicate_count"] == 2
    assert summary["content_bearing_max_similarity"] == 0.0
