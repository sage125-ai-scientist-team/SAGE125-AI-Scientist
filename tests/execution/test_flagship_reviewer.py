"""Tests for the real Qwen/Bailian scientific-reviewer closed loop (GAP-02).

These tests never perform a real network call: they monkeypatch
``QwenChatClient`` with a controllable fake so the *gating logic* (fail
closed on missing request_id / mock mode / schema violations / policy
overreach) can be verified deterministically and offline. The actual
end-to-end real-provider run is a separate, explicit, low-cost operation
performed outside the automated test suite.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.execution import flagship_reviewer as fr


ROUND1_RESULT = {
    "execution_id": "execution-test0001",
    "question_id": "Q028",
    "status": "succeeded",
    "actual_execution": True,
    "metrics": [
        {"name": "balanced_accuracy", "value": 0.9642857142857143},
        {"name": "malignant_recall", "value": 0.9285714285714286},
    ],
    "datasets": [{"sha256": "d606af41" * 8}],
    "seed": 125,
    "environment_fingerprint": {"git_dirty": False},
}

ROUND1_CONFIG = {
    "decision_threshold": 0.5,
    "seed": 125,
    "test_fraction": 0.2,
    "optimizer": {"iterations": 2000, "learning_rate": 0.05, "l2": 0.001},
    "round2_trigger": {"metric": "malignant_recall", "target": 0.95, "threshold_step": 0.1},
}

VALID_REVIEWER_JSON = {
    "review_id": "review-001",
    "passed": False,
    "critical_issues": [],
    "required_revisions": [
        {
            "issue_id": "req-rev-001",
            "severity": "P1",
            "affected_metric": "malignant_recall",
            "observed_value": 0.9285714285714286,
            "target_value": 0.95,
            "required_action": "decrease decision_threshold per allowed_revision_policy",
            "evidence_reference": "docs/modules/T05/round1/execution_result.json",
        }
    ],
    "comments": ["Round 1 balanced_accuracy is strong but malignant_recall misses target."],
}

VALID_V2_PLAN_JSON = {
    "plan_id": "plan-001",
    "responds_to_issue_ids": ["req-rev-001"],
    "proposed_changes": [
        {"field": "decision_threshold", "from": 0.5, "to": 0.4, "justification": "lower threshold to raise recall"}
    ],
    "expected_effect": "malignant_recall should increase at some cost to false positives",
}


class _FakeQwenClient:
    """Drop-in stand-in for QwenChatClient with a scripted response."""

    def __init__(self, *, response_text: str, request_id: str | None = "chatcmpl-fake-001", settings=None):
        self._response_text = response_text
        self.last_request_id = None
        self.last_usage: dict[str, Any] = {}
        self._request_id_to_set = request_id

    def chat(self, messages, model, temperature=0.1, response_format=None):  # noqa: ANN001
        self.last_request_id = self._request_id_to_set
        self.last_usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        return self._response_text


@pytest.fixture(autouse=True)
def _real_credentials_and_no_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most tests exercise the post-credential-check gating logic; make the
    credential/mock precheck pass by default and override per-test."""
    monkeypatch.setattr(fr, "is_mock_mode", lambda: False)

    class _FakeSettings:
        qwen_configured = True
        qwen_fast_model = "qwen3.6-flash"

    monkeypatch.setattr(fr, "get_settings", lambda: _FakeSettings())


def test_mock_mode_blocks_reviewer_call() -> None:
    import app.execution.flagship_reviewer as fr_module

    fr_module.is_mock_mode = lambda: True  # type: ignore[assignment]
    try:
        with pytest.raises(fr.FlagshipReviewerError) as exc_info:
            fr.assert_bailian_available()
        assert exc_info.value.gate == "BLOCKED_MOCK"
    finally:
        fr_module.is_mock_mode = lambda: False  # type: ignore[assignment]


def test_missing_credentials_blocks_reviewer_call(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Unconfigured:
        qwen_configured = False
        qwen_fast_model = "qwen3.6-flash"

    monkeypatch.setattr(fr, "get_settings", lambda: _Unconfigured())
    with pytest.raises(fr.FlagshipReviewerError) as exc_info:
        fr.assert_bailian_available()
    assert exc_info.value.gate == "BLOCKED_CREDENTIALS"


def test_reviewer_response_without_request_id_never_enters_chain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = _FakeQwenClient(response_text=json.dumps(VALID_REVIEWER_JSON), request_id=None)
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake)

    with pytest.raises(fr.FlagshipReviewerError) as exc_info:
        fr.call_scientific_reviewer(
            round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
        )
    assert exc_info.value.gate == "BLOCKED_NO_REQUEST_ID"


