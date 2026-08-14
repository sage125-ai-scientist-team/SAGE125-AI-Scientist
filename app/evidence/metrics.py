"""
T01 Wave B（08/04）黄金集指标计算。

计算支持关系精确率、拒绝率、未决/降级样本占比；
未达 90% 时必须依赖明确降级策略（禁止伪装通过）。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.contracts.evidence import EvidenceCardContract
from app.evidence.gold_set import DEFAULT_GOLD_SET_PATH, load_evidence_gold_set
from app.evidence.support_checker import (
    ClaimText,
    SupportDecision,
    SupportErrorCode,
    check_claim_evidence_support,
    is_fake_booklet_evidence_id,
)

DEFAULT_METRICS_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "modules"
    / "T01"
    / "metrics.json"
)

DEFAULT_DOMAIN_AUDIT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "modules"
    / "T01"
    / "domain_audit_12.json"
)


@dataclass
class PairEval:
    """
    单条黄金对评估结果。

    属性：
        claim_id: 声明 ID。
        expected_decision: allow / degrade / block。
        actual_decision: 检查器汇总结论。
        matched: 是否与期望一致。
        codes: 错误码列表。
        domain: 领域标签。
    """

    claim_id: str
    expected_decision: str
    actual_decision: str
    matched: bool
    codes: list[str] = field(default_factory=list)
    domain: str = "unknown"


@dataclass
class MetricsReport:
    """
    Wave B 指标报告。

    属性：
        gold_set_size: 黄金集条数。
        support_precision: 支持关系精确率（预测 allow 中正确占比）。
        decision_accuracy: 全体决策一致率。
        rejection_rate: 期望 block 样本中实际 block 占比。
        pending_or_degraded_rate: 实际 degrade 占比（未决/降级）。
        degrade_strategy: 未达阈值时的降级策略说明。
        meets_precision_target: 是否 ≥90% 或策略成立。
        pair_evals: 明细。
    """

    gold_set_size: int
    support_precision: float
    decision_accuracy: float
    rejection_rate: float
    pending_or_degraded_rate: float
    degrade_strategy: str
    meets_precision_target: bool
    pair_evals: list[PairEval] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可写 dict。"""
        return {
            "schema_version": "t01-metrics-v1",
            "generated_at": self.generated_at,
            "gold_set_size": self.gold_set_size,
            "support_precision": self.support_precision,
            "decision_accuracy": self.decision_accuracy,
            "rejection_rate": self.rejection_rate,
            "pending_or_degraded_rate": self.pending_or_degraded_rate,
            "precision_target": 0.90,
            "meets_precision_target": self.meets_precision_target,
            "precision_interpretation": (
                "fixture_accuracy_vs_hand_assigned_expected_decision"
            ),
            "not_independent_scientific_precision": True,
            "gold_label_tier": "wave_b_manual_fixture_accepted",
            "provisional_policy": (
                "provisional=true retained; Wave B accepts fixture harness; "
                "independent scientific precision deferred to Wave C DoD"
            ),
            "degrade_strategy": self.degrade_strategy,
            "pair_evals": [asdict(item) for item in self.pair_evals],
        }


def _pair_to_card(pair: dict[str, Any]) -> Optional[EvidenceCardContract]:
    """
    将黄金对转为契约卡；虚构 booklet ID 不入池。

    参数：
        pair: 黄金对字典。

    返回：
        EvidenceCardContract 或 None。
    """
    evidence_id = str(pair["evidence_id"])
    if is_fake_booklet_evidence_id(evidence_id):
        return None

    source_type = str(pair.get("source_type") or "test_fixture")
    allowed = {
        "paper",
        "dataset",
        "experiment",
        "web",
        "contract",
        "specification",
        "test_fixture",
        "question_booklet",
    }
    if source_type not in allowed:
        source_type = "test_fixture"

    # claim.domain 用于跨域判定；证据卡可用 evidence_domain 覆盖（CROSS_DOMAIN 夹具）。
    card_domain = str(
        pair.get("evidence_domain") or pair.get("domain") or "methodology"
    )
    locator = dict(pair["locator"])
    # 保证金标夹具具备 supports 所需完整 provenance（非科学 DOI，仅测试身份）。
    if not any(
        key in locator and locator.get(key) not in (None, "", [])
        for key in ("page", "section", "document", "source_path", "chunk")
    ):
        locator = {**locator, "document": "t01-gold-set", "section": "fixture"}

    doi = str(pair.get("doi") or "").strip() or f"10.0000/t01.gold.{evidence_id.lower()}"
    url = str(pair.get("url") or "").strip() or None
    authors = pair.get("authors")
    if not isinstance(authors, list) or not authors:
        authors = ["gold-set-annotator"]

    return EvidenceCardContract(
        evidence_id=evidence_id,
        source_id=str(pair.get("source_id") or evidence_id),
        source_type=source_type,  # type: ignore[arg-type]
        title=str(pair.get("claim") or evidence_id)[:80],
        quoted_text=str(pair["quote"]),
        locator=locator,
        authors=[str(item) for item in authors],
        year=2026,
        doi=doi,
        url=url,
        content_hash=f"sha256:gold:{evidence_id}",
        domain=card_domain,
        verification_status="pending",
    )


