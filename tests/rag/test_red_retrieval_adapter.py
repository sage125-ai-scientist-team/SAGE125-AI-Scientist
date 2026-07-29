"""Red test: current chunk adaptation cannot satisfy RetrievalHit."""

from __future__ import annotations

import pytest

from app.contracts.rag import coerce_retrieval_hit
from app.rag.evidence import chunk_to_evidence_card


@pytest.mark.xfail(
    reason="Retrieval adapter provenance fields waiting for cross-module integration",
    strict=True,
)
def test_chunk_adapter_preserves_structured_locator_and_content_hash():
    """Expected red until an adapter exposes the T04 RetrievalHit contract."""

    chunk_id = "CH-fixture"
    card = chunk_to_evidence_card(
        {
            "chunk_id": chunk_id,
            "text": "Exact offline fixture passage.",
            "metadata": {
                "source_name": "fixture.pdf",
                "source_path": "fixture://paper-01",
                "source_role": "user_literature",
                "doc_id": "DOC-fixture",
                "page": 4,
                "section": "Methods",
                "char_start": 20,
                "char_end": 50,
                "source_hash": "b" * 64,
                "content_sha256": "c" * 64,
                "is_user_upload": True,
            },
        },
        score=0.75,
        source_type="booklet",
    )

    hit = coerce_retrieval_hit(
        {
            "chunk_id": chunk_id,
            "quoted_text": card.quoted_text,
            "retrieval_score": card.relevance_score,
            "score_kind": "vector_similarity",
            "source_type": card.source_type,
            "source_role": "question_source",
            "title": card.title,
            "doi": card.doi,
            "url": card.url,
            "metadata": {},
            # The current adapter must provide these from chunk metadata.
            **{
                key: value
                for key, value in card.model_dump().items()
                if key in {"source_locator", "content_hash"}
            },
        }
    )

    assert hit.source_locator.document_id == "DOC-fixture"
    assert hit.source_locator.page == 4
    assert hit.source_locator.section == "Methods"
    assert hit.source_locator.char_start == 20
    assert hit.source_locator.char_end == 50
    assert hit.content_hash == "c" * 64
