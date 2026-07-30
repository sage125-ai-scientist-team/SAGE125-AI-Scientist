"""Persistence port for immutable T03 feedback and lineage records."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.contracts.validation import (
    AuditLineage,
    AuditLineageEvent,
    FeedbackDecision,
    FeedbackRecord,
)


@runtime_checkable
class FeedbackStore(Protocol):
    """Storage adapter implemented by the Wave B persistence layer."""

    def save_feedback(self, record: FeedbackRecord) -> FeedbackRecord:
        """Persist one immutable submission or return its idempotent match."""
        ...

    def get_feedback(self, feedback_id: str) -> FeedbackRecord:
        """Return one immutable feedback record or raise ``KeyError``."""
        ...

    def save_decision(self, decision: FeedbackDecision) -> FeedbackDecision:
        """Create one decision; reject attempts to overwrite an existing one."""
        ...

    def get_decision(self, feedback_id: str) -> FeedbackDecision | None:
        """Return the decision for a feedback record when one exists."""
        ...

    def save_decision_and_append(
        self,
        lineage_id: str,
        decision: FeedbackDecision,
        event: AuditLineageEvent,
    ) -> tuple[FeedbackDecision, AuditLineage]:
        """Atomically create a decision and bind its audit event."""
        ...

    def save_lineage(self, lineage: AuditLineage) -> AuditLineage:
        """Create one lineage; reject replacement of an existing lineage."""
        ...

    def append_lineage_event(
        self,
        lineage_id: str,
        event: AuditLineageEvent,
    ) -> AuditLineage:
        """Atomically append one event and return the new lineage snapshot."""
        ...

    def get_lineage(self, lineage_id: str) -> AuditLineage:
        """Return one lineage or raise ``KeyError``."""
        ...

    def get_lineage_by_feedback(self, feedback_id: str) -> AuditLineage:
        """Resolve the unique lineage for one feedback record."""
        ...
