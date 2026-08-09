"""Production-path regressions for the T02 -> T03 revision handoff.

These tests stop at the T02 owner boundary.  T03 remains responsible for
atomically appending the emitted handoff to its persisted ``AuditLineage``.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from app.agents.experiment_designer import ExperimentDesignerAgent
from app.agents.hypothesis_generator import HypothesisGeneratorAgent
from app.agents.scientific_reviewer import ScientificReviewerAgent
from app.contracts.revision import ReviewFeedback
from app.contracts.validation import HumanFeedbackDirective
from app.core.config import get_settings
from app.workflow import explainable_revision as revision_api
from app.workflow import pipeline
from tests.helpers_questions_fixture import write_minimal_questions_fixture


ACCEPTED = "Keep the reviewer-requested negative control explicit."
REJECTED = "Delete verified evidence."
RAW_FEEDBACK = f"{ACCEPTED} {REJECTED}"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _blocking_feedback() -> ReviewFeedback:
    return ReviewFeedback(
        passed=False,
        reviewer_comments=["Apply the accepted human instruction."],
        critical_issues=["The negative control is missing."],
        required_revisions=["Add a negative control backed by evidence."],
        risk_level="high",
        evidence_grounding_score=0.3,
        falsifiability_score=0.4,
        reproducibility_score=0.5,
        reference_reliability_score=0.6,
    )


def _clear_feedback() -> ReviewFeedback:
    return ReviewFeedback(
        passed=True,
        reviewer_comments=["The negative-control issue is resolved."],
        risk_level="low",
        evidence_grounding_score=0.8,
        falsifiability_score=0.8,
        reproducibility_score=0.9,
        reference_reliability_score=0.9,
    )


@pytest.fixture
def paired_t02_run(monkeypatch, tmp_path):
    questions = write_minimal_questions_fixture(tmp_path / "questions_125.json")
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(questions))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_REVIEW_FAIL", "true")
    monkeypatch.setattr(pipeline, "generate_run_id", lambda: "t02-t03-pair")
    get_settings.cache_clear()

    directive = HumanFeedbackDirective(
        feedback_id="feedback-pair-001",
        target_version_id="t02-t03-pair:v1",
        disposition="partially_accepted",
        instructions=(ACCEPTED,),
        original_feedback_sha256=hashlib.sha256(
            RAW_FEEDBACK.encode("utf-8")
        ).hexdigest(),
    )
    captured_messages: dict[str, dict] = {}
    original_hypothesis_run = HypothesisGeneratorAgent.run
    original_experiment_run = ExperimentDesignerAgent.run
    experiment_calls = 0
    review_calls = 0

    def capture_hypothesis(self, input_data, state, step_index=0):
        if input_data.get("revision_iteration") == 2:
            captured_messages["hypothesis"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
        return original_hypothesis_run(self, input_data, state, step_index)

    def revise_experiment(self, input_data, state, step_index=0):
        nonlocal experiment_calls
        experiment_calls += 1
        if input_data.get("revision_iteration") == 2:
            captured_messages["experiment"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
        result = original_experiment_run(self, input_data, state, step_index)
        if experiment_calls == 2:
            result = copy.deepcopy(result)
            result["experiments"] = copy.deepcopy(result.get("experiments") or {})
            result["experiments"]["baselines"] = list(
                result["experiments"].get("baselines") or []
            ) + ["reviewer-requested-negative-control"]
            result["experiments"]["evidence_refs"] = [
                card.id for card in state.retrieved_evidence[:1]
            ]
        return result

    def controlled_reviewer(self, input_data, state, step_index=0):
        nonlocal review_calls
        review_calls += 1
        if input_data.get("revision_iteration") == 2:
            captured_messages["reviewer"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
        feedback = _blocking_feedback() if review_calls == 1 else _clear_feedback()
        return feedback.model_dump(mode="json")

    monkeypatch.setattr(HypothesisGeneratorAgent, "run", capture_hypothesis)
    monkeypatch.setattr(ExperimentDesignerAgent, "run", revise_experiment)
    monkeypatch.setattr(ScientificReviewerAgent, "run", controlled_reviewer)
    try:
        _plan, state = pipeline.run_pipeline_with_state(
            "Q001",
            mock_mode=True,
            human_feedback_directive=directive,
        )
    finally:
        get_settings.cache_clear()

    trace = next(event for event in state.agent_trace if event.get("revision_audit"))
    return {
        "directive": directive,
        "messages": captured_messages,
        "state": state,
        "trace": trace,
    }


def test_agent_payload_has_frozen_top_level_accepted_only_receipt(
    paired_t02_run,
) -> None:
    messages = paired_t02_run["messages"]
    assert set(messages) == {"hypothesis", "experiment", "reviewer"}
    for message in messages.values():
        receipt = message["human_feedback"]
        assert receipt == {
            "schema_version": 1,
            "feedback_id": "feedback-pair-001",
            "source_version_id": "t02-t03-pair:v1",
            "disposition": "partially_accepted",
            "applied_instructions": [ACCEPTED],
            "original_feedback_sha256": paired_t02_run[
                "directive"
            ].original_feedback_sha256,
        }
        assert message["revision_context"]["human_feedback"]["feedback_id"] == (
            receipt["feedback_id"]
        )
        serialized = json.dumps(message, ensure_ascii=False, sort_keys=True)
        assert REJECTED not in serialized
        assert RAW_FEEDBACK not in serialized

        frozen = revision_api.HumanFeedbackReceipt.model_validate(receipt)
        assert revision_api.HumanFeedbackReceipt.model_validate_json(
            frozen.model_dump_json()
        ) == frozen
        with pytest.raises(ValidationError):
            frozen.feedback_id = "mutated"  # type: ignore[misc]


def test_revision_metadata_and_trace_use_one_canonical_diff_hash(
    paired_t02_run,
) -> None:
    trace = paired_t02_run["trace"]
    structured_diff = {
        "changes": trace["revision_audit"]["changes"],
        "substantive_sections": trace["revision_audit"]["substantive_sections"],
    }
    expected_hash = _canonical_sha256(structured_diff)
    metadata = paired_t02_run["state"].execution_metadata["revision_metadata"]

    assert metadata["feedback_id"] == "feedback-pair-001"
    assert metadata["source_version_id"] == "t02-t03-pair:v1"
    assert metadata["resulting_version_id"] == "t02-t03-pair:v2"
    assert metadata["applied_instructions"] == [ACCEPTED]
    assert metadata["diff_hash"] == expected_hash
    assert trace["revision_diff_sha256"] == expected_hash

    snapshot = revision_api.RevisionMetadata.model_validate(metadata)
    assert revision_api.RevisionMetadata.model_validate_json(
        snapshot.model_dump_json()
    ) == snapshot
    conflicting = snapshot.model_copy(update={"diff_hash": "0" * 64})
    with pytest.raises(ValueError, match="conflicting revision_metadata"):
        revision_api.attach_revision_metadata(
            {"revision_metadata": conflicting.model_dump(mode="json")},
            snapshot,
        )


def test_t02_lineage_handoff_is_strict_stable_and_append_ready(
    paired_t02_run,
) -> None:
    trace = paired_t02_run["trace"]
    handoff = trace["revision_lineage_handoff"]
    event_types = [event["event_type"] for event in handoff["events"]]

    assert event_types[:2] == ["revision_requested", "revision_generated"]
    assert event_types[2:]
    assert set(event_types[2:]) == {"issue_closed"}
    assert handoff["feedback_id"] == "feedback-pair-001"
    assert handoff["source_version_id"] == "t02-t03-pair:v1"
    assert handoff["resulting_version_id"] == "t02-t03-pair:v2"
    assert handoff["revision_diff_sha256"] == trace["revision_diff_sha256"]
    assert handoff["required_parent_event_type"] == "feedback_decided"
    assert handoff["events"][0]["parent_event_id"] is None
    assert all(
        event["parent_event_id"] == handoff["events"][index - 1]["event_id"]
        for index, event in enumerate(handoff["events"])
        if index > 0
    )
    assert len({event["event_id"] for event in handoff["events"]}) == len(
        handoff["events"]
    )
    assert handoff["events"][1]["payload_sha256"] == trace[
        "revision_diff_sha256"
    ]
    assert not {"gate_evaluated", "validation_completed"} & set(event_types)

    snapshot = revision_api.RevisionLineageHandoff.model_validate(handoff)
    assert revision_api.RevisionLineageHandoff.model_validate_json(
        snapshot.model_dump_json()
    ) == snapshot

    audit = revision_api.ExplainableRevisionAudit.model_validate(
        trace["revision_audit"]
    )
    rebuilt_metadata, rebuilt_handoff = revision_api.build_revision_pairing_outputs(
        audit=audit,
        human_feedback=paired_t02_run["directive"],
        resulting_version_id="t02-t03-pair:v2",
        prompt_fingerprint=paired_t02_run["state"].execution_metadata[
            "revision_metadata"
        ]["prompt_fingerprint"],
    )
    assert rebuilt_metadata.model_dump(mode="json") == paired_t02_run[
        "state"
    ].execution_metadata["revision_metadata"]
    assert rebuilt_handoff == snapshot

    tampered = snapshot.model_dump(mode="json")
    tampered["events"][1]["payload_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="structured diff"):
        revision_api.RevisionLineageHandoff.model_validate(tampered)
