"""Keep the two Wave A baseline failures machine-readable and reviewable."""

from __future__ import annotations

import json
from pathlib import Path


EXAMPLES = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "modules"
    / "T03"
    / "examples"
)


def _load(filename: str) -> dict:
    return json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))


def test_feedback_baseline_records_missing_next_round_input() -> None:
    sample = _load("baseline.feedback_not_propagated.json")

    observed = set(sample["observed_next_hypothesis_input_keys"])
    required = set(sample["required_next_input_keys"])
    assert required - observed == set(sample["missing_next_input_keys"])
    assert sample["expected_outcome"] == "blocking_failure"


def test_validator_baseline_records_all_four_missing_artifacts() -> None:
    sample = _load("baseline.validator_question_only.json")

    observed = set(sample["observed_validator_input"])
    required = set(sample["required_validator_input_keys"])
    assert required - observed == set(sample["missing_validator_input_keys"])
    assert sample["missing_validator_input_keys"] == [
        "research_plan",
        "evidence_cards",
        "agent_trace",
        "execution_metadata",
    ]
