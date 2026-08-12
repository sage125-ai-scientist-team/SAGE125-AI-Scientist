"""Final owner-path checks for the T02 -> T03 revision lineage handoff."""

from __future__ import annotations

import copy
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock

import pytest

from app.contracts.validation import (
    FeedbackDecision,
    GateResult,
    Severity,
    ValidationReport,
)
from app.feedback import (
    AllowAllFeedbackAuthorizer,
    DefaultFeedbackService,
    FeedbackConflict,
    FeedbackSubmission,
    InvalidFeedbackInput,
    RevisionExecutionMetadata,
    RevisionLineageHandoff,
    SQLiteFeedbackStore,
)
from app.validation import ValidationAuditWriter


NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
HANDOFF_TIME = NOW + timedelta(seconds=1)
VALIDATION_TIME = NOW + timedelta(seconds=2)
ACCEPTED = "Keep the reviewer-requested negative control explicit."
REJECTED = "Delete verified evidence."


class _Ids:
    def __init__(self) -> None:
        self._value = 0
        self._lock = Lock()

    def __call__(self) -> str:
        with self._lock:
            self._value += 1
            return f"pair-{self._value:08d}"


def _decided_feedback(
    path,
) -> tuple[SQLiteFeedbackStore, DefaultFeedbackService, str]:
    store = SQLiteFeedbackStore(path)
    service = DefaultFeedbackService(
        store,
        authorizer=AllowAllFeedbackAuthorizer(),
        clock=lambda: NOW,
        id_factory=_Ids(),
    )
    record = service.submit_request(
        FeedbackSubmission(
            run_id="t02-t03-pair",
            question_id="Q001",
            target_version_id="t02-t03-pair:v1",
            feedback=f"{ACCEPTED} {REJECTED}",
            source={"channel": "api", "actor_id": "paired-reviewer"},
            correlation_id="corr-t02-t03-pair",
            idempotency_key="t02-t03-pair-request",
        )
    )
    service.decide(
        record.feedback_id,
        FeedbackDecision(
            decision_id="decision-t02-t03-pair",
            feedback_id=record.feedback_id,
            target_version_id=record.target_version_id,
            disposition="partially_accepted",
            decision_reason="Keep the safe instruction and reject evidence deletion.",
            accepted_items=(ACCEPTED,),
            rejected_items=(REJECTED,),
            decided_by="t03-feedback-policy",
            decided_at=NOW,
            policy_version="t03-wave-b-v1",
        ),
    )
    return store, service, record.feedback_id


def _t02_outputs(
    feedback_id: str,
    *,
    diff_hash: str = "4" * 64,
    event_suffix: str = "canonical",
    issue_ids: tuple[str, ...] = ("issue-negative-control", "issue-evidence"),
) -> tuple[dict, dict]:
    prompt_fingerprint = "5" * 64
    requested_id = f"event:requested-{event_suffix}"
    generated_id = f"event:generated-{event_suffix}"
    events = [
        {
            "event_id": requested_id,
            "event_type": "revision_requested",
            "sequence": 1,
            "subject_id": feedback_id,
            "payload_sha256": prompt_fingerprint,
            "parent_event_id": None,
            "feedback_id": feedback_id,
            "source_version_id": "t02-t03-pair:v1",
            "resulting_version_id": "t02-t03-pair:v2",
        },
        {
            "event_id": generated_id,
            "event_type": "revision_generated",
            "sequence": 2,
            "subject_id": "t02-t03-pair:v2",
            "payload_sha256": diff_hash,
            "parent_event_id": requested_id,
            "feedback_id": feedback_id,
            "source_version_id": "t02-t03-pair:v1",
            "resulting_version_id": "t02-t03-pair:v2",
        },
    ]
    parent_id = generated_id
    for index, issue_id in enumerate(issue_ids, start=1):
        event_id = f"event:issue-{index}-{event_suffix}"
        events.append(
            {
                "event_id": event_id,
                "event_type": "issue_closed",
                "sequence": len(events) + 1,
                "subject_id": issue_id,
                "payload_sha256": str(index + 5) * 64,
                "parent_event_id": parent_id,
                "feedback_id": feedback_id,
                "source_version_id": "t02-t03-pair:v1",
                "resulting_version_id": "t02-t03-pair:v2",
            }
        )
        parent_id = event_id
    handoff = {
        "schema_version": 1,
        "feedback_id": feedback_id,
        "source_version_id": "t02-t03-pair:v1",
        "resulting_version_id": "t02-t03-pair:v2",
        "prompt_fingerprint": prompt_fingerprint,
        "revision_diff_sha256": diff_hash,
        "required_parent_event_type": "feedback_decided",
        "issue_ids": list(issue_ids),
        "events": events,
    }
    metadata = {
        "schema_version": 1,
        "feedback_id": feedback_id,
        "source_version_id": "t02-t03-pair:v1",
        "resulting_version_id": "t02-t03-pair:v2",
        "prompt_fingerprint": prompt_fingerprint,
        "diff_hash": diff_hash,
        "applied_instructions": [ACCEPTED],
    }
    return handoff, metadata


