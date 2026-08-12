"""Wave B persistence, idempotency, recovery, and concurrency tests."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier, Lock

import pytest

from app.contracts.validation import AuditLineageEvent, FeedbackDecision
from app.feedback import (
    AllowAllFeedbackAuthorizer,
    CorruptFeedbackSnapshot,
    DefaultFeedbackService,
    FeedbackConflict,
    FeedbackSubmission,
    IdempotencyConflict,
    SQLiteFeedbackStore,
    UnsupportedFeedbackSchema,
)


NOW = datetime(2026, 8, 3, 11, 0, tzinfo=timezone.utc)


class _Ids:
    def __init__(self) -> None:
        self._value = 0
        self._lock = Lock()

    def __call__(self) -> str:
        with self._lock:
            self._value += 1
            return f"{self._value:08d}"


def _service(path) -> tuple[SQLiteFeedbackStore, DefaultFeedbackService]:
    store = SQLiteFeedbackStore(path)
    service = DefaultFeedbackService(
        store,
        authorizer=AllowAllFeedbackAuthorizer(),
        clock=lambda: NOW,
        id_factory=_Ids(),
    )
    return store, service


def _submission(
    *,
    feedback: str = "Tighten the falsification threshold.",
    idempotency_key: str | None = "wave-b-request-001",
) -> FeedbackSubmission:
    return FeedbackSubmission(
        run_id="run-wave-b",
        question_id="Q003",
        target_version_id="run-wave-b:v1",
        feedback=feedback,
        source={"channel": "api", "actor_id": "reviewer-003"},
        correlation_id="corr-wave-b-001",
        idempotency_key=idempotency_key,
        metadata={"client": "test"},
    )


def _decision(feedback_id: str, *, decision_id: str = "decision-001") -> FeedbackDecision:
    return FeedbackDecision(
        decision_id=decision_id,
        feedback_id=feedback_id,
        target_version_id="run-wave-b:v1",
        disposition="accepted",
        decision_reason="The requested change is safe and testable.",
        accepted_items=("Tighten the falsification threshold.",),
        decided_by="reviewer-003",
        decided_at=NOW,
        policy_version="t03-wave-b-v1",
    )


def _count_rows(path, table: str) -> int:
    assert table in {
        "feedback_records",
        "feedback_decisions",
        "feedback_lineages",
    }
    with sqlite3.connect(path) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_feedback_and_lineage_survive_store_restart(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    store, service = _service(path)
    saved = service.submit_request(_submission())
    lineage_id = store.get_lineage_by_feedback(saved.feedback_id).lineage_id
    store.close()

    reopened = SQLiteFeedbackStore(path)
    assert reopened.get_feedback(saved.feedback_id) == saved
    lineage = reopened.get_lineage(lineage_id)
    assert lineage.events[0].event_type == "feedback_submitted"
    assert lineage.feedback_id == saved.feedback_id


def test_same_idempotency_key_and_payload_is_written_once(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    _, service = _service(path)

    first = service.submit_request(_submission())
    second = service.submit_request(_submission())

    assert second == first
    assert _count_rows(path, "feedback_records") == 1
    assert _count_rows(path, "feedback_lineages") == 1


def test_same_feedback_record_object_is_idempotent(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    _, service = _service(path)
    record = service.submit_request(_submission(idempotency_key=None))

    assert service.submit(record) == record
    assert _count_rows(path, "feedback_records") == 1
    assert _count_rows(path, "feedback_lineages") == 1


def test_reused_idempotency_key_with_other_payload_conflicts(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    _, service = _service(path)
    service.submit_request(_submission())

    with pytest.raises(IdempotencyConflict):
        service.submit_request(
            _submission(feedback="Delete every verified reference.")
        )

    assert _count_rows(path, "feedback_records") == 1


def test_new_alias_key_is_bound_to_existing_semantic_request(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    _, service = _service(path)
    original = service.submit_request(_submission(idempotency_key="first-key"))
    alias = service.submit_request(_submission(idempotency_key="second-key"))
    assert alias.feedback_id == original.feedback_id

    with pytest.raises(IdempotencyConflict):
        service.submit_request(
            _submission(
                feedback="A different request.",
                idempotency_key="second-key",
            )
        )


def test_future_database_schema_is_rejected_without_mutation(tmp_path) -> None:
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 2")

    with pytest.raises(UnsupportedFeedbackSchema) as caught:
        SQLiteFeedbackStore(path)

    assert caught.value.code == "feedback.unsupported_schema"
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_invalid_decision_event_rolls_back_decision_and_lineage(tmp_path) -> None:
    store, service = _service(tmp_path / "feedback.sqlite3")
    record = service.submit_request(_submission())
    lineage = store.get_lineage_by_feedback(record.feedback_id)
    decision = _decision(record.feedback_id)
    invalid_event = AuditLineageEvent(
        event_id="event-invalid-decision",
        event_type="feedback_decided",
        occurred_at=NOW,
        actor_id="reviewer-003",
        subject_id=decision.decision_id,
        payload_sha256="f" * 64,
        parent_event_id=lineage.events[-1].event_id,
    )

    with pytest.raises(FeedbackConflict):
        store.save_decision_and_append(
            lineage.lineage_id, decision, invalid_event
        )

    assert store.get_decision(record.feedback_id) is None
    assert store.get_lineage(lineage.lineage_id).decision_id is None


def test_decision_retry_with_conflicting_event_is_rejected(tmp_path) -> None:
    store, service = _service(tmp_path / "feedback.sqlite3")
    record = service.submit_request(_submission())
    decision = _decision(record.feedback_id)
    service.decide(record.feedback_id, decision)
    lineage = store.get_lineage_by_feedback(record.feedback_id)
    conflicting = AuditLineageEvent(
        event_id="event-conflicting-retry",
        event_type="feedback_decided",
        occurred_at=NOW,
        actor_id="reviewer-003",
        subject_id=decision.decision_id,
        payload_sha256=decision.fingerprint(),
        parent_event_id=lineage.events[0].event_id,
    )

    with pytest.raises(FeedbackConflict):
        store.save_decision_and_append(
            lineage.lineage_id, decision, conflicting
        )


def test_revision_events_and_diff_survive_restart(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    store, service = _service(path)
    record = service.submit_request(_submission())
    service.decide(record.feedback_id, _decision(record.feedback_id))
    lineage = store.get_lineage_by_feedback(record.feedback_id)
    requested = AuditLineageEvent(
        event_id="event-revision-requested",
        event_type="revision_requested",
        occurred_at=NOW,
        actor_id="t02-revision-runner",
        subject_id=record.feedback_id,
        payload_sha256="a" * 64,
        parent_event_id=lineage.events[-1].event_id,
    )
    lineage = store.append_lineage_event(lineage.lineage_id, requested)
    generated = AuditLineageEvent(
        event_id="event-revision-generated",
        event_type="revision_generated",
        occurred_at=NOW,
        actor_id="t02-revision-runner",
        subject_id="run-wave-b:v2",
        payload_sha256="d" * 64,
        parent_event_id=lineage.events[-1].event_id,
    )
    store.append_lineage_event(lineage.lineage_id, generated)
    store.close()

    restored = SQLiteFeedbackStore(path).get_lineage_by_feedback(record.feedback_id)
    assert restored.resulting_version_id == "run-wave-b:v2"
    assert restored.revision_diff_sha256 == "d" * 64


def test_concurrent_duplicate_submit_creates_one_record_and_lineage(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    _, service = _service(path)
    workers = 16
    barrier = Barrier(workers)

    def submit_once(_: int) -> str:
        barrier.wait()
        return service.submit_request(_submission()).feedback_id

    with ThreadPoolExecutor(max_workers=workers) as pool:
        feedback_ids = list(pool.map(submit_once, range(workers)))

    assert len(set(feedback_ids)) == 1
    assert _count_rows(path, "feedback_records") == 1
    assert _count_rows(path, "feedback_lineages") == 1


def test_concurrent_competing_appends_do_not_fork_lineage(tmp_path) -> None:
    store, service = _service(tmp_path / "feedback.sqlite3")
    record = service.submit_request(_submission())
    service.decide(record.feedback_id, _decision(record.feedback_id))
    lineage = store.get_lineage_by_feedback(record.feedback_id)
    barrier = Barrier(2)

    def append(index: int) -> str:
        event = AuditLineageEvent(
            event_id=f"event-revision-requested-{index}",
            event_type="revision_requested",
            occurred_at=NOW,
            actor_id=f"worker-{index}",
            subject_id=record.feedback_id,
            payload_sha256=str(index) * 64,
            parent_event_id=lineage.events[-1].event_id,
        )
        barrier.wait()
        try:
            store.append_lineage_event(lineage.lineage_id, event)
            return "saved"
        except (FeedbackConflict, ValueError):
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(append, (1, 2)))

    assert sorted(outcomes) == ["conflict", "saved"]
    restored = store.get_lineage(lineage.lineage_id)
    assert len(restored.events) == 3
    assert restored.events[-1].parent_event_id == restored.events[-2].event_id


def test_corrupted_persisted_payload_fails_closed(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    store, service = _service(path)
    record = service.submit_request(_submission())
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE feedback_records SET payload_json = '{}' WHERE feedback_id = ?",
            (record.feedback_id,),
        )

    with pytest.raises(CorruptFeedbackSnapshot):
        store.get_feedback(record.feedback_id)
