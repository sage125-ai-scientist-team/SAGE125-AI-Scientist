"""Red test: current chunk adaptation cannot satisfy RetrievalHit."""

from __future__ import annotations

from app.contracts.rag import ScoreKind, SourceRole, SourceType
from app.rag.evidence import chunk_to_retrieval_hit


def test_chunk_adapter_preserves_structured_locator_and_content_hash():
    """The T04 adapter preserves provenance without changing EvidenceCard."""

    chunk_id = "CH-fixture"
    hit = chunk_to_retrieval_hit(
        {
            "chunk_id": chunk_id,
            "text": "Exact offline fixture passage.",
            "metadata": {
                "source_name": "fixture.pdf",
                "source_path": "fixture://paper-01",
                "doc_id": "DOC-fixture",
                "page": 4,
                "section": "Methods",
                "char_start": 20,
                "char_end": 50,
                "source_hash": "b" * 64,
                "content_sha256": "c" * 64,
                "source_type": "booklet",
                "source_role": "question_source",
                "score_kind": "vector_similarity",
                "is_user_upload": True,
            },
        },
        score=0.75,
    )

    assert hit.source_type is SourceType.BOOKLET
    assert hit.source_role is SourceRole.QUESTION_SOURCE
    assert hit.score_kind is ScoreKind.VECTOR_SIMILARITY
    assert hit.source_locator.document_id == "DOC-fixture"
    assert hit.source_locator.page == 4
    assert hit.source_locator.section == "Methods"
    assert hit.source_locator.char_start == 20
    assert hit.source_locator.char_end == 50
    assert hit.content_hash == "c" * 64
