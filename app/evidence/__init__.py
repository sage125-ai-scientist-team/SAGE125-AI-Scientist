"""
T01 Evidence 运行时模块（Wave B）。

本包在契约层 ``app.contracts.evidence`` 之上提供可调用的构建与校验能力。
工作流接入（``pipeline.py``）由 T02 完成；本包不得越权修改 pipeline。
不修改已通过的 Wave A 契约文件内容（除非队长明确要求改冻结接口）。
"""

from app.evidence.bundle_builder import (
    BuildBundleResult,
    ClaimSpec,
    build_evidence_bundle,
    bundle_to_agent_context,
    estimate_token_count,
    runtime_card_to_contract,
)
from app.evidence.citation_renderer import (
    CitationItem,
    T08CitationPayload,
    build_citation_item,
    build_t08_citation_payload,
    render_citation_markdown,
)
from app.evidence.gold_set import gold_set_count, load_evidence_gold_set
from app.evidence.support_checker import (
    ClaimText,
    SupportCheckResult,
    SupportDecision,
    SupportErrorCode,
    SupportFinding,
    check_bundle_support,
    check_claim_evidence_support,
)

__all__ = [
    "BuildBundleResult",
    "CitationItem",
    "ClaimSpec",
    "ClaimText",
    "SupportCheckResult",
    "SupportDecision",
    "SupportErrorCode",
    "SupportFinding",
    "T08CitationPayload",
    "build_citation_item",
    "build_evidence_bundle",
    "build_t08_citation_payload",
    "bundle_to_agent_context",
    "check_bundle_support",
    "check_claim_evidence_support",
    "estimate_token_count",
    "gold_set_count",
    "load_evidence_gold_set",
    "render_citation_markdown",
    "runtime_card_to_contract",
]
