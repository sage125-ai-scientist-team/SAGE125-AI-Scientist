"""
app.rag.evidence —— 各类来源到 EvidenceCard 的统一转换、去重与导出。

覆盖来源：
    - RAG 片段（chunk_to_evidence_card）
    - 文献 API（literature_to_evidence_card，适配 Arxiv/OpenAlex/Crossref）
    - Deep Research（deep_research_to_evidence_cards）

核心原则（反造假、可追溯）：
    - quoted_text 必须为原文片段，禁止模型改写；
    - DOI / URL 不存在则留空，禁止伪造；
    - reliability_note 记录来源与可靠性标记（含 rerank 状态）；
    - DeepResearch 结果只能标记为 source_type="deep_research"，需下游核验，
      不得直接作为 validated reference。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from app.core.logging import get_logger
from app.core.schemas import EvidenceCard
from app.rag.chunker import Chunk

# 模块级日志器。
logger = get_logger("rag.evidence")

# 各来源类型的可靠性排序（用于去重时保留更可靠者，数值越大越可靠）。
_SOURCE_RELIABILITY = {
    "crossref": 5,
    "openalex": 4,
    "arxiv": 3,
    "booklet": 3,
    "user_upload": 2,
    "rag": 2,
    "deep_research": 1,
}


def _quoted_hash(text: str) -> str:
    """
    计算 quoted_text 的稳定 hash（用于去重）。

    参数：
        text: 原文片段。

    返回：
        16 位十六进制 hash。
    """
    # 归一化空白后计算，消除排版差异。
    normalized = " ".join(text.split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _clamp01(value: float) -> float:
    """
    将分数夹取到 [0,1]。

    参数：
        value: 原始分数。

    返回：
        夹取后的分数。
    """
    # 保证 relevance_score 合法。
    return max(0.0, min(1.0, float(value)))


def chunk_to_evidence_card(
    chunk: Union[Chunk, dict],
    score: float,
    source_type: str = "rag",
    query: Optional[str] = None,
    rerank_score: Optional[float] = None,
    reliability_note_extra: Optional[str] = None,
) -> EvidenceCard:
    """
    将 RAG 片段转换为 EvidenceCard（quoted_text 保持原文，不改写）。

    参数：
        chunk:                  Chunk 对象或等价 dict。
        score:                  向量相似度分数（0-1）。
        source_type:            证据来源类型（rag/booklet/user_upload）。
        query:                  触发检索的查询（写入 reliability_note，便于追溯）。
        rerank_score:           重排序分数（若有则优先作为相关性）。
        reliability_note_extra: 附加可靠性标记（如 rerank_failed_fallback_used）。

    返回：
        构造好的 EvidenceCard。
    """
    # 兼容 Chunk 与 dict 两种输入。
    if isinstance(chunk, Chunk):
        text = chunk.text
        metadata = chunk.metadata
        chunk_id = chunk.chunk_id
    else:
        text = chunk.get("text", "")
        metadata = chunk.get("metadata", {})
        chunk_id = chunk.get("chunk_id", "")

    # 稳定 ID：EV-{source_hash 前 12 位}。
    source_hash = metadata.get("source_hash") or _quoted_hash(text)
    evidence_id = f"EV-{source_hash[:12]}"

    # 标题：来源文件名 + 页码。
    source_name = metadata.get("source_name", "unknown")
    page = metadata.get("page")
    title = f"{source_name} (p{page})" if page is not None else source_name

    # 相关性：优先 rerank_score，否则 score，归一化到 0-1。
    relevance = _clamp01(rerank_score if rerank_score is not None else score)

    # summary：无 LLM 摘要时用原文前 180 字符。
    summary = text[:180].strip()

    # reliability_note：记录来源路径/页码/chunk/query/rerank 状态。
    notes = [
        f"source_path={metadata.get('source_path', '')}",
        f"source_role={metadata.get('source_role', '')}",
        f"page={page}",
        f"chunk_id={chunk_id}",
    ]
    if query:
        notes.append(f"query={query[:80]}")
    notes.append(f"rerank={'used' if rerank_score is not None else 'not_used'}")
    if reliability_note_extra:
        notes.append(reliability_note_extra)
    reliability_note = "; ".join(notes)

    return EvidenceCard(
        id=evidence_id,
        source_type=source_type,  # type: ignore[arg-type]
        title=title,
        authors=[],
        year=None,
        url=None,
        doi=None,
        quoted_text=text,
        summary=summary,
        relevance_score=relevance,
        reliability_note=reliability_note,
    )


def literature_to_evidence_card(
    item: Union[EvidenceCard, dict], source_type: str
) -> Optional[EvidenceCard]:
    """
    将文献 API 结果适配为 EvidenceCard（DOI/URL 不存在则留空，绝不伪造）。

    参数：
        item:        文献条目（EvidenceCard 或字段 dict）。
        source_type: 来源类型（arxiv/openalex/crossref）。

    返回：
        EvidenceCard；若无真实 title 则返回 None（不生成空壳证据）。
    """
    # literature_clients 已返回 EvidenceCard：仅补充 reliability_note 后透传。
    if isinstance(item, EvidenceCard):
        # 无标题则不生成。
        if not item.title.strip():
            return None
        # 补充来源标记（若尚未包含）。
        if source_type not in item.reliability_note:
            item.reliability_note = (item.reliability_note + f"; api_source={source_type}").strip("; ")
        return item

    # dict 输入：逐字段安全提取，缺失则留空/None。
    title = (item.get("title") or "").strip()
    if not title:
        return None
    quoted = (item.get("abstract") or item.get("summary") or title).strip()
    doi = item.get("doi") or None
    url = item.get("url") or None
    authors = item.get("authors") or []
    year = item.get("year")
    ev_id = f"LIT-{_quoted_hash(title)[:12]}"
    return EvidenceCard(
        id=ev_id,
        source_type=source_type,  # type: ignore[arg-type]
        title=title,
        authors=[a for a in authors if a],
        year=year,
        url=url,
        doi=doi,
        quoted_text=quoted[:800],
        summary=quoted[:180],
        relevance_score=0.5,
        reliability_note=f"api_source={source_type}",
    )


def deep_research_to_evidence_cards(result: dict) -> list[EvidenceCard]:
    """
    将 Deep Research 结果转换为 EvidenceCard 列表（标记为需下游核验）。

    参数：
        result: qwen_deep_research_client.run_deep_research 的返回字典。

    返回：
        EvidenceCard 列表：
            - 若含引用列表则逐条转换；
            - 否则生成 1 张 summary 卡片，reliability_note 标注需核验。
    """
    cards: list[EvidenceCard] = []
    # 失败结果不产出证据。
    if not result or result.get("status") != "succeeded":
        return cards

    references = result.get("references") or []
    if references:
        # 逐条引用转换（DeepResearch 引用仍需下游核验，不得直接 validated）。
        for i, ref in enumerate(references):
            title = (ref.get("title") or ref.get("description") or "").strip()
            if not title:
                continue
            url = ref.get("url") or None
            cards.append(
                EvidenceCard(
                    id=f"DR-{_quoted_hash(title + str(i))[:12]}",
                    source_type="deep_research",
                    title=title[:200],
                    authors=[],
                    year=None,
                    url=url,
                    doi=None,
                    quoted_text=(ref.get("description") or title)[:800],
                    summary=(ref.get("description") or title)[:180],
                    relevance_score=0.4,
                    reliability_note="DeepResearch reference; requires downstream verification.",
                )
            )
    else:
        # 无可核验引用：仅生成 1 张 summary 卡片。
        content = (result.get("content") or "").strip()
        if content:
            cards.append(
                EvidenceCard(
                    id=f"DR-{_quoted_hash(content)[:12]}",
                    source_type="deep_research",
                    title="DeepResearch summary",
                    authors=[],
                    year=None,
                    url=None,
                    doi=None,
                    quoted_text=content[:800],
                    summary=content[:180],
                    relevance_score=0.3,
                    reliability_note="DeepResearch summary; requires downstream verification.",
                )
            )
    return cards


def evidence_deduplicate(cards: list[EvidenceCard]) -> list[EvidenceCard]:
    """
    对证据去重：DOI / URL / 标题高相似 / quoted_text hash 相同者合并。

    参数：
        cards: 证据卡片列表。

    返回：
        去重后的列表（保留 relevance_score 更高、来源更可靠者）。
    """
    # 以多种 key 索引已保留证据；冲突时择优替换。
    kept: list[EvidenceCard] = []
    # key -> kept 列表索引。
    index: dict[str, int] = {}

    def _better(a: EvidenceCard, b: EvidenceCard) -> EvidenceCard:
        """比较两张证据，返回更优者（先比来源可靠性，再比相关性）。"""
        ra = _SOURCE_RELIABILITY.get(a.source_type, 0)
        rb = _SOURCE_RELIABILITY.get(b.source_type, 0)
        if ra != rb:
            return a if ra > rb else b
        return a if a.relevance_score >= b.relevance_score else b

    for card in cards:
        # 生成候选去重键。
        keys = []
        if card.doi:
            keys.append(f"doi:{card.doi.lower()}")
        if card.url:
            keys.append(f"url:{card.url.lower()}")
        keys.append(f"title:{' '.join(card.title.lower().split())}")
        keys.append(f"quote:{_quoted_hash(card.quoted_text)}")

        # 查找是否已存在任一相同键。
        hit_idx = next((index[k] for k in keys if k in index), None)
        if hit_idx is None:
            # 新证据：加入并登记所有键。
            new_idx = len(kept)
            kept.append(card)
            for k in keys:
                index[k] = new_idx
        else:
            # 冲突：择优保留，并更新键指向。
            better = _better(kept[hit_idx], card)
            kept[hit_idx] = better
            for k in keys:
                index[k] = hit_idx
    return kept


def evidence_export(
    cards: list[EvidenceCard], run_id: str, also_cache: bool = True
) -> dict:
    """
    导出证据到 exports/{run_id}/evidence_cards.json（可选写 data/cache 缓存）。

    参数：
        cards:      证据卡片列表。
        run_id:     运行 ID（用于导出目录）。
        also_cache: 是否同时追加写 data/cache/evidence_cache.jsonl。

    返回：
        含导出路径的字典 {"json_path": ..., "count": ...}。
    """
    # 导出目录：exports/{run_id}/。
    export_dir = Path("exports") / run_id
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "evidence_cards.json"
    # 序列化证据（pydantic v2 model_dump）。
    payload = [c.model_dump() for c in cards]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 可选缓存：追加写 jsonl。
    if also_cache:
        cache_path = Path("data/cache/evidence_cache.jsonl")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("a", encoding="utf-8") as f:
            for c in cards:
                rec = {"run_id": run_id, "exported_at": datetime.now(timezone.utc).isoformat(), **c.model_dump()}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    logger.info("evidence_export：run_id=%s，count=%d", run_id, len(cards))
    return {"json_path": str(json_path), "count": len(cards)}
