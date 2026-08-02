"""Stable T07 runner errors."""

from __future__ import annotations


class BatchRunnerError(RuntimeError):
    """A batch boundary failure with a stable machine-readable code."""

    def __init__(self, error_code: str, message: str) -> None:
        normalized_code = error_code.strip()
        normalized_message = message.strip()
        if not normalized_code:
            raise ValueError("error_code must not be empty")
        if not normalized_message:
            raise ValueError("message must not be empty")
        self.error_code = normalized_code
        super().__init__(normalized_message)
