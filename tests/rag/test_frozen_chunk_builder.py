"""Gate B1 tests for direct, provider-free frozen chunk consumption."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.rag.frozen_chunk_builder import (
    EmbeddingIdentity,
    FrozenChunkBuildError,
    FrozenChunkValidationError,
    FrozenChunksIndexBuilder,
    load_frozen_chunks,
)


class DeterministicFakeEmbedder:
    identity = EmbeddingIdentity(
        backend="deterministic-test-fake",
        model="gate-b1-test-only",
        version="1",
        fake=True,
    )

    def __init__(self) -> None:
        self.calls = 0

    def embed_texts(self, texts):
        self.calls += 1
        return [[float(len(text)), float(index), 1.0] for index, text in enumerate(texts)]


class CapturingStore:
    def __init__(self) -> None:
        self.chunks = []
        self.vectors = []
        self.persist_calls = 0

    def add_documents(self, chunks, embeddings):
        self.chunks = list(chunks)
        self.vectors = list(embeddings)

    def persist(self):
        self.persist_calls += 1


class CapturingStoreFactory:
    def __init__(self) -> None:
        self.store = CapturingStore()
        self.dimension = None
        self.index_dir = None

    def __call__(self, *, dimension, index_dir):
        self.dimension = dimension
        self.index_dir = index_dir
        return self.store


def _record(index: int, *, document_index: int | None = None) -> dict:
    document_index = document_index if document_index is not None else index % 5
    chunk_id = f"CH-{index:04d}"
    document_id = f"DOC-{document_index}"
    digest = hashlib.sha256(f"document-{document_index}".encode()).hexdigest()
    text = f"Exact frozen quoted passage {index}."
    return {
        "chunk_id": chunk_id,
        "text": text,
        "metadata": {
            "chunk_id": chunk_id,
            "quoted_text": text,
            "document_id": document_id,
            "doc_id": document_id,
            "source_id": f"SOURCE-{document_index}",
            "source_name": f"Q001_EVIDENCE_{document_index + 1:03d}.pdf",
            "content_sha256": digest,
            "source_sha256": digest,
            "source_type": "paper",
            "source_role": "external_retrieval",
            "title": f"Verified paper {document_index}",
            "authors": ["Verified Author"],
            "doi": "UNKNOWN",
            "url": "UNKNOWN",
            "loader_version": "2.0",
            "page": index + 1,
            "locator": {
                "document_id": document_id,
                "page": index + 1,
                "chunk_id": chunk_id,
                "char_start": 0,
                "char_end": len(text),
            },
            "provenance": {
                "origin": "UNKNOWN",
                "custodian": "UNKNOWN",
                "license_or_authorization": "UNKNOWN",
            },
            "synthetic": False,
            "fixture": False,
            "provisional": False,
        },
    }


def _write_records(path: Path, records: list[dict]) -> str:
    payload = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    ).encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _build(tmp_path: Path, records: list[dict], *, production: bool = False):
    chunks_path = tmp_path / "chunks.jsonl"
    digest = _write_records(chunks_path, records)
    embedder = DeterministicFakeEmbedder()
    factory = CapturingStoreFactory()
    builder = FrozenChunksIndexBuilder(
        embedder=embedder,
        vector_store_factory=factory,
    )
    result = builder.build(
        chunks_path,
        expected_sha256=digest,
        index_dir=tmp_path / "index" / "zvec",
        production=production,
    )
    return result, embedder, factory


def test_happy_path_loads_167_frozen_chunks_and_five_documents(tmp_path):
    records = [_record(index) for index in range(167)]
    result, embedder, factory = _build(tmp_path, records)

    assert result.record_count == 167
    assert result.document_count == 5
    assert result.embedding_dimension == 3
    assert result.production is False
    assert result.fake is True
    assert len(factory.store.chunks) == 167
    assert factory.store.persist_calls == 1
    assert embedder.calls == 1


def test_identity_quote_locator_hash_and_provenance_are_lossless(tmp_path):
    original = _record(7, document_index=2)
    result, _, factory = _build(tmp_path, [original])
    stored = factory.store.chunks[0]

    assert result.record_count == 1
    assert stored.chunk_id == original["chunk_id"]
    assert stored.text == original["text"]
    for field in (
        "document_id",
        "source_id",
        "source_type",
        "source_role",
        "title",
        "content_sha256",
        "source_sha256",
        "doi",
        "url",
        "loader_version",
        "locator",
        "provenance",
    ):
        assert stored.metadata[field] == original["metadata"][field]


def test_malformed_jsonl_fails_closed(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FrozenChunkValidationError, match="malformed JSON"):
        load_frozen_chunks(path, expected_sha256=digest)


def test_duplicate_chunk_id_fails_closed(tmp_path):
    record = _record(1)
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record, record])
    with pytest.raises(FrozenChunkValidationError, match="duplicate chunk_id"):
        load_frozen_chunks(path, expected_sha256=digest)


@pytest.mark.parametrize("value", [None, "short", "g" * 64])
def test_missing_or_invalid_content_hash_fails_closed(tmp_path, value):
    record = _record(1)
    record["metadata"]["content_sha256"] = value
    record["metadata"].pop("source_sha256", None)
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    with pytest.raises(FrozenChunkValidationError, match="content_hash"):
        load_frozen_chunks(path, expected_sha256=digest)


def test_empty_text_fails_closed(tmp_path):
    record = _record(1)
    record["text"] = "  "
    record["metadata"]["quoted_text"] = "  "
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    with pytest.raises(FrozenChunkValidationError, match="text must be non-empty"):
        load_frozen_chunks(path, expected_sha256=digest)


def test_missing_quote_fails_closed(tmp_path):
    record = _record(1)
    record["metadata"].pop("quoted_text")
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    with pytest.raises(FrozenChunkValidationError, match="quoted_text"):
        load_frozen_chunks(path, expected_sha256=digest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda locator: locator.pop("document_id"),
        lambda locator: locator.update(page=0),
        lambda locator: locator.update(chunk_id="CH-other"),
    ],
)
def test_invalid_locator_fails_closed(tmp_path, mutation):
    record = _record(1)
    mutation(record["metadata"]["locator"])
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    with pytest.raises(FrozenChunkValidationError, match="locator"):
        load_frozen_chunks(path, expected_sha256=digest)


@pytest.mark.parametrize(
    ("field", "value"),
    [("source_type", "research_pdf"), ("source_role", "scientific_evidence")],
)
def test_invalid_source_taxonomy_fails_closed(tmp_path, field, value):
    record = _record(1)
    record["metadata"][field] = value
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    with pytest.raises(FrozenChunkValidationError, match="source_type/source_role"):
        load_frozen_chunks(path, expected_sha256=digest)


@pytest.mark.parametrize(
    "field",
    [
        "document_id",
        "source_id",
        "source_name",
        "title",
        "loader_version",
        "provenance",
    ],
)
def test_missing_provenance_identity_fails_closed(tmp_path, field):
    record = _record(1)
    record["metadata"].pop(field)
    if field == "document_id":
        record["metadata"].pop("doc_id")
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    with pytest.raises(FrozenChunkValidationError):
        load_frozen_chunks(path, expected_sha256=digest)


def test_frozen_file_hash_mismatch_fails_before_record_use(tmp_path):
    path = tmp_path / "chunks.jsonl"
    _write_records(path, [_record(1)])
    with pytest.raises(FrozenChunkValidationError, match="SHA-256 mismatch"):
        load_frozen_chunks(path, expected_sha256="0" * 64)


def test_fake_embedding_cannot_build_production_index(tmp_path):
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [_record(1)])
    embedder = DeterministicFakeEmbedder()
    factory = CapturingStoreFactory()
    builder = FrozenChunksIndexBuilder(embedder=embedder, vector_store_factory=factory)

    with pytest.raises(FrozenChunkBuildError, match="fake embedding"):
        builder.build(
            path,
            expected_sha256=digest,
            index_dir=tmp_path / "index",
            production=True,
        )
    assert embedder.calls == 0
    assert factory.store.chunks == []


def test_builder_never_calls_real_embedding_client(tmp_path, monkeypatch):
    from app.clients.embedding_client import EmbeddingClient

    real_calls = 0

    def forbidden_call(*_args, **_kwargs):
        nonlocal real_calls
        real_calls += 1
        raise AssertionError("real provider embedding must not be called")

    monkeypatch.setattr(EmbeddingClient, "embed_texts", forbidden_call)
    result, _, _ = _build(tmp_path, [_record(1)])
    assert result.record_count == 1
    assert real_calls == 0
