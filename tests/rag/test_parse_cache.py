"""Versioned parse-cache behavior tests."""

from app.rag.document_loader import Document
from app.rag.parse_cache import ParseCache, parse_cache_key


def _documents(content_hash: str, version: str) -> list[Document]:
    return [
        Document(
            text="parsed text",
            metadata={
                "content_sha256": content_hash,
                "loader_version": version,
                "parse_status": "parsed",
            },
        )
    ]


def test_parse_cache_miss_then_hit(tmp_path):
    cache = ParseCache(tmp_path / "parse-cache")
    content_hash = "d" * 64

    assert cache.get(content_sha256=content_hash, loader_version="2.0") is None
    cache.put(
        content_sha256=content_hash,
        loader_version="2.0",
        documents=_documents(content_hash, "2.0"),
    )

    cached = cache.get(content_sha256=content_hash, loader_version="2.0")
    assert cached is not None
    assert cached[0].text == "parsed text"
    assert cached[0].metadata["parse_status"] == "parsed"


def test_loader_version_change_invalidates_cache(tmp_path):
    cache = ParseCache(tmp_path / "parse-cache")
    content_hash = "e" * 64
    cache.put(
        content_sha256=content_hash,
        loader_version="2.0",
        documents=_documents(content_hash, "2.0"),
    )

    assert cache.get(content_sha256=content_hash, loader_version="2.1") is None
    assert parse_cache_key(
        content_sha256=content_hash, loader_version="2.0"
    ) != parse_cache_key(content_sha256=content_hash, loader_version="2.1")
