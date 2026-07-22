"""Quality gate checks hypothesis/fact-level evidence links, not only references."""

from app.workflow.quality_gates import check_evidence_grounding


def _card(eid="E1", relevance=0.9):
    return {
        "id": eid,
        "title": "Source",
        "quoted_text": "A verifiable source passage.",
        "relevance_score": relevance,
    }


def test_missing_hypothesis_support_fails():
    result = check_evidence_grounding(
        {"references": [_card()]},
        [_card()],
        hypothesis_generation={"hypotheses": [{"hypothesis": "H", "supporting_evidence_ids": []}]},
    )
    assert result["passed"] is False
    assert any("supporting_evidence_ids" in error for error in result["errors"])


def test_unknown_fact_and_hypothesis_ids_fail():
    result = check_evidence_grounding(
        {"references": [_card()]},
        [_card()],
        hypothesis_generation={"hypotheses": [{"supporting_evidence_ids": ["E404"]}]},
        evidence_extraction={"established_facts": [{"fact": "F", "evidence_ids": ["E404"]}]},
    )
    assert result["passed"] is False
    assert sum("E404" in error for error in result["errors"]) >= 2

