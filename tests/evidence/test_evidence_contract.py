import pytest

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)

from app.contracts.validators import (
    validate_evidence_card,
    validate_evidence_link,
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
def test_missing_quote_should_fail():

    card = EvidenceCardContract(
        evidence_id="EV_BAD_001",
        source_id="paper001",
        source_type="paper",
        title="Missing quote",
        quoted_text="",
        locator={
            "page": 1
        },
    )

    with pytest.raises(ValueError):
        validate_evidence_card(card)


def test_missing_locator_should_fail():

    card = EvidenceCardContract(
        evidence_id="EV_BAD_002",
        source_id="paper002",
        source_type="paper",
        title="Missing locator",
        quoted_text="Some quote",
        locator={},
    )

    with pytest.raises(ValueError):
        validate_evidence_card(card)


def test_unknown_evidence_id_should_fail():

    link = ClaimEvidenceLink(
        claim_id="CLAIM_BAD",
        evidence_id="UNKNOWN_ID",
        relation="supports",
    )

    with pytest.raises(ValueError):
        validate_evidence_link(
            link,
            [
                "EV001"
            ],
        )