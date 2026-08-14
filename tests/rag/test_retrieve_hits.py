from __future__ import annotations

import inspect

import pytest

from app.contracts.rag import RetrievalHit, ScoreKind, SourceRole, SourceType
from app.rag.retriever import LocalRAGRetriever, RetrievalError
from app.rag.zvec_store import SearchResult


HASH = "a" * 64


def _metadata(**overrides):
    value = {
        "source_id": "SOURCE-1",
        "source_type": "paper",
        "source_role": "external_retrieval",
        "source_name": "paper.pdf",
        "doc_id": "DOC-1",
        "page": 2,
        "chunk_id": "CH-1",
        "content_sha256": HASH,
        "doi": "10.1234/example",
        "url": "https://example.test/paper",
        "loader_version": "2.0",
        "document_identity": "doi:10.1234/example",
        "provenance": {"registry": "production"},
    }
    value.update(overrides)
    return value


class _Embedder:
    def __init__(self):
        self.calls = 0

    def embed_texts(self, texts):
        self.calls += 1
        return [[1.0, 0.0]]


class _Reranker:
    def __init__(self, *, fallback=False, ranking=None):
        self.calls = 0
        self.last_used_fallback = fallback
        self.fallback = fallback
        self.ranking = ranking

    def rerank(self, query, documents, top_k):
        self.calls += 1
        self.last_used_fallback = self.fallback
        ranking = self.ranking or [(i, 0.9 - i * 0.1) for i in range(len(documents))]
        return ranking[:top_k]


class _Store:
    def __init__(self, hits):
        self.hits = hits
        self.filters = None
        self.top_k = None

    def search(self, query_embedding, top_k, filters=None):
        self.filters = filters
        self.top_k = top_k
        return self.hits[:top_k]


def _retriever(*, hits=None, fallback=False, ranking=None, top_k_vector=30, top_k_final=8):
    embedder = _Embedder()
    reranker = _Reranker(fallback=fallback, ranking=ranking)
    store = _Store(hits if hits is not None else [SearchResult("CH-1", 0.7, "Exact quote", _metadata())])
    retriever = LocalRAGRetriever(embedder, reranker, store, top_k_vector, top_k_final)
    return retriever, embedder, reranker, store


def test_retrieve_hits_is_lossless_tuple_and_runs_pipeline_once():
    retriever, embedder, reranker, _ = _retriever()
    hits = retriever.retrieve_hits("  test   query  ")
    assert isinstance(hits, tuple) and isinstance(hits[0], RetrievalHit)
    hit = hits[0]
    assert hit.quoted_text == "Exact quote"
    assert hit.source_locator.document_id == "DOC-1"
    assert hit.source_locator.page == 2
    assert hit.source_locator.chunk_id == "CH-1"
    assert hit.content_hash == HASH
    assert hit.doi == "10.1234/example"
    assert hit.url == "https://example.test/paper"
    assert hit.source_type is SourceType.PAPER
    assert hit.source_role is SourceRole.EXTERNAL_RETRIEVAL
    assert hit.metadata["source_id"] == "SOURCE-1"
    assert hit.metadata["loader_version"] == "2.0"
    assert hit.metadata["document_identity"] == "doi:10.1234/example"
    assert hit.metadata["provenance"] == {"registry": "production"}
    assert embedder.calls == reranker.calls == 1


def test_empty_results_return_empty_tuple_without_rerank():
    retriever, embedder, reranker, _ = _retriever(hits=[])
    assert retriever.retrieve_hits("query") == ()
    assert embedder.calls == 1
    assert reranker.calls == 0


