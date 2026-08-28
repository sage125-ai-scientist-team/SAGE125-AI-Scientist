"""
tests/test_evidence_cards.py — 证据卡片转换测试。

覆盖：
    - chunk_to_evidence_card 不改写 quoted_text；
    - DOI/URL 不存在时不伪造（保持 None）；
    - relevance_score 在 0-1；
    - reliability_note 含 source/page/chunk；
    - deep_research_to_evidence_cards 标记需核验；
    - evidence_deduplicate 去重。
"""

from __future__ import annotations

from app.core.schemas import EvidenceCard
from app.rag.chunker import Chunk
from app.rag.evidence import (
    chunk_to_evidence_card,
    deep_research_to_evidence_cards,
    evidence_deduplicate,
)


def _chunk() -> Chunk:
    """构造带来源 metadata 的 Chunk。"""
    return Chunk(
        chunk_id="CH-abc123",
        text="原始证据文本，不应被改写。",
        metadata={"source_name": "a.pdf", "page": 3, "source_path": "/x/a.pdf", "source_hash": "abc123def456"},
    )


def test_chunk_to_evidence_no_rewrite():
    """quoted_text 必须与 chunk 原文一致（不改写）。"""
    chunk = _chunk()
    card = chunk_to_evidence_card(chunk, score=0.8, query="test query")
    assert card.quoted_text == chunk.text
    # DOI/URL 不伪造。
    assert card.doi is None
    assert card.url is None
    # relevance 在 0-1。
    assert 0.0 <= card.relevance_score <= 1.0
    # reliability_note 含来源信息。
    assert "source_path=" in card.reliability_note
    assert "page=3" in card.reliability_note
    assert "chunk_id=CH-abc123" in card.reliability_note


def test_chunk_to_evidence_rerank_score_used():
    """提供 rerank_score 时应作为相关性。"""
    card = chunk_to_evidence_card(_chunk(), score=0.2, rerank_score=0.95)
    assert abs(card.relevance_score - 0.95) < 1e-6


def test_deep_research_requires_verification():
    """DeepResearch 无引用时应生成 1 张需核验的 summary 卡。"""
    result = {"status": "succeeded", "content": "一些调研结论。", "references": []}
    cards = deep_research_to_evidence_cards(result)
    assert len(cards) == 1
    assert cards[0].source_type == "deep_research"
    assert "verification" in cards[0].reliability_note.lower()


def test_deep_research_failed_no_cards():
    """DeepResearch 失败结果不产出证据。"""
    assert deep_research_to_evidence_cards({"status": "failed", "content": ""}) == []


def test_evidence_deduplicate_by_doi():
    """同一来源的相同 DOI 去重；不同来源即使 DOI 相同也各自保留。"""
    a = EvidenceCard(id="1", source_type="arxiv", title="T", quoted_text="q", summary="s",
                     relevance_score=0.5, doi="10.1000/x")
    b = EvidenceCard(id="2", source_type="crossref", title="T2", quoted_text="q2", summary="s2",
                     relevance_score=0.4, doi="10.1000/x")
    c = EvidenceCard(id="3", source_type="openalex", title="T3", quoted_text="q3", summary="s3",
                     relevance_score=0.3, doi="10.1000/x")
    d = EvidenceCard(id="4", source_type="crossref", title="T4", quoted_text="q4", summary="s4",
                     relevance_score=0.2, doi="10.1000/x")
    deduped = evidence_deduplicate([a, b, c, d])
    sources = {card.source_type for card in deduped}
    assert sources == {"arxiv", "crossref", "openalex"}
    crossref = next(card for card in deduped if card.source_type == "crossref")
    assert crossref.id == "2"
