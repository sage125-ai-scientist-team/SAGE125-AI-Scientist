"""
T01 ↔ T02/T03 联调桥 — Wave B（08/03）。

在不修改 ``pipeline.py`` / T02 / T03 owner 代码的前提下：
1. 将 ``EvidenceBundle`` 投影为 T03 ``ValidationContext.evidence_cards``；
2. 将 Bundle 指纹写入 T02 ``PlanVersion``（V1/V2 版本记录）；
3. 对缺证据 / 冲突证据产出可挂到 T03 ``GateFinding`` 的预检结果。

完整 Validator 业务规则仍由 T03 ``ValidationService`` 实现；本模块只保证
证据字段不在跨模块交接时丢失，并提供可复现 E2E 夹具。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.contracts.revision import (
    PlanVersion,
    RevisionContext,
    RevisionState,
    serialize_revision_state,
    deserialize_revision_state,
)
from app.contracts.validation import (
    GateFinding,
    GateResult,
    Severity,
    ValidationContext,
)
from app.evidence.support_checker import (
    ClaimText,
    SupportErrorCode,
    check_claim_evidence_support,
)

BUNDLE_FINGERPRINT_KEY = "t01_evidence_bundle_sha256"
BUNDLE_EVIDENCE_IDS_KEY = "t01_evidence_ids"
BUNDLE_PAYLOAD_KEY = "evidence_bundle"


def _canonical_json(value: Any) -> str:
    """确定性 JSON，用于指纹。"""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def evidence_card_to_validation_wire(
    card: EvidenceCardContract,
    *,
    run_id: str,
    version_id: str,
    question_id: str,
) -> dict[str, Any]:
    """
    将 T01 契约卡投影为 T03 ValidationContext 可接受的 evidence_cards 元素。

    T03 示例使用 ``id`` 字段；同时保留 T01 全量 provenance，防止字段丢失。

    参数：
        card: EvidenceCardContract。
        run_id / version_id / question_id: 可选身份字段，满足 T03 校验。

    返回：
        wire dict。
    """
    return {
        "id": card.evidence_id,
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
        "run_id": run_id,
        "version_id": version_id,
        "question_id": question_id,
    }


def bundle_fingerprint(bundle: EvidenceBundle) -> str:
    """
    计算 EvidenceBundle 内容指纹（sha256 hex）。

    参数：
        bundle: EvidenceBundle。

    返回：
        64 位小写 hex。
    """
    payload = bundle.model_dump(mode="json")
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return digest


def attach_bundle_to_plan_version(
    plan: PlanVersion,
    bundle: EvidenceBundle,
) -> PlanVersion:
    """
    把 Bundle 指纹与证据 ID 列表写入 PlanVersion（不破坏 T02 契约）。

    - ``prompt_fingerprints[t01_evidence_bundle_sha256]``
    - ``hypothesis_generation[evidence_bundle]`` 存放可审计摘要（非全文滥用）

    参数：
        plan: T02 PlanVersion。
        bundle: T01 EvidenceBundle。

    返回：
        更新后的 PlanVersion 拷贝。
    """
    fp = bundle_fingerprint(bundle)
    fingerprints = dict(plan.prompt_fingerprints)
    fingerprints[BUNDLE_FINGERPRINT_KEY] = fp
    fingerprints[BUNDLE_EVIDENCE_IDS_KEY] = ",".join(
        card.evidence_id for card in bundle.evidences
    )

    hypothesis = dict(plan.hypothesis_generation)
    hypothesis[BUNDLE_PAYLOAD_KEY] = {
        "bundle_id": bundle.bundle_id,
        "fingerprint": fp,
        "evidence_ids": [card.evidence_id for card in bundle.evidences],
        "link_count": len(bundle.links),
        "token_budget": bundle.token_budget,
        "truncated": bundle.truncated,
        "truncation_reason": bundle.truncation_reason,
    }
    return plan.model_copy(
        update={
            "prompt_fingerprints": fingerprints,
            "hypothesis_generation": hypothesis,
        }
    )


def build_validation_context_from_bundle(
    *,
    bundle: EvidenceBundle,
    plan: PlanVersion,
    question_id: str,
    question_text: str,
    validation_id: str,
    domain: str = "synthetic",
    correlation_id: str | None = None,
) -> ValidationContext:
    """
    用 T01 Bundle + T02 PlanVersion 组装 T03 ValidationContext。

    参数：
        bundle: 证据包。
        plan: 计划版本（应已 attach bundle）。
        question_id / question_text: 问题身份与正文（须一致）。
        validation_id: 校验会话 ID。
        domain: 问题领域。
        correlation_id: 可选关联 ID。

    返回：
        ValidationContext。
    """
    cards = [
        evidence_card_to_validation_wire(
            card,
            run_id=plan.run_id,
            version_id=plan.version_id,
            question_id=question_id,
        )
        for card in bundle.evidences
    ]
    return ValidationContext.model_validate(
        {
            "schema_version": 1,
            "validation_id": validation_id,
            "run_id": plan.run_id,
            "version_id": plan.version_id,
            "research_plan": {
                "question_id": question_id,
                "input_question": question_text,
                "actual_execution": False,
                "run_id": plan.run_id,
                "version_id": plan.version_id,
                "references": [{"id": card.evidence_id} for card in bundle.evidences],
                "evidence_bundle_id": bundle.bundle_id,
                "evidence_bundle_fingerprint": plan.prompt_fingerprints.get(
                    BUNDLE_FINGERPRINT_KEY
                ),
            },
            "evidence_cards": cards,
            "agent_trace": [
                {
                    "run_id": plan.run_id,
                    "agent_name": "t01_evidence_bridge",
                    "status": "success",
                    "version_id": plan.version_id,
                }
            ],
            "execution_metadata": {
                "actual_execution": False,
                "mode": "mock",
                "run_id": plan.run_id,
                "version_id": plan.version_id,
            },
            "question_item": {
                "id": question_id,
                "question": question_text,
                "domain": domain,
            },
            "revision_issues": [],
            "human_feedback": None,
            "correlation_id": correlation_id,
        }
    )


def find_conflict_claim_ids(links: Sequence[ClaimEvidenceLink]) -> list[str]:
    """
    找出同时存在 supports 与 contradicts 的 claim_id（冲突证据）。

    参数：
        links: ClaimEvidenceLink 列表。

    返回：
        冲突 claim_id 列表（排序）。
    """
    by_claim: dict[str, set[str]] = {}
    for link in links:
        by_claim.setdefault(link.claim_id, set()).add(link.relation)
    return sorted(
        claim_id
        for claim_id, relations in by_claim.items()
        if "supports" in relations and "contradicts" in relations
    )


@dataclass
class EvidenceIntegrationPrecheck:
    """
    T01 侧预检结果，可映射为 T03 GateResult。

    属性：
        missing_blocked: 是否存在未知证据 ID。
        conflict_claim_ids: 冲突声明。
        support_codes: 支持检查错误码。
        gate: 对应的 GateResult。
        field_loss: 投影后丢失的关键字段名（应为空）。
    """

    missing_blocked: bool
    conflict_claim_ids: list[str]
    support_codes: list[str]
    gate: GateResult
    field_loss: list[str] = field(default_factory=list)


def precheck_bundle_for_validation(
    *,
    bundle: EvidenceBundle,
    claims: Sequence[ClaimText],
    context: ValidationContext,
) -> EvidenceIntegrationPrecheck:
    """
    对 Bundle 做缺证据 / 冲突证据预检，并核对 ValidationContext 无字段丢失。

    参数：
        bundle: EvidenceBundle。
        claims: 声明文本。
        context: 已构建的 ValidationContext。

    返回：
        EvidenceIntegrationPrecheck。
    """
    support = check_claim_evidence_support(claims, bundle.evidences)
    conflicts = find_conflict_claim_ids(bundle.links)

    findings: list[GateFinding] = []
    if support.blocked and SupportErrorCode.UNKNOWN_EVIDENCE_ID.value in support.error_codes:
        findings.append(
            GateFinding(
                code="T01_MISSING_EVIDENCE",
                message="claim references evidence_id absent from EvidenceBundle",
                severity=Severity.P1,
                path="evidence_cards",
                source_ids=tuple(
                    f.evidence_id
                    for f in support.findings
                    if f.evidence_id and f.code == SupportErrorCode.UNKNOWN_EVIDENCE_ID
                ),
            )
        )
    if SupportErrorCode.FAKE_BOOKLET_EVIDENCE_ID.value in support.error_codes:
        findings.append(
            GateFinding(
                code="T01_FAKE_BOOKLET_EVIDENCE_ID",
                message="fabricated booklet_excerpt_Q* evidence_id is forbidden",
                severity=Severity.P0,
                path="evidence_cards",
            )
        )
    for claim_id in conflicts:
        findings.append(
            GateFinding(
                code="T01_CONFLICT_EVIDENCE",
                message=(
                    f"claim {claim_id} has both supports and contradicts links; "
                    "must not be silently resolved as established fact"
                ),
                severity=Severity.P1,
                path=f"links[{claim_id}]",
                source_ids=(claim_id,),
            )
        )

    # 字段丢失检查：Bundle 中每张卡的 quoted_text 必须出现在 ValidationContext。
    wire_by_id = {
        str(card.get("id") or card.get("evidence_id")): card
        for card in context.evidence_cards
    }
    field_loss: list[str] = []
    for card in bundle.evidences:
        wire = wire_by_id.get(card.evidence_id)
        if wire is None:
            field_loss.append(f"{card.evidence_id}:missing_card")
            continue
        for key in ("quoted_text", "locator", "source_type", "content_hash"):
            if key not in wire or wire.get(key) in (None, "", {}):
                field_loss.append(f"{card.evidence_id}:{key}")

    if field_loss:
        findings.append(
            GateFinding(
                code="T01_EVIDENCE_FIELD_LOSS",
                message="evidence provenance fields lost in T03 projection",
                severity=Severity.P0,
                path="evidence_cards",
                source_ids=tuple(field_loss),
            )
        )

    blocking = [f for f in findings if f.is_blocking]
    severity = Severity.P0
    if blocking:
        severity = min((f.severity for f in blocking), key=lambda s: s.rank)
    elif findings:
        severity = min((f.severity for f in findings), key=lambda s: s.rank)
    else:
        severity = Severity.P3

    gate = GateResult(
        gate_id="t01_evidence_integration_precheck",
        passed=not blocking,
        severity=severity,
        findings=tuple(findings),
        errors=tuple(f.code for f in blocking),
        warnings=tuple(
            f.code for f in findings if not f.is_blocking
        ),
        score=1.0 if not findings else 0.0,
    )
    return EvidenceIntegrationPrecheck(
        missing_blocked=any(
            code
            in {
                SupportErrorCode.UNKNOWN_EVIDENCE_ID.value,
                SupportErrorCode.FAKE_BOOKLET_EVIDENCE_ID.value,
            }
            for code in support.error_codes
        ),
        conflict_claim_ids=conflicts,
        support_codes=support.error_codes,
        gate=gate,
        field_loss=field_loss,
    )


def build_v1_v2_revision_with_bundle(
    *,
    run_id: str,
    bundle_v1: EvidenceBundle,
    bundle_v2: EvidenceBundle,
) -> RevisionState:
    """
    构建携带 EvidenceBundle 指纹的 V1→V2 RevisionState。

    参数：
        run_id: 运行 ID。
        bundle_v1 / bundle_v2: 两版证据包。

    返回：
        RevisionState。
    """
    context = RevisionContext(run_id=run_id, revision_iteration=1)
    v1 = attach_bundle_to_plan_version(
        PlanVersion.create(
            run_id=run_id,
            version_number=1,
            revision_iteration=1,
            hypothesis_generation={"stage": "v1"},
        ),
        bundle_v1,
    )
    v2 = attach_bundle_to_plan_version(
        PlanVersion.create(
            run_id=run_id,
            version_number=2,
            revision_iteration=2,
            parent_version_id=v1.version_id,
            hypothesis_generation={"stage": "v2"},
        ),
        bundle_v2,
    )
    return RevisionState(
        context=context,
        versions=[v1, v2],
        validation_status="draft",
    )


def round_trip_revision_state(state: RevisionState) -> RevisionState:
    """
    RevisionState 序列化往返，用于验证证据指纹不丢失。

    参数：
        state: RevisionState。

    返回：
        反序列化后的 RevisionState。
    """
    payload = serialize_revision_state(state)
    return deserialize_revision_state(payload)
