"""
T01 Wave B（08/03）：与 T02/T03 契约联调 E2E。

覆盖：V1/V2 版本记录、缺证据、冲突证据、字段不丢失。
不修改 pipeline.py。
"""

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.contracts.revision import PlanVersion
from app.evidence.integration_bridge import (
    BUNDLE_FINGERPRINT_KEY,
    attach_bundle_to_plan_version,
    build_v1_v2_revision_with_bundle,
    build_validation_context_from_bundle,
    find_conflict_claim_ids,
    precheck_bundle_for_validation,
    round_trip_revision_state,
)
from app.evidence.support_checker import ClaimText


def _card(evidence_id: str, quote: str, domain: str = "medicine") -> EvidenceCardContract:
    """构造联调用契约卡。"""
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
        content_hash=f"sha256:{evidence_id}",
        domain=domain,
        verification_status="pending",
    )


def _bundle(
    bundle_id: str,
    cards: list[EvidenceCardContract],
    links: list[ClaimEvidenceLink],
) -> EvidenceBundle:
    """构造 Bundle。"""
    return EvidenceBundle(
        bundle_id=bundle_id,
        evidences=cards,
        links=links,
        token_budget=8000,
    )


def test_v1_v2_revision_keeps_bundle_fingerprint_round_trip():
    """V1/V2 版本记录携带 Bundle 指纹，序列化往返不丢。"""
    card = _card("EV-OK", "EGFR inhibition improves response in lung adenocarcinoma.")
    link = ClaimEvidenceLink(
        claim_id="C-OK",
        evidence_id="EV-OK",
        relation="supports",
        claim_domain="medicine",
    )
    b1 = _bundle("B-V1", [card], [link])
    b2 = _bundle(
        "B-V2",
        [card, _card("EV-OK-2", "Additional cohort confirms EGFR response.")],
        [
            link,
            ClaimEvidenceLink(
                claim_id="C-OK",
                evidence_id="EV-OK-2",
                relation="supports",
                claim_domain="medicine",
            ),
        ],
    )
    state = build_v1_v2_revision_with_bundle(
        run_id="run-t01-e2e",
        bundle_v1=b1,
        bundle_v2=b2,
    )
    assert state.versions[0].version_id == "run-t01-e2e:v1"
    assert state.versions[1].parent_version_id == "run-t01-e2e:v1"
    assert BUNDLE_FINGERPRINT_KEY in state.versions[0].prompt_fingerprints
    assert BUNDLE_FINGERPRINT_KEY in state.versions[1].prompt_fingerprints
    assert (
        state.versions[0].prompt_fingerprints[BUNDLE_FINGERPRINT_KEY]
        != state.versions[1].prompt_fingerprints[BUNDLE_FINGERPRINT_KEY]
    )

    restored = round_trip_revision_state(state)
    assert (
        restored.versions[0].prompt_fingerprints[BUNDLE_FINGERPRINT_KEY]
        == state.versions[0].prompt_fingerprints[BUNDLE_FINGERPRINT_KEY]
    )
    assert restored.versions[1].hypothesis_generation["evidence_bundle"]["bundle_id"] == "B-V2"


def test_validation_context_preserves_quoted_text_and_locator():
    """投影到 T03 ValidationContext 不丢失 quote/locator/hash。"""
    card = _card("EV-KEEP", "Original quoted evidence must survive projection.")
    bundle = _bundle(
        "B-KEEP",
        [card],
        [
            ClaimEvidenceLink(
                claim_id="C1",
                evidence_id="EV-KEEP",
                relation="context",
            )
        ],
    )
    plan = attach_bundle_to_plan_version(
        PlanVersion.create(run_id="run-keep", version_number=1, revision_iteration=1),
        bundle,
    )
    ctx = build_validation_context_from_bundle(
        bundle=bundle,
        plan=plan,
        question_id="Q028",
        question_text="How should cancer evidence be scoped?",
        validation_id="validation-keep",
        domain="medicine",
    )
    wire = dict(ctx.evidence_cards[0])
    assert wire["id"] == "EV-KEEP"
    assert wire["quoted_text"] == card.quoted_text
    assert wire["locator"]["page"] == 1
    assert wire["content_hash"] == card.content_hash

    pre = precheck_bundle_for_validation(
        bundle=bundle,
        claims=[
            ClaimText(
                claim_id="C1",
                text="Original quoted evidence must survive projection.",
                evidence_ids=["EV-KEEP"],
                domain="medicine",
                relation="context",
            )
        ],
        context=ctx,
    )
    assert pre.field_loss == []
    assert pre.gate.passed is True


def test_missing_evidence_e2e_fails_precheck_gate():
    """缺证据：未知 evidence_id → T01_MISSING_EVIDENCE P1，gate 失败。"""
    card = _card("EV-ONLY", "Present evidence body text for pool.")
    bundle = _bundle(
        "B-MISS",
        [card],
        [
            ClaimEvidenceLink(
                claim_id="C-MISS",
                evidence_id="EV-ONLY",
                relation="context",
            )
        ],
    )
    plan = attach_bundle_to_plan_version(
        PlanVersion.create(run_id="run-miss", version_number=1, revision_iteration=1),
        bundle,
    )
    ctx = build_validation_context_from_bundle(
        bundle=bundle,
        plan=plan,
        question_id="Q001",
        question_text="How can this mechanism be tested?",
        validation_id="validation-miss",
    )
    pre = precheck_bundle_for_validation(
        bundle=bundle,
        claims=[
            ClaimText(
                claim_id="C-MISS",
                text="Present evidence body text for pool.",
                evidence_ids=["EV-MISSING"],
                domain="medicine",
            )
        ],
        context=ctx,
    )
    assert pre.missing_blocked is True
    assert pre.gate.passed is False
    assert "T01_MISSING_EVIDENCE" in pre.gate.errors


def test_conflict_evidence_e2e_emits_gate_finding():
    """冲突证据：同一 claim 同时 supports+contradicts → P1 finding。"""
    support = _card("EV-SUP", "Drug A improves survival in the reported cohort.")
    contra = _card("EV-CON", "Drug A fails to improve survival in replication.")
    links = [
        ClaimEvidenceLink(
            claim_id="C-CONFLICT",
            evidence_id="EV-SUP",
            relation="supports",
            claim_domain="medicine",
        ),
        ClaimEvidenceLink(
            claim_id="C-CONFLICT",
            evidence_id="EV-CON",
            relation="contradicts",
            claim_domain="medicine",
        ),
    ]
    assert find_conflict_claim_ids(links) == ["C-CONFLICT"]
    bundle = _bundle("B-CONFLICT", [support, contra], links)
    plan = attach_bundle_to_plan_version(
        PlanVersion.create(run_id="run-conflict", version_number=1, revision_iteration=1),
        bundle,
    )
    ctx = build_validation_context_from_bundle(
        bundle=bundle,
        plan=plan,
        question_id="Q024",
        question_text="Does drug A improve survival?",
        validation_id="validation-conflict",
        domain="medicine",
    )
    pre = precheck_bundle_for_validation(
        bundle=bundle,
        claims=[
            ClaimText(
                claim_id="C-CONFLICT",
                text="Drug A improves survival in the reported cohort.",
                evidence_ids=["EV-SUP", "EV-CON"],
                domain="medicine",
            )
        ],
        context=ctx,
    )
    assert "C-CONFLICT" in pre.conflict_claim_ids
    assert pre.gate.passed is False
    assert any(f.code == "T01_CONFLICT_EVIDENCE" for f in pre.gate.findings)
