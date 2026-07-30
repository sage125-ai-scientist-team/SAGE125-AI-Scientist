"""
Claim–Evidence 支持关系检查器 — T01 Wave B（07/31）。

在 ``app/evidence`` 内实现，不修改已冻结的 ``app/contracts/evidence.py``，
不修改 ``app/workflow/pipeline.py``，不影响 Wave A 已通过契约。

阻断类别（≥5）：
1. UNKNOWN_EVIDENCE_ID — 引用不存在的 evidence_id
2. METADATA_ONLY — 标题/元数据冒充原文（quote==title 或空 quote）
3. BOOKLET_EXCLUDED — 问题册不得支撑 established facts
4. CROSS_DOMAIN — supports 跨域外推
5. NON_ENTAILMENT — 声明与摘录无明显语义重叠（保守启发式）
6. UNSUPPORTED_CLAIM — supports 关系但无任何可用证据绑定
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)

# 英文停用词 + 极短 token，用于轻量重叠检查（非完整 NLP）。
_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "was",
    "were",
    "be",
    "as",
    "by",
    "with",
    "that",
    "this",
    "from",
    "it",
    "at",
    "as",
    "的",
    "了",
    "和",
    "与",
    "在",
    "是",
    "为",
    "及",
    "或",
}


class SupportErrorCode(str, Enum):
    """
    支持检查错误码（稳定字符串，供测试与下游消费）。
    """

    UNKNOWN_EVIDENCE_ID = "UNKNOWN_EVIDENCE_ID"
    METADATA_ONLY = "METADATA_ONLY"
    BOOKLET_EXCLUDED = "BOOKLET_EXCLUDED"
    CROSS_DOMAIN = "CROSS_DOMAIN"
    NON_ENTAILMENT = "NON_ENTAILMENT"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"


class SupportDecision(str, Enum):
    """
    单条声明—证据边的检查结论。
    """

    ALLOW = "allow"
    DEGRADE = "degrade"
    BLOCK = "block"


@dataclass(frozen=True)
class SupportFinding:
    """
    单条检查发现。

    属性：
        code: 错误码。
        decision: allow / degrade / block。
        claim_id: 相关声明 ID（可空）。
        evidence_id: 相关证据 ID（可空）。
        message: 人类可读说明。
    """

    code: SupportErrorCode
    decision: SupportDecision
    message: str
    claim_id: Optional[str] = None
    evidence_id: Optional[str] = None


@dataclass
class SupportCheckResult:
    """
    整次检查结果。

    属性：
        findings: 全部发现（含阻断与降级）。
        blocked: 是否存在任一 BLOCK。
        degraded_claim_ids: 被降级的声明 ID。
        allowed_links: 可通过的链接（仅 allow）。
    """

    findings: list[SupportFinding] = field(default_factory=list)
    blocked: bool = False
    degraded_claim_ids: list[str] = field(default_factory=list)
    allowed_links: list[ClaimEvidenceLink] = field(default_factory=list)

    @property
    def error_codes(self) -> list[str]:
        """
        返回本次出现的错误码列表（去重保序）。

        返回：
            错误码字符串列表。
        """
        seen: set[str] = set()
        codes: list[str] = []
        for finding in self.findings:
            value = finding.code.value
            if value not in seen:
                seen.add(value)
                codes.append(value)
        return codes


@dataclass(frozen=True)
class ClaimText:
    """
    带正文的声明输入（检查器需要文本才能做不蕴含判定）。

    属性：
        claim_id: 声明 ID。
        text: 声明文本。
        domain: 可选领域。
        evidence_ids: 声称绑定的证据 ID。
        relation: 关系类型，默认 supports。
        confidence: 置信度。
    """

    claim_id: str
    text: str
    evidence_ids: Sequence[str] = ()
    domain: Optional[str] = None
    relation: str = "supports"
    confidence: float = 0.5


def _normalize_tokens(text: str) -> set[str]:
    """
    将文本切成小写 token 集合，去掉停用词与过短词。

    参数：
        text: 原始文本。

    返回：
        token 集合。
    """
    raw = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", text.lower())
    return {tok for tok in raw if len(tok) >= 2 and tok not in _STOPWORDS}


def is_metadata_only(card: EvidenceCardContract) -> bool:
    """
    判断证据是否仅为标题/元数据（无独立原文）。

    参数：
        card: 契约证据卡。

    返回：
        True 表示 metadata-only。
    """
    quote = (card.quoted_text or "").strip()
    title = (card.title or "").strip()
    if not quote:
        return True
    return quote.lower() == title.lower()


def is_booklet_evidence(card: EvidenceCardContract) -> bool:
    """
    判断证据是否来自问题册。

    参数：
        card: 契约证据卡。

    返回：
        True 表示 booklet / question_booklet 来源。
    """
    if card.source_type == "question_booklet":
        return True
    if "booklet" in (card.source_id or "").lower():
        return True
    source = str(card.locator.get("source", "")).lower()
    return source == "booklet"


def has_lexical_entailment(claim_text: str, quoted_text: str) -> bool:
    """
    保守词法重叠启发：声明与摘录至少共享 1 个实义词，否则视为不蕴含。

    说明：这不是完整 NLI；不确定时由上层降级，禁止伪装通过。

    参数：
        claim_text: 声明正文。
        quoted_text: 证据原文。

    返回：
        True 表示通过最小重叠门。
    """
    claim_tokens = _normalize_tokens(claim_text)
    quote_tokens = _normalize_tokens(quoted_text)
    if not claim_tokens or not quote_tokens:
        return False
    return bool(claim_tokens & quote_tokens)


def check_claim_evidence_support(
    claims: Sequence[ClaimText],
    evidences: Sequence[EvidenceCardContract],
    *,
    require_supports_binding: bool = True,
) -> SupportCheckResult:
    """
    对声明—证据绑定执行支持关系检查。

    策略：
    - BLOCK：未知 ID / booklet supports / metadata-only 充当 supports / 无绑定 supports；
    - DEGRADE：跨域、不蕴含等不确定项 → 降级，不伪装 allow；
    - ALLOW：通过全部门禁的 supports/context/contradicts 边。

    参数：
        claims: 带文本的声明列表。
        evidences: 可用契约证据卡。
        require_supports_binding: supports 声明是否必须至少绑定一张卡。

    返回：
        SupportCheckResult。
    """
    by_id = {card.evidence_id: card for card in evidences}
    result = SupportCheckResult()
    degraded: set[str] = set()

    for claim in claims:
        if require_supports_binding and claim.relation == "supports" and not claim.evidence_ids:
            result.findings.append(
                SupportFinding(
                    code=SupportErrorCode.UNSUPPORTED_CLAIM,
                    decision=SupportDecision.BLOCK,
                    claim_id=claim.claim_id,
                    message="supports claim has no evidence binding",
                )
            )
            result.blocked = True
            continue

        if not claim.evidence_ids:
            # context 类无绑定：降级为待核验，不阻断整包。
            result.findings.append(
                SupportFinding(
                    code=SupportErrorCode.UNSUPPORTED_CLAIM,
                    decision=SupportDecision.DEGRADE,
                    claim_id=claim.claim_id,
                    message="claim has no evidence_ids; degraded to pending",
                )
            )
            degraded.add(claim.claim_id)
            continue

        for evidence_id in claim.evidence_ids:
            card = by_id.get(evidence_id)
            if card is None:
                result.findings.append(
                    SupportFinding(
                        code=SupportErrorCode.UNKNOWN_EVIDENCE_ID,
                        decision=SupportDecision.BLOCK,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        message=f"unknown evidence_id: {evidence_id}",
                    )
                )
                result.blocked = True
                continue

            # 1) booklet 不得作为 supports 事实支撑。
            if claim.relation == "supports" and is_booklet_evidence(card):
                result.findings.append(
                    SupportFinding(
                        code=SupportErrorCode.BOOKLET_EXCLUDED,
                        decision=SupportDecision.BLOCK,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        message="question booklet cannot support established facts",
                    )
                )
                result.blocked = True
                continue

            # 2) metadata-only 不得作为 supports。
            if claim.relation == "supports" and is_metadata_only(card):
                result.findings.append(
                    SupportFinding(
                        code=SupportErrorCode.METADATA_ONLY,
                        decision=SupportDecision.BLOCK,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        message="metadata-only evidence cannot support claims",
                    )
                )
                result.blocked = True
                continue

            # 3) 跨域 supports → 降级（不确定，不伪装通过）。
            if (
                claim.relation == "supports"
                and claim.domain
                and card.domain
                and claim.domain.strip().lower() != card.domain.strip().lower()
            ):
                result.findings.append(
                    SupportFinding(
                        code=SupportErrorCode.CROSS_DOMAIN,
                        decision=SupportDecision.DEGRADE,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        message=(
                            f"cross-domain supports degraded: claim={claim.domain!r} "
                            f"evidence={card.domain!r}"
                        ),
                    )
                )
                degraded.add(claim.claim_id)
                continue

            # 4) 语义/词法不蕴含 → 降级。
            if claim.relation == "supports" and not has_lexical_entailment(
                claim.text,
                card.quoted_text,
            ):
                result.findings.append(
                    SupportFinding(
                        code=SupportErrorCode.NON_ENTAILMENT,
                        decision=SupportDecision.DEGRADE,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        message="claim not lexically supported by quoted_text; degraded",
                    )
                )
                degraded.add(claim.claim_id)
                continue

            result.allowed_links.append(
                ClaimEvidenceLink(
                    claim_id=claim.claim_id,
                    evidence_id=evidence_id,
                    relation=claim.relation,  # type: ignore[arg-type]
                    confidence=claim.confidence,
                    claim_domain=claim.domain,
                    validation_status="pending",
                )
            )

    result.degraded_claim_ids = sorted(degraded)
    return result


def check_bundle_support(
    bundle: EvidenceBundle,
    claim_texts: Sequence[ClaimText],
) -> SupportCheckResult:
    """
    对已构建 Bundle + 声明文本执行支持检查。

    参数：
        bundle: EvidenceBundle。
        claim_texts: 声明文本列表（evidence_ids 可与 bundle.links 对齐）。

    返回：
        SupportCheckResult。
    """
    # 若 ClaimText 未带 evidence_ids，则从 bundle.links 回填。
    enriched: list[ClaimText] = []
    links_by_claim: dict[str, list[str]] = {}
    for link in bundle.links:
        links_by_claim.setdefault(link.claim_id, []).append(link.evidence_id)

    for claim in claim_texts:
        ids = list(claim.evidence_ids) or links_by_claim.get(claim.claim_id, [])
        enriched.append(
            ClaimText(
                claim_id=claim.claim_id,
                text=claim.text,
                evidence_ids=ids,
                domain=claim.domain,
                relation=claim.relation,
                confidence=claim.confidence,
            )
        )

    return check_claim_evidence_support(enriched, bundle.evidences)
