"""Local RAG in the pipeline must search only the dedicated user library."""

from types import SimpleNamespace


def test_pipeline_local_rag_never_requests_booklet_scope(monkeypatch):
    """The 125-question booklet is a catalogue, not scientific evidence."""
    from app.clients import embedding_client as embedding_module
    from app.clients import rerank_client as rerank_module
    from app.rag import retriever as retriever_module
    from app.rag import zvec_store as store_module
    from app.workflow import pipeline

    requested_scopes: list[str] = []

    class _Retriever:
        def __init__(self, embedding_client, rerank_client, vector_store):
            self.vector_store = vector_store

        def retrieve(self, query, filters=None, source_scope="all"):
            requested_scopes.append(source_scope)
            return []

    monkeypatch.setattr(embedding_module, "EmbeddingClient", lambda settings: object())
    monkeypatch.setattr(rerank_module, "RerankClient", lambda settings: object())
    monkeypatch.setattr(store_module, "get_vector_store", lambda *args, **kwargs: object())
    monkeypatch.setattr(retriever_module, "LocalRAGRetriever", _Retriever)

    state = SimpleNamespace(warnings=[])
    query_plan = {
        "queries": [
            {
                "query": "user supplied evidence",
                "source_preference": "local_rag",
            }
        ]
    }
    execution_plan = {"use_local_rag": True, "use_open_literature": False}

    assert pipeline._gather_real_evidence(state, query_plan, execution_plan, object()) == []
    assert requested_scopes == ["user_upload"]

