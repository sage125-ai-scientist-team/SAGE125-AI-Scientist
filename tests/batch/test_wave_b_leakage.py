"""Wave B explicitly synthetic leakage and completion-gate tests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.batch.errors import BatchRunnerError


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "wave_b_leakage.synthetic.json"
)


def _api():
    import app.batch.leakage as leakage

    return leakage


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _records():
    api = _api()
    return tuple(api.LeakageRecord.from_mapping(value) for value in _payload()["records"])


def _result():
    return _api().detect_leakage(_records())


def _findings(code: str):
    return [finding for finding in _result().findings if finding.finding_code == code]


def test_fixture_is_explicitly_synthetic_mock_not_formal_or_actual() -> None:
    payload = _payload()

    assert payload["synthetic"] is True
    assert payload["mock"] is True
    assert payload["formal_run"] is False
    assert payload["actual_execution"] is False
    assert "not a historical or formal output" in payload["description"]


def test_q901_q902_pandemic_plan_reuse_is_detected() -> None:
    findings = _findings("CROSS_QUESTION_CONTENT_REUSE")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q901", "Q902")
    assert findings[0].blocks_completion is True


def test_cross_question_evidence_id_reuse_is_detected() -> None:
    findings = _findings("CROSS_QUESTION_EVIDENCE_ID_REUSE")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q901", "Q903")
    assert findings[0].observed_value == "EV-MOCK-0001"


def test_output_question_id_mismatch_is_detected() -> None:
    findings = _findings("OUTPUT_QUESTION_ID_MISMATCH")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q903", "Q999")


def test_cache_namespace_collision_is_detected() -> None:
    findings = _findings("CACHE_NAMESPACE_COLLISION")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q901", "Q902")


def test_memory_namespace_collision_is_detected() -> None:
    findings = _findings("MEMORY_NAMESPACE_COLLISION")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q901", "Q903")


def test_previous_result_reuse_is_detected() -> None:
    findings = _findings("PREVIOUS_RESULT_REUSE")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q901", "Q902")


def test_prompt_context_reuse_is_detected() -> None:
    findings = _findings("PROMPT_CONTEXT_REUSE")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q901", "Q902")


def test_question_owned_keyword_leakage_is_detected() -> None:
    findings = _findings("KEYWORD_LEAKAGE")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q901", "Q903")
    assert findings[0].observed_value == "prime lattice marker"


def test_similarity_above_point_nine_enters_nonblocking_review() -> None:
    findings = _findings("HIGH_CROSS_QUESTION_SIMILARITY")

    assert len(findings) == 1
    assert findings[0].question_ids == ("Q901", "Q902")
    assert findings[0].similarity_score is not None
    assert findings[0].similarity_score > 0.90
    assert findings[0].threshold == 0.90
    assert findings[0].severity == "review"
    assert findings[0].blocks_completion is False


def test_same_question_retry_does_not_emit_cross_question_finding() -> None:
    original = _records()[0]
    retry = replace(original)

    result = _api().detect_leakage((original, retry))

    assert result.finding_count == 0
    assert result.findings == ()


def test_finding_count_is_derived_from_actual_finding_array() -> None:
    result = _result()

    assert result.finding_count == len(result.findings)
    assert result.finding_count == 9
    assert {finding.finding_code for finding in result.findings} == {
        "CROSS_QUESTION_CONTENT_REUSE",
        "CROSS_QUESTION_EVIDENCE_ID_REUSE",
        "OUTPUT_QUESTION_ID_MISMATCH",
        "KEYWORD_LEAKAGE",
        "CACHE_NAMESPACE_COLLISION",
        "MEMORY_NAMESPACE_COLLISION",
        "PREVIOUS_RESULT_REUSE",
        "PROMPT_CONTEXT_REUSE",
        "HIGH_CROSS_QUESTION_SIMILARITY",
    }


def test_every_finding_has_the_auditable_required_structure() -> None:
    required = {
        "finding_code",
        "severity",
        "question_ids",
        "field",
        "observed_value",
        "evidence",
        "similarity_score",
        "threshold",
        "blocks_completion",
        "message",
    }

    assert set(_api().LeakageFinding.model_fields) == required
    for finding in _result().findings:
        assert finding.question_ids
        assert finding.field
        assert finding.observed_value
        assert finding.message


def test_completion_gate_separates_blockers_from_similarity_review() -> None:
    result = _result()

    decision = _api().evaluate_completion_gate(result)

    assert decision.allowed is False
    assert decision.blocking_findings
    assert all(finding.blocks_completion for finding in decision.blocking_findings)
    assert {finding.finding_code for finding in decision.review_findings} == {
        "HIGH_CROSS_QUESTION_SIMILARITY"
    }


def test_dry_run_cannot_generate_actual_result() -> None:
    unsafe = replace(_records()[0], result_kind="actual")

    with pytest.raises(BatchRunnerError) as raised:
        _api().detect_leakage((unsafe,))

    assert raised.value.error_code == "DRY_RUN_ACTUAL_RESULT"
