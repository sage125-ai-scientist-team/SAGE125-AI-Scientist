"""
T06 Wave B：workflow hook（T06 owner 范围）——向 T02 提供摘要与验证结论。
"""

from __future__ import annotations

from typing import Any

from app.contracts.multimodal import MultimodalArtifact
from app.multimodal.audit import VisionCallAudit
from app.multimodal.evidence_bridge import (
    artifact_to_evidence_card,
    low_confidence_blocks_fact,
)
from app.multimodal.summary import build_consumer_summary


def build_revision_hook_payload(
    artifacts: list[MultimodalArtifact],
    *,
    audits: list[VisionCallAudit] | None = None,
) -> dict[str, Any]:
    """
    构造可供 T02 revision context 消费的摘要载荷。

    不修改 T02 代码；仅产出结构化 dict。低置信度标记 human_review_required。
    """
    items: list[dict[str, Any]] = []
    human_review_required = False
    for art in artifacts:
        summary = build_consumer_summary(art)
        blocked = low_confidence_blocks_fact(art)
        if blocked:
            human_review_required = True
        card = artifact_to_evidence_card(art)
        items.append(
            {
                "artifact_id": art.artifact_id,
                "summary": summary.model_dump(),
                "evidence_id": card.evidence_id,
                "locator": card.locator,
                "supports_fact": not blocked,
                "human_review_required": blocked,
            }
        )
    audit_payload = []
    for a in audits or []:
        safe = a.ensure_safe()
        audit_payload.append(safe.model_dump())
    return {
        "schema_version": "t06-workflow-hook-v1",
        "producer": "app.multimodal.workflow_hook",
        "human_review_required": human_review_required,
        "artifacts": items,
        "audits": audit_payload,
        "binary_in_prompt": False,
    }
