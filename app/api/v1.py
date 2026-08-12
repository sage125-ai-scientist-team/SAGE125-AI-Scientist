"""版本化 API v1 路由与 T08 owner-contract 薄投影。"""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import FileResponse

from app.api.artifact_registry import (
    ArtifactIntegrityError,
    ArtifactConflict,
    ArtifactNotFound,
    ArtifactPermissionDenied,
    ArtifactRecord,
)
from app.api.auth import authenticate_and_rate_limit, principal
from app.api.contracts import (
    Artifact,
    ArtifactListResponse,
    ArtifactStatus,
    EvidenceListResponse,
    EvidenceProjection,
    EvidenceRelation,
    ErrorResponse,
    ExportCreateRequest,
    ExportResponse,
    FeedbackCreateRequest,
    JobAccepted,
    JobCreateRequest,
    JobError,
    JobLinks,
    JobListResponse,
    JobStatus,
    JobStatusResponse,
    MultimodalDetailListResponse,
    QuestionListResponse,
    QuestionSummary,
    RetryMetadata,
    TimeoutMetadata,
    TruthStatus,
    Version,
    VersionDiff,
    VersionListResponse,
    FeedbackReceipt,
    IssueProjection,
)
from app.api.errors import APIError, correlation_id
from app.api.job_queue import QueueCapacityError
from app.api.job_store import (
    IdempotencyConflict,
    JobNotFound,
    JobRecord,
)
from app.api.owner_composition import OwnerPortFailure
from app.api.upstream import (
    OwnerContractInvalid,
    OwnerContractUnavailable,
    OwnerIdentityMismatch,
    OwnerResourceNotFound,
)
from app.core.logging import get_logger
from app.export.canonical import CanonicalReport, CanonicalReportUnavailable
from app.export.service import CanonicalReportIdentityError, ExportStorageError


router = APIRouter(
    prefix="/api/v1",
    tags=["API v1"],
    dependencies=[Depends(authenticate_and_rate_limit)],
)
logger = get_logger("api.v1")


def _safe_traceback(exc: BaseException) -> str:
    """Return every traceback frame without host paths or exception payloads."""
    frames = [
        {
            "file": Path(frame.filename).name,
            "line": frame.lineno,
            "function": frame.name,
        }
        for frame in traceback.extract_tb(exc.__traceback__)
    ]
    return json.dumps(frames, ensure_ascii=True, separators=(",", ":"))


def _documented_response(description: str, example: dict) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"example": example}},
    }


_ERROR_RESPONSES = {
    401: {
        "model": ErrorResponse,
        **_documented_response(
            "需要 API key",
            {
                "code": "AUTHENTICATION_REQUIRED",
                "message": "需要有效的 API key。",
                "details": {},
                "correlation_id": "judge-demo-001",
                "retryable": False,
            },
        ),
    },
    403: {
        "model": ErrorResponse,
        **_documented_response(
            "资源不属于当前调用方",
            {
                "code": "FORBIDDEN",
                "message": "无权访问该资源。",
                "details": {},
                "correlation_id": "judge-demo-001",
                "retryable": False,
            },
        ),
    },
    400: {
        "model": ErrorResponse,
        **_documented_response(
            "Correlation ID 格式无效",
            {
                "code": "INVALID_CORRELATION_ID",
                "message": "X-Correlation-ID 格式无效。",
                "details": {},
                "correlation_id": "8da1ef30-72fa-4aba-949f-4402079df58d",
                "retryable": False,
            },
        ),
    },
    404: {
        "model": ErrorResponse,
        **_documented_response(
            "资源不存在",
            {
                "code": "JOB_NOT_FOUND",
                "message": "任务不存在。",
                "details": {"job_id": "missing-job"},
                "correlation_id": "judge-demo-001",
                "retryable": False,
            },
        ),
    },
    409: {
        "model": ErrorResponse,
        **_documented_response(
            "幂等冲突",
            {
                "code": "IDEMPOTENCY_CONFLICT",
                "message": "相同 Idempotency-Key 已用于不同请求。",
                "details": {},
                "correlation_id": "judge-demo-001",
                "retryable": False,
            },
        ),
    },
    413: {
        "model": ErrorResponse,
        **_documented_response(
            "请求体超限",
            {
                "code": "REQUEST_BODY_TOO_LARGE",
                "message": "API 请求体超过 64 KiB 上限。",
                "details": {"max_bytes": 65536},
                "correlation_id": "judge-demo-001",
                "retryable": False,
            },
        ),
    },
    422: {
        "model": ErrorResponse,
        **_documented_response(
            "请求校验失败",
            {
                "code": "VALIDATION_ERROR",
                "message": "请求参数不符合 API 契约。",
                "details": {"errors": []},
                "correlation_id": "judge-demo-001",
                "retryable": False,
            },
        ),
    },
    429: {
        "model": ErrorResponse,
        **_documented_response(
            "请求频率超限",
            {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "请求频率超过限制，请稍后重试。",
                "details": {"limit": 60, "window_seconds": 60},
                "correlation_id": "judge-demo-001",
                "retryable": True,
            },
        ),
    },
    500: {
        "model": ErrorResponse,
        **_documented_response(
            "未预期错误",
            {
                "code": "INTERNAL_ERROR",
                "message": "服务发生未预期错误。",
                "details": {},
                "correlation_id": "judge-demo-001",
                "retryable": False,
            },
        ),
    },
    503: {
        "model": ErrorResponse,
        **_documented_response(
            "队列或上游契约不可用",
            {
                "code": "UPSTREAM_CONTRACT_UNAVAILABLE",
                "message": "上游公开契约尚未接入。",
                "details": {
                    "component": "T02/T03/T05 contract",
                    "availability": "unavailable",
                },
                "correlation_id": "judge-demo-001",
                "retryable": True,
            },
        ),
    },
}

