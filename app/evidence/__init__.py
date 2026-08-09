"""
T01 Evidence 运行时模块（Wave B + Wave C）。

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
from app.evidence.content_hash_cache import (
    ContentHashCache,
    assert_same_input_stable_evidence_set,
    deterministic_bundle_digest,
    get_global_content_hash_cache,
    stable_evidence_set_fingerprint,
    stable_sort_evidence_ids,
)
from app.evidence.gold_set import gold_set_count, load_evidence_gold_set
from app.evidence.integration_bridge import (
    BUNDLE_FINGERPRINT_KEY,
    EvidenceIntegrationPrecheck,
    attach_bundle_to_plan_version,
    build_v1_v2_revision_with_bundle,
    build_validation_context_from_bundle,
    bundle_fingerprint,
    evidence_card_to_validation_wire,
    find_conflict_claim_ids,
    precheck_bundle_for_validation,
    round_trip_revision_state,
)
from app.evidence.metrics import (
    MetricsReport,
    compute_metrics,
    generate_wave_b_metrics_artifacts,
)
from app.evidence.q028_regression import Q028RegressionReport, run_q028_regression
from app.evidence.quality_gate import (
    ConflictDisposition,
    ConflictRecord,
    EvidenceSourceStatus,
    QualityGateReport,
    SourceLifecycleStatus,
    detect_conflicts_preserving_both_sides,
    run_quality_gate,
)
from app.evidence.serialization import (
    build_api_example_payload,
    build_output_envelope_v125,
    dumps_output_envelope,
    serialize_evidence_bundle,
    serialize_quality_gate_report,
)
from app.evidence.support_checker import (
    ClaimText,
    SupportCheckResult,
    SupportDecision,
    SupportErrorCode,
    SupportFinding,
    check_bundle_support,
    check_claim_evidence_support,
)
from app.evidence.wave_c_signoff import (
    SeparatedSignoffPackage,
    build_separated_signoff_package,
    render_contract_regression_markdown,
    render_human_signoff_markdown,
    write_separated_signoff_artifacts,
)

__all__ = [
    "BUNDLE_FINGERPRINT_KEY",
    "BuildBundleResult",
    "CitationItem",
    "ClaimSpec",
    "ClaimText",
    "ConflictDisposition",
    "ConflictRecord",
    "ContentHashCache",
    "EvidenceIntegrationPrecheck",
    "EvidenceSourceStatus",
    "MetricsReport",
    "Q028RegressionReport",
    "QualityGateReport",
    "SourceLifecycleStatus",
    "SupportCheckResult",
    "SupportDecision",
    "SupportErrorCode",
    "SupportFinding",
    "T08CitationPayload",
    "SeparatedSignoffPackage",
    "assert_same_input_stable_evidence_set",
    "build_separated_signoff_package",
    "attach_bundle_to_plan_version",
    "build_api_example_payload",
    "build_citation_item",
    "build_evidence_bundle",
    "build_output_envelope_v125",
    "build_t08_citation_payload",
    "build_v1_v2_revision_with_bundle",
    "build_validation_context_from_bundle",
    "bundle_fingerprint",
    "bundle_to_agent_context",
    "check_bundle_support",
    "check_claim_evidence_support",
    "compute_metrics",
    "detect_conflicts_preserving_both_sides",
    "deterministic_bundle_digest",
    "dumps_output_envelope",
    "estimate_token_count",
    "evidence_card_to_validation_wire",
    "find_conflict_claim_ids",
    "generate_wave_b_metrics_artifacts",
    "get_global_content_hash_cache",
    "gold_set_count",
    "load_evidence_gold_set",
    "precheck_bundle_for_validation",
    "render_citation_markdown",
    "render_contract_regression_markdown",
    "render_human_signoff_markdown",
    "round_trip_revision_state",
    "run_q028_regression",
    "run_quality_gate",
    "runtime_card_to_contract",
    "serialize_evidence_bundle",
    "serialize_quality_gate_report",
    "stable_evidence_set_fingerprint",
    "stable_sort_evidence_ids",
    "write_separated_signoff_artifacts",
]
