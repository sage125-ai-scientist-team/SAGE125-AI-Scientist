"""Audit an explicitly synthetic Wave B leakage fixture without providers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.batch.errors import BatchRunnerError
from app.batch.leakage import (
    LeakageRecord,
    detect_leakage,
    evaluate_completion_gate,
)


WAVE_A_FINDING_CODES = frozenset(
    {
        "CROSS_QUESTION_CONTENT_REUSE",
        "CROSS_QUESTION_EVIDENCE_ID_REUSE",
        "OUTPUT_QUESTION_ID_MISMATCH",
    }
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a marked-synthetic Wave B leakage fixture",
    )
    parser.add_argument("--source", type=Path, required=True)
    return parser


def _load_source(path: Path) -> tuple[dict[str, Any], tuple[LeakageRecord, ...]]:
    if not path.is_file():
        raise BatchRunnerError(
            "LEAKAGE_SOURCE_NOT_FOUND",
            f"Leakage source does not exist: {path}",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "LEAKAGE_SOURCE_INVALID",
            f"Leakage source is not valid UTF-8 JSON: {path}",
        ) from exc
    if not isinstance(payload, dict):
        raise BatchRunnerError(
            "LEAKAGE_SOURCE_INVALID",
            "Leakage source must be a JSON object",
        )
    required_markers = {
        "synthetic": True,
        "mock": True,
        "formal_run": False,
        "actual_execution": False,
    }
    mismatches = [
        name
        for name, expected in required_markers.items()
        if payload.get(name) is not expected
    ]
    if mismatches:
        raise BatchRunnerError(
            "LEAKAGE_SOURCE_PROVENANCE_INVALID",
            f"Leakage source marker mismatch: {mismatches}",
        )
    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        raise BatchRunnerError(
            "LEAKAGE_SOURCE_INVALID",
            "Leakage source records must be a list",
        )
    return payload, tuple(
        LeakageRecord.from_mapping(record) for record in raw_records
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload, records = _load_source(args.source)
        result = detect_leakage(records)
        decision = evaluate_completion_gate(result)
    except (BatchRunnerError, TypeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "error_code": getattr(
                        exc,
                        "error_code",
                        "LEAKAGE_AUDIT_FAILED",
                    ),
                    "message": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1

    finding_codes = [finding.finding_code for finding in result.findings]
    summary = {
        "actual_execution": payload["actual_execution"],
        "actual_results": sum(
            record.result_kind == "actual" for record in records
        ),
        "blocking_findings": len(decision.blocking_findings),
        "finding_codes": finding_codes,
        "finding_count": result.finding_count,
        "findings": [finding.model_dump(mode="json") for finding in result.findings],
        "formal_run": payload["formal_run"],
        "mock": payload["mock"],
        "pandemic_reuse_detected": any(
            finding.finding_code == "CROSS_QUESTION_CONTENT_REUSE"
            and finding.question_ids == ("Q901", "Q902")
            for finding in result.findings
        ),
        "record_count": len(records),
        "review_findings": len(decision.review_findings),
        "synthetic": payload["synthetic"],
        "wave_a_finding_count": sum(
            code in WAVE_A_FINDING_CODES for code in finding_codes
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