def test_mock_reviewer_output_marker_does_not_bypass_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A response that merely *claims* mock=true but otherwise matches the
    schema must still be rejected because 'mock' is not a declared field
    (extra='forbid') -- this proves the schema itself cannot be gamed by a
    provider echoing a mock marker instead of a real verdict."""
    payload = dict(VALID_REVIEWER_JSON)
    payload["mock"] = True
    fake = _FakeQwenClient(response_text=json.dumps(payload))
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake)

    with pytest.raises(fr.FlagshipReviewerError) as exc_info:
        fr.call_scientific_reviewer(
            round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
        )
    assert exc_info.value.gate == "BLOCKED_SCHEMA_INVALID"


def test_reviewer_output_missing_required_field_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = dict(VALID_REVIEWER_JSON)
    del payload["review_id"]
    fake = _FakeQwenClient(response_text=json.dumps(payload))
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake)

    with pytest.raises(fr.FlagshipReviewerError) as exc_info:
        fr.call_scientific_reviewer(
            round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
        )
    assert exc_info.value.gate == "BLOCKED_SCHEMA_INVALID"


def test_non_json_output_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = _FakeQwenClient(response_text="I cannot comply with JSON output.")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake)

    with pytest.raises(fr.FlagshipReviewerError) as exc_info:
        fr.call_scientific_reviewer(
            round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
        )
    assert exc_info.value.gate == "BLOCKED_SCHEMA_INVALID"


def test_valid_reviewer_call_produces_full_audit_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = _FakeQwenClient(response_text=json.dumps(VALID_REVIEWER_JSON), request_id="chatcmpl-abc123")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake)

    output, audit, hashes = fr.call_scientific_reviewer(
        round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
    )
    assert output.review_id == "review-001"
    assert output.passed is False
    assert len(output.required_revisions) == 1
    assert audit.provider == "bailian"
    assert audit.request_id == "chatcmpl-abc123"
    assert audit.role == "scientific_reviewer"
    assert audit.input_hash and audit.output_hash
    assert Path(audit.prompt_snapshot_path).exists()
    # No secret material should ever appear in the persisted prompt snapshot.
    snapshot_text = Path(audit.prompt_snapshot_path).read_text(encoding="utf-8")
    assert "DASHSCOPE_API_KEY" not in snapshot_text
    assert "Authorization" not in snapshot_text
    assert "sk-" not in snapshot_text


def test_v1_and_v2_prompt_hashes_differ_and_are_not_timestamp_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_reviewer = _FakeQwenClient(response_text=json.dumps(VALID_REVIEWER_JSON), request_id="chatcmpl-r1")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake_reviewer)
    reviewer_output, reviewer_audit, v1_hashes = fr.call_scientific_reviewer(
        round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
    )

    fake_v2 = _FakeQwenClient(response_text=json.dumps(VALID_V2_PLAN_JSON), request_id="chatcmpl-v2")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake_v2)
    v2_output, v2_audit, v2_hashes = fr.call_v2_revision_plan(
        reviewer_output=reviewer_output, round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG,
        provider_audit_reference=reviewer_audit.call_id, destination_dir=tmp_path,
    )

    assert v1_hashes["prompt_hash"] != v2_hashes["prompt_hash"]
    assert v1_hashes["input_hash"] != v2_hashes["input_hash"]

    # Re-running the *same* reviewer call context (same content) must yield
    # the identical prompt/input hash -- proving the difference above comes
    # from real content (reviewer feedback), not from timestamps/run IDs
    # embedded in the prompt.
    fake_reviewer_again = _FakeQwenClient(response_text=json.dumps(VALID_REVIEWER_JSON), request_id="chatcmpl-r1-again")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake_reviewer_again)
    _, _, v1_hashes_again = fr.call_scientific_reviewer(
        round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
    )
    assert v1_hashes_again["prompt_hash"] == v1_hashes["prompt_hash"]
    assert v1_hashes_again["input_hash"] == v1_hashes["input_hash"]


def test_v2_plan_not_citing_any_open_issue_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Truthfulness item #3: if the reviewer raised an open issue but the V2
    plan's ``responds_to_issue_ids`` cites none of it, this must never be
    treated as a genuine reviewer-driven revision."""
    fake_reviewer = _FakeQwenClient(response_text=json.dumps(VALID_REVIEWER_JSON), request_id="chatcmpl-r1")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake_reviewer)
    reviewer_output, reviewer_audit, _ = fr.call_scientific_reviewer(
        round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
    )

    unresponsive_plan = {**VALID_V2_PLAN_JSON, "responds_to_issue_ids": ["some-other-issue"]}
    fake_v2 = _FakeQwenClient(response_text=json.dumps(unresponsive_plan), request_id="chatcmpl-v2")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake_v2)

    with pytest.raises(fr.FlagshipReviewerError) as exc_info:
        fr.call_v2_revision_plan(
            reviewer_output=reviewer_output, round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG,
            provider_audit_reference=reviewer_audit.call_id, destination_dir=tmp_path,
        )
    assert exc_info.value.gate == "BLOCKED_ISSUE_NOT_ADDRESSED"


