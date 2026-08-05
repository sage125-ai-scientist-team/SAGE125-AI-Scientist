"""DOI-first and content-hash document identity tests."""

from app.rag.document_registry import (
    DocumentRegistry,
    document_identity,
    normalize_doi,
)


def test_identity_prefers_normalized_doi():
    identity = document_identity(
        doi=" HTTPS://DOI.ORG/10.1234/Example.X ",
        content_sha256="a" * 64,
    )

    assert normalize_doi("doi:10.1234/EXAMPLE.X") == "10.1234/example.x"
    assert identity == "doi:10.1234/example.x"


def test_same_doi_different_files_is_duplicate():
    registry = DocumentRegistry()
    first = registry.register(
        filename="first.pdf", content_sha256="a" * 64, doi="10.1234/shared"
    )
    second = registry.register(
        filename="second.pdf", content_sha256="b" * 64, doi="10.1234/SHARED"
    )

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.duplicate_reason == "doi"
    assert second.record.filename == "first.pdf"


def test_same_content_different_filename_is_duplicate_without_doi():
    registry = DocumentRegistry()
    registry.register(filename="original.pdf", content_sha256="c" * 64)

    renamed = registry.register(filename="renamed.pdf", content_sha256="c" * 64)

    assert renamed.duplicate is True
    assert renamed.duplicate_reason == "content_sha256"
    assert renamed.record.identity == f"sha256:{'c' * 64}"
