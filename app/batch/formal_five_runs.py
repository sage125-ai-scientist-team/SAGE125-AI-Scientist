"""Fail-closed WB5 formal-run orchestration with an injectable executor.

The repository's general pipeline is deliberately not used as the default
executor: it does not yet expose a complete, token-bearing audit hook for every
possible provider boundary.  Production execution therefore stops before a
provider call until a compliant executor is injected.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Final

from app.batch.actual_call_audit import (
    ActualCallAudit,
    BudgetLedger,
    validate_actual_call_audit,
)
from app.batch.checkpoint import read_checkpoint, resume_job, write_checkpoint
from app.batch.completion_gate import (
    CompletionGateInput,
    CompletionGateIssue,
    CompletionGateResult,
    evaluate_question_completion,
)
from app.batch.delivery_index import (
    DeliveryIndex,
    QuestionDeliveryRecord,
    build_delivery_index,
    build_question_delivery_record,
    validate_delivery_index,
)
from app.batch.errors import BatchRunnerError
from app.batch.five_run_preflight import (
    APPROVED_TOKEN_ONLY_FREEZE_ID,
    FROZEN_QUESTION_IDS,
    FrozenFiveRunConfig,
    load_and_map_authoritative_questions,
    load_frozen_run_config,
    verify_authoritative_sources,
    verify_frozen_code_files,
    verify_frozen_question_text,
    verify_t01_gate_availability,
    verify_t03_gate_availability,
)
from app.batch.output_layout import (
    QuestionOutputPaths,
    build_question_output_paths,
    create_question_output_directory,
)
from app.batch.output_validation import (
    ArtifactFileRecord,
    ArtifactManifest,
    ArtifactValidationIssue,
    ArtifactValidationResult,
    build_artifact_manifest,
    validate_required_artifacts,
)
from app.contracts.batch import (
    REQUIRED_ARTIFACTS,
    STANDARD_OUTPUT_FIELDS,
    BatchBudgetV2,
    BatchJobV2,
    CheckpointRecordV2,
    JobStatus,
    ModelRoute,
    OutputContract,
    ResultKind,
    ResumePolicy,
    RetryPolicy,
)


AUTHORIZATION_TEXT: Final[str] = "FIVE_REAL_RUNS_AUTHORIZED=true"
FROZEN_EXECUTION_ORDER: Final[tuple[str, ...]] = FROZEN_QUESTION_IDS
FORMAL_MANIFEST_VERSION: Final[str] = "t07.wb5-formal-run-manifest.v1"
FORMAL_OUTPUT_CONTRACT_VERSION: Final[str] = "t07.wb5-formal-output.v1"
EXPECTED_FREEZE_ID: Final[str] = APPROVED_TOKEN_ONLY_FREEZE_ID
EXPECTED_PROVIDER: Final[str] = "bailian"
EXPECTED_PRIMARY_MODEL: Final[str] = "qwen3.6-flash"
EXPECTED_MODELS: Final[Mapping[str, str]] = {
    "fast": "qwen3.6-flash",
    "balanced": "qwen3.7-plus",
    "strong": "qwen3.7-max",
    "deep_research": "qwen-deep-research",
    "embedding": "text-embedding-v4",
    "rerank": "qwen3-rerank",
}
QUESTION_TOKEN_LIMIT: Final[int] = 200_000
BATCH_TOKEN_LIMIT: Final[int] = 1_000_000
MAX_OUTPUT_TOKENS: Final[int] = 8_192


@dataclass(frozen=True, slots=True)
class ProviderPreflightAuditReference:
    path: str
    sha256: str
    size_bytes: int
    audit: ActualCallAudit

    def to_manifest_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class FormalRunRequest:
    repo_root: Path
    config_path: Path
    run_root: Path
    authorization_reference: str
    provider_preflight_audit: Path
    question_ids: tuple[str, ...]
    execute: bool = False
    resume: bool = False
    provider_preflight_audit_sha256: str | None = None
    provider_configured: bool = True
    mock_environment: bool = False


@dataclass(frozen=True, slots=True)
class FormalExecutionContext:
    question_id: str
    run_id: str
    batch_root: Path
    question_root: Path
    paths: QuestionOutputPaths
    question: Mapping[str, Any]
    job: BatchJobV2


@dataclass(frozen=True, slots=True)
class FormalQuestionExecution:
    report_pdf: bytes | None
    report_markdown: str | None
    standard_fields: Mapping[str, Any]
    research_plan: Mapping[str, Any]
    evidence_cards: tuple[Mapping[str, Any], ...]
    agent_trace: tuple[Mapping[str, Any], ...]
    execution_metadata: Mapping[str, Any]
    evidence_bundle: Any
    claims: tuple[Any, ...]
    call_audits: tuple[ActualCallAudit, ...]
    duration_seconds: float
    open_issues: tuple[CompletionGateIssue, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FormalQuestionReceipt:
    question_id: str
    run_id: str
    status: str
    completed: bool
    error_codes: tuple[str, ...]
    tokens_used: int
    retries: int
    artifacts: tuple[ArtifactFileRecord, ...] = field(default_factory=tuple)
    resumed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "run_id": self.run_id,
            "status": self.status,
            "completed": self.completed,
            "error_codes": list(self.error_codes),
            "tokens_used": self.tokens_used,
            "retries": self.retries,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "resumed": self.resumed,
        }


@dataclass(frozen=True, slots=True)
class FormalRunReceipt:
    status: str
    batch_root: str
    code_sha: str
    questions: tuple[FormalQuestionReceipt, ...]
    provider_calls: int
    progress: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "batch_root": self.batch_root,
            "code_sha": self.code_sha,
            "questions": [question.to_dict() for question in self.questions],
            "provider_calls": self.provider_calls,
            "five_real_runs_progress": self.progress,
        }


FormalExecutor = Callable[[FormalExecutionContext], FormalQuestionExecution]
CompletionEvaluator = Callable[[CompletionGateInput], CompletionGateResult]


def validate_provider_preflight_audit(
    path: str | Path,
    repo_root: str | Path,
    *,
    expected_sha256: str | None = None,
) -> ProviderPreflightAuditReference:
    """Validate one external, secret-free successful provider audit."""

    candidate = Path(path)
    repo = Path(repo_root).resolve(strict=False)
    resolved = candidate.resolve(strict=False)
    if _is_within(resolved, repo):
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_PATH_INVALID",
            "provider preflight audit must be outside the repository",
        )
    if candidate.is_symlink() or not candidate.is_file():
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_MISSING",
            "provider preflight audit is missing or not a regular file",
        )
    raw = candidate.read_bytes()
    if not raw:
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_INVALID",
            "provider preflight audit is empty",
        )
    if raw.startswith(b"\xef\xbb\xbf"):
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_INVALID",
            "provider preflight audit must be UTF-8 without BOM",
        )
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_HASH_MISMATCH",
            "provider preflight audit hash changed after registration",
        )
    try:
        text = raw.decode("utf-8")
        payload = json.loads(text)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_INVALID",
            "provider preflight audit is not UTF-8 JSON",
        ) from exc
    if not isinstance(payload, Mapping):
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_INVALID",
            "provider preflight audit must be a JSON object",
        )
    status = payload.get("status")
    if status is not None and status not in {
        "success",
        "succeeded",
        "PROVIDER_PREFLIGHT_PASSED",
    }:
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_INVALID",
            "provider preflight audit does not record success",
        )
    for field_name in ("input_tokens", "output_tokens", "total_tokens"):
        if type(payload.get(field_name)) is not int:
            raise BatchRunnerError(
                "PROVIDER_PREFLIGHT_AUDIT_INVALID",
                "provider preflight token usage is incomplete",
            )
    try:
        audit = ActualCallAudit.from_mapping(payload)
        validate_actual_call_audit(
            audit,
            budget_mode="token_only",
        )
    except BatchRunnerError:
        raise
    except Exception as exc:
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_INVALID",
            "provider preflight audit semantics are invalid",
        ) from exc
    if audit.provider != EXPECTED_PROVIDER or audit.model != EXPECTED_PRIMARY_MODEL:
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_IDENTITY_MISMATCH",
            "provider preflight audit does not match the frozen provider/model",
        )
    return ProviderPreflightAuditReference(
        path=str(resolved),
        sha256=digest,
        size_bytes=len(raw),
        audit=audit,
    )


def run_formal_five_runs(
    request: FormalRunRequest,
    *,
    executor: FormalExecutor | None = None,
    completion_evaluator: CompletionEvaluator = evaluate_question_completion,
) -> FormalRunReceipt:
    """Validate, execute in frozen order, and stop at the first non-completion."""

    repo_root = Path(request.repo_root).resolve(strict=False)
    authorization = request.authorization_reference.strip()
    if not authorization:
        raise BatchRunnerError(
            "FIVE_REAL_RUNS_AUTHORIZATION_MISSING",
            "a captain PR authorization reference is required",
        )
    run_root = _validate_run_root(request.run_root, repo_root)
    question_ids = _validate_question_ids(request.question_ids)
    config = _validate_frozen_config(request.config_path, repo_root)
    if not request.provider_configured:
        raise BatchRunnerError(
            "PROVIDER_CONFIGURATION_MISSING",
            "provider configuration boolean is false",
        )
    if request.execute and request.mock_environment:
        raise BatchRunnerError(
            "FORMAL_MOCK_FORBIDDEN",
            "formal execution refuses MOCK_LLM",
        )
    audit_reference = validate_provider_preflight_audit(
        request.provider_preflight_audit,
        repo_root,
        expected_sha256=request.provider_preflight_audit_sha256,
    )
    mapped = load_and_map_authoritative_questions(config, repo_root)
    code_sha = _git_sha(repo_root)
    batch_root = run_root / config.freeze_id
    existing_manifest = _load_existing_manifest(batch_root, request.resume)
    if existing_manifest is not None:
        _validate_resume_manifest(existing_manifest, authorization, audit_reference)
    else:
        batch_root.mkdir(parents=True, exist_ok=False)
    manifest = existing_manifest or _base_manifest(
        config,
        authorization,
        audit_reference,
        code_sha,
        question_ids,
        execute=request.execute,
    )
    if not request.execute:
        manifest["status"] = "dry_run"
        _write_json(batch_root / "manifest.json", manifest)
        return FormalRunReceipt(
            status="dry_run",
            batch_root=str(batch_root),
            code_sha=code_sha,
            questions=(),
            provider_calls=0,
            progress="0/5",
        )

    ledger = _build_ledger(config)
    receipts: list[FormalQuestionReceipt] = []
    delivery_records: list[QuestionDeliveryRecord] = []
    provider_calls = int(manifest.get("provider_calls", 0))
    for question_id in question_ids:
        frozen = next(item for item in config.questions if item.question_id == question_id)
        run_id = _new_run_id(question_id)
        base_job = _build_job(config, frozen, run_id)
        if request.resume:
            resumed = _resume_completed_question(
                batch_root,
                base_job,
                question_id,
            )
            if resumed is not None:
                receipts.append(resumed)
                delivery = DeliveryIndex.from_json(
                    (batch_root / "delivery_index.json").read_text(encoding="utf-8")
                )
                delivery_records.extend(delivery.records)
                continue
        paths = build_question_output_paths(batch_root, question_id)
        create_question_output_directory(paths)
        context = FormalExecutionContext(
            question_id=question_id,
            run_id=run_id,
            batch_root=batch_root,
            question_root=paths.question_root,
            paths=paths,
            question=mapped[question_id],
            job=base_job,
        )
        try:
            if executor is None:
                raise BatchRunnerError(
                    "CALL_AUDIT_HOOK_UNAVAILABLE",
                    "no formal executor with complete per-call audit hooks is installed",
                )
            execution = executor(context)
            if not isinstance(execution, FormalQuestionExecution):
                raise BatchRunnerError(
                    "FORMAL_EXECUTOR_RESULT_INVALID",
                    "formal executor returned an invalid result",
                )
            if len(execution.call_audits) != 1:
                raise BatchRunnerError(
                    "CALL_AUDIT_INCOMPLETE",
                    "formal executor must prove every provider call",
                )
            for audit in execution.call_audits:
                ledger.record_call(question_id, audit)
            provider_calls += len(execution.call_audits)
            job = _job_for_execution(
                base_job,
                execution,
                ledger.question_tokens(question_id),
            )
            validation, artifact_manifest = _materialize_and_validate(
                context,
                job,
                execution,
            )
            delivery_record = build_question_delivery_record(
                job,
                config.source_kind,
                validation,
                artifact_manifest,
                output_contract_version=FORMAL_OUTPUT_CONTRACT_VERSION,
                input_tokens=sum(audit.input_tokens for audit in execution.call_audits),
                output_tokens=sum(audit.output_tokens for audit in execution.call_audits),
                duration_seconds=execution.duration_seconds,
                budget_policy=config.budget_policy,
                estimated_cost_usd=None,
                settled_cost_usd=None,
            )
            provisional_index = build_delivery_index(
                config.freeze_id,
                (*delivery_records, delivery_record),
            )
            completion_input = _completion_input(
                config,
                frozen,
                context,
                job,
                execution,
                artifact_manifest,
                provisional_index,
                ledger,
            )
            completion = completion_evaluator(completion_input)
            if not isinstance(completion, CompletionGateResult):
                raise BatchRunnerError(
                    "COMPLETION_DECISION_INVALID",
                    "completion evaluator returned an invalid decision",
                )
            _write_completion_outputs(paths.question_root, completion)
            final_job = _job_after_completion(job, completion)
            write_checkpoint(
                paths.question_root / "checkpoint.json",
                CheckpointRecordV2.from_job(final_job),
            )
            if completion.completed:
                delivery_record = build_question_delivery_record(
                    final_job,
                    config.source_kind,
                    validation,
                    artifact_manifest,
                    output_contract_version=FORMAL_OUTPUT_CONTRACT_VERSION,
                    input_tokens=sum(
                        audit.input_tokens for audit in execution.call_audits
                    ),
                    output_tokens=sum(
                        audit.output_tokens for audit in execution.call_audits
                    ),
                    duration_seconds=execution.duration_seconds,
                    budget_policy=config.budget_policy,
                    estimated_cost_usd=None,
                    settled_cost_usd=None,
                )
            delivery_records.append(delivery_record)
            index = build_delivery_index(config.freeze_id, delivery_records)
            _write_json(batch_root / "delivery_index.json", index.to_dict())
            receipt = FormalQuestionReceipt(
                question_id=question_id,
                run_id=run_id,
                status=completion.status,
                completed=completion.completed,
                error_codes=completion.error_codes,
                tokens_used=ledger.question_tokens(question_id),
                retries=ledger.question_retry_tokens(question_id),
                artifacts=artifact_manifest.artifacts,
            )
        except Exception as exc:
            receipt, failed_record = _persist_question_failure(
                config,
                context,
                base_job,
                exc,
                ledger,
            )
            delivery_records.append(failed_record)
            index = build_delivery_index(config.freeze_id, delivery_records)
            _write_json(batch_root / "delivery_index.json", index.to_dict())
        receipts.append(receipt)
        manifest["questions"] = [item.to_dict() for item in receipts]
        manifest["status"] = receipt.status
        manifest["provider_calls"] = provider_calls
        _write_json(batch_root / "manifest.json", manifest)
        if not receipt.completed:
            break

    completed = sum(item.completed for item in receipts)
    status = (
        "completed"
        if receipts and all(item.completed for item in receipts)
        else receipts[-1].status if receipts else "failed"
    )
    return FormalRunReceipt(
        status=status,
        batch_root=str(batch_root),
        code_sha=code_sha,
        questions=tuple(receipts),
        provider_calls=provider_calls,
        progress=f"{completed}/5",
    )


def _validate_run_root(run_root: Path, repo_root: Path) -> Path:
    candidate = Path(run_root).resolve(strict=False)
    if _is_within(candidate, repo_root) or _is_within(repo_root, candidate):
        raise BatchRunnerError(
            "FORMAL_RUN_ROOT_INVALID",
            "formal run root must not overlap the repository",
        )
    current = candidate
    while not current.exists() and current != current.parent:
        current = current.parent
    if current.is_symlink():
        raise BatchRunnerError(
            "FORMAL_RUN_ROOT_INVALID",
            "formal run root cannot traverse a symlink",
        )
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _validate_question_ids(question_ids: Sequence[str]) -> tuple[str, ...]:
    selected = tuple(question_ids)
    if not selected or len(selected) != len(set(selected)):
        raise BatchRunnerError(
            "FROZEN_QUESTION_ID_INVALID",
            "formal execution requires unique frozen question IDs",
        )
    unknown = [item for item in selected if item not in FROZEN_EXECUTION_ORDER]
    if unknown:
        raise BatchRunnerError(
            "FROZEN_QUESTION_ID_INVALID",
            "formal execution contains a non-frozen question ID",
        )
    ordered = tuple(item for item in FROZEN_EXECUTION_ORDER if item in selected)
    if selected != ordered:
        raise BatchRunnerError(
            "FROZEN_QUESTION_ORDER_INVALID",
            "formal questions must follow the frozen order",
        )
    return selected


def _validate_frozen_config(path: Path, repo_root: Path) -> FrozenFiveRunConfig:
    config = load_frozen_run_config(path)
    budgets = config.budgets
    per_question = budgets.get("per_question")
    batch = budgets.get("batch")
    exact = (
        config.freeze_id == EXPECTED_FREEZE_ID
        and config.provider_name == EXPECTED_PROVIDER
        and dict(config.models) == dict(EXPECTED_MODELS)
        and isinstance(per_question, Mapping)
        and per_question.get("token_limit") == QUESTION_TOKEN_LIMIT
        and isinstance(batch, Mapping)
        and batch.get("token_limit") == BATCH_TOKEN_LIMIT
        and budgets.get("max_output_tokens_per_call") == MAX_OUTPUT_TOKENS
        and config.price_snapshot_required is False
        and config.cost_accounting_required is False
    )
    if not exact:
        raise BatchRunnerError(
            "FROZEN_CONFIG_INVALID",
            "formal execution requires the exact approved WB5 v2 freeze",
        )
    source = verify_authoritative_sources(config, repo_root)
    if not source.passed:
        first = source.issues[0]
        raise BatchRunnerError(first.code, first.message)
    mapped = load_and_map_authoritative_questions(config, repo_root)
    question_issues = verify_frozen_question_text(config, mapped)
    if question_issues:
        first = question_issues[0]
        raise BatchRunnerError(first.code, first.message)
    code_issues = verify_frozen_code_files(config, repo_root)
    if code_issues:
        first = code_issues[0]
        raise BatchRunnerError(first.code, first.message)
    t01 = verify_t01_gate_availability(config.approved_t01_commit, repo_root)
    if not t01.available:
        raise BatchRunnerError(t01.code, t01.message)
    t03 = verify_t03_gate_availability()
    if not t03.available:
        raise BatchRunnerError(t03.code, t03.message)
    return config


def _build_ledger(config: FrozenFiveRunConfig) -> BudgetLedger:
    return BudgetLedger(
        per_question_token_limit=QUESTION_TOKEN_LIMIT,
        per_question_cost_limit_usd=None,
        batch_token_limit=BATCH_TOKEN_LIMIT,
        batch_cost_limit_usd=None,
        max_output_tokens_per_call=MAX_OUTPUT_TOKENS,
        budget_mode=config.budget_mode,
    )


def _build_job(config, frozen, run_id: str) -> BatchJobV2:
    question_id = frozen.question_id
    input_hash = str(frozen.canonical_input_hash)
    return BatchJobV2(
        batch_id=config.freeze_id,
        question_id=question_id,
        source_hash=config.production_question_source.sha256,
        input_hash=input_hash,
        workspace=f"{config.freeze_id}/{question_id}/workspace",
        context_id=f"ctx:{config.freeze_id}:{question_id}:{run_id}",
        cache_namespace=f"cache:{config.freeze_id}:{question_id}:{run_id}",
        status=JobStatus.GATES_PENDING,
        result_kind=ResultKind.ACTUAL,
        mock=False,
        attempt=1,
        retry_policy=RetryPolicy(max_attempts=3),
        budget=BatchBudgetV2(
            mode=config.budget_mode,
            token_limit=QUESTION_TOKEN_LIMIT,
            tokens_used=0,
            max_output_tokens_per_call=MAX_OUTPUT_TOKENS,
        ),
        model_route=ModelRoute(
            route_id=config.route_id,
            provider=config.provider_name,
            model=EXPECTED_PRIMARY_MODEL,
            model_version=config.model_version,
            prompt_version=config.prompt_version,
            prompt_hash=config.prompt_file.sha256,
        ),
        output_contract=OutputContract(),
        freeze_id=config.freeze_id,
        budget_policy=config.budget_policy,
    )


def _job_for_execution(
    base_job: BatchJobV2,
    execution: FormalQuestionExecution,
    tokens_used: int,
) -> BatchJobV2:
    fields = dict(execution.standard_fields)
    if set(fields) != set(STANDARD_OUTPUT_FIELDS):
        raise BatchRunnerError(
            "OUTPUT_CONTRACT_INCOMPLETE",
            "formal executor did not return exactly the standard fields",
        )
    artifacts = {
        name: f"{base_job.batch_id}/{base_job.question_id}/{name}"
        for name in REQUIRED_ARTIFACTS
    }
    payload = base_job.model_dump()
    payload["budget"]["tokens_used"] = tokens_used
    payload["output_contract"] = OutputContract(
        fields=fields,
        artifacts=artifacts,
    ).model_dump()
    return BatchJobV2.model_validate(payload)


def _materialize_and_validate(
    context: FormalExecutionContext,
    job: BatchJobV2,
    execution: FormalQuestionExecution,
) -> tuple[ArtifactValidationResult, ArtifactManifest]:
    paths = context.paths
    if execution.report_pdf is not None:
        paths.report_pdf.write_bytes(execution.report_pdf)
    if execution.report_markdown is not None:
        paths.report_md.write_text(execution.report_markdown, encoding="utf-8")
    identity = _identity(job, context.run_id)
    _write_json(
        paths.result_json,
        {
            **identity,
            "fields": dict(execution.standard_fields),
            "research_plan": dict(execution.research_plan),
        },
    )
    cards = []
    for index, card in enumerate(execution.evidence_cards, start=1):
        payload = dict(card)
        payload.update(identity)
        payload["evidence_id"] = str(
            card.get("evidence_id") or card.get("id") or f"EV-{job.question_id}-{index:03d}"
        )
        cards.append(payload)
    _write_json(paths.evidence_cards_json, cards)
    events = []
    for event in execution.agent_trace:
        payload = dict(event)
        payload.setdefault("run_id", context.run_id)
        events.append(payload)
    _write_json(paths.agent_trace_json, {**identity, "events": events})
    audit = execution.call_audits[0]
    audit_path = paths.question_root / "llm_call_audit.json"
    audit_path.write_text(audit.to_json(), encoding="utf-8", newline="\n")
    validation = validate_required_artifacts(job, paths)
    if not validation.passed:
        first = validation.issues[0]
        raise BatchRunnerError(first.error_code, first.message)
    artifact_manifest = build_artifact_manifest(
        job,
        paths,
        validation,
        output_contract_version=FORMAL_OUTPUT_CONTRACT_VERSION,
        supplemental_artifact_paths={"llm_call_audit.json": audit_path},
    )
    _write_json(paths.artifact_manifest_json, artifact_manifest.to_dict())
    return validation, artifact_manifest


def _completion_input(
    config,
    frozen,
    context,
    job,
    execution,
    artifact_manifest,
    delivery_index,
    ledger,
) -> CompletionGateInput:
    question_item = {
        "id": frozen.question_id,
        "question": frozen.question,
        "domain": frozen.domain,
        "batch_id": job.batch_id,
        "run_id": context.run_id,
        "version_id": f"{context.run_id}:v1",
        "source_hash": job.source_hash,
        "input_hash": job.input_hash,
    }
    trace = []
    for event in execution.agent_trace:
        payload = dict(event)
        payload.setdefault("run_id", context.run_id)
        trace.append(payload)
    return CompletionGateInput(
        batch_id=job.batch_id,
        question_id=job.question_id,
        question=str(frozen.question),
        domain=str(frozen.domain),
        run_id=context.run_id,
        version_id=question_item["version_id"],
        source_hash=job.source_hash,
        input_hash=job.input_hash,
        research_plan=dict(execution.research_plan),
        evidence_cards=tuple(dict(card) for card in execution.evidence_cards),
        agent_trace=tuple(trace),
        execution_metadata=dict(execution.execution_metadata),
        question_item=question_item,
        evidence_bundle=execution.evidence_bundle,
        claims=execution.claims,
        artifact_manifest=artifact_manifest,
        delivery_index=delivery_index,
        call_audit=execution.call_audits[0],
        source_kind=config.source_kind,
        source_provenance_verified=True,
        frozen_question_verified=True,
        budgets_verified=True,
        created_at=datetime.now(timezone.utc),
        open_issues=execution.open_issues,
        budget_policy=config.budget_policy,
        frozen_provider=config.provider_name,
        frozen_model=EXPECTED_PRIMARY_MODEL,
        question_tokens_used=ledger.question_tokens(job.question_id),
        question_token_limit=QUESTION_TOKEN_LIMIT,
        batch_tokens_used=ledger.batch_tokens,
        batch_token_limit=BATCH_TOKEN_LIMIT,
        max_output_tokens_per_call=MAX_OUTPUT_TOKENS,
    )


def _write_completion_outputs(root: Path, result: CompletionGateResult) -> None:
    _write_json(
        root / "quality_gate_results.json",
        [gate.model_dump(mode="json") for gate in result.gate_results],
    )
    _write_json(
        root / "validation_report.json",
        None
        if result.validation_report is None
        else result.validation_report.model_dump(mode="json"),
    )
    _write_json(
        root / "completion_decision.json",
        {
            "status": result.status,
            "completed": result.completed,
            "conditions": dict(result.conditions),
            "error_codes": list(result.error_codes),
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity.value,
                    "closure_status": issue.closure_status,
                }
                for issue in result.issues
            ],
        },
    )


def _job_after_completion(
    job: BatchJobV2,
    completion: CompletionGateResult,
) -> BatchJobV2:
    payload = job.model_dump()
    payload["status"] = (
        JobStatus.COMPLETED.value
        if completion.completed and completion.status == "completed"
        else JobStatus.GATES_PENDING.value
    )
    return BatchJobV2.model_validate(payload)


def _persist_question_failure(
    config,
    context,
    base_job,
    exc,
    ledger,
) -> tuple[FormalQuestionReceipt, QuestionDeliveryRecord]:
    code = exc.error_code if isinstance(exc, BatchRunnerError) else "FORMAL_RUN_FAILED"
    payload = base_job.model_dump()
    payload["status"] = JobStatus.FAILED.value
    payload["budget"]["tokens_used"] = ledger.question_tokens(base_job.question_id)
    payload["failures"] = [
        {
            "error_code": code,
            "message": "formal execution failed closed",
            "retryable": False,
            "attempt": 1,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    failed_job = BatchJobV2.model_validate(payload)
    write_checkpoint(
        context.question_root / "checkpoint.json",
        CheckpointRecordV2.from_job(failed_job),
    )
    _write_json(
        context.question_root / "completion_decision.json",
        {
            "status": "failed",
            "completed": False,
            "error_codes": [code],
        },
    )
    validation = ArtifactValidationResult(
        validation_status="failed",
        issues=(
            ArtifactValidationIssue(
                error_code=code,
                artifact=None,
                message="formal execution failed closed",
            ),
        ),
        artifacts=(),
    )
    record = build_question_delivery_record(
        failed_job,
        config.source_kind,
        validation,
        None,
        output_contract_version=FORMAL_OUTPUT_CONTRACT_VERSION,
        input_tokens=0,
        output_tokens=0,
        duration_seconds=0.0,
        budget_policy=config.budget_policy,
        estimated_cost_usd=None,
        settled_cost_usd=None,
    )
    return (
        FormalQuestionReceipt(
            question_id=base_job.question_id,
            run_id=context.run_id,
            status="failed",
            completed=False,
            error_codes=(code,),
            tokens_used=ledger.question_tokens(base_job.question_id),
            retries=ledger.question_retry_tokens(base_job.question_id),
        ),
        record,
    )


def _resume_completed_question(
    batch_root: Path,
    expected_job: BatchJobV2,
    question_id: str,
) -> FormalQuestionReceipt | None:
    root = batch_root / question_id
    checkpoint_path = root / "checkpoint.json"
    if not checkpoint_path.is_file():
        return None
    checkpoint = read_checkpoint(checkpoint_path)
    resumed = resume_job(checkpoint, expected_job, ResumePolicy())
    if resumed.status is not JobStatus.COMPLETED:
        return None
    manifest_path = root / "artifact_manifest.json"
    if not manifest_path.is_file():
        raise BatchRunnerError(
            "ARTIFACT_MANIFEST_MISSING",
            "completed checkpoint has no artifact manifest",
        )
    artifact_manifest = _artifact_manifest_from_json(manifest_path)
    index_path = batch_root / "delivery_index.json"
    if not index_path.is_file():
        raise BatchRunnerError(
            "DELIVERY_INDEX_MISSING",
            "completed checkpoint has no delivery index",
        )
    delivery = DeliveryIndex.from_json(index_path.read_text(encoding="utf-8"))
    validate_delivery_index(delivery, artifact_root=batch_root)
    records = [item for item in delivery.records if item.question_id == question_id]
    if len(records) != 1:
        raise BatchRunnerError(
            "DELIVERY_RECORD_MISSING",
            "completed checkpoint is not uniquely indexed",
        )
    indexed = {item.name: item.sha256 for item in records[0].artifacts}
    manifested = {item.name: item.sha256 for item in artifact_manifest.artifacts}
    if indexed != manifested:
        raise BatchRunnerError(
            "DELIVERY_ARTIFACT_HASH_MISMATCH",
            "delivery index no longer matches the artifact manifest",
        )
    return FormalQuestionReceipt(
        question_id=question_id,
        run_id=_run_id_from_checkpoint(checkpoint),
        status="completed",
        completed=True,
        error_codes=(),
        tokens_used=resumed.budget.tokens_used,
        retries=0,
        artifacts=artifact_manifest.artifacts,
        resumed=True,
    )


def _artifact_manifest_from_json(path: Path) -> ArtifactManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ArtifactManifest(
            batch_id=str(payload["batch_id"]),
            question_id=str(payload["question_id"]),
            output_contract_version=str(payload["output_contract_version"]),
            validation_status=str(payload["validation_status"]),
            artifacts=tuple(
                ArtifactFileRecord.from_dict(item) for item in payload["artifacts"]
            ),
            manifest_sha256=str(payload["manifest_sha256"]),
        )
    except Exception as exc:
        raise BatchRunnerError(
            "ARTIFACT_MANIFEST_INVALID",
            "artifact manifest is not valid UTF-8 JSON",
        ) from exc


def _load_existing_manifest(batch_root: Path, resume: bool) -> dict[str, Any] | None:
    if not batch_root.exists():
        return None
    if not resume:
        raise BatchRunnerError(
            "FORMAL_RUN_ALREADY_EXISTS",
            "formal run root already contains this freeze",
        )
    path = batch_root / "manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "FORMAL_MANIFEST_INVALID",
            "resume manifest is unavailable or invalid",
        ) from exc
    if not isinstance(payload, dict):
        raise BatchRunnerError("FORMAL_MANIFEST_INVALID", "resume manifest is invalid")
    return payload


def _validate_resume_manifest(manifest, authorization, audit_reference) -> None:
    if manifest.get("authorization_reference") != authorization:
        raise BatchRunnerError(
            "FIVE_REAL_RUNS_AUTHORIZATION_MISMATCH",
            "resume authorization reference changed",
        )
    audit = manifest.get("provider_preflight_audit")
    if not isinstance(audit, Mapping) or audit.get("sha256") != audit_reference.sha256:
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_AUDIT_HASH_MISMATCH",
            "resume provider preflight audit hash changed",
        )


def _base_manifest(config, authorization, audit_reference, code_sha, questions, *, execute):
    return {
        "manifest_version": FORMAL_MANIFEST_VERSION,
        "freeze_id": config.freeze_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_sha": code_sha,
        "authorization_text": AUTHORIZATION_TEXT,
        "authorization_reference": authorization,
        "provider_preflight_audit": audit_reference.to_manifest_dict(),
        "source_kind": config.source_kind,
        "question_order": list(FROZEN_EXECUTION_ORDER),
        "selected_question_ids": list(questions),
        "execute": execute,
        "mock": False,
        "fallback": False,
        "provider_calls": 0,
        "questions": [],
        "status": "preflight",
    }


def _identity(job: BatchJobV2, run_id: str) -> dict[str, Any]:
    return {
        "batch_id": job.batch_id,
        "question_id": job.question_id,
        "run_id": run_id,
        "attempt": job.attempt,
        "source_hash": job.source_hash,
        "input_hash": job.input_hash,
        "status": job.status.value,
    }


def _git_sha(repo_root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or len(value) != 40:
        raise BatchRunnerError("GIT_HEAD_UNAVAILABLE", "unable to resolve tested code SHA")
    return value


def _new_run_id(question_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{question_id.lower()}-{stamp}-{uuid.uuid4().hex[:8]}"


def _run_id_from_checkpoint(checkpoint: CheckpointRecordV2) -> str:
    return checkpoint.job.context_id.rsplit(":", 1)[-1]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f"{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True
