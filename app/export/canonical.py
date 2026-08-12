"""Single canonical report projection used by JSON, Markdown, and PDF."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


Availability = Literal["available", "partial", "unavailable"]
ReportTruthStatus = Literal["planned", "expected", "mock", "actual", "unavailable"]


class _ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportEvidence(_ReportModel):
    evidence_id: str
    title: str
    quoted_text: str
    locator: str
    doi: str | None = None
    url: str | None = None
    verification_status: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ReportIssue(_ReportModel):
    issue_id: str
    severity: str
    status: str
    summary: str
    resolution_note: str | None = None


class ReportFeedback(_ReportModel):
    feedback_id: str
    status: str
    target_version_id: str
    decision_reason: str | None = None


class ReportGate(_ReportModel):
    gate_id: str
    passed: bool
    severity: str
    findings: list[dict[str, Any]] = Field(default_factory=list)


class ReportExecution(_ReportModel):
    availability: Availability
    status: str
    actual_execution: bool | None
    execution_id: str | None = None
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReportMultimodal(_ReportModel):
    artifact_id: str
    modality: str
    source: str
    page: int | None = None
    bbox: list[float] | None = None
    units: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    validation_status: str


class CanonicalReport(_ReportModel):
    schema_version: Literal["t08.report.v1"] = "t08.report.v1"
    generated_at: datetime
    job_id: str
    question_id: str
    run_id: str
    version_id: str | None = None
    title: str
    question: str
    domain: str
    truth_status: ReportTruthStatus
    hypotheses: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    evidence: list[ReportEvidence] = Field(default_factory=list)
    reviewer_issues: list[ReportIssue] = Field(default_factory=list)
    feedback: list[ReportFeedback] = Field(default_factory=list)
    gates: list[ReportGate] = Field(default_factory=list)
    execution: ReportExecution
    multimodal: list[ReportMultimodal] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    content_sha256: str = ""

    @model_validator(mode="after")
    def bind_content_hash(self) -> "CanonicalReport":
        payload = self.model_dump(mode="json", exclude={"content_sha256"})
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected = hashlib.sha256(encoded).hexdigest()
        if self.content_sha256 and self.content_sha256 != expected:
            raise ValueError("content_sha256 does not match canonical report")
        object.__setattr__(self, "content_sha256", expected)
        return self


class CanonicalReportSource(Protocol):
    def get_report(
        self,
        *,
        job_id: str,
        question_id: str,
        run_id: str,
    ) -> CanonicalReport: ...


class CanonicalReportUnavailable(RuntimeError):
    pass


class UnavailableCanonicalReportSource:
    def get_report(
        self,
        *,
        job_id: str,
        question_id: str,
        run_id: str,
    ) -> CanonicalReport:
        del job_id, question_id, run_id
        raise CanonicalReportUnavailable("canonical report source is unavailable")


class StaticCanonicalReportSource:
    """Validated owner-fixture adapter used for API contract and E2E tests."""

    def __init__(self, reports_by_run: Mapping[str, CanonicalReport]) -> None:
        self._reports = {
            key: value.model_copy(deep=True) for key, value in reports_by_run.items()
        }

    def get_report(
        self,
        *,
        job_id: str,
        question_id: str,
        run_id: str,
    ) -> CanonicalReport:
        try:
            template = self._reports[run_id]
        except KeyError:
            raise CanonicalReportUnavailable(run_id) from None
        payload = template.model_dump(mode="json", exclude={"content_sha256"})
        payload.update(
            {"job_id": job_id, "question_id": question_id, "run_id": run_id}
        )
        return CanonicalReport.model_validate(payload)
