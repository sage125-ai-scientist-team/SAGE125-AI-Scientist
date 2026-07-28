from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceCardContract,
)


def validate_evidence_card(card: EvidenceCardContract) -> bool:
    """
    Validate minimum evidence provenance requirements.
    """

    if not card.quoted_text:
        raise ValueError("Evidence quote is missing")

    if not card.locator:
        raise ValueError("Evidence locator is missing")

    return True



def validate_evidence_link(
    link: ClaimEvidenceLink,
    existing_evidence_ids: list[str],
) -> bool:
    """
    Validate evidence reference integrity.
    """

    if link.evidence_id not in existing_evidence_ids:
        raise ValueError(
            f"Unknown evidence_id: {link.evidence_id}"
        )

    return True