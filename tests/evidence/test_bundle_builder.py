"""
T01 Wave B：EvidenceBundle builder 验收测试（07/30）。

核心验收：quoted_text 不被删除；token 截断可审计；缺失字段可报告。
"""

from app.core.schemas import EvidenceCard
from app.evidence.bundle_builder import (
    ClaimSpec,
    build_evidence_bundle,
    bundle_to_agent_context,
    compute_content_hash,
    estimate_token_count,
)


def _card(
    evidence_id: str,
    *,
    title: str = "Paper title",
    quote: str = "Original quoted evidence body text.",
    source_type: str = "arxiv",
    relevance: float = 0.9,
    reliability_note: str = "source_path=demo.pdf; page=3; section=Results",
) -> EvidenceCard:
    """
    构造运行时 EvidenceCard 测试夹具。

    参数：
        evidence_id: 证据 ID。
        title: 标题。
        quote: 原文摘录。
        source_type: 运行时来源类型。
        relevance: 相关性分数。
        reliability_note: 可靠性备注（可解析 locator）。

    返回：
        EvidenceCard 实例。
    """
    return EvidenceCard(
        id=evidence_id,
        source_type=source_type,  # type: ignore[arg-type]
        title=title,
        authors=["Alice"],
        year=2024,
        url="https://example.org/p",
        doi="10.1234/demo",
        quoted_text=quote,
        summary="summary",
        relevance_score=relevance,
        reliability_note=reliability_note,
    )


def test_builder_keeps_quoted_text_unlike_catalog():
    """验收：Bundle / Agent 上下文保留 quoted_text。"""
    long_quote = "This quoted text must survive bundle construction."
    result = build_evidence_bundle(
        [_card("EV001", quote=long_quote)],
        bundle_id="B-KEEP-QUOTE",
        token_budget=8000,
    )
    assert result.kept_quoted_text is True
    assert result.bundle.evidences[0].quoted_text == long_quote
    context = bundle_to_agent_context(result.bundle)
    assert context[0]["quoted_text"] == long_quote
    assert "quoted_text" in context[0]


def test_builder_preserves_locator_authors_year_hash():
    """验收：locator / 作者 / 年份 / content_hash 进入受控上下文。"""
    result = build_evidence_bundle(
        [_card("EV002")],
        bundle_id="B-FIELDS",
        domain="oncology",
    )
    card = result.bundle.evidences[0]
    assert card.locator.get("page") == 3
    assert card.locator.get("section") == "Results"
    assert card.authors == ["Alice"]
    assert card.year == 2024
    assert card.source_type == "paper"
    assert card.content_hash == compute_content_hash(card.quoted_text)
    assert card.domain == "oncology"


def test_builder_records_truncation_reason_and_drops():
    """验收：超预算时截断并记录 truncation_reason / dropped ids。"""
    cards = [
        _card(
            f"EV{i:03d}",
            quote=("word " * 200) + f"marker-{i}",
            relevance=1.0 - i * 0.01,
        )
        for i in range(6)
    ]
    result = build_evidence_bundle(
        cards,
        bundle_id="B-TRUNC",
        token_budget=120,
    )
    assert result.bundle.truncated is True
    assert result.bundle.truncation_reason is not None
    assert "token_budget=120" in result.bundle.truncation_reason
    assert result.dropped_evidence_ids
    assert len(result.bundle.evidences) < len(cards)
    # 保留卡仍有 quote
    assert all(c.quoted_text.strip() for c in result.bundle.evidences)


def test_builder_reports_missing_fields():
    """验收：缺失作者/年份/定位时写入 missing_fields。"""
    card = EvidenceCard(
        id="EV-MISS",
        source_type="arxiv",
        title="Sparse meta",
        authors=[],
        year=None,
        url=None,
        doi=None,
        quoted_text="Body quote remains.",
        summary="s",
        relevance_score=0.5,
        reliability_note="",
    )
    result = build_evidence_bundle(
        [card],
        bundle_id="B-MISS",
    )
    missing = result.missing_fields["EV-MISS"]
    assert "authors" in missing
    assert "year" in missing
    assert "doi_or_url" in missing
    assert "locator" in missing


def test_builder_with_claim_specs():
    """绿灯：按 ClaimSpec 生成 supports 链接。"""
    result = build_evidence_bundle(
        [_card("EV010"), _card("EV011", quote="Second quote body.")],
        bundle_id="B-CLAIMS",
        claims=[
            ClaimSpec(
                claim_id="CLAIM-1",
                evidence_ids=["EV010"],
                relation="supports",
                claim_domain="oncology",
                confidence=0.8,
            )
        ],
        domain="oncology",
    )
    assert len(result.bundle.links) == 1
    assert result.bundle.links[0].claim_id == "CLAIM-1"
    assert result.bundle.links[0].evidence_id == "EV010"


def test_booklet_maps_to_question_booklet_pending():
    """问题册来源映射为 question_booklet，保持 pending。"""
    result = build_evidence_bundle(
        [
            _card(
                "EV-BOOK",
                source_type="booklet",
                quote="Booklet question context text.",
                title="Q028 title",
            )
        ],
        bundle_id="B-BOOK",
    )
    card = result.bundle.evidences[0]
    assert card.source_type == "question_booklet"
    assert card.verification_status == "pending"


def test_estimate_token_count_nonzero():
    """辅助：token 估算对非空文本为正。"""
    assert estimate_token_count("") == 0
    assert estimate_token_count("abcd") >= 1
