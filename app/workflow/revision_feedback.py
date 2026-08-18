"""Bounded T05/T06 feedback views for the T02 revision workflow.

The frozen execution and multimodal contracts deliberately contain more data
than an agent prompt should receive.  This module is the workflow-owned trust
boundary: it accepts validated contract instances, selects an explicit field
allowlist, applies deterministic limits, and reports every dropped/truncated
item without copying raw rows or process output.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.execution import ExecutionResult
from app.contracts.multimodal import MultimodalArtifact, to_consumer_summary


MAX_EXECUTION_METRICS = 8
MAX_EXECUTION_ARTIFACTS = 8
MAX_MULTIMODAL_ARTIFACTS = 6
MAX_UNIT_ITEMS = 8
MAX_TEXT_LENGTH = 512
MAX_SOURCE_PATH_LENGTH = 320
MAX_IDENTIFIER_LENGTH = 160
MAX_UNIT_LENGTH = 96
MAX_MEDIA_TYPE_LENGTH = 128
MAX_PROJECTION_BYTES = 32_768

_DROP_KEYS = (
    "execution_metrics",
    "execution_artifacts",
    "multimodal_artifacts",
    "multimodal_units",
    "multimodal_column_units",
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _bounded_text(value: str, limit: int) -> tuple[str, bool]:
    """Keep a traceable prefix and digest when a contract string is too long."""
    if len(value) <= limit:
        return value, False
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    suffix = f"…[sha256:{digest}]"
    return f"{value[: limit - len(suffix)]}{suffix}", True


class _FeedbackModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExecutionMetricFeedback(_FeedbackModel):
    name: str
    value: float
    unit: str
    source: Literal["observed", "expected", "default", "mock", "test"]
    artifact_id: str
    validation_status: Literal["pending", "valid", "missing", "invalid"]
    round_index: int = Field(ge=0)


class ExecutionArtifactFeedback(_FeedbackModel):
    artifact_id: str
    relative_path: str
    kind: str
    media_type: str
    required: bool
    sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    validation_status: str


class ExecutionFailureFeedback(_FeedbackModel):
    code: str
    message: str
    stage: str
    retryable: bool


class ExecutionOutputSummary(_FeedbackModel):
    stdout_bytes: int = Field(ge=0)
    stderr_bytes: int = Field(ge=0)
    stdout_truncated: bool
    stderr_truncated: bool
    warning_count: int = Field(ge=0)


class ExecutionFeedback(_FeedbackModel):
    execution_id: str
    spec_id: str
    question_id: str
    round_index: int = Field(ge=0)
    parent_execution_id: str | None = None
    mode: Literal["actual", "dry_run", "mock", "test"]
    status: Literal[
        "planned",
        "rejected",
        "running",
        "succeeded",
        "failed",
        "timed_out",
        "cancelled",
    ]
    entrypoint: str
    entrypoint_class: Literal["scientific", "test"] | None = None
    actual_execution: bool
    scientific_result_usable: bool
    runner_verified: bool
    provenance_complete: bool
    datasets_validated: bool
    artifacts_validated: bool
    metrics_validated: bool
    git_sha: str | None = None
    metrics: tuple[ExecutionMetricFeedback, ...] = ()
    artifacts: tuple[ExecutionArtifactFeedback, ...] = ()
    failure: ExecutionFailureFeedback | None = None
    output: ExecutionOutputSummary


class ColumnUnitFeedback(_FeedbackModel):
    column: str
    unit: str


class MultimodalFeedback(_FeedbackModel):
    artifact_id: str
    modality: Literal["table", "chart", "timeseries"]
    source_path: str
    source_type: Literal[
        "synthetic_fixture",
        "real_fixture",
        "pdf",
        "csv",
        "user_upload",
    ]
    page: int = Field(ge=1)
    units: tuple[str, ...] = ()
    column_units: tuple[ColumnUnitFeedback, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    validation_status: Literal["passed", "needs_review", "failed", "pending"]
    header_count: int = Field(ge=0)
    row_count: int = Field(ge=0)


class ProjectionDropCounts(_FeedbackModel):
    execution_metrics: int = Field(ge=0)
    execution_artifacts: int = Field(ge=0)
    multimodal_artifacts: int = Field(ge=0)
    multimodal_units: int = Field(ge=0)
    multimodal_column_units: int = Field(ge=0)


class RevisionFeedbackProjection(_FeedbackModel):
    """The only T05/T06 object allowed into a T02 revision prompt."""

    schema_version: Literal[1] = 1
    execution: ExecutionFeedback | None = None
    multimodal: tuple[MultimodalFeedback, ...] = ()
    dropped_counts: ProjectionDropCounts
    truncated_field_count: int = Field(ge=0)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_fingerprint(self) -> "RevisionFeedbackProjection":
        payload = self.model_dump(mode="json", exclude={"fingerprint"})
        expected = hashlib.sha256(
            _canonical_json(payload).encode("utf-8")
        ).hexdigest()
        if self.fingerprint != expected:
            raise ValueError("revision feedback fingerprint does not match content")
        return self


def _project_execution(
    result: ExecutionResult,
    dropped: dict[str, int],
) -> tuple[ExecutionFeedback, int]:
    truncated = 0

    def bounded(value: str, limit: int) -> str:
        nonlocal truncated
        output, was_truncated = _bounded_text(value, limit)
        truncated += int(was_truncated)
        return output

    ordered_metrics = sorted(
        result.metrics,
        key=lambda item: (item.name, item.artifact_id, item.round_index),
    )
    dropped["execution_metrics"] = max(
        0,
        len(ordered_metrics) - MAX_EXECUTION_METRICS,
    )
    metrics = tuple(
        ExecutionMetricFeedback(
            name=bounded(item.name, MAX_IDENTIFIER_LENGTH),
            value=item.value,
            unit=bounded(item.unit, MAX_UNIT_LENGTH),
            source=item.source,
            artifact_id=bounded(item.artifact_id, MAX_IDENTIFIER_LENGTH),
            validation_status=item.validation_status,
            round_index=item.round_index,
        )
        for item in ordered_metrics[:MAX_EXECUTION_METRICS]
    )

    ordered_artifacts = sorted(
        result.artifacts,
        key=lambda item: (item.artifact_id, item.relative_path),
    )
    dropped["execution_artifacts"] = max(
        0,
        len(ordered_artifacts) - MAX_EXECUTION_ARTIFACTS,
    )
    artifacts = tuple(
        ExecutionArtifactFeedback(
            artifact_id=bounded(item.artifact_id, MAX_IDENTIFIER_LENGTH),
            relative_path=bounded(item.relative_path, MAX_SOURCE_PATH_LENGTH),
            kind=item.kind,
            media_type=bounded(item.media_type, MAX_MEDIA_TYPE_LENGTH),
            required=item.required,
            sha256=item.sha256,
            size_bytes=item.size_bytes,
            validation_status=item.validation_status,
        )
        for item in ordered_artifacts[:MAX_EXECUTION_ARTIFACTS]
    )

    failure = None
    if result.error is not None:
        failure = ExecutionFailureFeedback(
            code=bounded(result.error.code, MAX_IDENTIFIER_LENGTH),
            message=bounded(result.error.message, MAX_TEXT_LENGTH),
            stage=bounded(result.error.stage, MAX_IDENTIFIER_LENGTH),
            retryable=result.error.retryable,
        )

    environment = result.environment_fingerprint
    projection = ExecutionFeedback(
        execution_id=bounded(result.execution_id, MAX_IDENTIFIER_LENGTH),
        spec_id=bounded(result.spec_id, MAX_IDENTIFIER_LENGTH),
        question_id=bounded(result.question_id, MAX_IDENTIFIER_LENGTH),
        round_index=result.round_index,
        parent_execution_id=(
            bounded(result.parent_execution_id, MAX_IDENTIFIER_LENGTH)
            if result.parent_execution_id is not None
            else None
        ),
        mode=result.mode,
        status=result.status,
        entrypoint=bounded(result.entrypoint, MAX_IDENTIFIER_LENGTH),
        entrypoint_class=result.entrypoint_class,
        actual_execution=result.actual_execution,
        scientific_result_usable=result.scientific_result_usable,
        runner_verified=result.runner_verified,
        provenance_complete=result.provenance_complete,
        datasets_validated=result.datasets_validated,
        artifacts_validated=result.artifacts_validated,
        metrics_validated=result.metrics_validated,
        git_sha=(environment.git_sha if environment is not None else None),
        metrics=metrics,
        artifacts=artifacts,
        failure=failure,
        output=ExecutionOutputSummary(
            stdout_bytes=result.stdout_bytes,
            stderr_bytes=result.stderr_bytes,
            stdout_truncated=result.stdout_truncated,
            stderr_truncated=result.stderr_truncated,
            warning_count=len(result.warnings),
        ),
    )
    return projection, truncated


def _project_multimodal(
    artifacts: Sequence[MultimodalArtifact],
    dropped: dict[str, int],
) -> tuple[tuple[MultimodalFeedback, ...], int]:
    by_id: dict[str, MultimodalArtifact] = {}
    for artifact in artifacts:
        if not isinstance(artifact, MultimodalArtifact):
            raise TypeError(
                "multimodal_artifacts must contain MultimodalArtifact instances"
            )
        if artifact.artifact_id in by_id:
            raise ValueError(
                f"duplicate multimodal artifact_id: {artifact.artifact_id}"
            )
        by_id[artifact.artifact_id] = artifact

    ordered = [by_id[key] for key in sorted(by_id)]
    dropped["multimodal_artifacts"] = max(
        0,
        len(ordered) - MAX_MULTIMODAL_ARTIFACTS,
    )
    truncated = 0

    def bounded(value: str, limit: int) -> str:
        nonlocal truncated
        output, was_truncated = _bounded_text(value, limit)
        truncated += int(was_truncated)
        return output

    projected: list[MultimodalFeedback] = []
    for artifact in ordered[:MAX_MULTIMODAL_ARTIFACTS]:
        summary = to_consumer_summary(artifact)
        dropped["multimodal_units"] += max(
            0,
            len(summary.units) - MAX_UNIT_ITEMS,
        )
        dropped["multimodal_column_units"] += max(
            0,
            len(summary.column_units) - MAX_UNIT_ITEMS,
        )
        projected.append(
            MultimodalFeedback(
                artifact_id=bounded(
                    summary.artifact_id,
                    MAX_IDENTIFIER_LENGTH,
                ),
                modality=summary.modality,
                source_path=bounded(
                    summary.source_path,
                    MAX_SOURCE_PATH_LENGTH,
                ),
                source_type=summary.source_type,
                page=summary.page,
                units=tuple(
                    bounded(unit, MAX_UNIT_LENGTH)
                    for unit in summary.units[:MAX_UNIT_ITEMS]
                ),
                column_units=tuple(
                    ColumnUnitFeedback(
                        column=bounded(binding.column, MAX_IDENTIFIER_LENGTH),
                        unit=bounded(binding.unit, MAX_UNIT_LENGTH),
                    )
                    for binding in summary.column_units[:MAX_UNIT_ITEMS]
                ),
                confidence=summary.confidence,
                validation_status=summary.validation_status,
                header_count=summary.header_count,
                row_count=summary.row_count,
            )
        )
    return tuple(projected), truncated


def build_revision_feedback(
    *,
    execution_result: ExecutionResult | None = None,
    multimodal_artifacts: Sequence[MultimodalArtifact] | None = None,
) -> RevisionFeedbackProjection | None:
    """Build one deterministic, bounded, whitelist-only revision projection."""
    if execution_result is not None and not isinstance(
        execution_result,
        ExecutionResult,
    ):
        raise TypeError("execution_result must be an ExecutionResult instance")
    if multimodal_artifacts is not None and not isinstance(
        multimodal_artifacts,
        Sequence,
    ):
        raise TypeError("multimodal_artifacts must be a sequence")

    multimodal_input = tuple(multimodal_artifacts or ())
    if execution_result is None and not multimodal_input:
        return None

    dropped = {key: 0 for key in _DROP_KEYS}
    execution = None
    truncated = 0
    if execution_result is not None:
        execution, execution_truncated = _project_execution(
            execution_result,
            dropped,
        )
        truncated += execution_truncated
    multimodal, multimodal_truncated = _project_multimodal(
        multimodal_input,
        dropped,
    )
    truncated += multimodal_truncated

    drop_counts = ProjectionDropCounts(**dropped)
    content = {
        "schema_version": 1,
        "execution": execution,
        "multimodal": multimodal,
        "dropped_counts": drop_counts,
        "truncated_field_count": truncated,
    }
    fingerprint_payload = {
        "schema_version": content["schema_version"],
        "execution": (
            execution.model_dump(mode="json")
            if execution is not None
            else None
        ),
        "multimodal": [
            item.model_dump(mode="json") for item in multimodal
        ],
        "dropped_counts": drop_counts.model_dump(mode="json"),
        "truncated_field_count": truncated,
    }
    fingerprint = hashlib.sha256(
        _canonical_json(fingerprint_payload).encode("utf-8")
    ).hexdigest()
    projection = RevisionFeedbackProjection(
        **content,
        fingerprint=fingerprint,
    )
    serialized_bytes = len(
        _canonical_json(projection.model_dump(mode="json")).encode("utf-8")
    )
    if serialized_bytes > MAX_PROJECTION_BYTES:
        raise ValueError(
            "bounded revision feedback exceeded MAX_PROJECTION_BYTES"
        )
    return projection


__all__ = [
    "MAX_EXECUTION_ARTIFACTS",
    "MAX_EXECUTION_METRICS",
    "MAX_MULTIMODAL_ARTIFACTS",
    "MAX_PROJECTION_BYTES",
    "MAX_TEXT_LENGTH",
    "MAX_UNIT_ITEMS",
    "RevisionFeedbackProjection",
    "build_revision_feedback",
]