def test_v2_plan_citing_issue_but_no_proposed_changes_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Truthfulness item #8: citing the issue id alone (with an empty
    ``proposed_changes``) is not a substantive response."""
    fake_reviewer = _FakeQwenClient(response_text=json.dumps(VALID_REVIEWER_JSON), request_id="chatcmpl-r1")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake_reviewer)
    reviewer_output, reviewer_audit, _ = fr.call_scientific_reviewer(
        round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG, destination_dir=tmp_path,
    )

    hollow_plan = {**VALID_V2_PLAN_JSON, "proposed_changes": []}
    fake_v2 = _FakeQwenClient(response_text=json.dumps(hollow_plan), request_id="chatcmpl-v2")
    monkeypatch.setattr(fr, "QwenChatClient", lambda settings=None: fake_v2)

    with pytest.raises(fr.FlagshipReviewerError) as exc_info:
        fr.call_v2_revision_plan(
            reviewer_output=reviewer_output, round1_result=ROUND1_RESULT, round1_config=ROUND1_CONFIG,
            provider_audit_reference=reviewer_audit.call_id, destination_dir=tmp_path,
        )
    assert exc_info.value.gate == "BLOCKED_ISSUE_NOT_ADDRESSED"


def test_v2_plan_with_no_open_issues_does_not_require_response() -> None:
    """If the reviewer already passed (no open issues), there is nothing to
    respond to -- the gate must not fire."""
    passed_reviewer_output = fr.ScientificReviewerOutput.model_validate(
        {**VALID_REVIEWER_JSON, "passed": True, "required_revisions": [], "critical_issues": []}
    )
    empty_plan = fr.V2RevisionPlanOutput.model_validate(
        {"plan_id": "plan-noop", "responds_to_issue_ids": [], "proposed_changes": [], "expected_effect": ""}
    )
    fr._assert_v2_responds_to_open_issues(reviewer_output=passed_reviewer_output, v2_plan=empty_plan)


def test_policy_validator_authorizes_the_single_allowed_threshold_change() -> None:
    plan = fr.V2RevisionPlanOutput.model_validate(VALID_V2_PLAN_JSON)
    result = fr.validate_v2_plan_against_policy(plan)
    assert result.ok is True
    assert len(result.authorized_changes) == 1
    assert result.unauthorized_changes == []

    round2_config = fr.apply_policy_filtered_round2_config(ROUND1_CONFIG, result)
    assert round2_config["decision_threshold"] == 0.4
    # Everything else must remain byte-for-byte identical to Round 1.
    for key in ("seed", "test_fraction", "optimizer"):
        assert round2_config[key] == ROUND1_CONFIG[key]


@pytest.mark.parametrize(
    "unauthorized_change",
    [
        {"field": "seed", "from": 125, "to": 42, "justification": "try a different seed"},
        {"field": "dataset", "from": "wdbc-v1", "to": "wdbc-v2", "justification": "use a newer dataset"},
        {"field": "decision_threshold", "from": 0.5, "to": 0.1, "justification": "cherry-pick a better threshold"},
        {"field": "test_fraction", "from": 0.2, "to": 0.3, "justification": "change split"},
    ],
)
def test_policy_validator_rejects_unauthorized_changes(unauthorized_change: dict) -> None:
    plan = fr.V2RevisionPlanOutput.model_validate(
        {**VALID_V2_PLAN_JSON, "proposed_changes": [unauthorized_change]}
    )
    result = fr.validate_v2_plan_against_policy(plan)
    assert result.ok is False
    assert result.unauthorized_changes == [unauthorized_change]
    assert result.authorized_changes == []

    # An unauthorized change must never be applied to the executed config.
    round2_config = fr.apply_policy_filtered_round2_config(ROUND1_CONFIG, result)
    assert round2_config == ROUND1_CONFIG


def test_policy_validator_mixed_authorized_and_unauthorized_only_applies_authorized() -> None:
    plan = fr.V2RevisionPlanOutput.model_validate(
        {
            **VALID_V2_PLAN_JSON,
            "proposed_changes": [
                {"field": "decision_threshold", "from": 0.5, "to": 0.4, "justification": "ok"},
                {"field": "seed", "from": 125, "to": 7, "justification": "not ok"},
            ],
        }
    )
    result = fr.validate_v2_plan_against_policy(plan)
    assert result.ok is False
    assert len(result.authorized_changes) == 1
    assert len(result.unauthorized_changes) == 1

    round2_config = fr.apply_policy_filtered_round2_config(ROUND1_CONFIG, result)
    assert round2_config["decision_threshold"] == 0.4
    assert round2_config["seed"] == 125  # unauthorized change never applied
