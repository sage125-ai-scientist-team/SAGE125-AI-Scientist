"""Stable T07 runner errors."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


_SAFE_DIAGNOSTIC_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_SAFE_DIAGNOSTIC_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SAFE_EVIDENCE_DETAIL_KEYS = {
    "validation_code",
    "card_index",
    "hypothesis_index",
    "evidence_id",
    "field",
}


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
        call_audits: tuple[Any, ...] = (),
        diagnostic_details: Mapping[str, str | int] | None = None,
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
        self.call_audits = call_audits
        self.diagnostic_details = _safe_diagnostic_details(diagnostic_details)
        super().__init__(normalized_message)


def _safe_diagnostic_details(
    details: Mapping[str, str | int] | None,
) -> dict[str, str | int]:
    """Accept only bounded structural evidence-validation metadata."""

    if details is None:
        return {}
    normalized: dict[str, str | int] = {}
    for key, value in details.items():
        if key not in _SAFE_EVIDENCE_DETAIL_KEYS:
            raise ValueError("diagnostic detail key is not allowlisted")
        if key in {"card_index", "hypothesis_index"}:
            if type(value) is not int or value < 0:
                raise ValueError(f"{key} must be a non-negative integer")
        elif not isinstance(value, str) or not _SAFE_DIAGNOSTIC_ID.fullmatch(value):
            raise ValueError(f"{key} must be a safe diagnostic identifier")
        normalized[key] = value
    return normalized
