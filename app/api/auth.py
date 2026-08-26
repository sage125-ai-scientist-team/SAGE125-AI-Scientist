"""Server-side API-key authentication and bounded fixed-window rate limiting."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Mapping, Protocol

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from app.api.errors import APIError


@dataclass(frozen=True)
class APIPrincipal:
    actor_id: str


class AuthPolicy(Protocol):
    def authenticate(self, api_key: str | None) -> APIPrincipal: ...


class HashedAPIKeyAuth:
    """Keep only SHA-256 token digests in memory and compare in constant time."""

    #: 仅在 APP_ENV=local|preview 或 SAGE_API_OPEN_ACCESS=1 时启用的放行 actor。
    #: 未配置 SAGE_API_KEYS_JSON 的默认/CI 环境必须 fail-closed。
    _OPEN_ACCESS_ACTOR = "local-open-access"

    def __init__(self, actor_tokens: Mapping[str, str], *, open_access: bool = False) -> None:
        digests: dict[str, str] = {}
        for actor_id, token in actor_tokens.items():
            actor = str(actor_id).strip()
            secret = str(token)
            if not actor or len(secret) < 12:
                raise ValueError("API actors must be nonblank and keys at least 12 characters")
            digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
            if digest in digests:
                raise ValueError("API keys must be unique")
            digests[digest] = actor
        self._actors_by_digest = digests
        self._open_access = open_access

    @classmethod
    def from_environment(cls) -> "HashedAPIKeyAuth":
        raw = os.getenv("SAGE_API_KEYS_JSON", "").strip()
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("SAGE_API_KEYS_JSON must be a JSON object") from exc
            if not isinstance(payload, dict):
                raise ValueError("SAGE_API_KEYS_JSON must map actor IDs to API keys")
            return cls({str(actor): str(token) for actor, token in payload.items()})
        app_env = os.getenv("APP_ENV", "").strip().lower()
        open_flag = os.getenv("SAGE_API_OPEN_ACCESS", "").strip().lower() in {"1", "true", "yes"}
        # 仅本地/预览显式开放；未配置 key 的默认与 CI 必须 fail-closed。
        if open_flag or app_env in {"local", "preview"}:
            return cls({}, open_access=True)
        return cls({}, open_access=False)

    def authenticate(self, api_key: str | None) -> APIPrincipal:
        if self._open_access:
            # 本地开放模式：任意 key（含空）均放行，统一记为同一 actor。
            return APIPrincipal(actor_id=self._OPEN_ACCESS_ACTOR)
        if not self._actors_by_digest:
            raise APIError(
                status_code=503,
                code="AUTH_NOT_CONFIGURED",
                message="API 鉴权尚未配置。",
                details={"configuration": "SAGE_API_KEYS_JSON"},
                retryable=False,
            )
        if not api_key:
            raise APIError(
                status_code=401,
                code="AUTHENTICATION_REQUIRED",
                message="需要有效的 API key。",
                retryable=False,
                headers={"WWW-Authenticate": "ApiKey"},
            )
        candidate = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        actor_id = None
        for digest, actor in self._actors_by_digest.items():
            if hmac.compare_digest(candidate, digest):
                actor_id = actor
        if actor_id is None:
            raise APIError(
                status_code=401,
                code="INVALID_API_KEY",
                message="API key 无效。",
                retryable=False,
                headers={"WWW-Authenticate": "ApiKey"},
            )
        return APIPrincipal(actor_id=actor_id)


class FixedWindowRateLimiter:
    """Small bounded in-process limiter suitable for the existing runtime surface."""

    def __init__(self, *, limit: int = 60, window_seconds: int = 60) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("rate limit and window must be positive")
        self.limit = int(limit)
        self.window_seconds = int(window_seconds)
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    def check(self, actor_id: str) -> None:
        now = int(time.monotonic())
        window = now // self.window_seconds
        with self._lock:
            stored_window, count = self._windows.get(actor_id, (window, 0))
            if stored_window != window:
                stored_window, count = window, 0
            count += 1
            self._windows[actor_id] = (stored_window, count)
            if len(self._windows) > 10_000:
                self._windows = {
                    key: value
                    for key, value in self._windows.items()
                    if value[0] == window
                }
        if count > self.limit:
            raise APIError(
                status_code=429,
                code="RATE_LIMIT_EXCEEDED",
                message="请求频率超过限制，请稍后重试。",
                details={
                    "limit": self.limit,
                    "window_seconds": self.window_seconds,
                },
                retryable=True,
                headers={"Retry-After": str(self.window_seconds)},
            )


_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
# 进度轮询只读 Job 状态，不得占满写操作（创建任务）的窗口。
_JOB_PROGRESS_READ = re.compile(r"^/api/v1/jobs(?:/[^/]+(?:/events)?)?$")


def _is_job_progress_read(request: Request) -> bool:
    return request.method == "GET" and bool(_JOB_PROGRESS_READ.match(request.url.path))


async def authenticate_and_rate_limit(
    request: Request,
    api_key: str | None = Security(_API_KEY_HEADER),
) -> APIPrincipal:
    policy: AuthPolicy | None = getattr(request.app.state, "auth_policy", None)
    if policy is None:
        raise APIError(
            status_code=503,
            code="AUTH_NOT_CONFIGURED",
            message="API 鉴权尚未配置。",
            retryable=False,
        )
    principal = policy.authenticate(api_key)
    limiter: FixedWindowRateLimiter | None = getattr(
        request.app.state, "rate_limiter", None
    )
    if limiter is not None and not _is_job_progress_read(request):
        limiter.check(principal.actor_id)
    request.state.principal = principal
    return principal


def principal(request: Request) -> APIPrincipal:
    value = getattr(request.state, "principal", None)
    if not isinstance(value, APIPrincipal):
        raise APIError(
            status_code=401,
            code="AUTHENTICATION_REQUIRED",
            message="需要有效的 API key。",
            retryable=False,
        )
    return value
