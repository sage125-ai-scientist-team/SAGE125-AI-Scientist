"""API v1 稳定错误结构与 FastAPI 映射。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.contracts import ErrorResponse
from app.core.logging import mask_text


class APIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable


def correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", ""))


def error_response(request: Request, error: APIError) -> JSONResponse:
    payload = ErrorResponse(
        code=error.code,
        message=error.message,
        details=error.details,
        correlation_id=correlation_id(request),
        retryable=error.retryable,
    )
    return JSONResponse(
        status_code=error.status_code,
        content=payload.model_dump(mode="json"),
        headers={"X-Correlation-ID": payload.correlation_id},
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return error_response(request, exc)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith("/api/v1"):
        return await request_validation_exception_handler(request, exc)
    safe_errors = [
        {
            "type": item.get("type"),
            "loc": list(item.get("loc", ())),
            "msg": mask_text(str(item.get("msg", ""))),
        }
        for item in exc.errors()
    ]
    return error_response(
        request,
        APIError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="请求参数不符合 API 契约。",
            details={"errors": safe_errors},
        ),
    )


async def http_error_handler(request: Request, exc: HTTPException):
    if not request.url.path.startswith("/api/v1"):
        return await http_exception_handler(request, exc)
    return error_response(
        request,
        APIError(
            status_code=exc.status_code,
            code="HTTP_ERROR",
            message=mask_text(str(exc.detail)),
        ),
    )
