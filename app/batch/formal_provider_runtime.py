"""Audited single-call provider runtime for the frozen WB5 formal entrypoint.

The audit hook is registered before the provider boundary is crossed.  The
provider response is not accepted until request identity and token usage have
sealed one :class:`ActualCallAudit`.  Missing hooks or incomplete metadata stay
fail-closed and never become successful formal receipts.
"""

from __future__ import annotations

import hashlib
import json
import re
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
from app.clients.qwen_chat_client import QwenChatClient, QwenClientError
from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.evidence import ClaimText
from app.exporters.pdf_exporter import export_markdown_to_pdf


Clock = Callable[[], datetime]
ClientFactory = Callable[[Any], Any]
PdfRenderer = Callable[[str, Path], bytes | None]


_HTTP_STATUS_PATTERN = re.compile(
    r"(?:[（(]\s*|(?:http(?:\s+status)?|status(?:_code)?|error\s+code)"
    r"\s*[:=]?\s*)([1-5]\d{2})(?:\s*[）)]|\b)",
    re.IGNORECASE,
)
_HTTP_ERROR_CODES = {
    400: "PROVIDER_BAD_REQUEST",
    401: "PROVIDER_AUTH_ERROR",
    403: "PROVIDER_PERMISSION_ERROR",
    404: "PROVIDER_NOT_FOUND",
    429: "PROVIDER_RATE_LIMITED",
}


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


@dataclass(frozen=True, slots=True)
class ProviderFailureClassification:
    """Allowlisted diagnostics safe to persist for a failed provider boundary."""

    error_code: str
    message: str
    http_status: int | None
    stage: str
    exception_type: str


@dataclass(frozen=True, slots=True)
class FormalEvidencePayload:
    """Validated T01/T03 evidence inputs derived without inventing evidence."""

    cards: tuple[Mapping[str, Any], ...]
    bundle: EvidenceBundle
    claims: tuple[ClaimText, ...]
    hypotheses: tuple[Mapping[str, Any], ...]
    references: tuple[Mapping[str, Any], ...]


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
            failure = _classify_provider_failure(exc)
            raise BatchRunnerError(
                failure.error_code,
                failure.message,
                http_status=failure.http_status,
                stage=failure.stage,
                exception_type=failure.exception_type,
            ) from None
        duration_seconds = perf_counter() - started
        audit = audit_hook.seal(
            registration,
            raw_request_id=getattr(client, "last_request_id", None),
            usage=getattr(client, "last_usage", None),
        )
        try:
            return _build_execution(
                context,
                payload,
                audit,
                dynamic_prompt_hash,
                duration_seconds,
                render_pdf,
            )
        except BatchRunnerError as exc:
            raise BatchRunnerError(
                exc.error_code,
                str(exc),
                http_status=exc.http_status,
                stage=exc.stage,
                exception_type=exc.exception_type,
                call_audits=(audit,),
            ) from None

    return execute


def _classify_provider_failure(exc: Exception) -> ProviderFailureClassification:
    """Map an already-sanitized client failure to a stable, secret-free code.

    ``QwenChatClient`` deliberately hides transport details behind
    :class:`QwenClientError`.  Only its fixed friendly categories are inspected
    here; the original message is never copied into runner receipts.
    """

    exception_type = type(exc).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", exception_type):
        exception_type = "Exception"
    friendly = str(exc) if isinstance(exc, QwenClientError) else ""
    stage = "response_parse" if "不是合法 JSON" in friendly else "provider_call"
    http_status = _extract_http_status(exc, friendly)

    if http_status is not None:
        error_code = _HTTP_ERROR_CODES.get(http_status)
        if error_code is None and 500 <= http_status <= 599:
            error_code = "PROVIDER_SERVER_ERROR"
        return ProviderFailureClassification(
            error_code=error_code or "PROVIDER_HTTP_ERROR",
            message="formal provider HTTP request failed",
            http_status=http_status,
            stage=stage,
            exception_type=exception_type,
        )

    if stage == "response_parse":
        return ProviderFailureClassification(
            error_code="PROVIDER_RESPONSE_PARSE_ERROR",
            message="formal provider response was not valid JSON",
            http_status=None,
            stage=stage,
            exception_type=exception_type,
        )
    if "超时" in friendly:
        return ProviderFailureClassification(
            error_code="PROVIDER_TIMEOUT",
            message="formal provider call timed out",
            http_status=None,
            stage=stage,
            exception_type=exception_type,
        )

    http_markers = (
        "鉴权失败",
        "拒绝访问",
        "模型或端点不存在",
        "限流或额度不足",
        "请求参数不兼容",
        "HTTPS/TLS",
        "无法连接百炼 HTTPS",
        "百炼调用失败",
    )
    if any(marker in friendly for marker in http_markers):
        return ProviderFailureClassification(
            error_code="PROVIDER_HTTP_ERROR",
            message="formal provider HTTP request failed",
            http_status=None,
            stage=stage,
            exception_type=exception_type,
        )
    return ProviderFailureClassification(
        error_code="PROVIDER_CALL_FAILED",
        message="formal provider call failed",
        http_status=None,
        stage=stage,
        exception_type=exception_type,
    )


