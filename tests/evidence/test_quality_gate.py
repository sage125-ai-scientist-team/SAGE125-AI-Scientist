"""
T01 Wave C：冲突/反例证据不被静默覆盖；撤稿占位门禁红灯。
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


def _one_sided_after_overwrite_bundle() -> EvidenceBundle:
    """
    模拟上游静默丢弃 contradicts 侧后的 Bundle（仅剩 supports）。

    返回：
        EvidenceBundle。
    """
    return EvidenceBundle(
        bundle_id="B-OVERWRITE",
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


def test_quality_gate_retracted_fails_under_keep_both_flagged():
    """红灯：KEEP_BOTH_FLAGGED 下撤稿 supports 必须 passed=False。"""
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
    assert report.passed is False


def test_quality_gate_withdrawn_fails_independent_of_disposition():
    """红灯：WITHDRAWN supports 失败不依赖 disposition。"""
    bundle = _conflict_bundle()
    statuses = {
        "EV-SUP": EvidenceSourceStatus(
            evidence_id="EV-SUP",
            lifecycle=SourceLifecycleStatus.WITHDRAWN,
            note="withdrawn",
        ),
        "EV-CON": EvidenceSourceStatus(
            evidence_id="EV-CON",
            lifecycle=SourceLifecycleStatus.ACTIVE,
            note="ok",
        ),
    }
    for disposition in (
        ConflictDisposition.KEEP_BOTH_FLAGGED,
        ConflictDisposition.BLOCK_CLAIM,
    ):
        report = run_quality_gate(
            bundle,
            status_by_id=statuses,
            disposition=disposition,
        )
        assert report.passed is False
        assert "EV-SUP" in report.retracted_blocked_ids


def test_silent_overwrite_detectable_via_prior_links():
    """红灯：prior 双侧齐全、当前丢一侧 → silently_overwritten=True。"""
    prior = _conflict_bundle().links
    current = _one_sided_after_overwrite_bundle()
    records = detect_conflicts_preserving_both_sides(
        current,
        prior_links=prior,
    )
    assert len(records) == 1
    assert records[0].silently_overwritten is True
    assert records[0].support_evidence_ids == ("EV-SUP",)
    assert records[0].contradict_evidence_ids == ()


def test_silent_overwrite_detectable_via_expected_claim_ids():
    """红灯：expected_conflict_claim_ids 在丢一侧时可到达。"""
    current = _one_sided_after_overwrite_bundle()
    records = detect_conflicts_preserving_both_sides(
        current,
        expected_conflict_claim_ids=["C1"],
    )
    assert len(records) == 1
    assert records[0].silently_overwritten is True
    report = run_quality_gate(
        current,
        expected_conflict_claim_ids=["C1"],
    )
    assert report.passed is False


def test_default_statuses_are_placeholders():
    """默认来源状态为 PLACEHOLDER，不得伪装 ACTIVE；无撤稿时可通过。"""
    bundle = _conflict_bundle()
    report = run_quality_gate(bundle)
    assert set(report.placeholder_status_ids) >= {"EV-SUP", "EV-CON"}
    assert report.passed is True
