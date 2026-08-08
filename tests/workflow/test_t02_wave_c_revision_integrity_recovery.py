"""T02-C-004/005 revision integrity, idempotency, and recovery tests."""

from __future__ import annotations

import importlib
import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.agents.base import AgentOutputError
from app.contracts.execution import ExecutionResult
from app.contracts.revision import IssueClosure, PlanVersion, ReviewFeedback
from app.workflow import explainable_revision as revision_api
from app.workflow.revision_feedback import build_revision_feedback
from tests.workflow.test_t02_wave_c_execution_multimodal_feedback import (
    _failed_execution,
    _multimodal_artifact,
    _successful_execution,
)


GENERATED_AT = "2026-08-08T08:00:00+00:00"


def _recovery_api() -> Any:
    try:
        return importlib.import_module("app.workflow.revision_recovery")
    except ModuleNotFoundError as exc:
        if exc.name == "app.workflow.revision_recovery":
            pytest.fail(
                "T02-C-005: durable revision recovery coordinator is missing",
                pytrace=False,
            )
        raise


def _blocking_feedback() -> ReviewFeedback:
    return ReviewFeedback(
        passed=False,
        reviewer_comments=["Add an explicit negative control."],
        critical_issues=["No negative control is defined."],
        required_revisions=["Add a negative control and stopping rule."],
        risk_level="high",
        evidence_grounding_score=0.5,
        falsifiability_score=0.4,
        reproducibility_score=0.5,
        reference_reliability_score=0.6,
    )


def _clear_feedback() -> ReviewFeedback:
    return ReviewFeedback(
        passed=True,
        reviewer_comments=["The control and stopping rule are now explicit."],
        critical_issues=[],
        required_revisions=[],
        risk_level="low",
        evidence_grounding_score=0.8,
        falsifiability_score=0.8,
        reproducibility_score=0.9,
        reference_reliability_score=0.8,
    )


def _open_issues() -> list[IssueClosure]:
    return revision_api.issues_for_revision(
        _blocking_feedback(),
        opened_in_version=1,
    )


def _v1(*, with_feedback: bool = True) -> PlanVersion:
    return PlanVersion.create(
        run_id="wave-c-integrity",
        version_number=1,
        revision_iteration=1,
        hypothesis_generation={"hypotheses": [{"hypothesis": "H1"}]},
        experiment_design={
            "experiments": {
                "baselines": ["positive-control"],
                "metrics": ["accuracy"],
            }
        },
        review_feedback=_blocking_feedback() if with_feedback else None,
        issue_closures=_open_issues() if with_feedback else (),
    )


def _resolved_issues() -> list[IssueClosure]:
    return [
        issue.model_copy(
            update={
                "status": "resolved",
                "closed_in_version": 2,
                "resolution_note": "change-v2; evidence=EV-1",
            },
            deep=True,
        )
        for issue in _open_issues()
    ]


def _v2() -> PlanVersion:
    return PlanVersion.create(
        run_id="wave-c-integrity",
        version_number=2,
        parent_version_id="wave-c-integrity:v1",
        revision_iteration=2,
        hypothesis_generation={"hypotheses": [{"hypothesis": "H1"}]},
        experiment_design={
            "experiments": {
                "baselines": ["negative-control", "positive-control"],
                "metrics": ["accuracy"],
                "stopping_conditions": ["stop below 0.5"],
                "evidence_refs": ["EV-1"],
            }
        },
        review_feedback=_clear_feedback(),
        issue_closures=_resolved_issues(),
    )


def _complete_feedback():
    return build_revision_feedback(
        execution_result=_successful_execution(),
        multimodal_artifacts=[_multimodal_artifact()],
    )


def _context():
    previous = _v1()
    return revision_api.build_experiment_revision_context(
        previous_version=previous,
        unresolved_issues=_open_issues(),
        failure_reasons=revision_api.failure_reasons_from_feedback(
            _blocking_feedback(),
            _open_issues(),
        ),
        wave_c_feedback=_complete_feedback(),
        generated_at=GENERATED_AT,
    )