def _extract_http_status(exc: Exception, friendly: str) -> int | None:
    raw_status = getattr(exc, "status_code", None)
    if type(raw_status) is int and 100 <= raw_status <= 599:
        return raw_status
    match = _HTTP_STATUS_PATTERN.search(friendly)
    return int(match.group(1)) if match is not None else None


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
            "evidence_cards_required": True,
            "evidence_card_fields": [
                "evidence_id",
                "source_id",
                "source_type",
                "title",
                "quoted_text",
                "locator",
                "content_hash",
                "domain",
                "verification_status",
            ],
            "content_hash_format": "sha256:<sha256 of exact quoted_text UTF-8>",
            "generated_hypothesis_fields": [
                "hypothesis",
                "supporting_evidence_ids",
                "contradicted_by_evidence_ids",
            ],
            "reference_ids_required": True,
            "evidence_id_integrity_required": True,
            "question_booklet_is_not_research_evidence": True,
            "fail_closed_if_traceable_evidence_is_unavailable": True,
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
    evidence = _build_formal_evidence(context, payload)
    datasets = payload.get("datasets")
    datasets = datasets if isinstance(datasets, Mapping) else {}
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
        "References": _json_text(evidence.references),
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
    plan = {
        **payload,
        "question_id": context.question_id,
        "input_question": context.question.get("question"),
        "domain": context.question.get("domain"),
        "actual_execution": True,
        "generated_hypotheses": list(evidence.hypotheses),
        "references": list(evidence.references),
        "reference_ids": [str(item["id"]) for item in evidence.references],
    }
    return FormalQuestionExecution(
        report_pdf=pdf_renderer(markdown, context.question_root),
        report_markdown=markdown,
        standard_fields=fields,
        research_plan=plan,
        evidence_cards=evidence.cards,
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
        evidence_bundle=evidence.bundle,
        claims=evidence.claims,
        call_audits=(audit,),
        duration_seconds=duration_seconds,
        open_issues=issues,
    )


def _build_formal_evidence(
    context: FormalExecutionContext,
    payload: Mapping[str, Any],
) -> FormalEvidencePayload:
    try:
        return _validate_formal_evidence(context, payload)
    except (KeyError, TypeError, ValueError):
        raise BatchRunnerError(
            "FORMAL_PROVIDER_EVIDENCE_INVALID",
            "provider response did not contain a valid traceable evidence contract",
            stage="response_validation",
            exception_type="EvidenceContractError",
        ) from None


