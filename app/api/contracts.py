"""T08 对外交付 DTO。

这些模型是上游公开契约的稳定 projection，不拥有 Reviewer、质量门、
真实执行或多模态判定。上游契约尚未可用的接口必须返回 unavailable。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FEEDBACK = "waiting_feedback"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class RunOptions(BaseModel):
    use_deep_research: bool = True
    use_open_literature: bool = True
    use_local_rag: bool = True
    reviewer_auto_revision: bool = True


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_id": "Q001",
                "mode": "mock",
                "options": {
                    "use_deep_research": True,
                    "use_open_literature": True,
                    "use_local_rag": True,
                    "reviewer_auto_revision": True,
                },
            }
        }
    )

    question_id: str = Field(min_length=1, max_length=64)
    mode: Literal["mock", "real"] = "mock"
    options: RunOptions = Field(default_factory=RunOptions)


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    retryable: bool = False


class JobError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class RetryMetadata(BaseModel):
    attempt: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    retryable: bool = False
    last_attempt_at: datetime | None = None
    next_retry_at: datetime | None = None
    backoff_seconds: int | None = Field(default=None, ge=0)


class TimeoutMetadata(BaseModel):
    timeout_seconds: int | None = Field(default=None, ge=1)
    deadline_at: datetime | None = None
    timed_out_at: datetime | None = None


class JobLinks(BaseModel):
    self: str
    evidence: str
    multimodal: str
    artifacts: str
    versions: str
    feedback: str


class JobAccepted(BaseModel):
    job_id: str
    correlation_id: str
    status: JobStatus
    created_at: datetime
    status_url: str
    reused: bool = False


class JobStatusResponse(BaseModel):
    job_id: str
    correlation_id: str
    kind: Literal["research_run", "feedback_revision", "export"] = "research_run"
    question_id: str
    mode: Literal["mock", "real"]
    status: JobStatus
    stage: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempt: int = 0
    max_attempts: int = 1
    retry: RetryMetadata
    timeout: TimeoutMetadata
    upstream_run_id: str | None = None
    error: JobError | None = None
    links: JobLinks


class JobListResponse(BaseModel):
    items: list[JobStatusResponse]
    count: int


class QuestionSummary(BaseModel):
    question_id: str
    domain: str
    question: str
    source_page: int | None = None
    source_excerpt: str | None = None
    status: str
    status_reason: str | None = None


class QuestionListResponse(BaseModel):
    items: list[QuestionSummary]
    count: int
    total: int
    availability: Literal["available", "partial", "unavailable"]


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    MISSING = "missing"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class TruthStatus(str, Enum):
    PLANNED = "planned"
    EXPECTED = "expected"
    MOCK = "mock"
    ACTUAL = "actual"
    UNAVAILABLE = "unavailable"


class Artifact(BaseModel):
    artifact_id: str
    name: str
    artifact_type: str
    media_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    status: ArtifactStatus
    truth_status: TruthStatus
    created_at: datetime | None = None
    download_url: str | None = None
    unavailable_reason: str | None = None


class ArtifactListResponse(BaseModel):
    job_id: str
    items: list[Artifact]
    availability: Literal["available", "partial", "unavailable"]


class ExportCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"formats": ["json", "markdown", "pdf"]}}
    )

    formats: list[Literal["json", "markdown", "pdf"]] = Field(
        min_length=1,
        max_length=3,
    )

    @field_validator("formats")
    @classmethod
    def _unique_formats(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("formats must not contain duplicates")
        return values


class ExportResponse(BaseModel):
    job_id: str
    items: list[Artifact]
    reused: bool


class EvidenceRelation(BaseModel):
    claim_id: str
    relation: Literal["supports", "contradicts", "context"]
    confidence: float = Field(ge=0.0, le=1.0)
    validation_status: Literal["valid", "invalid", "pending"]


class EvidenceProjection(BaseModel):
    evidence_id: str
    source_id: str
    source_type: str
    title: str
    quoted_text: str
    locator: dict[str, Any]
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    content_hash: str | None = None
    domain: str | None = None
    verification_status: str
    relations: list[EvidenceRelation] = Field(default_factory=list)


class EvidenceListResponse(BaseModel):
    job_id: str
    bundle_id: str
    items: list[EvidenceProjection]
    truncated: bool = False
    truncation_reason: str | None = None
    availability: Literal["available", "partial", "unavailable"]


class IssueProjection(BaseModel):
    issue_id: str
    severity: str
    summary: str
    closure_status: str
    required_revision: str | None = None
    category: str | None = None
    opened_in_version: int | None = None
    closed_in_version: int | None = None
    resolution_note: str | None = None


class Version(BaseModel):
    version_id: str
    ordinal: int
    created_at: datetime | None = None
    parent_version_id: str | None = None
    revision_iteration: int | None = None
    validation_status: str | None = None
    feedback_ids: list[str] = Field(default_factory=list)
    reviewer_issues: list[IssueProjection] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    stop_reason: str | None = None
    availability: Literal["available", "partial", "unavailable"] = "unavailable"


class VersionListResponse(BaseModel):
    job_id: str
    items: list[Version]
    availability: Literal["available", "partial", "unavailable"]


class VersionDiff(BaseModel):
    job_id: str
    from_version_id: str
    to_version_id: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    issue_changes: list[dict[str, Any]] = Field(default_factory=list)
    score_delta: dict[str, float] = Field(default_factory=dict)
    stop_reason: str | None = None
    availability: Literal["available", "partial", "unavailable"]


class FeedbackCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_version_id": "v1",
                "feedback": "请让假设更保守，并补充可证伪阈值。",
            }
        }
    )

    target_version_id: str = Field(min_length=1, max_length=128)
    feedback: str = Field(min_length=1, max_length=10_000)


class FeedbackReceipt(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "feedback_id": "feedback-7f4a",
                "job_id": "job-123",
                "target_version_id": "run-123:v1",
                "status": "submitted",
                "decision_reason": None,
                "resulting_version_id": None,
                "correlation_id": "judge-demo-001",
            }
        }
    )

    feedback_id: str
    job_id: str
    target_version_id: str
    status: Literal[
        "submitted",
        "processing",
        "accepted",
        "partially_accepted",
        "rejected",
        "failed",
        "unavailable",
    ]
    decision_reason: str | None = None
    resulting_version_id: str | None = None
    correlation_id: str


class MultimodalDetailProjection(BaseModel):
    """Public T06 detail projection preserving provenance and review semantics."""

    artifact_id: str
    modality: str
    source_id: str
    source_label: str
    preview_artifact_id: str
    coordinate_space: str
    page: int
    bbox: dict[str, float] | None = None
    extracted_values: dict[str, Any]
    units: list[str] = Field(default_factory=list)
    column_units: list[dict[str, Any]] = Field(default_factory=list)
    axes: list[dict[str, Any]] = Field(default_factory=list)
    legend: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    validation_status: str
    needs_human_review: bool


class MultimodalDetailListResponse(BaseModel):
    """Identity-bound T06 detail collection for one plan version."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job-123",
                "version_id": "run-123:v1",
                "items": [],
                "availability": "available",
            }
        }
    )

    job_id: str
    version_id: str
    items: list[MultimodalDetailProjection] = Field(default_factory=list)
    availability: Literal["available", "unavailable"]
