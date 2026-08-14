"""Fail-closed preparation tests for the blocked T02 Wave C release run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.workflow.revision_consumer import RevisionConsumerRecord, RevisionConsumerStore
from app.workflow.wave_c_release import (
    CaptainCaseAuthorization,
    Metric004Evidence,
    ReleaseCaseResult,
    ReleaseSelectionManifest,
    T02WaveCReleaseHarness,
    canonical_sha256,
    release_schema_bundle,
)


FIXTURE = Path(__file__).parent / "fixtures" / "t02_consumer" / "v1_to_v2.json"
CAPTAIN_REFERENCE = (
    "https://github.com/sage125-ai-scientist-team/"
    "SAGE125-AI-Scientist/pull/37#issuecomment-5263000000"
)
GIT_SHA = "1" * 40


def _authorization(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "captain_approved",
        "reviewer_login": "captain-example",
        "reference_url": CAPTAIN_REFERENCE,
        "authorized_at": "2026-08-12T12:00:00+00:00",
        "random_case_ids": ["Q001", "Q050", "Q107"],
        "random_seed": 125,
        "selection_policy": "Captain-supplied fixed IDs",
        "q028_flagship_execution": "independent_runs",
        "metric004_semantic": "random_case_count",
    }
    payload.update(updates)
    return payload


def _case(
    label: str,
    question_id: str,
    *,
    input_hash: str,
    question: str,
    source_reference: str = "data/processed/questions_125.json",
    shared_run_key: str | None = None,
) -> dict[str, Any]:
    return {
        "requirement_label": label,
        "question_id": question_id,
        "canonical_input": {"id": question_id, "question": question},
        "canonical_question": question,
        "input_hash": input_hash,
        "source_reference": source_reference,
        "shared_run_key": shared_run_key,
    }


def _manifest(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "authorization": _authorization(),
        "selected_at": "2026-08-12T12:05:00+00:00",
        "git_sha": GIT_SHA,
        "cases": [
            _case(
                "Q028",
                "Q028",
                input_hash=(
                    "badcae2fec281a0bbaec81b36d8ed4a149696db855d0f399e7cbe382fdc78da8"
                ),
                question="Will it be possible to cure all cancers?",
            ),
            _case(
                "flagship",
                "Q028",
                input_hash=(
                    "badcae2fec281a0bbaec81b36d8ed4a149696db855d0f399e7cbe382fdc78da8"
                ),
                question="Will it be possible to cure all cancers?",
                source_reference="experiments/flagship/selection_manifest.json",
            ),
            _case("random_1", "Q001", input_hash="a" * 64, question="Question 1"),
            _case("random_2", "Q050", input_hash="b" * 64, question="Question 50"),
            _case("random_3", "Q107", input_hash="c" * 64, question="Question 107"),
        ],
    }
    payload.update(updates)
    return payload


def _valid_result() -> ReleaseCaseResult:
    record = RevisionConsumerRecord.model_validate(
        json.loads(FIXTURE.read_text(encoding="utf-8"))
    )
    assert record.revision_context is not None
    assert record.revision_audit is not None
    first, second = record.plan_versions
    assert first.review_feedback is not None
    scores = record.revision_audit.score_changes
    return ReleaseCaseResult(
        requirement_label="random_1",
        question_id="Q001",
        canonical_input={"id": "Q001", "question": "Question 1"},
        input_hash="a" * 64,
        run_id=record.run_id,
        job_id=record.job_id,
        started_at=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 8, 12, 12, 1, tzinfo=timezone.utc),
        model="authorized-real-model",
        v1_version_id=first.version_id,
        v2_version_id=second.version_id,
        v1_prompt_hash="1" * 12,
        v2_prompt_hash="2" * 12,
        reviewer_feedback=first.review_feedback,
        required_revisions=tuple(first.review_feedback.required_revisions),
        revision_context=record.revision_context,
        feedback_fingerprint=canonical_sha256(
            first.review_feedback.model_dump(mode="json")
        ),
        revision_context_fingerprint=canonical_sha256(
            record.revision_context.model_dump(mode="json")
        ),
        structured_diff=record.version_diffs[0].diff,
        diff_hash=record.version_diffs[0].diff_hash,
        issue_closures=second.issue_closures,
        score_before={name: value.before for name, value in scores.items()},
        score_after={name: value.after for name, value in scores.items()},
        score_delta={name: value.delta for name, value in scores.items()},
        lineage=RevisionConsumerStore([record]).get_lineage(run_id=record.run_id),
        stop_reason=record.revision_control.stop_reason,
        unresolved_p0=0,
        unresolved_p1=0,
        validation_result="passed",
        execution_status="succeeded",
        evidence_provenance=("exports/authorized-run/agent_trace.json",),
        git_sha=GIT_SHA,
        same_prompt_hash_false_iteration=False,
        passed=True,
    )


def test_release_manifest_requires_explicit_captain_authorization() -> None:
    missing = _manifest()
    del missing["authorization"]
    with pytest.raises(ValidationError, match="authorization"):
        ReleaseSelectionManifest.model_validate(missing)

    placeholder = _manifest(authorization=_authorization(selection_policy="PENDING"))
    with pytest.raises(ValidationError, match="real authorized value"):
        ReleaseSelectionManifest.model_validate(placeholder)


def test_release_manifest_binds_exact_case_set_to_captain_decision() -> None:
    manifest = ReleaseSelectionManifest.model_validate(_manifest())

    assert [case.requirement_label for case in manifest.cases] == [
        "Q028",
        "flagship",
        "random_1",
        "random_2",
        "random_3",
    ]
    assert tuple(case.question_id for case in manifest.cases[2:]) == (
        "Q001",
        "Q050",
        "Q107",
    )

    mismatched = _manifest(
        authorization=_authorization(random_case_ids=["Q002", "Q050", "Q107"])
    )
    with pytest.raises(ValidationError, match="do not match Captain authorization"):
        ReleaseSelectionManifest.model_validate(mismatched)


def test_shared_q028_flagship_run_requires_explicit_shared_key() -> None:
    payload = _manifest(
        authorization=_authorization(q028_flagship_execution="shared_run")
    )
    with pytest.raises(ValidationError, match="shared_run_key"):
        ReleaseSelectionManifest.model_validate(payload)

    payload["cases"][0]["shared_run_key"] = "captain-shared-q028"
    payload["cases"][1]["shared_run_key"] = "captain-shared-q028"
    manifest = ReleaseSelectionManifest.model_validate(payload)
    assert manifest.authorization.q028_flagship_execution == "shared_run"


def test_harness_verifies_authority_before_inputs_or_execution() -> None:
    calls: list[str] = []

    def reject_authority(_authorization: CaptainCaseAuthorization) -> None:
        calls.append("authority")
        raise RuntimeError("Captain reference is not verified")

    harness = T02WaveCReleaseHarness(
        _manifest(),
        authorization_verifier=reject_authority,
        canonical_input_verifier=lambda _case: calls.append("input"),
        executor=lambda _case: calls.append("execute"),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="not verified"):
        harness.run()
    assert calls == ["authority"]


def test_harness_verifies_every_canonical_input_before_execution() -> None:
    calls: list[str] = []

    def verify_input(case) -> None:
        calls.append(f"input:{case.requirement_label}")
        if case.requirement_label == "random_2":
            raise ValueError("canonical input unavailable")

    harness = T02WaveCReleaseHarness(
        _manifest(),
        authorization_verifier=lambda _authorization: calls.append("authority"),
        canonical_input_verifier=verify_input,
        executor=lambda _case: calls.append("execute"),  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="canonical input unavailable"):
        harness.run()
    assert "execute" not in calls
    assert calls[:2] == ["authority", "input:Q028"]


def test_release_case_rejects_same_prompt_hash_false_pass() -> None:
    result = _valid_result()
    forged = result.model_dump(mode="json")
    forged["v2_prompt_hash"] = forged["v1_prompt_hash"]
    forged["same_prompt_hash_false_iteration"] = True

    with pytest.raises(ValidationError, match="case PASS"):
        ReleaseCaseResult.model_validate(forged)


def test_release_case_rejects_forged_diff_hash_and_open_issue_counts() -> None:
    result = _valid_result()
    forged_hash = result.model_dump(mode="json")
    forged_hash["diff_hash"] = "f" * 64
    with pytest.raises(ValidationError, match="diff hash"):
        ReleaseCaseResult.model_validate(forged_hash)

    forged_count = result.model_dump(mode="json")
    forged_count["unresolved_p0"] = 1
    with pytest.raises(ValidationError, match="unresolved P0/P1"):
        ReleaseCaseResult.model_validate(forged_count)


def test_release_case_cannot_downgrade_actual_run_to_mock() -> None:
    result = _valid_result().model_dump(mode="json")
    result["mode"] = "mock"
    result["mock_mode"] = True
    result["truth_status"] = "mock"

    with pytest.raises(ValidationError, match="literal_error"):
        ReleaseCaseResult.model_validate(result)


def test_metric004_is_only_the_authorized_random_case_quantity() -> None:
    failed = Metric004Evidence(
        random_case_executed=3,
        random_case_passed=2,
        selection_manifest_sha256="a" * 64,
        raw_results_sha256="b" * 64,
        git_sha=GIT_SHA,
        passed=False,
    )
    assert failed.authorized_semantic == "random_case_count"

    forged_pass = failed.model_dump(mode="json")
    forged_pass["passed"] = True
    with pytest.raises(ValidationError, match="authorized count"):
        Metric004Evidence.model_validate(forged_pass)

    invented_metric = failed.model_dump(mode="json")
    invented_metric["authorized_semantic"] = "three_independent_thresholds"
    with pytest.raises(ValidationError, match="literal_error"):
        Metric004Evidence.model_validate(invented_metric)


def test_release_schemas_forbid_unknown_top_level_fields() -> None:
    schemas = release_schema_bundle()

    assert set(schemas) == {
        "selection_manifest",
        "dataset_manifest",
        "raw_results",
        "metric004",
        "regression_matrix",
    }
    assert all(schema["additionalProperties"] is False for schema in schemas.values())

    unknown = _manifest(unexpected_field=True)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ReleaseSelectionManifest.model_validate(unknown)
