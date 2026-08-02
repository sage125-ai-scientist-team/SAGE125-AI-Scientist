"""Scan explicitly synthetic Mock records for cross-question contamination."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.batch import BatchRunnerError, detect_cross_question_contamination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Detect cross-question contamination in explicitly marked "
            "synthetic Mock records"
        )
    )
    parser.add_argument("--source", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = _read_marked_fixture(args.source)
        findings = detect_cross_question_contamination(payload["records"])
    except BatchRunnerError as exc:
        print(
            json.dumps(
                {"error_code": exc.error_code, "message": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    summary = {
        "finding_codes": sorted(
            {finding.error_code for finding in findings}
        ),
        "finding_count": len(findings),
        "findings": [
            finding.model_dump(mode="json") for finding in findings
        ],
        "mock": payload["mock"],
        "record_count": len(payload["records"]),
        "synthetic": payload["synthetic"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _read_marked_fixture(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "CONTAMINATION_SOURCE_INVALID",
            f"Contamination source is not valid UTF-8 JSON: {path}",
        ) from exc
    if not isinstance(payload, dict):
        raise BatchRunnerError(
            "CONTAMINATION_SOURCE_INVALID",
            "Contamination source must be a JSON object",
        )
    if payload.get("synthetic") is not True or payload.get("mock") is not True:
        raise BatchRunnerError(
            "CONTAMINATION_SOURCE_NOT_SYNTHETIC_MOCK",
            "Contamination source must declare synthetic=true and mock=true",
        )
    if not isinstance(payload.get("records"), list):
        raise BatchRunnerError(
            "CONTAMINATION_SOURCE_INVALID",
            "Contamination source must contain a records list",
        )
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
