"""Typed HTTP client for the T08 API v1 frontend boundary.

This module intentionally has no filesystem or in-process pipeline fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx


@dataclass
class APIClientError(RuntimeError):
    status_code: int
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class B4APIClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url must be nonblank")
        if not api_key:
            raise ValueError("api_key must be configured")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    @staticmethod
    def _segment(value: str) -> str:
        return quote(str(value), safe="")

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise APIClientError(
                504,
                "API_TIMEOUT",
                "API 请求超时。",
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise APIClientError(
                503,
                "API_UNREACHABLE",
                "API 暂不可达。",
                retryable=True,
            ) from exc
        if response.is_success:
            return response
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        raise APIClientError(
            status_code=response.status_code,
            code=str(payload.get("code") or "HTTP_ERROR"),
            message=str(payload.get("message") or "API 请求失败。"),
            details=(payload.get("details") if isinstance(payload.get("details"), dict) else {}),
            correlation_id=str(payload.get("correlation_id") or ""),
            retryable=bool(payload.get("retryable", False)),
        )

    def _json(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        payload = self._request(method, path, **kwargs).json()
        if not isinstance(payload, dict):
            raise APIClientError(502, "INVALID_API_RESPONSE", "API 返回的结构无效。")
        return payload

    def questions(self, **filters: Any) -> dict[str, Any]:
        params = {key: value for key, value in filters.items() if value not in (None, "")}
        return self._json("GET", "/api/v1/questions", params=params)

    def create_job(
        self,
        *,
        question_id: str,
        mode: str,
        options: dict[str, bool],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._json(
            "POST",
            "/api/v1/jobs",
            headers={"Idempotency-Key": idempotency_key},
            json={"question_id": question_id, "mode": mode, "options": options},
        )

    def jobs(self, *, limit: int = 20) -> dict[str, Any]:
        return self._json("GET", "/api/v1/jobs", params={"limit": limit})

    def job(self, job_id: str) -> dict[str, Any]:
        return self._json("GET", f"/api/v1/jobs/{self._segment(job_id)}")

    def evidence(self, job_id: str) -> dict[str, Any]:
        return self._json("GET", f"/api/v1/jobs/{self._segment(job_id)}/evidence")

    def versions(self, job_id: str) -> dict[str, Any]:
        return self._json("GET", f"/api/v1/jobs/{self._segment(job_id)}/versions")

    def version_diff(
        self,
        job_id: str,
        *,
        from_version_id: str,
        to_version_id: str,
    ) -> dict[str, Any]:
        return self._json(
            "GET",
            f"/api/v1/jobs/{self._segment(job_id)}/versions/diff",
            params={
                "from_version_id": from_version_id,
                "to_version_id": to_version_id,
            },
        )

    def submit_feedback(
        self,
        job_id: str,
        *,
        target_version_id: str,
        feedback: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._json(
            "POST",
            f"/api/v1/jobs/{self._segment(job_id)}/feedback",
            headers={"Idempotency-Key": idempotency_key},
            json={"target_version_id": target_version_id, "feedback": feedback},
        )

    def feedback(self, job_id: str, feedback_id: str) -> dict[str, Any]:
        return self._json(
            "GET",
            f"/api/v1/jobs/{self._segment(job_id)}/feedback/{self._segment(feedback_id)}",
        )

    def report(self, job_id: str) -> dict[str, Any]:
        return self._json("GET", f"/api/v1/jobs/{self._segment(job_id)}/report")

    def artifacts(self, job_id: str) -> dict[str, Any]:
        return self._json("GET", f"/api/v1/jobs/{self._segment(job_id)}/artifacts")

    def create_export(
        self,
        job_id: str,
        *,
        formats: list[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._json(
            "POST",
            f"/api/v1/jobs/{self._segment(job_id)}/exports",
            headers={"Idempotency-Key": idempotency_key},
            json={"formats": formats},
        )

    def download(self, job_id: str, artifact_id: str) -> bytes:
        return self._request(
            "GET",
            f"/api/v1/jobs/{self._segment(job_id)}/artifacts/"
            f"{self._segment(artifact_id)}/download",
            headers={"Accept": "*/*"},
        ).content
