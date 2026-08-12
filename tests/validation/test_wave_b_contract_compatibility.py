"""Wave B regressions for the frozen T03 v1 wire contract."""

from __future__ import annotations

from datetime import datetime, timezone

from app.contracts.validation import FeedbackDecision


NOW = datetime(2026, 8, 3, 8, 0, tzinfo=timezone.utc)


def test_accepted_decision_allows_direct_child_resulting_version() -> None:
    """The diff hash belongs to AuditLineage, not FeedbackDecision v1."""
    decision = FeedbackDecision(
        decision_id="decision-accepted-001",
        feedback_id="feedback-001",
        target_version_id="run-demo:v1",
        disposition="accepted",
        decision_reason="The requested threshold change is safe and testable.",
        accepted_items=["Tighten the falsification threshold."],
        decided_by="feedback-policy-v1",
        decided_at=NOW,
        policy_version="t03-wave-b-v1",
        resulting_version_id="run-demo:v2",
    )

    assert decision.resulting_version_id == "run-demo:v2"
    assert "revision_diff_sha256" not in decision.model_dump(mode="json")