_EXPORT_ERROR_RESPONSES = {
    **_ERROR_RESPONSES,
    503: {
        "model": ErrorResponse,
        "description": "canonical report 或导出存储暂时不可用",
        "content": {
            "application/json": {
                "examples": {
                    "canonical_unavailable": {
                        "summary": "owner canonical projection 尚不可用",
                        "value": {
                            "code": "CANONICAL_REPORT_UNAVAILABLE",
                            "message": "canonical report 上游投影不可用。",
                            "details": {
                                "job_id": "job-example",
                                "run_id": "run-example",
                            },
                            "correlation_id": "judge-demo-001",
                            "retryable": True,
                        },
                    },
                    "storage_unavailable": {
                        "summary": "导出文件系统暂时不可用",
                        "value": {
                            "code": "EXPORT_STORAGE_UNAVAILABLE",
                            "message": "导出存储暂时不可用，未返回不完整产物。",
                            "details": {"job_id": "job-example", "format": "pdf"},
                            "correlation_id": "judge-demo-001",
                            "retryable": True,
                        },
                    },
                }
            }
        },
    },
}

_UPSTREAM_UNAVAILABLE_RESPONSES = {
    status_code: response
    for status_code, response in _ERROR_RESPONSES.items()
    if status_code in {400, 401, 403, 404, 413, 422, 429, 500, 503}
}

_READ_RESPONSES = {
    status_code: response
    for status_code, response in _ERROR_RESPONSES.items()
    if status_code in {400, 401, 403, 404, 409, 413, 422, 429, 500, 503}
}

_JOB_ACCEPTED_EXAMPLE = {
    "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
    "correlation_id": "judge-demo-001",
    "status": "queued",
    "created_at": "2026-07-28T06:30:00Z",
    "status_url": "/api/v1/jobs/c4ef4580-e351-4b44-b9a2-19edac5ec977",
    "reused": False,
}
_JOB_STATUS_EXAMPLE = {
    "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
    "correlation_id": "judge-demo-001",
    "kind": "research_run",
    "question_id": "Q001",
    "mode": "mock",
    "status": "running",
    "stage": "retrieval",
    "created_at": "2026-07-28T06:30:00Z",
    "updated_at": "2026-07-28T06:30:03Z",
    "started_at": "2026-07-28T06:30:01Z",
    "finished_at": None,
    "attempt": 1,
    "max_attempts": 2,
    "retry": {
        "attempt": 1,
        "max_attempts": 2,
        "retryable": False,
        "last_attempt_at": "2026-07-28T06:30:01Z",
        "next_retry_at": None,
        "backoff_seconds": None,
    },
    "timeout": {
        "timeout_seconds": 300,
        "deadline_at": "2026-07-28T06:35:01Z",
        "timed_out_at": None,
    },
    "upstream_run_id": None,
    "error": None,
    "links": {
        "self": "/api/v1/jobs/c4ef4580-e351-4b44-b9a2-19edac5ec977",
        "evidence": "/api/v1/jobs/c4ef4580-e351-4b44-b9a2-19edac5ec977/evidence",
        "artifacts": "/api/v1/jobs/c4ef4580-e351-4b44-b9a2-19edac5ec977/artifacts",
        "versions": "/api/v1/jobs/c4ef4580-e351-4b44-b9a2-19edac5ec977/versions",
        "feedback": "/api/v1/jobs/c4ef4580-e351-4b44-b9a2-19edac5ec977/feedback",
    },
}


def _store(request: Request):
    store = getattr(request.app.state, "job_store", None)
    if store is None:
        raise APIError(
            status_code=503,
            code="JOB_STORE_UNAVAILABLE",
            message="任务状态存储尚未就绪。",
            retryable=True,
        )
    return store


def _queue(request: Request):
    job_queue = getattr(request.app.state, "job_queue", None)
    if job_queue is None:
        raise APIError(
            status_code=503,
            code="JOB_QUEUE_UNAVAILABLE",
            message="任务队列尚未就绪。",
            retryable=True,
        )
    return job_queue


def _registry(request: Request):
    registry = getattr(request.app.state, "artifact_registry", None)
    if registry is None:
        raise APIError(
            status_code=503,
            code="ARTIFACT_REGISTRY_UNAVAILABLE",
            message="产物注册表尚未就绪。",
            retryable=True,
        )
    return registry


def _export_service(request: Request):
    service = getattr(request.app.state, "export_service", None)
    if service is None:
        raise APIError(
            status_code=503,
            code="EXPORT_SERVICE_UNAVAILABLE",
            message="导出服务尚未就绪。",
            retryable=True,
        )
    return service


