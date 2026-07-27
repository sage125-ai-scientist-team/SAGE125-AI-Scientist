# -*- coding: utf-8 -*-
"""百炼嵌入异常的分类、脱敏与 UI 提示回归测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.clients.embedding_client import (
    EmbeddingClient,
    EmbeddingError,
    classify_embedding_error_text,
    classify_embedding_exception,
)
from app.ui.api_client import format_library_errors


def fake_sk_token() -> str:
    """构造只用于脱敏回归测试的假 Key。"""
    return "sk-" + ("x" * 32)


class _StatusError(Exception):
    """模拟仅在 response 上携带状态码的 OpenAI/httpx 异常。"""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.response = SimpleNamespace(status_code=status_code)


class ProxyError(Exception):
    pass


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        embedding_backend="bailian",
        bailian_embedding_model="text-embedding-v4",
        qwen_configured=True,
    )


@pytest.mark.parametrize(
    ("exc", "expected_code"),
    [
        (ProxyError("proxy tunnel failed"), "EMBEDDING_PROXY"),
        (APITimeoutError("request timed out"), "EMBEDDING_TIMEOUT"),
        (APIConnectionError("DNS name resolution failed"), "EMBEDDING_NETWORK"),
        (_StatusError("not allowed", 401), "EMBEDDING_AUTH"),
        (_StatusError("slow down", 429), "EMBEDDING_RATE_LIMIT"),
        (_StatusError("upstream unavailable", 503), "EMBEDDING_SERVICE"),
    ],
)
def test_embedding_exception_categories_are_stable(exc: Exception, expected_code: str):
    mapped = classify_embedding_exception(exc)
    assert mapped.code == expected_code
    assert str(mapped).startswith(f"[{expected_code}]")
    assert "smoke_bailian.py --embedding" in str(mapped) or expected_code == "EMBEDDING_RATE_LIMIT"


def test_embedding_exception_never_exposes_original_credentials():
    raw_key = fake_sk_token()
    raw_token = "topsecretbearertoken987654321"
    mapped = classify_embedding_exception(
        _StatusError(
            f"Authorization: Bearer {raw_token}; DASHSCOPE_API_KEY={raw_key}",
            401,
        )
    )

    assert mapped.code == "EMBEDDING_AUTH"
    assert raw_key not in str(mapped)
    assert raw_token not in str(mapped)
    assert "认证" in str(mapped)


def test_missing_dashscope_configuration_is_classified_as_config():
    assert (
        classify_embedding_error_text("DASHSCOPE_BASE_URL not configured")
        == "EMBEDDING_CONFIG"
    )


def test_embed_texts_maps_sdk_proxy_error_without_echoing_secret():
    raw_token = "proxybearertoken987654321"

    class _FailingEmbeddings:
        def create(self, **_kwargs):
            raise ProxyError(f"ProxyError Authorization: Bearer {raw_token}")

    client = EmbeddingClient(_settings())
    client._client = SimpleNamespace(embeddings=_FailingEmbeddings())

    with pytest.raises(EmbeddingError) as caught:
        client.embed_texts(["example"])

    assert caught.value.code == "EMBEDDING_PROXY"
    assert raw_token not in str(caught.value)
    msg = str(caught.value)
    # Canonical project proxy contract is OUTBOUND_HTTPS_PROXY only.
    assert "OUTBOUND_HTTPS_PROXY" in msg
    # Do not recommend implicit env proxies (avoid substring of OUTBOUND_HTTPS_PROXY).
    assert "HTTP_PROXY" not in msg
    assert "配置 HTTPS_PROXY" not in msg
    assert "环境变量 HTTPS_PROXY" not in msg
    # Must not echo credential-bearing proxy URLs from the raw exception.
    assert "Authorization" not in msg
    assert "Bearer" not in msg


def test_proxy_guidance_names_outbound_https_proxy_not_http_proxy():
    """项目正式代理契约是 OUTBOUND_HTTPS_PROXY，不得建议隐式 HTTP_PROXY。"""
    import re

    from app.clients.embedding_client import embedding_error_guidance

    text = embedding_error_guidance("EMBEDDING_PROXY")
    assert "OUTBOUND_HTTPS_PROXY" in text
    assert "HTTP_PROXY" not in text
    # Bare HTTPS_PROXY must not appear outside the OUTBOUND_ prefix.
    assert re.search(r"(?<!OUTBOUND_)HTTPS_PROXY", text) is None
    assert "Windows" in text


def test_embed_texts_rejects_incomplete_response():
    class _EmptyEmbeddings:
        def create(self, **_kwargs):
            return SimpleNamespace(data=[])

    client = EmbeddingClient(_settings())
    client._client = SimpleNamespace(embeddings=_EmptyEmbeddings())

    with pytest.raises(EmbeddingError) as caught:
        client.embed_texts(["example"])

    assert caught.value.code == "EMBEDDING_RESPONSE"
    assert "响应不完整" in str(caught.value)


def test_library_ui_maps_typed_embedding_error_and_deduplicates():
    raw_key = fake_sk_token()
    payload = {
        "errors": [
            f"paper.pdf: 原文件已保留，但索引失败：[EMBEDDING_AUTH] {raw_key}",
            "[EMBEDDING_AUTH] duplicate detail",
        ]
    }

    messages = format_library_errors(payload)

    assert len(messages) == 1
    assert "认证" in messages[0]
    assert "smoke_bailian.py --embedding" in messages[0]
    assert raw_key not in messages[0]


def test_library_ui_maps_legacy_network_error_to_actionable_chinese():
    messages = format_library_errors(
        {"errors": ["index_write_failed: APIConnectionError DNS name resolution failed"]}
    )

    assert len(messages) == 1
    assert "无法连接阿里云百炼嵌入服务" in messages[0]
    assert "smoke_bailian.py --embedding" in messages[0]


def test_library_ui_masks_unclassified_header_and_query_secrets():
    bearer = "bearersecret987654321"
    query_key = "plainapikey987654321"
    messages = format_library_errors(
        {
            "errors": [
                f"local failure Authorization: Bearer {bearer}; "
                f"https://localhost/test?api_key={query_key}"
            ]
        }
    )

    rendered = "；".join(messages)
    assert bearer not in rendered
    assert query_key not in rendered
    assert "MASKED" in rendered
