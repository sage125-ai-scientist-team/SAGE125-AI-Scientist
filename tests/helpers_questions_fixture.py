# -*- coding: utf-8 -*-
"""Minimal isolated questions_125.json fixtures for pipeline unit tests."""

from __future__ import annotations

import json
from pathlib import Path


def write_minimal_questions_fixture(target: Path, *, question_id: str = "Q001") -> Path:
    """
    Write a tiny questions catalog JSON for offline tests.

    Parameters:
        target: Destination file path (usually under pytest tmp_path).
        question_id: Id of the single sample question record.

    Returns:
        The same target path after writing UTF-8 JSON.
    """
    payload = [
        {
            "id": question_id,
            "domain": "synthetic-domain",
            "question": "Synthetic offline question for unit tests?",
        }
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
