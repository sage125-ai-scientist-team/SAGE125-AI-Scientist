"""Audited single-call provider runtime for the frozen WB5 formal entrypoint.

The audit hook is registered before the provider boundary is crossed.  The
provider response is not accepted until request identity and token usage have
sealed one :class:`ActualCallAudit`.  Missing hooks or incomplete metadata stay
fail-closed and never become successful formal receipts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Protocol

from app.agents.prompts import REPORT_WRITER_PROMPT
from app.batch.actual_call_audit import (
    ActualCallAudit,
    CostAccountingMode,
    sanitize_request_id,
)
from app.batch.completion_gate import CompletionGateIssue
from app.batch.errors import BatchRunnerError
from app.batch.formal_five_runs import (
    EXPECTED_PRIMARY_MODEL,
    EXPECTED_PROVIDER,
    FormalExecutionContext,
    FormalExecutor,
    FormalQuestionExecution,
)
from app.clients.qwen_chat_client import QwenChatClient
from app.exporters.pdf_exporter import export_markdown_to_pdf


Clock = Callable[[], datetime]
ClientFactory = Callable[[Any], Any]
PdfRenderer = Callable[[str, Path], bytes | None]


class FormalProviderClient(Protocol):
    """Minimal client surface used by the audited provider boundary."""

    last_request_id: str | None
    last_usage: Mapping[str, Any]

    def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.1,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ProviderAuditRegistration:
    """Immutable proof that an audit sink existed before a provider call."""

    question_id: str
    run_id: str
    provider: str
    model: str
    route_tier: str
    request_timestamp: datetime
    static_prompt_version: str
    static_prompt_hash: str
    dynamic_prompt_hash: str
    retry_attempt: int


class ProviderAuditHook:
    """Register-before-call hook that seals complete, secret-free call truth."""

    def __init__(self, *, available: bool = True, clock: Clock | None = None) -> None:
        self.available = available
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._active: dict[str, ProviderAuditRegistration] = {}

    def is_registered(self, run_id: str) -> bool:
        return run_id in self._active

    def register(
        self,
        context: FormalExecutionContext,
        *,
        provider: str,
        model: str,
        route_tier: str,
        static_prompt_version: str,
        static_prompt_hash: str,
        dynamic_prompt_hash: str,
        retry_attempt: int = 1,
    ) -> ProviderAuditRegistration:
        if not self.available:
            raise BatchRunnerError(
                "CALL_AUDIT_HOOK_UNAVAILABLE",
                "formal provider audit hook is not available",
            )
        if context.run_id in self._active:
            raise BatchRunnerError(
                "CALL_AUDIT_HOOK_UNAVAILABLE",
                "formal provider audit hook already has an active call",
            )
        registration = ProviderAuditRegistration(
            question_id=context.question_id,
            run_id=context.run_id,
            provider=provider,
            model=model,
            route_tier=route_tier,
            request_timestamp=self._clock(),
            static_prompt_version=static_prompt_version,
            static_prompt_hash=static_prompt_hash,
            dynamic_prompt_hash=dynamic_prompt_hash,
            retry_attempt=retry_attempt,
        )
        self._active[context.run_id] = registration
        return registration

    def abort(self, registration: ProviderAuditRegistration) -> None:
        if self._active.get(registration.run_id) is registration:
            self._active.pop(registration.run_id, None)

    def seal(
        self,
        registration: ProviderAuditRegistration,
        *,
        raw_request_id: Any,
        usage: Mapping[str, Any] | None,
    ) -> ActualCallAudit:
        active = self._active.pop(registration.run_id, None)
        if active is not registration:
            raise BatchRunnerError(
                "CALL_AUDIT_HOOK_UNAVAILABLE",
                "formal provider audit registration was not active",
            )
        try:
            request_id = str(raw_request_id).strip()
            usage_map = usage if isinstance(usage, Mapping) else {}
            counts = {
                name: _strict_token_count(usage_map.get(name), name)
                for name in ("input_tokens", "output_tokens", "total_tokens")
            }
            if not request_id:
                raise ValueError("request id missing")
            if counts["total_tokens"] != (
                counts["input_tokens"] + counts["output_tokens"]
            ):
                raise ValueError("token total mismatch")
            return ActualCallAudit(
                provider=registration.provider,
                model=registration.model,
                route_tier=registration.route_tier,
                request_timestamp=registration.request_timestamp,
                sanitized_request_id=sanitize_request_id(request_id),
                static_prompt_version=registration.static_prompt_version,
                static_prompt_hash=registration.static_prompt_hash,
                dynamic_prompt_hash=registration.dynamic_prompt_hash,
                input_tokens=counts["input_tokens"],
                output_tokens=counts["output_tokens"],
                total_tokens=counts["total_tokens"],
                estimated_cost_usd=None,
                settled_cost_usd=None,
                retry_attempt=registration.retry_attempt,
                fallback=False,
                price_snapshot_version=None,
                cost_accounting_mode=CostAccountingMode.TOKEN_ONLY,
            )
        except (TypeError, ValueError) as exc:
            raise BatchRunnerError(
                "CALL_AUDIT_INCOMPLETE",
                "provider response did not expose complete request and token audit metadata",
            ) from exc


def build_formal_provider_executor(
    settings: Any,
    *,
    hook: ProviderAuditHook | None = None,
    client_factory: ClientFactory = QwenChatClient,
    pdf_renderer: PdfRenderer | None = None,
) -> FormalExecutor:
    """Initialize the production executor and inject its pre-call audit hook."""

    if getattr(settings, "llm_provider", None) != EXPECTED_PROVIDER:
        raise BatchRunnerError(
            "FROZEN_PROVIDER_RUNTIME_MISMATCH",
            "runtime provider does not match the frozen formal provider",
        )
    if getattr(settings, "qwen_fast_model", None) != EXPECTED_PRIMARY_MODEL:
        raise BatchRunnerError(
            "FROZEN_PROVIDER_RUNTIME_MISMATCH",
            "runtime fast model does not match the frozen formal model",
        )
    audit_hook = hook or ProviderAuditHook()
    # One formal executor invocation crosses exactly one provider boundary.
    # Client-internal retries are disabled so a single hook registration cannot
    # accidentally summarize multiple transport calls as one audit event.
    runtime_settings = settings.model_copy(
        update={"llm_max_retries": 0, "llm_max_output_tokens": 8192}
    )
    render_pdf = pdf_renderer or _render_pdf

    def execute(context: FormalExecutionContext) -> FormalQuestionExecution:
        messages = _build_messages(context)
        dynamic_prompt_hash = _canonical_hash(messages)
        client: FormalProviderClient = client_factory(runtime_settings)
        registration = audit_hook.register(
            context,
            provider=EXPECTED_PROVIDER,
            model=EXPECTED_PRIMARY_MODEL,
            route_tier="fast",
            static_prompt_version=context.job.model_route.prompt_version,
            static_prompt_hash=context.job.model_route.prompt_hash,
            dynamic_prompt_hash=dynamic_prompt_hash,
        )
        started = perf_counter()
        try:
            payload = client.chat_json(
                messages,
                model=EXPECTED_PRIMARY_MODEL,
                temperature=0.1,
            )
        except Exception as exc:
            audit_hook.abort(registration)
            if isinstance(exc, BatchRunnerError):
                raise
            raise BatchRunnerError(
                "PROVIDER_CALL_FAILED",
                f"formal provider call failed: {type(exc).__name__}",
            ) from None
        duration_seconds = perf_counter() - started
        audit = audit_hook.seal(
            registration,
            raw_request_id=getattr(client, "last_request_id", None),
            usage=getattr(client, "last_usage", None),
        )
        return _build_execution(
            context,
            payload,
            audit,
            dynamic_prompt_hash,
            duration_seconds,
            render_pdf,
        )

    return execute


def _strict_token_count(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _build_messages(context: FormalExecutionContext) -> list[dict[str, str]]:
    request = {
        "question_id": context.question_id,
        "domain": context.question.get("domain"),
        "question": context.question.get("question"),
        "contract": {
            "no_fabricated_results": True,
            "references_must_be_traceable": True,
            "return_json_only": True,
        },
    }
    return [
        {"role": "system", "content": REPORT_WRITER_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                request,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    ]


def _build_execution(
    context: FormalExecutionContext,
    value: Mapping[str, Any],
    audit: ActualCallAudit,
    dynamic_prompt_hash: str,
    duration_seconds: float,
    pdf_renderer: PdfRenderer,
) -> FormalQuestionExecution:
    payload = dict(value) if isinstance(value, Mapping) else {}
    datasets = payload.get("datasets")
    datasets = datasets if isinstance(datasets, Mapping) else {}
    references = payload.get("references", payload.get("reference_ids", []))
    fields = {
        "Problem": _text(payload.get("problem_statement")),
        "Rationale": _text(payload.get("rationale")),
        "Technical Details": _text(payload.get("technical_details")),
        "Datasets Source": _text(datasets.get("source")),
        "Datasets Target": _text(datasets.get("target")),
        "Title": _text(payload.get("paper_title")),
        "Abstract": _text(payload.get("paper_abstract")),
        "Methods": _text(payload.get("methods")),
        "Experiments": _json_text(payload.get("experiments")),
        "Results": _text(payload.get("results")),
        "References": _json_text(references),
    }
    missing = tuple(name for name, item in fields.items() if not item.strip())
    issues = (
        (
            CompletionGateIssue(
                "FORMAL_PROVIDER_RESPONSE_INVALID",
                "provider response left formal output fields empty: " + ", ".join(missing),
            ),
        )
        if missing
        else ()
    )
    markdown = _report_markdown(fields)
    evidence_cards = _mapping_sequence(payload.get("evidence_cards"))
    claims = tuple(payload.get("claims", ())) if isinstance(payload.get("claims", ()), list) else ()
    plan = {
        **payload,
        "question_id": context.question_id,
        "input_question": context.question.get("question"),
        "domain": context.question.get("domain"),
        "actual_execution": True,
        "references": references if isinstance(references, list) else [],
    }
    return FormalQuestionExecution(
        report_pdf=pdf_renderer(markdown, context.question_root),
        report_markdown=markdown,
        standard_fields=fields,
        research_plan=plan,
        evidence_cards=evidence_cards,
        agent_trace=(
            {
                "run_id": context.run_id,
                "agent_name": "formal_provider_runtime",
                "model_name": EXPECTED_PRIMARY_MODEL,
                "status": "completed",
                "prompt_hash": dynamic_prompt_hash,
                "mock": False,
            },
        ),
        execution_metadata={
            "actual_execution": True,
            "mode": "actual",
            "provider": EXPECTED_PROVIDER,
            "model": EXPECTED_PRIMARY_MODEL,
        },
        evidence_bundle=payload.get("evidence_bundle", {}),
        claims=claims,
        call_audits=(audit,),
        duration_seconds=duration_seconds,
        open_issues=issues,
    )


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return ""


def _mapping_sequence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, Mapping))


def _report_markdown(fields: Mapping[str, str]) -> str:
    return "\n\n".join(f"## {name}\n\n{fields[name]}" for name in fields) + "\n"


def _render_pdf(markdown: str, question_root: Path) -> bytes | None:
    question_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".formal-pdf-", dir=question_root) as temporary:
        temp_root = Path(temporary)
        source = temp_root / "report.md"
        target = temp_root / "report.pdf"
        source.write_text(markdown, encoding="utf-8", newline="\n")
        result = export_markdown_to_pdf(source, target)
        if result.get("status") != "ok" or not target.is_file():
            return None
        content = target.read_bytes()
        return content if content.startswith(b"%PDF-") else None
