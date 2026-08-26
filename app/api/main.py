"""
app.api.main —— FastAPI 应用入口。

通过 create_app() 组装应用并挂载路由；模块级 app 变量供 uvicorn 启动：
    uvicorn app.api.main:app --reload --port 8000
"""

from __future__ import annotations

import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.artifact_registry import SQLiteArtifactRegistry
from app.api.auth import AuthPolicy, FixedWindowRateLimiter, HashedAPIKeyAuth
from app.api.errors import (
    APIError,
    api_error_handler,
    error_response,
    http_error_handler,
    validation_error_handler,
)
from app.api.job_queue import InProcessJobQueue, JobRunner, PipelineJobRunner
from app.api.job_store import JobStore, SQLiteJobStore
from app.api.preview_catalog import ensure_preview_catalog
from app.api.owner_composition import (
    ComposedOwnerContractAdapter,
    FeedbackSubmitPort,
    MultimodalReadPort,
    T03FeedbackSubmitAdapter,
    T06MultimodalReadAdapter,
)
from app.api.routes import _questions_path, router
from app.api.upstream import OwnerContractReadPort
from app.api.v1 import router as v1_router
from app.export.canonical import (
    CanonicalReportSource,
    UnavailableCanonicalReportSource,
)
from app.export.service import ExportService
from app.feedback import SQLiteFeedbackStore
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

# 项目版本，用于 OpenAPI 文档展示。
from app import __version__


_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
logger = get_logger("api.main")