def _upstream(request: Request):
    port = getattr(request.app.state, "upstream_read_port", None)
    if port is None:
        _upstream_unavailable("T01/T02/T07 read port")
    return port


def _feedback_submit_port(request: Request):
    """Return the configured T03 submit adapter or fail closed."""
    port = getattr(request.app.state, "feedback_submit_port", None)
    if port is None:
        _upstream_unavailable("T03 FeedbackService.submit")
    return port


def _multimodal_read_port(request: Request):
    """Return the configured frozen T06 detail adapter or fail closed."""
    port = getattr(request.app.state, "multimodal_read_port", None)
    if port is None:
        _upstream_unavailable("T06 list_multimodal_details")
    return port


def _links(job_id: str) -> JobLinks:
    base = f"/api/v1/jobs/{job_id}"
    return JobLinks(
        self=base,
        evidence=f"{base}/evidence",
        multimodal=f"{base}/multimodal",
        artifacts=f"{base}/artifacts",
        versions=f"{base}/versions",
        feedback=f"{base}/feedback",
    )


def _status(record: JobRecord) -> JobStatusResponse:
    error = None
    if record.error_code:
        error = JobError(
            code=record.error_code,
            message=record.error_message or "任务失败。",
            retryable=record.retryable,
        )
    return JobStatusResponse(
        job_id=record.job_id,
        correlation_id=record.correlation_id,
        kind=record.kind,
        question_id=record.question_id,
        mode=record.mode,
        status=JobStatus(record.status),
        stage=record.stage,
        created_at=datetime.fromisoformat(record.created_at),
        updated_at=datetime.fromisoformat(record.updated_at),
        started_at=(
            datetime.fromisoformat(record.started_at) if record.started_at else None
        ),
        finished_at=(
            datetime.fromisoformat(record.finished_at)
            if record.finished_at
            else None
        ),
        attempt=record.attempt,
        max_attempts=record.max_attempts,
        retry=RetryMetadata(
            attempt=record.attempt,
            max_attempts=record.max_attempts,
            retryable=record.retryable,
            last_attempt_at=(
                datetime.fromisoformat(record.last_attempt_at)
                if record.last_attempt_at
                else None
            ),
            next_retry_at=(
                datetime.fromisoformat(record.next_retry_at)
                if record.next_retry_at
                else None
            ),
            backoff_seconds=record.retry_backoff_seconds,
        ),
        timeout=TimeoutMetadata(
            timeout_seconds=record.timeout_seconds,
            deadline_at=(
                datetime.fromisoformat(record.deadline_at)
                if record.deadline_at
                else None
            ),
            timed_out_at=(
                datetime.fromisoformat(record.timed_out_at)
                if record.timed_out_at
                else None
            ),
        ),
        upstream_run_id=record.upstream_run_id,
        error=error,
        links=_links(record.job_id),
    )


def _get_job(request: Request, job_id: str) -> JobRecord:
    try:
        record = _store(request).get_job(job_id)
    except JobNotFound:
        raise APIError(
            status_code=404,
            code="JOB_NOT_FOUND",
            message="任务不存在。",
            details={"job_id": job_id},
        ) from None
    if record.requested_by != principal(request).actor_id:
        raise APIError(
            status_code=403,
            code="FORBIDDEN",
            message="无权访问该任务。",
            details={"job_id": job_id},
            retryable=False,
        )
    return record


def _upstream_unavailable(component: str) -> None:
    raise APIError(
        status_code=503,
        code="UPSTREAM_CONTRACT_UNAVAILABLE",
        message=f"{component} 公开契约尚未接入。",
        details={"component": component, "availability": "unavailable"},
        retryable=True,
    )


def _owner_call(component: str, operation):
    try:
        return operation()
    except OwnerContractUnavailable as exc:
        _upstream_unavailable(exc.component)
    except OwnerIdentityMismatch as exc:
        raise APIError(
            status_code=409,
            code="UPSTREAM_IDENTITY_MISMATCH",
            message="上游资源身份与当前任务不一致。",
            details={"component": exc.component},
            retryable=False,
        ) from None
    except OwnerResourceNotFound as exc:
        raise APIError(
            status_code=404,
            code="UPSTREAM_RESOURCE_NOT_FOUND",
            message="上游资源不存在。",
            details={"resource": exc.resource, "identifier": exc.identifier},
            retryable=False,
        ) from None
    except OwnerContractInvalid as exc:
        raise APIError(
            status_code=503,
            code="UPSTREAM_CONTRACT_INVALID",
            message=f"{component} 返回的数据不符合冻结契约。",
            details={"component": exc.component, "availability": "unavailable"},
            retryable=False,
        ) from None


