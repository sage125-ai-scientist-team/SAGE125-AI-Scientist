from pathlib import Path

from app.formal125.continuous_fast import MANUAL_REVIEW_24
from app.formal125.review_rc import (
    DECISIONS,
    ORIGINAL_CANDIDATE,
    decision_hash,
    official_ids,
    pre_review_question,
    risk_sort_key,
    validate_decision,
)
from app.formal125.continuous_fast import catalog_item, load_catalog


def test_frozen_review_set_is_24() -> None:
    assert len(MANUAL_REVIEW_24) == 24
    assert MANUAL_REVIEW_24[0] == "Q001"
    assert MANUAL_REVIEW_24[-1] == "Q118"


def test_pre_review_does_not_mark_manual_reviewed() -> None:
    repo = Path(__file__).resolve().parents[2]
    catalog = load_catalog(repo)
    item = pre_review_question(ORIGINAL_CANDIDATE, catalog_item(catalog, "Q095"))
    assert item["manual_reviewed"] is False
    assert item["status"] == "partial"
    assert item["suggested_decision"] == "ACCEPT_GENUINE_PARTIAL"


def test_risk_sort_blocked_then_partial_then_succeeded() -> None:
    rows = [
        {"question_id": "Q003", "status": "succeeded", "risk": "RISK_LOW"},
        {"question_id": "Q012", "status": "blocked", "risk": "RISK_HIGH"},
        {"question_id": "Q002", "status": "partial", "risk": "RISK_MEDIUM"},
        {"question_id": "Q118", "status": "blocked", "risk": "RISK_HIGH"},
    ]
    ordered = [item["question_id"] for item in sorted(rows, key=risk_sort_key)]
    assert ordered == ["Q012", "Q118", "Q002", "Q003"]


def test_decision_requires_reason_for_remediation() -> None:
    payload = {
        "question_id": "Q012",
        "reviewer_role": "captain",
        "reviewer_account": "liuyanbo12",
        "decision": "REQUEST_REMEDIATION",
        "reason": "",
        "reviewed": True,
    }
    payload["decision_hash"] = decision_hash(payload)
    try:
        validate_decision(payload, require_reason=True)
        raise AssertionError("expected reason requirement")
    except ValueError:
        pass


def test_official_ids_are_q001_q125() -> None:
    assert official_ids() == [f"Q{i:03d}" for i in range(1, 126)]
    assert set(DECISIONS) == {
        "ACCEPT_SUCCEEDED",
        "ACCEPT_GENUINE_PARTIAL",
        "ACCEPT_GENUINE_BLOCKED",
        "REQUEST_REMEDIATION",
        "SYSTEMIC_REJECT",
    }


def test_html_has_no_approve_all() -> None:
    text = (Path(__file__).resolve().parents[2] / "scripts/batch_125/run_review_rc.py").read_text(encoding="utf-8")
    assert "自动通过全部" not in text
    assert "approve all" not in text.lower()
    assert "ACCEPT_SUCCEEDED" in text
    assert "SYSTEMIC_REJECT" in text
