"""
T01 Wave B（08/04）：黄金集指标与 12 题抽查表测试。
"""

from pathlib import Path

from app.evidence.gold_set import gold_set_count, load_evidence_gold_set
from app.evidence.metrics import (
    build_domain_audit_12,
    compute_metrics,
    generate_wave_b_metrics_artifacts,
)


def test_gold_set_has_30_pairs():
    """黄金集扩展至 30 条，且保持 provisional 诚实标注。"""
    assert gold_set_count() >= 30
    pairs = load_evidence_gold_set()
    assert len(pairs) >= 30
    assert pairs[-1]["claim_id"] == "CLAIM-030"
    assert all(pair.get("provisional") is True for pair in pairs)
    assert all(pair.get("expected_decision") for pair in pairs)


def test_gold_set_covers_multiple_handbook_domains():
    """
    Wave B 黄金集须覆盖多领域（避免几乎全是 methodology）。

    手册 08/04 要求对 12 领域代表题抽查；金标应能支撑该抽查。
    """
    pairs = load_evidence_gold_set()
    domains = {str(pair.get("domain") or "") for pair in pairs}
    # methodology + 12 audit domains 中的绝大多数
    assert len(domains) >= 12
    required = {
        "mathematics",
        "physics",
        "chemistry",
        "biology",
        "medicine",
        "earth_science",
        "computer_science",
        "materials",
        "astronomy",
        "neuroscience",
        "climate",
        "engineering",
    }
    assert required.issubset(domains)


def test_metrics_meet_precision_target_or_degrade_strategy():
    """支持关系精确率 ≥90%，并记录降级策略。"""
    report = compute_metrics()
    assert report.gold_set_size >= 30
    assert report.support_precision >= 0.90
    assert report.meets_precision_target is True
    assert report.rejection_rate >= 0.90
    assert "DEGRADE" in report.degrade_strategy or "degraded" in report.degrade_strategy.lower()


def test_domain_audit_has_12_rows_including_q028_policy():
    """12 题抽查表含 Q028 策略，并诚实声明非 live trace。"""
    table = build_domain_audit_12()
    assert table["count"] == 12
    assert len(table["rows"]) == 12
    assert table.get("not_live_pipeline_traces") is True
    q028 = next(row for row in table["rows"] if row["question_id"] == "Q028")
    assert "OVERGENERALIZATION" in q028["policy"]
    assert "CLAIM-027" in q028["linked_gold_claim_ids"]
    domains = {row["domain"] for row in table["rows"]}
    assert len(domains) == 12
    for row in table["rows"]:
        assert row.get("linked_gold_claim_ids")


def test_generate_artifacts_writes_files(tmp_path: Path):
    """可写入 metrics / domain audit 产物。"""
    # 使用仓库默认路径生成一次，确认文件存在且可解析。
    paths = generate_wave_b_metrics_artifacts()
    assert paths["metrics"].is_file()
    assert paths["domain_audit_12"].is_file()
    text = paths["metrics"].read_text(encoding="utf-8")
    assert "support_precision" in text
    assert "gold_set_size" in text
