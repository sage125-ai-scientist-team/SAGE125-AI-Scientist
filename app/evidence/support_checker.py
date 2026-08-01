"""
Claim–Evidence 支持关系检查器 — T01 Wave B（07/31）。

在 ``app/evidence`` 内实现，不修改已冻结的 ``app/contracts/evidence.py``，
不修改 ``app/workflow/pipeline.py``，不影响 Wave A 已通过契约。

阻断类别（≥5）：
1. UNKNOWN_EVIDENCE_ID — 引用不存在的 evidence_id
2. METADATA_ONLY — 标题/DOI/URL/元数据冒充原文（含 DOI-only quote）
3. BOOKLET_EXCLUDED — 问题册不得支撑 established facts（含改名线索）
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
    FAKE_BOOKLET_EVIDENCE_ID = "FAKE_BOOKLET_EVIDENCE_ID"
    METADATA_ONLY = "METADATA_ONLY"
    BOOKLET_EXCLUDED = "BOOKLET_EXCLUDED"
    CROSS_DOMAIN = "CROSS_DOMAIN"
    NON_ENTAILMENT = "NON_ENTAILMENT"
    OVERGENERALIZATION = "OVERGENERALIZATION"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"


# Q028 类虚构证据 ID：booklet_excerpt_Q028 等。
_FAKE_BOOKLET_EVIDENCE_ID_RE = re.compile(
    r"^booklet_excerpt_Q\d+$",
    re.IGNORECASE,
)

# 单一癌种证据 vs “所有癌症”外推（保守词表）。
_SPECIFIC_CANCER_PATTERNS = (
    r"lung adenocarcinoma",
    r"lung cancer",
    r"breast cancer",
    r"prostate cancer",
    r"colorectal cancer",
    r"肺癌",
    r"肺腺癌",
    r"乳腺癌",
    r"前列腺癌",
    r"结直肠癌",
)
_GENERAL_CANCER_PATTERNS = (
    r"all cancers?",
    r"every cancer",
    r"any cancer",
    r"all types of cancer",
    r"所有癌症",
    r"全部癌症",
    r"各种癌症",
    r"任意癌症",
)


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


# DOI / DOI URL：单独出现时不得充当科学原文（手册：标题/DOI/问题册不得单独支撑事实）。
_DOI_CORE_RE = re.compile(
    r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$",
    re.IGNORECASE,
)
_DOI_PREFIXED_RE = re.compile(
    r"^(?:doi:|https?://(?:dx\.)?doi\.org/)\s*(10\.\d{4,9}/[-._;()/:A-Z0-9]+)$",
    re.IGNORECASE,
)
_URL_ONLY_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def is_doi_only_text(text: str) -> bool:
    """
    判断文本是否仅为 DOI 或 DOI URL（无独立科学原文）。

    参数：
        text: quoted_text 或同类字段。

    返回：
        True 表示 DOI-only / DOI-URL-only。

    说明：
        覆盖队长 DOI probe：``quoted_text='10.1234/x.y.z'`` 必须为 True。
    """
    value = (text or "").strip()
    if not value:
        return False
    if _DOI_CORE_RE.match(value):
        return True
    prefixed = _DOI_PREFIXED_RE.match(value)
    if prefixed and _DOI_CORE_RE.match(prefixed.group(1)):
        return True
    return False


def is_metadata_only(card: EvidenceCardContract) -> bool:
    """
    判断证据是否仅为标题/DOI/URL 等元数据（无独立原文）。

    参数：
        card: 契约证据卡。

    返回：
        True 表示 metadata-only，supports 必须 BLOCK。

    规则：
        1. 空 quote；
        2. quote 与 title 忽略大小写全等；
        3. quote 仅为 DOI / DOI URL；
        4. quote 与 ``doi`` / ``url`` 字段规范化后相等；
        5. quote 仅为裸 http(s) URL（无正文）。
    """
    quote = (card.quoted_text or "").strip()
    title = (card.title or "").strip()
    if not quote:
        return True
    if quote.lower() == title.lower():
        return True
    if is_doi_only_text(quote):
        return True

    doi = (card.doi or "").strip()
    if doi and quote.lower() in {doi.lower(), f"doi:{doi.lower()}", f"https://doi.org/{doi.lower()}"}:
        return True

    url = (card.url or "").strip()
    if url and quote.lower() == url.lower():
        return True

    if _URL_ONLY_RE.match(quote):
        return True

    return False


def is_booklet_evidence(card: EvidenceCardContract) -> bool:
    """
    判断证据是否来自问题册（含改名/别名绕过的保守识别）。

    参数：
        card: 契约证据卡。

    返回：
        True 表示 booklet / question_booklet 来源。

    说明：
        除 ``source_type`` 外，检查 source_id / title / locator / evidence_id
        中的 booklet / question_booklet / booklet_excerpt 线索，降低 T04 改名孔洞风险。
    """
    if card.source_type == "question_booklet":
        return True

    haystacks = [
        card.source_id or "",
        card.evidence_id or "",
        card.title or "",
        str(card.locator.get("source", "")),
        str(card.locator.get("collection", "")),
        str(card.locator.get("corpus", "")),
        str(card.locator.get("dataset", "")),
    ]
    joined = " ".join(haystacks).lower()
    markers = (
        "booklet",
        "question_booklet",
        "question-booklet",
        "booklet_excerpt",
        "bookletexcerpt",
    )
    return any(marker in joined for marker in markers)


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


def is_fake_booklet_evidence_id(evidence_id: str) -> bool:
    """
    判断是否为 Q028 类虚构 booklet 证据 ID。

    参数：
        evidence_id: 证据 ID。

    返回：
        True 表示匹配 ``booklet_excerpt_Q\\d+``。
    """
    return bool(_FAKE_BOOKLET_EVIDENCE_ID_RE.match((evidence_id or "").strip()))


def is_cancer_overgeneralization(claim_text: str, quoted_text: str) -> bool:
    """
    检测“单一癌种证据 → 所有癌症”外推。

    参数：
        claim_text: 声明正文。
        quoted_text: 证据原文。

    返回：
        True 表示疑似过度外推，应降级而非 allow。
    """
    claim_l = (claim_text or "").lower()
    quote_l = (quoted_text or "").lower()
    has_specific = any(re.search(p, quote_l) for p in _SPECIFIC_CANCER_PATTERNS)
    has_general = any(re.search(p, claim_l) for p in _GENERAL_CANCER_PATTERNS)
    return has_specific and has_general


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
            # 0) Q028 虚构 booklet 证据 ID：无论是否在池中，一律 BLOCK。
            if is_fake_booklet_evidence_id(evidence_id):
                result.findings.append(
                    SupportFinding(
                        code=SupportErrorCode.FAKE_BOOKLET_EVIDENCE_ID,
                        decision=SupportDecision.BLOCK,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        message=(
                            f"fabricated booklet evidence_id is forbidden: {evidence_id}"
                        ),
                    )
                )
                result.blocked = True
                continue

            card = by_id.get(evidence_id)
            if card is None:
                result.findings.append(
                    SupportFinding(
                        code=SupportErrorCode.UNKNOWN_EVIDENCE_ID,
                        decision=SupportDecision.BLOCK,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        message=(
                            f"unknown evidence_id={evidence_id!r} for claim="
                            f"{claim.claim_id!r}; not present in evidence pool"
                        ),
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
                        message=(
                            f"booklet evidence {evidence_id!r} cannot support "
                            f"established facts for claim {claim.claim_id!r}"
                        ),
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
                        message=(
                            f"metadata-only evidence {evidence_id!r} "
                            f"(quote equals title) cannot support claim {claim.claim_id!r}"
                        ),
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

            # 4) 单一癌种 → 所有癌症 外推 → 降级（Q028 DoD）。
            if claim.relation == "supports" and is_cancer_overgeneralization(
                claim.text,
                card.quoted_text,
            ):
                result.findings.append(
                    SupportFinding(
                        code=SupportErrorCode.OVERGENERALIZATION,
                        decision=SupportDecision.DEGRADE,
                        claim_id=claim.claim_id,
                        evidence_id=evidence_id,
                        message=(
                            "single-cancer evidence cannot unconditionally support "
                            "all-cancer claims; degraded to pending verification"
                        ),
                    )
                )
                degraded.add(claim.claim_id)
                continue

            # 5) 语义/词法不蕴含 → 降级。
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
                        message=(
                            f"claim {claim.claim_id!r} not lexically supported by "
                            f"quoted_text of {evidence_id!r}; degraded"
                        ),
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
