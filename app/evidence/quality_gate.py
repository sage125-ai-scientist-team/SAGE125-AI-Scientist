"""
T01 Wave C 质量门 — 冲突/反例证据与撤稿/来源状态占位。

约束：
1. 不得修改 ``app/workflow/pipeline.py``；
2. 不得改写已冻结 Wave A ``app/contracts/evidence.py`` 字段；
3. 冲突证据两侧必须保留并显式标记，禁止静默覆盖/丢弃任一侧；
4. 撤稿/来源生命周期以占位元数据叠加，不伪装为已核验正式状态；
5. 撤稿门禁与冲突处置策略解耦：RETRACTED/WITHDRAWN supports 一律使 passed=False。
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
    单条声明的冲突证据记录（两侧应完整保留）。

    属性：
        claim_id: 声明 ID。
        support_evidence_ids: supports 侧证据 ID（排序）。
        contradict_evidence_ids: contradicts 侧证据 ID（排序）。
        counterexample_evidence_ids: 反例侧别名（= contradicts）。
        disposition: 处置方式。
        silently_overwritten: 期望双侧冲突但当前丢失任一侧时为 True。
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
        passed: 是否通过（无静默覆盖且无撤稿 supports）。
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


def _relation_ids_for_claim(
    links: Sequence[ClaimEvidenceLink],
    claim_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """
    提取声明的 supports / contradicts 证据 ID（排序去重）。

    参数：
        links: 链接序列。
        claim_id: 声明 ID。

    返回：
        (support_ids, contradict_ids)。
    """
    claim_links = _links_for_claim(links, claim_id)
    support_ids = tuple(
        sorted(
            {
                link.evidence_id
                for link in claim_links
                if link.relation == "supports"
            }
        )
    )
    contradict_ids = tuple(
        sorted(
            {
                link.evidence_id
                for link in claim_links
                if link.relation == "contradicts"
            }
        )
    )
    return support_ids, contradict_ids


def build_conflict_record(
    *,
    claim_id: str,
    links: Sequence[ClaimEvidenceLink],
    disposition: ConflictDisposition = ConflictDisposition.KEEP_BOTH_FLAGGED,
    silently_overwritten: bool = False,
) -> ConflictRecord:
    """
    为冲突声明构建记录；可标记静默覆盖。

    参数：
        claim_id: 声明 ID。
        links: 全量链接。
        disposition: 处置策略。
        silently_overwritten: 是否检测到上游丢弃一侧。

    返回：
        ConflictRecord。
    """
    support_ids, contradict_ids = _relation_ids_for_claim(links, claim_id)
    return ConflictRecord(
        claim_id=claim_id,
        support_evidence_ids=support_ids,
        contradict_evidence_ids=contradict_ids,
        counterexample_evidence_ids=contradict_ids,
        disposition=disposition,
        silently_overwritten=silently_overwritten,
    )


def _candidate_conflict_claim_ids(
    *,
    current_links: Sequence[ClaimEvidenceLink],
    expected_conflict_claim_ids: Optional[Sequence[str]],
    prior_links: Optional[Sequence[ClaimEvidenceLink]],
) -> list[str]:
    """
    汇总需要检查双侧完整性的声明 ID。

    来源：
    1. 当前仍同时存在 supports+contradicts 的声明；
    2. 调用方声明的 expected_conflict_claim_ids；
    3. prior_links 中曾同时存在两侧的声明（用于检测上游静默丢弃）。

    参数：
        current_links: 当前 Bundle 链接。
        expected_conflict_claim_ids: 期望保持冲突的声明。
        prior_links: 上游覆盖前的链接快照。

    返回：
        排序后的 claim_id 列表。
    """
    candidates: set[str] = set(find_conflict_claim_ids(current_links))
    if expected_conflict_claim_ids:
        candidates.update(str(item) for item in expected_conflict_claim_ids)
    if prior_links is not None:
        candidates.update(find_conflict_claim_ids(prior_links))
    return sorted(candidates)


def detect_conflicts_preserving_both_sides(
    bundle: EvidenceBundle,
    *,
    disposition: ConflictDisposition = ConflictDisposition.KEEP_BOTH_FLAGGED,
    expected_conflict_claim_ids: Optional[Sequence[str]] = None,
    prior_links: Optional[Sequence[ClaimEvidenceLink]] = None,
) -> list[ConflictRecord]:
    """
    检测冲突并强制两侧证据 ID 均保留；上游丢一侧时可标记 silently_overwritten。

    仅遍历“当前仍双侧齐全”的 claim 无法发现静默覆盖，因此额外接受：
    - ``expected_conflict_claim_ids``：调用方声明应保持冲突的 claim；
    - ``prior_links``：覆盖前链接快照（其中双侧齐全的 claim 必须在当前仍双侧齐全）。

    参数：
        bundle: EvidenceBundle。
        disposition: 冲突处置。
        expected_conflict_claim_ids: 期望冲突声明 ID。
        prior_links: 上游覆盖前的链接。

    返回：
        ConflictRecord 列表（按 claim_id 排序）。丢失一侧时不抛错，
        而是 ``silently_overwritten=True``，供质量门失败。
    """
    records: list[ConflictRecord] = []
    for claim_id in _candidate_conflict_claim_ids(
        current_links=bundle.links,
        expected_conflict_claim_ids=expected_conflict_claim_ids,
        prior_links=prior_links,
    ):
        support_ids, contradict_ids = _relation_ids_for_claim(
            bundle.links,
            claim_id,
        )
        missing_side = (not support_ids) or (not contradict_ids)
        # 仅当该 claim 被期望为冲突（expected/prior/当前双侧）时才记记录。
        was_expected = (
            claim_id in find_conflict_claim_ids(bundle.links)
            or (
                expected_conflict_claim_ids is not None
                and claim_id in set(expected_conflict_claim_ids)
            )
            or (
                prior_links is not None
                and claim_id in set(find_conflict_claim_ids(prior_links))
            )
        )
        if not was_expected:
            continue
        records.append(
            build_conflict_record(
                claim_id=claim_id,
                links=bundle.links,
                disposition=disposition,
                silently_overwritten=missing_side,
            )
        )
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
    expected_conflict_claim_ids: Optional[Sequence[str]] = None,
    prior_links: Optional[Sequence[ClaimEvidenceLink]] = None,
) -> QualityGateReport:
    """
    运行 Wave C 质量门：冲突保留 + 撤稿占位门禁。

    撤稿门禁独立于 ``disposition``：任一 RETRACTED/WITHDRAWN supports
    均使 ``passed=False``（含默认 KEEP_BOTH_FLAGGED）。

    参数：
        bundle: EvidenceBundle。
        status_by_id: 可选生命周期映射；缺省为全 PLACEHOLDER。
        disposition: 冲突处置（不影响撤稿失败判定）。
        expected_conflict_claim_ids: 期望保持冲突的声明。
        prior_links: 上游覆盖前链接快照。

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
        expected_conflict_claim_ids=expected_conflict_claim_ids,
        prior_links=prior_links,
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
        "retracted/withdrawn supports fail the gate independent of disposition",
        "placeholders are not treated as active",
    ]
    if conflicts:
        notes.append(f"conflict_claim_count={len(conflicts)}")
    if retracted:
        notes.append(f"retracted_blocked={','.join(retracted)}")
    overwritten = any(record.silently_overwritten for record in conflicts)
    if overwritten:
        notes.append("silent_overwrite_detected=true")
    # 撤稿失败不依赖 disposition；静默覆盖也独立失败。
    passed = (not retracted) and (not overwritten)
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
