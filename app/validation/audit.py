"""Replay-safe audit writer for gate and validation completion events."""

from __future__ import annotations

import hashlib
import json

from app.contracts.validation import (
    AuditLineage,
    AuditLineageEvent,
    GateResult,
    ValidationReport,
)
from app.feedback.storage import FeedbackStore


def _payload_sha256(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    wire = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


def _event_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:24]}"


class ValidationAuditWriter:
    """Append a complete validation result to a feedback lineage.

    Events use deterministic IDs.  If a process stops after only some gate
    events were written, retrying resumes the same chain instead of forking it.
    """

    def __init__(self, store: FeedbackStore) -> None:
        self._store = store

    def record(
        self,
        feedback_id: str,
        report: ValidationReport,
        *,
        actor_id: str,
    ) -> AuditLineage:
        """Append all gate hashes and the report hash, then return the lineage."""
        normalized_actor = actor_id.strip()
        if not normalized_actor:
            raise ValueError("actor_id cannot be blank")
        lineage = self._store.get_lineage_by_feedback(feedback_id)
        if lineage.run_id != report.run_id:
            raise ValueError("validation report belongs to a different run")
        expected_version = (
            lineage.resulting_version_id or lineage.target_version_id
        )
        if report.version_id != expected_version:
            raise ValueError("validation report belongs to a different version")
        if lineage.validation_report_id is not None:
            if lineage.validation_report_id != report.report_id:
                raise ValueError("lineage already contains another validation report")
            existing = next(
                (
                    event
                    for event in lineage.events
                    if event.event_type == "validation_completed"
                ),
                None,
            )
            if existing is None or existing.payload_sha256 != _payload_sha256(report):
                raise ValueError("validation retry conflicts with audit history")
            return lineage

        for gate in report.gate_results:
            lineage = self._append_gate_if_missing(
                lineage,
                gate,
                report=report,
                actor_id=normalized_actor,
            )

        report_event_id = _event_id(
            "validation-event", lineage.lineage_id, report.report_id
        )
        existing = {event.event_id: event for event in lineage.events}
        report_hash = _payload_sha256(report)
        if report_event_id in existing:
            event = existing[report_event_id]
            if (
                event.event_type != "validation_completed"
                or event.subject_id != report.report_id
                or event.payload_sha256 != report_hash
            ):
                raise ValueError("validation event ID conflicts with audit history")
            return lineage
        event = AuditLineageEvent(
            event_id=report_event_id,
            event_type="validation_completed",
            occurred_at=report.created_at,
            actor_id=normalized_actor,
            subject_id=report.report_id,
            payload_sha256=report_hash,
            parent_event_id=lineage.events[-1].event_id,
            metadata={
                "validation_id": report.validation_id,
                "version_id": report.version_id,
                "validation_status": report.validation_status,
            },
        )
        return self._store.append_lineage_event(lineage.lineage_id, event)

    def _append_gate_if_missing(
        self,
        lineage: AuditLineage,
        gate: GateResult,
        *,
        report: ValidationReport,
        actor_id: str,
    ) -> AuditLineage:
        event_id = _event_id(
            "gate-event", lineage.lineage_id, report.report_id, gate.gate_id
        )
        gate_hash = _payload_sha256(gate)
        existing = {event.event_id: event for event in lineage.events}
        if event_id in existing:
            event = existing[event_id]
            if (
                event.event_type != "gate_evaluated"
                or event.subject_id != gate.gate_id
                or event.payload_sha256 != gate_hash
            ):
                raise ValueError("gate event ID conflicts with audit history")
            return lineage
        event = AuditLineageEvent(
            event_id=event_id,
            event_type="gate_evaluated",
            occurred_at=report.created_at,
            actor_id=actor_id,
            subject_id=gate.gate_id,
            payload_sha256=gate_hash,
            parent_event_id=lineage.events[-1].event_id,
            metadata={
                "report_id": report.report_id,
                "passed": gate.passed,
                "severity": gate.severity.value,
            },
        )
        return self._store.append_lineage_event(lineage.lineage_id, event)


__all__ = ["ValidationAuditWriter"]