def _accepted_audit():
    return revision_api.assess_experiment_revision(
        previous_version=_v1(),
        revised_hypothesis={"hypotheses": [{"hypothesis": "H1"}]},
        revised_experiment=_v2().experiment_design,
        final_feedback=_clear_feedback(),
        available_evidence_refs=["EV-1"],
    )


def test_T02_C_004_complete_context_is_cross_checked_and_traceable() -> None:
    context = _context()
    integrity = context.integrity

    assert integrity is not None
    assert integrity.reviewer_feedback.review_id.startswith("review:")
    assert integrity.reviewer_feedback.critical_issues == tuple(
        _blocking_feedback().critical_issues
    )
    assert integrity.reviewer_feedback.required_revisions == tuple(
        _blocking_feedback().required_revisions
    )
    assert integrity.reviewer_feedback.comments == tuple(
        _blocking_feedback().reviewer_comments
    )
    assert integrity.reviewer_feedback.severity == "high"

    execution = context.wave_c_feedback.execution
    assert execution.execution_id == "execution-wave-c-success"
    assert execution.status == "succeeded"
    assert execution.metrics[0].unit == "ratio"
    assert execution.artifacts[0].artifact_id == "metrics-main"
    assert execution.failure is None
    assert execution.output.stdout_bytes > 0

    multimodal = context.wave_c_feedback.multimodal[0]
    assert multimodal.modality == "chart"
    assert multimodal.source_path == "fixtures/chart-page-7.csv"
    assert multimodal.row_count == 2
    assert multimodal.units == ("ratio",)
    assert multimodal.confidence == 0.93
    assert multimodal.validation_status == "passed"

    assert all(
        transition.previous_status == "open"
        and transition.current_status == "open"
        and transition.closure_reason is None
        for transition in integrity.issue_closure_state
    )
    assert integrity.lineage_provenance.source_version_id == (
        "wave-c-integrity:v1"
    )
    assert integrity.lineage_provenance.parent_plan_version_id == (
        "wave-c-integrity:v1"
    )
    assert integrity.lineage_provenance.generated_version_id == (
        "wave-c-integrity:v2"
    )
    assert integrity.lineage_provenance.generated_at == GENERATED_AT
    assert len(integrity.lineage_provenance.context_hash) == 64


def test_T02_C_004_missing_reviewer_feedback_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="Reviewer feedback"):
        revision_api.build_experiment_revision_context(
            previous_version=_v1(with_feedback=False),
            unresolved_issues=[],
            failure_reasons=[],
            wave_c_feedback=_complete_feedback(),
            generated_at=GENERATED_AT,
        )


def test_T02_C_004_missing_execution_or_multimodal_summary_fails() -> None:
    multimodal_only = build_revision_feedback(
        multimodal_artifacts=[_multimodal_artifact()]
    )
    execution_only = build_revision_feedback(
        execution_result=_successful_execution()
    )

    for incomplete in (multimodal_only, execution_only):
        with pytest.raises(ValueError, match="complete execution and multimodal"):
            revision_api.build_experiment_revision_context(
                previous_version=_v1(),
                unresolved_issues=_open_issues(),
                failure_reasons=[],
                wave_c_feedback=incomplete,
                generated_at=GENERATED_AT,
            )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_provenance", "lineage provenance"),
        ("version_mismatch", "generated version"),
    ],
)
def test_T02_C_004_provenance_loss_or_version_mismatch_fails(
    mutation: str,
    message: str,
) -> None:
    payload = _context().model_dump(mode="python")
    lineage = payload["integrity"]["lineage_provenance"]
    if mutation == "missing_provenance":
        lineage.pop("source_version_id")
    else:
        lineage["generated_version_id"] = "wave-c-integrity:v3"

    with pytest.raises(ValidationError, match=message):
        revision_api.ExperimentRevisionContext.model_validate(payload)


