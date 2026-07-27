from typing import Literal, Optional

from pydantic import BaseModel, Field


class EvidenceCardContract(BaseModel):
    """
    Contract layer for traceable scientific evidence.
    
    This model defines evidence requirements.
    It does not replace existing runtime EvidenceCard.
    """

    evidence_id: str

    source_id: str

    source_type: Literal[
        "paper",
        "dataset",
        "experiment",
        "web",
    ]

    title: str

    quoted_text: str

    locator: dict = Field(default_factory=dict)

    authors: list[str] = Field(default_factory=list)

    year: Optional[int] = None

    doi: Optional[str] = None

    url: Optional[str] = None

    content_hash: Optional[str] = None

    verification_status: Literal[
        "verified",
        "pending",
        "rejected",
    ] = "pending"



class ClaimEvidenceLink(BaseModel):
    """
    Contract between factual claims and evidence.
    """

    claim_id: str

    evidence_id: str

    relation: Literal[
        "supports",
        "contradicts",
        "context",
    ]

    confidence: float = 0.0

    validation_status: Literal[
        "valid",
        "invalid",
        "pending",
    ] = "pending"



class EvidenceBundle(BaseModel):
    """
    Controlled evidence package passed to downstream agents.
    """

    bundle_id: str

    evidences: list[EvidenceCardContract]

    links: list[ClaimEvidenceLink]

    token_budget: int = 8000

    truncated: bool = False

    truncation_reason: Optional[str] = None