"""
T01 Wave C：冲突/反例证据不被静默覆盖；撤稿占位门禁。
"""

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.evidence.quality_gate import (
    ConflictDisposition,
    EvidenceSourceStatus,
    SourceLifecycleStatus,
    detect_conflicts_preserving_both_sides,
    run_quality_gate,
)


def _card(evidence_id: str, quote: str) -> EvidenceCardContract:
    """
    构造最小可用证据卡。

    参数：
        evidence_id: 证据 ID。
        quote: 原文。

    返回：
        EvidenceCardContract。
    """
    return EvidenceCardContract(
        evidence_id=evidence_id,
        source_id=f"src-{evidence_id}",
        source_type="paper",
        title=f"Title {evidence_id}",
        quoted_text=quote,
        locator={"page": 1, "section": "Results"},
        authors=["A"],
        year=2024,
        doi=f"10.1234/{evidence_id.lower()}",
        content_hash=f"sha256:{evidence_id.lower()}",
        domain="oncology",
        verification_status="pending",
    )


def _conflict_bundle() -> EvidenceBundle:
    """
    构造同一声明同时 supports + contradicts 的 Bundle。

    返回：
        EvidenceBundle。
    """
    return EvidenceBundle(
        bundle_id="B-CONFLICT",
        evidences=[
            _card("EV-SUP", "EGFR inhibition improves response in lung adenocarcinoma."),
            _card(
                "EV-CON",
                "EGFR inhibition failed to improve response in the same cohort.",
            ),
        ],
        links=[
            ClaimEvidenceLink(
                claim_id="C1",
                evidence_id="EV-SUP",
                relation="supports",
                claim_domain="oncology",
            ),
            ClaimEvidenceLink(
                claim_id="C1",
                evidence_id="EV-CON",
                relation="contradicts",
                claim_domain="oncology",
            ),
        ],
    )


def test_conflict_preserves_both_sides():
    """冲突两侧证据 ID 均保留，禁止静默覆盖。"""
    bundle = _conflict_bundle()
    records = detect_conflicts_preserving_both_sides(bundle)
    assert len(records) == 1
    record = records[0]
    assert record.claim_id == "C1"
    assert record.support_evidence_ids == ("EV-SUP",)
    assert record.contradict_evidence_ids == ("EV-CON",)
    assert record.counterexample_evidence_ids == ("EV-CON",)
    assert record.silently_overwritten is False


def test_quality_gate_flags_retracted_support():
    """撤稿证据不得伪装支撑 established facts。"""
    bundle = _conflict_bundle()
    statuses = {
        "EV-SUP": EvidenceSourceStatus(
            evidence_id="EV-SUP",
            lifecycle=SourceLifecycleStatus.RETRACTED,
            note="retraction placeholder",
        ),
        "EV-CON": EvidenceSourceStatus(
            evidence_id="EV-CON",
            lifecycle=SourceLifecycleStatus.PLACEHOLDER,
            note="not verified",
        ),
    }
    report = run_quality_gate(
        bundle,
        status_by_id=statuses,
        disposition=ConflictDisposition.KEEP_BOTH_FLAGGED,
    )
    assert "EV-SUP" in report.retracted_blocked_ids
    assert report.conflict_records[0].support_evidence_ids == ("EV-SUP",)
    assert report.conflict_records[0].contradict_evidence_ids == ("EV-CON",)


def test_default_statuses_are_placeholders():
    """默认来源状态为 PLACEHOLDER，不得伪装 ACTIVE。"""
    bundle = _conflict_bundle()
    report = run_quality_gate(bundle)
    assert set(report.placeholder_status_ids) >= {"EV-SUP", "EV-CON"}
    assert report.passed is True
