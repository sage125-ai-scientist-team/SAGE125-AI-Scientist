"""Official-catalog search, filters, and verified quick-example resolution.

All picker surfaces must use this module against ``OfficialQuestionCatalog``.
No filesystem walk, no per-question result IO, and no model calls.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.catalog.official import (
    EXPECTED_IDS,
    OfficialQuestion,
    OfficialQuestionCatalog,
    load_official_catalog,
)

QUICK_EXAMPLE_TITLE_EN: dict[str, str] = {
    "prime": "What makes prime numbers so special?",
    "pandemic": "Can we predict the next pandemic?",
    "climate": "Can we stop global climate change?",
    "creativity": "Can robots or AIs have human creativity?",
    "quantum": "What is the optimum hardware for quantum computers?",
}

STATUS_FILTER_ALL = "全部"
STATUS_FILTER_OPTIONS: tuple[str, ...] = (
    STATUS_FILTER_ALL,
    "尚未开始",
    "运行中",
    "已完成",
    "部分完成",
    "失败",
    "阻断",
)

_STATUS_TO_FILTER: dict[str, str] = {
    "not_started": "尚未开始",
    "draft": "尚未开始",
    "idle": "尚未开始",
    "running": "运行中",
    "in_progress": "运行中",
    "completed": "已完成",
    "has_result": "已完成",
    "mock": "已完成",
    "success": "已完成",
    "partial": "部分完成",
    "partial_failed": "部分完成",
    "needs_data": "部分完成",
    "failed": "失败",
    "error": "失败",
    "blocked": "阻断",
    "blocked_gate": "阻断",
}

_PUNCT = str.maketrans(
    {
        "，": " ",
        "。": " ",
        "、": " ",
        "；": " ",
        "：": " ",
        ",": " ",
        ".": " ",
        ";": " ",
        ":": " ",
        "！": " ",
        "？": " ",
        "!": " ",
        "?": " ",
        "（": " ",
        "）": " ",
        "(": " ",
        ")": " ",
        "【": " ",
        "】": " ",
        "[": " ",
        "]": " ",
        "“": " ",
        "”": " ",
        '"': " ",
        "'": " ",
        "—": " ",
        "-": " ",
        "/": " ",
        "\\": " ",
    }
)


def normalize_query(text: str | None) -> str:
    """Strip, NFKC, casefold, unify punctuation, and collapse whitespace."""
    raw = unicodedata.normalize("NFKC", str(text or "")).translate(_PUNCT)
    return " ".join(raw.casefold().split())


def _haystack(item: OfficialQuestion) -> str:
    parts = [item.question_id, item.title_en, item.title_zh, item.domain]
    return normalize_query(" ".join(part for part in parts if part))


def search_official_questions(
    query: str | None,
    *,
    catalog: OfficialQuestionCatalog | None = None,
) -> list[OfficialQuestion]:
    catalog = catalog or load_official_catalog()
    tokens = normalize_query(query).split()
    if not tokens:
        return list(catalog.list_questions())
    hits: list[OfficialQuestion] = []
    for item in catalog.list_questions():
        blob = _haystack(item)
        if all(token in blob for token in tokens):
            hits.append(item)
    return hits


def domain_options_with_counts(
    *,
    catalog: OfficialQuestionCatalog | None = None,
) -> list[tuple[str, int]]:
    catalog = catalog or load_official_catalog()
    counts: dict[str, int] = {}
    for item in catalog.list_questions():
        counts[item.domain] = counts.get(item.domain, 0) + 1
    return [(domain, counts[domain]) for domain in sorted(counts)]


def map_index_status(raw: str | None) -> str:
    key = str(raw or "not_started").strip().casefold()
    return _STATUS_TO_FILTER.get(key, "尚未开始")


def filter_questions(
    *,
    query: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    status_by_id: dict[str, str] | None = None,
    catalog: OfficialQuestionCatalog | None = None,
) -> list[OfficialQuestion]:
    catalog = catalog or load_official_catalog()
    rows = search_official_questions(query, catalog=catalog)
    if domain and domain != "全部":
        rows = [item for item in rows if item.domain == domain]
    if status and status != STATUS_FILTER_ALL:
        lookup = status_by_id or {}
        rows = [item for item in rows if map_index_status(lookup.get(item.question_id)) == status]
    return rows


@dataclass(frozen=True)
class QuickExample:
    key: str
    question_id: str
    title_en: str


@lru_cache(maxsize=8)
def resolve_quick_examples(digest: str) -> tuple[QuickExample, ...]:
    del digest
    catalog = load_official_catalog()
    by_title = {item.title_en: item for item in catalog.list_questions()}
    resolved: list[QuickExample] = []
    for key, title in QUICK_EXAMPLE_TITLE_EN.items():
        item = by_title.get(title)
        if item is None:
            raise ValueError(f"quick example {key!r} title not in official catalog: {title}")
        resolved.append(QuickExample(key=key, question_id=item.question_id, title_en=item.title_en))
    if len(resolved) != 5:
        raise ValueError("quick example map must contain exactly 5 official IDs")
    ids = {item.question_id for item in resolved}
    if len(ids) != 5 or any(qid not in EXPECTED_IDS for qid in ids):
        raise ValueError("quick example IDs are not five distinct official question_ids")
    return tuple(resolved)


def quick_example_map() -> dict[str, str]:
    catalog = load_official_catalog()
    return {item.key: item.question_id for item in resolve_quick_examples(catalog.get_catalog_digest())}


def official_selector_ids() -> list[str]:
    return list(EXPECTED_IDS)


def questions_as_api_items(catalog: OfficialQuestionCatalog | None = None) -> list[dict]:
    catalog = catalog or load_official_catalog()
    digest = catalog.get_catalog_digest()
    return [item.as_api_item(digest) for item in catalog.list_questions()]
