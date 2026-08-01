"""
T01 Wave B（07/31）：支持检查器红灯夹具。

至少 5 类坏引用被阻断或降级；不确定项不得伪装 allow。
不修改 Wave A 契约文件。
"""

from app.contracts.evidence import EvidenceCardContract
from app.evidence.support_checker import (
    ClaimText,
    SupportDecision,
    SupportErrorCode,
    check_claim_evidence_support,
    is_booklet_evidence,
    is_doi_only_text,
    is_metadata_only,
)


def _card(**overrides) -> EvidenceCardContract:
    """
    构造默认可用的契约证据卡。

    参数：
        **overrides: 字段覆盖。

    返回：
        EvidenceCardContract。
    """
    data = {
        "evidence_id": "EV-OK",
        "source_id": "paper-1",
        "source_type": "paper",
        "title": "EGFR inhibition improves response",
        "quoted_text": "EGFR inhibition improves response in lung adenocarcinoma samples.",
        "locator": {"page": 3, "section": "Results"},
        "authors": ["A"],
        "year": 2024,
        "content_hash": "sha256:demo",
        "domain": "oncology",
        "verification_status": "pending",
    }
    data.update(overrides)
    return EvidenceCardContract(**data)


def test_block_unknown_evidence_id():
    """坏引用 1：未知 evidence_id → BLOCK。"""
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C1",
                text="EGFR inhibition improves response",
                evidence_ids=["MISSING"],
                domain="oncology",
            )
        ],
        [_card()],
    )
    assert result.blocked is True
    assert SupportErrorCode.UNKNOWN_EVIDENCE_ID.value in result.error_codes
    assert result.allowed_links == []


def test_block_metadata_only_supports():
    """坏引用 2：title-only / metadata-only → BLOCK。"""
    card = _card(
        evidence_id="EV-META",
        title="Paper title only",
        quoted_text="Paper title only",
    )
    assert is_metadata_only(card) is True
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C2",
                text="Paper title only proves a clinical fact",
                evidence_ids=["EV-META"],
                domain="oncology",
            )
        ],
        [card],
    )
    assert result.blocked is True
    assert SupportErrorCode.METADATA_ONLY.value in result.error_codes


def test_block_doi_only_quoted_text_supports():
    """
    队长 P0 / T01-B-004：DOI-only quote 不得支撑事实。

    probe: quoted_text='10.1234/x.y.z' → metadata-only → BLOCK，无 allowed_links。
    """
    assert is_doi_only_text("10.1234/x.y.z") is True
    assert is_doi_only_text("https://doi.org/10.1234/x.y.z") is True
    assert is_doi_only_text("doi:10.1234/x.y.z") is True
    assert is_doi_only_text("EGFR inhibition improves response in cohort.") is False

    card = _card(
        evidence_id="EV-DOI-ONLY",
        title="Some paper title",
        quoted_text="10.1234/x.y.z",
        doi="10.1234/x.y.z",
    )
    assert is_metadata_only(card) is True
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C-DOI",
                text="10.1234/x.y.z proves a clinical fact by identifier alone",
                evidence_ids=["EV-DOI-ONLY"],
                domain="oncology",
                relation="supports",
            )
        ],
        [card],
    )
    assert result.blocked is True
    assert SupportErrorCode.METADATA_ONLY.value in result.error_codes
    assert result.allowed_links == []


def test_block_url_only_quoted_text_supports():
    """纯 URL quote（无正文）→ metadata-only BLOCK。"""
    card = _card(
        evidence_id="EV-URL-ONLY",
        title="Landing page",
        quoted_text="https://example.org/paper/123",
        url="https://example.org/paper/123",
    )
    assert is_metadata_only(card) is True
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C-URL",
                text="https://example.org/paper/123 alone establishes the fact",
                evidence_ids=["EV-URL-ONLY"],
                domain="oncology",
            )
        ],
        [card],
    )
    assert result.blocked is True
    assert SupportErrorCode.METADATA_ONLY.value in result.error_codes


def test_booklet_rename_still_excluded():
    """跨 PR：source_type 改名但仍含 booklet 线索 → 仍排除。"""
    card = _card(
        evidence_id="renamed_booklet_excerpt_Q028",
        source_id="corpus-question-pack-01",
        source_type="dataset",
        title="Booklet question pack excerpt",
        quoted_text="Broad cancer question text from the student booklet.",
        locator={"collection": "question_booklet_v2"},
        domain="oncology",
    )
    assert is_booklet_evidence(card) is True
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C-BOOK-RENAME",
                text="Broad cancer question text from the student booklet proves therapy",
                evidence_ids=["renamed_booklet_excerpt_Q028"],
                domain="oncology",
            )
        ],
        [card],
    )
    assert result.blocked is True
    assert SupportErrorCode.BOOKLET_EXCLUDED.value in result.error_codes


def test_block_booklet_supports():
    """坏引用 3：问题册证据支撑事实 → BLOCK。"""
    card = _card(
        evidence_id="EV-BOOK",
        source_id="booklet-Q028",
        source_type="question_booklet",
        title="Question text",
        quoted_text="Question booklet excerpt about cancer broadly.",
        locator={"source": "booklet"},
        domain="oncology",
    )
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C3",
                text="cancer broadly is solved by booklet text",
                evidence_ids=["EV-BOOK"],
                domain="oncology",
            )
        ],
        [card],
    )
    assert result.blocked is True
    assert SupportErrorCode.BOOKLET_EXCLUDED.value in result.error_codes


def test_degrade_cross_domain_supports():
    """坏引用 4：跨域 supports → DEGRADE（不伪装 allow）。"""
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C4",
                text="EGFR inhibition improves response",
                evidence_ids=["EV-OK"],
                domain="climate",
            )
        ],
        [_card(domain="oncology")],
    )
    assert result.blocked is False
    assert SupportErrorCode.CROSS_DOMAIN.value in result.error_codes
    assert "C4" in result.degraded_claim_ids
    assert result.allowed_links == []
    assert any(f.decision == SupportDecision.DEGRADE for f in result.findings)


def test_degrade_non_entailment():
    """坏引用 5：声明与摘录无重叠 → DEGRADE。"""
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C5",
                text="Ocean salinity drives monsoon variability",
                evidence_ids=["EV-OK"],
                domain="oncology",
            )
        ],
        [_card()],
    )
    assert result.blocked is False
    assert SupportErrorCode.NON_ENTAILMENT.value in result.error_codes
    assert "C5" in result.degraded_claim_ids
    assert result.allowed_links == []


def test_block_unsupported_supports_claim():
    """坏引用 6：supports 无任何证据绑定 → BLOCK。"""
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C6",
                text="EGFR inhibition improves response",
                evidence_ids=[],
                domain="oncology",
                relation="supports",
            )
        ],
        [_card()],
    )
    assert result.blocked is True
    assert SupportErrorCode.UNSUPPORTED_CLAIM.value in result.error_codes


def test_allow_supported_claim():
    """绿灯：声明被原文词法支撑 → ALLOW。"""
    result = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="C-OK",
                text="EGFR inhibition improves response in adenocarcinoma",
                evidence_ids=["EV-OK"],
                domain="oncology",
            )
        ],
        [_card()],
    )
    assert result.blocked is False
    assert result.degraded_claim_ids == []
    assert len(result.allowed_links) == 1
    assert result.allowed_links[0].evidence_id == "EV-OK"
