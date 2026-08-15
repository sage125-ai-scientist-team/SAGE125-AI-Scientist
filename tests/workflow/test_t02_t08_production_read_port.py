"""T02 -> T08 production read-port identity and lineage regressions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.workflow.revision_consumer import RevisionConsumerRecord
from app.workflow.revision_read_port import (
    FeedbackVersionBinding,
    RevisionIdentityError,
    RevisionLineageError,
    RevisionProductionReadPort,
    RevisionReadSnapshot,
)
from app.workflow.revision_recovery import RevisionRecoveryCoordinator


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "t02_consumer"


def _consumer_record(name: str) -> RevisionConsumerRecord:
    payload = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return RevisionConsumerRecord.model_validate(payload)


def _snapshot(
    name: str,
    question_id: str,
    *,
    feedback_bindings: tuple[FeedbackVersionBinding, ...] = (),
) -> RevisionReadSnapshot:
    record = _consumer_record(name)
    base = datetime(2026, 8, 15, 8, 0, tzinfo=UTC)
    timestamps = {
        version.version_id: base + timedelta(minutes=index)
        for index, version in enumerate(record.plan_versions)
    }
    return RevisionReadSnapshot.create(
        run_id=record.run_id,
        question_id=question_id,
        consumer_record=record,
        version_timestamps=timestamps,
        validation_status="ready_for_validation",
        feedback_bindings=feedback_bindings,
    )


def _binding() -> FeedbackVersionBinding:
    return FeedbackVersionBinding(
        feedback_id="feedback-gate0-001",
        source_version_id="gate0-v1-v2:v1",
        resulting_version_id="gate0-v1-v2:v2",
    )


def _port() -> RevisionProductionReadPort:
    return RevisionProductionReadPort(
        (
            _snapshot("v1_to_v2", "Q001", feedback_bindings=(_binding(),)),
            _snapshot("open_p0_p1", "Q002"),
        )
    )


def test_list_plan_versions_rejects_cross_run() -> None:
    port = _port()

    with pytest.raises(RevisionIdentityError, match="cross-run"):
        port.list_plan_versions(
            run_id="gate0-open-p0-p1",
            question_id="Q001",
        )


def test_list_plan_versions_rejects_cross_question() -> None:
    port = _port()

    with pytest.raises(RevisionIdentityError, match="question_id"):
        port.list_plan_versions(
            run_id="gate0-v1-v2",
            question_id="Q999",
        )


def test_get_version_diff_rejects_unknown_version() -> None:
    port = _port()

    with pytest.raises(KeyError, match="unknown version_id"):
        port.get_version_diff(
            run_id="gate0-v1-v2",
            question_id="Q001",
            from_version_id="gate0-v1-v2:v1",
            to_version_id="gate0-v1-v2:v99",
        )


def test_get_version_diff_rejects_cross_run() -> None:
    port = _port()

    with pytest.raises(RevisionIdentityError, match="run/question lineage"):
        port.get_version_diff(
            run_id="gate0-v1-v2",
            question_id="Q001",
            from_version_id="gate0-v1-v2:v1",
            to_version_id="gate0-open-p0-p1:v1",
        )


def test_get_version_diff_rejects_cross_question() -> None:
    port = _port()

    with pytest.raises(RevisionIdentityError, match="question_id"):
        port.get_version_diff(
            run_id="gate0-v1-v2",
            question_id="Q999",
            from_version_id="gate0-v1-v2:v1",
            to_version_id="gate0-v1-v2:v2",
        )


def test_get_version_diff_rejects_reversed_order() -> None:
    port = _port()

    with pytest.raises(RevisionLineageError, match="reversed"):
        port.get_version_diff(
            run_id="gate0-v1-v2",
            question_id="Q001",
            from_version_id="gate0-v1-v2:v2",
            to_version_id="gate0-v1-v2:v1",
        )


def test_get_version_diff_rejects_broken_lineage() -> None:
    snapshot = _snapshot("v1_to_v2", "Q001", feedback_bindings=(_binding(),))
    port = RevisionProductionReadPort((snapshot,))
    first, second = snapshot.consumer_record.plan_versions
    broken_second = second.model_copy(update={"parent_version_id": "unrelated:v1"})
    broken_consumer = snapshot.consumer_record.model_copy(
        update={"plan_versions": (first, broken_second)}
    )
    # Model a storage/backend corruption after the boundary was constructed. The
    # read method must still validate the lineage at query time and fail closed.
    port._snapshots_by_run[snapshot.run_id] = snapshot.model_copy(  # noqa: SLF001
        update={"consumer_record": broken_consumer}
    )

    with pytest.raises(RevisionLineageError, match="broken lineage"):
        port.get_version_diff(
            run_id="gate0-v1-v2",
            question_id="Q001",
            from_version_id="gate0-v1-v2:v1",
            to_version_id="gate0-v1-v2:v2",
        )


def test_duplicate_feedback_does_not_create_duplicate_version() -> None:
    record = _consumer_record("v1_to_v2")
    first_version, second_version = record.plan_versions
    coordinator = RevisionRecoveryCoordinator.create(
        run_id=record.run_id,
        issue_closures=first_version.issue_closures,
    )
    coordinator.apply_version_event(
        event_id="reviewer-callback-v1",
        event_type="reviewer_callback",
        version=first_version,
    )

    first = coordinator.apply_version_event(
        event_id=f"feedback:{_binding().feedback_id}",
        event_type="revision_event",
        version=second_version,
    )
    duplicate = coordinator.apply_version_event(
        event_id=f"feedback:{_binding().feedback_id}",
        event_type="revision_event",
        version=second_version,
    )
    snapshot = _snapshot(
        "v1_to_v2",
        "Q001",
        feedback_bindings=(_binding(), _binding()),
    )
    views = RevisionProductionReadPort((snapshot,)).list_plan_versions(
        run_id=record.run_id,
        question_id="Q001",
    )

    assert first.created is True
    assert duplicate.created is False and duplicate.duplicate is True
    assert duplicate.version == first.version
    assert [version.version_id for version in coordinator.list_versions()] == [
        first_version.version_id,
        second_version.version_id,
    ]
    assert views[-1].reviewer.feedback_ids == (_binding().feedback_id,)


def test_issue_closure_matches_resulting_version() -> None:
    port = _port()

    versions = port.list_plan_versions(
        run_id="gate0-v1-v2",
        question_id="Q001",
    )
    resulting = versions[-1]

    assert resulting.reviewer.feedback_ids == (_binding().feedback_id,)
    assert resulting.issues
    assert all(
        issue.closed_in_version == resulting.version_id
        for issue in resulting.issues
        if issue.closure_status == "resolved"
    )
    assert all(
        issue.closed_in_version is None
        or versions.index(
            next(item for item in versions if item.version_id == issue.opened_in_version)
        )
        <= versions.index(
            next(item for item in versions if item.version_id == issue.closed_in_version)
        )
        for issue in resulting.issues
    )


def test_production_read_port_returns_owner_shape_without_inference() -> None:
    port = _port()

    versions = port.list_plan_versions(
        run_id="gate0-v1-v2",
        question_id="Q001",
    )
    diff = port.get_version_diff(
        run_id="gate0-v1-v2",
        question_id="Q001",
        from_version_id="gate0-v1-v2:v1",
        to_version_id="gate0-v1-v2:v2",
    )

    assert versions[-1].model_dump(mode="json") == {
        "schema_version": 1,
        "version_id": "gate0-v1-v2:v2",
        "version_number": 2,
        "run_id": "gate0-v1-v2",
        "question_id": "Q001",
        "parent_version_id": "gate0-v1-v2:v1",
        "lineage": ["gate0-v1-v2:v1", "gate0-v1-v2:v2"],
        "timestamp": "2026-08-15T08:01:00Z",
        "reviewer": {
            "score": {
                "evidence_grounding_score": 0.8,
                "falsifiability_score": 0.8,
                "reproducibility_score": 0.9,
                "reference_reliability_score": 0.8,
            },
            "score_delta": {
                "evidence_grounding_score": pytest.approx(0.3),
                "falsifiability_score": pytest.approx(0.4),
                "reproducibility_score": pytest.approx(0.4),
                "reference_reliability_score": pytest.approx(0.2),
            },
            "feedback_ids": ["feedback-gate0-001"],
        },
        "issues": [
            issue.model_dump(mode="json") for issue in versions[-1].issues
        ],
        "state": {
            "validation_status": "ready_for_validation",
            "stop_reason": None,
            "unresolved_p0": [],
            "unresolved_p1": [],
        },
    }
    assert diff.run_id == "gate0-v1-v2"
    assert diff.question_id == "Q001"
    assert diff.from_version_id == "gate0-v1-v2:v1"
    assert diff.to_version_id == "gate0-v1-v2:v2"
    assert diff.lineage == ("gate0-v1-v2:v1", "gate0-v1-v2:v2")
    assert diff.diff_hash == diff.diff.fingerprint()
