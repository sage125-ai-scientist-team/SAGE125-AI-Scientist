"""
T04 VectorStore live index/retrieve for multimodal EvidenceCards.

Uses existing app.rag MemoryVectorStore + chunk_to_retrieval_hit.
Does NOT invent a T06-only memory Evidence index as a substitute.
"""

from __future__ import annotations

import os
from typing import Any

from app.contracts.multimodal import MultimodalArtifact
from app.multimodal.evidence_bridge import (
    artifact_to_evidence_card,
    low_confidence_blocks_fact,
)
from app.multimodal.workflow_hook import build_revision_hook_payload
from app.rag.chunker import Chunk
from app.rag.evidence import chunk_to_retrieval_hit
from app.rag.indexing_service import mock_embed
from app.rag.zvec_store import MemoryVectorStore, SearchResult


def index_and_retrieve_via_t04_store(
    artifacts: list[MultimodalArtifact],
    *,
    claim_id: str = "claim-t06-demo",
) -> dict[str, Any]:
    """
    Write MultimodalArtifact-derived cards into T04 MemoryVectorStore and read back.
    """
    os.environ.setdefault("MOCK_EMBEDDING", "true")
    store = MemoryVectorStore()
    chunks: list[Chunk] = []
    for art in artifacts:
        card = artifact_to_evidence_card(art)
        meta = {
            "doc_id": card.source_id[:200] or art.artifact_id,
            "document_id": card.source_id[:200] or art.artifact_id,
            "source_name": f"t06-{art.modality}-{art.artifact_id}",
            "page": card.locator.get("page"),
            "content_sha256": card.content_hash,
            "source_type": "dataset",
            "source_role": "user_upload",
            "score_kind": "vector_similarity",
            "t06_locator": card.locator,
            "t06_evidence_id": card.evidence_id,
            "supports_fact": not low_confidence_blocks_fact(art),
            "is_user_upload": True,
        }
        chunks.append(
            Chunk(
                chunk_id=f"CH-{card.evidence_id}",
                text=card.quoted_text,
                metadata=meta,
            )
        )
    embeddings = mock_embed([c.text for c in chunks])
    store.add_documents(chunks, embeddings)

    retrieved: list[dict[str, Any]] = []
    for chunk, emb in zip(chunks, embeddings, strict=True):
        hits: list[SearchResult] = store.search(emb, top_k=1)
        if not hits:
            raise AssertionError(f"T04 store returned no hit for {chunk.chunk_id}")
        hit = hits[0]
        # Lossless T04 contract adaptation
        retrieval_hit = chunk_to_retrieval_hit(
            {
                "text": hit.text,
                "metadata": hit.metadata,
                "chunk_id": hit.chunk_id,
            },
            score=hit.score,
        )
        locator = hit.metadata.get("t06_locator") or {}
        for key in (
            "source_path",
            "page",
            "modality",
            "confidence",
            "validation_status",
            "file_sha256",
        ):
            if key not in locator and key != "file_sha256":
                raise AssertionError(f"locator missing {key} after T04 retrieve")
        # file_sha256 may live inside source_path suffix or locator
        if "file_sha256" not in locator and "sha256=" not in str(locator.get("source_path", "")):
            raise AssertionError("file sha256 not preserved in retrieved locator/path")
        retrieved.append(
            {
                "chunk_id": hit.chunk_id,
                "evidence_id": hit.metadata.get("t06_evidence_id"),
                "locator": locator,
                "supports_fact": hit.metadata.get("supports_fact"),
                "retrieval_hit_page": retrieval_hit.source_locator.page,
                "metadata_keys": sorted(retrieval_hit.metadata.keys()),
            }
        )

    supports = [
        r["evidence_id"]
        for r in retrieved
        if r.get("supports_fact") is True
    ]
    # Policy: low confidence must not support facts — already encoded in metadata
    low_support_violations = [
        r
        for r in retrieved
        if r.get("supports_fact") is True
        and float((r.get("locator") or {}).get("confidence") or 0) < 0.8
    ]
    if low_support_violations:
        raise AssertionError("low confidence evidence incorrectly marked supports_fact")

    hook = build_revision_hook_payload(artifacts)
    return {
        "store": "app.rag.zvec_store.MemoryVectorStore",
        "adapter": "app.rag.evidence.chunk_to_retrieval_hit",
        "n_indexed": len(chunks),
        "retrieved": retrieved,
        "supports_ids": supports,
        "claim_id": claim_id,
        "hook": hook,
        "binary_in_prompt": hook.get("binary_in_prompt"),
    }
