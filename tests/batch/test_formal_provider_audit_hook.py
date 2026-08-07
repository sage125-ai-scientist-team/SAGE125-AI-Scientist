"""Offline integration tests for the formal provider audit-hook runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.batch.errors import BatchRunnerError
from app.batch.formal_provider_runtime import (
    ProviderAuditHook,
    build_formal_provider_executor,
)
from app.clients.qwen_chat_client import QwenClientError


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
            "references": [],
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


def test_hook_is_registered_before_provider_call_and_seals_legal_audit() -> None:
    hook = ProviderAuditHook()
    client = _FakeClient(hook)
    executor = build_formal_provider_executor(
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


def test_unavailable_hook_blocks_before_provider_call() -> None:
    hook = ProviderAuditHook(available=False)
    client = _FakeClient(hook)
    executor = build_formal_provider_executor(
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
    executor = build_formal_provider_executor(
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

    executor = build_formal_provider_executor(
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
    executor = build_formal_provider_executor(
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
    executor = build_formal_provider_executor(
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
    executor = build_formal_provider_executor(
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
