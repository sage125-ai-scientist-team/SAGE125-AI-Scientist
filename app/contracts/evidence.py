"""
T01 Evidence Contract — Wave A 契约层。

本模块定义下游智能体可消费的证据契约，不替代运行时 ``EvidenceCard``。
运行时 ``_evidence_catalog`` 接入由后续任务完成；本文件只冻结字段与校验门禁。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EvidenceCardContract(BaseModel):
    """
    可追溯科学证据的契约对象（代码名：EvidenceCardContract）。

    设计约束：
    1. 标题/元数据 alone 不得支撑 established facts（不得标 ``valid``）。
    2. 必须保留原文 ``quoted_text`` 与非空 ``locator``。
    3. 未核验证据默认 ``pending``；问题册来源不得标 ``valid``。
    4. Wave A：``content_hash`` 可选，但缺失时禁止 ``verification_status=valid``。
    """

    evidence_id: str = Field(min_length=1)

    source_id: str = Field(min_length=1)

    source_type: Literal[
        "paper",
        "dataset",
        "experiment",
        "web",
        "contract",
        "specification",
        "test_fixture",
        "question_booklet",
    ]

    title: str = Field(min_length=1)

    quoted_text: str = Field(min_length=1)

    locator: dict

    authors: list[str] = Field(default_factory=list)

    year: Optional[int] = None

    doi: Optional[str] = None

    url: Optional[str] = None

    content_hash: Optional[str] = None

    domain: Optional[str] = None

    verification_status: Literal[
        "valid",
        "invalid",
        "pending",
        "rejected",
    ] = "pending"

    @field_validator("quoted_text")
    @classmethod
    def validate_quote(cls, value: str) -> str:
        """
        校验原文摘录非空。

        参数：
            value: 待校验的 ``quoted_text``。

        返回：
            去首尾空白后仍非空的原文。

        异常：
            ValueError: 仅空白字符串。
        """
        if not value.strip():
            raise ValueError("quoted_text cannot be empty")
        return value

    @field_validator("locator")
    @classmethod
    def validate_locator(cls, value: dict) -> dict:
        """
        校验定位信息非空。

        参数：
            value: 页码/章节等 locator 字典。

        返回：
            非空 locator。

        异常：
            ValueError: 空字典。
        """
        if not value:
            raise ValueError("locator cannot be empty")
        return value

    @model_validator(mode="after")
    def enforce_provenance_gates(self) -> EvidenceCardContract:
        """
        强制 Wave A 出处门禁。

        规则：
        - title-only（quote 与 title 相同）不得标 ``valid``；
        - 问题册来源不得标 ``valid``；
        - 缺少 ``content_hash`` 时不得标 ``valid``。

        返回：
            通过门禁的自身实例。

        异常：
            ValueError: 违反任一出处门禁。
        """
        if self.verification_status != "valid":
            return self

        if self.quoted_text.strip().lower() == self.title.strip().lower():
            raise ValueError(
                "title-only evidence cannot have verification_status=valid"
            )

        if self._is_booklet_source():
            raise ValueError(
                "question booklet evidence cannot have verification_status=valid"
            )

        if not (self.content_hash and self.content_hash.strip()):
            raise ValueError(
                "content_hash is required when verification_status=valid"
            )

        return self

    def _is_booklet_source(self) -> bool:
        """
        判断证据是否来自问题册（booklet）。

        返回：
            True 表示 source_type / source_id / locator 指向 booklet。
        """
        if self.source_type == "question_booklet":
            return True
        if "booklet" in self.source_id.lower():
            return True
        locator_source = str(self.locator.get("source", "")).lower()
        return locator_source == "booklet"


class ClaimEvidenceLink(BaseModel):
    """
    事实声明与证据对象之间的契约绑定。

    ``evidence_id`` 在 Bundle 构造时必须落在已声明 evidences 集合内。
    跨域 ``supports`` 在两侧 domain 均给出且不一致时必须拒绝。
    """

    claim_id: str = Field(min_length=1)

    evidence_id: str = Field(min_length=1)

    relation: Literal[
        "supports",
        "contradicts",
        "context",
    ]

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    claim_domain: Optional[str] = None

    validation_status: Literal[
        "valid",
        "invalid",
        "pending",
    ] = "pending"

    @field_validator("evidence_id")
    @classmethod
    def validate_link_evidence_id(cls, value: str) -> str:
        """
        校验链接侧 evidence_id 非空。

        参数：
            value: 链接引用的 evidence_id。

        返回：
            非空白 evidence_id。

        异常：
            ValueError: 仅空白字符串。
        """
        if not value.strip():
            raise ValueError("evidence_id cannot be empty")
        return value


class EvidenceBundle(BaseModel):
    """
    受控证据包：供下游 Agent 消费的 evidences + links + token 预算。

    构造时强制：
    1. evidences / links 非空；
    2. 每个 ``link.evidence_id`` 必须存在于 evidences；
    3. ``supports`` 且两侧 domain 均给出但不一致 → 拒绝（跨域外推红灯）。
    """

    bundle_id: str = Field(min_length=1)

    evidences: list[EvidenceCardContract]

    links: list[ClaimEvidenceLink]

    token_budget: int = 8000

    truncated: bool = False

    truncation_reason: Optional[str] = None

    @field_validator("evidences")
    @classmethod
    def validate_evidences(
        cls,
        value: list[EvidenceCardContract],
    ) -> list[EvidenceCardContract]:
        """
        校验证据列表非空且 evidence_id 唯一。

        参数：
            value: EvidenceCardContract 列表。

        返回：
            通过校验的列表。

        异常：
            ValueError: 空列表或重复 evidence_id。
        """
        if not value:
            raise ValueError("EvidenceBundle requires evidences")
        ids = [card.evidence_id for card in value]
        if len(ids) != len(set(ids)):
            raise ValueError("EvidenceBundle evidence_id values must be unique")
        return value

    @field_validator("links")
    @classmethod
    def validate_links(
        cls,
        value: list[ClaimEvidenceLink],
    ) -> list[ClaimEvidenceLink]:
        """
        校验链接列表非空。

        参数：
            value: ClaimEvidenceLink 列表。

        返回：
            非空链接列表。

        异常：
            ValueError: 空列表。
        """
        if not value:
            raise ValueError("EvidenceBundle requires links")
        return value

    @model_validator(mode="after")
    def enforce_link_integrity(self) -> EvidenceBundle:
        """
        Bundle 级完整性：未知 evidence_id 与跨域 supports 一律拒绝。

        返回：
            通过校验的 Bundle。

        异常：
            ValueError: 悬挂引用或跨域 supports。
        """
        evidence_by_id = {card.evidence_id: card for card in self.evidences}
        known_ids = set(evidence_by_id)

        for link in self.links:
            if link.evidence_id not in known_ids:
                raise ValueError(
                    f"Unknown evidence_id in bundle links: {link.evidence_id}"
                )

            card = evidence_by_id[link.evidence_id]
            if (
                link.relation == "supports"
                and link.claim_domain
                and card.domain
                and link.claim_domain.strip().lower()
                != card.domain.strip().lower()
            ):
                raise ValueError(
                    "cross-domain supports relation requires additional validation: "
                    f"claim_domain={link.claim_domain!r} evidence_domain={card.domain!r}"
                )

        return self


def validate_evidence_card(
    card: EvidenceCardContract,
) -> bool:
    """
    二次校验证据卡片最小出处要求（quote + locator）。

    参数：
        card: 已构造的 EvidenceCardContract。

    返回：
        True 表示通过。

    异常：
        ValueError: quote 或 locator 缺失。
    """
    if not card.quoted_text:
        raise ValueError("Evidence quote is missing")

    if not card.locator:
        raise ValueError("Evidence locator is missing")

    return True


def validate_evidence_link(
    link: ClaimEvidenceLink,
    existing_evidence_ids: list[str],
) -> bool:
    """
    校验单条 claim-evidence 链接的引用完整性。

    参数：
        link: ClaimEvidenceLink 实例。
        existing_evidence_ids: 已知 evidence_id 列表。

    返回：
        True 表示引用存在。

    异常：
        ValueError: evidence_id 不在已知集合中。
    """
    if link.evidence_id not in existing_evidence_ids:
        raise ValueError(
            f"Unknown evidence_id: {link.evidence_id}"
        )

    return True
