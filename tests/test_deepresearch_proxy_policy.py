"""Unit tests for the explicit, TLS-verifying DeepResearch outbound policy."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from app.clients.qwen_deep_research_client import QwenDeepResearchClient


def _settings(**overrides):
    values = {
        "deep_research_configured": True,
        "qwen_deep_research_model": "qwen-deep-research",
        "dashscope_deep_research_base_url": "https://workspace.example.aliyuncs.com/api/v1",
        "dashscope_api_key": "unit-test-key",
        "outbound_https_proxy": "",
        "deep_research_timeout_seconds": 12,
        "llm_max_retries": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _install_fake_dashscope(monkeypatch, call):
    module = types.SimpleNamespace(base_http_api_url=None, Generation=types.SimpleNamespace(call=call))
    monkeypatch.setitem(sys.modules, "dashscope", module)
    return module


def _answer_stream():
    response = SimpleNamespace(
        status_code=200,
        request_id="req-unit",
        usage={},
        output={"message": {"phase": "answer", "content": "brief", "extra": {}}},
    )
    return iter([response])


def test_deepresearch_without_explicit_proxy_is_direct_and_ignores_environment(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://ignored.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://ignored.invalid:8080")
    captured = {}

    def call(**kwargs):
        captured.update(kwargs)
        return _answer_stream()

    _install_fake_dashscope(monkeypatch, call)
    result = QwenDeepResearchClient(_settings()).run_deep_research("unit topic")

    session = captured["session"]
    assert result["status"] == "succeeded"
    assert session.trust_env is False
    assert session.verify is True
    assert session.proxies == {}
    assert captured["stream"] is True


def test_deepresearch_uses_only_explicit_project_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://ignored.invalid:8080")
    captured = {}

    def call(**kwargs):
        captured.update(kwargs)
        return _answer_stream()

    _install_fake_dashscope(monkeypatch, call)
    result = QwenDeepResearchClient(
        _settings(outbound_https_proxy="http://proxy.example:8443")
    ).run_deep_research("unit topic")

    session = captured["session"]
    assert result["status"] == "succeeded"
    assert session.trust_env is False
    assert session.verify is True
    assert session.proxies == {
        "http": "http://proxy.example:8443",
        "https": "http://proxy.example:8443",
    }


def test_deepresearch_redacts_proxy_credentials_from_error_and_log(monkeypatch, caplog):
    secret = "user:password"

    def call(**_kwargs):
        raise ConnectionError(f"ProxyError http://{secret}@proxy.example:8443 tunnel failed")

    _install_fake_dashscope(monkeypatch, call)
    result = QwenDeepResearchClient(_settings()).run_deep_research("unit topic")

    assert result["status"] == "failed"
    assert result["error_code"] == "DEEP_RESEARCH_PROXY"
    assert secret not in result["error"]
    assert secret not in caplog.text


def test_deepresearch_maps_connection_reset_to_stable_stage(monkeypatch):
    def call(**_kwargs):
        raise ConnectionError("[WinError 10054] An existing connection was forcibly closed")

    _install_fake_dashscope(monkeypatch, call)
    result = QwenDeepResearchClient(_settings()).run_deep_research("unit topic")

    assert result == {
        "status": "failed",
        "error": "DeepResearch HTTPS 流式连接被重置；请检查网络出口、VPN 或显式 HTTPS 代理。",
        "error_code": "DEEP_RESEARCH_CONNECTION_RESET",
        "error_stage": "http_stream_open",
        "content": "",
    }


def test_deepresearch_maps_http_status_and_retries_once(monkeypatch):
    calls = []
    monkeypatch.setattr("app.clients.qwen_deep_research_client.time.sleep", lambda _seconds: None)

    def call(**_kwargs):
        calls.append(True)
        if len(calls) == 1:
            return iter([SimpleNamespace(status_code=429, request_id="req-rate", usage={}, output=None)])
        return _answer_stream()

    _install_fake_dashscope(monkeypatch, call)
    result = QwenDeepResearchClient(_settings(llm_max_retries=1)).run_deep_research("unit topic")

    assert result["status"] == "succeeded"
    assert len(calls) == 2


def test_deepresearch_maps_5xx_and_timeout_without_unbounded_retry(monkeypatch):
    def service_call(**_kwargs):
        return iter([SimpleNamespace(status_code=503, request_id="req-service", usage={}, output=None)])

    _install_fake_dashscope(monkeypatch, service_call)
    service = QwenDeepResearchClient(_settings()).run_deep_research("unit topic")
    assert service["error_code"] == "DEEP_RESEARCH_SERVICE"

    def timeout_call(**_kwargs):
        raise TimeoutError("timed out")

    _install_fake_dashscope(monkeypatch, timeout_call)
    timeout = QwenDeepResearchClient(_settings()).run_deep_research("unit topic")
    assert timeout["error_code"] == "DEEP_RESEARCH_TIMEOUT"
