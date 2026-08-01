"""T02-B-004/005/006 explainable experiment revision contract tests."""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
from types import ModuleType

import pytest
from pydantic import ValidationError

from app.agents.experiment_designer import ExperimentDesignerAgent
from app.agents.scientific_reviewer import ScientificReviewerAgent
from app.contracts.revision import (
    IssueClosure,
    PlanVersion,
    ReviewFeedback,
    deserialize_revision_state,
)
from app.core.config import get_settings
from app.workflow.pipeline import run_pipeline_with_state
from tests.helpers_questions_fixture import write_minimal_questions_fixture


def _wave_b() -> ModuleType:
    """Load the Wave B API while keeping missing capability a test failure."""
    module_name = "app.workflow.explainable_revision"
    if importlib.util.find_spec(module_name) is None:
        pytest.fail(
            "T02 Wave B explainable revision capability is not implemented",
            pytrace=False,
        )
    return importlib.import_module(module_name)


def _blocking_feedback() -> ReviewFeedback:
    return ReviewFeedback(
        passed=False,
        reviewer_comments=["Add an evidence-backed negative control."],
        critical_issues=["The design has no negative control."],
        required_revisions=["Add a negative control and an AUROC metric."],
        risk_level="high",
        evidence_grounding_score=0.4,
        falsifiability_score=0.5,
        reproducibility_score=0.6,
        reference_reliability_score=0.7,
    )


def _clear_feedback() -> ReviewFeedback:
    return ReviewFeedback(
        passed=True,
        reviewer_comments=["The negative control and metric are now explicit."],
        risk_level="low",
        evidence_grounding_score=0.8,
        falsifiability_score=0.8,
        reproducibility_score=0.8,
        reference_reliability_score=0.8,
    )


def _v1() -> PlanVersion:
    return PlanVersion.create(
        run_id="wave-b-run",
        version_number=1,
        revision_iteration=1,
        hypothesis_generation={"hypotheses": [{"hypothesis": "H1"}]},
        experiment_design={
            "technical_details": "Initial prose.",
            "experiments": {
                "baselines": ["positive-control"],
                "metrics": ["accuracy"],
            },
        },
        review_feedback=_blocking_feedback(),
        prompt_fingerprints={"experiment_designer": "v1-input"},
    )


def _revised_experiment() -> dict:
    return {
        "technical_details": "Revised prose.",
        "datasets": {
            "source": "source-set",
            "target": "target-set",
            "evidence_ids": ["EV-1"],
        },
        "methods": "Controlled comparison.",
        "experiments": {
            "baselines": ["positive-control", "negative-control"],
            "metrics": ["accuracy", "AUROC"],
            "steps": ["fit", "evaluate", "bootstrap"],
            "safety_constraints": ["abort on data leakage"],
            "stopping_conditions": {"max_trials": 20},
            "evidence_refs": ["EV-1"],
        },
        "results": "pending",
        "reproducibility_checklist": ["fixed seed"],
        "execution_metadata": {"actual_execution": False},
    }


def test_experiment_revision_context_carries_previous_plan_and_full_feedback() -> None:
    """T02-B-004: the next experiment round gets all structured prior state."""
    api = _wave_b()
    version = _v1()
    issues = api.issues_for_revision(version.review_feedback, opened_in_version=1)
    failures = api.failure_reasons_from_feedback(version.review_feedback, issues)

    context = api.build_experiment_revision_context(
        previous_version=version,
        unresolved_issues=issues,
        failure_reasons=failures,
    ).model_dump(mode="json")

    assert context["previous_plan"] == {
        "hypothesis_generation": version.hypothesis_generation,
        "experiment_design": version.experiment_design,
    }
    assert context["previous_plan_version"]["version_id"] == "wave-b-run:v1"
    assert context["parent_version_id"] == "wave-b-run:v1"
    assert context["lineage"] == ["wave-b-run:v1", "wave-b-run:v2"]
    assert context["reviewer_feedback"] == _blocking_feedback().model_dump(mode="json")
    assert context["unresolved_issues"]
    assert context["failure_reasons"]
    assert all(item["failure_id"] and item["source"] for item in context["failure_reasons"])


