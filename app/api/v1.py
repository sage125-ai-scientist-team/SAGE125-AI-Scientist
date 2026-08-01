"""版本化 API v1 路由。

Wave A 实际接通 Job/Status；Artifact、Version、Feedback 仅冻结外部契约，
在上游公开契约可用前明确返回 unavailable。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Header, Query, Request

from app.api.contracts import (
    ErrorResponse,
    FeedbackCreateRequest,
    JobAccepted,
    JobCreateRequest,
    JobError,
    JobLinks,
    JobListResponse,
    JobStatus,
    JobStatusResponse,
)
from app.api.errors import APIError, correlation_id
from app.api.job_queue import QueueCapacityError
from app.api.job_store import (
    IdempotencyConflict,
    JobNotFound,
    JobRecord,
)


router = APIRouter(prefix="/api/v1", tags=["API v1"])


def _documented_response(description: str, example: dict) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"example": example}},
    }


_ERROR_RESPONSES = {
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

_UPSTREAM_UNAVAILABLE_RESPONSES = {
    status_code: response
    for status_code, response in _ERROR_RESPONSES.items()
    if status_code in {400, 404, 422, 500, 503}
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
    "upstream_run_id": None,
    "error": None,
    "links": {
        "self": "/api/v1/jobs/c4ef4580-e351-4b44-b9a2-19edac5ec977",
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


def _links(job_id: str) -> JobLinks:
    base = f"/api/v1/jobs/{job_id}"
    return JobLinks(
        self=base,
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
        upstream_run_id=record.upstream_run_id,
        error=error,
        links=_links(record.job_id),
    )


def _get_job(request: Request, job_id: str) -> JobRecord:
    try:
        return _store(request).get_job(job_id)
    except JobNotFound:
        raise APIError(
            status_code=404,
            code="JOB_NOT_FOUND",
            message="任务不存在。",
            details={"job_id": job_id},
        ) from None


def _upstream_unavailable(component: str) -> None:
    raise APIError(
        status_code=503,
        code="UPSTREAM_CONTRACT_UNAVAILABLE",
        message=f"{component} 公开契约尚未接入。",
        details={"component": component, "availability": "unavailable"},
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
        )
    except IdempotencyConflict:
        raise APIError(
            status_code=409,
            code="IDEMPOTENCY_CONFLICT",
            message="相同 Idempotency-Key 已用于不同请求。",
        ) from None

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
    "/jobs/{job_id}/artifacts",
    response_model=ErrorResponse,
    status_code=503,
    responses=_UPSTREAM_UNAVAILABLE_RESPONSES,
    summary="列出任务产物（契约冻结）",
)
def list_artifacts(job_id: str, request: Request):
    _get_job(request, job_id)
    _upstream_unavailable("T05 ArtifactManifest")


@router.get(
    "/jobs/{job_id}/versions/diff",
    response_model=ErrorResponse,
    status_code=503,
    responses=_UPSTREAM_UNAVAILABLE_RESPONSES,
    summary="查询版本差异（契约冻结）",
)
def version_diff(
    job_id: str,
    request: Request,
    from_version_id: str = Query(min_length=1, max_length=128),
    to_version_id: str = Query(min_length=1, max_length=128),
):
    _get_job(request, job_id)
    _upstream_unavailable("T02 PlanVersion/IssueClosure")


@router.get(
    "/jobs/{job_id}/versions",
    response_model=ErrorResponse,
    status_code=503,
    responses=_UPSTREAM_UNAVAILABLE_RESPONSES,
    summary="列出任务版本（契约冻结）",
)
def list_versions(job_id: str, request: Request):
    _get_job(request, job_id)
    _upstream_unavailable("T02 PlanVersion/IssueClosure")


@router.post(
    "/jobs/{job_id}/feedback",
    response_model=ErrorResponse,
    status_code=503,
    responses=_UPSTREAM_UNAVAILABLE_RESPONSES,
    summary="提交人工反馈（契约冻结）",
)
def create_feedback(
    job_id: str,
    payload: FeedbackCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        max_length=256,
    ),
):
    del payload, idempotency_key
    _get_job(request, job_id)
    _upstream_unavailable("T03 FeedbackRecord/FeedbackDecision")


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