def test_order_top_k_filters_and_scope_match_legacy_path():
    hits = [
        SearchResult("CH-1", 0.7, "one", _metadata(chunk_id="CH-1")),
        SearchResult("CH-2", 0.6, "two", _metadata(chunk_id="CH-2", doc_id="DOC-2")),
        SearchResult("CH-3", 0.5, "three", _metadata(chunk_id="CH-3", doc_id="DOC-3")),
    ]
    retriever, _, _, store = _retriever(hits=hits, ranking=[(1, 0.95), (0, 0.8), (2, 0.7)], top_k_vector=3, top_k_final=2)
    result = retriever.retrieve_hits("query", filters={"domain": "chem"}, source_scope="booklet")
    assert [hit.chunk_id for hit in result] == ["CH-2", "CH-1"]
    assert store.top_k == 3
    assert store.filters == {"domain": "chem", "source_type": "booklet"}


def test_score_kind_uses_rerank_score_without_mixing_vector_score():
    retriever, _, _, _ = _retriever(ranking=[(0, 4.25)])
    hit = retriever.retrieve_hits("query")[0]
    assert hit.retrieval_score == 4.25
    assert hit.score_kind is ScoreKind.RERANK_SCORE


def test_fallback_preserves_vector_score_kind_and_legacy_marker():
    metadata = _metadata(score_kind="vector_distance")
    retriever, _, _, _ = _retriever(hits=[SearchResult("CH-1", 0.23, "Exact quote", metadata)], fallback=True)
    hit = retriever.retrieve_hits("query")[0]
    card = retriever.retrieve("query")[0]
    assert hit.retrieval_score == 0.23
    assert hit.score_kind is ScoreKind.VECTOR_DISTANCE
    assert "rerank_failed_fallback_used" in card.reliability_note


@pytest.mark.parametrize(
    ("text", "chunk_id", "changes"),
    [
        ("", "CH-1", {}),
        ("Exact quote", "CH-1", {"doc_id": "", "page": None}),
        ("Exact quote", "CH-1", {"content_sha256": "abc"}),
        ("Exact quote", "", {}),
        ("Exact quote", "CH-1", {"source_id": ""}),
        ("Exact quote", "CH-1", {"source_type": None}),
        ("Exact quote", "CH-1", {"source_role": None}),
    ],
)
def test_invalid_persisted_provenance_fails_closed(text, chunk_id, changes):
    metadata = _metadata(**changes)
    retriever, _, _, _ = _retriever(hits=[SearchResult(chunk_id, 0.7, text, metadata)])
    with pytest.raises(RetrievalError, match="invalid persisted retrieval provenance"):
        retriever.retrieve_hits("query")


def test_invalid_nested_locator_fails_closed():
    metadata = _metadata(source_locator={"document_id": "DOC-1", "page": 0, "chunk_id": "CH-1"})
    retriever, _, _, _ = _retriever(hits=[SearchResult("CH-1", 0.7, "Exact quote", metadata)])
    with pytest.raises(RetrievalError):
        retriever.retrieve_hits("query")


def test_question_booklet_remains_identifiable_and_is_not_paper():
    metadata = _metadata(source_type="booklet", source_role="question_source", source_name="renamed.pdf")
    retriever, _, _, _ = _retriever(hits=[SearchResult("CH-1", 0.7, "Question wording", metadata)])
    hit = retriever.retrieve_hits("query")[0]
    assert hit.source_type is SourceType.BOOKLET
    assert hit.source_role is SourceRole.QUESTION_SOURCE
    assert hit.source_type is not SourceType.PAPER


def test_legacy_retrieve_signature_return_type_and_errors_are_unchanged():
    signature = inspect.signature(LocalRAGRetriever.retrieve)
    assert list(signature.parameters) == ["self", "query", "filters", "source_scope"]
    retriever, _, _, _ = _retriever()
    cards = retriever.retrieve("query")
    assert isinstance(cards, list)
    assert cards[0].quoted_text == "Exact quote"
    with pytest.raises(ValueError, match="query must not be empty"):
        retriever.retrieve("  ")
    with pytest.raises(ValueError, match="query must not be empty"):
        retriever.retrieve_hits("  ")