def _validate_formal_evidence(
    context: FormalExecutionContext,
    payload: Mapping[str, Any],
) -> FormalEvidencePayload:
    raw_cards = payload.get("evidence_cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        raise ValueError("evidence cards missing")

    contracts: list[EvidenceCardContract] = []
    wires: list[Mapping[str, Any]] = []
    wire_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_card in raw_cards:
        if not isinstance(raw_card, Mapping):
            raise TypeError("evidence card must be a mapping")
        card_payload = dict(raw_card)
        evidence_id = _text(card_payload.get("evidence_id") or card_payload.get("id"))
        quoted_text = _text(card_payload.get("quoted_text"))
        if not evidence_id or not quoted_text:
            raise ValueError("evidence identity and quote are required")
        expected_hash = "sha256:" + hashlib.sha256(
            quoted_text.encode("utf-8")
        ).hexdigest()
        supplied_hash = _text(card_payload.get("content_hash"))
        if supplied_hash and supplied_hash != expected_hash:
            raise ValueError("evidence content hash mismatch")
        card_payload["evidence_id"] = evidence_id
        card_payload["content_hash"] = expected_hash
        card_payload.setdefault("domain", context.question.get("domain"))
        card_payload.setdefault("verification_status", "pending")
        contract = EvidenceCardContract.model_validate(card_payload)
        if (
            contract.source_type == "question_booklet"
            or "booklet" in contract.source_id.lower()
            or str(contract.locator.get("source", "")).lower() == "booklet"
        ):
            raise ValueError("question source cannot become research evidence")
        relevance = card_payload.get("relevance_score", 1.0)
        if isinstance(relevance, bool) or not isinstance(relevance, (int, float)):
            raise TypeError("relevance score must be numeric")
        if not 0.0 <= float(relevance) <= 1.0:
            raise ValueError("relevance score out of range")
        wire = contract.model_dump(mode="json")
        wire["id"] = evidence_id
        wire["relevance_score"] = float(relevance)
        if evidence_id in wire_by_id:
            raise ValueError("duplicate evidence id")
        contracts.append(contract)
        wires.append(wire)
        wire_by_id[evidence_id] = wire

    raw_hypotheses = payload.get("generated_hypotheses")
    if not isinstance(raw_hypotheses, list) or not raw_hypotheses:
        raise ValueError("generated hypotheses missing")
    claims: list[ClaimText] = []
    links: list[ClaimEvidenceLink] = []
    hypotheses: list[Mapping[str, Any]] = []
    for index, raw_hypothesis in enumerate(raw_hypotheses, start=1):
        if not isinstance(raw_hypothesis, Mapping):
            raise TypeError("hypothesis must be a mapping")
        hypothesis = dict(raw_hypothesis)
        text = _text(hypothesis.get("hypothesis"))
        supporting = _evidence_ids(hypothesis.get("supporting_evidence_ids"))
        contradicted = _evidence_ids(
            hypothesis.get("contradicted_by_evidence_ids"),
            allow_empty=True,
        )
        if not text or not supporting:
            raise ValueError("hypothesis support binding missing")
        if any(item not in wire_by_id for item in (*supporting, *contradicted)):
            raise ValueError("hypothesis references unknown evidence")
        claim_id = _text(hypothesis.get("claim_id")) or (
            f"{context.question_id}-hypothesis-{index}"
        )
        claim_domain = _text(context.question.get("domain")) or None
        claims.append(
            ClaimText(
                claim_id=claim_id,
                text=text,
                evidence_ids=supporting,
                domain=claim_domain,
            )
        )
        links.extend(
            ClaimEvidenceLink(
                claim_id=claim_id,
                evidence_id=evidence_id,
                relation="supports",
                confidence=0.5,
                claim_domain=claim_domain,
                validation_status="pending",
            )
            for evidence_id in supporting
        )
        links.extend(
            ClaimEvidenceLink(
                claim_id=claim_id,
                evidence_id=evidence_id,
                relation="contradicts",
                confidence=0.5,
                claim_domain=claim_domain,
                validation_status="pending",
            )
            for evidence_id in contradicted
        )
        hypothesis["supporting_evidence_ids"] = list(supporting)
        hypothesis["contradicted_by_evidence_ids"] = list(contradicted)
        hypotheses.append(hypothesis)

    reference_source = payload.get("reference_ids")
    if not isinstance(reference_source, list) or not reference_source:
        reference_source = payload.get("references")
    reference_ids = _reference_ids(reference_source)
    if not reference_ids or any(item not in wire_by_id for item in reference_ids):
        raise ValueError("traceable references missing")
    references = tuple(dict(wire_by_id[item]) for item in reference_ids)
    bundle = EvidenceBundle(
        bundle_id=f"{context.run_id}:evidence",
        evidences=contracts,
        links=links,
        token_budget=8000,
    )
    return FormalEvidencePayload(
        cards=tuple(wires),
        bundle=bundle,
        claims=tuple(claims),
        hypotheses=tuple(hypotheses),
        references=references,
    )


def _evidence_ids(value: Any, *, allow_empty: bool = False) -> tuple[str, ...]:
    if value is None and allow_empty:
        return ()
    if not isinstance(value, list):
        raise TypeError("evidence id collection must be a list")
    identifiers = tuple(_text(item) for item in value)
    if any(not item for item in identifiers) or len(identifiers) != len(set(identifiers)):
        raise ValueError("evidence id collection is invalid")
    if not identifiers and not allow_empty:
        raise ValueError("evidence id collection is empty")
    return identifiers


def _reference_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    identifiers = []
    for item in value:
        identifier = (
            _text(item.get("id") or item.get("evidence_id"))
            if isinstance(item, Mapping)
            else _text(item)
        )
        if not identifier:
            raise ValueError("reference id missing")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate reference id")
    return tuple(identifiers)


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