def test_T02_C_004_t08_consumer_summary_needs_no_internal_object_parsing() -> None:
    recovery = _recovery_api()
    coordinator = recovery.RevisionRecoveryCoordinator.create(
        run_id="wave-c-integrity",
        issue_closures=_open_issues(),
    )
    coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )
    coordinator.apply_version_event(
        event_id="revision-generated-v2",
        event_type="revision_event",
        version=_v2(),
    )
    coordinator.set_issue_closures(_resolved_issues())
    coordinator.controller.complete()

    summary = revision_api.build_revision_consumer_summary(
        audit=_accepted_audit(),
        plan_versions=coordinator.list_versions(),
        revision_control=coordinator.controller.state,
        integrity=_context().integrity,
    )
    payload = summary.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["version"] == {
        "source_version_id": "wave-c-integrity:v1",
        "parent_plan_version_id": "wave-c-integrity:v1",
        "generated_version_id": "wave-c-integrity:v2",
        "generated_at": GENERATED_AT,
        "context_hash": _context().integrity.lineage_provenance.context_hash,
    }
    assert payload["status"] == "completed"
    assert payload["stop_reason"] is None
    assert payload["issues"]
    assert payload["diff"]
    assert payload["status_events"][-1]["event_type"] == "revision_completed"
    assert len(payload["summary_hash"]) == 64
    for internal in (
        "previous_plan",
        "hypothesis_generation",
        "experiment_design",
        "stdout",
        '"rows"',
    ):
        assert internal not in serialized


def test_T02_C_005_duplicate_callback_creates_one_plan_version() -> None:
    recovery = _recovery_api()
    coordinator = recovery.RevisionRecoveryCoordinator.create(
        run_id="wave-c-integrity",
        issue_closures=_open_issues(),
    )

    first = coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )
    duplicate = coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.duplicate is True
    assert [item.version_id for item in coordinator.list_versions()] == [
        "wave-c-integrity:v1"
    ]


def test_T02_C_005_repeated_revision_event_is_idempotent() -> None:
    recovery = _recovery_api()
    coordinator = recovery.RevisionRecoveryCoordinator.create(
        run_id="wave-c-integrity",
        issue_closures=_open_issues(),
    )
    coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )
    first = coordinator.apply_version_event(
        event_id="revision-generated-v2",
        event_type="revision_event",
        version=_v2(),
    )
    repeated = coordinator.apply_version_event(
        event_id="revision-generated-v2",
        event_type="revision_event",
        version=_v2(),
    )

    assert first.created and not repeated.created and repeated.duplicate
    assert len(coordinator.list_versions()) == 2


def test_T02_C_005_interrupted_iteration_resumes_without_duplicate() -> None:
    recovery = _recovery_api()
    coordinator = recovery.RevisionRecoveryCoordinator.create(
        run_id="wave-c-integrity",
        issue_closures=_open_issues(),
    )
    coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )
    assert coordinator.begin_event(
        "revision-generated-v2",
        "revision_event",
    ) == "started"
    coordinator.controller.pause("interrupted:experiment_designer")

    restored = recovery.RevisionRecoveryCoordinator.deserialize(
        coordinator.serialize()
    )
    assert restored.controller.state.status == "paused"
    assert [item.version_id for item in restored.list_versions()] == [
        "wave-c-integrity:v1"
    ]
    restored.controller.resume()
    resumed = restored.apply_version_event(
        event_id="revision-generated-v2",
        event_type="revision_event",
        version=_v2(),
    )
    duplicate = restored.apply_version_event(
        event_id="revision-generated-v2",
        event_type="revision_event",
        version=_v2(),
    )

    assert resumed.created and resumed.resumed
    assert duplicate.duplicate and not duplicate.created
    assert [item.version_id for item in restored.list_versions()] == [
        "wave-c-integrity:v1",
        "wave-c-integrity:v2",
    ]


