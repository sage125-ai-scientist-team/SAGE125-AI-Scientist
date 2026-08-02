"""Fail-closed T01/T03 adapter and sole WB5 formal-completion decision."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal

from app.batch.actual_call_audit import (
    ActualCallAudit,
    validate_actual_call_audit,
)
from app.batch.delivery_index import DeliveryIndex, validate_delivery_index
from app.batch.errors import BatchRunnerError
from app.batch.output_validation import ArtifactManifest
from app.contracts.batch import REQUIRED_ARTIFACTS
from app.contracts.validation import (
    GateFinding,
    GateResult,
    Severity,
    ValidationContext,
    ValidationReport,
)


CALL_AUDIT_ARTIFACT: Final[str] = "llm_call_audit.json"
CompletionStatus = Literal["gates_pending", "completed"]


@dataclass(frozen=True, slots=True)
class CompletionGateIssue:
    code: str
    message: str
    severity: Severity = Severity.P1
    closure_status: str = "open"

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("completion issue code and message are required")

    @property
    def is_blocking(self) -> bool:
        return self.closure_status == "open" and self.severity.is_blocking


@dataclass(frozen=True, slots=True)
class CompletionGateInput:
    batch_id: str
    question_id: str
    question: str
    domain: str
    run_id: str
    version_id: str
    source_hash: str
    input_hash: str
    research_plan: Mapping[str, Any]
    evidence_cards: Sequence[Mapping[str, Any]]
    agent_trace: Sequence[Mapping[str, Any]]
    execution_metadata: Mapping[str, Any]
    question_item: Mapping[str, Any]
    evidence_bundle: Any
    claims: Sequence[Any]
    artifact_manifest: ArtifactManifest
    delivery_index: DeliveryIndex
    call_audit: ActualCallAudit | None
    source_kind: str
    source_provenance_verified: bool
    frozen_question_verified: bool
    budgets_verified: bool
    created_at: datetime
    open_issues: tuple[CompletionGateIssue, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CompletionGateResult:
    status: CompletionStatus
    completed: bool
    conditions: Mapping[str, bool]
    issues: tuple[CompletionGateIssue, ...]
    gate_results: tuple[GateResult, ...]
    validation_report: ValidationReport | None

    @property
    def error_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)


T01Runner = Callable[[ValidationContext, Any, Sequence[Any]], GateResult]
T03Runner = Callable[[ValidationContext], Sequence[GateResult]]


def build_actual_validation_context(value: CompletionGateInput) -> ValidationContext:
    """Rebuild T03 context from real artifacts and require actual=true twice."""

    plan_actual = value.research_plan.get("actual_execution")
    metadata_actual = value.execution_metadata.get("actual_execution")
    if plan_actual is not True or metadata_actual is not True:
        raise ValueError(
            "actual completion requires research_plan.actual_execution and "
            "execution_metadata.actual_execution to both be true"
        )
    payload = {
        "validation_id": f"validation:{value.run_id}:{value.question_id}",
        "run_id": value.run_id,
        "version_id": value.version_id,
        "research_plan": dict(value.research_plan),
        "evidence_cards": [dict(card) for card in value.evidence_cards],
        "agent_trace": [dict(event) for event in value.agent_trace],
        "execution_metadata": dict(value.execution_metadata),
        "question_item": dict(value.question_item),
    }
    return ValidationContext.model_validate(payload)


def _failed_gate(gate_id: str, code: str, message: str) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        passed=False,
        severity=Severity.P1,
        findings=(
            GateFinding(
                code=code,
                message=message,
                severity=Severity.P1,
                closure_status="open",
            ),
        ),
        errors=(message,),
        score=0.0,
    )


def run_t01_evidence_precheck(
    context: ValidationContext,
    evidence_bundle: Any,
    claims: Sequence[Any],
) -> GateResult:
    """Invoke only T01's frozen public bridge; absence becomes a blocking gate."""

    try:
        module = importlib.import_module("app.evidence")
        precheck = getattr(module, "precheck_bundle_for_validation")
        result = precheck(
            bundle=evidence_bundle,
            claims=claims,
            context=context,
        )
        raw_gate = getattr(result, "gate")
        if isinstance(raw_gate, GateResult):
            return raw_gate
        if isinstance(raw_gate, Mapping):
            return GateResult.from_legacy("t01-evidence-precheck", raw_gate)
        raise TypeError("T01 precheck result has no GateResult")
    except Exception as exc:  # T01 may not exist on this integration head.
        return _failed_gate(
            "t01-evidence-precheck",
            "T01_INTERFACE_UNAVAILABLE",
            f"T01 evidence precheck unavailable: {type(exc).__name__}",
        )


