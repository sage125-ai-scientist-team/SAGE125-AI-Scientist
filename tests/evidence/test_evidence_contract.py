from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardV2,
)


def test_evidence_card_contains_traceable_fields():
    card = EvidenceCardV2(
        evidence_id="EV001",
        source_id="paper001",
        source_type="paper",
        title="Scientific paper",
        quoted_text="Original evidence text",
        locator={
            "page": 3,
            "section": "Results",
        },
        content_hash="hash001",
    )

    assert card.evidence_id == "EV001"
    assert card.quoted_text == "Original evidence text"
    assert card.locator["page"] == 3


def test_title_only_evidence_remains_pending():
    card = EvidenceCardV2(
        evidence_id="EV002",
        source_id="paper002",
        source_type="paper",
        title="Paper title only",
        quoted_text="Paper title only",
    )

    assert card.verification_status == "pending"


def test_claim_requires_existing_evidence_reference():
    link = ClaimEvidenceLink(
        claim_id="CLAIM001",
        evidence_id="EV001",
        relation="supports",
        confidence=0.8,
    )

    assert link.evidence_id == "EV001"
    assert link.validation_status == "pending"


def test_evidence_bundle_tracks_token_budget():

    bundle = EvidenceBundle(
        bundle_id="BUNDLE001",
        evidences=[],
        links=[],
        token_budget=8000,
    )

    assert bundle.token_budget == 8000
    assert bundle.truncated is False