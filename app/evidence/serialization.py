"""
T01 Wave C — 证据输出序列化与 API 样例构建。

保证 EvidenceBundle / 引用 / 质量门字段可完整 JSON 序列化，
供 T07/T08 联调消费；不修改共享契约冻结字段语义。
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Sequence

from app.contracts.evidence import EvidenceBundle, EvidenceCardContract
from app.evidence.citation_renderer import (
    CitationItem,
    T08CitationPayload,
    build_citation_item,
    build_t08_citation_payload,
    render_citation_markdown,
)
from app.evidence.content_hash_cache import (
    deterministic_bundle_digest,
    stable_evidence_set_fingerprint,
)
from app.evidence.quality_gate import (
    ConflictRecord,
    EvidenceSourceStatus,
    QualityGateReport,
    conflict_records_to_audit_dict,
)
from app.evidence.support_checker import SupportDecision


def serialize_evidence_card(card: EvidenceCardContract) -> dict[str, Any]:
    """
    将单张证据卡序列化为 JSON 友好 dict（全字段）。

    参数：
        card: EvidenceCardContract。

    返回：
        含全部契约字段的字典。
    """
    return card.model_dump(mode="json")


def serialize_evidence_bundle(bundle: EvidenceBundle) -> dict[str, Any]:
    """
    将 EvidenceBundle 全量序列化，并附加确定性指纹。

    参数：
        bundle: EvidenceBundle。

    返回：
        可 ``json.dumps`` 的字典。
    """
    payload = bundle.model_dump(mode="json")
    payload["deterministic_digest"] = deterministic_bundle_digest(bundle)
    payload["evidence_set_fingerprint"] = stable_evidence_set_fingerprint(
        bundle.evidences
    )
    return payload


def serialize_quality_gate_report(
    report: QualityGateReport,
    *,
    status_by_id: Optional[Mapping[str, EvidenceSourceStatus]] = None,
) -> dict[str, Any]:
    """
    序列化质量门报告。

    参数：
        report: QualityGateReport。
        status_by_id: 可选来源状态映射。

    返回：
        JSON 友好字典。
    """
    statuses: list[dict[str, str]] = []
    if status_by_id:
        for evidence_id in sorted(status_by_id):
            item = status_by_id[evidence_id]
            statuses.append(
                {
                    "evidence_id": item.evidence_id,
                    "lifecycle": item.lifecycle.value,
                    "note": item.note,
                }
            )
    return {
        "passed": report.passed,
        "conflict_records": conflict_records_to_audit_dict(
            report.conflict_records
        ),
        "retracted_blocked_ids": list(report.retracted_blocked_ids),
        "placeholder_status_ids": list(report.placeholder_status_ids),
        "source_statuses": statuses,
        "notes": list(report.notes),
    }


def build_output_envelope_v125(
    *,
    bundle: EvidenceBundle,
    citations: Sequence[CitationItem],
    quality: QualityGateReport,
    status_by_id: Optional[Mapping[str, EvidenceSourceStatus]] = None,
    upstream_ref: str = "integration/2026-08-10 + t01/c-evidence-hardening",
) -> dict[str, Any]:
    """
    构建 Wave C「125 输出」证据信封（可序列化全集）。

    参数：
        bundle: EvidenceBundle。
        citations: CitationItem 列表。
        quality: 质量门报告。
        status_by_id: 来源状态。
        upstream_ref: 上游引用说明。

    返回：
        完整输出信封 dict。
    """
    t08 = build_t08_citation_payload(
        citations,
        upstream_ref=upstream_ref,
    )
    return {
        "schema_version": "t01-output-envelope-v125",
        "upstream_ref": upstream_ref,
        "bundle": serialize_evidence_bundle(bundle),
        "citations": [item.__dict__ for item in citations],
        "t08_payload": t08.to_dict(),
        "markdown": render_citation_markdown(list(citations)),
        "quality_gate": serialize_quality_gate_report(
            quality,
            status_by_id=status_by_id,
        ),
    }


def dumps_output_envelope(envelope: Mapping[str, Any]) -> str:
    """
    以确定性键序将输出信封转为 JSON 文本。

    参数：
        envelope: 输出信封。

    返回：
        UTF-8 JSON 字符串。
    """
    return json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        default=str,
    )


def build_api_example_payload(
    *,
    claim_id: str,
    card: EvidenceCardContract,
    support_status: str = SupportDecision.ALLOW.value,
) -> dict[str, Any]:
    """
    构建给 T08 的最小 API 样例（单声明—单证据）。

    参数：
        claim_id: 声明 ID。
        card: 证据卡。
        support_status: 支持状态字符串。

    返回：
        API 样例 dict。
    """
    item = build_citation_item(
        claim_id=claim_id,
        card=card,
        support_status=support_status,
    )
    payload = T08CitationPayload(
        upstream_ref="integration/2026-08-10 + t01/c-evidence-hardening",
        citations=[item.__dict__],
        markdown=render_citation_markdown([item]),
    )
    return {
        "endpoint": "T01.build_t08_citation_payload",
        "consumer": "T08",
        "example": payload.to_dict(),
    }


def conflict_side_ids_complete(record: ConflictRecord) -> bool:
    """
    检查冲突记录两侧 ID 是否均非空（无静默覆盖）。

    参数：
        record: ConflictRecord。

    返回：
        True 表示两侧完整。
    """
    return bool(record.support_evidence_ids) and bool(
        record.contradict_evidence_ids
    )
