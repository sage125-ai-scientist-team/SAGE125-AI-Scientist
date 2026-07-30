"""
T01 Evidence 运行时模块（Wave B）。

本包在契约层 ``app.contracts.evidence`` 之上提供可调用的构建与校验能力。
工作流接入（``pipeline.py``）由 T02 完成；本包不得越权修改 pipeline。
"""

from app.evidence.bundle_builder import (
    BuildBundleResult,
    ClaimSpec,
    build_evidence_bundle,
    bundle_to_agent_context,
    estimate_token_count,
    runtime_card_to_contract,
)

__all__ = [
    "BuildBundleResult",
    "ClaimSpec",
    "build_evidence_bundle",
    "bundle_to_agent_context",
    "estimate_token_count",
    "runtime_card_to_contract",
]
