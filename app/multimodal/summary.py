"""
下游摘要封装：转发契约层 to_consumer_summary，供 queue/adapter 边界使用。
"""

from __future__ import annotations

from app.contracts.multimodal import MultimodalArtifact, MultimodalSummary, to_consumer_summary


def build_consumer_summary(artifact: MultimodalArtifact) -> MultimodalSummary:
    """构建保留来源/单位/置信度/校验状态的下游摘要。"""
    return to_consumer_summary(artifact)
