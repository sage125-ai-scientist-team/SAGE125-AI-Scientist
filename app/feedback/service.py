"""Application port for T03 human-feedback processing."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.contracts.validation import (
    FeedbackDecision,
    FeedbackRecord,
    HumanFeedbackDirective,
)


@runtime_checkable
class FeedbackService(Protocol):
    """Wave B service contract consumed by T02 and T08."""

    def submit(self, record: FeedbackRecord) -> FeedbackRecord:
        """Validate and persist a feedback submission."""
        ...

    def decide(
        self,
        feedback_id: str,
        decision: FeedbackDecision,
    ) -> FeedbackDecision:
        """Record an accept/partial/reject decision."""
        ...

    def build_directive(
        self,
        feedback_id: str,
    ) -> HumanFeedbackDirective | None:
        """Return accepted prompt instructions; rejected feedback yields ``None``."""
        ...
