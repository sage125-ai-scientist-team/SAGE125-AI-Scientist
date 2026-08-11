"""Legacy feedback imports remain explicitly unverified and reversible."""

from __future__ import annotations

import pytest

from app.feedback import (
    InvalidFeedbackInput,
    SQLiteFeedbackStore,
    import_legacy_feedback,
    migrate_legacy_feedback_payload,
)


def _legacy_payload() -> dict:
    return {
        "run_id": "run-legacy",
        "question_id": "Q003",
        "version_id": "run-legacy:v1",
        "text": "Recheck the source selection.",
        "reviewer_id": "legacy-reviewer",
        "created_at": "2026-07-29T08:00:00Z",
        "accepted": True,
        "passed": True,
    }


def test_legacy_flags_never_become_acceptance_or_validation() -> None:
    record, lineage = migrate_legacy_feedback_payload(_legacy_payload())

    assert record.source.channel == "migration"
    assert record.metadata["verified"] is False
    assert lineage.events[0].event_type == "legacy_unverified"
    assert lineage.decision_id is None
    assert lineage.validation_report_id is None


def test_legacy_import_is_idempotent_across_restart(tmp_path) -> None:
    path = tmp_path / "feedback.sqlite3"
    first_store = SQLiteFeedbackStore(path)
    first_record, first_lineage = import_legacy_feedback(
        _legacy_payload(), first_store
    )
    first_store.close()

    second_store = SQLiteFeedbackStore(path)
    second_record, second_lineage = import_legacy_feedback(
        _legacy_payload(), second_store
    )

    assert second_record == first_record
    assert second_lineage == first_lineage
    assert second_store.get_decision(first_record.feedback_id) is None


def test_future_legacy_schema_fails_closed() -> None:
    with pytest.raises(InvalidFeedbackInput):
        migrate_legacy_feedback_payload(
            {**_legacy_payload(), "schema_version": 99}
        )
