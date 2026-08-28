"""
app.rag.open_literature_retriever —— 开放文献统一检索入口。

聚合 ArxivClient / OpenAlexClient / CrossrefClient 的检索结果，
统一转换为 EvidenceCard 并去重。用于为假设/研究计划补充外部可溯源证据。

约束：
    - 不下载论文 PDF 全文；
    - 遵守 arXiv 请求间隔（由 ArxivClient 内部限流）；
    - OpenAlex 缺 Key 时跳过，不导致失败；
    - Crossref 仅用于元数据 / DOI 核验；
    - 绝不伪造 DOI / URL / 作者；
    - 每条 EvidenceCard 的 reliability_note 标明来源。
"""

from __future__ import annotations

import re
from typing import Optional

from app.clients.literature_clients import ArxivClient, CrossrefClient, OpenAlexClient
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.schemas import EvidenceCard
from app.rag.evidence import evidence_deduplicate, literature_to_evidence_card

# 模块级日志器。
logger = get_logger("rag.open_literature")

OPEN_LITERATURE_SOURCES = ("arxiv", "openalex", "crossref")

_GENERIC_QUERY_WORDS = {
    "about", "after", "against", "associated", "current", "different",
    "donor", "effects", "human", "mechanism", "mechanisms", "molecular",
    "organ", "paper", "profile", "recent", "review", "solution", "study",
    "using", "with", "without",
}


def _topic_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").casefold())
        if len(token) >= 5 and token not in _GENERIC_QUERY_WORDS
    }


def _has_topic_match(query: str, card: EvidenceCard) -> bool:
    """Reject obvious keyword collisions such as donor semiconductors.

    One distinctive long term (for example ``xenotransplantation`` or
    ``thrombomodulin``) is sufficient; otherwise at least two meaningful query
    terms must occur in the title/abstract metadata.
    """

    query_tokens = _topic_tokens(query)
    if not query_tokens:
        return True
    document = " ".join((card.title, card.summary, card.quoted_text))
    overlap = query_tokens & _topic_tokens(document)
    return any(len(token) >= 10 for token in overlap) or len(overlap) >= 2


def ensure_open_literature_queries(
    queries: list[dict],
    *,
    fallback_query: str = "",
) -> list[dict]:
    """Planner 若只给出 Crossref 查询，补齐 arXiv / OpenAlex 同主题检索。"""
    lit = [
        query
        for query in queries
        if isinstance(query, dict)
        and str(query.get("source_preference") or "") in OPEN_LITERATURE_SOURCES
        and str(query.get("query") or "").strip()
    ]
    seed = next((str(item.get("query") or "").strip() for item in lit), "")
    seed = seed or " ".join((fallback_query or "").split())
    present = {str(item.get("source_preference")) for item in lit}
    extras: list[dict] = []
    for source in OPEN_LITERATURE_SOURCES:
        if source in present or not seed:
            continue
        extras.append(
            {
                "query": seed,
                "source_preference": source,
                "purpose": f"cover_{source}",
                "expected_evidence": "open literature metadata",
                "priority": "medium",
            }
        )
    return lit + extras


class OpenLiteratureRetriever:
    """开放文献统一检索器：聚合 arXiv / OpenAlex / Crossref 并去重。"""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        arxiv: Optional[ArxivClient] = None,
        openalex: Optional[OpenAlexClient] = None,
        crossref: Optional[CrossrefClient] = None,
    ) -> None:
        """
        初始化统一检索器，允许注入各客户端以便测试。

        参数：
            settings: 可选配置；缺省使用全局单例。
            arxiv/openalex/crossref: 可选注入的文献客户端。
        """
        # 保存配置与客户端（缺省新建）。
        self.settings = settings or get_settings()
        self.arxiv = arxiv or ArxivClient(self.settings)
        self.openalex = openalex or OpenAlexClient(self.settings)
        self.crossref = crossref or CrossrefClient(self.settings)

    def search(
        self, queries: list[str | dict], max_results_per_query: int = 5
    ) -> list[EvidenceCard]:
        """
        对多个查询聚合检索 arXiv / OpenAlex / Crossref，返回去重后的证据。

        参数：
            queries:               查询列表。
            max_results_per_query: 每个查询每个来源的最大条数。

        返回：
            去重后的 EvidenceCard 列表。
        """
        collected: list[EvidenceCard] = []
        for query_spec in queries:
            strict_preference = isinstance(query_spec, dict)
            query = query_spec.get("query", "") if strict_preference else str(query_spec)
            preferred = str(query_spec.get("source_preference", "")) if strict_preference else ""
            # 跳过空查询。
            q = " ".join((query or "").split())
            if not q:
                continue

            query_cards: list[EvidenceCard] = []

            # 1) arXiv（内部已限流；不下载全文）。
            if preferred in ("", "arxiv"):
                try:
                    for card in self.arxiv.search(q, max_results=max_results_per_query):
                        ev = literature_to_evidence_card(card, "arxiv")
                        if ev:
                            query_cards.append(ev)
                except Exception as exc:  # 单来源失败不影响其它来源
                    logger.warning("arXiv 检索异常（忽略该来源）：%s", exc)

            # 2) OpenAlex（缺 Key 自动跳过，不报错）。
            if preferred in ("", "openalex"):
                try:
                    for card in self.openalex.search(q, per_page=max_results_per_query):
                        ev = literature_to_evidence_card(card, "openalex")
                        if ev:
                            query_cards.append(ev)
                except Exception as exc:
                    logger.warning("OpenAlex 检索异常（忽略该来源）：%s", exc)

            # 3) Crossref（带 mailto；用于元数据/DOI 核验）。
            if preferred in ("", "crossref"):
                try:
                    for card in self.crossref.search(q, rows=max_results_per_query):
                        ev = literature_to_evidence_card(card, "crossref")
                        if ev:
                            query_cards.append(ev)
                except Exception as exc:
                    logger.warning("Crossref 检索异常（忽略该来源）：%s", exc)

            # Planner-provided source preferences are production queries. Apply
            # a conservative lexical guard before candidates enter the evidence
            # pool; legacy plain-string callers retain aggregate behavior.
            if strict_preference:
                matched = [card for card in query_cards if _has_topic_match(q, card)]
                dropped = len(query_cards) - len(matched)
                if dropped:
                    logger.info(
                        "open_literature 过滤主题不匹配候选：source=%s, dropped=%d",
                        preferred,
                        dropped,
                    )
                query_cards = matched
            collected.extend(query_cards)

        # 统一去重后返回。
        deduped = evidence_deduplicate(collected)
        logger.info(
            "open_literature 检索完成：queries=%d，raw=%d，deduped=%d",
            len(queries),
            len(collected),
            len(deduped),
        )
        return deduped