def test_failure_reason_ids_are_stable_and_source_bound() -> None:
    api = _wave_b()
    feedback = _blocking_feedback()
    issues = api.issues_for_revision(feedback, opened_in_version=1)

    first = api.failure_reasons_from_feedback(feedback, issues)
    second = api.failure_reasons_from_feedback(feedback, issues)

    assert first == second
    assert {item.issue_id for item in first if item.issue_id} == {
        issue.issue_id for issue in issues
    }
    assert all(item.source == "scientific_reviewer" for item in first)


def test_explainable_mapping_has_required_machine_readable_fields() -> None:
    """T02-B-005: every important change explains issue, delta, evidence, and closure."""
    api = _wave_b()
    audit = api.assess_experiment_revision(
        previous_version=_v1(),
        revised_hypothesis={"hypotheses": [{"hypothesis": "H2"}]},
        revised_experiment=_revised_experiment(),
        final_feedback=_clear_feedback(),
        available_evidence_refs=["EV-1"],
    )

    assert audit.changes
    required = {
        "change_id",
        "issue_id",
        "reason",
        "before",
        "after",
        "evidence_refs",
        "affected_plan_section",
        "closure_status",
    }
    for change in audit.model_dump(mode="json")["changes"]:
        assert required <= change.keys()
        assert change["reason"]
        assert change["before"] != change["after"]
        assert change["evidence_refs"] == ["EV-1"]
    assert {change.issue_id for change in audit.changes} >= {
        issue.issue_id for issue in audit.issue_closures if issue.opened_in_version == 1
    }


def test_issue_closure_requires_change_evidence_and_final_reviewer_clearance() -> None:
    api = _wave_b()
    accepted = api.assess_experiment_revision(
        previous_version=_v1(),
        revised_hypothesis={"hypotheses": [{"hypothesis": "H2"}]},
        revised_experiment=_revised_experiment(),
        final_feedback=_clear_feedback(),
        available_evidence_refs=["EV-1"],
    )
    no_evidence = api.assess_experiment_revision(
        previous_version=_v1(),
        revised_hypothesis={"hypotheses": [{"hypothesis": "H2"}]},
        revised_experiment=_revised_experiment(),
        final_feedback=_clear_feedback(),
        available_evidence_refs=[],
    )
    still_open = api.assess_experiment_revision(
        previous_version=_v1(),
        revised_hypothesis={"hypotheses": [{"hypothesis": "H2"}]},
        revised_experiment=_revised_experiment(),
        final_feedback=_blocking_feedback(),
        available_evidence_refs=["EV-1"],
    )

    assert accepted.accepted
    assert all(issue.status == "resolved" for issue in accepted.issue_closures)
    assert all(issue.resolution_note for issue in accepted.issue_closures)
    assert not no_evidence.accepted
    assert all(issue.status == "open" for issue in no_evidence.issue_closures)
    assert any("evidence" in reason.lower() for reason in no_evidence.blocking_reasons)
    assert not still_open.accepted
    assert any(issue.status == "open" for issue in still_open.issue_closures)
    assert still_open.stop_reason == "max_revision_iterations_exhausted"


def test_non_substantive_rewrites_and_bookkeeping_are_rejected() -> None:
    """T02-B-006: prose, iteration, and history changes are not experiment changes."""
    api = _wave_b()
    previous = {
        "technical_details": "Fit the model and report uncertainty.",
        "methods": "Use a deterministic split.",
        "experiments": {"baselines": ["B1"], "metrics": ["M1"]},
        "revision_iteration": 1,
        "revision_history": [],
    }
    rewritten = {
        **previous,
        "technical_details": "Report uncertainty after fitting the model.",
        "methods": "Apply one deterministic split.",
        "revision_iteration": 2,
        "revision_history": ["rewrote prose"],
    }

    assert api.substantive_experiment_diff(previous, rewritten) == []
    previous_version = PlanVersion.create(
        run_id="rewrite-only",
        version_number=1,
        revision_iteration=1,
        experiment_design=previous,
        review_feedback=_blocking_feedback(),
    )
    audit = api.assess_experiment_revision(
        previous_version=previous_version,
        revised_hypothesis=previous_version.hypothesis_generation,
        revised_experiment=rewritten,
        final_feedback=_clear_feedback(),
        available_evidence_refs=["EV-1"],
    )
    assert not audit.accepted
    assert audit.changes == []
    assert "no_substantive_experiment_change" in audit.blocking_reasons


