"""
T01 Wave B（08/04）：黄金集指标与 12 题抽查表测试。

Issue #44：pytest 不得改写已跟踪的 docs/modules/T01 审计产物。
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from app.evidence.gold_set import gold_set_count, load_evidence_gold_set
from app.evidence.metrics import (
    DEFAULT_DOMAIN_AUDIT_PATH,
    DEFAULT_METRICS_PATH,
    build_domain_audit_12,
    compute_metrics,
    generate_wave_b_metrics_artifacts,
)

_FROZEN_GENERATED_AT = "2026-08-02T06:41:57.966684+00:00"
_TRACKED_AUDIT_FILES = (
    DEFAULT_METRICS_PATH,
    DEFAULT_DOMAIN_AUDIT_PATH,
)


def _file_digest(path: Path) -> str:
    """返回文件原始字节 SHA-256。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_gold_set_has_30_pairs():
    """黄金集扩展至 30 条；Wave B 接受夹具层，provisional 明确留给 Wave C 终审。"""
    assert gold_set_count() >= 30
    pairs = load_evidence_gold_set()
    assert len(pairs) >= 30
    assert pairs[-1]["claim_id"] == "CLAIM-030"
    assert all(pair.get("provisional") is True for pair in pairs)
    assert all(pair.get("expected_decision") for pair in pairs)
    assert all(
        pair.get("label_tier") == "wave_b_manual_fixture_accepted" for pair in pairs
    )
    assert all(pair.get("wave_c_followup") == "human_signoff_required" for pair in pairs)


def test_gold_set_covers_multiple_handbook_domains():
    """
    Wave B 黄金集须覆盖多领域（避免几乎全是 methodology）。

    手册 08/04 要求对 12 领域代表题抽查；金标应能支撑该抽查。
    """
    pairs = load_evidence_gold_set()
    domains = {str(pair.get("domain") or "") for pair in pairs}
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
    """支持关系精确率 ≥90%，并记录降级策略；时钟可冻结。"""
    report = compute_metrics(generated_at=_FROZEN_GENERATED_AT)
    assert report.gold_set_size >= 30
    assert report.support_precision >= 0.90
    assert report.meets_precision_target is True
    assert report.rejection_rate >= 0.90
    assert "DEGRADE" in report.degrade_strategy or "degraded" in report.degrade_strategy.lower()
    assert report.generated_at == _FROZEN_GENERATED_AT


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


def test_generate_artifacts_writes_to_tmp_path_only(tmp_path: Path) -> None:
    """产物必须写入注入目录（tmp_path），不得触碰 tracked 审计文件。"""
    before = {path: _file_digest(path) for path in _TRACKED_AUDIT_FILES if path.is_file()}
    paths = generate_wave_b_metrics_artifacts(
        output_dir=tmp_path,
        generated_at=_FROZEN_GENERATED_AT,
    )
    assert paths["metrics"] == tmp_path / "metrics.json"
    assert paths["domain_audit_12"] == tmp_path / "domain_audit_12.json"
    assert paths["metrics"].is_file()
    assert paths["domain_audit_12"].is_file()
    text = paths["metrics"].read_text(encoding="utf-8")
    assert "support_precision" in text
    assert "gold_set_size" in text
    assert _FROZEN_GENERATED_AT in text
    # 确定性 LF：文件中不应出现 CRLF
    assert b"\r\n" not in paths["metrics"].read_bytes()
    assert b"\r\n" not in paths["domain_audit_12"].read_bytes()
    for path, digest in before.items():
        assert _file_digest(path) == digest


def test_generate_artifacts_refuses_tracked_default_without_opt_in() -> None:
    """未提供 output_dir 且未 opt-in 时拒绝写入 tracked 路径。"""
    with pytest.raises(ValueError, match="refusing|requires output_dir"):
        generate_wave_b_metrics_artifacts(generated_at=_FROZEN_GENERATED_AT)


def test_pytest_metrics_path_does_not_dirty_tracked_audit_files(
    tmp_path: Path,
) -> None:
    """
    Issue #44 回归：跑 metrics 生成后，tracked 审计文件字节不变，
    且 git 不将这些路径标为 modified。
    """
    before_digests = {
        path: _file_digest(path) for path in _TRACKED_AUDIT_FILES if path.is_file()
    }
    assert before_digests, "tracked T01 audit artifacts must exist in repo"

    generate_wave_b_metrics_artifacts(
        output_dir=tmp_path,
        generated_at=_FROZEN_GENERATED_AT,
    )
    # 再跑一次只读计算，确认也不会写盘
    compute_metrics(generated_at=_FROZEN_GENERATED_AT)

    for path, digest in before_digests.items():
        assert _file_digest(path) == digest

    repo_root = Path(__file__).resolve().parents[2]
    rels = [
        str(path.relative_to(repo_root)).replace("\\", "/")
        for path in _TRACKED_AUDIT_FILES
    ]
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--", *rels],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.stdout.strip() == "", proc.stdout
