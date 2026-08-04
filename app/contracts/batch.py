"""Stable JSON contracts for T07 batch planning and recovery."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Final, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


BATCH_SCHEMA_VERSION: Final[str] = "t07.batch.v1"
CHECKPOINT_SCHEMA_VERSION: Final[str] = "t07.checkpoint.v1"
STANDARD_OUTPUT_FIELDS: Final[tuple[str, ...]] = (
    "Problem",
    "Rationale",
    "Technical Details",
    "Datasets Source",
    "Datasets Target",
    "Title",
    "Abstract",
    "Methods",
    "Experiments",
    "Results",
    "References",
)
REQUIRED_ARTIFACTS: Final[tuple[str, ...]] = (
    "report.pdf",
    "report.md",
    "result.json",
    "evidence_cards.json",
    "agent_trace.json",
)
SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_non_empty(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be empty")
    return normalized


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


class JobStatus(str, Enum):
    QUEUED = "queued"
    PREFLIGHT = "preflight"
    RUNNING = "running"
    CHECKPOINTED = "checkpointed"
    RETRY_WAIT = "retry_wait"
    GATES_PENDING = "gates_pending"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"


class ResultKind(str, Enum):
    PLANNED = "planned"
    EXPECTED = "expected"
    MOCK = "mock"
    ACTUAL = "actual"


class SourceKind(str, Enum):
    PRODUCTION = "production"
    SYNTHETIC = "synthetic"


class StaleCheckpointAction(str, Enum):
    REJECT = "reject"


class FailureRecord(BaseModel):
    error_code: str
    message: str
    retryable: bool
    attempt: int = Field(ge=1)
    occurred_at: datetime = Field(default_factory=_utc_now)

    _normalize_error_code = field_validator("error_code")(_require_non_empty)
    _normalize_message = field_validator("message")(_require_non_empty)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class ModelRoute(BaseModel):
    route_id: str = "dry-run"
    provider: str = "none"
    model: str = "none"
    model_version: str = "unassigned"
    prompt_version: str = "unassigned"
    prompt_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)

    _normalize_route_id = field_validator("route_id")(_require_non_empty)
    _normalize_provider = field_validator("provider")(_require_non_empty)
    _normalize_model = field_validator("model")(_require_non_empty)
    _normalize_model_version = field_validator("model_version")(
        _require_non_empty
    )
    _normalize_prompt_version = field_validator("prompt_version")(
        _require_non_empty
    )


class BatchBudget(BaseModel):
    token_limit: int = Field(default=0, ge=0)
    cost_limit_usd: Decimal = Field(default=Decimal("0"), ge=0)
    tokens_used: int = Field(default=0, ge=0)
    cost_used_usd: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def enforce_limits(self) -> "BatchBudget":
        if self.tokens_used > self.token_limit:
            raise ValueError("token budget exceeded")
        if self.cost_used_usd > self.cost_limit_usd:
            raise ValueError("cost budget exceeded")
        return self


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)


class ResumePolicy(BaseModel):
    enabled: bool = True
    require_source_hash_match: bool = True
    require_input_hash_match: bool = True
    require_model_route_match: bool = True
    require_model_version_match: bool = True
    require_prompt_version_match: bool = True
    require_prompt_hash_match: bool = True
    require_schema_version_match: bool = True
    stale_checkpoint_action: StaleCheckpointAction = (
        StaleCheckpointAction.REJECT
    )


class OutputContract(BaseModel):
    required_fields: tuple[str, ...] = STANDARD_OUTPUT_FIELDS
    required_artifacts: tuple[str, ...] = REQUIRED_ARTIFACTS
    fields: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)

    @field_validator("required_fields")
    @classmethod
    def retain_standard_fields(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        missing = [name for name in STANDARD_OUTPUT_FIELDS if name not in value]
        if missing:
            raise ValueError(
                f"required_fields cannot omit standard fields: {missing}"
            )
        if len(value) != len(set(value)):
            raise ValueError("required_fields contains duplicates")
        return value

    @field_validator("required_artifacts")
    @classmethod
    def retain_required_artifacts(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        missing = [name for name in REQUIRED_ARTIFACTS if name not in value]
        if missing:
            raise ValueError(
                f"required_artifacts cannot omit required files: {missing}"
            )
        if len(value) != len(set(value)):
            raise ValueError("required_artifacts contains duplicates")
        return value

    @field_validator("artifacts")
    @classmethod
    def require_non_empty_artifact_paths(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for name, path in value.items():
            normalized[_require_non_empty(name)] = _require_non_empty(path)
        return normalized

    def missing_fields(self) -> list[str]:
        return [
            name
            for name in self.required_fields
            if name not in self.fields or _is_missing(self.fields[name])
        ]

    def missing_artifacts(self) -> list[str]:
        return [
            name
            for name in self.required_artifacts
            if name not in self.artifacts or _is_missing(self.artifacts[name])
        ]


class BatchJob(BaseModel):
    schema_version: Literal["t07.batch.v1"] = BATCH_SCHEMA_VERSION
    batch_id: str
    question_id: str
    source_hash: str = Field(pattern=SHA256_PATTERN)
    input_hash: str = Field(pattern=SHA256_PATTERN)
    workspace: str
    context_id: str
    cache_namespace: str
    status: JobStatus = JobStatus.QUEUED
    result_kind: ResultKind = ResultKind.PLANNED
    mock: bool = False
    attempt: int = Field(default=0, ge=0)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    budget: BatchBudget = Field(default_factory=BatchBudget)
    model_route: ModelRoute = Field(default_factory=ModelRoute)
    output_contract: OutputContract = Field(default_factory=OutputContract)
    failures: list[FailureRecord] = Field(default_factory=list)

    _normalize_schema_version = field_validator("schema_version")(
        _require_non_empty
    )
    _normalize_batch_id = field_validator("batch_id")(_require_non_empty)
    _normalize_question_id = field_validator("question_id")(_require_non_empty)
    _normalize_workspace = field_validator("workspace")(_require_non_empty)
    _normalize_context_id = field_validator("context_id")(_require_non_empty)
    _normalize_cache_namespace = field_validator("cache_namespace")(
        _require_non_empty
    )

    @model_validator(mode="after")
    def enforce_job_invariants(self) -> "BatchJob":
        if self.attempt > self.retry_policy.max_attempts:
            raise ValueError("attempt exceeds retry hard limit")
        if any(failure.attempt > self.attempt for failure in self.failures):
            raise ValueError("failure attempt exceeds job attempt")
        if self.mock and self.result_kind is not ResultKind.MOCK:
            raise ValueError("mock=true requires result_kind=mock")
        if self.result_kind is ResultKind.MOCK and not self.mock:
            raise ValueError("result_kind=mock requires mock=true")
        if self.result_kind is ResultKind.ACTUAL and self.mock:
            raise ValueError("actual result cannot be Mock")

        if self.status is JobStatus.COMPLETED:
            if self.mock:
                raise ValueError("Mock job cannot be completed")
            if self.result_kind is not ResultKind.ACTUAL:
                raise ValueError("completed job requires result_kind=actual")

            missing_fields = self.output_contract.missing_fields()
            if missing_fields:
                raise ValueError(
                    f"missing required output fields: {missing_fields}"
                )
            missing_artifacts = self.output_contract.missing_artifacts()
            if missing_artifacts:
                raise ValueError(
                    f"missing required artifacts: {missing_artifacts}"
                )

            prefix = f"{self.batch_id}/{self.question_id}/"
            unscoped = [
                path
                for path in self.output_contract.artifacts.values()
                if not path.replace("\\", "/").startswith(prefix)
            ]
            if unscoped:
                raise ValueError(
                    "completed artifact paths must be question-scoped"
                )
            route_values = (
                self.model_route.route_id,
                self.model_route.provider,
                self.model_route.model,
                self.model_route.model_version,
                self.model_route.prompt_version,
                self.model_route.prompt_hash,
            )
            if any(
                value is None
                or value in {"dry-run", "none", "unassigned"}
                for value in route_values
            ):
                raise ValueError(
                    "completed job requires an assigned model route"
                )
        return self


class CheckpointRecord(BaseModel):
    checkpoint_version: Literal["t07.checkpoint.v1"] = (
        CHECKPOINT_SCHEMA_VERSION
    )
    batch_id: str
    question_id: str
    source_hash: str = Field(pattern=SHA256_PATTERN)
    input_hash: str = Field(pattern=SHA256_PATTERN)
    schema_version: Literal["t07.batch.v1"]
    route_id: str
    provider: str
    model: str
    model_version: str
    prompt_version: str
    prompt_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    status: JobStatus
    attempt: int = Field(ge=0)
    job: BatchJob
    updated_at: datetime = Field(default_factory=_utc_now)

    _normalize_checkpoint_version = field_validator("checkpoint_version")(
        _require_non_empty
    )

    @field_validator("updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def bind_embedded_job(self) -> "CheckpointRecord":
        expected = {
            "batch_id": self.job.batch_id,
            "question_id": self.job.question_id,
            "source_hash": self.job.source_hash,
            "input_hash": self.job.input_hash,
            "schema_version": self.job.schema_version,
            "route_id": self.job.model_route.route_id,
            "provider": self.job.model_route.provider,
            "model": self.job.model_route.model,
            "model_version": self.job.model_route.model_version,
            "prompt_version": self.job.model_route.prompt_version,
            "prompt_hash": self.job.model_route.prompt_hash,
            "status": self.job.status,
            "attempt": self.job.attempt,
        }
        mismatches = [
            name for name, value in expected.items() if getattr(self, name) != value
        ]
        if mismatches:
            raise ValueError(
                f"checkpoint fields do not match embedded job: {mismatches}"
            )
        return self

    @classmethod
    def from_job(cls, job: BatchJob) -> "CheckpointRecord":
        return cls(
            batch_id=job.batch_id,
            question_id=job.question_id,
            source_hash=job.source_hash,
            input_hash=job.input_hash,
            schema_version=job.schema_version,
            route_id=job.model_route.route_id,
            provider=job.model_route.provider,
            model=job.model_route.model,
            model_version=job.model_route.model_version,
            prompt_version=job.model_route.prompt_version,
            prompt_hash=job.model_route.prompt_hash,
            status=job.status,
            attempt=job.attempt,
            job=job,
        )


class BatchManifest(BaseModel):
    schema_version: Literal["t07.batch.v1"] = BATCH_SCHEMA_VERSION
    batch_id: str
    source_kind: SourceKind
    source_path: str
    source_hash: str = Field(pattern=SHA256_PATTERN)
    dry_run: bool
    model_route: ModelRoute = Field(default_factory=ModelRoute)
    budget: BatchBudget = Field(default_factory=BatchBudget)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    resume_policy: ResumePolicy = Field(default_factory=ResumePolicy)
    jobs: list[BatchJob]
    total: int = Field(ge=0)
    status_counts: dict[str, int]
    created_at: datetime = Field(default_factory=_utc_now)

    _normalize_schema_version = field_validator("schema_version")(
        _require_non_empty
    )
    _normalize_batch_id = field_validator("batch_id")(_require_non_empty)
    _normalize_source_path = field_validator("source_path")(_require_non_empty)

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value

    @model_validator(mode="before")
    @classmethod
    def derive_and_validate_summary(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            return payload

        expected_total = len(jobs)
        expected_counts = _status_counts_from_jobs(jobs)
        if "total" in payload and payload["total"] != expected_total:
            raise ValueError("manifest total does not match jobs")
        if (
            "status_counts" in payload
            and payload["status_counts"] != expected_counts
        ):
            raise ValueError("manifest status_counts do not match jobs")
        payload["total"] = expected_total
        payload["status_counts"] = expected_counts
        return payload

    @model_validator(mode="after")
    def enforce_manifest_invariants(self) -> "BatchManifest":
        uniqueness_fields = (
            "question_id",
            "workspace",
            "context_id",
            "cache_namespace",
        )
        for field_name in uniqueness_fields:
            values = [getattr(job, field_name) for job in self.jobs]
            if len(values) != len(set(values)):
                label = (
                    "duplicate question_id"
                    if field_name == "question_id"
                    else f"duplicate {field_name}"
                )
                raise ValueError(label)

        for job in self.jobs:
            if job.batch_id != self.batch_id:
                raise ValueError("job batch_id does not match manifest")
            if job.source_hash != self.source_hash:
                raise ValueError("job source_hash does not match manifest")
            if job.schema_version != self.schema_version:
                raise ValueError("job schema_version does not match manifest")
            if job.retry_policy != self.retry_policy:
                raise ValueError("job retry_policy does not match manifest")
            if job.model_route != self.model_route:
                raise ValueError("job model_route does not match manifest")
            if (
                self.source_kind is SourceKind.SYNTHETIC
                and job.status is JobStatus.COMPLETED
                and job.result_kind is ResultKind.ACTUAL
            ):
                raise ValueError(
                    "synthetic manifest cannot contain completed actual jobs"
                )
        return self


def _status_counts_from_jobs(jobs: list[Any]) -> dict[str, int]:
    counts = {status.value: 0 for status in JobStatus}
    for job in jobs:
        raw_status = (
            job.status
            if isinstance(job, BatchJob)
            else job.get("status", JobStatus.QUEUED)
        )
        status = (
            raw_status
            if isinstance(raw_status, JobStatus)
            else JobStatus(str(raw_status))
        )
        counts[status.value] += 1
    return {
        status.value: counts[status.value]
        for status in JobStatus
        if counts[status.value]
    }
