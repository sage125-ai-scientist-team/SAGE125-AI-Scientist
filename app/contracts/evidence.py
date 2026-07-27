from typing import Literal, Optional

from pydantic import BaseModel, Field


class EvidenceCardV2(BaseModel):
    """
    Traceable scientific evidence object.
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
    Relation between factual claim and evidence.
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
    Controlled evidence context passed to agents.
    """

    bundle_id: str

    evidences: list[EvidenceCardV2]

    links: list[ClaimEvidenceLink]

    token_budget: int = 8000

    truncated: bool = False

    truncation_reason: Optional[str] = None