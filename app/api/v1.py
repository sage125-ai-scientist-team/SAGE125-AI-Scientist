"""版本化 API v1 路由。

Wave A 实际接通 Job/Status；Artifact、Version、Feedback 仅冻结外部契约，
在上游公开契约可用前明确返回 unavailable。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Header, Query, Request

from app.api.contracts import (
    ArtifactListResponse,
    ErrorResponse,
    FeedbackCreateRequest,
    FeedbackReceipt,
    JobAccepted,
    JobCreateRequest,
    JobError,
    JobLinks,
    JobListResponse,
    JobStatus,
    JobStatusResponse,
    VersionDiff,
    VersionListResponse,
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
_UNAVAILABLE_LIST_EXAMPLE = {
    "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
    "items": [],
    "availability": "unavailable",
}
_VERSION_DIFF_EXAMPLE = {
    "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
    "from_version_id": "v1",
    "to_version_id": "v2",
    "changes": [],
    "issue_changes": [],
    "score_delta": {},
    "stop_reason": None,
    "availability": "unavailable",
}
_FEEDBACK_EXAMPLE = {
    "feedback_id": "feedback-unavailable",
    "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
    "target_version_id": "v1",
    "status": "unavailable",
    "decision_reason": "T03 公开契约尚未接入。",
    "resulting_version_id": None,
    "correlation_id": "judge-demo-001",
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

    if not reused:
        try:
            _queue(request).submit(record.job_id)
        except QueueCapacityError:
            store.transition(
                record.job_id,
                JobStatus.FAILED,
                stage="queue_rejected",
                actor="api",
                source="queue",
                error_code="QUEUE_CAPACITY_EXCEEDED",
                error_message="任务队列已满，请稍后重试。",
                retryable=True,
            )
            raise APIError(
                status_code=503,
                code="QUEUE_CAPACITY_EXCEEDED",
                message="任务队列已满，请稍后重试。",
                details={"job_id": record.job_id},
                retryable=True,
            ) from None

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
    response_model=ArtifactListResponse,
    responses={
        200: _documented_response("任务产物列表", _UNAVAILABLE_LIST_EXAMPLE),
        **_ERROR_RESPONSES,
    },
    summary="列出任务产物（契约冻结）",
)
def list_artifacts(job_id: str, request: Request):
    _get_job(request, job_id)
    _upstream_unavailable("T05 ArtifactManifest")


@router.get(
    "/jobs/{job_id}/versions/diff",
    response_model=VersionDiff,
    responses={
        200: _documented_response("版本差异", _VERSION_DIFF_EXAMPLE),
        **_ERROR_RESPONSES,
    },
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
    response_model=VersionListResponse,
    responses={
        200: _documented_response("任务版本列表", _UNAVAILABLE_LIST_EXAMPLE),
        **_ERROR_RESPONSES,
    },
    summary="列出任务版本（契约冻结）",
)
def list_versions(job_id: str, request: Request):
    _get_job(request, job_id)
    _upstream_unavailable("T02 PlanVersion/IssueClosure")


@router.post(
    "/jobs/{job_id}/feedback",
    response_model=FeedbackReceipt,
    status_code=202,
    responses={
        202: _documented_response("反馈已接收", _FEEDBACK_EXAMPLE),
        **_ERROR_RESPONSES,
    },
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
    response_model=FeedbackReceipt,
    responses={
        200: _documented_response("反馈决策", _FEEDBACK_EXAMPLE),
        **_ERROR_RESPONSES,
    },
    summary="查询人工反馈决策（契约冻结）",
)
def get_feedback(job_id: str, feedback_id: str, request: Request):
    del feedback_id
    _get_job(request, job_id)
    _upstream_unavailable("T03 FeedbackRecord/FeedbackDecision")
