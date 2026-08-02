from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "contamination_cases.synthetic.json"
)


def _payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _detect() -> list[Any]:
    from app.batch.contamination import detect_cross_question_contamination

    return detect_cross_question_contamination(_payload()["records"])


def test_contamination_fixture_is_explicitly_synthetic_mock() -> None:
    payload = _payload()

    assert payload["synthetic"] is True
    assert payload["mock"] is True
    assert all(
        record["output"]["question_id"] != "actual"
        for record in payload["records"]
    )


def test_detector_flags_identical_content_across_question_ids() -> None:
    findings = _detect()
    duplicated = [
        finding
        for finding in findings
        if finding.error_code == "CROSS_QUESTION_CONTENT_REUSE"
    ]

    assert len(duplicated) == 1
    assert duplicated[0].question_ids == ("Q901", "Q902")
    assert "pandemic" in duplicated[0].message.lower()


def test_detector_flags_evidence_id_reused_across_questions() -> None:
    findings = _detect()
    reused = [
        finding
        for finding in findings
        if finding.error_code == "CROSS_QUESTION_EVIDENCE_ID_REUSE"
    ]

    assert len(reused) == 1
    assert reused[0].question_ids == ("Q901", "Q903")
    assert reused[0].evidence_id == "EV-MOCK-0001"


def test_detector_flags_output_question_identity_mismatch() -> None:
    findings = _detect()
    mismatches = [
        finding
        for finding in findings
        if finding.error_code == "OUTPUT_QUESTION_ID_MISMATCH"
    ]

    assert len(mismatches) == 1
    assert mismatches[0].question_ids == ("Q903", "Q999")


def test_contamination_detector_reports_three_distinct_patterns() -> None:
    findings = _detect()

    assert len(findings) == 3
    assert {finding.error_code for finding in findings} == {
        "CROSS_QUESTION_CONTENT_REUSE",
        "CROSS_QUESTION_EVIDENCE_ID_REUSE",
        "OUTPUT_QUESTION_ID_MISMATCH",
    }
