import pytest

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)


def test_evidence_card_contains_traceable_fields():

    card = EvidenceCardContract(
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

    card = EvidenceCardContract(
        evidence_id="EV002",
        source_id="paper002",
        source_type="paper",
        title="Paper title only",
        quoted_text="Paper title only",
    )

    assert card.verification_status == "pending"



def test_unknown_evidence_reference_is_invalid():

    link = ClaimEvidenceLink(
        claim_id="CLAIM001",
        evidence_id="UNKNOWN_ID",
        relation="supports",
    )

    assert link.validation_status == "pending"



def test_booklet_excerpt_cannot_be_verified_evidence():

    card = EvidenceCardContract(
        evidence_id="EV_BOOKLET",
        source_id="booklet",
        source_type="web",
        title="Question booklet",
        quoted_text="Question description",
    )

    assert card.verification_status == "pending"



def test_cross_domain_extrapolation_requires_validation():

    link = ClaimEvidenceLink(
        claim_id="CLAIM_DOMAIN",
        evidence_id="EV_DOMAIN",
        relation="context",
    )

    assert link.validation_status == "pending"



def test_evidence_bundle_tracks_token_budget():

    bundle = EvidenceBundle(
        bundle_id="BUNDLE001",
        evidences=[],
        links=[],
        token_budget=8000,
    )

    assert bundle.token_budget == 8000