"""T02 Gate 0 stable consumer reads and fail-closed fixture coverage."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "t02_consumer"
VALID_FIXTURES = (
    "v1_only",
    "v1_to_v2",
    "open_p0_p1",
    "stopped_failed",
)


def _api() -> Any:
    try:
        return importlib.import_module("app.workflow.revision_consumer")
    except ModuleNotFoundError as exc:
        if exc.name == "app.workflow.revision_consumer":
            pytest.fail(
                "T02 Gate 0: stable revision consumer wrapper is missing",
                pytrace=False,
            )
        raise


def _payload(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text(encoding="utf-8"))


def _record(name: str):
    return _api().RevisionConsumerRecord.model_validate(_payload(name))


def _store():
    api = _api()
    return api.RevisionConsumerStore([_record(name) for name in VALID_FIXTURES])


def test_gate0_lists_plan_versions_by_run_or_job() -> None:
    store = _store()

    by_run = store.list_plan_versions(run_id="gate0-v1-v2")
    by_job = store.list_plan_versions(job_id="job-gate0-v1-v2")

    assert [item.version_id for item in by_run] == [
        "gate0-v1-v2:v1",
        "gate0-v1-v2:v2",
    ]
    assert by_run == by_job
    by_run[0].hypothesis_generation["mutated"] = True
    assert "mutated" not in store.get_plan_version("gate0-v1-v2:v1").hypothesis_generation


def test_gate0_reads_diff_by_target_version() -> None:
    store = _store()

    envelope = store.get_version_diff("gate0-v1-v2:v2")

    assert envelope.source_version_id == "gate0-v1-v2:v1"
    assert envelope.target_version_id == "gate0-v1-v2:v2"
    assert {item.affected_plan_section for item in envelope.diff.changes} == {
        "control_groups",
        "stopping_conditions",
    }
    assert envelope.diff_hash == envelope.diff.fingerprint()


def test_gate0_reads_reviewer_issues_and_latest_closures() -> None:
    store = _store()

    issues = store.get_reviewer_issues(run_id="gate0-v1-v2")
    closures = store.get_issue_closures(run_id="gate0-v1-v2")

    assert {(item.priority, item.description) for item in issues} == {
        ("P0", "No negative control is defined."),
        ("P1", "Add a negative control and stopping rule."),
    }
    assert {item.status for item in closures} == {"resolved"}
    assert all(item.resolution_note for item in closures)


def test_gate0_reads_score_delta_and_lineage() -> None:
    store = _store()

    deltas = store.get_score_deltas("gate0-v1-v2:v2")
    lineage = store.get_lineage(job_id="job-gate0-v1-v2")

    assert deltas["reproducibility_score"].delta == pytest.approx(0.4)
    assert lineage.version_ids == (
        "gate0-v1-v2:v1",
        "gate0-v1-v2:v2",
    )
    assert lineage.parents == {
        "gate0-v1-v2:v1": None,
        "gate0-v1-v2:v2": "gate0-v1-v2:v1",
    }
    assert len(lineage.lineage_hash) == 64


def test_gate0_reads_stop_reason_and_open_p0_p1() -> None:
    store = _store()

    assert store.get_stop_reason(run_id="gate0-stopped-failed") == (
        "retry_budget_exhausted"
    )
    assert store.get_stop_reason(run_id="gate0-v1-only") is None
    open_issues = store.get_open_p0_p1(job_id="job-gate0-open-p0-p1")

    assert [(item.priority, item.status) for item in open_issues] == [
        ("P0", "open"),
        ("P1", "open"),
    ]


def test_gate0_invalid_lineage_and_hash_fail_closed() -> None:
    api = _api()

    with pytest.raises(ValidationError, match="lineage|parent"):
        api.RevisionConsumerRecord.model_validate(_payload("invalid_lineage"))

    forged = _payload("v1_to_v2")
    forged["version_diffs"][0]["diff_hash"] = "f" * 64
    with pytest.raises(ValidationError, match="diff hash"):
        api.RevisionConsumerRecord.model_validate(forged)


def test_gate0_context_and_issue_history_tampering_fail_closed() -> None:
    api = _api()

    wrong_feedback = _payload("v1_to_v2")
    wrong_feedback["revision_context"]["reviewer_feedback"]["reviewer_comments"] = [
        "Forged context feedback."
    ]
    with pytest.raises(ValidationError, match="context reviewer feedback"):
        api.RevisionConsumerRecord.model_validate(wrong_feedback)

    missing_issue = _payload("v1_to_v2")
    missing_issue["revision_context"]["unresolved_issues"].pop()
    with pytest.raises(ValidationError, match="context unresolved issues"):
        api.RevisionConsumerRecord.model_validate(missing_issue)

    future_issue = _payload("open_p0_p1")
    future_issue["plan_versions"][0]["issue_closures"][0][
        "opened_in_version"
    ] = 2
    with pytest.raises(ValidationError, match="first appearance"):
        api.RevisionConsumerRecord.model_validate(future_issue)


def test_gate0_terminal_audit_state_mismatch_fails_closed() -> None:
    api = _api()
    payload = _payload("v1_to_v2")
    payload["revision_control"]["status"] = "active"

    with pytest.raises(ValidationError, match="terminal state"):
        api.RevisionConsumerRecord.model_validate(payload)


def test_gate0_unknown_or_ambiguous_reads_fail_closed() -> None:
    api = _api()
    store = _store()

    with pytest.raises(ValueError, match="exactly one"):
        store.list_plan_versions()
    with pytest.raises(ValueError, match="exactly one"):
        store.list_plan_versions(
            run_id="gate0-v1-only",
            job_id="job-gate0-v1-only",
        )
    with pytest.raises(KeyError, match="unknown job_id"):
        store.get_lineage(job_id="missing-job")
    with pytest.raises(KeyError, match="unknown version"):
        store.get_version_diff("gate0-v1-only:v1")

    duplicate = _record("v1_only").model_copy(
        update={"job_id": "job-gate0-v1-v2"},
        deep=True,
    )
    with pytest.raises(ValueError, match="duplicate job_id"):
        api.RevisionConsumerStore([*_store().records, duplicate])


def test_gate0_future_schema_and_unknown_fields_fail_closed() -> None:
    api = _api()

    future = _payload("v1_only")
    future["schema_version"] = 2
    with pytest.raises(ValidationError, match="schema_version"):
        api.RevisionConsumerRecord.model_validate(future)

    unknown = _payload("v1_only")
    unknown["unexpected_field"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        api.RevisionConsumerRecord.model_validate(unknown)