def run_t03_quality_gates(context: ValidationContext) -> tuple[GateResult, ...]:
    """Run T03 quality gates and convert every legacy result without loss."""

    try:
        module = importlib.import_module("app.workflow.quality_gates")
        run_all = getattr(module, "run_all_quality_gates")
        payload = context.model_dump(mode="json")
        raw = run_all(
            payload["research_plan"],
            payload["evidence_cards"],
            payload["agent_trace"],
        )
        raw_gates = raw.get("gates") if isinstance(raw, Mapping) else None
        if not isinstance(raw_gates, Mapping) or not raw_gates:
            raise TypeError("T03 returned no gate mapping")
        return tuple(
            GateResult.from_legacy(str(gate_id), gate_payload)
            for gate_id, gate_payload in raw_gates.items()
        )
    except Exception as exc:
        return (
            _failed_gate(
                "t03-quality-gates",
                "T03_INTERFACE_UNAVAILABLE",
                f"T03 quality gates unavailable: {type(exc).__name__}",
            ),
        )


def _local_gate(issues: Sequence[CompletionGateIssue]) -> GateResult:
    blocking = tuple(issue for issue in issues if issue.is_blocking)
    if not blocking:
        return GateResult(
            gate_id="t07-wb5-local-completion",
            passed=True,
            severity=Severity.P3,
            score=1.0,
        )
    findings = tuple(
        GateFinding(
            code=issue.code,
            message=issue.message,
            severity=issue.severity,
            closure_status="open",
        )
        for issue in blocking
    )
    most_severe = min(
        (finding.severity for finding in findings),
        key=lambda item: item.rank,
    )
    return GateResult(
        gate_id="t07-wb5-local-completion",
        passed=False,
        severity=most_severe,
        findings=findings,
        errors=tuple(issue.message for issue in blocking),
        score=0.0,
    )


def aggregate_completion_report(
    context: ValidationContext,
    gate_results: Sequence[GateResult],
    issues: Sequence[CompletionGateIssue],
    *,
    created_at: datetime,
) -> ValidationReport:
    """Create the immutable T03 report; blocking findings can never pass."""

    all_gates = (_local_gate(issues), *tuple(gate_results))
    passed = not any(issue.is_blocking for issue in issues) and all(
        gate.passed and not gate.is_blocking for gate in gate_results
    )
    return ValidationReport.from_context(
        context,
        report_id=f"report:{context.validation_id}",
        validation_status="passed" if passed else "blocked",
        recommended_plan_status="validated" if passed else "draft",
        gate_results=all_gates,
        created_at=created_at,
    )


