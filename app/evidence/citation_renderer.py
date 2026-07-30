"""
可点击引用渲染器 — T01 Wave B（08/01）。

在 ``app/evidence`` 内生成：
1. Markdown 引用（结论 → 证据锚点）；
2. 给 T08 的稳定 JSON payload（来源/页码/章节/原文/支持状态）。

不修改 ``pipeline.py`` / UI 主流程；T08 可直接消费 payload。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import quote

from app.contracts.evidence import EvidenceCardContract
from app.evidence.support_checker import SupportDecision


@dataclass(frozen=True)
class CitationItem:
    """
    单条可点击引用。

    属性：
        claim_id: 声明 ID。
        evidence_id: 证据 ID（锚点）。
        title: 文献标题。
        source_url: 可点击外链（DOI/URL 规范化后）。
        locator: 页码/章节等定位。
        quoted_text: 原文片段。
        support_status: allow / degrade / block / pending。
        support_note: 可选说明（降级/阻断原因）。
    """

    claim_id: str
    evidence_id: str
    title: str
    source_url: Optional[str]
    locator: dict[str, Any]
    quoted_text: str
    support_status: str
    support_note: str = ""


@dataclass
class T08CitationPayload:
    """
    给 T08 前端/报告消费的引用载荷。

    属性：
        schema_version: 载荷版本。
        upstream_ref: 上游版本说明（PR/分支）。
        citations: CitationItem 列表的 dict 形式。
        markdown: 可粘贴进报告的 Markdown。
    """

    schema_version: str = "t01-citation-payload-v1"
    upstream_ref: str = "integration/2026-08-10 + t01/b-evidence-core"
    citations: list[dict[str, Any]] = field(default_factory=list)
    markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        """
        序列化为普通 dict，便于 JSON 导出。

        返回：
            可 ``json.dumps`` 的字典。
        """
        return {
            "schema_version": self.schema_version,
            "upstream_ref": self.upstream_ref,
            "citations": list(self.citations),
            "markdown": self.markdown,
        }


def normalize_source_url(
    *,
    doi: Optional[str],
    url: Optional[str],
) -> Optional[str]:
    """
    将 DOI/URL 规范为可点击链接；禁止伪造，缺失则返回 None。

    参数：
        doi: DOI 字符串。
        url: 原始 URL。

    返回：
        https 链接或 None。
    """
    if doi and doi.strip():
        cleaned = doi.strip()
        if cleaned.lower().startswith("http"):
            return cleaned
        return f"https://doi.org/{cleaned}"
    if url and url.strip():
        return url.strip()
    return None


def evidence_anchor_id(evidence_id: str) -> str:
    """
    生成 Markdown/HTML 锚点 ID。

    参数：
        evidence_id: 证据 ID。

    返回：
        安全锚点字符串。
    """
    safe = quote(evidence_id, safe="_-.")
    return f"evidence-{safe}"


def format_locator(locator: Mapping[str, Any]) -> str:
    """
    将 locator 格式化为短文本（页码/章节优先）。

    参数：
        locator: 定位字典。

    返回：
        人类可读定位串。
    """
    parts: list[str] = []
    if "page" in locator:
        parts.append(f"p.{locator['page']}")
    if "section" in locator:
        parts.append(str(locator["section"]))
    if "document" in locator and not parts:
        parts.append(str(locator["document"]))
    if not parts:
        for key in ("source_path", "chunk", "field", "source"):
            if key in locator:
                parts.append(f"{key}={locator[key]}")
    return ", ".join(parts) if parts else "locator:n/a"


def build_citation_item(
    *,
    claim_id: str,
    card: EvidenceCardContract,
    support_status: str = SupportDecision.ALLOW.value,
    support_note: str = "",
) -> CitationItem:
    """
    从契约证据卡构建单条 CitationItem。

    参数：
        claim_id: 声明 ID。
        card: EvidenceCardContract。
        support_status: 支持状态。
        support_note: 状态说明。

    返回：
        CitationItem。
    """
    return CitationItem(
        claim_id=claim_id,
        evidence_id=card.evidence_id,
        title=card.title,
        source_url=normalize_source_url(doi=card.doi, url=card.url),
        locator=dict(card.locator),
        quoted_text=card.quoted_text,
        support_status=support_status,
        support_note=support_note,
    )


def render_citation_markdown(citations: Sequence[CitationItem]) -> str:
    """
    渲染可从结论一键回到证据的 Markdown。

    结构：
    - 声明行带内部锚点链接；
    - 后附证据详情块（含原文、定位、外链、支持状态）。

    参数：
        citations: 引用条目列表。

    返回：
        Markdown 字符串。
    """
    if not citations:
        return "_No citations available._\n"

    lines: list[str] = ["## Citations", ""]
    # 声明索引
    lines.append("### Claims")
    lines.append("")
    for item in citations:
        anchor = evidence_anchor_id(item.evidence_id)
        status = item.support_status
        lines.append(
            f"- Claim `{item.claim_id}` → "
            f"[`{item.evidence_id}`](#{anchor}) "
            f"(status: **{status}**)"
        )
    lines.append("")
    lines.append("### Evidence details")
    lines.append("")

    seen: set[str] = set()
    for item in citations:
        if item.evidence_id in seen:
            continue
        seen.add(item.evidence_id)
        anchor = evidence_anchor_id(item.evidence_id)
        lines.append(f'<a id="{anchor}"></a>')
        lines.append(f"#### `{item.evidence_id}` — {item.title}")
        lines.append("")
        loc = format_locator(item.locator)
        lines.append(f"- Locator: {loc}")
        if item.source_url:
            lines.append(f"- Source: [{item.source_url}]({item.source_url})")
        else:
            lines.append("- Source: _(no DOI/URL)_")
        lines.append(f"- Support status: **{item.support_status}**")
        if item.support_note:
            lines.append(f"- Note: {item.support_note}")
        lines.append(f"- Quote: > {item.quoted_text}")
        lines.append("")

    return "\n".join(lines)


def build_t08_citation_payload(
    citations: Sequence[CitationItem],
    *,
    upstream_ref: str = "integration/2026-08-10 + t01/b-evidence-core",
) -> T08CitationPayload:
    """
    构建 T08 可消费的引用 payload（Markdown + JSON 字段）。

    参数：
        citations: 引用条目。
        upstream_ref: 上游版本标记，写入 payload 便于联调对账。

    返回：
        T08CitationPayload。
    """
    markdown = render_citation_markdown(citations)
    return T08CitationPayload(
        upstream_ref=upstream_ref,
        citations=[asdict(item) for item in citations],
        markdown=markdown,
    )


def render_claim_to_evidence_jump(
    claim_id: str,
    evidence_id: str,
) -> str:
    """
    生成单条“结论 → 证据”跳转 Markdown 链接。

    参数：
        claim_id: 声明 ID。
        evidence_id: 证据 ID。

    返回：
        Markdown 链接文本。
    """
    return f"[claim {claim_id} → {evidence_id}](#{evidence_anchor_id(evidence_id)})"
