"""Application port for complete-context validation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.contracts.validation import ValidationContext, ValidationReport


@runtime_checkable
class ValidationService(Protocol):
    """Validate all artifacts and return a fail-closed aggregate report."""

    def validate(self, context: ValidationContext) -> ValidationReport:
        """Evaluate the frozen context without mutating upstream artifacts."""
        ...
