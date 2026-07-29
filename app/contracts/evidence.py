from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class EvidenceCardContract(BaseModel):
    """
    Contract layer for traceable scientific evidence.
    """

    evidence_id: str = Field(min_length=1)

    source_id: str = Field(min_length=1)

    source_type: Literal[
        "paper",
        "dataset",
        "experiment",
        "web",
        "contract",
        "specification",
        "test_fixture",
    ]

    title: str = Field(min_length=1)

    quoted_text: str = Field(min_length=1)

    locator: dict

    authors: list[str] = Field(default_factory=list)

    year: Optional[int] = None

    doi: Optional[str] = None

    url: Optional[str] = None

    content_hash: Optional[str] = None

    verification_status: Literal[
        "valid",
        "invalid",
        "pending",
        "rejected",
    ] = "pending"


    @field_validator("quoted_text")
    @classmethod
    def validate_quote(cls, value: str):
        if not value.strip():
            raise ValueError(
                "quoted_text cannot be empty"
            )
        return value


    @field_validator("locator")
    @classmethod
    def validate_locator(cls, value: dict):
        if not value:
            raise ValueError(
                "locator cannot be empty"
            )
        return value



class ClaimEvidenceLink(BaseModel):
    """
    Contract between factual claims and evidence.
    """

    claim_id: str = Field(min_length=1)

    evidence_id: str = Field(min_length=1)

    relation: Literal[
        "supports",
        "contradicts",
        "context",
    ]

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    validation_status: Literal[
        "valid",
        "invalid",
        "pending",
    ] = "pending"


    @field_validator("evidence_id")
    @classmethod
    def validate_link_evidence_id(cls, value: str):
        if not value.strip():
            raise ValueError(
                "evidence_id cannot be empty"
            )
        return value



class EvidenceBundle(BaseModel):
    """
    Controlled evidence package passed to downstream agents.
    """

    bundle_id: str = Field(min_length=1)

    evidences: list[EvidenceCardContract]

    links: list[ClaimEvidenceLink]

    token_budget: int = 8000

    truncated: bool = False

    truncation_reason: Optional[str] = None


    @field_validator("evidences")
    @classmethod
    def validate_evidences(
        cls,
        value: list[EvidenceCardContract],
    ):
        if not value:
            raise ValueError(
                "EvidenceBundle requires evidences"
            )
        return value


    @field_validator("links")
    @classmethod
    def validate_links(
        cls,
        value: list[ClaimEvidenceLink],
    ):
        if not value:
            raise ValueError(
                "EvidenceBundle requires links"
            )
        return value



def validate_evidence_card(
    card: EvidenceCardContract,
) -> bool:
    """
    Validate minimum evidence provenance requirements.
    """

    if not card.quoted_text:
        raise ValueError(
            "Evidence quote is missing"
        )

    if not card.locator:
        raise ValueError(
            "Evidence locator is missing"
        )

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