def _actual_decision(result_codes: list[str], allowed: int, blocked: bool, degraded: bool) -> str:
    """
    将检查器结果折叠为 allow / degrade / block。

    参数：
        result_codes: 错误码。
        allowed: allow 链接数。
        blocked: 是否阻断。
        degraded: 是否降级。

    返回：
        决策字符串。
    """
    if blocked or SupportErrorCode.FAKE_BOOKLET_EVIDENCE_ID.value in result_codes:
        return SupportDecision.BLOCK.value
    if degraded or allowed == 0:
        # 无 allow 且未 block：视为 degrade/pending，不得伪装 allow。
        return SupportDecision.DEGRADE.value
    return SupportDecision.ALLOW.value


def evaluate_gold_pair(pair: dict[str, Any]) -> PairEval:
    """
    评估单条黄金对。

    参数：
        pair: 黄金对。

    返回：
        PairEval。
    """
    expected = str(pair.get("expected_decision") or "allow").lower()
    evidence_id = str(pair["evidence_id"])
    card = _pair_to_card(pair)
    evidences = [card] if card is not None else []

    claim = ClaimText(
        claim_id=str(pair["claim_id"]),
        text=str(pair["claim"]),
        evidence_ids=[evidence_id],
        domain=str(pair.get("domain") or "methodology"),
        relation=str(pair.get("relation") or "supports"),
        confidence=0.5,
    )
    result = check_claim_evidence_support([claim], evidences)
    actual = _actual_decision(
        result.error_codes,
        len(result.allowed_links),
        result.blocked,
        bool(result.degraded_claim_ids),
    )
    return PairEval(
        claim_id=str(pair["claim_id"]),
        expected_decision=expected,
        actual_decision=actual,
        matched=(actual == expected),
        codes=result.error_codes,
        domain=str(pair.get("domain") or "methodology"),
    )


def compute_metrics(
    path: Path | None = None,
    *,
    generated_at: str | None = None,
) -> MetricsReport:
    """
    基于黄金集计算 Wave B 指标。

    参数：
        path: 黄金集 JSON 路径。
        generated_at: 可选冻结时间戳（ISO8601）。测试必须传入，避免静默改写审计产物。
            未传入时才使用当前 UTC 时间（仅供维护者有意刷新）。

    返回：
        MetricsReport。
    """
    pairs = load_evidence_gold_set(path)
    evals = [evaluate_gold_pair(pair) for pair in pairs]

    predicted_allow = [item for item in evals if item.actual_decision == "allow"]
    true_allow = [item for item in predicted_allow if item.expected_decision == "allow"]
    support_precision = (
        len(true_allow) / len(predicted_allow) if predicted_allow else 1.0
    )

    decision_accuracy = (
        sum(1 for item in evals if item.matched) / len(evals) if evals else 0.0
    )

    expected_block = [item for item in evals if item.expected_decision == "block"]
    rejected_ok = [item for item in expected_block if item.actual_decision == "block"]
    rejection_rate = (
        len(rejected_ok) / len(expected_block) if expected_block else 1.0
    )

    degraded = [item for item in evals if item.actual_decision == "degrade"]
    pending_or_degraded_rate = len(degraded) / len(evals) if evals else 0.0

    degrade_strategy = (
        "Uncertain supports are degraded (DEGRADE) rather than ALLOW; "
        "booklet / fake booklet IDs / metadata-only (title/DOI/URL-only) are BLOCK; "
        "cross-domain and cancer overgeneralization are DEGRADE. "
        "support_precision is fixture accuracy vs hand-assigned expected_decision "
        "on predicted ALLOW only — NOT an independent scientific annotator score. "
        "All gold pairs remain provisional=true until Wave C DoD sign-off."
    )
    meets = support_precision >= 0.90
    stamp = (
        generated_at
        if generated_at is not None
        else datetime.now(timezone.utc).isoformat()
    )

    return MetricsReport(
        gold_set_size=len(pairs),
        support_precision=round(support_precision, 4),
        decision_accuracy=round(decision_accuracy, 4),
        rejection_rate=round(rejection_rate, 4),
        pending_or_degraded_rate=round(pending_or_degraded_rate, 4),
        degrade_strategy=degrade_strategy,
        meets_precision_target=meets,
        pair_evals=evals,
        generated_at=stamp,
    )


