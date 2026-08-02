"""Executable detection of cross-question contamination patterns."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.batch.errors import BatchRunnerError


FindingCode = Literal[
    "CROSS_QUESTION_CONTENT_REUSE",
    "CROSS_QUESTION_EVIDENCE_ID_REUSE",
    "OUTPUT_QUESTION_ID_MISMATCH",
]


class ContaminationFinding(BaseModel):
    error_code: FindingCode
    question_ids: tuple[str, ...] = Field(min_length=2)
    message: str = Field(min_length=1)
    evidence_id: str | None = None
    content_fingerprint: str | None = None


def detect_cross_question_contamination(
    records: Sequence[dict[str, Any]],
) -> list[ContaminationFinding]:
    """Return deterministic findings derived from supplied output records."""

    content_groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    evidence_groups: dict[str, set[str]] = defaultdict(set)
    identity_mismatches: list[tuple[str, str]] = []

    for index, record in enumerate(records):
        question_id = _required_text(
            record.get("question_id"),
            f"records[{index}].question_id",
        )
        output = record.get("output")
        if not isinstance(output, dict):
            raise BatchRunnerError(
                "CONTAMINATION_RECORD_INVALID",
                f"records[{index}].output must be an object",
            )

        output_question_id = _required_text(
            output.get("question_id"),
            f"records[{index}].output.question_id",
        )
        if output_question_id != question_id:
            identity_mismatches.append((question_id, output_question_id))

        normalized_content = _normalize_content(
            output.get("title"),
            output.get("abstract"),
        )
        if normalized_content:
            fingerprint = hashlib.sha256(
                normalized_content.encode("utf-8")
            ).hexdigest()
            content_groups[fingerprint].append(
                (question_id, normalized_content)
            )

        evidence_ids = output.get("evidence_ids", [])
        if not isinstance(evidence_ids, list):
            raise BatchRunnerError(
                "CONTAMINATION_RECORD_INVALID",
                f"records[{index}].output.evidence_ids must be a list",
            )
        for evidence_id in evidence_ids:
            normalized_evidence_id = _required_text(
                evidence_id,
                f"records[{index}].output.evidence_ids",
            )
            evidence_groups[normalized_evidence_id].add(question_id)

    findings: list[ContaminationFinding] = []
    for fingerprint, grouped_records in sorted(content_groups.items()):
        question_ids = tuple(
            sorted({question_id for question_id, _ in grouped_records})
        )
        if len(question_ids) < 2:
            continue
        sample = grouped_records[0][1]
        findings.append(
            ContaminationFinding(
                error_code="CROSS_QUESTION_CONTENT_REUSE",
                question_ids=question_ids,
                content_fingerprint=fingerprint,
                message=(
                    "Identical normalized output content was reused across "
                    f"{', '.join(question_ids)}: {sample[:120]}"
                ),
            )
        )

    for evidence_id, grouped_question_ids in sorted(evidence_groups.items()):
        question_ids = tuple(sorted(grouped_question_ids))
        if len(question_ids) < 2:
            continue
        findings.append(
            ContaminationFinding(
                error_code="CROSS_QUESTION_EVIDENCE_ID_REUSE",
                question_ids=question_ids,
                evidence_id=evidence_id,
                message=(
                    f"Evidence ID {evidence_id} was reused across "
                    f"{', '.join(question_ids)}"
                ),
            )
        )

    for question_id, output_question_id in sorted(identity_mismatches):
        findings.append(
            ContaminationFinding(
                error_code="OUTPUT_QUESTION_ID_MISMATCH",
                question_ids=(question_id, output_question_id),
                message=(
                    f"Output bound to {question_id} declares "
                    f"question_id={output_question_id}"
                ),
            )
        )
    return findings


def _normalize_content(title: Any, abstract: Any) -> str:
    parts = [
        value.strip()
        for value in (title, abstract)
        if isinstance(value, str) and value.strip()
    ]
    return re.sub(r"\s+", " ", "\n".join(parts)).casefold()


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BatchRunnerError(
            "CONTAMINATION_RECORD_INVALID",
            f"{field_name} must be a non-empty string",
        )
    return value.strip()
