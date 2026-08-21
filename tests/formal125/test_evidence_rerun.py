"""Offline tests for attempt-2 evidence rerun gates. No provider calls."""

from __future__ import annotations

import json
from pathlib import Path

from app.formal125.evidence_rerun import evaluate_attempt2_gates


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_attempt2_gate_rejects_unknown_and_booklet(tmp_path: Path) -> None:
    question_dir = tmp_path / "Q028"
    question_dir.mkdir()
    allowed = ["EV-Q028-aaaaaaaaaaaaaaaaaaaaaaaa"]
    _write(
        question_dir / "evidence_bundle.json",
        {"allowed_evidence_ids": allowed, "bundle_hash": "a" * 64},
    )
    _write(
        question_dir / "evidence_cards.json",
        [
            {
                "id": allowed[0],
                "source_type": "arxiv",
                "title": "arXiv:1",
                "quoted_text": "A verified quote about cancer mutations.",
                "reliability_note": "eligibility_status=FULLTEXT_VERIFIED; locator=page:1",
            }
        ],
    )
    _write(
        question_dir / "result.json",
        {
            "generated_hypotheses": [
                {"supporting_evidence_ids": ["Q028_booklet", allowed[0]]}
            ]
        },
    )
    report = evaluate_attempt2_gates("Q028", question_dir)
    assert report["unknown_evidence_id_count"] >= 1
    assert report["blocking"] is True


def test_attempt2_gate_accepts_allowed_fulltext(tmp_path: Path) -> None:
    question_dir = tmp_path / "Q001"
    question_dir.mkdir()
    allowed = ["EV-Q001-bbbbbbbbbbbbbbbbbbbbbbbb"]
    _write(
        question_dir / "evidence_bundle.json",
        {"allowed_evidence_ids": allowed, "bundle_hash": "b" * 64},
    )
    _write(
        question_dir / "evidence_cards.json",
        [
            {
                "id": allowed[0],
                "source_type": "arxiv",
                "title": "arXiv:1",
                "quoted_text": "Prime numbers are used in cryptography.",
                "reliability_note": "eligibility_status=FULLTEXT_VERIFIED; locator=page:2",
            }
        ],
    )
    _write(
        question_dir / "result.json",
        {"generated_hypotheses": [{"supporting_evidence_ids": allowed}]},
    )
    report = evaluate_attempt2_gates("Q001", question_dir)
    assert report["unknown_evidence_id_count"] == 0
    assert report["booklet_evidence_count"] == 0
    assert report["blocking"] is False
