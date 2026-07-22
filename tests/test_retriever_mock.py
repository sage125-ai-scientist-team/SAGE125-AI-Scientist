"""
tests/test_retriever_mock.py — 本地 RAG 检索器测试（全 mock）。

覆盖：
    - MOCK 环境下 LocalRAGRetriever 返回 EvidenceCards；
    - rerank 失败 fallback 时 reliability_note 含 rerank_failed_fallback_used；
    - 空 query 抛错；embedding 失败抛 RetrievalError。
"""

from __future__ import annotations

import hashlib

import pytest

from app.rag.chunker import Chunk
from app.rag.retriever import LocalRAGRetriever, RetrievalError
from app.rag.zvec_store import MemoryVectorStore


class _FakeEmbedder:
    """确定性假嵌入客户端：由文本 hash 生成固定 8 维向量。"""

    def embed_texts(self, texts):
        """返回与输入等长的确定性向量列表。"""
        vecs = []
        for t in texts:
            digest = hashlib.sha256(t.encode("utf-8")).digest()
            vecs.append([digest[i] / 255.0 for i in range(8)])
        return vecs


class _FailingEmbedder:
    """始终失败的假嵌入客户端，用于验证不伪造 embedding。"""

    def embed_texts(self, texts):
        raise RuntimeError("embedding backend down")


def _build_store(embedder) -> MemoryVectorStore:
    """构造并填充一个内存向量库。"""
    store = MemoryVectorStore()
    chunks = [
        Chunk(chunk_id="c1", text="gravity bends spacetime", metadata={"source_name": "a.pdf", "page": 1}),
        Chunk(chunk_id="c2", text="prime numbers factorization", metadata={"source_name": "a.pdf", "page": 2}),
    ]
    embeddings = embedder.embed_texts([c.text for c in chunks])
    store.add_documents(chunks, embeddings)
    return store


def test_retriever_returns_evidence(monkeypatch):
    """mock rerank 下检索应返回 EvidenceCard 列表。"""
    monkeypatch.setenv("MOCK_RERANK", "true")
    from app.clients.rerank_client import RerankClient

    embedder = _FakeEmbedder()
    store = _build_store(embedder)
    retriever = LocalRAGRetriever(embedder, RerankClient(), store, top_k_vector=10, top_k_final=2)
    cards = retriever.retrieve("what is gravity", source_scope="all")
    assert cards
    # 每张卡具备必要字段。
    for c in cards:
        assert c.quoted_text
        assert c.source_type in ("rag", "user_upload")
        assert 0.0 <= c.relevance_score <= 1.0
        assert c.reliability_note


def test_retriever_rerank_fallback(monkeypatch):
    """rerank 失败时应 fallback 且 reliability_note 含标记。"""
    monkeypatch.delenv("MOCK_RERANK", raising=False)
    from app.clients.rerank_client import RerankClient

    client = RerankClient()

    def _fail(*args, **kwargs):
        raise RuntimeError("rerank down")

    monkeypatch.setattr(client, "_call_bailian_rerank", _fail)
    embedder = _FakeEmbedder()
    store = _build_store(embedder)
    retriever = LocalRAGRetriever(embedder, client, store, top_k_vector=10, top_k_final=2)
    cards = retriever.retrieve("prime numbers", source_scope="all")
    assert cards
    assert all("rerank_failed_fallback_used" in c.reliability_note for c in cards)


def test_retriever_empty_query(monkeypatch):
    """空 query 应抛 ValueError。"""
    monkeypatch.setenv("MOCK_RERANK", "true")
    from app.clients.rerank_client import RerankClient

    retriever = LocalRAGRetriever(_FakeEmbedder(), RerankClient(), MemoryVectorStore())
    with pytest.raises(ValueError):
        retriever.retrieve("   ")


def test_retriever_embedding_failure(monkeypatch):
    """embedding 失败应抛 RetrievalError（不伪造向量）。"""
    monkeypatch.setenv("MOCK_RERANK", "true")
    from app.clients.rerank_client import RerankClient

    store = _build_store(_FakeEmbedder())
    retriever = LocalRAGRetriever(_FailingEmbedder(), RerankClient(), store)
    with pytest.raises(RetrievalError):
        retriever.retrieve("anything")
