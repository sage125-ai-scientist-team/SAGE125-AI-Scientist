"""
tests/test_open_literature_retriever.py — 开放文献检索器测试（无网络）。

覆盖：
    - OpenAlex key 为空时跳过、不崩溃；
    - arXiv 限流参数存在；
    - Crossref contact email 为空仍可构造，不崩溃；
    - OpenLiteratureRetriever.search 返回的均为 EvidenceCard。
"""

from __future__ import annotations

from app.clients.literature_clients import ArxivClient, CrossrefClient, OpenAlexClient
from app.core.config import Settings
from app.core.schemas import EvidenceCard
from app.rag.open_literature_retriever import OpenLiteratureRetriever


def test_openalex_skips_without_key():
    """OPENALEX_API_KEY 为空时 search 返回空列表（不联网、不报错）。"""
    settings = Settings(OPENALEX_API_KEY="")
    client = OpenAlexClient(settings)
    assert client.search("gravity") == []


def test_arxiv_rate_limit_param():
    """arXiv 限流参数应存在且为正数。"""
    settings = Settings()
    client = ArxivClient(settings)
    assert client.settings.arxiv_request_interval_seconds >= 1


def test_crossref_no_email_ok():
    """CONTACT_EMAIL 为空时 Crossref 客户端仍可构造。"""
    settings = Settings(CONTACT_EMAIL="")
    client = CrossrefClient(settings)
    assert client is not None


class _FakeArxiv:
    """返回固定 EvidenceCard 的假 arXiv 客户端。"""

    def search(self, query, max_results=5):
        return [
            EvidenceCard(id="a1", source_type="arxiv", title="Gravity paper", quoted_text="abstract",
                         summary="s", relevance_score=0.6, url="https://arxiv.org/abs/x")
        ]


class _EmptyClient:
    """返回空的假客户端（模拟无 Key/无结果）。"""

    def search(self, query, **kwargs):
        return []


class _TrackingClient:
    def __init__(self, source_type: str, cards: list[EvidenceCard]):
        self.source_type = source_type
        self.cards = cards
        self.calls = 0

    def search(self, query, **kwargs):
        self.calls += 1
        return self.cards


def test_open_literature_returns_evidence_cards():
    """聚合检索的返回项应全部为 EvidenceCard。"""
    retriever = OpenLiteratureRetriever(
        settings=Settings(),
        arxiv=_FakeArxiv(),
        openalex=_EmptyClient(),
        crossref=_EmptyClient(),
    )
    cards = retriever.search(["gravity"], max_results_per_query=3)
    assert cards
    assert all(isinstance(c, EvidenceCard) for c in cards)


def test_planner_preference_calls_only_requested_source_and_filters_collision():
    relevant = EvidenceCard(
        id="a-relevant", source_type="arxiv",
        title="Recent xenotransplantation barriers and coagulation",
        quoted_text="xenotransplantation coagulation rejection", summary="abstract",
        relevance_score=0.5, url="https://arxiv.org/abs/2401.00001",
    )
    collision = EvidenceCard(
        id="a-collision", source_type="arxiv",
        title="Donor type semiconductor at low temperature",
        quoted_text="donor impurity atoms and electrons", summary="physics",
        relevance_score=0.5, url="https://arxiv.org/abs/2401.00002",
    )
    arxiv = _TrackingClient("arxiv", [relevant, collision])
    openalex = _TrackingClient("openalex", [])
    crossref = _TrackingClient("crossref", [])
    retriever = OpenLiteratureRetriever(
        settings=Settings(), arxiv=arxiv, openalex=openalex, crossref=crossref
    )

    cards = retriever.search([{
        "query": "xenotransplantation donor organ shortage coagulation barriers",
        "source_preference": "arxiv",
    }])

    assert arxiv.calls == 1
    assert openalex.calls == 0
    assert crossref.calls == 0
    assert [card.id for card in cards] == ["a-relevant"]


def test_ensure_open_literature_queries_fills_missing_arxiv_and_openalex() -> None:
    from app.rag.open_literature_retriever import ensure_open_literature_queries

    filled = ensure_open_literature_queries(
        [{
            "query": "general relativity gravitational waves",
            "source_preference": "crossref",
        }],
        fallback_query="unused",
    )
    prefs = [item["source_preference"] for item in filled]
    assert prefs == ["crossref", "arxiv", "openalex"]
    assert all(item["query"] == "general relativity gravitational waves" for item in filled)
