"""
T06 侧 EvidenceBundle 辅助索引（契约完整性校验）。

注意：这不是 T01/T04 生产 live index。跨模块 E2E 请用
`evidence_rag.index_and_retrieve_via_t04_store`（MemoryVectorStore + chunk_to_retrieval_hit）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
    validate_evidence_card,
    validate_evidence_link,
)
from app.contracts.multimodal import MultimodalArtifact
from app.multimodal.evidence_bridge import (
    artifact_to_evidence_card,
    low_confidence_blocks_fact,
)
from app.multimodal.workflow_hook import build_revision_hook_payload


@dataclass
class EvidenceBundleIndex:
    """In-memory EvidenceBundle helper (NOT a T04 VectorStore substitute)."""

    _cards: dict[str, EvidenceCardContract] = field(default_factory=dict)
    _links: list[ClaimEvidenceLink] = field(default_factory=list)

    def upsert_card(self, card: EvidenceCardContract) -> None:
        validate_evidence_card(card)
        self._cards[card.evidence_id] = card

    def add_link(self, link: ClaimEvidenceLink) -> None:
        validate_evidence_link(link, list(self._cards.keys()))
        self._links.append(link)

    def build_bundle(self, bundle_id: str) -> EvidenceBundle:
        return EvidenceBundle(
            bundle_id=bundle_id,
            evidences=list(self._cards.values()),
            links=list(self._links),
        )

    def get(self, evidence_id: str) -> EvidenceCardContract | None:
        return self._cards.get(evidence_id)

    def consume_supporting_ids(self, claim_id: str) -> list[str]:
        return [
            link.evidence_id
            for link in self._links
            if link.claim_id == claim_id and link.relation == "supports"
        ]


# Backward-compatible alias — do not document as live T01/T04 index.
LiveEvidenceIndex = EvidenceBundleIndex


def index_multimodal_artifacts(
    artifacts: list[MultimodalArtifact],
    *,
    claim_id: str = "claim-t06-demo",
) -> tuple[EvidenceBundleIndex, EvidenceBundle, dict[str, Any]]:
    """Bundle-only helper. Prefer evidence_rag for T04 store E2E."""
    index = EvidenceBundleIndex()
    for art in artifacts:
        card = artifact_to_evidence_card(art)
        index.upsert_card(card)
        # Low confidence must not create supports links — always context.
        index.add_link(
            ClaimEvidenceLink(
                claim_id=claim_id,
                evidence_id=card.evidence_id,
                relation="context",
                confidence=art.confidence,
                claim_domain="multimodal",
            )
        )
        if not low_confidence_blocks_fact(art):
            # Still never fabricate supports from T06 alone.
            pass
    bundle = index.build_bundle(bundle_id=f"bundle-{claim_id}")
    consumed = []
    for art in artifacts:
        eid = f"t06-{art.artifact_id}"
        got = index.get(eid)
        assert got is not None
        for key in ("source_path", "page", "modality", "confidence", "validation_status"):
            if key not in got.locator:
                raise AssertionError(f"locator missing {key} after consume")
        consumed.append(got.evidence_id)
    hook = build_revision_hook_payload(artifacts)
    return index, bundle, {
        "consumed_evidence_ids": consumed,
        "supports_ids": index.consume_supporting_ids(claim_id),
        "hook": hook,
        "bundle_id": bundle.bundle_id,
        "n_evidences": len(bundle.evidences),
        "index_kind": "t06_evidence_bundle_helper_not_t04_vector_store",
    }
