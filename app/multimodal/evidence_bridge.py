"""
T06 Wave B：MultimodalArtifact → T01 EvidenceCardContract 适配（不改 T01 路径）。
"""

from __future__ import annotations

import hashlib
import json

from app.contracts.evidence import EvidenceCardContract
from app.contracts.multimodal import MultimodalArtifact
from app.multimodal.summary import build_consumer_summary

_LOW_CONFIDENCE = 0.80


def extract_file_sha256(source_path: str) -> str | None:
    """Parse `#sha256=` suffix from provenance.source_path if present."""
    marker = "#sha256="
    if marker not in source_path:
        return None
    return source_path.split(marker, 1)[1].split("#", 1)[0].strip() or None


def artifact_to_evidence_card(
    artifact: MultimodalArtifact,
    *,
    title: str | None = None,
) -> EvidenceCardContract:
    """
    将多模态产物映射为 EvidenceCardContract。

    - 保留 page/bbox/units/confidence/file_sha256 于 locator；
    - 低置信度或 needs_review/failed 不得标 verification_status=valid；
    - quoted_text 使用结构化摘要原文片段，不编造 DOI。
    """
    summary = build_consumer_summary(artifact)
    file_sha = extract_file_sha256(artifact.provenance.source_path)
    locator = {
        "source_path": artifact.provenance.source_path,
        "source_type": artifact.provenance.source_type,
        "page": artifact.provenance.page,
        "modality": artifact.modality,
        "units": list(artifact.units),
        "confidence": artifact.confidence,
        "validation_status": artifact.validation_status,
    }
    if file_sha:
        locator["file_sha256"] = file_sha
    if artifact.provenance.bbox is not None:
        locator["bbox"] = artifact.provenance.bbox.model_dump()

    quote_payload = {
        "headers": artifact.data.headers,
        "row_count": len(artifact.data.rows),
        "sample_rows": artifact.data.rows[:3],
    }
    quoted = json.dumps(quote_payload, ensure_ascii=False, sort_keys=True)
    content_hash = hashlib.sha256(quoted.encode("utf-8")).hexdigest()

    notes = [
        f"modality={artifact.modality}",
        f"confidence={artifact.confidence:.4f}",
        f"validation_status={artifact.validation_status}",
        f"t06_bridge=artifact_to_evidence_card",
    ]
    if artifact.confidence < _LOW_CONFIDENCE:
        notes.append("low_confidence_requires_human_review")
    if artifact.validation_status in ("needs_review", "failed", "pending"):
        notes.append("not_factual_support_until_review")

    verification = "pending"
    if (
        artifact.validation_status == "failed"
        or artifact.confidence < 0.5
    ):
        verification = "rejected"
    elif artifact.validation_status == "passed" and artifact.confidence >= _LOW_CONFIDENCE:
        # 仍保持 pending：跨模块事实支持需人工/上游确认，避免 T06 单方面标 valid
        verification = "pending"
        notes.append("passed_extraction_but_pending_upstream_validation")

    return EvidenceCardContract(
        evidence_id=f"t06-{artifact.artifact_id}",
        source_id=artifact.provenance.source_path,
        source_type="test_fixture"
        if artifact.provenance.source_type.endswith("fixture")
        else "dataset",
        title=title or f"T06 {artifact.modality} artifact {artifact.artifact_id}",
        quoted_text=quoted[:2000],
        locator=locator,
        content_hash=content_hash,
        verification_status=verification,  # type: ignore[arg-type]
        domain="multimodal",
    )


def low_confidence_blocks_fact(artifact: MultimodalArtifact) -> bool:
    """低置信度不得支撑事实。"""
    return (
        artifact.confidence < _LOW_CONFIDENCE
        or artifact.validation_status in ("needs_review", "failed", "pending")
    )
