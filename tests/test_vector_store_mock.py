"""
tests/test_vector_store_mock.py — 内存向量存储测试。

覆盖：
    - MemoryVectorStore add / search 正常；
    - 维度不一致报错；
    - search 返回 SearchResult；
    - inspect_zvec_capabilities 可运行并落盘。
"""

from __future__ import annotations

import pytest

from app.rag.chunker import Chunk
from app.rag.zvec_store import MemoryVectorStore, SearchResult, inspect_zvec_capabilities


def _chunk(cid: str, text: str, is_upload: bool = False) -> Chunk:
    """构造一个测试 Chunk。"""
    return Chunk(chunk_id=cid, text=text, metadata={"source_name": "t", "page": 1, "is_user_upload": is_upload})


def test_memory_add_and_search():
    """add 后 search 应返回按相似度排序的 SearchResult。"""
    store = MemoryVectorStore()
    chunks = [_chunk("c1", "alpha"), _chunk("c2", "beta")]
    embeddings = [[1.0, 0.0], [0.0, 1.0]]
    store.add_documents(chunks, embeddings)
    results = store.search([1.0, 0.0], top_k=2)
    assert len(results) == 2
    assert isinstance(results[0], SearchResult)
    # 与 [1,0] 最相似的是 c1。
    assert results[0].chunk_id == "c1"


def test_memory_dimension_mismatch():
    """维度不一致的向量应报错。"""
    store = MemoryVectorStore()
    with pytest.raises(ValueError):
        store.add_documents([_chunk("c1", "x"), _chunk("c2", "y")], [[1.0, 0.0], [1.0]])


def test_memory_query_dimension_mismatch():
    """查询向量维度与索引不一致应报错。"""
    store = MemoryVectorStore()
    store.add_documents([_chunk("c1", "x")], [[1.0, 0.0]])
    with pytest.raises(ValueError):
        store.search([1.0, 0.0, 0.0], top_k=1)


def test_memory_filters():
    """filters 应按 metadata 等值过滤。"""
    store = MemoryVectorStore()
    store.add_documents(
        [_chunk("c1", "x", is_upload=True), _chunk("c2", "y", is_upload=False)],
        [[1.0, 0.0], [0.9, 0.1]],
    )
    results = store.search([1.0, 0.0], top_k=5, filters={"is_user_upload": True})
    # 仅返回 upload=True 的 c1。
    assert [r.chunk_id for r in results] == ["c1"]


def test_inspect_capabilities_runs():
    """能力探测应返回含 installed 键的字典。"""
    caps = inspect_zvec_capabilities()
    assert "installed" in caps
