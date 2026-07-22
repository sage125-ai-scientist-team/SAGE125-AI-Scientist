"""Per-run execution mode without mutating process-wide environment state.

The environment variable remains a backwards-compatible default for CLI/tests,
while API and Streamlit runs use a ContextVar so concurrent mock/real requests
cannot switch each other midway through a run.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_mock_override: ContextVar[bool | None] = ContextVar("sage125_mock_mode", default=None)


def is_mock_mode(explicit: bool | None = None) -> bool:
    """Resolve mock mode: explicit argument, run context, then legacy env var."""
    if explicit is not None:
        return bool(explicit)
    contextual = _mock_override.get()
    if contextual is not None:
        return contextual
    return os.getenv("MOCK_LLM", "").strip().lower() in {"1", "true", "yes"}


@contextmanager
def execution_mode(mock: bool) -> Iterator[None]:
    """Temporarily bind mock/real mode to the current execution context."""
    token = _mock_override.set(bool(mock))
    try:
        yield
    finally:
        _mock_override.reset(token)