def _raise_owner_port_failure(exc: OwnerPortFailure) -> NoReturn:
    """Map safe T03/T06 adapter categories to stable HTTP errors."""
    mappings = {
        "invalid_input": (
            422,
            "OWNER_INPUT_INVALID",
            "请求不符合 owner 冻结契约。",
        ),
        "unsafe_input": (
            422,
            "FEEDBACK_UNSAFE_INPUT",
            "反馈内容未通过安全校验。",
        ),
        "permission_denied": (
            403,
            "FEEDBACK_PERMISSION_DENIED",
            "当前调用方无权提交该反馈。",
        ),
        "conflict": (
            409,
            "OWNER_STATE_CONFLICT",
            "相同幂等键或 owner 状态与本次请求冲突。",
        ),
        "identity_mismatch": (
            409,
            "UPSTREAM_IDENTITY_MISMATCH",
            "上游资源身份与当前任务不一致。",
        ),
        "unavailable": (
            503,
            "UPSTREAM_CONTRACT_UNAVAILABLE",
            "owner 公开端口当前不可用。",
        ),
    }
    status_code, code, message = mappings[exc.category]
    raise APIError(
        status_code=status_code,
        code=code,
        message=message,
        details={
            "component": exc.component,
            "availability": (
                "unavailable" if status_code == 503 else "available"
            ),
        },
        retryable=exc.retryable,
    ) from None


def _upstream_run_id(record: JobRecord) -> str:
    if record.upstream_run_id:
        return record.upstream_run_id
    raise APIError(
        status_code=409,
        code="UPSTREAM_RESULT_NOT_READY",
        message="任务尚未绑定可读取的上游运行结果。",
        details={"job_id": record.job_id, "status": record.status},
        retryable=True,
    )


def _is_capacity_rejection(record: JobRecord) -> bool:
    return (
        record.status == JobStatus.FAILED.value
        and record.stage == "queue_rejected"
        and record.error_code == "QUEUE_CAPACITY_EXCEEDED"
        and record.retryable
    )


def _has_execution_marker(record: JobRecord) -> bool:
    return bool(
        record.attempt != 0
        or record.started_at is not None
        or record.upstream_run_id is not None
    )


def _raise_queue_capacity(record: JobRecord) -> None:
    raise APIError(
        status_code=503,
        code="QUEUE_CAPACITY_EXCEEDED",
        message="任务队列已满，请稍后重试。",
        details={"job_id": record.job_id},
        retryable=True,
    )


def _reject_unsafe_capacity_retry(record: JobRecord) -> None:
    raise APIError(
        status_code=409,
        code="QUEUE_CAPACITY_RETRY_UNSAFE",
        message="任务已有执行痕迹，不能通过容量恢复机制重新入队。",
        details={"job_id": record.job_id},
        retryable=False,
    )


def _submit_capacity_retry(request: Request, record: JobRecord) -> JobRecord:
    store = _store(request)
    claimed_record, claimed = store.claim_queue_capacity_retry(
        record.job_id,
        expected_updated_at=record.updated_at,
    )
    if not claimed:
        if (
            claimed_record.status == JobStatus.RETRYING.value
            and claimed_record.stage == "queue_retry_claimed"
        ):
            raise APIError(
                status_code=503,
                code="QUEUE_RETRY_IN_PROGRESS",
                message="容量重试正在认领并等待入队确认，请稍后重试。",
                details={"job_id": claimed_record.job_id},
                retryable=True,
            )
        if _is_capacity_rejection(claimed_record):
            if _has_execution_marker(claimed_record):
                _reject_unsafe_capacity_retry(claimed_record)
            _raise_queue_capacity(claimed_record)
        return claimed_record

    try:
        _queue(request).submit(claimed_record.job_id)
    except QueueCapacityError:
        rejected = store.transition(
            claimed_record.job_id,
            JobStatus.FAILED,
            stage="queue_rejected",
            actor="api",
            source="queue_retry",
            error_code="QUEUE_CAPACITY_EXCEEDED",
            error_message="任务队列已满，请稍后重试。",
            retryable=True,
        )
        _raise_queue_capacity(rejected)

    store.mark_queue_retry_submitted(claimed_record.job_id)
    return store.get_job(claimed_record.job_id)


@router.get(
    "/questions",
    response_model=QuestionListResponse,
    responses={
        200: _documented_response(
            "问题列表",
            {
                "items": [
                    {
                        "question_id": "Q001",
                        "domain": "materials science",
                        "question": "How can a stable catalyst be designed?",
                        "source_page": 12,
                        "source_excerpt": "Design a stable catalyst.",
                        "status": "unavailable",
                        "status_reason": "T07 question status was not supplied.",
                    }
                ],
                "count": 1,
                "total": 1,
                "availability": "partial",
            },
        ),
        **_READ_RESPONSES,
    },
    summary="查询问题清单与 owner 状态",
)
def list_questions(
    request: Request,
    domain: str | None = Query(default=None, min_length=1, max_length=128),
    status: str | None = Query(default=None, min_length=1, max_length=64),
    query: str | None = Query(default=None, min_length=1, max_length=256),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=125),
) -> QuestionListResponse:
    records = _owner_call(
        "T07 QuestionItem",
        lambda: _upstream(request).list_questions(),
    )
    normalized_query = query.casefold() if query else None
    filtered = [
        record
        for record in records
        if (domain is None or record.item.domain == domain)
        and (status is None or (record.status or "unavailable") == status)
        and (
            normalized_query is None
            or normalized_query in record.item.id.casefold()
            or normalized_query in record.item.question.casefold()
        )
    ]
    page = filtered[offset : offset + limit]
    items = [
        QuestionSummary(
            question_id=record.item.id,
            domain=record.item.domain,
            question=record.item.question,
            source_page=record.item.source_page,
            source_excerpt=record.item.booklet_excerpt,
            status=record.status or "unavailable",
            status_reason=(
                record.status_reason
                if record.status is not None
                else "T07 question status was not supplied."
            ),
        )
        for record in page
    ]
    availability = (
        "available"
        if all(record.status is not None for record in filtered)
        else "partial"
    )
    return QuestionListResponse(
        items=items,
        count=len(items),
        total=len(filtered),
        availability=availability,
    )


