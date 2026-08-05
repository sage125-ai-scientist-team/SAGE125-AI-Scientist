"""
T01 Wave B（08/02）：Q028 回归测试。
"""

from app.core.schemas import EvidenceCard
from app.evidence.bundle_builder import build_evidence_bundle
from app.evidence.q028_regression import run_q028_regression
from app.evidence.support_checker import SupportErrorCode


def test_q028_regression_all_scenarios_pass():
    """Q028 四场景回归全部通过。"""
    report = run_q028_regression()
    assert report.all_passed is True
    data = report.to_dict()
    assert data["all_passed"] is True
    assert {s["scenario_id"] for s in data["scenarios"]} == {"S1", "S2", "S3", "S4"}


def test_q028_fake_booklet_id_blocked():
    """S1：booklet_excerpt_Q028 被阻断。"""
    report = run_q028_regression()
    s1 = next(s for s in report.scenarios if s.scenario_id == "S1")
    assert SupportErrorCode.FAKE_BOOKLET_EVIDENCE_ID.value in s1.after.error_codes
    assert s1.after.blocked is True


def test_q028_overgeneralization_degraded_not_allowed():
    """S3：跨癌种外推降级，不得 allow。"""
    report = run_q028_regression()
    s3 = next(s for s in report.scenarios if s.scenario_id == "S3")
    assert SupportErrorCode.OVERGENERALIZATION.value in s3.after.error_codes
    assert s3.after.allowed_links == []
    assert "Q028-C-OVER" in s3.after.degraded_claim_ids


def test_builder_dedupes_and_sorts_by_relevance():
    """截断前按相关性排序并按 quote/hash 去重。"""
    low = EvidenceCard(
        id="EV-LOW",
        source_type="arxiv",
        title="Low",
        authors=["A"],
        year=2020,
        url="https://example.org/a",
        doi=None,
        quoted_text="Same quoted body for dedupe test case.",
        summary="s",
        relevance_score=0.2,
        reliability_note="page=1",
    )
    high = EvidenceCard(
        id="EV-HIGH",
        source_type="arxiv",
        title="High",
        authors=["A"],
        year=2020,
        url="https://example.org/b",
        doi=None,
        quoted_text="Same quoted body for dedupe test case.",
        summary="s",
        relevance_score=0.95,
        reliability_note="page=2",
    )
    other = EvidenceCard(
        id="EV-OTHER",
        source_type="arxiv",
        title="Other",
        authors=["B"],
        year=2021,
        url="https://example.org/c",
        doi=None,
        quoted_text="Different quoted body remains after dedupe.",
        summary="s",
        relevance_score=0.5,
        reliability_note="page=3",
    )
    result = build_evidence_bundle(
        [low, other, high],
        bundle_id="B-DEDUP",
        token_budget=8000,
    )
    ids = [card.evidence_id for card in result.bundle.evidences]
    assert "EV-HIGH" in ids
    assert "EV-LOW" not in ids
    assert "EV-OTHER" in ids
    assert result.bundle.truncated is True
    assert result.bundle.truncation_reason is not None
    assert "dedupe_removed" in result.bundle.truncation_reason
