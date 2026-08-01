"""Stable public API for controlled local execution."""

from .registry import EntrypointRegistry
from .runner import LocalProcessRunner

__all__ = ["EntrypointRegistry", "LocalProcessRunner"]
