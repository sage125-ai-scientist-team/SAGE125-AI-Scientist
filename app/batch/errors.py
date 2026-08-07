"""Stable T07 runner errors."""

from __future__ import annotations

import re


_SAFE_DIAGNOSTIC_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class BatchRunnerError(RuntimeError):
    """A batch boundary failure with a stable machine-readable code."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        http_status: int | None = None,
        stage: str | None = None,
        exception_type: str | None = None,
    ) -> None:
        normalized_code = error_code.strip()
        normalized_message = message.strip()
        if not normalized_code:
            raise ValueError("error_code must not be empty")
        if not normalized_message:
            raise ValueError("message must not be empty")
        if http_status is not None and (
            type(http_status) is not int or not 100 <= http_status <= 599
        ):
            raise ValueError("http_status must be a valid HTTP status or None")
        for field_name, value in (
            ("stage", stage),
            ("exception_type", exception_type),
        ):
            if value is not None and not _SAFE_DIAGNOSTIC_TOKEN.fullmatch(value):
                raise ValueError(f"{field_name} must be a safe diagnostic token")
        self.error_code = normalized_code
        self.http_status = http_status
        self.stage = stage
        self.exception_type = exception_type
        super().__init__(normalized_message)
