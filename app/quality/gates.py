"""Production T03 quality gates over the frozen :class:`ValidationContext`.

This module adapts the existing workflow gates without changing their public
dictionary shape.  T03 adds stable finding codes, strict artifact/lineage checks,
and blocking P0/P1 semantics around those legacy checks.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from app.contracts.validation import (
    GateFinding,
    GateResult,
    Severity,
    ValidationContext,
)
from app.workflow import quality_gates as legacy_quality_gates


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_TRACE_TERMINAL_SUCCESS = {"completed", "success", "succeeded"}
_TRACE_ALLOWED_STATUS = {
    "pending",
    "running",
    "completed",
    "success",
    "succeeded",
    "failed",
    "skipped",
}


def _safe_message(value: str) -> str:
    """Bound and flatten a legacy diagnostic before exposing it in a report."""

    flattened = " ".join(value.split())
    return (flattened[:997] + "...") if len(flattened) > 1_000 else flattened


def _result(
    *,
    gate_id: str,
    default_severity: Severity,
    findings: Sequence[GateFinding],
    score: float | None = None,
) -> GateResult:
    ordered = tuple(findings)
    blocking = tuple(item for item in ordered if item.is_blocking)
    advisory = tuple(item for item in ordered if not item.is_blocking)
    if blocking:
        severity = min(
            (default_severity, *(item.severity for item in blocking)),
            key=lambda item: item.rank,
        )
    elif advisory:
        severity = min(
            (item.severity for item in advisory),
            key=lambda item: item.rank,
        )
    else:
        severity = Severity.P3
    return GateResult(
        gate_id=gate_id,
        passed=not blocking,
        severity=severity,
        findings=ordered,
        errors=tuple(item.message for item in blocking),
        warnings=tuple(item.message for item in advisory),
        score=(
            score
            if score is not None
            else (0.0 if blocking else (0.75 if advisory else 1.0))
        ),
    )


def _finding(
    *,
    code: str,
    message: str,
    severity: Severity,
    path: str,
    context: ValidationContext,
    source_ids: Sequence[str] = (),
) -> GateFinding:
    ids = tuple(source_ids) or (context.validation_id,)
    return GateFinding(
        code=code,
        message=message,
        severity=severity,
        closure_status="open",
        path=path,
        source_ids=ids,
    )


@dataclass(frozen=True, slots=True)
class ArtifactPresenceGate:
    """Require all five validator inputs and non-empty collection artifacts."""

    gate_id: str = "artifact-presence"
    severity: Severity = Severity.P1

    def evaluate(self, context: ValidationContext) -> GateResult:
        findings: list[GateFinding] = []
        checks: tuple[tuple[str, object, str], ...] = (
            ("research_plan", context.research_plan, "MISSING_RESEARCH_PLAN"),
            ("evidence_cards", context.evidence_cards, "MISSING_EVIDENCE_CARDS"),
            ("agent_trace", context.agent_trace, "MISSING_AGENT_TRACE"),
            (
                "execution_metadata",
                context.execution_metadata,
                "MISSING_EXECUTION_METADATA",
            ),
            ("question_item", context.question_item, "MISSING_QUESTION_ITEM"),
        )
        for path, artifact, code in checks:
            if not artifact:
                findings.append(
                    _finding(
                        code=code,
                        message=f"Required artifact {path} is empty.",
                        severity=Severity.P1,
                        path=path,
                        context=context,
                    )
                )

        for path, value in (
            ("research_plan.question_id", context.research_plan.get("question_id")),
            (
                "research_plan.input_question",
                context.research_plan.get("input_question"),
            ),
            ("question_item.id", context.question_item.get("id")),
            ("question_item.question", context.question_item.get("question")),
        ):
            if not isinstance(value, str) or not value.strip():
                findings.append(
                    _finding(
                        code="ARTIFACT_IDENTITY_FIELD_INVALID",
                        message="Artifact identity fields must be non-blank strings.",
                        severity=Severity.P1,
                        path=path,
                        context=context,
                    )
                )

        evidence_ids: set[str] = set()
        for index, card in enumerate(context.evidence_cards):
            if not card:
                findings.append(
                    _finding(
                        code="EMPTY_EVIDENCE_CARD",
                        message="Evidence card must not be empty.",
                        severity=Severity.P1,
                        path=f"evidence_cards[{index}]",
                        context=context,
                    )
                )
            evidence_id = card.get("id")
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                findings.append(
                    _finding(
                        code="EVIDENCE_CARD_ID_MISSING",
                        message="Every evidence card requires a non-blank id.",
                        severity=Severity.P1,
                        path=f"evidence_cards[{index}].id",
                        context=context,
                    )
                )
            elif evidence_id in evidence_ids:
                findings.append(
                    _finding(
                        code="EVIDENCE_CARD_ID_DUPLICATE",
                        message="Evidence card ids must be unique.",
                        severity=Severity.P1,
                        path=f"evidence_cards[{index}].id",
                        context=context,
                        source_ids=(evidence_id,),
                    )
                )
            else:
                evidence_ids.add(evidence_id)

        references = context.research_plan.get("references", ())
        reference_sequence = _as_sequence(references)
        if reference_sequence is None:
            findings.append(
                _finding(
                    code="RESEARCH_PLAN_REFERENCES_INVALID",
                    message="Research plan references must be a structured list.",
                    severity=Severity.P1,
                    path="research_plan.references",
                    context=context,
                )
            )
        else:
            for index, reference in enumerate(reference_sequence):
                if (
                    not isinstance(reference, Mapping)
                    or not isinstance(reference.get("id"), str)
                    or not reference.get("id").strip()
                ):
                    findings.append(
                        _finding(
                            code="REFERENCE_ID_MISSING",
                            message="Every research plan reference requires an id.",
                            severity=Severity.P1,
                            path=f"research_plan.references[{index}].id",
                            context=context,
                        )
                    )
        for index, event in enumerate(context.agent_trace):
            if not event:
                findings.append(
                    _finding(
                        code="EMPTY_AGENT_TRACE_EVENT",
                        message="Agent trace event must not be empty.",
                        severity=Severity.P1,
                        path=f"agent_trace[{index}]",
                        context=context,
                    )
                )
        return _result(
            gate_id=self.gate_id,
            default_severity=self.severity,
            findings=findings,
        )


LegacyGateName = Literal[
    "evidence_grounding",
    "results_integrity",
    "research_plan_schema",
    "model_compliance",
    "reference_integrity",
]


@dataclass(frozen=True, slots=True)
class LegacyWorkflowGateAdapter:
    """Convert one existing workflow gate to a strict T03 ``GateResult``."""

    gate_id: str
    legacy_gate: LegacyGateName
    severity: Severity
    error_code: str
    warning_code: str

    def evaluate(self, context: ValidationContext) -> GateResult:
        # model_dump(mode="json") thaws MappingProxy/tuple snapshots while keeping
        # the ValidationContext itself immutable.
        payload = context.model_dump(mode="json")
        plan = payload["research_plan"]
        evidence_cards = payload["evidence_cards"]
        agent_trace = payload["agent_trace"]

        if self.legacy_gate == "evidence_grounding":
            raw = legacy_quality_gates.check_evidence_grounding(
                plan,
                evidence_cards,
            )
        elif self.legacy_gate == "results_integrity":
            raw = legacy_quality_gates.check_results_integrity(plan)
        elif self.legacy_gate == "research_plan_schema":
            raw = legacy_quality_gates.check_research_plan_schema(plan)
        elif self.legacy_gate == "model_compliance":
            raw = legacy_quality_gates.check_model_compliance(agent_trace)
        elif self.legacy_gate == "reference_integrity":
            raw = legacy_quality_gates.check_reference_integrity(
                plan,
                evidence_cards,
            )
        else:  # pragma: no cover - Literal plus frozen defaults make this defensive.
            raise ValueError("unknown legacy workflow gate")

        if not isinstance(raw, Mapping):
            raise TypeError("legacy gate result must be a mapping")
        passed = raw.get("passed")
        errors = raw.get("errors")
        warnings = raw.get("warnings")
        score = raw.get("score")
        if type(passed) is not bool:
            raise ValueError("legacy gate passed must be a boolean")
        if not isinstance(errors, list) or not all(
            isinstance(item, str) and item.strip() for item in errors
        ):
            raise ValueError("legacy gate errors must be non-blank strings")
        if not isinstance(warnings, list) or not all(
            isinstance(item, str) and item.strip() for item in warnings
        ):
            raise ValueError("legacy gate warnings must be non-blank strings")
        if (
            type(score) not in {int, float}
            or not math.isfinite(float(score))
            or not 0.0 <= float(score) <= 1.0
        ):
            raise ValueError("legacy gate score must be between zero and one")
        if passed != (not errors):
            raise ValueError("legacy gate passed flag conflicts with its errors")

        findings: list[GateFinding] = []
        for message in errors:
            findings.append(
                _finding(
                    code=self.error_code,
                    message=_safe_message(message),
                    severity=self.severity,
                    path=f"legacy.{self.legacy_gate}",
                    context=context,
                )
            )
        for message in warnings:
            findings.append(
                _finding(
                    code=self.warning_code,
                    message=_safe_message(message),
                    severity=Severity.P3,
                    path=f"legacy.{self.legacy_gate}",
                    context=context,
                )
            )
        return _result(
            gate_id=self.gate_id,
            default_severity=self.severity,
            findings=findings,
            score=float(score),
        )


@dataclass(frozen=True, slots=True)
class ExecutionTruthGate:
    """Fail closed when an actual-execution claim lacks the T05 proof chain."""

    gate_id: str = "execution-truth"
    severity: Severity = Severity.P0

    def evaluate(self, context: ValidationContext) -> GateResult:
        findings: list[GateFinding] = []
        plan_actual = context.research_plan.get("actual_execution")
        metadata_actual = context.execution_metadata.get("actual_execution")
        if type(plan_actual) is not bool or type(metadata_actual) is not bool:
            findings.append(
                _finding(
                    code="EXECUTION_TRUTH_NOT_BOOLEAN",
                    message="actual_execution must be an explicit boolean.",
                    severity=Severity.P0,
                    path="execution_metadata.actual_execution",
                    context=context,
                )
            )
        elif plan_actual is not metadata_actual:
            findings.append(
                _finding(
                    code="EXECUTION_TRUTH_MISMATCH",
                    message="Plan and execution metadata disagree on actual execution.",
                    severity=Severity.P0,
                    path="execution_metadata.actual_execution",
                    context=context,
                )
            )

        nested = context.execution_metadata.get("execution_result")
        proof: Mapping[str, Any]
        if nested is None:
            proof = context.execution_metadata
        elif isinstance(nested, Mapping):
            proof = nested
        else:
            findings.append(
                _finding(
                    code="EXECUTION_PROOF_INVALID",
                    message="execution_result proof must be a structured object.",
                    severity=Severity.P0,
                    path="execution_metadata.execution_result",
                    context=context,
                )
            )
            proof = {}

        if metadata_actual is False:
            truth_fields = (
                "runner_verified",
                "scientific_result_usable",
                "datasets_validated",
                "artifacts_validated",
                "metrics_validated",
                "provenance_complete",
            )
            if any(proof.get(field) is True for field in truth_fields):
                findings.append(
                    _finding(
                        code="EXECUTION_TRUTH_FLAG_CONFLICT",
                        message="Runner truth flags conflict with actual_execution=false.",
                        severity=Severity.P0,
                        path="execution_metadata",
                        context=context,
                    )
                )

        if metadata_actual is True:
            if not _has_complete_execution_proof(proof):
                findings.append(
                    _finding(
                        code="EXECUTION_PROOF_INCOMPLETE",
                        message=(
                            "actual_execution=true lacks a complete runner-verified "
                            "execution proof chain."
                        ),
                        severity=Severity.P0,
                        path="execution_metadata.execution_result",
                        context=context,
                    )
                )

        return _result(
            gate_id=self.gate_id,
            default_severity=self.severity,
            findings=findings,
        )


def _has_complete_execution_proof(proof: Mapping[str, Any]) -> bool:
    required_true = (
        "actual_execution",
        "runner_verified",
        "datasets_validated",
        "artifacts_validated",
        "metrics_validated",
        "provenance_complete",
        "scientific_result_usable",
        "process_started",
        "process_reaped",
    )
    if any(proof.get(field) is not True for field in required_true):
        return False
    if (
        proof.get("mode") != "actual"
        or proof.get("entrypoint_class") != "scientific"
        or proof.get("status") != "succeeded"
        or type(proof.get("exit_code")) is not int
        or proof.get("exit_code") != 0
        or proof.get("timed_out") is not False
        or proof.get("process_alive_after_cleanup") is not False
        or proof.get("error") is not None
        or proof.get("cleanup_status") not in {"succeeded", "preserved"}
    ):
        return False

    datasets = _as_sequence(proof.get("datasets"))
    artifacts = _as_sequence(proof.get("artifacts"))
    metrics = _as_sequence(proof.get("metrics"))
    if datasets is None or artifacts is None or metrics is None:
        return False
    if not datasets or not artifacts or not metrics:
        return False
    if not all(
        isinstance(item, Mapping) and item.get("validation_status") == "valid"
        for item in artifacts
    ):
        return False
    artifact_ids = {
        item.get("artifact_id")
        for item in artifacts
        if isinstance(item.get("artifact_id"), str) and item.get("artifact_id")
    }
    if len(artifact_ids) != len(artifacts):
        return False
    if not all(
        isinstance(item, Mapping)
        and item.get("source") == "observed"
        and item.get("validation_status") == "valid"
        and item.get("artifact_id") in artifact_ids
        for item in metrics
    ):
        return False
    fingerprint = proof.get("environment_fingerprint")
    return bool(
        isinstance(fingerprint, Mapping)
        and fingerprint.get("git_available") is True
        and fingerprint.get("git_dirty") is False
        and isinstance(fingerprint.get("git_sha"), str)
        and _GIT_SHA_PATTERN.fullmatch(fingerprint["git_sha"])
    )


def _as_sequence(value: object) -> Sequence[Any] | None:
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return value
    return None


@dataclass(frozen=True, slots=True)
class AgentTraceGate:
    """Validate trace completeness, status, uniqueness, and mock truth claims."""

    gate_id: str = "agent-trace"
    severity: Severity = Severity.P1

    def evaluate(self, context: ValidationContext) -> GateResult:
        findings: list[GateFinding] = []
        event_ids: set[str] = set()
        step_indexes: set[int] = set()
        actual_execution = context.execution_metadata.get("actual_execution") is True

        for index, event in enumerate(context.agent_trace):
            path = f"agent_trace[{index}]"
            required = ("event_id", "run_id", "step_index", "agent_name", "model_name", "status")
            missing = tuple(
                field
                for field in required
                if field not in event
                or event.get(field) is None
                or (isinstance(event.get(field), str) and not event.get(field).strip())
            )
            if missing:
                findings.append(
                    _finding(
                        code="AGENT_TRACE_FIELD_MISSING",
                        message="Agent trace event is missing required fields.",
                        severity=Severity.P1,
                        path=path,
                        context=context,
                    )
                )

            event_id = event.get("event_id")
            if isinstance(event_id, str) and event_id.strip():
                if event_id in event_ids:
                    findings.append(
                        _finding(
                            code="AGENT_TRACE_EVENT_ID_DUPLICATE",
                            message="Agent trace event_id values must be unique.",
                            severity=Severity.P1,
                            path=f"{path}.event_id",
                            context=context,
                            source_ids=(event_id,),
                        )
                    )
                event_ids.add(event_id)

            step_index = event.get("step_index")
            if type(step_index) is int and step_index >= 0:
                if step_index in step_indexes:
                    findings.append(
                        _finding(
                            code="AGENT_TRACE_STEP_DUPLICATE",
                            message="Agent trace step_index values must be unique.",
                            severity=Severity.P1,
                            path=f"{path}.step_index",
                            context=context,
                        )
                    )
                step_indexes.add(step_index)
            elif "step_index" in event:
                findings.append(
                    _finding(
                        code="AGENT_TRACE_STEP_INVALID",
                        message="Agent trace step_index must be a non-negative integer.",
                        severity=Severity.P1,
                        path=f"{path}.step_index",
                        context=context,
                    )
                )

            raw_status = event.get("status")
            status = raw_status.strip().casefold() if isinstance(raw_status, str) else ""
            if status and status not in _TRACE_ALLOWED_STATUS:
                findings.append(
                    _finding(
                        code="AGENT_TRACE_STATUS_INVALID",
                        message="Agent trace status is not recognized.",
                        severity=Severity.P1,
                        path=f"{path}.status",
                        context=context,
                    )
                )
            elif status in {"pending", "running", "failed"}:
                findings.append(
                    _finding(
                        code="AGENT_TRACE_NOT_SUCCESSFUL",
                        message="Agent trace contains an incomplete or failed event.",
                        severity=Severity.P1,
                        path=f"{path}.status",
                        context=context,
                    )
                )

            prompt_hash = event.get("prompt_hash")
            if prompt_hash is not None and (
                not isinstance(prompt_hash, str)
                or _SHA256_PATTERN.fullmatch(prompt_hash) is None
            ):
                findings.append(
                    _finding(
                        code="AGENT_TRACE_PROMPT_HASH_INVALID",
                        message="Agent trace prompt_hash must be a canonical SHA-256 value.",
                        severity=Severity.P1,
                        path=f"{path}.prompt_hash",
                        context=context,
                    )
                )

            raw_errors = event.get("errors")
            if raw_errors is not None:
                trace_errors = _as_sequence(raw_errors)
                if trace_errors is None or not all(
                    isinstance(item, str) for item in trace_errors
                ):
                    findings.append(
                        _finding(
                            code="AGENT_TRACE_ERRORS_INVALID",
                            message="Agent trace errors must be a list of strings.",
                            severity=Severity.P1,
                            path=f"{path}.errors",
                            context=context,
                        )
                    )
                elif trace_errors:
                    findings.append(
                        _finding(
                            code="AGENT_TRACE_REPORTED_ERRORS",
                            message="Agent trace event reports execution errors.",
                            severity=Severity.P1,
                            path=f"{path}.errors",
                            context=context,
                        )
                    )
            if "mock" in event and type(event.get("mock")) is not bool:
                findings.append(
                    _finding(
                        code="AGENT_TRACE_MOCK_FLAG_INVALID",
                        message="Agent trace mock flag must be a boolean.",
                        severity=Severity.P1,
                        path=f"{path}.mock",
                        context=context,
                    )
                )
            if actual_execution and (
                event.get("mock") is True
                or (status and status not in _TRACE_TERMINAL_SUCCESS)
            ):
                findings.append(
                    _finding(
                        code="ACTUAL_EXECUTION_HAS_UNTRUSTED_TRACE",
                        message="Actual execution cannot rely on mock or unsuccessful trace events.",
                        severity=Severity.P0,
                        path=path,
                        context=context,
                    )
                )

        return _result(
            gate_id=self.gate_id,
            default_severity=self.severity,
            findings=findings,
        )


@dataclass(frozen=True, slots=True)
class HumanFeedbackPropagationGate:
    """Prove that accepted feedback changed the direct next version audibly."""

    gate_id: str = "human-feedback-propagation"
    severity: Severity = Severity.P1

    def evaluate(self, context: ValidationContext) -> GateResult:
        findings: list[GateFinding] = []
        directive = context.human_feedback
        metadata = _revision_metadata(context.execution_metadata)

        if directive is None:
            if metadata is not None and metadata.get("feedback_id") is not None:
                findings.append(
                    _finding(
                        code="FEEDBACK_DIRECTIVE_MISSING",
                        message="Revision metadata references feedback without a directive.",
                        severity=Severity.P1,
                        path="human_feedback",
                        context=context,
                    )
                )
            return _result(
                gate_id=self.gate_id,
                default_severity=self.severity,
                findings=findings,
            )

        current_number = _version_number(context.version_id)
        source_number = _version_number(directive.target_version_id)
        if source_number + 1 != current_number:
            findings.append(
                _finding(
                    code="FEEDBACK_TARGET_NOT_PREVIOUS_VERSION",
                    message="Human feedback must target the direct previous version.",
                    severity=Severity.P1,
                    path="human_feedback.target_version_id",
                    context=context,
                    source_ids=(directive.feedback_id,),
                )
            )

        if metadata is None:
            findings.append(
                _finding(
                    code="REVISION_METADATA_MISSING",
                    message="Feedback revision metadata is required for audit.",
                    severity=Severity.P1,
                    path="execution_metadata.revision_metadata",
                    context=context,
                    source_ids=(directive.feedback_id,),
                )
            )
            return _result(
                gate_id=self.gate_id,
                default_severity=self.severity,
                findings=findings,
            )

        _compare_revision_identity(
            findings=findings,
            context=context,
            metadata=metadata,
            key="feedback_id",
            expected=directive.feedback_id,
            missing_code="REVISION_FEEDBACK_ID_MISSING",
            mismatch_code="REVISION_FEEDBACK_ID_MISMATCH",
        )
        _compare_revision_identity(
            findings=findings,
            context=context,
            metadata=metadata,
            key="source_version_id",
            expected=directive.target_version_id,
            missing_code="REVISION_SOURCE_VERSION_MISSING",
            mismatch_code="REVISION_SOURCE_VERSION_MISMATCH",
        )

        prompt_fingerprint = _first_present(
            metadata,
            "prompt_fingerprint",
            "prompt_sha256",
            "prompt_hash",
        )
        if prompt_fingerprint is None:
            findings.append(
                _finding(
                    code="REVISION_PROMPT_FINGERPRINT_MISSING",
                    message="Revision prompt fingerprint is required for audit.",
                    severity=Severity.P1,
                    path="execution_metadata.revision_metadata.prompt_fingerprint",
                    context=context,
                    source_ids=(directive.feedback_id,),
                )
            )
        elif not isinstance(prompt_fingerprint, str) or not _SHA256_PATTERN.fullmatch(
            prompt_fingerprint
        ):
            findings.append(
                _finding(
                    code="REVISION_PROMPT_FINGERPRINT_INVALID",
                    message="Revision prompt fingerprint must be a canonical SHA-256 value.",
                    severity=Severity.P1,
                    path="execution_metadata.revision_metadata.prompt_fingerprint",
                    context=context,
                    source_ids=(directive.feedback_id,),
                )
            )

        diff_hash = _first_present(
            metadata,
            "diff_hash",
            "revision_diff_sha256",
            "diff_sha256",
        )
        if diff_hash is None:
            findings.append(
                _finding(
                    code="REVISION_DIFF_HASH_MISSING",
                    message="Revision diff hash is required for audit.",
                    severity=Severity.P1,
                    path="execution_metadata.revision_metadata.diff_hash",
                    context=context,
                    source_ids=(directive.feedback_id,),
                )
            )
        elif not isinstance(diff_hash, str) or not _SHA256_PATTERN.fullmatch(diff_hash):
            findings.append(
                _finding(
                    code="REVISION_DIFF_HASH_INVALID",
                    message="Revision diff hash must be a canonical SHA-256 value.",
                    severity=Severity.P1,
                    path="execution_metadata.revision_metadata.diff_hash",
                    context=context,
                    source_ids=(directive.feedback_id,),
                )
            )

        applied = metadata.get("applied_instructions")
        applied_sequence = _as_sequence(applied)
        if applied_sequence is None or not applied_sequence:
            findings.append(
                _finding(
                    code="REVISION_APPLIED_INSTRUCTIONS_MISSING",
                    message="Applied feedback instructions are required for audit.",
                    severity=Severity.P1,
                    path="execution_metadata.revision_metadata.applied_instructions",
                    context=context,
                    source_ids=(directive.feedback_id,),
                )
            )
        elif (
            not all(isinstance(item, str) and item.strip() for item in applied_sequence)
            or tuple(item.strip() for item in applied_sequence) != directive.instructions
        ):
            findings.append(
                _finding(
                    code="REVISION_APPLIED_INSTRUCTIONS_MISMATCH",
                    message="Applied instructions do not match the accepted feedback directive.",
                    severity=Severity.P1,
                    path="execution_metadata.revision_metadata.applied_instructions",
                    context=context,
                    source_ids=(directive.feedback_id,),
                )
            )

        return _result(
            gate_id=self.gate_id,
            default_severity=self.severity,
            findings=findings,
        )


# A shorter compatibility name for callers that do not need the contract prefix.
FeedbackPropagationGate = HumanFeedbackPropagationGate


def _revision_metadata(
    execution_metadata: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for key in ("revision_metadata", "revision_audit", "feedback_application"):
        candidate = execution_metadata.get(key)
        if candidate is not None:
            if not isinstance(candidate, Mapping):
                return None
            return candidate
    # Transitional callers may place the same frozen fields at the top level.
    if "feedback_id" in execution_metadata:
        return execution_metadata
    return None


def _first_present(metadata: Mapping[str, Any], *keys: str) -> object | None:
    for key in keys:
        if key in metadata:
            return metadata[key]
    return None


def _compare_revision_identity(
    *,
    findings: list[GateFinding],
    context: ValidationContext,
    metadata: Mapping[str, Any],
    key: str,
    expected: str,
    missing_code: str,
    mismatch_code: str,
) -> None:
    value = metadata.get(key)
    path = f"execution_metadata.revision_metadata.{key}"
    if value is None or (isinstance(value, str) and not value.strip()):
        findings.append(
            _finding(
                code=missing_code,
                message=f"Revision metadata {key} is required.",
                severity=Severity.P1,
                path=path,
                context=context,
                source_ids=(context.human_feedback.feedback_id,),
            )
        )
    elif value != expected:
        findings.append(
            _finding(
                code=mismatch_code,
                message=f"Revision metadata {key} does not match the directive.",
                severity=Severity.P1,
                path=path,
                context=context,
                source_ids=(context.human_feedback.feedback_id,),
            )
        )


def _version_number(version_id: str) -> int:
    # ValidationContext has already enforced the canonical ``<run>:vN`` shape.
    return int(version_id.rsplit(":v", 1)[1])


def build_default_quality_gates() -> tuple[object, ...]:
    """Return the canonical, deterministic T03 Wave B gate sequence."""

    return (
        ArtifactPresenceGate(),
        LegacyWorkflowGateAdapter(
            gate_id="evidence_grounding",
            legacy_gate="evidence_grounding",
            severity=Severity.P0,
            error_code="EVIDENCE_GROUNDING_ERROR",
            warning_code="EVIDENCE_GROUNDING_WARNING",
        ),
        LegacyWorkflowGateAdapter(
            gate_id="results_integrity",
            legacy_gate="results_integrity",
            severity=Severity.P0,
            error_code="RESULTS_INTEGRITY_ERROR",
            warning_code="RESULTS_INTEGRITY_WARNING",
        ),
        LegacyWorkflowGateAdapter(
            gate_id="research_plan_schema",
            legacy_gate="research_plan_schema",
            severity=Severity.P1,
            error_code="RESEARCH_PLAN_SCHEMA_ERROR",
            warning_code="RESEARCH_PLAN_SCHEMA_WARNING",
        ),
        LegacyWorkflowGateAdapter(
            gate_id="model_compliance",
            legacy_gate="model_compliance",
            severity=Severity.P1,
            error_code="MODEL_COMPLIANCE_ERROR",
            warning_code="MODEL_COMPLIANCE_WARNING",
        ),
        LegacyWorkflowGateAdapter(
            gate_id="reference_integrity",
            legacy_gate="reference_integrity",
            severity=Severity.P0,
            error_code="REFERENCE_INTEGRITY_ERROR",
            warning_code="REFERENCE_INTEGRITY_WARNING",
        ),
        ExecutionTruthGate(),
        AgentTraceGate(),
        HumanFeedbackPropagationGate(),
    )


def build_default_quality_gate_runner():
    """Build the default runner without making the port import implementations."""

    from app.quality.runner import DefaultQualityGateRunner

    return DefaultQualityGateRunner(build_default_quality_gates())


# Friendly aliases used by integration callers during the Wave B transition.
default_quality_gates = build_default_quality_gates
build_default_runner = build_default_quality_gate_runner


__all__ = [
    "AgentTraceGate",
    "ArtifactPresenceGate",
    "ExecutionTruthGate",
    "FeedbackPropagationGate",
    "HumanFeedbackPropagationGate",
    "LegacyWorkflowGateAdapter",
    "build_default_quality_gate_runner",
    "build_default_quality_gates",
    "build_default_runner",
    "default_quality_gates",
]
