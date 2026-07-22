"""
tests/test_chunker.py — 切分器测试。

覆盖：
    - chunk 保留来源 metadata；
    - overlap > 30% 报错；
    - source_hash 稳定；
    - 过短文本处理正确（问题标题短文本保留并标记）。
"""

from __future__ import annotations

import pytest

from app.rag.chunker import Chunk, chunk_documents, compute_source_hash, estimate_length
from app.rag.document_loader import Document


def _doc(text: str) -> Document:
    """构造一个带最小 metadata 的 Document。"""
    return Document(
        text=text,
        metadata={"source_path": "/x/a.txt", "source_name": "a.txt", "file_type": "txt", "page": 1,
                  "doc_id": "d1", "created_at": "t", "is_user_upload": False},
    )


def test_chunk_preserves_metadata():
    """chunk 应继承来源 metadata 并补充位置字段。"""
    long_text = "这是一个段落。" * 200
    chunks = chunk_documents([_doc(long_text)], chunk_size=100, overlap=20)
    assert chunks
    meta = chunks[0].metadata
    for key in ("source_path", "source_name", "page", "chunk_index", "char_start", "char_end", "source_hash"):
        assert key in meta


def test_overlap_too_large_raises():
    """overlap 超过 chunk_size*0.3 应报错。"""
    with pytest.raises(ValueError):
        chunk_documents([_doc("abc")], chunk_size=100, overlap=40)


def test_source_hash_stable():
    """相同输入生成相同 hash。"""
    h1 = compute_source_hash("hello", "/x/a.txt", 1)
    h2 = compute_source_hash("hello", "/x/a.txt", 1)
    assert h1 == h2
    assert compute_source_hash("hello", "/x/a.txt", 2) != h1


def test_estimate_length_mixed():
    """中英文混合长度估计：中文按字，英文按词。"""
    # 3 个中文字 + 2 个英文词。
    assert estimate_length("你好吗 hello world") == 3 + 2


def test_short_question_title_kept():
    """短问题标题应被保留并标记 is_question_title。"""
    chunks = chunk_documents([_doc("What is gravity?")], chunk_size=1000, overlap=100, min_chunk_chars=120)
    # 短标题保留为一个 chunk。
    assert any(c.metadata.get("is_question_title") for c in chunks)