def test_T02_C_005_llm_timeout_retry_preserves_partial_state() -> None:
    recovery = _recovery_api()
    coordinator = recovery.RevisionRecoveryCoordinator.create(
        run_id="wave-c-integrity",
        issue_closures=_open_issues(),
        max_retries=1,
    )
    coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )
    calls = 0

    def timeout_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("controlled timeout")
        return {"status": "recovered"}

    result = revision_api.run_revision_step_with_retry(
        timeout_once,
        controller=coordinator.controller,
        step_name="experiment_designer",
    )
    restored = recovery.RevisionRecoveryCoordinator.deserialize(
        coordinator.serialize()
    )

    assert result == {"status": "recovered"}
    assert restored.controller.state.retry_count == 1
    assert restored.controller.state.failure_reasons == (
        "experiment_designer:TimeoutError",
    )
    assert restored.controller.state.status == "active"
    assert [item.version_id for item in restored.list_versions()] == [
        "wave-c-integrity:v1"
    ]
    assert all(issue.status == "open" for issue in restored.issue_closures)


def test_T02_C_005_execution_failure_is_deduplicated_and_fail_closed() -> None:
    recovery = _recovery_api()
    coordinator = recovery.RevisionRecoveryCoordinator.create(
        run_id="wave-c-integrity",
        issue_closures=_open_issues(),
        max_retries=1,
    )
    coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )
    first_failure = _failed_execution()
    second_payload = first_failure.model_dump(mode="python")
    second_payload["execution_id"] = "execution-wave-c-failed-2"
    second_failure = ExecutionResult.model_validate(second_payload)

    assert coordinator.record_execution_result(first_failure) == "retry"
    assert coordinator.record_execution_result(first_failure) == "duplicate"
    assert coordinator.controller.state.retry_count == 1
    assert coordinator.record_execution_result(second_failure) == "stopped"
    assert coordinator.controller.state.status == "stopped"
    assert coordinator.controller.state.stop_reason == "retry_budget_exhausted"
    assert len(coordinator.controller.state.failure_reasons) == 2
    assert all(issue.status == "open" for issue in coordinator.issue_closures)
    assert len(coordinator.list_versions()) == 1


def test_T02_C_005_agent_failure_and_inconsistent_partial_state_fail_closed() -> None:
    recovery = _recovery_api()
    coordinator = recovery.RevisionRecoveryCoordinator.create(
        run_id="wave-c-integrity",
        issue_closures=_open_issues(),
        max_retries=0,
    )
    coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )

    with pytest.raises(AgentOutputError):
        revision_api.run_revision_step_with_retry(
            lambda: (_ for _ in ()).throw(AgentOutputError("controlled")),
            controller=coordinator.controller,
            step_name="reviewer",
        )
    assert coordinator.controller.state.status == "stopped"
    assert all(issue.status == "open" for issue in coordinator.issue_closures)
    with pytest.raises(ValueError, match="active revision"):
        coordinator.apply_version_event(
            event_id="late-revision-v2",
            event_type="revision_event",
            version=_v2(),
        )

    payload = json.loads(coordinator.serialize())
    payload["versions"] = []
    with pytest.raises(ValidationError, match="controller version lineage"):
        recovery.RevisionRecoveryCheckpoint.model_validate(payload)


def test_T02_C_005_issue_cannot_close_before_generated_version_exists() -> None:
    recovery = _recovery_api()
    coordinator = recovery.RevisionRecoveryCoordinator.create(
        run_id="wave-c-integrity",
        issue_closures=_open_issues(),
    )
    coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=_v1(),
    )

    with pytest.raises(ValueError, match="generated V2"):
        coordinator.set_issue_closures(_resolved_issues())
    assert all(issue.status == "open" for issue in coordinator.issue_closures)
