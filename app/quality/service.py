"""Ports for quality gates that emit the frozen T03 ``GateResult`` shape."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.contracts.validation import (
    GateResult,
    Severity,
    ValidationContext,
)


@runtime_checkable
class QualityGate(Protocol):
    """One deterministic gate evaluated against a complete artifact context."""

    gate_id: str
    severity: Severity

    def evaluate(self, context: ValidationContext) -> GateResult:
        """Evaluate one gate without mutating the supplied context."""
        ...


@runtime_checkable
class QualityGateRunner(Protocol):
    """Aggregate an ordered set of quality gates."""

    def run(self, context: ValidationContext) -> list[GateResult]:
        """Return all gate results in deterministic order."""
        ...