@router.post(
    "/jobs",
    response_model=JobAccepted,
    status_code=202,
    responses={
        202: _documented_response("任务已进入队列", _JOB_ACCEPTED_EXAMPLE),
        **_ERROR_RESPONSES,
    },
    summary="异步创建科研任务",
)
def create_job(
    payload: JobCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        max_length=256,
    ),
) -> JobAccepted:
    store = _store(request)
    try:
        record, reused = store.create_job(
            request=payload,
            correlation_id=correlation_id(request),
            idempotency_key=idempotency_key,
            requested_by=principal(request).actor_id,
        )
    except IdempotencyConflict:
        raise APIError(
            status_code=409,
            code="IDEMPOTENCY_CONFLICT",
            message="相同 Idempotency-Key 已用于不同请求。",
        ) from None

    if reused and record.requested_by != principal(request).actor_id:
        raise APIError(
            status_code=409,
            code="IDEMPOTENCY_CONFLICT",
            message="相同 Idempotency-Key 已用于其他调用方。",
            retryable=False,
        )
    if reused and _is_capacity_rejection(record):
        if _has_execution_marker(record):
            store.claim_queue_capacity_retry(
                record.job_id,
                expected_updated_at=record.updated_at,
            )
            _reject_unsafe_capacity_retry(record)
        record = _submit_capacity_retry(request, record)
    elif (
        reused
        and record.status == JobStatus.RETRYING.value
        and record.stage == "queue_retry_claimed"
    ):
        raise APIError(
            status_code=503,
            code="QUEUE_RETRY_IN_PROGRESS",
            message="容量重试正在认领并等待入队确认，请稍后重试。",
            details={"job_id": record.job_id},
            retryable=True,
        )
    elif not reused:
        try:
            _queue(request).submit(record.job_id)
        except QueueCapacityError:
            rejected = store.transition(
                record.job_id,
                JobStatus.FAILED,
                stage="queue_rejected",
                actor="api",
                source="queue",
                error_code="QUEUE_CAPACITY_EXCEEDED",
                error_message="任务队列已满，请稍后重试。",
                retryable=True,
            )
            _raise_queue_capacity(rejected)

    return JobAccepted(
        job_id=record.job_id,
        correlation_id=record.correlation_id,
        status=JobStatus(record.status),
        created_at=datetime.fromisoformat(record.created_at),
        status_url=f"/api/v1/jobs/{record.job_id}",
        reused=reused,
    )


@router.get(
    "/jobs",
    response_model=JobListResponse,
    responses={
        200: _documented_response(
            "任务列表",
            {"items": [_JOB_STATUS_EXAMPLE], "count": 1},
        ),
        **_ERROR_RESPONSES,
    },
    summary="查询任务列表",
)
def list_jobs(
    request: Request,
    question_id: str | None = Query(default=None, max_length=64),
    status: JobStatus | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> JobListResponse:
    records = _store(request).list_jobs(
        question_id=question_id,
        status=status,
        requested_by=principal(request).actor_id,
        limit=limit,
    )
    items = [_status(record) for record in records]
    return JobListResponse(items=items, count=len(items))


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    responses={
        200: _documented_response("任务状态", _JOB_STATUS_EXAMPLE),
        **_ERROR_RESPONSES,
    },
    summary="查询任务状态",
)
def get_job(job_id: str, request: Request) -> JobStatusResponse:
    return _status(_get_job(request, job_id))


@router.get(
    "/jobs/{job_id}/evidence",
    response_model=EvidenceListResponse,
    responses={
        200: _documented_response(
            "证据包",
            {
                "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
                "bundle_id": "bundle-001",
                "items": [],
                "truncated": False,
                "truncation_reason": None,
                "availability": "available",
            },
        ),
        **_READ_RESPONSES,
    },
    summary="读取 T01 证据包",
)
def list_evidence(job_id: str, request: Request) -> EvidenceListResponse:
    record = _get_job(request, job_id)
    run_id = _upstream_run_id(record)
    bundle = _owner_call(
        "T01 EvidenceBundle",
        lambda: _upstream(request).get_evidence_bundle(
            run_id=run_id,
            question_id=record.question_id,
        ),
    )
    links_by_evidence: dict[str, list[EvidenceRelation]] = {}
    for link in bundle.links:
        links_by_evidence.setdefault(link.evidence_id, []).append(
            EvidenceRelation(
                claim_id=link.claim_id,
                relation=link.relation,
                confidence=link.confidence,
                validation_status=link.validation_status,
            )
        )
    items = [
        EvidenceProjection(
            evidence_id=card.evidence_id,
            source_id=card.source_id,
            source_type=card.source_type,
            title=card.title,
            quoted_text=card.quoted_text,
            locator=card.locator,
            authors=card.authors,
            year=card.year,
            doi=card.doi,
            url=card.url,
            content_hash=card.content_hash,
            domain=card.domain,
            verification_status=card.verification_status,
            relations=links_by_evidence.get(card.evidence_id, []),
        )
        for card in bundle.evidences
    ]
    return EvidenceListResponse(
        job_id=job_id,
        bundle_id=bundle.bundle_id,
        items=items,
        truncated=bundle.truncated,
        truncation_reason=bundle.truncation_reason,
        availability="available",
    )


