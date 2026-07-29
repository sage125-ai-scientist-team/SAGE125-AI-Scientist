"""
T01 Evidence Contract 红灯 / 绿灯测试。

覆盖 Wave A：字段可追溯、未知 ID、title-only、问题册、跨域外推、Bundle 完整性。
"""

import pytest
from pydantic import ValidationError

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
    validate_evidence_card,
    validate_evidence_link,
)


def _valid_card(**overrides) -> EvidenceCardContract:
    """
    构造一张默认合法的证据契约卡片。

    参数：
        **overrides: 覆盖默认字段。

    返回：
        EvidenceCardContract 实例。
    """
    data = {
        "evidence_id": "EV001",
        "source_id": "paper001",
        "source_type": "paper",
        "title": "Scientific paper",
        "quoted_text": "Original evidence text",
        "locator": {"page": 3, "section": "Results"},
        "domain": "oncology",
        "content_hash": "sha256:demo",
    }
    data.update(overrides)
    return EvidenceCardContract(**data)


def test_evidence_card_contains_traceable_fields():
    """绿灯：证据卡片包含可追溯字段。"""
    card = _valid_card()
    assert card.evidence_id == "EV001"
    assert card.quoted_text == "Original evidence text"
    assert card.locator["page"] == 3
    assert validate_evidence_card(card) is True


def test_title_only_evidence_remains_pending():
    """title-only 默认为 pending，不得伪装为已核验。"""
    card = EvidenceCardContract(
        evidence_id="EV002",
        source_id="paper002",
        source_type="paper",
        title="Paper title only",
        quoted_text="Paper title only",
        locator={"section": "unknown"},
    )
    assert card.verification_status == "pending"


def test_title_only_evidence_cannot_be_valid():
    """红灯：title-only 不得 verification_status=valid。"""
    with pytest.raises(ValidationError):
        EvidenceCardContract(
            evidence_id="EV002",
            source_id="paper002",
            source_type="paper",
            title="Paper title only",
            quoted_text="Paper title only",
            locator={"section": "unknown"},
            content_hash="sha256:x",
            verification_status="valid",
        )


def test_booklet_excerpt_cannot_be_verified_evidence():
    """问题册证据默认为 pending。"""
    card = EvidenceCardContract(
        evidence_id="EV_BOOKLET",
        source_id="booklet",
        source_type="web",
        title="Question booklet",
        quoted_text="Question description",
        locator={"source": "booklet"},
    )
    assert card.verification_status == "pending"


def test_booklet_excerpt_cannot_be_valid():
    """红灯：问题册来源不得 verification_status=valid。"""
    with pytest.raises(ValidationError):
        EvidenceCardContract(
            evidence_id="EV_BOOKLET",
            source_id="booklet",
            source_type="question_booklet",
            title="Question booklet",
            quoted_text="Question description from booklet",
            locator={"source": "booklet"},
            content_hash="sha256:x",
            verification_status="valid",
        )


def test_evidence_bundle_tracks_token_budget():
    """绿灯：Bundle 记录 token 预算。"""
    card = _valid_card()
    link = ClaimEvidenceLink(
        claim_id="CLAIM001",
        evidence_id="EV001",
        relation="supports",
        claim_domain="oncology",
    )
    bundle = EvidenceBundle(
        bundle_id="BUNDLE001",
        evidences=[card],
        links=[link],
        token_budget=8000,
    )
    assert bundle.token_budget == 8000


def test_missing_quote_should_fail():
    """红灯：空 quoted_text 构造失败。"""
    with pytest.raises(ValidationError):
        EvidenceCardContract(
            evidence_id="EV_BAD_001",
            source_id="paper001",
            source_type="paper",
            title="Missing quote",
            quoted_text="",
            locator={"page": 1},
        )


def test_missing_locator_should_fail():
    """红灯：空 locator 构造失败。"""
    with pytest.raises(ValidationError):
        EvidenceCardContract(
            evidence_id="EV_BAD_002",
            source_id="paper002",
            source_type="paper",
            title="Missing locator",
            quoted_text="Some quote",
            locator={},
        )


def test_empty_evidence_id_should_fail():
    """红灯：空 evidence_id 构造失败。"""
    with pytest.raises(ValidationError):
        EvidenceCardContract(
            evidence_id="",
            source_id="paper003",
            source_type="paper",
            title="Empty id",
            quoted_text="Valid quote",
            locator={"page": 1},
        )


def test_unknown_evidence_id_should_fail():
    """红灯：validate_evidence_link 拒绝未知 ID。"""
    link = ClaimEvidenceLink(
        claim_id="CLAIM_BAD",
        evidence_id="UNKNOWN_ID",
        relation="supports",
    )
    with pytest.raises(ValueError):
        validate_evidence_link(link, ["EV001"])


def test_bundle_rejects_unknown_evidence_link():
    """红灯：Bundle 构造时拒绝悬挂 evidence_id（队长 P1 阻断项）。"""
    card = _valid_card()
    link = ClaimEvidenceLink(
        claim_id="CLAIM_BAD",
        evidence_id="UNKNOWN_ID",
        relation="supports",
    )
    with pytest.raises(ValidationError):
        EvidenceBundle(
            bundle_id="BUNDLE_BAD",
            evidences=[card],
            links=[link],
        )


def test_cross_domain_supports_should_fail():
    """红灯：跨域 supports 需要额外核验，契约层直接拒绝。"""
    card = _valid_card(domain="oncology")
    link = ClaimEvidenceLink(
        claim_id="CLAIM_XD",
        evidence_id="EV001",
        relation="supports",
        claim_domain="climate",
    )
    with pytest.raises(ValidationError):
        EvidenceBundle(
            bundle_id="BUNDLE_XD",
            evidences=[card],
            links=[link],
        )


def test_valid_without_content_hash_should_fail():
    """红灯：verification_status=valid 时 content_hash 必填。"""
    with pytest.raises(ValidationError):
        EvidenceCardContract(
            evidence_id="EV_HASH",
            source_id="paper001",
            source_type="paper",
            title="Hashed paper",
            quoted_text="Body quote distinct from title",
            locator={"page": 2},
            verification_status="valid",
            content_hash=None,
        )


def test_validate_existing_evidence_link():
    """绿灯：已知 evidence_id 链接通过。"""
    link = ClaimEvidenceLink(
        claim_id="CLAIM001",
        evidence_id="EV001",
        relation="supports",
    )
    assert validate_evidence_link(link, ["EV001"]) is True


def test_evidence_contract_serialization_round_trip():
    """绿灯：契约序列化 / 反序列化 round-trip。"""
    card = _valid_card(verification_status="pending")
    link = ClaimEvidenceLink(
        claim_id="CLAIM001",
        evidence_id="EV001",
        relation="supports",
        claim_domain="oncology",
    )
    bundle = EvidenceBundle(
        bundle_id="BUNDLE001",
        evidences=[card],
        links=[link],
        token_budget=8000,
        truncated=False,
    )
    restored = EvidenceBundle.model_validate(bundle.model_dump())
    assert restored.bundle_id == bundle.bundle_id
    assert restored.evidences[0].evidence_id == "EV001"
    assert restored.links[0].relation == "supports"
    assert restored.token_budget == 8000
