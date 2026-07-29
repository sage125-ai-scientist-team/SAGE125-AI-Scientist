"""T02 formal revision state, prompt, version, migration, and closure tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts.revision import (
    IssueClosure,
    PlanVersion,
    PlanVersionStore,
    ReviewFeedback,
    RevisionContext,
    RevisionPromptBuilder,
    RevisionState,
    deserialize_revision_state,
    issues_from_review_feedback,
    serialize_revision_state,
)


def _feedback(*, passed: bool, blocking: bool) -> ReviewFeedback:
    return ReviewFeedback(
        passed=passed,
        reviewer_comments=["请补充证伪阈值"],
        critical_issues=["缺少证伪判据"] if blocking else [],
        required_revisions=["补充阈值"] if blocking else [],
        evidence_grounding_score=0.7,
        falsifiability_score=0.6,
        reproducibility_score=0.8,
        reference_reliability_score=0.9,
    )


def test_review_feedback_effective_pass_requires_no_blockers() -> None:
    """passed=True alone cannot override critical issues or required revisions."""
    assert _feedback(passed=True, blocking=False).is_effective_pass
    assert not _feedback(passed=False, blocking=False).is_effective_pass
    assert not _feedback(passed=True, blocking=True).is_effective_pass


def test_prompt_builder_is_deterministic_and_injects_second_round_feedback() -> None:
    """Round 2 contains the complete prior feedback and has a stable new fingerprint."""
    question = {"id": "Q001", "question": "Q?", "domain": "synthetic"}
    evidence = [{"id": "EV-1", "title": "Evidence"}]
    first = RevisionContext(run_id="run-1", revision_iteration=1)
    feedback = _feedback(passed=False, blocking=True)
    second = RevisionContext(
        run_id="run-1",
        revision_iteration=2,
        review_feedback=feedback,
    )

    first_input = RevisionPromptBuilder.build_hypothesis_input(
        first,
        question_item=question,
        evidence_catalog=evidence,
        evidence_extraction={"established_facts": []},
    )
    second_input = RevisionPromptBuilder.build_hypothesis_input(
        second,
        question_item=question,
        evidence_catalog=evidence,
        evidence_extraction={"established_facts": []},
    )
    experiment_input = RevisionPromptBuilder.build_experiment_input(
        second,
        question_item=question,
        question_type="general_scientific_unknown",
        recommended_hypothesis={"hypothesis": "H2"},
        hypothesis_generation={"hypotheses": [{"hypothesis": "H2"}]},
        evidence_extraction={"established_facts": []},
        evidence_catalog=evidence,
    )

    assert first_input["revision_iteration"] == 1
    assert "review_result" not in first_input
    assert second_input["revision_iteration"] == 2
    assert second_input["review_result"] == feedback.model_dump(mode="json")
    assert experiment_input["review_result"] == feedback.model_dump(mode="json")
    first_fingerprint = RevisionPromptBuilder.fingerprint(first_input)
    second_fingerprint = RevisionPromptBuilder.fingerprint(second_input)
    assert first_fingerprint != second_fingerprint
    assert second_fingerprint == RevisionPromptBuilder.fingerprint(second_input)


def test_plan_version_store_saves_reads_and_restores_lineage() -> None:
    """The version store persists V1/V2, their parent link, feedback, and hashes."""
    blocking = _feedback(passed=False, blocking=True)
    issues = issues_from_review_feedback(blocking, opened_in_version=1)
    v1 = PlanVersion.create(
        run_id="run-versions",
        version_number=1,
        revision_iteration=1,
        hypothesis_generation={"hypotheses": ["H1"]},
        experiment_design={"methods": "M1"},
        review_feedback=blocking,
        issue_closures=issues,
        prompt_fingerprints={"hypothesis_generator": "hash-v1"},
    )
    v2 = PlanVersion.create(
        run_id="run-versions",
        version_number=2,
        parent_version_id=v1.version_id,
        revision_iteration=2,
        hypothesis_generation={"hypotheses": ["H2"]},
        experiment_design={"methods": "M2"},
        review_feedback=_feedback(passed=True, blocking=False),
        prompt_fingerprints={"hypothesis_generator": "hash-v2"},
    )

    store = PlanVersionStore()
    store.save(v1)
    store.save(v2)
    restored = PlanVersionStore.deserialize(store.serialize())

    assert restored.get("run-versions", 1).version_id == "run-versions:v1"
    restored_v2 = restored.get("run-versions", 2)
    assert restored_v2.parent_version_id == "run-versions:v1"
    assert restored_v2.revision_iteration == 2
    assert restored_v2.hypothesis_generation == {"hypotheses": ["H2"]}
    assert restored_v2.prompt_fingerprints["hypothesis_generator"] == "hash-v2"


def test_revision_state_serialization_round_trip_preserves_contract_fields() -> None:
    """serialize -> deserialize keeps iteration, versions, lineage, and review data."""
    passed = _feedback(passed=True, blocking=False)
    v1 = PlanVersion.create(
        run_id="run-roundtrip",
        version_number=1,
        revision_iteration=1,
        hypothesis_generation={"hypotheses": ["H1"]},
    )
    v2 = PlanVersion.create(
        run_id="run-roundtrip",
        version_number=2,
        parent_version_id=v1.version_id,
        revision_iteration=2,
        hypothesis_generation={"hypotheses": ["H2"]},
        review_feedback=passed,
    )
    state = RevisionState(
        context=RevisionContext(
            run_id="run-roundtrip",
            revision_iteration=2,
            review_feedback=passed,
        ),
        versions=[v1, v2],
        validation_status="ready_for_validation",
    )

    restored = deserialize_revision_state(serialize_revision_state(state))

    assert restored == state
    assert restored.context.revision_iteration == 2
    assert restored.context.review_feedback == passed
    assert restored.versions[1].parent_version_id == restored.versions[0].version_id


def test_legacy_state_migration_defaults_missing_new_fields() -> None:
    """Old unversioned payloads restore conservatively without losing old plan data."""
    legacy = {
        "run_id": "legacy-run",
        "iteration": 1,
        "plan_versions": [
            {
                "version": 1,
                "hypothesis_generation": {"hypotheses": ["legacy-H1"]},
            }
        ],
    }

    restored = deserialize_revision_state(legacy)

    assert restored.schema_version == 1
    assert restored.context.run_id == "legacy-run"
    assert restored.context.revision_iteration == 1
    assert restored.context.review_feedback is None
    assert restored.context.issue_closures == []
    assert restored.validation_status == "draft"
    assert restored.versions[0].version_id == "legacy-run:v1"
    assert restored.versions[0].hypothesis_generation["hypotheses"] == ["legacy-H1"]


def test_second_round_blockers_force_draft_and_remain_open() -> None:
    """A blocking second review cannot become ready or silently close its issues."""
    feedback = _feedback(passed=True, blocking=True)
    issues = issues_from_review_feedback(feedback, opened_in_version=2)
    context = RevisionContext(
        run_id="blocked-run",
        revision_iteration=2,
        review_feedback=feedback,
        issue_closures=issues,
    )

    draft = RevisionState(
        context=context,
        validation_status="draft",
    )
    assert draft.validation_status == "draft"
    assert all(issue.status == "open" for issue in draft.context.issue_closures)
    with pytest.raises(ValidationError, match="draft terminal state"):
        RevisionState(
            context=context,
            validation_status="ready_for_validation",
        )


def test_issue_closure_requires_a_valid_resolution_version() -> None:
    """IssueClosure cannot claim resolution without a valid closing version."""
    with pytest.raises(ValidationError, match="requires closed_in_version"):
        IssueClosure(
            issue_id="required_revision:abc",
            category="required_revision",
            description="补充阈值",
            status="resolved",
            opened_in_version=1,
        )
    resolved = IssueClosure(
        issue_id="required_revision:abc",
        category="required_revision",
        description="补充阈值",
        status="resolved",
        opened_in_version=1,
        closed_in_version=2,
        resolution_note="V2 已补充可证伪阈值",
    )
    assert resolved.closed_in_version == 2
