"""按标题和摘要原文计算开放文献相关性。

分数来自检索词 / 科学问题与真实题录文本的重叠，必要时再用
qwen3-rerank 覆盖。禁止用固定 0.5 充当区分度。
"""

from __future__ import annotations

import os
import re
from typing import Iterable, Optional

from app.core.schemas import EvidenceCard

_LATIN_TOKEN = re.compile(r"[a-z0-9]+")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")

_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "against",
        "associated",
        "current",
        "different",
        "effects",
        "from",
        "human",
        "into",
        "mechanism",
        "mechanisms",
        "molecular",
        "paper",
        "profile",
        "recent",
        "review",
        "solution",
        "study",
        "that",
        "their",
        "this",
        "using",
        "with",
        "without",
        "and",
        "for",
        "the",
        "are",
        "was",
        "were",
    }
)

_LEXICAL_NOTE = "relevance=title_abstract_overlap"
_RERANK_NOTE = "relevance=qwen3-rerank"


def content_tokens(text: str) -> set[str]:
    """从标题/摘要/查询中提取可比较词元（英文词与中文片段）。"""
    tokens: set[str] = set()
    raw = text or ""
    for token in _LATIN_TOKEN.findall(raw.casefold()):
        if len(token) >= 4 and token not in _STOPWORDS:
            tokens.add(token)
    for run in _CJK_RUN.findall(raw):
        if len(run) >= 2:
            tokens.add(run)
            for index in range(len(run) - 1):
                tokens.add(run[index : index + 2])
    return tokens


def lexical_relevance(query: str, title: str, body: str) -> float:
    """用查询词在标题、摘要中的覆盖率给出 0.05–0.99 的可核验分数。"""
    query_tokens = content_tokens(query)
    if not query_tokens:
        return 0.0
    title_tokens = content_tokens(title)
    body_tokens = content_tokens(body)
    document_tokens = title_tokens | body_tokens
    title_coverage = len(query_tokens & title_tokens) / len(query_tokens)
    body_coverage = len(query_tokens & body_tokens) / len(query_tokens)
    union = query_tokens | document_tokens
    jaccard = (len(query_tokens & document_tokens) / len(union)) if union else 0.0
    raw = 0.12 + 0.50 * title_coverage + 0.28 * body_coverage + 0.10 * jaccard
    return round(min(0.99, max(0.05, raw)), 4)


def _append_note(note: str, marker: str) -> str:
    cleaned = (note or "").strip()
    for old in (_LEXICAL_NOTE, _RERANK_NOTE):
        cleaned = cleaned.replace(f"; {old}", "").replace(old, "")
    cleaned = cleaned.strip(" ;")
    return f"{cleaned}; {marker}".strip("; ")


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _try_rerank(
    cards: list[EvidenceCard],
    query: str,
    settings: object | None,
    rerank_client: object | None,
) -> None:
    """在真实百炼可用时用 rerank 覆盖词面分；失败则保留词面分。"""
    if not cards or not query.strip():
        return
    if _env_flag("MOCK_LLM") or _env_flag("MOCK_RERANK"):
        return
    if settings is not None and not bool(getattr(settings, "qwen_configured", False)):
        return
    client = rerank_client
    if client is None:
        if settings is None:
            return
        from app.clients.rerank_client import RerankClient

        client = RerankClient(settings)  # type: ignore[arg-type]
    documents = [
        "\n".join(part for part in (card.title, card.quoted_text or card.summary) if part)
        for card in cards
    ]
    ranked = client.rerank(query, documents, top_k=len(documents))
    if getattr(client, "last_used_fallback", False):
        return
    for index, score in ranked:
        if not (0 <= int(index) < len(cards)):
            continue
        cards[int(index)].relevance_score = round(min(0.99, max(0.05, float(score))), 4)
        cards[int(index)].reliability_note = _append_note(
            cards[int(index)].reliability_note, _RERANK_NOTE
        )


def apply_content_relevance(
    cards: Iterable[EvidenceCard],
    query: str,
    *,
    topic_text: str = "",
    settings: object | None = None,
    rerank_client: Optional[object] = None,
) -> list[EvidenceCard]:
    """就地写入基于原文的相关性，并返回同一列表。"""
    scored = list(cards)
    score_query = " ".join(part for part in (topic_text, query) if str(part).strip())
    for card in scored:
        body = " ".join(part for part in (card.summary, card.quoted_text) if part)
        card.relevance_score = lexical_relevance(score_query, card.title, body)
        card.reliability_note = _append_note(card.reliability_note, _LEXICAL_NOTE)
    _try_rerank(scored, score_query, settings, rerank_client)
    return scored