def _manifest_hash(manifest: ArtifactManifest) -> str:
    payload = {
        "batch_id": manifest.batch_id,
        "question_id": manifest.question_id,
        "output_contract_version": manifest.output_contract_version,
        "validation_status": manifest.validation_status,
        "artifacts": [
            artifact.to_dict()
            for artifact in sorted(manifest.artifacts, key=lambda item: item.name)
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _add_issue(
    issues: list[CompletionGateIssue],
    code: str,
    message: str,
) -> None:
    issues.append(CompletionGateIssue(code, message, Severity.P1))


def evaluate_question_completion(
    value: CompletionGateInput,
    *,
    t01_runner: T01Runner = run_t01_evidence_precheck,
    t03_runner: T03Runner = run_t03_quality_gates,
) -> CompletionGateResult:
    """Evaluate all 20 frozen conditions; no caller can supply completed."""

    issues: list[CompletionGateIssue] = []
    conditions: dict[str, bool] = {}

    conditions["01_authoritative_source"] = (
        value.source_kind == "production" and value.source_provenance_verified
    )
    if not conditions["01_authoritative_source"]:
        _add_issue(
            issues,
            "SOURCE_PROVENANCE_UNVERIFIED",
            "formal completion requires verified production provenance",
        )
    conditions["02_frozen_question_mapping"] = value.frozen_question_verified
    if not conditions["02_frozen_question_mapping"]:
        _add_issue(
            issues,
            "FROZEN_QUESTION_MISMATCH",
            "question text/domain/canonical hash does not match the freeze",
        )

    item = value.question_item
    identity_checks = (
        ("03_batch_id", item.get("batch_id") == value.batch_id, "BATCH_ID_MISMATCH"),
        (
            "04_question_id",
            item.get("id") == value.question_id
            and value.research_plan.get("question_id") == value.question_id,
            "QUESTION_ID_MISMATCH",
        ),
        (
            "05_question_text",
            item.get("question") == value.question
            and value.research_plan.get("input_question") == value.question,
            "QUESTION_TEXT_MISMATCH",
        ),
        ("06_domain", item.get("domain") == value.domain, "DOMAIN_MISMATCH"),
        ("07_run_id", item.get("run_id") == value.run_id, "RUN_ID_MISMATCH"),
        (
            "08_version_id",
            item.get("version_id") == value.version_id,
            "VERSION_ID_MISMATCH",
        ),
        (
            "09_source_hash",
            item.get("source_hash") == value.source_hash,
            "SOURCE_HASH_MISMATCH",
        ),
        (
            "10_input_hash",
            item.get("input_hash") == value.input_hash,
            "INPUT_HASH_MISMATCH",
        ),
    )
    for condition_id, passed, code in identity_checks:
        conditions[condition_id] = passed
        if not passed:
            _add_issue(issues, code, f"completion identity failed: {condition_id}")

    context: ValidationContext | None = None
    try:
        context = build_actual_validation_context(value)
    except Exception as exc:
        conditions["11_actual_validation_context"] = False
        _add_issue(
            issues,
            "ACTUAL_CONTEXT_INVALID",
            f"real ValidationContext rejected artifacts: {type(exc).__name__}",
        )
    else:
        conditions["11_actual_validation_context"] = True

    if context is None:
        t01_gate = _failed_gate(
            "t01-evidence-precheck",
            "ACTUAL_CONTEXT_INVALID",
            "T01 cannot run without a valid actual ValidationContext",
        )
        t03_gates = (
            _failed_gate(
                "t03-quality-gates",
                "ACTUAL_CONTEXT_INVALID",
                "T03 cannot run without a valid actual ValidationContext",
            ),
        )
    else:
        t01_gate = t01_runner(context, value.evidence_bundle, value.claims)
        t03_gates = tuple(t03_runner(context))
    conditions["12_t01_evidence_precheck"] = (
        t01_gate.passed and not t01_gate.is_blocking
    )
    if not conditions["12_t01_evidence_precheck"]:
        _add_issue(issues, "T01_GATE_FAILED", "T01 evidence precheck did not pass")
    conditions["13_t03_quality_gates"] = bool(t03_gates) and all(
        gate.passed and not gate.is_blocking for gate in t03_gates
    )
    if not conditions["13_t03_quality_gates"]:
        _add_issue(issues, "T03_GATE_FAILED", "one or more T03 gates did not pass")

    conditions["14_no_open_p0_p1"] = not any(
        issue.is_blocking for issue in value.open_issues
    )
    if not conditions["14_no_open_p0_p1"]:
        _add_issue(issues, "OPEN_P0_P1", "an unresolved P0/P1 issue remains")
    issues.extend(issue for issue in value.open_issues if issue.is_blocking)

    manifest_names = {artifact.name for artifact in value.artifact_manifest.artifacts}
    conditions["15_five_required_artifacts"] = set(REQUIRED_ARTIFACTS).issubset(
        manifest_names
    )
    if not conditions["15_five_required_artifacts"]:
        _add_issue(
            issues,
            "REQUIRED_ARTIFACT_MISSING",
            "one or more of the five minimum artifacts is absent",
        )
    conditions["16_call_audit_registered"] = (
        value.call_audit is not None and CALL_AUDIT_ARTIFACT in manifest_names
    )
    if not conditions["16_call_audit_registered"]:
        _add_issue(
            issues,
            "LLM_CALL_AUDIT_MISSING",
            "llm_call_audit.json must be present in the artifact manifest",
        )

    audit_valid = False
    if value.call_audit is not None:
        try:
            validate_actual_call_audit(value.call_audit)
        except BatchRunnerError as exc:
            _add_issue(issues, exc.error_code, str(exc))
        else:
            audit_valid = True
    conditions["17_call_audit_truth_and_cost"] = audit_valid

    manifest_valid = (
        value.artifact_manifest.batch_id == value.batch_id
        and value.artifact_manifest.question_id == value.question_id
        and value.artifact_manifest.validation_status == "passed"
        and value.artifact_manifest.manifest_sha256
        == _manifest_hash(value.artifact_manifest)
    )
    if audit_valid:
        assert value.call_audit is not None
        audit_record = next(
            (
                artifact
                for artifact in value.artifact_manifest.artifacts
                if artifact.name == CALL_AUDIT_ARTIFACT
            ),
            None,
        )
        expected_audit_hash = hashlib.sha256(
            value.call_audit.to_json().encode("utf-8")
        ).hexdigest()
        manifest_valid = (
            manifest_valid
            and audit_record is not None
            and audit_record.sha256 == expected_audit_hash
        )
    conditions["18_artifact_manifest_integrity"] = manifest_valid
    if not manifest_valid:
        _add_issue(
            issues,
            "ARTIFACT_MANIFEST_HASH_MISMATCH",
            "artifact manifest identity, checksum, or call-audit hash is invalid",
        )

    delivery_valid = True
    try:
        validate_delivery_index(value.delivery_index)
    except BatchRunnerError as exc:
        delivery_valid = False
        _add_issue(issues, exc.error_code, str(exc))
    records = [
        record
        for record in value.delivery_index.records
        if record.question_id == value.question_id
    ]
    if len(records) != 1 or value.delivery_index.batch_id != value.batch_id:
        delivery_valid = False
    else:
        delivery_artifacts = {
            artifact.name: artifact.sha256 for artifact in records[0].artifacts
        }
        manifest_artifacts = {
            artifact.name: artifact.sha256
            for artifact in value.artifact_manifest.artifacts
        }
        delivery_valid = delivery_valid and delivery_artifacts == manifest_artifacts
    conditions["19_delivery_index_integrity"] = delivery_valid
    if not delivery_valid and "DELIVERY_CHECKSUM_MISMATCH" not in {
        issue.code for issue in issues
    }:
        _add_issue(
            issues,
            "DELIVERY_ARTIFACT_HASH_MISMATCH",
            "delivery index does not bind the exact manifest artifacts",
        )

    conditions["20_question_and_batch_budgets"] = value.budgets_verified
    if not conditions["20_question_and_batch_budgets"]:
        _add_issue(
            issues,
            "BUDGET_EXHAUSTED",
            "question and batch budgets must both remain within the freeze",
        )

    unique: list[CompletionGateIssue] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (issue.code, issue.message)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    all_gates = (t01_gate, *t03_gates)
    report = (
        None
        if context is None
        else aggregate_completion_report(
            context,
            all_gates,
            unique,
            created_at=value.created_at,
        )
    )
    completed = (
        len(conditions) == 20
        and all(conditions.values())
        and report is not None
        and report.passed
    )
    persisted_gates = (
        report.gate_results
        if report is not None
        else (_local_gate(unique), *all_gates)
    )
    return CompletionGateResult(
        status="completed" if completed else "gates_pending",
        completed=completed,
        conditions=conditions,
        issues=tuple(unique),
        gate_results=tuple(persisted_gates),
        validation_report=report,
    )


def save_completion_gate_result(
    result: CompletionGateResult,
    question_root: str | Path,
) -> tuple[Path, Path, Path]:
    """Persist the exact report, gates, and 20-condition decision as UTF-8 JSON."""

    if not isinstance(result, CompletionGateResult):
        raise TypeError("result must be CompletionGateResult")
    root = Path(question_root)
    if root.is_symlink():
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "completion-gate output root cannot be a symlink",
        )
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / "validation_report.json"
    gates_path = root / "gate_results.json"
    decision_path = root / "completion_gate.json"
    report_payload = (
        None
        if result.validation_report is None
        else result.validation_report.model_dump(mode="json")
    )
    gates_payload = [gate.model_dump(mode="json") for gate in result.gate_results]
    decision_payload = {
        "status": result.status,
        "completed": result.completed,
        "conditions": dict(result.conditions),
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity.value,
                "closure_status": issue.closure_status,
            }
            for issue in result.issues
        ],
    }
    for path, payload in (
        (report_path, report_payload),
        (gates_path, gates_payload),
        (decision_path, decision_payload),
    ):
        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
    return report_path, gates_path, decision_path
