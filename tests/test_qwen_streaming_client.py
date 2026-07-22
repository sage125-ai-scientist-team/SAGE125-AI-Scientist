"""Streaming/non-thinking Model Studio client regression tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.clients.qwen_chat_client import QwenChatClient, QwenClientError
from app.core.config import Settings
from app.core.execution_mode import execution_mode
from app.core.run_progress import progress_reporting


def _settings(**overrides):
    values = {
        "DASHSCOPE_API_KEY": "sk-test-only-not-real",
        "WORKSPACE_ID": "ws-test",
        "DASHSCOPE_BASE_URL": "https://ws-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "LLM_MAX_RETRIES": 1,
        "LLM_MAX_OUTPUT_TOKENS": 1024,
    }
    values.update(overrides)
    return Settings(**values)


def _chunk(content=None, *, usage=None, chunk_id="chatcmpl-test"):
    choices = [] if content is None else [SimpleNamespace(delta=SimpleNamespace(content=content))]
    return SimpleNamespace(id=chunk_id, choices=choices, usage=usage)


class _Completions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return iter(outcome)


def _client(model_outcomes, **settings):
    c = QwenChatClient(_settings(**settings))
    completions = _Completions(model_outcomes)
    c._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return c, completions


def test_plus_json_stream_disables_thinking_and_collects_usage():
    usage = SimpleNamespace(prompt_tokens=7, completion_tokens=5, total_tokens=12)
    client, completions = _client([[_chunk('{"ok":'), _chunk("true}"), _chunk(usage=usage)]])
    events = []
    with execution_mode(False), progress_reporting(events.append):
        data = client.chat_json([{"role": "user", "content": "Return JSON"}], "qwen3.7-plus")
    assert data == {"ok": True}
    sent = completions.calls[0]
    assert sent["stream"] is True
    assert sent["stream_options"] == {"include_usage": True}
    assert sent["extra_body"]["enable_thinking"] is False
    assert sent["response_format"] == {"type": "json_object"}
    assert client.last_usage["total_tokens"] == 12
    assert any(event["status"] == "running" for event in events)


def test_max_uses_prompt_json_without_unsupported_response_format():
    client, completions = _client([[_chunk("```json\n{\"answer\": 1}\n```")]])
    with execution_mode(False):
        data = client.chat_json([{"role": "user", "content": "Return JSON"}], "qwen3.7-max")
    assert data == {"answer": 1}
    assert "response_format" not in completions.calls[0]
    assert completions.calls[0]["extra_body"]["enable_thinking"] is False


def test_retryable_connection_failure_retries_only_once():
    timeout_error = type("APITimeoutError", (Exception,), {})
    client, completions = _client([timeout_error("timed out"), [_chunk("ok")]])
    with execution_mode(False):
        assert client.chat([{"role": "user", "content": "hi"}], "qwen3.6-flash") == "ok"
    assert len(completions.calls) == 2


def test_auth_failure_is_not_retried_and_is_actionable():
    class AuthError(Exception):
        status_code = 401

    client, completions = _client([AuthError("bad token"), [_chunk("unused")]])
    with execution_mode(False), pytest.raises(QwenClientError, match="401"):
        client.chat([{"role": "user", "content": "hi"}], "qwen3.6-flash")
    assert len(completions.calls) == 1

