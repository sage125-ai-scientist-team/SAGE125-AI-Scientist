"""
EvidenceBundle builder — T01 Wave B（07/30）全文受控上下文构建。

相对运行时 ``_evidence_catalog``（丢弃 ``quoted_text``），本 builder：
1. 保留 quote / 作者 / 年份 / 来源类型 / content_hash / locator；
2. 按 token 预算截断，并记录 truncation_reason 与缺失字段；
3. 输出可被契约层 ``EvidenceBundle`` 校验的对象。

注意：不修改 ``app/workflow/pipeline.py``；由 T02 后续接入。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.core.schemas import EvidenceCard

# 运行时 SourceType → 契约 source_type 映射（不扩展已冻结契约枚举）。
_SOURCE_TYPE_MAP: dict[str, str] = {
    "booklet": "question_booklet",
    "rag": "paper",
    "deep_research": "web",
    "arxiv": "paper",
    "crossref": "paper",
    "openalex": "paper",
    "user_upload": "paper",
}

# 从 reliability_note 抽取 page / section / path 的简单模式。
_PAGE_RE = re.compile(r"page\s*[=:：]\s*(\d+)", re.IGNORECASE)
_SECTION_RE = re.compile(r"section\s*[=:：]\s*([^;|]+)", re.IGNORECASE)
_PATH_RE = re.compile(r"source_path\s*[=:：]\s*([^;|]+)", re.IGNORECASE)
_CHUNK_RE = re.compile(r"chunk\s*[=:：]\s*([^;|]+)", re.IGNORECASE)


@dataclass(frozen=True)
class ClaimSpec:
    """
    构建 Bundle 时的声明规格（轻量输入，非 Pydantic 契约）。

    属性：
        claim_id: 声明唯一标识。
        evidence_ids: 关联的证据 ID 列表。
        relation: supports / contradicts / context。
        claim_domain: 可选领域标签，用于跨域门禁。
        confidence: 置信度 0–1。
    """

    claim_id: str
    evidence_ids: Sequence[str]
    relation: str = "supports"
    claim_domain: Optional[str] = None
    confidence: float = 0.5


@dataclass
class BuildBundleResult:
    """
    Bundle 构建结果，附带可审计元数据。

    属性：
        bundle: 通过契约校验的 EvidenceBundle。
        missing_fields: 每张卡缺失字段列表（evidence_id → fields）。
        dropped_evidence_ids: 因 token 预算被截掉的证据 ID。
        kept_quoted_text: 是否所有保留卡均含非空 quoted_text。
    """

    bundle: EvidenceBundle
    missing_fields: dict[str, list[str]] = field(default_factory=dict)
    dropped_evidence_ids: list[str] = field(default_factory=list)
    kept_quoted_text: bool = True


def estimate_token_count(text: str) -> int:
    """
    估算文本 token 数（Wave B 轻量启发式，非模型 tokenizer）。

    规则：按 Unicode 字符数 / 4 向上取整，空串为 0。

    参数：
        text: 任意文本。

    返回：
        非负整数 token 估算值。
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def compute_content_hash(quoted_text: str) -> str:
    """
    基于原文摘录计算稳定内容哈希。

    参数：
        quoted_text: 证据原文片段。

    返回：
        ``sha256:<hex>`` 形式字符串。
    """
    digest = hashlib.sha256(quoted_text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def parse_locator_from_reliability_note(note: str) -> dict[str, Any]:
    """
    从 ``reliability_note`` 解析 page / section / path / chunk。

    参数：
        note: 运行时 EvidenceCard.reliability_note。

    返回：
        可能为空的 locator 字典；调用方需保证最终非空。
    """
    locator: dict[str, Any] = {}
    if not note:
        return locator

    page_match = _PAGE_RE.search(note)
    if page_match:
        locator["page"] = int(page_match.group(1))

    section_match = _SECTION_RE.search(note)
    if section_match:
        locator["section"] = section_match.group(1).strip()

    path_match = _PATH_RE.search(note)
    if path_match:
        locator["source_path"] = path_match.group(1).strip()

    chunk_match = _CHUNK_RE.search(note)
    if chunk_match:
        locator["chunk"] = chunk_match.group(1).strip()

    return locator


def map_runtime_source_type(source_type: str) -> str:
    """
    将运行时 ``EvidenceCard.source_type`` 映射到契约枚举。

    参数：
        source_type: 运行时来源类型字符串。

    返回：
        契约允许的 source_type；未知时回退 ``web``。
    """
    return _SOURCE_TYPE_MAP.get(source_type, "web")


def runtime_card_to_contract(
    card: EvidenceCard,
    *,
    domain: Optional[str] = None,
    locator_override: Optional[Mapping[str, Any]] = None,
) -> tuple[EvidenceCardContract, list[str]]:
    """
    将运行时 ``EvidenceCard`` 转为 ``EvidenceCardContract``，并报告缺失字段。

    关键行为：
    - **保留** ``quoted_text``（与 ``_evidence_catalog`` 相反）；
    - 生成 ``content_hash``；
    - 组装 locator（override > reliability_note 解析 > 兜底标记）；
    - booklet / title-only 保持 ``pending``，不得标 valid。

    参数：
        card: 运行时证据卡。
        domain: 可选领域标签。
        locator_override: 显式 locator，优先于解析结果。

    返回：
        (契约卡片, 缺失字段名列表)。
    """
    missing: list[str] = []
    quoted = (card.quoted_text or "").strip()
    if not quoted:
        missing.append("quoted_text")
        quoted = (card.summary or card.title or "missing_quote").strip()

    locator: dict[str, Any] = dict(locator_override or {})
    if not locator:
        locator.update(parse_locator_from_reliability_note(card.reliability_note or ""))
    if not locator:
        missing.append("locator")
        locator = {
            "source": "runtime_evidence_card",
            "evidence_id": card.id,
            "note": "locator_inferred_from_card_identity",
        }

    if not card.authors:
        missing.append("authors")
    if card.year is None:
        missing.append("year")
    if not card.doi and not card.url:
        missing.append("doi_or_url")

    source_type = map_runtime_source_type(card.source_type)
    content_hash = compute_content_hash(quoted)

    contract = EvidenceCardContract(
        evidence_id=card.id,
        source_id=card.doi or card.url or card.id,
        source_type=source_type,  # type: ignore[arg-type]
        title=card.title or "untitled",
        quoted_text=quoted,
        locator=locator,
        authors=list(card.authors or []),
        year=card.year,
        doi=card.doi,
        url=card.url,
        content_hash=content_hash,
        domain=domain,
        verification_status="pending",
    )
    return contract, missing


def _card_token_cost(card: EvidenceCardContract) -> int:
    """
    估算单张契约卡占用的 token（标题 + 原文 + 元数据开销）。

    参数：
        card: EvidenceCardContract。

    返回：
        token 估算值。
    """
    meta = f"{card.evidence_id}|{card.title}|{card.source_type}|{card.doi}|{card.url}"
    return estimate_token_count(card.quoted_text) + estimate_token_count(meta) + 16


def _select_within_budget(
    cards: Sequence[EvidenceCardContract],
    token_budget: int,
) -> tuple[list[EvidenceCardContract], list[str], bool, Optional[str]]:
    """
    在 token 预算内选择证据卡；优先保留列表前部（调用方应按相关性排序）。

    参数：
        cards: 已转换的契约卡序列。
        token_budget: 最大 token 预算。

    返回：
        (保留列表, 丢弃 ID 列表, 是否截断, 截断原因)。
    """
    kept: list[EvidenceCardContract] = []
    dropped: list[str] = []
    used = 0
    truncated = False
    reason: Optional[str] = None

    for card in cards:
        cost = _card_token_cost(card)
        if kept and used + cost > token_budget:
            dropped.append(card.evidence_id)
            truncated = True
            continue
        if not kept and cost > token_budget:
            # 至少保留一张，标记预算不足。
            kept.append(card)
            used += cost
            truncated = True
            reason = (
                f"token_budget={token_budget} insufficient for full card "
                f"cost≈{cost}; kept first evidence only"
            )
            continue
        kept.append(card)
        used += cost

    if truncated and reason is None:
        reason = (
            f"truncated to fit token_budget={token_budget}; "
            f"kept={len(kept)} dropped={len(dropped)} used_tokens≈{used}"
        )
    return kept, dropped, truncated, reason


def _build_links(
    claims: Sequence[ClaimSpec],
    kept_ids: set[str],
) -> list[ClaimEvidenceLink]:
    """
    根据 ClaimSpec 生成契约链接；丢弃指向已截断证据的边。

    参数：
        claims: 声明规格列表。
        kept_ids: 保留的 evidence_id 集合。

    返回：
        ClaimEvidenceLink 列表；若全部被滤空则抛错由上层处理。
    """
    links: list[ClaimEvidenceLink] = []
    for claim in claims:
        for evidence_id in claim.evidence_ids:
            if evidence_id not in kept_ids:
                continue
            links.append(
                ClaimEvidenceLink(
                    claim_id=claim.claim_id,
                    evidence_id=evidence_id,
                    relation=claim.relation,  # type: ignore[arg-type]
                    confidence=claim.confidence,
                    claim_domain=claim.claim_domain,
                    validation_status="pending",
                )
            )
    return links


def _default_context_claims(
    cards: Sequence[EvidenceCardContract],
) -> list[ClaimSpec]:
    """
    当调用方未提供声明时，为每张卡生成 context 链接规格。

    参数：
        cards: 契约卡列表。

    返回：
        ClaimSpec 列表。
    """
    return [
        ClaimSpec(
            claim_id=f"CTX-{card.evidence_id}",
            evidence_ids=[card.evidence_id],
            relation="context",
            claim_domain=card.domain,
            confidence=0.0,
        )
        for card in cards
    ]


def build_evidence_bundle(
    evidence_cards: Sequence[EvidenceCard],
    *,
    bundle_id: str,
    claims: Optional[Sequence[ClaimSpec]] = None,
    token_budget: int = 8000,
    domain: Optional[str] = None,
    locators: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> BuildBundleResult:
    """
    从运行时 EvidenceCard 列表构建受控 ``EvidenceBundle``。

    验收要点（手册 07/30）：
    - quoted_text 不再被删除；
    - 记录截断原因、token 预算和缺失字段；
    - 输入可审计且不暴露无关全文（按预算截断）。

    参数：
        evidence_cards: 运行时证据卡（建议已按相关性降序）。
        bundle_id: Bundle 标识。
        claims: 可选声明—证据规格；缺省时生成 context 链接。
        token_budget: token 预算上限。
        domain: 默认领域，写入每张卡（卡级 domain 未单独给出时）。
        locators: 可选 ``evidence_id → locator`` 覆盖表。

    返回：
        BuildBundleResult。

    异常：
        ValueError: 无可用证据、或截断后无法形成合法 Bundle。
    """
    if not evidence_cards:
        raise ValueError("build_evidence_bundle requires at least one EvidenceCard")

    if token_budget <= 0:
        raise ValueError("token_budget must be positive")

    locators = locators or {}
    converted: list[EvidenceCardContract] = []
    missing_fields: dict[str, list[str]] = {}

    for card in evidence_cards:
        contract, missing = runtime_card_to_contract(
            card,
            domain=domain,
            locator_override=locators.get(card.id),
        )
        converted.append(contract)
        if missing:
            missing_fields[contract.evidence_id] = missing

    kept, dropped, truncated, reason = _select_within_budget(
        converted,
        token_budget,
    )
    if not kept:
        raise ValueError("token budget removed all evidence cards")

    kept_ids = {card.evidence_id for card in kept}
    claim_specs: Sequence[ClaimSpec]
    if claims:
        claim_specs = list(claims)
    else:
        claim_specs = _default_context_claims(kept)

    links = _build_links(claim_specs, kept_ids)
    if not links:
        # 声明全指向被截断证据时，回退为保留卡的 context 链接。
        links = _build_links(_default_context_claims(kept), kept_ids)

    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        evidences=list(kept),
        links=links,
        token_budget=token_budget,
        truncated=truncated,
        truncation_reason=reason,
    )

    kept_quoted = all(bool(card.quoted_text.strip()) for card in bundle.evidences)
    return BuildBundleResult(
        bundle=bundle,
        missing_fields=missing_fields,
        dropped_evidence_ids=dropped,
        kept_quoted_text=kept_quoted,
    )


def bundle_to_agent_context(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    """
    将 Bundle 序列化为 Agent 可消费的受控上下文字典列表（保留 quoted_text）。

    参数：
        bundle: EvidenceBundle。

    返回：
        每张卡的可审计字段字典（含 quote / locator / hash）。
    """
    rows: list[dict[str, Any]] = []
    for card in bundle.evidences:
        rows.append(
            {
                "evidence_id": card.evidence_id,
                "source_id": card.source_id,
                "source_type": card.source_type,
                "title": card.title,
                "quoted_text": card.quoted_text,
                "locator": dict(card.locator),
                "authors": list(card.authors),
                "year": card.year,
                "doi": card.doi,
                "url": card.url,
                "content_hash": card.content_hash,
                "domain": card.domain,
                "verification_status": card.verification_status,
            }
        )
    return rows