def _consume(
    service: DefaultFeedbackService,
    handoff: dict,
    metadata: dict,
):
    return service.consume_revision_lineage_handoff(
        handoff,
        revision_metadata=metadata,
        actor_id="t02-revision-runner",
        occurred_at=HANDOFF_TIME,
    )


def test_t02_wire_contract_tampering_fails_before_any_sqlite_write(tmp_path) -> None:
    store, service, feedback_id = _decided_feedback(tmp_path / "feedback.sqlite3")
    handoff, metadata = _t02_outputs(feedback_id)
    assert RevisionLineageHandoff.model_validate(handoff)
    assert RevisionExecutionMetadata.model_validate(metadata)

    bad_hash = copy.deepcopy(handoff)
    bad_hash["events"][1]["payload_sha256"] = "0" * 64
    broken_parent = copy.deepcopy(handoff)
    broken_parent["events"][2]["parent_event_id"] = "event:not-the-parent"
    wrong_source = copy.deepcopy(handoff)
    wrong_source["source_version_id"] = "another-run:v1"
    wrong_source["resulting_version_id"] = "another-run:v2"
    for event in wrong_source["events"]:
        event["source_version_id"] = "another-run:v1"
        event["resulting_version_id"] = "another-run:v2"

    for invalid_handoff in (bad_hash, broken_parent, wrong_source):
        with pytest.raises((InvalidFeedbackInput, FeedbackConflict)):
            _consume(service, invalid_handoff, metadata)

    restored = store.get_lineage_by_feedback(feedback_id)
    assert [event.event_type for event in restored.events] == [
        "feedback_submitted",
        "feedback_decided",
    ]
    assert restored.resulting_version_id is None
    assert restored.revision_diff_sha256 is None