@pytest.mark.parametrize(
    ("section", "before", "after"),
    [
        ("experimental_variables", {"variables": ["x"]}, {"variables": ["x", "z"]}),
        ("control_groups", {"baselines": ["B1"]}, {"baselines": ["B1", "B2"]}),
        ("experiment_steps", {"steps": ["fit"]}, {"steps": ["fit", "test"]}),
        ("evaluation_metrics", {"metrics": ["M1"]}, {"metrics": ["M1", "M2"]}),
        ("safety_constraints", {"safety_constraints": ["S1"]}, {"safety_constraints": ["S1", "S2"]}),
        ("stopping_conditions", {"stopping_conditions": {"n": 5}}, {"stopping_conditions": {"n": 10}}),
        ("evidence_references", {"evidence_refs": ["EV-1"]}, {"evidence_refs": ["EV-1", "EV-2"]}),
    ],
)
def test_substantive_detector_accepts_structural_experiment_changes(
    section: str,
    before: dict,
    after: dict,
) -> None:
    api = _wave_b()
    changes = api.substantive_experiment_diff(
        {"experiments": before},
        {"experiments": after},
    )
    assert [change.section for change in changes] == [section]


def test_revision_change_rejects_false_resolution_claims() -> None:
    api = _wave_b()
    with pytest.raises(ValidationError, match="resolved change requires evidence_refs"):
        api.RevisionChange(
            change_id="change-1",
            issue_id="required_revision:one",
            reason="Changed a metric.",
            before=["accuracy"],
            after=["accuracy", "AUROC"],
            evidence_refs=[],
            affected_plan_section="evaluation_metrics",
            closure_status="resolved",
        )
    with pytest.raises(ValidationError, match="before and after must differ"):
        api.RevisionChange(
            change_id="change-2",
            issue_id="required_revision:one",
            reason="Only rewrote text.",
            before=["accuracy"],
            after=["accuracy"],
            evidence_refs=["EV-1"],
            affected_plan_section="evaluation_metrics",
            closure_status="resolved",
        )


def test_issue_closure_round_trip_and_legacy_state_remain_compatible() -> None:
    closure = IssueClosure(
        issue_id="required_revision:stable",
        category="required_revision",
        description="Add a control.",
        status="resolved",
        opened_in_version=1,
        closed_in_version=2,
        resolution_note="change-1; evidence=EV-1",
    )
    assert IssueClosure.model_validate_json(closure.model_dump_json()) == closure

    restored = deserialize_revision_state(
        {
            "run_id": "legacy-wave-b",
            "iteration": 1,
            "plan_versions": [{"version": 1, "experiment_design": {}}],
        }
    )
    assert restored.context.issue_closures == []
    assert restored.versions[0].version_id == "legacy-wave-b:v1"


def _configure_pipeline(monkeypatch, tmp_path) -> str:
    questions = write_minimal_questions_fixture(tmp_path / "questions_125.json")
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(questions))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_REVIEW_FAIL", "true")
    get_settings.cache_clear()
    return "Q001"


def test_pipeline_experiment_prompt_and_trace_preserve_revision_audit(
    monkeypatch,
    tmp_path,
) -> None:
    """The real two-round pipeline carries context and records a replayable sidecar."""
    question_id = _configure_pipeline(monkeypatch, tmp_path)
    captured_inputs: list[dict] = []
    captured_agents: list[ExperimentDesignerAgent] = []
    original_run = ExperimentDesignerAgent.run

    def capture(self, input_data, state, step_index=0):
        captured_inputs.append(copy.deepcopy(input_data))
        captured_agents.append(self)
        return original_run(self, input_data, state, step_index)

    monkeypatch.setattr(ExperimentDesignerAgent, "run", capture)
    try:
        plan, state = run_pipeline_with_state(question_id, mock_mode=True)
    finally:
        get_settings.cache_clear()

    assert len(captured_inputs) == 2
    second = captured_inputs[1]
    expected = {
        "previous_plan",
        "previous_plan_version",
        "parent_version_id",
        "lineage",
        "unresolved_issues",
        "failure_reasons",
        "reviewer_feedback",
    }
    assert expected <= second["revision_context"].keys()
    assert ReviewFeedback.from_review_result(second["review_result"])
    assert "revision_context" not in second["review_result"]
    user_payload = json.loads(captured_agents[1].build_messages(second)[1]["content"])
    assert expected <= user_payload["revision_context"].keys()
    assert ReviewFeedback.from_review_result(user_payload["review_result"])

    audit_events = [
        event for event in state.agent_trace
        if event.get("revision_audit")
    ]
    assert len(audit_events) == 1
    audit = audit_events[0]["revision_audit"]
    assert [version["version_id"] for version in audit_events[0]["plan_versions"]] == [
        f"{state.run_id}:v1",
    ]
    assert audit["parent_version_id"] == f"{state.run_id}:v1"
    assert audit["lineage"] == [f"{state.run_id}:v1", f"{state.run_id}:v2"]
    assert audit["reviewer_feedback"]
    assert audit["failure_reasons"]
    assert audit["issue_closures"]
    # Existing mock output repeats the experiment; Wave B must expose and block it.
    assert "no_substantive_experiment_change" in audit["blocking_reasons"]
    assert audit["stop_reason"] == "no_improvement"
    assert audit_events[0]["revision_control"]["version_ids"] == [
        f"{state.run_id}:v1"
    ]
    assert not audit_events[0]["two_round_case_report"]["passed"]
    assert plan.validation_status not in {"ready_for_validation", "validated"}