def _write_json_deterministic(path: Path, payload: dict[str, Any]) -> Path:
    """
    以确定性 UTF-8 + LF 写入 JSON（末尾换行）。

    参数：
        path: 目标文件。
        payload: 可 JSON 序列化的字典。

    返回：
        写入路径。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.encode("utf-8"))
    return path


def write_metrics_json(
    report: MetricsReport,
    path: Path | None = None,
) -> Path:
    """
    写入 metrics.json。

    参数：
        report: MetricsReport。
        path: 输出路径；``None`` 时写入仓库默认审计路径（仅维护者显式刷新用）。

    返回：
        实际写入路径。
    """
    target = path or DEFAULT_METRICS_PATH
    return _write_json_deterministic(target, report.to_dict())


def build_domain_audit_12() -> dict[str, Any]:
    """
    构建 12 个领域代表题抽查表（题目相关性 + 跨域外推策略）。

    说明（严格对齐手册 08/04）：
    - 这是代表题抽查表，不是 live pipeline / agent-trace 跑题产物；
    - 每行记录题目相关性与跨域外推策略；
    - 通过 linked_gold_claim_ids 回链 Wave B 黄金集夹具，便于复现。

    返回：
        可写入 JSON 的抽查表。
    """
    rows = [
        {
            "question_id": "Q001",
            "domain": "mathematics",
            "topic": "prime distribution",
            "evidence_domain": "mathematics",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-013"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q012",
            "domain": "physics",
            "topic": "quantum error correction",
            "evidence_domain": "physics",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-024", "CLAIM-030"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q018",
            "domain": "chemistry",
            "topic": "catalysis",
            "evidence_domain": "chemistry",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-014"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q024",
            "domain": "biology",
            "topic": "xenotransplantation",
            "evidence_domain": "biology",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-015"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q028",
            "domain": "medicine",
            "topic": "cancer therapy generalization",
            "evidence_domain": "medicine",
            "topic_relevant": True,
            "cross_domain_extrapolation": "single_cancer_to_all_cancers",
            "policy": "DEGRADE via OVERGENERALIZATION; never unconditional allow",
            "linked_gold_claim_ids": ["CLAIM-026", "CLAIM-027", "CLAIM-028"],
            "evidence_consistency": "q028_contract_layer_regression_fixtures",
        },
        {
            "question_id": "Q035",
            "domain": "earth_science",
            "topic": "monsoon and salinity",
            "evidence_domain": "earth_science",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-023", "CLAIM-029"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q042",
            "domain": "computer_science",
            "topic": "evidence grounding systems",
            "evidence_domain": "computer_science",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-021", "CLAIM-025"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q051",
            "domain": "materials",
            "topic": "battery electrolytes",
            "evidence_domain": "materials",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-016"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q063",
            "domain": "astronomy",
            "topic": "exoplanet atmospheres",
            "evidence_domain": "astronomy",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-017"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q077",
            "domain": "neuroscience",
            "topic": "synaptic plasticity",
            "evidence_domain": "neuroscience",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-018"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
        {
            "question_id": "Q089",
            "domain": "climate",
            "topic": "carbon cycle feedbacks",
            "evidence_domain": "medicine",
            "topic_relevant": False,
            "cross_domain_extrapolation": "climate_claim_with_oncology_evidence",
            "policy": "DEGRADE via CROSS_DOMAIN",
            "linked_gold_claim_ids": ["CLAIM-020"],
            "evidence_consistency": "intentional_domain_mismatch_for_red_light",
        },
        {
            "question_id": "Q102",
            "domain": "engineering",
            "topic": "control stability",
            "evidence_domain": "engineering",
            "topic_relevant": True,
            "cross_domain_extrapolation": "none",
            "policy": "allow_if_quote_overlaps",
            "linked_gold_claim_ids": ["CLAIM-019"],
            "evidence_consistency": "evidence_domain_matches_question_domain",
        },
    ]
    return {
        "schema_version": "t01-domain-audit-12-v1",
        "count": len(rows),
        "audit_type": "representative_policy_sampling_table",
        "not_live_pipeline_traces": True,
        "note": (
            "Wave B 08/04 representative 12-domain sampling table. "
            "Records topic relevance and cross-domain extrapolation policy only; "
            "not full agent-trace execution. linked_gold_claim_ids point to "
            "docs/modules/T01/evidence_gold_set.json fixtures for reproduction."
        ),
        "rows": rows,
    }


def write_domain_audit_12(path: Path | None = None) -> Path:
    """
    写入 12 题抽查表 JSON。

    参数：
        path: 输出路径；``None`` 时写入仓库默认审计路径（仅维护者显式刷新用）。

    返回：
        实际路径。
    """
    target = path or DEFAULT_DOMAIN_AUDIT_PATH
    return _write_json_deterministic(target, build_domain_audit_12())


def generate_wave_b_metrics_artifacts(
    gold_path: Path | None = None,
    *,
    output_dir: Path | None = None,
    metrics_path: Path | None = None,
    domain_audit_path: Path | None = None,
    generated_at: str | None = None,
    allow_tracked_write: bool = False,
) -> dict[str, Path]:
    """
    一键生成 metrics.json 与 domain_audit_12.json。

    默认**禁止**写入仓库已跟踪的审计路径，避免 pytest 弄脏工作树。
    测试应传入 ``output_dir``（如 pytest ``tmp_path``）并冻结 ``generated_at``。
    维护者若要刷新 tracked 文件，须显式 ``allow_tracked_write=True``。

    参数：
        gold_path: 黄金集路径。
        output_dir: 输出目录；与 metrics_path/domain_audit_path 二选一组合。
        metrics_path: 可选显式 metrics 输出路径。
        domain_audit_path: 可选显式 domain audit 输出路径。
        generated_at: 冻结的 ISO8601 时间戳；测试必须传入。
        allow_tracked_write: 为 True 时才允许落到 DEFAULT_* tracked 路径。

    返回：
        产物路径字典。

    异常：
        ValueError: 未提供 output_dir/显式路径且未允许 tracked 写入。
    """
    if output_dir is not None:
        out = Path(output_dir)
        metrics_target = metrics_path or (out / "metrics.json")
        domain_target = domain_audit_path or (out / "domain_audit_12.json")
    else:
        metrics_target = metrics_path
        domain_target = domain_audit_path

    if metrics_target is None or domain_target is None:
        if not allow_tracked_write:
            raise ValueError(
                "generate_wave_b_metrics_artifacts requires output_dir "
                "(or metrics_path + domain_audit_path); refusing to rewrite "
                "tracked docs/modules/T01 audit artifacts unless "
                "allow_tracked_write=True"
            )
        metrics_target = metrics_target or DEFAULT_METRICS_PATH
        domain_target = domain_target or DEFAULT_DOMAIN_AUDIT_PATH

    if not allow_tracked_write:
        tracked = {
            DEFAULT_METRICS_PATH.resolve(),
            DEFAULT_DOMAIN_AUDIT_PATH.resolve(),
        }
        if metrics_target.resolve() in tracked or domain_target.resolve() in tracked:
            raise ValueError(
                "refusing to write tracked T01 audit artifacts during generation; "
                "pass output_dir/tmp_path or allow_tracked_write=True"
            )

    report = compute_metrics(
        gold_path or DEFAULT_GOLD_SET_PATH,
        generated_at=generated_at,
    )
    written_metrics = write_metrics_json(report, metrics_target)
    written_domain = write_domain_audit_12(domain_target)
    return {"metrics": written_metrics, "domain_audit_12": written_domain}