def create_app(
    *,
    job_store: JobStore | None = None,
    job_runner: JobRunner | None = None,
    queue_capacity: int = 100,
    worker_count: int = 1,
    upstream_read_port: OwnerContractReadPort | None = None,
    auth_policy: AuthPolicy | None = None,
    rate_limiter: FixedWindowRateLimiter | None = None,
    artifact_registry: SQLiteArtifactRegistry | None = None,
    canonical_report_source: CanonicalReportSource | None = None,
    artifact_root: str | Path | None = None,
    feedback_submit_port: FeedbackSubmitPort | None = None,
    multimodal_read_port: MultimodalReadPort | None = None,
) -> FastAPI:
    """
    应用工厂：初始化日志、创建 FastAPI 实例并挂载路由与 CORS。

    返回：
        组装完成的 FastAPI 应用实例。
    """
    # 依据配置初始化统一日志（含 API Key 脱敏过滤器）。
    settings = get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        export_root = Path(
            os.getenv("SAGE_TEST_EXPORT_DIR") or settings.export_dir
        )
        store = job_store or SQLiteJobStore(
            export_root / ".api-state" / "jobs.sqlite3"
        )
        store.initialize()
        default_artifact_files = Path(artifact_root or export_root / ".api-artifacts")
        registry = artifact_registry or SQLiteArtifactRegistry(
            export_root / ".api-state" / "artifacts.sqlite3",
            root=default_artifact_files,
        )
        registry.initialize()
        artifact_files = registry.root
        job_queue = InProcessJobQueue(
            store,
            job_runner or PipelineJobRunner(),
            capacity=queue_capacity,
            worker_count=worker_count,
        )
        ensure_preview_catalog()
        application.state.job_store = store
        application.state.job_queue = job_queue
        application.state.upstream_read_port = (
            upstream_read_port or ComposedOwnerContractAdapter(_questions_path())
        )
        application.state.auth_policy = (
            auth_policy or HashedAPIKeyAuth.from_environment()
        )
        application.state.rate_limiter = rate_limiter or FixedWindowRateLimiter(
            limit=180, window_seconds=60
        )
        application.state.artifact_registry = registry
        application.state.feedback_submit_port = (
            feedback_submit_port
            or T03FeedbackSubmitAdapter(
                SQLiteFeedbackStore(
                    export_root / ".api-state" / "feedback.sqlite3"
                )
            )
        )
        application.state.multimodal_read_port = (
            multimodal_read_port or T06MultimodalReadAdapter()
        )
        application.state.export_service = ExportService(
            registry=registry,
            source=canonical_report_source or UnavailableCanonicalReportSource(),
            root=artifact_files,
        )
        job_queue.start()
        try:
            yield
        finally:
            job_queue.stop()

    # 创建应用并声明基础元信息。
    application = FastAPI(
        title="SAGE125-AI-Scientist",
        description="面向赛道 A『科学假设生成与研究计划设计』的 AI Scientist 原型 API。",
        version=__version__,
        lifespan=lifespan,
    )
    # 仅允许显式配置的本地 Streamlit origin，避免把本地 API 暴露给任意网页。
    allowed_origins = [x.strip() for x in settings.cors_allow_origins.split(",") if x.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.add_exception_handler(APIError, api_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    from fastapi import HTTPException

    application.add_exception_handler(HTTPException, http_error_handler)

    @application.middleware("http")
    async def reject_oversized_upload_request(request: Request, call_next):
        """在 multipart 解析前按 Content-Length 拒绝明显超限的上传请求。"""
        raw_length = request.headers.get("content-length", "")
        if (
            request.url.path.startswith("/api/v1")
            and request.method.upper() in {"POST", "PUT", "PATCH"}
        ):
            hard_limit = 64 * 1024
            if raw_length.isdigit() and int(raw_length) > hard_limit:
                return error_response(
                    request,
                    APIError(
                        status_code=413,
                        code="REQUEST_BODY_TOO_LARGE",
                        message="API 请求体超过 64 KiB 上限。",
                        details={"max_bytes": hard_limit},
                        retryable=False,
                    ),
                )
            body = await request.body()
            if len(body) > hard_limit:
                return error_response(
                    request,
                    APIError(
                        status_code=413,
                        code="REQUEST_BODY_TOO_LARGE",
                        message="API 请求体超过 64 KiB 上限。",
                        details={"max_bytes": hard_limit},
                        retryable=False,
                    ),
                )
        if request.url.path == "/ingest" and request.method.upper() == "POST":
            if raw_length.isdigit():
                # 为 multipart 边界和每个文件头预留 1 MiB；文献内容本身仍由 LibraryManager
                # 精确执行单文件/批次上限。
                hard_limit = settings.library_max_batch_mb * 1024 * 1024 + 1024 * 1024
                if int(raw_length) > hard_limit:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "status": "failed",
                            "message": f"上传请求超过 {settings.library_max_batch_mb} MB 批次上限。",
                        },
                    )
        return await call_next(request)

    # 最后注册，使 correlation middleware 位于其它 HTTP middleware 外层，
    # 包括 multipart 解析前直接返回的 413。
    @application.middleware("http")
    async def propagate_correlation_id(request: Request, call_next):
        raw = request.headers.get("X-Correlation-ID", "").strip()
        if raw and not _CORRELATION_ID.fullmatch(raw):
            request.state.correlation_id = str(uuid.uuid4())
            if request.url.path.startswith("/api/v1"):
                return error_response(
                    request,
                    APIError(
                        status_code=400,
                        code="INVALID_CORRELATION_ID",
                        message="X-Correlation-ID 格式无效。",
                    ),
                )
            raw = ""
        request.state.correlation_id = raw or str(uuid.uuid4())
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001
            if not request.url.path.startswith("/api/v1"):
                raise
            logger.error(
                "v1_unhandled_error correlation_id=%s error_type=%s",
                request.state.correlation_id,
                type(exc).__name__,
            )
            return error_response(
                request,
                APIError(
                    status_code=500,
                    code="INTERNAL_ERROR",
                    message="服务发生未预期错误。",
                    retryable=False,
                ),
            )
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response

    # 挂载业务路由。
    application.include_router(router)
    application.include_router(v1_router)
    return application


# 模块级应用实例：uvicorn 的启动目标。
app = create_app()
