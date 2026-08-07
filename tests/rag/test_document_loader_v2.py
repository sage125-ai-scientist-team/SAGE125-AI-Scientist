"""Document loader v2 provenance and parse-state tests."""

from __future__ import annotations

import hashlib

from app.rag.document_loader import LOADER_VERSION, load_pdf


def _write_pdf(path) -> bytes:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text(
        (72, 72),
        "Introduction\nEvidence body. DOI: 10.1234/Loader.V2 https://example.test/paper",
    )
    pdf.set_metadata(
        {
            "author": "Ada Example; Bo Researcher",
            "subject": "A compact abstract for loader metadata.",
        }
    )
    pdf.set_toc([[1, "Introduction", 1]])
    pdf.save(path)
    pdf.close()
    return path.read_bytes()


def test_pdf_loader_v2_preserves_hash_status_and_metadata(tmp_path):
    path = tmp_path / "paper.pdf"
    content = _write_pdf(path)

    documents = load_pdf(str(path))

    assert len(documents) == 1
    metadata = documents[0].metadata
    assert metadata["content_sha256"] == hashlib.sha256(content).hexdigest()
    assert metadata["loader_version"] == LOADER_VERSION
    assert metadata["parse_status"] == "parsed"
    assert metadata["authors"] == ["Ada Example", "Bo Researcher"]
    assert metadata["abstract"] == "A compact abstract for loader metadata."
    assert metadata["doi"] == "10.1234/Loader.V2"
    assert metadata["url"] == "https://example.test/paper"
    assert metadata["sections"] == ["Introduction"]
    assert metadata["page"] == 1


def test_pdf_loader_v2_returns_failed_status_for_invalid_pdf(tmp_path):
    path = tmp_path / "broken.pdf"
    content = b"this is not a valid PDF"
    path.write_bytes(content)

    documents = load_pdf(str(path))

    assert len(documents) == 1
    assert documents[0].text == ""
    metadata = documents[0].metadata
    assert metadata["parse_status"] == "failed"
    assert metadata["content_sha256"] == hashlib.sha256(content).hexdigest()
    assert metadata["loader_version"] == LOADER_VERSION
    assert metadata["parse_error"]
