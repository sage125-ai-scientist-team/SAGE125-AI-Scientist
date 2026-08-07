"""
T01 Wave C 质量门 — 冲突/反例证据与撤稿/来源状态占位。

约束：
1. 不得修改 ``app/workflow/pipeline.py``；
2. 不得改写已冻结 Wave A ``app/contracts/evidence.py`` 字段；
3. 冲突证据两侧必须保留并显式标记，禁止静默覆盖/丢弃任一侧；
4. 撤稿/来源生命周期以占位元数据叠加，不伪装为已核验正式状态。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Sequence

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.evidence.integration_bridge import find_conflict_claim_ids


class SourceLifecycleStatus(str, Enum):
    """
    来源生命周期占位状态（Wave C）。

    ``PLACEHOLDER`` 表示尚未核验；``RETRACTED`` / ``WITHDRAWN`` 禁止支撑 established facts。
    """

    ACTIVE = "active"
    RETRACTED = "retracted"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"
    PLACEHOLDER = "placeholder"


class ConflictDisposition(str, Enum):
    """
    冲突声明处置方式。

    ``KEEP_BOTH_FLAGGED``：两侧证据均保留并标冲突（默认，禁止静默覆盖）。
    ``BLOCK_CLAIM``：声明级阻断，仍保留全部证据 ID 供审计。
    """

    KEEP_BOTH_FLAGGED = "keep_both_flagged"
    BLOCK_CLAIM = "block_claim"


@dataclass(frozen=True)
class EvidenceSourceStatus:
    """
    单条证据的来源生命周期占位记录。

    属性：
        evidence_id: 证据 ID。
        lifecycle: 生命周期状态。
        note: 可审计说明（撤稿通知 URL、占位原因等）。
    """

    evidence_id: str
    lifecycle: SourceLifecycleStatus
    note: str = ""


@dataclass(frozen=True)
class ConflictRecord:
    """
    单条声明的冲突证据记录（两侧完整保留）。

    属性：
        claim_id: 声明 ID。
        support_evidence_ids: supports 侧证据 ID（排序）。
        contradict_evidence_ids: contradicts 侧证据 ID（排序）。
        counterexample_evidence_ids: 反例侧别名（= contradicts）。
        disposition: 处置方式。
        silently_overwritten: 恒为 False；若检测到来自上游的丢弃则置门禁失败。
    """

    claim_id: str
    support_evidence_ids: tuple[str, ...]
    contradict_evidence_ids: tuple[str, ...]
    counterexample_evidence_ids: tuple[str, ...]
    disposition: ConflictDisposition
    silently_overwritten: bool = False


@dataclass
class QualityGateReport:
    """
    Wave C 质量门报告。

    属性：
        conflict_records: 冲突记录列表。
        retracted_blocked_ids: 因撤稿/撤回被阻断的证据 ID。
        placeholder_status_ids: 仍为占位/未知的证据 ID。
        passed: 是否通过（无静默覆盖且撤稿未伪装 allow）。
        notes: 人类可读说明。
    """

    conflict_records: list[ConflictRecord] = field(default_factory=list)
    retracted_blocked_ids: list[str] = field(default_factory=list)
    placeholder_status_ids: list[str] = field(default_factory=list)
    passed: bool = True
    notes: list[str] = field(default_factory=list)


def _links_for_claim(
    links: Sequence[ClaimEvidenceLink],
    claim_id: str,
) -> list[ClaimEvidenceLink]:
    """
    取出指定声明的全部链接。

    参数：
        links: Bundle 链接列表。
        claim_id: 声明 ID。

    返回：
        匹配的 ClaimEvidenceLink 列表（保持输入相对顺序）。
    """
    return [link for link in links if link.claim_id == claim_id]


def build_conflict_record(
    *,
    claim_id: str,
    links: Sequence[ClaimEvidenceLink],
    disposition: ConflictDisposition = ConflictDisposition.KEEP_BOTH_FLAGGED,
) -> ConflictRecord:
    """
    为冲突声明构建两侧完整保留的记录。

    参数：
        claim_id: 声明 ID。
        links: 全量链接。
        disposition: 处置策略。

    返回：
        ConflictRecord；supports 与 contradicts ID 均非空时视为真冲突。
    """
    claim_links = _links_for_claim(links, claim_id)
    support_ids = sorted(
        {
            link.evidence_id
            for link in claim_links
            if link.relation == "supports"
        }
    )
    contradict_ids = sorted(
        {
            link.evidence_id
            for link in claim_links
            if link.relation == "contradicts"
        }
    )
    return ConflictRecord(
        claim_id=claim_id,
        support_evidence_ids=tuple(support_ids),
        contradict_evidence_ids=tuple(contradict_ids),
        counterexample_evidence_ids=tuple(contradict_ids),
        disposition=disposition,
        silently_overwritten=False,
    )


def detect_conflicts_preserving_both_sides(
    bundle: EvidenceBundle,
    *,
    disposition: ConflictDisposition = ConflictDisposition.KEEP_BOTH_FLAGGED,
) -> list[ConflictRecord]:
    """
    检测 supports∩contradicts 冲突，并强制两侧证据 ID 均写入记录。

    参数：
        bundle: EvidenceBundle。
        disposition: 冲突处置。

    返回：
        ConflictRecord 列表（按 claim_id 排序）。

    异常：
        ValueError: 若冲突声明任一侧为空（表示上游已静默丢弃）。
    """
    records: list[ConflictRecord] = []
    for claim_id in find_conflict_claim_ids(bundle.links):
        record = build_conflict_record(
            claim_id=claim_id,
            links=bundle.links,
            disposition=disposition,
        )
        if (
            not record.support_evidence_ids
            or not record.contradict_evidence_ids
        ):
            raise ValueError(
                f"conflict claim {claim_id!r} lost one side "
                "(silent overwrite forbidden)"
            )
        records.append(record)
    return records


def default_source_status_map(
    evidences: Sequence[EvidenceCardContract],
) -> dict[str, EvidenceSourceStatus]:
    """
    为 Bundle 内全部证据生成默认占位来源状态。

    规则：未知生命周期一律 ``PLACEHOLDER``，不得伪装 ``ACTIVE`` 已核验。

    参数：
        evidences: 证据卡列表。

    返回：
        evidence_id → EvidenceSourceStatus。
    """
    return {
        card.evidence_id: EvidenceSourceStatus(
            evidence_id=card.evidence_id,
            lifecycle=SourceLifecycleStatus.PLACEHOLDER,
            note="Wave C source lifecycle placeholder; not independently verified",
        )
        for card in evidences
    }


def apply_source_lifecycle_gate(
    *,
    evidences: Sequence[EvidenceCardContract],
    status_by_id: Mapping[str, EvidenceSourceStatus],
    supporting_evidence_ids: Sequence[str],
) -> tuple[list[str], list[str]]:
    """
    对 supports 边应用撤稿/撤回门禁。

    参数：
        evidences: 证据卡。
        status_by_id: 生命周期映射。
        supporting_evidence_ids: 声明试图用 supports 绑定的证据 ID。

    返回：
        (retracted_blocked_ids, placeholder_status_ids)。
    """
    known = {card.evidence_id for card in evidences}
    retracted_blocked: list[str] = []
    placeholders: list[str] = []
    for evidence_id in supporting_evidence_ids:
        if evidence_id not in known:
            continue
        status = status_by_id.get(evidence_id)
        if status is None:
            placeholders.append(evidence_id)
            continue
        if status.lifecycle in {
            SourceLifecycleStatus.RETRACTED,
            SourceLifecycleStatus.WITHDRAWN,
        }:
            retracted_blocked.append(evidence_id)
        elif status.lifecycle in {
            SourceLifecycleStatus.PLACEHOLDER,
            SourceLifecycleStatus.UNKNOWN,
        }:
            placeholders.append(evidence_id)
    return sorted(set(retracted_blocked)), sorted(set(placeholders))


def run_quality_gate(
    bundle: EvidenceBundle,
    *,
    status_by_id: Optional[Mapping[str, EvidenceSourceStatus]] = None,
    disposition: ConflictDisposition = ConflictDisposition.KEEP_BOTH_FLAGGED,
) -> QualityGateReport:
    """
    运行 Wave C 质量门：冲突保留 + 撤稿占位门禁。

    参数：
        bundle: EvidenceBundle。
        status_by_id: 可选生命周期映射；缺省为全 PLACEHOLDER。
        disposition: 冲突处置。

    返回：
        QualityGateReport。
    """
    statuses = (
        dict(status_by_id)
        if status_by_id is not None
        else default_source_status_map(bundle.evidences)
    )
    conflicts = detect_conflicts_preserving_both_sides(
        bundle,
        disposition=disposition,
    )
    supporting_ids = [
        link.evidence_id
        for link in bundle.links
        if link.relation == "supports"
    ]
    retracted, _ = apply_source_lifecycle_gate(
        evidences=bundle.evidences,
        status_by_id=statuses,
        supporting_evidence_ids=supporting_ids,
    )
    # 占位状态覆盖 Bundle 内全部证据（含 contradicts/反例），避免只扫 supports。
    _, placeholders = apply_source_lifecycle_gate(
        evidences=bundle.evidences,
        status_by_id=statuses,
        supporting_evidence_ids=[card.evidence_id for card in bundle.evidences],
    )
    notes = [
        "conflicts preserve both support and contradict evidence ids",
        "retracted/withdrawn supports are blocked; placeholders are not treated as active",
    ]
    if conflicts:
        notes.append(f"conflict_claim_count={len(conflicts)}")
    if retracted:
        notes.append(f"retracted_blocked={','.join(retracted)}")
    passed = all(not record.silently_overwritten for record in conflicts)
    if retracted and disposition == ConflictDisposition.BLOCK_CLAIM:
        passed = False
    return QualityGateReport(
        conflict_records=conflicts,
        retracted_blocked_ids=retracted,
        placeholder_status_ids=placeholders,
        passed=passed,
        notes=notes,
    )


def conflict_records_to_audit_dict(
    records: Sequence[ConflictRecord],
) -> list[dict[str, object]]:
    """
    将冲突记录序列化为可审计 dict 列表。

    参数：
        records: ConflictRecord 序列。

    返回：
        JSON 友好结构。
    """
    return [
        {
            "claim_id": record.claim_id,
            "support_evidence_ids": list(record.support_evidence_ids),
            "contradict_evidence_ids": list(record.contradict_evidence_ids),
            "counterexample_evidence_ids": list(
                record.counterexample_evidence_ids
            ),
            "disposition": record.disposition.value,
            "silently_overwritten": record.silently_overwritten,
        }
        for record in records
    ]
