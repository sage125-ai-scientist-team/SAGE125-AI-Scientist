"""T08 对外交付 DTO。

这些模型是上游公开契约的稳定 projection，不拥有 Reviewer、质量门、
真实执行或多模态判定。上游契约尚未可用的接口必须返回 unavailable。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class JobLinks(BaseModel):
    self: str
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
    upstream_run_id: str | None = None
    error: JobError | None = None
    links: JobLinks


class JobListResponse(BaseModel):
    items: list[JobStatusResponse]
    count: int


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


class IssueProjection(BaseModel):
    issue_id: str
    severity: str
    summary: str
    closure_status: str
    required_revision: str | None = None


class Version(BaseModel):
    version_id: str
    ordinal: int
    created_at: datetime | None = None
    parent_version_id: str | None = None
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
