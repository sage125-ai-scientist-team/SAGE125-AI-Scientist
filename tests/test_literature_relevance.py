"""开放文献原文相关性与 OpenAlex 摘要还原测试（无网络）。"""

from __future__ import annotations

from app.clients.literature_clients import reconstruct_openalex_abstract
from app.core.config import Settings
from app.core.schemas import EvidenceCard
from app.rag.literature_relevance import apply_content_relevance, lexical_relevance
from app.rag.open_literature_retriever import OpenLiteratureRetriever


def test_reconstruct_openalex_abstract_restores_word_order() -> None:
    inverted = {
        "Xenotransplantation": [0],
        "requires": [1],
        "thrombomodulin": [2],
        "expression": [3],
    }
    assert (
        reconstruct_openalex_abstract(inverted)
        == "Xenotransplantation requires thrombomodulin expression"
    )


def test_reconstruct_openalex_abstract_empty_or_invalid() -> None:
    assert reconstruct_openalex_abstract(None) == ""
    assert reconstruct_openalex_abstract({}) == ""
    assert reconstruct_openalex_abstract({"x": "bad"}) == ""


def test_lexical_relevance_separates_on_topic_from_collision() -> None:
    query = "xenotransplantation coagulation thrombomodulin endothelial"
    on_topic = lexical_relevance(
        query,
        "Thrombomodulin expression in xenotransplantation",
        "Coagulation control on porcine endothelial cells after xenotransplantation.",
    )
    collision = lexical_relevance(
        query,
        "Donor type semiconductor at low temperature",
        "Impurity atoms and electrons in silicon wafers.",
    )
    assert on_topic > 0.55
    assert collision < 0.25
    assert on_topic != 0.5
    assert collision != 0.5


def test_apply_content_relevance_overwrites_placeholder_half() -> None:
    cards = [
        EvidenceCard(
            id="hi",
            source_type="openalex",
            title="Night-sky brightness monitoring and light pollution assessment",
            quoted_text="Urban light pollution measured by night-sky brightness networks.",
            summary="light pollution night-sky brightness",
            relevance_score=0.5,
        ),
        EvidenceCard(
            id="lo",
            source_type="crossref",
            title="Unrelated semiconductor donor impurities",
            quoted_text="Silicon wafer doping at cryogenic temperature.",
            summary="semiconductor",
            relevance_score=0.5,
        ),
    ]
    apply_content_relevance(
        cards,
        "light pollution night-sky brightness monitoring",
        settings=Settings(DASHSCOPE_API_KEY="", WORKSPACE_ID=""),
    )
    assert cards[0].relevance_score != cards[1].relevance_score
    assert cards[0].relevance_score > cards[1].relevance_score
    assert 0.5 not in {cards[0].relevance_score, cards[1].relevance_score}
    assert "relevance=title_abstract_overlap" in cards[0].reliability_note


class _FixedClient:
    def __init__(self, cards: list[EvidenceCard]) -> None:
        self.cards = cards

    def search(self, query, **kwargs):
        return list(self.cards)


def test_open_literature_keeps_openalex_when_doi_matches_crossref() -> None:
    shared_doi = "10.1000/example.doi"
    openalex = EvidenceCard(
        id="oa-1",
        source_type="openalex",
        title="Light pollution and night-sky brightness monitoring",
        quoted_text="Night-sky brightness networks quantify urban light pollution.",
        summary="light pollution night-sky",
        relevance_score=0.5,
        doi=shared_doi,
        url="https://openalex.org/W1",
    )
    crossref = EvidenceCard(
        id="cr-1",
        source_type="crossref",
        title="Light pollution and night-sky brightness monitoring",
        quoted_text="Light pollution and night-sky brightness monitoring",
        summary="Light pollution and night-sky brightness monitoring",
        relevance_score=0.5,
        doi=shared_doi,
        url="https://doi.org/10.1000/example.doi",
    )
    retriever = OpenLiteratureRetriever(
        settings=Settings(DASHSCOPE_API_KEY="", WORKSPACE_ID=""),
        arxiv=_FixedClient([]),
        openalex=_FixedClient([openalex]),
        crossref=_FixedClient([crossref]),
    )
    cards = retriever.search(
        [
            {
                "query": "light pollution night-sky brightness monitoring",
                "source_preference": "openalex",
            },
            {
                "query": "light pollution night-sky brightness monitoring",
                "source_preference": "crossref",
            },
        ]
    )
    sources = {card.source_type for card in cards}
    assert "openalex" in sources
    assert "crossref" in sources
    scores = {card.relevance_score for card in cards}
    assert 0.5 not in scores
