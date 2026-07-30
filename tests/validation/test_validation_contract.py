"""T03 Wave A contracts for human feedback and blocking validation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.contracts.validation import (
    AuditLineage,
    AuditLineageEvent,
    FeedbackDecision,
    FeedbackRecord,
    GateFinding,
    GateResult,
    HumanFeedbackDirective,
    RevisionIssueSnapshot,
    Severity,
    ValidationContext,
    ValidationReport,
)


NOW = datetime(2026, 7, 28, 8, 0, tzinfo=timezone.utc)


def _feedback_record() -> FeedbackRecord:
    return FeedbackRecord(
        feedback_id="feedback-001",
        run_id="run-demo",
        question_id="Q001",
        target_version_id="run-demo:v1",
        feedback="请收紧证伪阈值，同时保留已有引用。",
        source={"channel": "api", "actor_id": "human-reviewer"},
        correlation_id="corr-001",
        submitted_at=NOW,
        request_fingerprint="a" * 64,
    )


def _partial_decision() -> FeedbackDecision:
    return FeedbackDecision(
        decision_id="decision-001",
        feedback_id="feedback-001",
        target_version_id="run-demo:v1",
        disposition="partially_accepted",
        decision_reason="接受证伪阈值建议；拒绝删除已核验引用。",
        accepted_items=["收紧证伪阈值"],
        rejected_items=["删除已核验引用"],
        decided_by="feedback-policy-v1",
        decided_at=NOW,
        policy_version="t03-wave-a-v1",
    )


def _context_payload() -> dict:
    return {
        "validation_id": "validation-001",
        "run_id": "run-demo",
        "version_id": "run-demo:v1",
        "research_plan": {
            "question_id": "Q001",
            "input_question": "How can this mechanism be tested?",
            "actual_execution": False,
            "references": [{"id": "EV-001"}],
        },
        "evidence_cards": [{"id": "EV-001", "title": "Evidence"}],
        "agent_trace": [
            {
                "run_id": "run-demo",
                "agent_name": "report_writer",
                "status": "success",
            }
        ],
        "execution_metadata": {"actual_execution": False, "mode": "mock"},
        "question_item": {
            "id": "Q001",
            "question": "How can this mechanism be tested?",
            "domain": "synthetic",
        },
    }


def _blocked_gate() -> GateResult:
    return GateResult(
        gate_id="artifact-presence",
        passed=False,
        severity=Severity.P1,
        findings=[
            GateFinding(
                code="MISSING_AGENT_TRACE",
                message="Agent trace is required.",
                severity=Severity.P1,
                closure_status="open",
                path="agent_trace",
                source_ids=["validation-001"],
            )
        ],
        errors=["Agent trace is required."],
        score=0.0,
    )


def test_feedback_record_uses_canonical_t02_version_id() -> None:
    record = _feedback_record()
    assert record.target_version_id == "run-demo:v1"
    assert FeedbackRecord.model_validate(record.model_dump(mode="json")) == record

    with pytest.raises(ValidationError, match="canonical"):
        FeedbackRecord.model_validate(
            {
                **record.model_dump(mode="json"),
                "target_version_id": "v1",
            }
        )

    with pytest.raises(ValidationError, match="canonical"):
        FeedbackRecord.model_validate(
            {
                **record.model_dump(mode="json"),
                "target_version_id": " run-demo:v1 ",
            }
        )


def test_feedback_record_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        FeedbackRecord.model_validate(
            {
                **_feedback_record().model_dump(mode="json"),
                "raw_secret": "must not cross the contract boundary",
            }
        )


def test_feedback_decision_is_auditable_and_partial_is_explicit() -> None:
    decision = _partial_decision()
    assert decision.disposition == "partially_accepted"
    assert decision.accepted_items == ("收紧证伪阈值",)
    assert decision.rejected_items == ("删除已核验引用",)

    with pytest.raises(ValidationError, match="accepted_items and rejected_items"):
        FeedbackDecision.model_validate(
            {
                **decision.model_dump(mode="json"),
                "rejected_items": [],
            }
        )


def test_feedback_decision_rejects_overlap_and_non_child_version() -> None:
    payload = _partial_decision().model_dump(mode="json")

    with pytest.raises(ValidationError, match="must not overlap"):
        FeedbackDecision.model_validate(
            {
                **payload,
                "rejected_items": ["收紧证伪阈值"],
            }
        )

    with pytest.raises(ValidationError, match="direct next version"):
        FeedbackDecision.model_validate(
            {
                **payload,
                "resulting_version_id": "run-demo:v3",
            }
        )


def test_directive_only_contains_accepted_feedback() -> None:
    directive = HumanFeedbackDirective.from_feedback(
        _feedback_record(),
        _partial_decision(),
    )

    assert directive.feedback_id == "feedback-001"
    assert directive.instructions == ("收紧证伪阈值",)
    assert "删除已核验引用" not in directive.model_dump_json()
    assert len(directive.original_feedback_sha256) == 64


def test_rejected_feedback_cannot_produce_a_prompt_directive() -> None:
    decision = FeedbackDecision(
        decision_id="decision-rejected-001",
        feedback_id="feedback-001",
        target_version_id="run-demo:v1",
        disposition="rejected",
        decision_reason="The request would remove verified evidence.",
        rejected_items=["删除已核验引用"],
        decided_by="feedback-policy-v1",
        decided_at=NOW,
        policy_version="t03-wave-a-v1",
    )

    with pytest.raises(ValueError, match="rejected feedback"):
        HumanFeedbackDirective.from_feedback(_feedback_record(), decision)


@pytest.mark.parametrize(
    "missing_field",
    [
        "research_plan",
        "evidence_cards",
        "agent_trace",
        "execution_metadata",
        "question_item",
    ],
)
def test_validation_context_requires_all_five_artifacts(
    missing_field: str,
) -> None:
    payload = _context_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        ValidationContext.model_validate(payload)


def test_validation_context_rejects_cross_question_artifacts() -> None:
    payload = _context_payload()
    payload["research_plan"]["question_id"] = "Q028"

    with pytest.raises(ValidationError, match="question"):
        ValidationContext.model_validate(payload)


def test_validation_context_rejects_execution_truth_mismatch() -> None:
    payload = _context_payload()
    payload["execution_metadata"]["actual_execution"] = True

    with pytest.raises(ValidationError, match="actual_execution"):
        ValidationContext.model_validate(payload)


def test_validation_context_rejects_cross_run_trace() -> None:
    payload = _context_payload()
    payload["agent_trace"][0]["run_id"] = "another-run"

    with pytest.raises(ValidationError, match="different run"):
        ValidationContext.model_validate(payload)


def test_validation_context_rejects_cross_run_nested_artifacts() -> None:
    payload = _context_payload()
    payload["execution_metadata"]["run_id"] = "another-run"

    with pytest.raises(ValidationError, match="execution_metadata.run_id"):
        ValidationContext.model_validate(payload)


def test_validation_context_allows_ancestor_evidence_version() -> None:
    payload = _context_payload()
    payload["version_id"] = "run-demo:v2"
    payload["evidence_cards"][0]["version_id"] = "run-demo:v1"
    payload["agent_trace"][0]["version_id"] = "run-demo:v1"

    context = ValidationContext.model_validate(payload)
    assert context.evidence_cards[0]["version_id"] == "run-demo:v1"


def test_validation_context_rejects_future_feedback_and_issue_closure() -> None:
    payload = _context_payload()
    payload["human_feedback"] = {
        "schema_version": 1,
        "feedback_id": "feedback-future",
        "target_version_id": "run-demo:v2",
        "disposition": "accepted",
        "instructions": ["Apply this later."],
        "original_feedback_sha256": "f" * 64,
    }
    with pytest.raises(ValidationError, match="future plan version"):
        ValidationContext.model_validate(payload)

    payload = _context_payload()
    payload["revision_issues"] = [
        {
            "issue_id": "issue-future",
            "status": "resolved",
            "severity": "P0",
            "opened_in_version": 1,
            "closed_in_version": 2,
            "resolution_note": "Not resolved in V1.",
        }
    ]
    with pytest.raises(ValidationError, match="future plan version"):
        ValidationContext.model_validate(payload)


def test_validation_context_is_a_deeply_immutable_snapshot() -> None:
    payload = _context_payload()
    context = ValidationContext.model_validate(payload)
    payload["research_plan"]["question_id"] = "Q999"

    assert context.research_plan["question_id"] == "Q001"
    with pytest.raises(TypeError):
        context.research_plan["question_id"] = "Q999"
    with pytest.raises(TypeError):
        context.evidence_cards[0]["id"] = "EV-999"

    copied = context.model_copy(deep=True)
    restored = ValidationContext.model_validate(
        context.model_dump(mode="json")
    )
    assert copied == context
    assert restored == context
    assert context.fingerprint() == restored.fingerprint()


def test_gate_result_cannot_pass_with_open_p0_or_p1() -> None:
    blocked = _blocked_gate()
    assert blocked.is_blocking

    with pytest.raises(ValidationError, match="open P0/P1"):
        GateResult.model_validate(
            {
                **blocked.model_dump(mode="json"),
                "passed": True,
            }
        )


def test_gate_result_can_pass_after_p1_is_resolved() -> None:
    result = GateResult(
        gate_id="artifact-presence",
        passed=True,
        severity=Severity.P1,
        findings=[
            GateFinding(
                code="MISSING_AGENT_TRACE",
                message="Agent trace is required.",
                severity=Severity.P1,
                closure_status="resolved",
                issue_id="issue-agent-trace",
                resolution_note="A trace from the same run was supplied.",
            )
        ],
        score=1.0,
    )

    assert result.passed
    assert not result.is_blocking


def test_closed_p1_requires_auditable_issue_and_reason() -> None:
    with pytest.raises(ValidationError, match="resolution_note"):
        GateFinding(
            code="EXECUTION_UNVERIFIED",
            message="Execution claim lacks proof.",
            severity=Severity.P1,
            closure_status="not_applicable",
            issue_id="issue-execution",
        )

    with pytest.raises(ValidationError, match="issue_id"):
        GateFinding(
            code="EXECUTION_UNVERIFIED",
            message="Execution claim lacks proof.",
            severity=Severity.P1,
            closure_status="not_applicable",
            resolution_note="The plan makes no execution claim.",
        )


def test_non_blocking_finding_cannot_fail_a_gate() -> None:
    with pytest.raises(ValidationError, match="non-blocking"):
        GateResult(
            gate_id="advisory-style",
            passed=False,
            severity=Severity.P2,
            findings=[
                GateFinding(
                    code="STYLE_ADVISORY",
                    message="Improve wording before final publication.",
                    severity=Severity.P2,
                )
            ],
            score=0.8,
        )


def test_validation_report_cannot_pass_blocking_gate() -> None:
    blocked = _blocked_gate()
    context = ValidationContext.model_validate(_context_payload())

    with pytest.raises(ValidationError, match="blocking"):
        ValidationReport.from_context(
            context,
            report_id="report-001",
            validation_status="passed",
            recommended_plan_status="ready_for_validation",
            gate_results=[blocked],
            created_at=NOW,
        )

    report = ValidationReport.from_context(
        context,
        report_id="report-001",
        validation_status="blocked",
        recommended_plan_status="draft",
        gate_results=[blocked],
        created_at=NOW,
    )
    assert not report.passed
    assert report.validation_context_sha256 == context.fingerprint()


def test_validation_report_cannot_ignore_open_revision_issue() -> None:
    payload = _context_payload()
    payload["revision_issues"] = [
        RevisionIssueSnapshot(
            issue_id="issue-001",
            status="open",
            severity=Severity.P0,
            opened_in_version=1,
        ).model_dump(mode="json")
    ]
    context = ValidationContext.model_validate(payload)
    passing_gate = GateResult(
        gate_id="schema",
        passed=True,
        severity=Severity.P3,
        score=1.0,
    )

    with pytest.raises(ValidationError, match="blocking"):
        ValidationReport.from_context(
            context,
            report_id="report-issue-blocked",
            validation_status="passed",
            recommended_plan_status="validated",
            gate_results=[passing_gate],
            created_at=NOW,
        )


def test_validation_report_requires_unique_gate_ids() -> None:
    context = ValidationContext.model_validate(_context_payload())
    gate = GateResult(
        gate_id="schema",
        passed=True,
        severity=Severity.P3,
        score=1.0,
    )

    with pytest.raises(ValidationError, match="gate_id values must be unique"):
        ValidationReport.from_context(
            context,
            report_id="report-duplicate-gates",
            validation_status="passed",
            recommended_plan_status="ready_for_validation",
            gate_results=[gate, gate],
            created_at=NOW,
        )


def test_legacy_gate_adapter_preserves_errors_and_warnings() -> None:
    result = GateResult.from_legacy(
        "legacy-reference-integrity",
        {
            "passed": False,
            "errors": ["unknown evidence id"],
            "warnings": ["metadata-only source"],
            "score": 0.2,
        },
        default_severity=Severity.P1,
    )

    assert result.is_blocking
    assert result.to_legacy() == {
        "passed": False,
        "errors": ["unknown evidence id"],
        "warnings": ["metadata-only source"],
        "score": 0.2,
    }

    with pytest.raises(ValueError, match="must be a boolean"):
        GateResult.from_legacy(
            "legacy-invalid",
            {
                "passed": "false",
                "errors": [],
                "warnings": [],
                "score": 0,
            },
        )


def test_audit_lineage_is_append_only_and_parent_ordered() -> None:
    submitted = AuditLineageEvent(
        event_id="event-001",
        event_type="feedback_submitted",
        occurred_at=NOW,
        actor_id="human-reviewer",
        subject_id="feedback-001",
        payload_sha256=_feedback_record().fingerprint(),
    )
    decided = AuditLineageEvent(
        event_id="event-002",
        event_type="feedback_decided",
        occurred_at=NOW,
        actor_id="feedback-policy-v1",
        subject_id="decision-001",
        parent_event_id="event-001",
        payload_sha256=_partial_decision().fingerprint(),
    )
    lineage = AuditLineage.start(
        _feedback_record(),
        lineage_id="lineage-001",
        event=submitted,
    ).bind_decision(
        _partial_decision(),
        decided,
    )

    extended = lineage.append(
        AuditLineageEvent(
            event_id="event-003",
            event_type="validation_completed",
            occurred_at=NOW,
            actor_id="validation-service",
            subject_id="report-001",
            parent_event_id="event-002",
            payload_sha256="d" * 64,
        )
    )
    assert [event.event_id for event in lineage.events] == [
        "event-001",
        "event-002",
    ]
    assert [event.event_id for event in extended.events] == [
        "event-001",
        "event-002",
        "event-003",
    ]
    assert extended.validation_report_id == "report-001"
    with pytest.raises(AttributeError):
        lineage.events.append(decided)

    with pytest.raises(ValidationError, match="unique"):
        AuditLineage.model_validate(
            {
                **lineage.model_dump(mode="json"),
                "events": [
                    submitted.model_dump(mode="json"),
                    submitted.model_dump(mode="json"),
                ],
            }
        )

    with pytest.raises(ValidationError, match="subject"):
        AuditLineage.model_validate(
            {
                **lineage.model_dump(mode="json"),
                "events": [
                    {
                        **submitted.model_dump(mode="json"),
                        "subject_id": "another-feedback",
                    },
                    decided.model_dump(mode="json"),
                ],
            }
        )

    with pytest.raises(ValidationError, match="resulting_version_id"):
        AuditLineage.model_validate(
            {
                **lineage.model_dump(mode="json"),
                "revision_diff_sha256": "e" * 64,
            }
        )


def test_rejected_decision_cannot_create_revision_lineage() -> None:
    submitted = AuditLineageEvent(
        event_id="event-rejected-001",
        event_type="feedback_submitted",
        occurred_at=NOW,
        actor_id="human-reviewer",
        subject_id="feedback-001",
        payload_sha256=_feedback_record().fingerprint(),
    )
    rejected = FeedbackDecision(
        decision_id="decision-rejected-001",
        feedback_id="feedback-001",
        target_version_id="run-demo:v1",
        disposition="rejected",
        decision_reason="The request removes verified evidence.",
        rejected_items=["删除已核验引用"],
        decided_by="feedback-policy-v1",
        decided_at=NOW,
        policy_version="t03-wave-a-v1",
    )
    decided = AuditLineageEvent(
        event_id="event-rejected-002",
        event_type="feedback_decided",
        occurred_at=NOW,
        actor_id="feedback-policy-v1",
        subject_id=rejected.decision_id,
        parent_event_id=submitted.event_id,
        payload_sha256=rejected.fingerprint(),
    )
    lineage = AuditLineage.start(
        _feedback_record(),
        lineage_id="lineage-rejected",
        event=submitted,
    ).bind_decision(rejected, decided)

    with pytest.raises(ValidationError, match="rejected feedback"):
        lineage.append(
            AuditLineageEvent(
                event_id="event-rejected-003",
                event_type="revision_requested",
                occurred_at=NOW,
                actor_id="revision-service",
                subject_id=rejected.decision_id,
                parent_event_id=decided.event_id,
                payload_sha256="b" * 64,
            )
        )


def test_revision_event_atomically_binds_version_and_diff_hash() -> None:
    submitted = AuditLineageEvent(
        event_id="event-revision-001",
        event_type="feedback_submitted",
        occurred_at=NOW,
        actor_id="human-reviewer",
        subject_id="feedback-001",
        payload_sha256=_feedback_record().fingerprint(),
    )
    decided = AuditLineageEvent(
        event_id="event-revision-002",
        event_type="feedback_decided",
        occurred_at=NOW,
        actor_id="feedback-policy-v1",
        subject_id="decision-001",
        parent_event_id=submitted.event_id,
        payload_sha256=_partial_decision().fingerprint(),
    )
    lineage = AuditLineage.start(
        _feedback_record(),
        lineage_id="lineage-revision",
        event=submitted,
    ).bind_decision(_partial_decision(), decided)
    requested = lineage.append(
        AuditLineageEvent(
            event_id="event-revision-003",
            event_type="revision_requested",
            occurred_at=NOW,
            actor_id="feedback-service",
            subject_id="decision-001",
            parent_event_id=decided.event_id,
            payload_sha256="b" * 64,
        )
    )
    generated = requested.append(
        AuditLineageEvent(
            event_id="event-revision-004",
            event_type="revision_generated",
            occurred_at=NOW,
            actor_id="revision-service",
            subject_id="run-demo:v2",
            parent_event_id="event-revision-003",
            payload_sha256="c" * 64,
        )
    )

    assert generated.resulting_version_id == "run-demo:v2"
    assert generated.revision_diff_sha256 == "c" * 64


def test_validated_objects_cannot_be_mutated_past_their_invariants() -> None:
    directive = HumanFeedbackDirective.from_feedback(
        _feedback_record(),
        _partial_decision(),
    )
    gate = GateResult(
        gate_id="schema",
        passed=True,
        severity=Severity.P3,
        score=1.0,
    )
    context = ValidationContext.model_validate(_context_payload())
    report = ValidationReport.from_context(
        context,
        report_id="report-immutable",
        validation_status="passed",
        recommended_plan_status="ready_for_validation",
        gate_results=[gate],
        created_at=NOW,
    )

    with pytest.raises(AttributeError):
        directive.instructions.append("rejected after validation")
    with pytest.raises(AttributeError):
        gate.findings.append(
            GateFinding(
                code="LATE_P0",
                message="A late blocker.",
                severity=Severity.P0,
            )
        )
    with pytest.raises(AttributeError):
        report.gate_results.append(_blocked_gate())

    assert deepcopy(report) == report
    assert report.passed