@router.get(
    "/jobs/{job_id}/multimodal",
    response_model=MultimodalDetailListResponse,
    responses={
        200: _documented_response(
            "T06 多模态详情",
            {
                "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
                "version_id": "run-001:v1",
                "items": [],
                "availability": "available",
            },
        ),
        **_READ_RESPONSES,
    },
    summary="读取 T06 冻结多模态详情",
)
def list_multimodal_details(
    job_id: str,
    request: Request,
    version_id: str = Query(min_length=1, max_length=128),
) -> MultimodalDetailListResponse:
    """Read identity-bound T06 details without scanning owner storage."""
    record = _get_job(request, job_id)
    run_id = _upstream_run_id(record)
    try:
        items = _multimodal_read_port(request).list_details(
            run_id=run_id,
            question_id=record.question_id,
            version_id=version_id,
        )
    except OwnerPortFailure as exc:
        _raise_owner_port_failure(exc)
    return MultimodalDetailListResponse(
        job_id=job_id,
        version_id=version_id,
        items=items,
        availability="available",
    )


@router.get(
    "/jobs/{job_id}/artifacts",
    response_model=ArtifactListResponse,
    responses={200: _documented_response("任务产物", {"items": []}), **_ERROR_RESPONSES},
    summary="列出当前调用方的任务产物",
)
def list_artifacts(job_id: str, request: Request) -> ArtifactListResponse:
    _get_job(request, job_id)
    records = _registry(request).list_for_job(
        job_id,
        actor_id=principal(request).actor_id,
    )
    return ArtifactListResponse(
        job_id=job_id,
        items=[_artifact_projection(record) for record in records],
        availability="available",
    )


def _artifact_projection(record: ArtifactRecord) -> Artifact:
    return Artifact(
        artifact_id=record.artifact_id,
        name=record.name,
        artifact_type=record.artifact_type,
        media_type=record.media_type,
        size_bytes=record.size_bytes,
        sha256=record.sha256,
        status=ArtifactStatus(record.status),
        truth_status=TruthStatus(record.truth_status),
        created_at=datetime.fromisoformat(record.created_at),
        download_url=(
            f"/api/v1/jobs/{record.job_id}/artifacts/"
            f"{record.artifact_id}/download"
        ),
    )


@router.get(
    "/jobs/{job_id}/report",
    response_model=CanonicalReport,
    responses={
        200: _documented_response(
            "Canonical report",
            {
                "schema_version": "t08.report.v1",
                "generated_at": "2026-08-10T12:00:00Z",
                "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
                "question_id": "Q001",
                "run_id": "run-001",
                "version_id": "run-001:v2",
                "title": "Canonical Research Report",
                "question": "How can a stable catalyst be designed?",
                "domain": "materials science",
                "truth_status": "planned",
                "hypotheses": [],
                "methods": [],
                "evidence": [],
                "reviewer_issues": [],
                "feedback": [],
                "gates": [],
                "execution": {
                    "availability": "unavailable",
                    "status": "planned",
                    "actual_execution": False,
                    "metrics": [],
                    "warnings": [],
                },
                "multimodal": [],
                "known_limitations": [],
                "content_sha256": "3f43d005df1dbde5e79cd613a0779f4ccb6cfa85653a3d1f1cb66b24198bb993",
            },
        ),
        **_ERROR_RESPONSES,
    },
    summary="读取 Gate、执行与多模态的 canonical report 投影",
)
def get_canonical_report(job_id: str, request: Request) -> CanonicalReport:
    job = _get_job(request, job_id)
    run_id = _upstream_run_id(job)
    try:
        return _export_service(request).get_report(
            job_id=job.job_id,
            question_id=job.question_id,
            run_id=run_id,
        )
    except CanonicalReportUnavailable:
        raise APIError(
            status_code=503,
            code="CANONICAL_REPORT_UNAVAILABLE",
            message="canonical report 上游投影不可用。",
            details={"job_id": job.job_id, "run_id": run_id},
            retryable=True,
        ) from None
    except CanonicalReportIdentityError:
        raise APIError(
            status_code=503,
            code="CANONICAL_REPORT_IDENTITY_MISMATCH",
            message="canonical report 与任务标识不一致。",
            details={"job_id": job.job_id, "run_id": run_id},
            retryable=False,
        ) from None


