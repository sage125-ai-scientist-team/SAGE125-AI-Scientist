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
from typing import Any

import pytest

from app.execution import flagship_revision as fr
from app.execution import flagship_reviewer as freviewer


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


class _FakeQwenClient:
    def __init__(self, *, response_text: str, request_id: str | None, settings=None):
        self._response_text = response_text
        self._request_id = request_id
        self.last_request_id = None
        self.last_usage: dict[str, Any] = {}

    def chat(self, messages, model, temperature=0.1, response_format=None):  # noqa: ANN001
        self.last_request_id = self._request_id
        self.last_usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        return self._response_text


ROUND1_RESULT = {
    "execution_id": "execution-test0001",
    "question_id": "Q028",
    "status": "succeeded",
    "actual_execution": True,
    "metrics": [
        {"name": "balanced_accuracy", "value": 0.9642857142857143},
        {"name": "malignant_recall", "value": 0.9285714285714286},
    ],
    "datasets": [{"sha256": "d606af41" * 8}],
    "seed": 125,
    "environment_fingerprint": {"git_dirty": False},
}

VALID_REVIEWER_JSON = {
    "review_id": "review-001",
    "passed": False,
    "critical_issues": [],
    "required_revisions": [
        {
            "issue_id": "req-rev-001",
            "severity": "P1",
            "affected_metric": "malignant_recall",
            "observed_value": 0.9285714285714286,
            "target_value": 0.95,
            "required_action": "decrease decision_threshold per allowed_revision_policy",
            "evidence_reference": "docs/modules/T05/round1/execution_result.json",
        }
    ],
    "comments": ["Round 1 balanced_accuracy is strong but malignant_recall misses target."],
}

VALID_V2_PLAN_JSON = {
    "plan_id": "plan-001",
    "responds_to_issue_ids": ["req-rev-001"],
    "proposed_changes": [
        {"field": "decision_threshold", "from": 0.5, "to": 0.4, "justification": "lower threshold to raise recall"}
    ],
    "expected_effect": "malignant_recall should increase at some cost to false positives",
}


def _fake_preparation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    monkeypatch.setattr(freviewer, "is_mock_mode", lambda: False)

    class _FakeSettings:
        qwen_configured = True
        qwen_fast_model = "qwen3.6-flash"

    monkeypatch.setattr(freviewer, "get_settings", lambda: _FakeSettings())

    round1_config = _round1_config()
    fake_reviewer = _FakeQwenClient(response_text=json.dumps(VALID_REVIEWER_JSON), request_id="chatcmpl-r1")
    monkeypatch.setattr(freviewer, "QwenChatClient", lambda settings=None: fake_reviewer)
    reviewer_output, reviewer_audit, v1_hashes = freviewer.call_scientific_reviewer(
        round1_result=ROUND1_RESULT, round1_config=round1_config, destination_dir=tmp_path,
    )
    fake_v2 = _FakeQwenClient(response_text=json.dumps(VALID_V2_PLAN_JSON), request_id="chatcmpl-v2")
    monkeypatch.setattr(freviewer, "QwenChatClient", lambda settings=None: fake_v2)
    v2_output, v2_audit, v2_hashes = freviewer.call_v2_revision_plan(
        reviewer_output=reviewer_output, round1_result=ROUND1_RESULT, round1_config=round1_config,
        provider_audit_reference=reviewer_audit.call_id, destination_dir=tmp_path,
    )
    policy_result = freviewer.validate_v2_plan_against_policy(v2_output)
    round2_config = freviewer.apply_policy_filtered_round2_config(round1_config, policy_result)
    review_feedback = fr.review_feedback_from_reviewer_output(reviewer_output)
    return {
        "reviewer_output": reviewer_output,
        "v2_output": v2_output,
        "policy_result": policy_result,
        "round2_config": round2_config,
        "reviewer_audit": reviewer_audit,
        "v2_audit": v2_audit,
        "v1_hashes": v1_hashes,
        "v2_hashes": v2_hashes,
        "review_feedback": review_feedback,
    }


def test_real_reviewer_driven_bundle_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    preparation = _fake_preparation(monkeypatch, tmp_path)
    round1_config = _round1_config()
    bundle = fr.build_real_reviewer_driven_bundle(
        preparation=preparation,
        round1_config=round1_config,
        round2_metrics={"malignant_recall": 0.9523809523809523},
        control_invariants={"only_permitted_change": "decision_threshold"},
        round1_version_id="version-round1-fake",
        round1_execution_result_reference={"execution_id": ROUND1_RESULT["execution_id"]},
    )
    assert bundle["revision_context"]["reviewer_issues_injected"] is True
    assert bundle["revision_context"]["execution_result_injected"] is True
    assert bundle["revision_context"]["round1_execution_result_reference"]["execution_id"] == (
        ROUND1_RESULT["execution_id"]
    )
    assert bundle["policy_validation"]["ok"] is True
    assert bundle["provider_audit"]["calls"][0]["role"] == "scientific_reviewer"
    assert bundle["provider_audit"]["calls"][1]["role"] == "v2_revision_plan"


def test_real_reviewer_driven_bundle_fails_closed_without_execution_result_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Truthfulness item #4: a missing/empty Round 1 ExecutionResult reference
    must never silently pass -- RevisionContext injection is not optional."""
    preparation = _fake_preparation(monkeypatch, tmp_path)
    round1_config = _round1_config()
    with pytest.raises(fr.FlagshipRevisionError):
        fr.build_real_reviewer_driven_bundle(
            preparation=preparation,
            round1_config=round1_config,
            round2_metrics={"malignant_recall": 0.9523809523809523},
            control_invariants={"only_permitted_change": "decision_threshold"},
            round1_version_id="version-round1-fake",
            round1_execution_result_reference={},
        )


def test_real_reviewer_driven_bundle_fails_closed_when_hashes_identical(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Truthfulness item #5/#6: identical V1/V2 prompt or input hashes must
    never be published as a genuine reviewer-driven iteration."""
    preparation = _fake_preparation(monkeypatch, tmp_path)
    preparation["v2_hashes"] = dict(preparation["v1_hashes"])
    round1_config = _round1_config()
    with pytest.raises(fr.FlagshipRevisionError):
        fr.build_real_reviewer_driven_bundle(
            preparation=preparation,
            round1_config=round1_config,
            round2_metrics={"malignant_recall": 0.9523809523809523},
            control_invariants={"only_permitted_change": "decision_threshold"},
            round1_version_id="version-round1-fake",
            round1_execution_result_reference={"execution_id": ROUND1_RESULT["execution_id"]},
        )


def test_real_reviewer_driven_bundle_fails_closed_on_audit_role_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Truthfulness item #11: provider audit records must be attributable to
    the correct call role -- a swapped/mismatched audit record must fail
    closed rather than be silently attributed to the wrong call."""
    preparation = _fake_preparation(monkeypatch, tmp_path)
    preparation["reviewer_audit"], preparation["v2_audit"] = preparation["v2_audit"], preparation["reviewer_audit"]
    round1_config = _round1_config()
    with pytest.raises(fr.FlagshipRevisionError):
        fr.build_real_reviewer_driven_bundle(
            preparation=preparation,
            round1_config=round1_config,
            round2_metrics={"malignant_recall": 0.9523809523809523},
            control_invariants={"only_permitted_change": "decision_threshold"},
            round1_version_id="version-round1-fake",
            round1_execution_result_reference={"execution_id": ROUND1_RESULT["execution_id"]},
        )


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
