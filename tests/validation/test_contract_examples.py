"""Keep the published T03 JSON examples executable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts.validation import (
    AuditLineage,
    FeedbackDecision,
    FeedbackRecord,
    GateResult,
    HumanFeedbackDirective,
    ValidationContext,
    ValidationReport,
)


EXAMPLES = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "modules"
    / "T03"
    / "examples"
)


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("feedback_record.submitted.json", FeedbackRecord),
        ("feedback_decision.partially_accepted.json", FeedbackDecision),
        ("human_feedback_directive.json", HumanFeedbackDirective),
        ("validation_context.complete.json", ValidationContext),
        ("gate_result.blocked_p1.json", GateResult),
        ("validation_report.blocked.json", ValidationReport),
        ("audit_lineage.complete.json", AuditLineage),
    ],
)
def test_valid_contract_example(filename: str, model: type) -> None:
    payload = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
    model.model_validate(payload)


def test_missing_agent_trace_example_is_intentionally_invalid() -> None:
    payload = json.loads(
        (EXAMPLES / "validation_context.missing_agent_trace.invalid.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(ValidationError):
        ValidationContext.model_validate(payload)


def test_t08_projection_uses_upstream_run_id_not_job_id() -> None:
    payload = json.loads(
        (EXAMPLES / "t08.feedback_projection.json").read_text(
            encoding="utf-8"
        )
    )
    record = FeedbackRecord.model_validate(
        payload["expected_feedback_record"]
    )

    assert record.run_id == payload["job"]["upstream_run_id"]
    assert record.run_id != payload["job"]["job_id"]
    assert record.question_id == payload["job"]["question_id"]
    assert record.target_version_id == payload["request"]["target_version_id"]
    assert record.feedback == payload["request"]["feedback"]
    assert record.correlation_id == payload["request"]["correlation_id"]
