from __future__ import annotations

from app.rag.retriever import LocalRAGRetriever
from app.rag.zvec_store import SearchResult


class _Embedder:
    def embed_texts(self, texts):
        return [[1.0, 0.0] for _ in texts]


class _Reranker:
    last_used_fallback = False

    def rerank(self, query, documents, top_k):
        return [(index, 0.9) for index in range(min(top_k, len(documents)))]


class _Store:
    def __init__(self, metadata):
        self.metadata = metadata
        self.filters = None

    def search(self, query_embedding, top_k, filters=None):
        self.filters = filters
        return [
            SearchResult(
                chunk_id="chunk-1",
                score=0.8,
                text="retrieved text",
                metadata=self.metadata,
            )
        ]


def _retrieve(metadata, source_scope="all"):
    store = _Store(metadata)
    retriever = LocalRAGRetriever(
        _Embedder(), _Reranker(), store, top_k_vector=1, top_k_final=1
    )
    return retriever.retrieve("query", source_scope=source_scope)[0], store


def test_filename_does_not_promote_missing_provenance_to_booklet_or_paper():
    card, _ = _retrieve(
        {
            "source_name": "sjtu-booklet.pdf",
            "doc_id": "doc-1",
            "content_sha256": "a" * 64,
        }
    )

    assert card.source_type == "user_upload"
    assert "source_type=unknown" in card.reliability_note
    assert "source_role=user_upload" in card.reliability_note


def test_retriever_consumes_ingestion_provenance_and_locator():
    card, _ = _retrieve(
        {
            "source_name": "renamed-paper.pdf",
            "source_type": "booklet",
            "source_role": "question_source",
            "source_id": "source-1",
            "content_hash": "b" * 64,
            "source_locator": {
                "document_id": "doc-1",
                "page": 7,
                "chunk_id": "chunk-1",
            },
        }
    )

    assert card.source_type == "booklet"
    assert "source_role=question_source" in card.reliability_note
    assert "source_id=source-1" in card.reliability_note
    assert f"content_hash={'b' * 64}" in card.reliability_note
    assert "document_id" in card.reliability_note


def test_invalid_provenance_uses_safe_defaults():
    card, _ = _retrieve(
        {
            "source_type": "paper_by_filename",
            "source_role": "user_literature",
        }
    )

    assert card.source_type == "user_upload"
    assert "source_type=unknown" in card.reliability_note
    assert "source_role=user_upload" in card.reliability_note


def test_source_scope_filters_use_ingestion_provenance():
    _, booklet_store = _retrieve(
        {"source_type": "booklet", "source_role": "question_source"},
        source_scope="booklet",
    )
    _, upload_store = _retrieve(
        {"source_type": "unknown", "source_role": "user_upload"},
        source_scope="user_upload",
    )

    assert booklet_store.filters == {"source_type": "booklet"}
    assert upload_store.filters == {"source_role": "user_upload"}