@router.get(
    "/jobs/{job_id}/artifacts/{artifact_id}/download",
    response_class=FileResponse,
    responses=_ERROR_RESPONSES,
    summary="校验归属与完整性后下载产物",
)
def download_artifact(job_id: str, artifact_id: str, request: Request):
    job = _get_job(request, job_id)
    actor_id = principal(request).actor_id
    try:
        record = _registry(request).get(artifact_id, actor_id=actor_id)
        if record.job_id != job.job_id or record.question_id != job.question_id:
            raise ArtifactPermissionDenied(artifact_id)
        path = _registry(request).resolve_for_download(
            artifact_id,
            actor_id=actor_id,
        )
    except ArtifactNotFound:
        raise APIError(
            status_code=404,
            code="ARTIFACT_NOT_FOUND",
            message="产物不存在。",
            details={"artifact_id": artifact_id},
        ) from None
    except ArtifactPermissionDenied:
        raise APIError(
            status_code=403,
            code="FORBIDDEN",
            message="无权访问该产物。",
            retryable=False,
        ) from None
    except ArtifactIntegrityError:
        raise APIError(
            status_code=409,
            code="ARTIFACT_INTEGRITY_FAILED",
            message="产物完整性校验失败，已拒绝下载。",
            details={"artifact_id": artifact_id},
            retryable=False,
        ) from None
    return FileResponse(
        path,
        media_type=record.media_type,
        filename=record.name,
        headers={
            "ETag": f'"{record.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/jobs/{job_id}/exports",
    response_model=ExportResponse,
    status_code=201,
    responses={
        200: _documented_response("幂等重放，复用已有导出", {"items": [], "reused": True}),
        201: _documented_response("导出已生成", {"items": [], "reused": False}),
        **_EXPORT_ERROR_RESPONSES,
    },
    summary="从 canonical report 生成一致的 JSON/Markdown/PDF",
)
def create_export(
    job_id: str,
    payload: ExportCreateRequest,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=256,
    ),
) -> ExportResponse:
    job = _get_job(request, job_id)
    if not idempotency_key:
        raise APIError(
            status_code=400,
            code="IDEMPOTENCY_KEY_REQUIRED",
            message="导出请求必须提供 Idempotency-Key。",
            retryable=False,
        )
    run_id = _upstream_run_id(job)
    try:
        result = _export_service(request).export(
            job_id=job.job_id,
            question_id=job.question_id,
            run_id=run_id,
            actor_id=principal(request).actor_id,
            idempotency_key=idempotency_key,
            formats=payload.formats,
        )
    except CanonicalReportUnavailable:
        raise APIError(
            status_code=503,
            code="CANONICAL_REPORT_UNAVAILABLE",
            message="canonical report 上游投影不可用。",
            details={"job_id": job.job_id, "run_id": run_id},
            retryable=True,
        ) from None
    except CanonicalReportIdentityError:
        raise APIError(
            status_code=503,
            code="CANONICAL_REPORT_IDENTITY_MISMATCH",
            message="canonical report 与任务标识不一致。",
            details={"job_id": job.job_id, "run_id": run_id},
            retryable=False,
        ) from None
    except ArtifactIntegrityError:
        raise APIError(
            status_code=409,
            code="ARTIFACT_INTEGRITY_FAILED",
            message="已有导出产物完整性校验失败。",
            retryable=False,
        ) from None
    except ArtifactConflict:
        raise APIError(
            status_code=409,
            code="IDEMPOTENCY_CONFLICT",
            message="相同 Idempotency-Key 已用于不同导出请求。",
            retryable=False,
        ) from None
    except ExportStorageError as exc:
        cause = exc.cause
        logger.error(
            "export_storage_unavailable correlation_id=%s job_id=%s format=%s "
            "error_type=%s errno=%s winerror=%s stack=%s",
            correlation_id(request),
            job.job_id,
            exc.format_name,
            type(cause).__name__,
            getattr(cause, "errno", None),
            getattr(cause, "winerror", None),
            _safe_traceback(cause),
        )
        raise APIError(
            status_code=503,
            code="EXPORT_STORAGE_UNAVAILABLE",
            message="导出存储暂时不可用，未返回不完整产物。",
            details={"job_id": job.job_id, "format": exc.format_name},
            retryable=True,
        ) from None
    response.status_code = 200 if result.reused else 201
    return ExportResponse(
        job_id=job.job_id,
        items=[_artifact_projection(record) for record in result.items],
        reused=result.reused,
    )


@router.get(
    "/jobs/{job_id}/versions/diff",
    response_model=VersionDiff,
    responses={
        200: _documented_response(
            "结构化版本差异",
            {
                "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
                "from_version_id": "run-1:v1",
                "to_version_id": "run-1:v2",
                "changes": [],
                "issue_changes": [],
                "score_delta": {},
                "stop_reason": None,
                "availability": "available",
            },
        ),
        **_READ_RESPONSES,
    },
    summary="查询 T02 提供的结构化版本差异",
)
def version_diff(
    job_id: str,
    request: Request,
    from_version_id: str = Query(min_length=1, max_length=128),
    to_version_id: str = Query(min_length=1, max_length=128),
):
    record = _get_job(request, job_id)
    run_id = _upstream_run_id(record)
    diff = _owner_call(
        "T02 structured version diff",
        lambda: _upstream(request).get_version_diff(
            run_id=run_id,
            question_id=record.question_id,
            from_version_id=from_version_id,
            to_version_id=to_version_id,
        ),
    )
    if (
        diff.run_id != run_id
        or diff.question_id != record.question_id
        or diff.from_version_id != from_version_id
        or diff.to_version_id != to_version_id
    ):
        raise APIError(
            status_code=409,
            code="UPSTREAM_IDENTITY_MISMATCH",
            message="上游版本差异与任务运行标识不一致。",
            details={"component": "T02 structured version diff"},
            retryable=False,
        )
    return VersionDiff(
        job_id=job_id,
        from_version_id=diff.from_version_id,
        to_version_id=diff.to_version_id,
        changes=diff.changes,
        issue_changes=diff.issue_changes,
        score_delta=diff.score_delta,
        stop_reason=diff.stop_reason,
        availability="available",
    )


