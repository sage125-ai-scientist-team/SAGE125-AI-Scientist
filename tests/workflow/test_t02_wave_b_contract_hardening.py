"""Red-to-green coverage for the remaining T02 Wave B contract gaps."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.contracts.revision import PlanVersion, ReviewFeedback
from app.contracts.validation import HumanFeedbackDirective
from app.agents.experiment_designer import ExperimentDesignerAgent
from app.agents.hypothesis_generator import HypothesisGeneratorAgent
from app.agents.scientific_reviewer import ScientificReviewerAgent
from app.core.config import get_settings
from app.workflow import explainable_revision as revision_api
from app.workflow import pipeline
from tests.helpers_questions_fixture import write_minimal_questions_fixture


PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRIC_CASE_PATH = (
    PROJECT_ROOT
    / "docs"
    / "modules"
    / "T02"
    / "evidence"
    / "T02_METRIC_003_CASE.json"
)
METRIC_RESULT_PATH = METRIC_CASE_PATH.with_name("T02_METRIC_003_RESULT.json")


def _blocking_feedback() -> ReviewFeedback:
    return ReviewFeedback(
        passed=False,
        reviewer_comments=["Add a negative control."],
        critical_issues=["The negative control is missing."],
        required_revisions=["Add a negative control and AUROC."],
        risk_level="high",
        evidence_grounding_score=0.3,
        falsifiability_score=0.4,
        reproducibility_score=0.5,
        reference_reliability_score=0.6,
    )


def _clear_feedback() -> ReviewFeedback:
    return ReviewFeedback(
        passed=True,
        reviewer_comments=["The blocking issue is resolved."],
        risk_level="low",
        evidence_grounding_score=0.8,
        falsifiability_score=0.8,
        reproducibility_score=0.9,
        reference_reliability_score=0.9,
    )


def _v1() -> PlanVersion:
    return PlanVersion.create(
        run_id="wave-b-hardening",
        version_number=1,
        revision_iteration=1,
        hypothesis_generation={
            "hypotheses": [
                {"hypothesis": "H1", "overall_score": 0.45},
                {"hypothesis": "H0", "overall_score": 0.25},
            ],
            "recommended_hypothesis_index": 0,
        },
        experiment_design={
            "experiments": {
                "baselines": ["positive-control"],
                "metrics": ["accuracy"],
                "evidence_refs": ["EV-1"],
            }
        },
        review_feedback=_blocking_feedback(),
    )


def _evidence_bundle() -> EvidenceBundle:
    card = EvidenceCardContract(
        evidence_id="EV-1",
        source_id="paper-1",
        source_type="paper",
        title="Controlled evaluation",
        quoted_text="Negative controls expose leakage in comparative evaluation.",
        locator={"section": "Methods"},
        verification_status="pending",
    )
    return EvidenceBundle(
        bundle_id="bundle-wave-b",
        evidences=[card],
        links=[
            ClaimEvidenceLink(
                claim_id="claim-negative-control",
                evidence_id="EV-1",
                relation="supports",
                confidence=0.8,
                validation_status="pending",
            )
        ],
    )


def _human_feedback() -> HumanFeedbackDirective:
    return HumanFeedbackDirective(
        feedback_id="feedback-1",
        target_version_id="wave-b-hardening:v1",
        disposition="accepted",
        instructions=("Keep the negative control explicit.",),
        original_feedback_sha256="a" * 64,
    )


def _context():
    version = _v1()
    issues = revision_api.issues_for_revision(
        version.review_feedback,
        opened_in_version=1,
    )
    failures = revision_api.failure_reasons_from_feedback(
        version.review_feedback,
        issues,
    )
    return revision_api.build_experiment_revision_context(
        previous_version=version,
        unresolved_issues=issues,
        failure_reasons=failures,
        evidence_bundle=_evidence_bundle(),
        human_feedback=_human_feedback(),
    )


def test_revision_context_is_a_strict_sibling_of_review_feedback() -> None:
    """The revision carrier must not violate ReviewFeedback(extra='forbid')."""
    feedback = _blocking_feedback()
    payload = revision_api.inject_revision_context(
        {
            "revision_iteration": 2,
            "review_result": feedback.model_dump(mode="json"),
        },
        _context(),
    )

    assert ReviewFeedback.from_review_result(payload["review_result"]) == feedback
    assert "revision_context" not in payload["review_result"]
    assert payload["revision_context"]["parent_version_id"] == "wave-b-hardening:v1"

    envelope = revision_api.RevisionRoundInput.model_validate(
        {
            "review_result": payload["review_result"],
            "revision_context": payload["revision_context"],
        }
    )
    assert revision_api.RevisionRoundInput.model_validate_json(
        envelope.model_dump_json()
    ) == envelope
    with pytest.raises(ValidationError):
        revision_api.RevisionRoundInput.model_validate(
            {
                **envelope.model_dump(mode="json"),
                "unknown_field": "rejected",
            }
        )


def test_t01_bundle_and_t03_human_feedback_reach_revision_messages() -> None:
    """B-013/015: frozen T01/T03 objects survive the real message boundary."""
    payload = revision_api.inject_revision_context(
        {
            "revision_iteration": 2,
            "review_result": _blocking_feedback().model_dump(mode="json"),
            "question_type": "causal",
        },
        _context(),
    )
    agent_type = getattr(
        revision_api,
        "RevisionAwareExperimentDesignerAgent",
        None,
    )
    assert agent_type is not None, "workflow lacks a typed revision-aware Agent adapter"
    user_payload = json.loads(agent_type().build_messages(payload)[1]["content"])

    assert user_payload["review_result"] == _blocking_feedback().model_dump(mode="json")
    context = user_payload["revision_context"]
    assert context["evidence_bundle"]["bundle_id"] == "bundle-wave-b"
    assert context["human_feedback"]["feedback_id"] == "feedback-1"


def test_revision_controller_is_bounded_idempotent_and_recoverable() -> None:
    """B-007/010/012: duplicate events and failures cannot create versions forever."""
    controller_type = getattr(revision_api, "RevisionExecutionController", None)
    assert controller_type is not None, "bounded revision controller is missing"
    controller = controller_type.create(
        run_id="wave-b-hardening",
        max_iterations=2,
        max_retries=1,
    )

    assert controller.claim_event("review-v1")
    assert not controller.claim_event("review-v1")
    assert controller.record_version("wave-b-hardening:v1")
    assert not controller.record_version("wave-b-hardening:v1")
    controller.pause("awaiting_human_feedback")

    restored = controller_type.deserialize(controller.serialize())
    assert restored.state.status == "paused"
    restored.resume()
    assert restored.record_failure("timeout") == "retry"
    assert restored.record_failure("empty_reviewer") == "stopped"
    assert restored.state.stop_reason == "retry_budget_exhausted"
    assert restored.state.version_ids == ("wave-b-hardening:v1",)


def test_revision_retry_executes_once_and_empty_output_stops() -> None:
    controller = revision_api.RevisionExecutionController.create(
        run_id="retry-run",
        max_retries=1,
    )
    calls = 0

    def timeout_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("transient")
        return {"status": "recovered"}

    assert revision_api.run_revision_step_with_retry(
        timeout_once,
        controller=controller,
        step_name="reviewer",
    ) == {"status": "recovered"}
    assert calls == 2

    empty = revision_api.RevisionExecutionController.create(
        run_id="empty-run",
        max_retries=0,
    )
    with pytest.raises(ValueError, match="returned empty output"):
        revision_api.run_revision_step_with_retry(
            lambda: {},
            controller=empty,
            step_name="reviewer",
        )
    assert empty.state.status == "stopped"
    assert empty.state.stop_reason == "retry_budget_exhausted"


def test_revision_checkpoint_rejects_unknown_fields_and_supports_rollback() -> None:
    controller = revision_api.RevisionExecutionController.create(
        run_id="rollback-run"
    )
    controller.record_version("rollback-run:v1")
    controller.advance_iteration()
    controller.record_version("rollback-run:v2")
    assert controller.rollback_last_version() == "rollback-run:v2"
    assert controller.state.version_ids == ("rollback-run:v1",)
    payload = controller.state.model_dump(mode="json")
    payload["unknown"] = True
    with pytest.raises(ValidationError):
        revision_api.RevisionExecutionState.model_validate(payload)


def test_pipeline_uses_one_strict_revision_type_for_all_three_agents(
    monkeypatch,
    tmp_path,
) -> None:
    questions = write_minimal_questions_fixture(tmp_path / "questions_125.json")
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(questions))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_REVIEW_FAIL", "true")
    monkeypatch.setattr(pipeline, "generate_run_id", lambda: "wave-b-hardening")
    get_settings.cache_clear()

    captured_messages: dict[str, dict] = {}
    original_hypothesis_run = HypothesisGeneratorAgent.run
    original_experiment_run = ExperimentDesignerAgent.run
    original_reviewer_run = ScientificReviewerAgent.run

    def capture_hypothesis(self, input_data, state, step_index=0):
        if input_data.get("revision_iteration") == 2:
            captured_messages["hypothesis"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
        return original_hypothesis_run(self, input_data, state, step_index)

    def capture_experiment(self, input_data, state, step_index=0):
        if input_data.get("revision_iteration") == 2:
            captured_messages["experiment"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
        return original_experiment_run(self, input_data, state, step_index)

    def capture_reviewer(self, input_data, state, step_index=0):
        if input_data.get("revision_iteration") == 2:
            captured_messages["reviewer"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
        return original_reviewer_run(self, input_data, state, step_index)

    monkeypatch.setattr(HypothesisGeneratorAgent, "run", capture_hypothesis)
    monkeypatch.setattr(ExperimentDesignerAgent, "run", capture_experiment)
    monkeypatch.setattr(ScientificReviewerAgent, "run", capture_reviewer)
    try:
        pipeline.run_pipeline_with_state(
            "Q001",
            mock_mode=True,
            evidence_bundle=_evidence_bundle(),
            human_feedback_directive=_human_feedback(),
        )
    finally:
        get_settings.cache_clear()

    assert set(captured_messages) == {"hypothesis", "experiment", "reviewer"}
    for message in captured_messages.values():
        assert ReviewFeedback.from_review_result(message["review_result"])
        assert "revision_context" not in message["review_result"]
        assert message["revision_context"]["evidence_bundle"]["bundle_id"] == (
            "bundle-wave-b"
        )
        assert message["revision_context"]["human_feedback"]["feedback_id"] == (
            "feedback-1"
        )


def test_audit_records_score_change_ranking_and_no_improvement_stop() -> None:
    """B-007/016/017: audit evidence includes score delta and candidate ranking."""
    revised_hypothesis = {
        "hypotheses": [
            {"hypothesis": "H2", "overall_score": 0.85},
            {"hypothesis": "H1", "overall_score": 0.55},
        ],
        "recommended_hypothesis_index": 0,
    }
    revised_experiment = {
        "experiments": {
            "baselines": ["positive-control", "negative-control"],
            "metrics": ["accuracy", "AUROC"],
            "evidence_refs": ["EV-1"],
        }
    }
    audit = revision_api.assess_experiment_revision(
        previous_version=_v1(),
        revised_hypothesis=revised_hypothesis,
        revised_experiment=revised_experiment,
        final_feedback=_clear_feedback(),
        available_evidence_refs=["EV-1"],
    )

    assert audit.score_changes["evidence_grounding_score"].before == 0.3
    assert audit.score_changes["evidence_grounding_score"].after == 0.8
    assert [item.rank for item in audit.candidate_hypothesis_ranking] == [1, 2]
    assert audit.candidate_hypothesis_ranking[0].overall_score == 0.85
    assert audit.responded_issue_count >= 1

    unchanged = revision_api.assess_experiment_revision(
        previous_version=_v1(),
        revised_hypothesis=_v1().hypothesis_generation,
        revised_experiment=_v1().experiment_design,
        final_feedback=_clear_feedback(),
        available_evidence_refs=["EV-1"],
    )
    assert unchanged.stop_reason == "no_improvement"


def test_metric_003_case_report_is_round_trip_safe_and_ready_gated() -> None:
    """B-018/METRIC-003/B-020: one V1 issue must be reproducibly answered."""
    manifest = json.loads(METRIC_CASE_PATH.read_text(encoding="utf-8"))
    v1 = manifest["v1"]
    v2 = manifest["v2"]
    previous_version = PlanVersion.create(
        run_id=v1["run_id"],
        version_number=1,
        revision_iteration=1,
        hypothesis_generation=v1["hypothesis_generation"],
        experiment_design=v1["experiment_design"],
        review_feedback=v1["review_feedback"],
    )
    audit = revision_api.assess_experiment_revision(
        previous_version=previous_version,
        revised_hypothesis=v2["hypothesis_generation"],
        revised_experiment=v2["experiment_design"],
        final_feedback=v2["review_feedback"],
        available_evidence_refs=manifest["available_evidence_refs"],
    )
    report_type = getattr(revision_api, "TwoRoundCaseReport", None)
    assert report_type is not None, "METRIC-003 case report contract is missing"
    report = report_type.from_audit(
        case_id=manifest["case_id"],
        audit=audit,
        input_fingerprints=manifest["input_fingerprints"],
    )

    assert report.metric_id == "T02-METRIC-003"
    assert report.responded_issue_count >= 1
    assert report.passed
    assert report_type.model_validate_json(report.model_dump_json()) == report
    recorded = json.loads(METRIC_RESULT_PATH.read_text(encoding="utf-8"))
    assert recorded["raw_result"] == report.model_dump(mode="json")
    assert recorded["metrics"] == {
        "passed": True,
        "responded_issue_count": report.responded_issue_count,
    }

    readiness = revision_api.evaluate_wave_b_readiness(
        audit=audit,
        case_report=report,
        evidence_bundle=_evidence_bundle(),
        branch_up_to_date=True,
        quality_gates_passed=True,
    )
    assert readiness.ready
    assert readiness.blocking_reasons == ()
