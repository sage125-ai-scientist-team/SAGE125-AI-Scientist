"""Offline integration tests for the formal provider audit-hook runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.batch.errors import BatchRunnerError
from app.batch.formal_evidence_context import (
    FormalEvidenceContextAdapter,
    FormalEvidenceQuery,
)
from app.batch.formal_provider_runtime import (
    ProviderAuditHook,
    build_formal_provider_executor,
)
from app.clients.qwen_chat_client import QwenClientError
from app.contracts.rag import (
    RetrievalHit,
    ScoreKind,
    SourceLocator,
    SourceRole,
    SourceType,
)
from app.evidence import precheck_bundle_for_validation
from app.workflow.quality_gates import run_all_quality_gates


PROMPT_HASH = "a" * 64


@dataclass(frozen=True)
class _Settings:
    llm_provider: str = "bailian"
    qwen_fast_model: str = "qwen3.6-flash"
    llm_max_retries: int = 1
    llm_max_output_tokens: int = 8192

    def model_copy(self, *, update):
        return replace(self, **update)


class _FakeClient:
    def __init__(self, hook: ProviderAuditHook, *, complete_usage: bool = True):
        self.hook = hook
        self.complete_usage = complete_usage
        self.calls = 0
        self.last_request_id = None
        self.last_usage = {}

    def chat_json(self, messages, model, temperature=0.1):
        assert self.hook.is_registered("formal-run-001")
        self.calls += 1
        self.last_request_id = "req-live-do-not-persist"
        if self.complete_usage:
            self.last_usage = {
                "input_tokens": 101,
                "output_tokens": 23,
                "total_tokens": 124,
            }
        request = json.loads(messages[-1]["content"])
        evidence_id = request["trusted_evidence_context"][0]["id"]
        return {
            "problem_statement": "Prime numbers are irreducible integers.",
            "rationale": "They organize divisibility.",
            "technical_details": "Use unique factorization.",
            "datasets": {"source": "authoritative question", "target": "evidence synthesis"},
            "paper_title": "Why primes are special",
            "paper_abstract": "A bounded synthesis.",
            "methods": "Structured mathematical analysis.",
            "experiments": {"validation_protocol": "formal checks"},
            "results": "No empirical result is claimed.",
            "generated_hypotheses": [
                {
                    "hypothesis": (
                        "Prime numbers are fundamental because they uniquely "
                        "factorize integers."
                    ),
                    "supporting_evidence_ids": [evidence_id],
                    "contradicted_by_evidence_ids": [],
                }
            ],
            "reference_ids": [evidence_id],
        }


class _FailingClient:
    def __init__(self, hook: ProviderAuditHook, failure: Exception):
        self.hook = hook
        self.failure = failure
        self.calls = 0
        self.last_request_id = None
        self.last_usage = {}

    def chat_json(self, messages, model, temperature=0.1):
        assert self.hook.is_registered("formal-run-001")
        self.calls += 1
        raise self.failure


def _context():
    return SimpleNamespace(
        question_id="Q001",
        run_id="formal-run-001",
        question_root=Path("D:/external/formal/Q001"),
        question={
            "id": "Q001",
            "domain": "Mathematical Sciences",
            "question": "What makes prime numbers so special?",
        },
        job=SimpleNamespace(
            model_route=SimpleNamespace(
                prompt_version="sage125-agent-prompts-20260803-v1",
                prompt_hash=PROMPT_HASH,
            )
        ),
    )


class _TrustedRetriever:
    def retrieve(self, query, filters=None, source_scope="user_upload"):
        return [
            RetrievalHit(
                chunk_id="prime-source-001-chunk",
                quoted_text=(
                    "Every integer greater than one has a unique factorization "
                    "into prime numbers."
                ),
                retrieval_score=0.9,
                score_kind=ScoreKind.VECTOR_SIMILARITY,
                source_type=SourceType.PAPER,
                source_role=SourceRole.USER_UPLOAD,
                source_locator=SourceLocator(
                    document_id="prime-source-001",
                    section="Fundamental theorem of arithmetic",
                    chunk_id="prime-source-001-chunk",
                ),
                content_hash="d" * 64,
                title="Prime-number factorization evidence",
                doi="10.1000/prime.001",
                url="https://example.test/prime-source-001",
                metadata={"authors": ["A. Mathematician"], "year": 2024},
            )
        ]


def _evidence_context_loader(query: FormalEvidenceQuery):
    return FormalEvidenceContextAdapter(_TrustedRetriever()).build(query)


def _build_test_executor(settings, **kwargs):
    return build_formal_provider_executor(
        settings,
        evidence_context_loader=_evidence_context_loader,
        **kwargs,
    )


def test_hook_is_registered_before_provider_call_and_seals_legal_audit() -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook)
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n% offline integration\n",
    )

    execution = executor(_context())

    assert client.calls == 1
    assert not hook.is_registered("formal-run-001")
    assert len(execution.call_audits) == 1
    audit = execution.call_audits[0]
    assert audit.model == "qwen3.6-flash"
    assert audit.input_tokens == 101
    assert audit.output_tokens == 23
    assert audit.total_tokens == 124
    assert audit.estimated_cost_usd is None
    assert audit.settled_cost_usd is None
    assert audit.fallback is False
    assert "req-live-do-not-persist" not in audit.to_json()
    evidence_id = execution.evidence_cards[0]["id"]
    assert evidence_id.startswith("EV-")
    assert execution.evidence_bundle.evidences[0].evidence_id == evidence_id
    assert execution.claims[0].evidence_ids == (evidence_id,)


def test_compliant_provider_evidence_passes_t01_and_t03_grounding() -> None:
    hook = ProviderAuditHook()
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: _FakeClient(hook),
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )
    execution = executor(_context())
    context = SimpleNamespace(evidence_cards=execution.evidence_cards)

    t01 = precheck_bundle_for_validation(
        bundle=execution.evidence_bundle,
        claims=execution.claims,
        context=context,
    ).gate
    t03 = run_all_quality_gates(
        execution.research_plan,
        list(execution.evidence_cards),
        list(execution.agent_trace),
    )

    assert t01.passed
    assert t03["gates"]["evidence_grounding"]["passed"]
    assert t03["gates"]["reference_integrity"]["passed"]


def test_missing_evidence_context_stops_before_provider_call() -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook)
    executor = build_formal_provider_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    with pytest.raises(BatchRunnerError) as captured:
        executor(_context())

    assert captured.value.error_code == "FORMAL_EVIDENCE_CONTEXT_UNAVAILABLE"
    assert captured.value.stage == "evidence_context"
    assert captured.value.diagnostic_details == {
        "validation_code": "EVIDENCE_RETRIEVER_UNAVAILABLE"
    }
    assert captured.value.call_audits == ()
    assert client.calls == 0


def test_request_supplies_trusted_evidence_and_forbids_model_cards() -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook)
    original = client.chat_json

    def inspect_contract(messages, model, temperature=0.1):
        request = json.loads(messages[-1]["content"])
        contract = request["contract"]
        assert request["trusted_evidence_context"]
        assert "evidence_cards" not in contract["required_top_level_fields"]
        assert "evidence_cards" in contract["provider_output_forbidden_fields"]
        assert contract["provider_may_not_create_or_modify_evidence"] is True
        return original(messages, model, temperature)

    client.chat_json = inspect_contract
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    execution = executor(_context())

    assert execution.evidence_cards


def test_provider_evidence_card_mutation_is_rejected() -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook)
    original = client.chat_json

    def with_untrusted_card(messages, model, temperature=0.1):
        payload = original(messages, model, temperature)
        payload["evidence_cards"] = [
            {
                "evidence_id": "MODEL-CREATED",
                "quoted_text": "model-controlled quote",
                "locator": {"page": 1},
            }
        ]
        return payload

    client.chat_json = with_untrusted_card
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    with pytest.raises(BatchRunnerError) as captured:
        executor(_context())

    assert captured.value.diagnostic_details == {
        "validation_code": "MODEL_EVIDENCE_MUTATION_FORBIDDEN",
        "field": "evidence_cards",
    }
    assert len(captured.value.call_audits) == 1


def test_provider_reference_locator_mutation_is_rejected() -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook)
    original = client.chat_json

    def with_mutated_reference(messages, model, temperature=0.1):
        payload = original(messages, model, temperature)
        evidence_id = payload["reference_ids"][0]
        payload["reference_ids"] = []
        payload["references"] = [
            {"id": evidence_id, "locator": {"page": 999}}
        ]
        return payload

    client.chat_json = with_mutated_reference
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    with pytest.raises(BatchRunnerError) as captured:
        executor(_context())

    assert captured.value.diagnostic_details["validation_code"] == (
        "MODEL_EVIDENCE_MUTATION_FORBIDDEN"
    )
    assert captured.value.diagnostic_details["field"] == "locator"
    assert len(captured.value.call_audits) == 1


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda payload: payload["generated_hypotheses"][0].update(
                {"supporting_evidence_ids": ["EV-UNKNOWN"]}
            ),
            {
                "validation_code": "SUPPORTING_EVIDENCE_ID_UNKNOWN",
                "hypothesis_index": 0,
                "evidence_id": "EV-UNKNOWN",
                "field": "supporting_evidence_ids",
            },
        ),
        (
            lambda payload: payload["generated_hypotheses"][0].pop(
                "supporting_evidence_ids"
            ),
            {
                "validation_code": "HYPOTHESIS_SUPPORT_BINDING_INVALID",
                "hypothesis_index": 0,
                "field": "supporting_evidence_ids",
            },
        ),
    ],
)
def test_invalid_evidence_reports_only_structural_diagnostics(mutate, expected) -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook)
    original = client.chat_json

    def invalid_payload(messages, model, temperature=0.1):
        payload = original(messages, model, temperature)
        mutate(payload)
        return payload

    client.chat_json = invalid_payload
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    with pytest.raises(BatchRunnerError) as captured:
        executor(_context())

    assert captured.value.error_code == "FORMAL_PROVIDER_EVIDENCE_INVALID"
    assert captured.value.diagnostic_details == expected
    assert len(captured.value.call_audits) == 1


def test_unavailable_hook_blocks_before_provider_call() -> None:
    hook = ProviderAuditHook(available=False)
    client = _FakeClient(hook)
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    with pytest.raises(BatchRunnerError) as captured:
        executor(_context())

    assert captured.value.error_code == "CALL_AUDIT_HOOK_UNAVAILABLE"
    assert client.calls == 0


def test_incomplete_provider_metadata_remains_fail_closed() -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook, complete_usage=False)
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    with pytest.raises(BatchRunnerError) as captured:
        executor(_context())

    assert captured.value.error_code == "CALL_AUDIT_INCOMPLETE"
    assert client.calls == 1
    assert not hook.is_registered("formal-run-001")


def test_runtime_disables_client_retries_so_one_hook_event_equals_one_call() -> None:
    hook = ProviderAuditHook()
    observed_settings = []
    client = _FakeClient(hook)

    def client_factory(settings):
        observed_settings.append(settings)
        return client

    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=client_factory,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )
    executor(_context())

    assert observed_settings[0].llm_max_retries == 0
    assert observed_settings[0].llm_max_output_tokens == 8192


def test_runtime_receipt_does_not_serialize_secret() -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook)
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )
    execution = executor(_context())

    serialized = json.dumps(
        {
            "audits": [audit.to_dict() for audit in execution.call_audits],
            "trace": execution.agent_trace,
        }
    )
    assert "req-live-do-not-persist" not in serialized
    assert "api_key" not in serialized.lower()


@pytest.mark.parametrize(
    ("failure", "expected_code", "expected_status", "expected_stage"),
    [
        (
            QwenClientError("百炼请求超时；系统已停止继续重试。"),
            "PROVIDER_TIMEOUT",
            None,
            "provider_call",
        ),
        (
            QwenClientError("千问返回内容不是合法 JSON；已停止本次步骤。"),
            "PROVIDER_RESPONSE_PARSE_ERROR",
            None,
            "response_parse",
        ),
        (
            RuntimeError("Authorization: Bearer SENSITIVE_TEST_VALUE"),
            "PROVIDER_CALL_FAILED",
            None,
            "provider_call",
        ),
    ],
)
def test_non_http_provider_failures_preserve_only_safe_diagnostics(
    failure: Exception,
    expected_code: str,
    expected_status: int | None,
    expected_stage: str,
) -> None:
    hook = ProviderAuditHook()
    client = _FailingClient(hook, failure)
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    with pytest.raises(BatchRunnerError) as captured:
        executor(_context())

    assert captured.value.error_code == expected_code
    assert captured.value.http_status == expected_status
    assert captured.value.stage == expected_stage
    assert captured.value.exception_type == type(failure).__name__
    assert "SENSITIVE_TEST_VALUE" not in str(captured.value)
    assert client.calls == 1
    assert not hook.is_registered("formal-run-001")


@pytest.mark.parametrize(
    ("status", "friendly", "expected_code"),
    [
        (
            400,
            "百炼请求参数不兼容（400）：Authorization: Bearer SENSITIVE_TEST_VALUE",
            "PROVIDER_BAD_REQUEST",
        ),
        (401, "百炼鉴权失败（401）：测试用脱敏消息。", "PROVIDER_AUTH_ERROR"),
        (403, "百炼拒绝访问（403）：测试用脱敏消息。", "PROVIDER_PERMISSION_ERROR"),
        (404, "百炼模型或端点不存在（404）：测试用脱敏消息。", "PROVIDER_NOT_FOUND"),
        (429, "百炼限流或额度不足（429）：测试用脱敏消息。", "PROVIDER_RATE_LIMITED"),
        (
            503,
            "百炼调用失败：Error code: 503 - SENSITIVE_TEST_VALUE",
            "PROVIDER_SERVER_ERROR",
        ),
    ],
)
def test_http_failures_are_safely_classified_with_status(
    status: int,
    friendly: str,
    expected_code: str,
) -> None:
    hook = ProviderAuditHook()
    failure = QwenClientError(friendly)
    client = _FailingClient(hook, failure)
    executor = _build_test_executor(
        _Settings(),
        hook=hook,
        client_factory=lambda _settings: client,
        pdf_renderer=lambda _markdown, _root: b"%PDF-1.7\n",
    )

    with pytest.raises(BatchRunnerError) as captured:
        executor(_context())

    assert captured.value.error_code == expected_code
    assert str(captured.value) == "formal provider HTTP request failed"
    assert captured.value.http_status == status
    assert captured.value.stage == "provider_call"
    assert captured.value.exception_type == "QwenClientError"
    assert "SENSITIVE_TEST_VALUE" not in str(captured.value)
    assert client.calls == 1
    assert not hook.is_registered("formal-run-001")
