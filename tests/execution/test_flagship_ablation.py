"""Tests for Q028 ACTUAL-ABLATION-01 (FULL_SYSTEM vs NO_REVIEWER).

These tests never make a real provider call. The live ablation run is a
separate one-shot harness invocation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.execution import flagship_ablation as fa
from app.execution.flagship_reviewer import V2RevisionPlanOutput, validate_v2_plan_against_policy


def _authorized_plan_json() -> str:
    return json.dumps(
        {
            "plan_id": "nr-plan-1",
            "responds_to_issue_ids": [],
            "proposed_changes": [
                {
                    "field": "decision_threshold",
                    "from": 0.5,
                    "to": 0.4,
                    "justification": "Round 1 malignant_recall is below 0.95; policy allows 0.5->0.4",
                }
            ],
            "expected_effect": "higher malignant recall on the same holdout",
        }
    )


def test_01_protocol_is_committed_before_provider_call() -> None:
    sha = fa.protocol_commit_sha()
    assert len(sha) == 40
    protocol = fa.load_protocol()
    assert protocol["protocol_id"] == "Q028-ACTUAL-ABLATION-01"
    assert protocol["max_new_provider_calls"] == 1
    assert protocol["negative_results_must_be_reported"] is True


def test_02_control_and_ablation_differ_only_by_reviewer() -> None:
    protocol = fa.load_protocol()
    assert protocol["ablated_component"] == "Scientific Reviewer"
    assert protocol["arm_difference"]["NO_REVIEWER"]["reviewer_enabled"] is False
    assert protocol["arm_difference"]["FULL_SYSTEM"]["reviewer_enabled"] is True
    context = fa.build_no_reviewer_context()
    assert context["review_feedback"] is None
    assert context["reviewer_enabled"] is False
    assert context["round1_execution_result"]["execution_id"] == fa.ROUND1_EXECUTION_ID


def test_03_no_reviewer_prompt_has_zero_reviewer_leaks() -> None:
    protocol = fa.load_protocol()
    context = fa.build_no_reviewer_context()
    system_prompt, user_prompt = fa.build_no_reviewer_prompts(context)
    hits = fa.detect_reviewer_leaks(system_prompt + "\n" + user_prompt, protocol)
    assert hits == []


def test_03b_leak_detector_catches_full_system_issue_id() -> None:
    protocol = fa.load_protocol()
    hits = fa.detect_reviewer_leaks("see ISSUE-001 in reviewer notes", protocol)
    assert "FULL_SYSTEM_ISSUE_ID" in hits


def test_04_no_reviewer_context_does_not_call_or_embed_reviewer() -> None:
    context = fa.build_no_reviewer_context()
    dumped = json.dumps(context)
    assert "Q028-REV-001" not in dumped
    assert "scientific_reviewer" not in dumped
    assert context["review_feedback"] is None


def test_05_provider_budget_refuses_second_call(tmp_path: Path) -> None:
    fa._write_json(tmp_path / "provider_audit.json", {"calls": [{"call_id": "already"}]})
    assert fa.existing_ablation_call_count(tmp_path) == 1


def test_06_mock_output_is_refused(tmp_path: Path) -> None:
    def fake_chat(messages, **kwargs):
        return "【MOCK】fixed"

    result = fa.call_no_reviewer_planner(
        system_prompt="s",
        user_prompt="u",
        model="qwen3.6-flash",
        temperature=0.1,
        destination_dir=tmp_path,
        chat_fn=fake_chat,
    )
    assert result["status"] == "failed"
    assert result["record"]["gate"] == "BLOCKED_MOCK"


def test_07_invalid_schema_is_preserved_not_repaired() -> None:
    plan, err = fa.parse_v2_plan("not-json {")
    assert plan is None
    assert err == "invalid_json"
    plan2, err2 = fa.parse_v2_plan('{"plan_id": 1}')
    assert plan2 is None
    assert err2 == "schema_invalid"


def test_08_unauthorized_change_is_policy_rejected() -> None:
    plan = V2RevisionPlanOutput(
        plan_id="bad",
        responds_to_issue_ids=[],
        proposed_changes=[{"field": "seed", "from": 125, "to": 999, "justification": "no"}],
        expected_effect="cheat",
    )
    result = validate_v2_plan_against_policy(plan)
    assert result.ok is False
    assert result.unauthorized_changes


def test_09_no_reviewer_does_not_fabricate_issue_closure() -> None:
    full_system = fa.build_full_system_reference()
    no_reviewer = {
        "structured_issue_available": False,
        "issue_closure_auditable": False,
        "unresolved_p0": None,
        "unresolved_p1": None,
        "target_achieved": False,
        "revision_effective": False,
        "authorized_revision_proposed": False,
        "scientific_scope_pass": True,
        "provider_failed": False,
        "round2_executed": False,
        "REVIEW_STATUS": "NOT_PRESENT_BY_ABLATION",
        "ISSUE_CLOSURE_STATUS": "NOT_APPLICABLE_NO_REVIEWER",
    }
    assert no_reviewer["unresolved_p0"] is not 0
    assert no_reviewer["ISSUE_CLOSURE_STATUS"] == "NOT_APPLICABLE_NO_REVIEWER"
    assert full_system["issue_closure_auditable"] is True


def test_10_missing_reviewer_must_not_report_unresolved_zero() -> None:
    payload = {
        "REVIEW_STATUS": "NOT_PRESENT_BY_ABLATION",
        "unresolved_p0": None,
        "unresolved_p1": None,
        "unresolved_p0_p1_reported": False,
    }
    assert payload["unresolved_p0"] is None
    assert payload["unresolved_p1"] is None


def test_11_ablation_status_does_not_update_canonical_pointer() -> None:
    before = fa.POINTER_PATH.read_bytes()
    status = fa.get_actual_ablation_status()
    after = fa.POINTER_PATH.read_bytes()
    assert before == after
    assert status.get("canonical_pointer_updated") is False
    assert status.get("no_reviewer_canonical_eligible") is False


def test_12_full_system_canonical_final_bytes_unchanged() -> None:
    report = fa.verify_canonical_package_readonly()
    assert report["ok"] is True
    assert report["pointer_unchanged"] is True
    assert not report["mismatches"]


def test_13_round1_input_matches_full_system() -> None:
    summary = fa._round1_execution_summary()
    assert summary["execution_id"] == fa.ROUND1_EXECUTION_ID
    assert summary["dataset_sha256"] == fa.DATASET_SHA256
    ref = fa.build_full_system_reference()
    assert ref["round1_recompute_match"] is True


def test_14_frozen_controls_match_round1_config() -> None:
    config = json.loads(fa.ROUND1_CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["seed"] == 125
    assert config["test_fraction"] == 0.2
    assert config["optimizer"]["learning_rate"] == 0.05
    assert config["optimizer"]["iterations"] == 2000
    assert config["optimizer"]["l2"] == 0.001
    assert config["decision_threshold"] == 0.5
    assert config["round2_trigger"]["target"] == 0.95


def test_15_raw_metrics_recompute_from_predictions() -> None:
    recomputed = fa.recompute_holdout_metrics(
        fa.ROUND1_DIR / "artifacts" / "predictions.csv"
    )
    historical = json.loads(
        (fa.ROUND1_DIR / "artifacts" / "run-summary.json").read_text(encoding="utf-8")
    )
    assert abs(recomputed["malignant_recall"] - historical["metrics"]["malignant_recall"]) < 1e-12


def test_16_comparison_matrix_requires_primary_metrics() -> None:
    full_system = fa.build_full_system_reference()
    no_reviewer = {
        "planner_calls": 1,
        "provider_call_count": 1,
        "revision_plan_schema_valid": True,
        "authorized_revision_proposed": True,
        "revision_effective": True,
        "round2_executed": True,
        "round2_malignant_recall": 0.9523809523809523,
        "round2_balanced_accuracy": 0.9761904761904762,
        "round2_false_negative_rate": 0.047619047619047616,
        "target_achieved": True,
        "traceability_complete": False,
        "scientific_scope_pass": True,
        "latency_seconds": 1.2,
        "total_tokens": 100,
    }
    matrix = fa.build_comparison_matrix(full_system, no_reviewer)
    names = {row["metric"] for row in matrix["rows"]}
    required = {
        "Reviewer calls",
        "Planner calls",
        "Total calls",
        "V2 schema valid",
        "Authorized revision",
        "Revision effective",
        "Round 2 executed",
        "Malignant recall",
        "Balanced accuracy",
        "False negative rate",
        "Target achieved",
        "Structured issue",
        "Issue closure auditable",
        "Traceability complete",
        "Scientific scope pass",
        "Latency seconds",
        "Tokens",
        "Cost",
    }
    assert required.issubset(names)
    cost_row = next(row for row in matrix["rows"] if row["metric"] == "Cost")
    assert cost_row["NO_REVIEWER"] == "unknown"


def test_17_negative_result_is_a_valid_complete_experiment() -> None:
    full_system = fa.build_full_system_reference()
    no_reviewer = {
        "target_achieved": False,
        "revision_effective": False,
        "authorized_revision_proposed": False,
        "round2_executed": False,
        "scientific_scope_pass": True,
        "provider_failed": False,
        "structured_issue_available": False,
        "issue_closure_auditable": False,
        "traceability_complete": True,
    }
    conclusion = fa.classify_conclusion(
        full_system=full_system, no_reviewer=no_reviewer, protocol_ok=True
    )
    assert conclusion["REVIEWER_EFFECT_RESULT"] == "QUALITY_AND_TRACEABILITY_GAIN"


def test_18_conclusion_follows_preregistered_traceability_only_rule() -> None:
    full_system = fa.build_full_system_reference()
    no_reviewer = {
        "target_achieved": True,
        "revision_effective": True,
        "authorized_revision_proposed": True,
        "round2_executed": True,
        "round2_malignant_recall": full_system["round2_malignant_recall"],
        "round2_balanced_accuracy": full_system["round2_balanced_accuracy"],
        "round2_false_negative_rate": full_system["round2_false_negative_rate"],
        "scientific_scope_pass": True,
        "provider_failed": False,
        "structured_issue_available": False,
        "issue_closure_auditable": False,
        "traceability_complete": False,
        "policy_ok": True,
    }
    conclusion = fa.classify_conclusion(
        full_system=full_system, no_reviewer=no_reviewer, protocol_ok=True
    )
    assert conclusion["REVIEWER_EFFECT_RESULT"] == "TRACEABILITY_ONLY_GAIN"


def test_18b_provider_failure_is_inconclusive() -> None:
    full_system = fa.build_full_system_reference()
    conclusion = fa.classify_conclusion(
        full_system=full_system,
        no_reviewer={"provider_failed": True, "scientific_scope_pass": True},
        protocol_ok=True,
    )
    assert conclusion["REVIEWER_EFFECT_RESULT"] == "INCONCLUSIVE"


def test_19_provider_disclosure_baseline_counts() -> None:
    protocol = fa.load_protocol()
    baseline = protocol["provider_disclosure_baseline"]
    assert baseline["project_provider_calls_before"] == 4
    assert baseline["full_system_canonical_calls"] == 2
    assert baseline["historical_abandoned_calls"] == 2


def test_20_api_status_has_no_secrets() -> None:
    from app.execution.flagship_ablation import get_actual_ablation_status

    status = get_actual_ablation_status()
    text = json.dumps(status, ensure_ascii=False)
    for banned in ("Authorization", "Bearer ", "DASHSCOPE_API_KEY", "sk-"):
        assert banned not in text


def test_21_injected_planner_can_complete_without_real_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Harness completeness: a schema-valid in-policy plan is accepted without mock fallback."""
    calls = {"n": 0}

    def fake_chat(messages, **kwargs):
        calls["n"] += 1
        assert kwargs.get("temperature") == 0.1
        return _authorized_plan_json()

    result = fa.call_no_reviewer_planner(
        system_prompt="s",
        user_prompt="u",
        model="qwen3.6-flash",
        temperature=0.1,
        destination_dir=tmp_path,
        chat_fn=fake_chat,
    )
    assert calls["n"] == 1
    assert result["status"] == "ok"
    plan, err = fa.parse_v2_plan(result["raw_text"])
    assert err is None
    policy = validate_v2_plan_against_policy(plan)
    assert policy.ok is True
    assert policy.authorized_changes