@router.get(
    "/jobs/{job_id}/versions",
    response_model=VersionListResponse,
    responses={
        200: _documented_response(
            "版本列表",
            {
                "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
                "items": [],
                "availability": "partial",
            },
        ),
        **_READ_RESPONSES,
    },
    summary="列出 T02 计划版本与 Reviewer issue",
)
def list_versions(job_id: str, request: Request):
    record = _get_job(request, job_id)
    run_id = _upstream_run_id(record)
    versions = _owner_call(
        "T02 PlanVersion/IssueClosure",
        lambda: _upstream(request).list_plan_versions(
            run_id=run_id,
            question_id=record.question_id,
        ),
    )
    items: list[Version] = []
    for owner_version in versions:
        if owner_version.run_id != run_id:
            raise APIError(
                status_code=409,
                code="UPSTREAM_IDENTITY_MISMATCH",
                message="上游版本与任务运行标识不一致。",
                details={"component": "T02 PlanVersion"},
                retryable=False,
            )
        feedback = owner_version.review_feedback
        scores = {}
        if feedback is not None:
            scores = {
                "evidence_grounding": feedback.evidence_grounding_score,
                "falsifiability": feedback.falsifiability_score,
                "reproducibility": feedback.reproducibility_score,
                "reference_reliability": feedback.reference_reliability_score,
            }
        issues = [
            IssueProjection(
                issue_id=issue.issue_id,
                severity="unavailable",
                summary=issue.description,
                closure_status=issue.status,
                required_revision=(
                    issue.description
                    if issue.category == "required_revision"
                    else None
                ),
                category=issue.category,
                opened_in_version=issue.opened_in_version,
                closed_in_version=issue.closed_in_version,
                resolution_note=issue.resolution_note,
            )
            for issue in owner_version.issue_closures
        ]
        items.append(
            Version(
                version_id=owner_version.version_id,
                ordinal=owner_version.version_number,
                parent_version_id=owner_version.parent_version_id,
                revision_iteration=owner_version.revision_iteration,
                reviewer_issues=issues,
                scores=scores,
                availability="partial",
            )
        )
    return VersionListResponse(job_id=job_id, items=items, availability="partial")


def _canonical_feedback_version_id(run_id: str, version_id: str) -> str:
    """Normalize the documented short vN label to T03's canonical run:vN."""
    normalized = version_id.strip()
    if normalized.startswith("v") and normalized[1:].isdigit():
        return f"{run_id}:{normalized}"
    return normalized


@router.post(
    "/jobs/{job_id}/feedback",
    response_model=FeedbackReceipt,
    status_code=202,
    responses={
        202: _documented_response(
            "反馈已持久化，等待 T03/T02 决策与版本闭环",
            {
                "feedback_id": "feedback-7f4a",
                "job_id": "job-123",
                "target_version_id": "run-123:v1",
                "status": "submitted",
                "decision_reason": None,
                "resulting_version_id": None,
                "correlation_id": "judge-demo-001",
            },
        ),
        **_ERROR_RESPONSES,
    },
    summary="通过 T03 冻结服务提交人工反馈",
)
def create_feedback(
    job_id: str,
    payload: FeedbackCreateRequest,
    request: Request,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=256,
    ),
) -> FeedbackReceipt:
    """Persist feedback only; decisions and resulting versions remain owner-owned."""
    record = _get_job(request, job_id)
    run_id = _upstream_run_id(record)
    try:
        submitted = _feedback_submit_port(request).submit(
            job_id=job_id,
            run_id=run_id,
            question_id=record.question_id,
            target_version_id=_canonical_feedback_version_id(
                run_id,
                payload.target_version_id,
            ),
            feedback=payload.feedback,
            actor_id=principal(request).actor_id,
            correlation_id=correlation_id(request),
            idempotency_key=idempotency_key,
        )
    except OwnerPortFailure as exc:
        _raise_owner_port_failure(exc)
    return FeedbackReceipt(
        feedback_id=submitted.feedback_id,
        job_id=job_id,
        target_version_id=submitted.target_version_id,
        status="submitted",
        decision_reason=None,
        resulting_version_id=None,
        correlation_id=submitted.correlation_id,
    )


@router.get(
    "/jobs/{job_id}/feedback/{feedback_id}",
    response_model=ErrorResponse,
    status_code=503,
    responses=_UPSTREAM_UNAVAILABLE_RESPONSES,
    summary="查询人工反馈决策（契约冻结）",
)
def get_feedback(job_id: str, feedback_id: str, request: Request):
    del feedback_id
    _get_job(request, job_id)
    _upstream_unavailable("T03 FeedbackRecord/FeedbackDecision")
