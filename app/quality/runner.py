"""Deterministic, fail-closed execution of T03 quality gates."""

from __future__ import annotations

from collections.abc import Iterable

from app.contracts.validation import (
    GateFinding,
    GateResult,
    Severity,
    ValidationContext,
)
from app.quality.service import QualityGate


class DefaultQualityGateRunner:
    """Run a fixed gate sequence and convert gate failures into P0/P1 results.

    The runner intentionally does not execute gates concurrently.  Stable order is
    part of the validator's audit surface, and a broken gate must not prevent the
    remaining gates from reporting their findings.
    """

    def __init__(self, gates: Iterable[QualityGate] | None = None) -> None:
        if gates is None:
            # Import lazily to keep the port module independent and avoid a module
            # cycle between the default builder and this runner.
            from app.quality.gates import build_default_quality_gates

            gates = build_default_quality_gates()

        ordered = tuple(gates)
        gate_ids: list[str] = []
        for gate in ordered:
            gate_id = getattr(gate, "gate_id", None)
            if not isinstance(gate_id, str) or not gate_id.strip():
                raise ValueError("quality gate_id must be a non-blank string")
            if gate_id != gate_id.strip():
                raise ValueError("quality gate_id must be canonical")
            gate_ids.append(gate_id)
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("quality gate_id values must be unique")
        self._gates = ordered

    @property
    def gates(self) -> tuple[QualityGate, ...]:
        """Return the immutable gate sequence used by this runner."""

        return self._gates

    def run(self, context: ValidationContext) -> list[GateResult]:
        """Evaluate every gate in order; exceptions become blocking results."""

        results: list[GateResult] = []
        for gate in self._gates:
            try:
                result = gate.evaluate(context)
                if not isinstance(result, GateResult):
                    raise TypeError("quality gate did not return GateResult")
                if result.gate_id != gate.gate_id:
                    raise ValueError("quality gate returned a different gate_id")
            except Exception:
                # Do not expose exception text: gate inputs can include untrusted
                # feedback and artifact content.  The stable code is sufficient for
                # operators to correlate with private application logs.
                severity = _failure_severity(getattr(gate, "severity", None))
                message = "Quality gate execution failed closed."
                result = GateResult(
                    gate_id=gate.gate_id,
                    passed=False,
                    severity=severity,
                    findings=(
                        GateFinding(
                            code="GATE_EXECUTION_ERROR",
                            message=message,
                            severity=severity,
                            closure_status="open",
                            path=f"quality.{gate.gate_id}",
                            source_ids=(context.validation_id,),
                        ),
                    ),
                    errors=(message,),
                    score=0.0,
                )
            results.append(result)
        return results


def _failure_severity(value: object) -> Severity:
    """Failures of advisory gates are still release-blocking (fail closed)."""

    if value is Severity.P0 or value == Severity.P0:
        return Severity.P0
    return Severity.P1


__all__ = ["DefaultQualityGateRunner"]
