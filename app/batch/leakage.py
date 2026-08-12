"""Auditable Wave B leakage findings around the frozen Wave A detector."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.batch.contamination import detect_cross_question_contamination
from app.batch.errors import BatchRunnerError
from app.batch.fingerprint import (
    DEFAULT_TEMPLATE_PHRASES,
    OutputFingerprint,
    build_output_fingerprint,
    build_text_sha256,
    evaluate_cross_question_similarity,
    normalize_scientific_text,
)


FindingCode = Literal[
    "CROSS_QUESTION_CONTENT_REUSE",
    "CROSS_QUESTION_EVIDENCE_ID_REUSE",
    "OUTPUT_QUESTION_ID_MISMATCH",
    "KEYWORD_LEAKAGE",
    "CACHE_NAMESPACE_COLLISION",
    "MEMORY_NAMESPACE_COLLISION",
    "PREVIOUS_RESULT_REUSE",
    "PROMPT_CONTEXT_REUSE",
    "HIGH_CROSS_QUESTION_SIMILARITY",
]
Severity = Literal["review", "warning", "high", "critical"]
SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class LeakageRecord:
    """Adapter for one question-scoped output and isolation snapshot."""

    question_id: str
    source_hash: str
    input_hash: str
    output_question_id: str
    title: str = ""
    abstract: str = ""
    hypothesis: str = ""
    evidence_ids: tuple[str, ...] = ()
    owned_keywords: tuple[str, ...] = ()
    cache_namespace: str = ""
    memory_namespace: str = ""
    prompt_namespace: str = ""
    prompt_context: str = ""
    previous_result_question_id: str | None = None
    dry_run: bool = False
    result_kind: str = "planned"

    def __post_init__(self) -> None:
        _require_text(self.question_id, "question_id")
        _require_text(self.output_question_id, "output_question_id")
        _require_sha256(self.source_hash, "source_hash")
        _require_sha256(self.input_hash, "input_hash")
        for field_name in ("title", "abstract", "hypothesis", "prompt_context"):
            if not isinstance(getattr(self, field_name), str):
                raise TypeError(f"{field_name} must be a string")
        for field_name in ("evidence_ids", "owned_keywords"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise TypeError(
                    f"{field_name} must be a tuple of non-empty strings"
                )
        for field_name in (
            "cache_namespace",
            "memory_namespace",
            "prompt_namespace",
            "result_kind",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.previous_result_question_id is not None:
            _require_text(
                self.previous_result_question_id,
                "previous_result_question_id",
            )
        if not isinstance(self.dry_run, bool):
            raise TypeError("dry_run must be boolean")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LeakageRecord":
        if not isinstance(value, Mapping):
            raise TypeError("leakage record must be a mapping")
        output = value.get("output")
        isolation = value.get("isolation")
        if not isinstance(output, Mapping) or not isinstance(isolation, Mapping):
            raise BatchRunnerError(
                "LEAKAGE_RECORD_INVALID",
                "record output and isolation must be objects",
            )
        return cls(
            question_id=value.get("question_id", ""),
            source_hash=value.get("source_hash", ""),
            input_hash=value.get("input_hash", ""),
            output_question_id=output.get("question_id", ""),
            title=output.get("title", ""),
            abstract=output.get("abstract", ""),
            hypothesis=output.get("hypothesis", ""),
            evidence_ids=tuple(output.get("evidence_ids", ())),
            owned_keywords=tuple(value.get("owned_keywords", ())),
            cache_namespace=isolation.get("cache_namespace", ""),
            memory_namespace=isolation.get("memory_namespace", ""),
            prompt_namespace=isolation.get("prompt_namespace", ""),
            prompt_context=value.get("prompt_context", ""),
            previous_result_question_id=value.get(
                "previous_result_question_id"
            ),
            dry_run=value.get("dry_run", False),
            result_kind=value.get("result_kind", "planned"),
        )


class LeakageFinding(BaseModel):
    """Machine-readable signal; similarity alone is not contamination proof."""

    model_config = ConfigDict(frozen=True)

    finding_code: FindingCode
    severity: Severity
    question_ids: tuple[str, ...] = Field(min_length=2)
    field: str = Field(min_length=1)
    observed_value: str = Field(min_length=1)
    evidence: dict[str, Any]
    similarity_score: float | None
    threshold: float | None
    blocks_completion: bool
    message: str = Field(min_length=1)


class LeakageScanResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    findings: tuple[LeakageFinding, ...]

    @computed_field
    @property
    def finding_count(self) -> int:
        return len(self.findings)


class CompletionGateDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    blocking_findings: tuple[LeakageFinding, ...]
    review_findings: tuple[LeakageFinding, ...]


def detect_leakage(
    records: Sequence[LeakageRecord],
    *,
    similarity_threshold: float = 0.90,
    template_phrases: Sequence[str] = DEFAULT_TEMPLATE_PHRASES,
) -> LeakageScanResult:
    """Return deterministic Wave A-compatible and Wave B findings."""

    normalized_records = tuple(records)
    if not all(isinstance(record, LeakageRecord) for record in normalized_records):
        raise TypeError("records must contain LeakageRecord values")
    validate_dry_run_no_actual(normalized_records)
    fingerprints = {
        index: build_output_fingerprint(
            title=record.title,
            abstract=record.abstract,
            hypothesis=record.hypothesis,
        )
        for index, record in enumerate(normalized_records)
    }
    findings: list[LeakageFinding] = []
    findings.extend(_wave_a_findings(normalized_records))
    findings.extend(_namespace_findings(normalized_records))
    findings.extend(_previous_result_findings(normalized_records))
    findings.extend(_prompt_context_findings(normalized_records))
    findings.extend(_keyword_findings(normalized_records, template_phrases))
    findings.extend(
        _similarity_findings(
            normalized_records,
            fingerprints,
            similarity_threshold,
            template_phrases,
        )
    )
    findings.sort(
        key=lambda finding: (
            finding.finding_code,
            finding.question_ids,
            finding.field,
            finding.observed_value,
        )
    )
    return LeakageScanResult(findings=tuple(findings))


def evaluate_completion_gate(result: LeakageScanResult) -> CompletionGateDecision:
    """Separate hard blockers from non-blocking similarity review."""

    if not isinstance(result, LeakageScanResult):
        raise TypeError("result must be a LeakageScanResult")
    blocking = tuple(
        finding for finding in result.findings if finding.blocks_completion
    )
    review = tuple(
        finding
        for finding in result.findings
        if finding.finding_code == "HIGH_CROSS_QUESTION_SIMILARITY"
    )
    return CompletionGateDecision(
        allowed=not blocking,
        blocking_findings=blocking,
        review_findings=review,
    )


def validate_dry_run_no_actual(records: Sequence[LeakageRecord]) -> None:
    offenders = sorted(
        {
            record.question_id
            for record in records
            if record.dry_run and record.result_kind == "actual"
        }
    )
    if offenders:
        raise BatchRunnerError(
            "DRY_RUN_ACTUAL_RESULT",
            f"dry-run records cannot be actual: {', '.join(offenders)}",
        )


def _wave_a_findings(
    records: tuple[LeakageRecord, ...],
) -> list[LeakageFinding]:
    """Reuse the frozen Wave A detector for its three established signals."""

    wave_a_records = [
        {
            "question_id": record.question_id,
            "output": {
                "question_id": record.output_question_id,
                "title": record.title,
                "abstract": record.abstract,
                "evidence_ids": list(record.evidence_ids),
            },
        }
        for record in records
    ]
    adapted: list[LeakageFinding] = []
    for finding in detect_cross_question_contamination(wave_a_records):
        if finding.error_code == "CROSS_QUESTION_CONTENT_REUSE":
            adapted.append(
                LeakageFinding(
                    finding_code=finding.error_code,
                    severity="high",
                    question_ids=finding.question_ids,
                    field="title+abstract",
                    observed_value=finding.content_fingerprint or "unavailable",
                    evidence={
                        "content_fingerprint": finding.content_fingerprint
                    },
                    similarity_score=1.0,
                    threshold=1.0,
                    blocks_completion=True,
                    message=finding.message,
                )
            )
        elif finding.error_code == "CROSS_QUESTION_EVIDENCE_ID_REUSE":
            adapted.append(
                LeakageFinding(
                    finding_code=finding.error_code,
                    severity="high",
                    question_ids=finding.question_ids,
                    field="evidence_ids",
                    observed_value=finding.evidence_id or "unavailable",
                    evidence={"evidence_id": finding.evidence_id},
                    similarity_score=None,
                    threshold=None,
                    blocks_completion=True,
                    message=finding.message,
                )
            )
        else:
            adapted.append(
                LeakageFinding(
                    finding_code=finding.error_code,
                    severity="critical",
                    question_ids=finding.question_ids,
                    field="output.question_id",
                    observed_value=finding.question_ids[-1],
                    evidence={
                        "expected_question_id": finding.question_ids[0]
                    },
                    similarity_score=None,
                    threshold=None,
                    blocks_completion=True,
                    message=finding.message,
                )
            )
    return adapted


def _namespace_findings(
    records: tuple[LeakageRecord, ...],
) -> list[LeakageFinding]:
    findings: list[LeakageFinding] = []
    specifications = (
        ("cache_namespace", "CACHE_NAMESPACE_COLLISION"),
        ("memory_namespace", "MEMORY_NAMESPACE_COLLISION"),
    )
    for field_name, finding_code in specifications:
        groups: dict[str, set[str]] = defaultdict(set)
        for record in records:
            groups[getattr(record, field_name)].add(record.question_id)
        for namespace, question_ids in sorted(groups.items()):
            if len(question_ids) < 2:
                continue
            findings.append(
                LeakageFinding(
                    finding_code=finding_code,
                    severity="critical",
                    question_ids=tuple(sorted(question_ids)),
                    field=field_name,
                    observed_value=namespace,
                    evidence={"namespace": namespace},
                    similarity_score=None,
                    threshold=None,
                    blocks_completion=True,
                    message=f"{field_name} is shared across distinct questions",
                )
            )
    return findings


def _previous_result_findings(
    records: tuple[LeakageRecord, ...],
) -> list[LeakageFinding]:
    return [
        LeakageFinding(
            finding_code="PREVIOUS_RESULT_REUSE",
            severity="critical",
            question_ids=tuple(
                sorted((record.question_id, record.previous_result_question_id))
            ),
            field="previous_result.question_id",
            observed_value=record.previous_result_question_id,
            evidence={"consumer_question_id": record.question_id},
            similarity_score=None,
            threshold=None,
            blocks_completion=True,
            message="previous_result belongs to another question",
        )
        for record in records
        if record.previous_result_question_id is not None
        and record.previous_result_question_id != record.question_id
    ]


def _prompt_context_findings(
    records: tuple[LeakageRecord, ...],
) -> list[LeakageFinding]:
    groups: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if normalize_scientific_text(record.prompt_context):
            groups[build_text_sha256(record.prompt_context)].add(
                record.question_id
            )
    return [
        LeakageFinding(
            finding_code="PROMPT_CONTEXT_REUSE",
            severity="high",
            question_ids=tuple(sorted(question_ids)),
            field="prompt_context",
            observed_value=prompt_hash,
            evidence={"prompt_context_sha256": prompt_hash},
            similarity_score=1.0,
            threshold=1.0,
            blocks_completion=True,
            message="Exact prompt context was reused across distinct questions",
        )
        for prompt_hash, question_ids in sorted(groups.items())
        if len(question_ids) > 1
    ]


def _keyword_findings(
    records: tuple[LeakageRecord, ...],
    template_phrases: Sequence[str],
) -> list[LeakageFinding]:
    templates = {normalize_scientific_text(value) for value in template_phrases}
    findings: list[LeakageFinding] = []
    for owner in records:
        for raw_keyword in owner.owned_keywords:
            keyword = normalize_scientific_text(raw_keyword)
            if not keyword or keyword in templates:
                continue
            for consumer in records:
                if consumer.question_id == owner.question_id:
                    continue
                output = normalize_scientific_text(
                    " ".join(
                        (consumer.title, consumer.abstract, consumer.hypothesis)
                    )
                )
                if f" {keyword} " not in f" {output} ":
                    continue
                findings.append(
                    LeakageFinding(
                        finding_code="KEYWORD_LEAKAGE",
                        severity="high",
                        question_ids=tuple(
                            sorted((owner.question_id, consumer.question_id))
                        ),
                        field="title+abstract+hypothesis",
                        observed_value=keyword,
                        evidence={
                            "keyword_owner": owner.question_id,
                            "keyword_consumer": consumer.question_id,
                        },
                        similarity_score=None,
                        threshold=None,
                        blocks_completion=True,
                        message="Question-owned keyword appeared in another output",
                    )
                )
    return findings


def _similarity_findings(
    records: tuple[LeakageRecord, ...],
    fingerprints: dict[int, OutputFingerprint],
    threshold: float,
    template_phrases: Sequence[str],
) -> list[LeakageFinding]:
    findings: list[LeakageFinding] = []
    for left_index, right_index in combinations(range(len(records)), 2):
        left = records[left_index]
        right = records[right_index]
        evaluation = evaluate_cross_question_similarity(
            left_question_id=left.question_id,
            left=fingerprints[left_index],
            right_question_id=right.question_id,
            right=fingerprints[right_index],
            threshold=threshold,
            template_phrases=template_phrases,
        )
        if not evaluation.compared or not evaluation.requires_review:
            continue
        findings.append(
            LeakageFinding(
                finding_code="HIGH_CROSS_QUESTION_SIMILARITY",
                severity="review",
                question_ids=tuple(
                    sorted((left.question_id, right.question_id))
                ),
                field="title+abstract+hypothesis",
                observed_value=f"{evaluation.combined_score:.6f}",
                evidence={
                    "title_score": evaluation.title.score,
                    "abstract_score": evaluation.abstract.score,
                    "hypothesis_score": evaluation.hypothesis.score,
                    "calculation": (
                        "normalized weighted mean: title=.25, "
                        "abstract=.50, hypothesis=.25; empty fields excluded"
                    ),
                },
                similarity_score=evaluation.combined_score,
                threshold=evaluation.threshold,
                blocks_completion=False,
                message="High cross-question similarity requires human review",
            )
        )
    return findings


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_sha256(value: Any, field_name: str) -> str:
    normalized = _require_text(value, field_name)
    if not SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase SHA-256")
    return normalized