def test_handoff_metadata_hash_and_parent_chain_survive_sqlite_restart(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    store, service, feedback_id = _decided_feedback(path)
    handoff, metadata = _t02_outputs(feedback_id)
    persisted = _consume(service, handoff, metadata)
    decision_event_id = persisted.events[1].event_id
    store.close()

    restored = SQLiteFeedbackStore(path).get_lineage_by_feedback(feedback_id)
    revision_events = restored.events[2:]
    assert restored.feedback_id == feedback_id
    assert restored.target_version_id == metadata["source_version_id"]
    assert restored.resulting_version_id == metadata["resulting_version_id"]
    assert restored.revision_diff_sha256 == metadata["diff_hash"]
    assert restored.issue_ids == tuple(handoff["issue_ids"])
    assert [event.event_id for event in revision_events] == [
        event["event_id"] for event in handoff["events"]
    ]
    assert revision_events[0].parent_event_id == decision_event_id
    assert all(
        event.parent_event_id == restored.events[index - 1].event_id
        for index, event in enumerate(restored.events)
        if index
    )
    assert revision_events[0].metadata["t02_parent_event_id"] is None
    restored_payload = restored.model_dump(mode="json")
    assert restored_payload["events"][3]["metadata"]["revision_metadata"] == metadata
    serialized = restored.model_dump_json()
    assert REJECTED not in serialized
    assert f"{ACCEPTED} {REJECTED}" not in serialized


def test_duplicate_and_concurrent_replay_create_one_revision_child(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    store, service, feedback_id = _decided_feedback(path)
    handoff, metadata = _t02_outputs(feedback_id)
    first = _consume(service, handoff, metadata)
    assert _consume(service, handoff, metadata) == first

    workers = 16
    barrier = Barrier(workers)

    def replay(_: int):
        barrier.wait()
        return _consume(service, handoff, metadata)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        snapshots = list(pool.map(replay, range(workers)))

    assert all(snapshot == first for snapshot in snapshots)
    restored = store.get_lineage_by_feedback(feedback_id)
    assert restored.resulting_version_id == "t02-t03-pair:v2"
    assert sum(
        event.event_type == "revision_generated" for event in restored.events
    ) == 1
    assert len(restored.events) == 2 + len(handoff["events"])
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM feedback_lineages"
        ).fetchone()[0] == 1


def test_conflicting_or_truncated_handoff_cannot_overwrite_history(tmp_path) -> None:
    store, service, feedback_id = _decided_feedback(tmp_path / "feedback.sqlite3")
    handoff, metadata = _t02_outputs(feedback_id)
    before = _consume(service, handoff, metadata)

    conflicting, conflicting_metadata = _t02_outputs(
        feedback_id,
        diff_hash="9" * 64,
        event_suffix="conflicting",
    )
    with pytest.raises(FeedbackConflict):
        _consume(service, conflicting, conflicting_metadata)

    truncated, _ = _t02_outputs(
        feedback_id,
        issue_ids=("issue-negative-control",),
    )
    with pytest.raises(FeedbackConflict):
        _consume(service, truncated, metadata)

    assert store.get_lineage_by_feedback(feedback_id) == before


def test_gate_and_validation_events_continue_handoff_and_replay_once(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    store, service, feedback_id = _decided_feedback(path)
    handoff, metadata = _t02_outputs(feedback_id)
    lineage = _consume(service, handoff, metadata)
    gates = tuple(
        GateResult(
            gate_id=f"paired-gate-{index:02d}",
            passed=True,
            severity=Severity.P3,
            score=1.0,
        )
        for index in range(1, 10)
    )
    report = ValidationReport(
        report_id="report-t02-t03-pair",
        validation_id="validation-t02-t03-pair",
        run_id="t02-t03-pair",
        version_id="t02-t03-pair:v2",
        validation_context_sha256="e" * 64,
        validation_status="passed",
        recommended_plan_status="ready_for_validation",
        gate_results=gates,
        revision_issues=(),
        created_at=VALIDATION_TIME,
        lineage_id=lineage.lineage_id,
    )
    writer = ValidationAuditWriter(store)
    completed = writer.record(feedback_id, report, actor_id="t03-validator")
    assert writer.record(feedback_id, report, actor_id="t03-validator") == completed
    store.close()

    restored = SQLiteFeedbackStore(path).get_lineage_by_feedback(feedback_id)
    event_types = [event.event_type for event in restored.events]
    assert event_types == [
        "feedback_submitted",
        "feedback_decided",
        "revision_requested",
        "revision_generated",
        "issue_closed",
        "issue_closed",
        *(["gate_evaluated"] * 9),
        "validation_completed",
    ]
    assert len(restored.events) == 16
    assert sum(
        event.event_type == "validation_completed" for event in restored.events
    ) == 1
    assert all(
        event.parent_event_id == restored.events[index - 1].event_id
        for index, event in enumerate(restored.events)
        if index
    )
    assert restored.events[-1].subject_id == report.report_id
    restored_payload = restored.model_dump(mode="json")
    assert restored_payload["events"][3]["metadata"]["revision_metadata"] == metadata