def test_pipeline_maps_a_substantive_second_round_change_and_closes_issues(
    monkeypatch,
    tmp_path,
) -> None:
    question_id = _configure_pipeline(monkeypatch, tmp_path)
    original_experiment_run = ExperimentDesignerAgent.run
    experiment_calls = 0
    review_calls = 0

    def revised_second_round(self, input_data, state, step_index=0):
        nonlocal experiment_calls
        experiment_calls += 1
        result = original_experiment_run(self, input_data, state, step_index)
        if experiment_calls == 2:
            result = copy.deepcopy(result)
            result["experiments"] = copy.deepcopy(result.get("experiments") or {})
            result["experiments"]["baselines"] = list(
                result["experiments"].get("baselines") or []
            ) + ["reviewer-requested-negative-control"]
            result["experiments"]["evidence_refs"] = [
                card.id for card in state.retrieved_evidence[:1]
            ]
        return result

    def controlled_reviewer(self, input_data, state, step_index=0):
        nonlocal review_calls
        review_calls += 1
        feedback = _blocking_feedback() if review_calls == 1 else _clear_feedback()
        return feedback.model_dump(mode="json")

    monkeypatch.setattr(ExperimentDesignerAgent, "run", revised_second_round)
    monkeypatch.setattr(ScientificReviewerAgent, "run", controlled_reviewer)
    try:
        _plan, state = run_pipeline_with_state(question_id, mock_mode=True)
    finally:
        get_settings.cache_clear()

    audit = next(
        event["revision_audit"]
        for event in state.agent_trace
        if event.get("revision_audit")
    )
    assert audit["accepted"]
    assert audit["changes"]
    assert all(change["reason"] and change["evidence_refs"] for change in audit["changes"])
    assert all(issue["status"] == "resolved" for issue in audit["issue_closures"])
    assert audit["blocking_reasons"] == []
    trace = next(event for event in state.agent_trace if event.get("revision_audit"))
    assert [version["version_id"] for version in trace["plan_versions"]] == [
        f"{state.run_id}:v1",
        f"{state.run_id}:v2",
    ]
    assert trace["revision_control"]["status"] == "completed"
    assert trace["two_round_case_report"]["passed"]
    assert trace["two_round_case_report"]["responded_issue_count"] >= 1


def test_pipeline_keeps_budget_exhaustion_as_an_explicit_blocker(
    monkeypatch,
    tmp_path,
) -> None:
    question_id = _configure_pipeline(monkeypatch, tmp_path)
    blocking = _blocking_feedback().model_dump(mode="json")

    def always_block(self, input_data, state, step_index=0):
        return copy.deepcopy(blocking)

    monkeypatch.setattr(ScientificReviewerAgent, "run", always_block)
    try:
        plan, state = run_pipeline_with_state(question_id, mock_mode=True)
    finally:
        get_settings.cache_clear()

    audit = next(
        event["revision_audit"]
        for event in state.agent_trace
        if event.get("revision_audit")
    )
    assert not audit["accepted"]
    assert audit["stop_reason"] == "no_improvement"
    assert any(issue["status"] == "open" for issue in audit["issue_closures"])
    assert plan.validation_status not in {"ready_for_validation", "validated"}
