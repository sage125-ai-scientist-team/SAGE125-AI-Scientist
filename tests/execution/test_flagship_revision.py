"""Tests for the deterministic Q028/WDBC reviewer-feedback/revision bridge.

These tests never call an LLM and never touch the network; they only verify
that ``app.execution.flagship_revision`` derives ReviewFeedback / IssueClosure
/ RevisionContext / PlanVersion / structured_diff / stop_reason purely and
deterministically from real, frozen configuration and real metrics, and that
it fails closed whenever required evidence is missing or the two rounds are
not a genuine iteration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.execution import flagship_revision as fr


ROOT = Path(__file__).resolve().parents[2]
ROUND1_CONFIG = ROOT / "experiments" / "flagship" / "round1_config.json"
ROUND2_CONFIG = ROOT / "experiments" / "flagship" / "round2_config.json"


def _round1_config() -> dict:
    return json.loads(ROUND1_CONFIG.read_text(encoding="utf-8"))


def _round2_config() -> dict:
    return json.loads(ROUND2_CONFIG.read_text(encoding="utf-8"))


def test_round1_review_feedback_fails_below_target() -> None:
    config = _round1_config()
    feedback = fr.build_round1_review_feedback(config, {"malignant_recall": 0.9285714285714286})
    assert feedback.passed is False
    assert feedback.critical_issues == []
    assert len(feedback.required_revisions) == 1
    assert "0.928571" in feedback.required_revisions[0] or "0.928571" in feedback.reviewer_comments[0]
    assert feedback.is_effective_pass is False


def test_round1_review_feedback_passes_at_target() -> None:
    config = _round1_config()
    feedback = fr.build_round1_review_feedback(config, {"malignant_recall": 0.97})
    assert feedback.passed is True
    assert feedback.critical_issues == []
    assert feedback.required_revisions == []
    assert feedback.is_effective_pass is True


def test_round1_review_feedback_fails_closed_on_missing_metric() -> None:
    config = _round1_config()
    with pytest.raises(fr.FlagshipRevisionError):
        fr.build_round1_review_feedback(config, {"balanced_accuracy": 0.9})


def test_round2_review_feedback_passes_when_target_met() -> None:
    config = _round1_config()
    feedback = fr.build_round2_review_feedback(config, {"malignant_recall": 0.9523809523809523})
    assert feedback.passed is True
    assert feedback.critical_issues == []
    assert feedback.is_effective_pass is True


def test_round2_review_feedback_fails_when_target_still_missed() -> None:
    config = _round1_config()
    feedback = fr.build_round2_review_feedback(config, {"malignant_recall": 0.5})
    assert feedback.passed is False
    assert len(feedback.critical_issues) == 1
    assert feedback.is_effective_pass is False


def test_issue_closure_resolves_only_when_round2_passes() -> None:
    config = _round1_config()
    r1 = fr.build_round1_review_feedback(config, {"malignant_recall": 0.9285714285714286})
    r2_pass = fr.build_round2_review_feedback(config, {"malignant_recall": 0.9523809523809523})
    r2_fail = fr.build_round2_review_feedback(config, {"malignant_recall": 0.5})

    resolved = fr.build_issue_closure(r1, r2_pass)
    assert len(resolved) == 1
    assert resolved[0].status == "resolved"
    assert resolved[0].closed_in_version == 2
    assert resolved[0].resolution_note

    still_open = fr.build_issue_closure(r1, r2_fail)
    assert len(still_open) == 1
    assert still_open[0].status == "open"
    assert still_open[0].closed_in_version is None


def test_issue_closure_empty_when_round1_already_passed() -> None:
    config = _round1_config()
    r1_pass = fr.build_round1_review_feedback(config, {"malignant_recall": 0.97})
    r2_pass = fr.build_round2_review_feedback(config, {"malignant_recall": 0.97})
    assert fr.build_issue_closure(r1_pass, r2_pass) == []


def test_plan_versions_have_distinct_fingerprints_and_valid_lineage() -> None:
    round1_config = _round1_config()
    round2_config = _round2_config()
    r1 = fr.build_round1_review_feedback(round1_config, {"malignant_recall": 0.9285714285714286})
    issues = fr.build_issue_closure(
        r1, fr.build_round2_review_feedback(round1_config, {"malignant_recall": 0.9523809523809523})
    )
    versions = fr.build_plan_versions(round1_config, round2_config, r1, issues)
    assert len(versions) == 2
    v1, v2 = versions
    assert v1.version_number == 1
    assert v1.parent_version_id is None
    assert v2.version_number == 2
    assert v2.parent_version_id == v1.version_id
    assert v1.prompt_fingerprints["experiment_design_config"] != (
        v2.prompt_fingerprints["experiment_design_config"]
    )


def test_plan_versions_reject_identical_configs_as_non_iteration() -> None:
    round1_config = _round1_config()
    r1 = fr.build_round1_review_feedback(round1_config, {"malignant_recall": 0.9285714285714286})
    with pytest.raises(fr.FlagshipRevisionError):
        # Passing round1_config for BOTH v1 and v2 must be rejected: identical
        # fingerprints can never represent a true iteration.
        fr.build_plan_versions(round1_config, round1_config, r1, [])


def test_structured_diff_reports_only_threshold_as_changed() -> None:
    round1_config = _round1_config()
    round2_config = _round2_config()
    diff = fr.build_structured_diff(round1_config, round2_config, {"only_permitted_change": "decision_threshold"})
    fields = {item["field"] for item in diff["changed_fields"]}
    assert fields == {"decision_threshold"}
    assert set(diff["unchanged_fields"]) == {"seed", "test_fraction", "optimizer"}
    assert diff["substantive_diff"] is True
    assert diff["v1_config_fingerprint"] != diff["v2_config_fingerprint"]


def test_stop_reason_target_achieved() -> None:
    config = _round1_config()
    r1 = fr.build_round1_review_feedback(config, {"malignant_recall": 0.9285714285714286})
    r2 = fr.build_round2_review_feedback(config, {"malignant_recall": 0.9523809523809523})
    issues = fr.build_issue_closure(r1, r2)
    stop = fr.build_stop_reason(config, {"malignant_recall": 0.9523809523809523}, issues)
    assert stop["stop_reason"] == "target_achieved"
    assert stop["unresolved_p0"] == 0
    assert stop["unresolved_p1"] == 0
    assert "cure" not in stop["rationale"].lower()
    assert "clinical" in stop["scientific_limitation"].lower()


def test_stop_reason_unresolved_when_target_still_missed() -> None:
    config = _round1_config()
    r1 = fr.build_round1_review_feedback(config, {"malignant_recall": 0.9285714285714286})
    r2 = fr.build_round2_review_feedback(config, {"malignant_recall": 0.5})
    issues = fr.build_issue_closure(r1, r2)
    stop = fr.build_stop_reason(config, {"malignant_recall": 0.5}, issues)
    assert stop["stop_reason"] == "unresolved_after_authorized_change"
    assert stop["unresolved_p1"] == 1


def test_build_and_write_from_disk_fails_closed_without_round2(tmp_path: Path) -> None:
    empty_round2 = tmp_path / "round2-not-executed"
    with pytest.raises(fr.FlagshipRevisionError):
        fr.build_and_write_from_disk(round2_package=empty_round2)


def test_build_and_write_from_disk_uses_real_committed_evidence() -> None:
    """End-to-end check against the real, already-executed Round 1 / Round 2
    evidence committed in this workspace (no fabrication, no LLM call)."""
    if not (fr.ROUND2_PACKAGE_PATH / "execution_result.json").exists():
        pytest.skip("formal Round 2 has not been executed in this workspace yet")
    bundle = fr.build_and_write_from_disk(destination_dir=None)
    assert bundle["stop_reason"]["target_metric"] == "malignant_recall"
    assert bundle["stop_reason"]["unresolved_p0"] == 0
    assert bundle["stop_reason"]["unresolved_p1"] == 0
    assert bundle["structured_diff"]["v1_config_fingerprint"] != (
        bundle["structured_diff"]["v2_config_fingerprint"]
    )
    round1_review = bundle["reviewer_feedback"]["round1_review"]
    round2_review = bundle["reviewer_feedback"]["round2_review"]
    assert round1_review["passed"] is False
    assert round2_review["passed"] is True
