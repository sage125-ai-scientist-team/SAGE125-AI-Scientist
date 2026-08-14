"""Gate B1 hardening tests; all embeddings and indexes are test-only fakes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.contracts.rag import SourceRole, SourceType
from app.rag.frozen_chunk_builder import (
    EmbeddingIdentity,
    FrozenChunkBuildError,
    FrozenChunkValidationError,
    FrozenChunksIndexBuilder,
    ProductionBuildAuthorization,
    load_frozen_chunks,
)
from app.rag.retriever import LocalRAGRetriever
from app.rag.zvec_store import MemoryVectorStore, SearchResult


FROZEN_SHA = "205b7e0c44805fe568cd9d20cd5760862f906b5be4453ecb011deca7d9d14d46"


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


class ClaimedProductionEmbedder(DeterministicFakeEmbedder):
    identity = EmbeddingIdentity(
        backend="bailian",
        model="text-embedding-v4",
        version="gate-b2-stub",
        fake=False,
    )


class TestFileStore:
    """Filesystem-backed fake used only to exercise staging and rename semantics."""

    __test__ = False

    def __init__(self, index_dir, *, fail_at=None):
        self.index_dir = Path(index_dir)
        self.fail_at = fail_at
        self.chunks = []
        self.vectors = []
        self.persist_calls = 0

    def add_documents(self, chunks, embeddings):
        self.index_dir.mkdir(parents=True, exist_ok=True)
        (self.index_dir / "vectors.test-only").write_bytes(b"not-a-production-index")
        if self.fail_at == "add":
            raise RuntimeError("add failed")
        self.chunks = list(chunks)
        self.vectors = list(embeddings)

    def persist(self):
        self.persist_calls += 1
        if self.fail_at == "persist":
            raise RuntimeError("persist failed")

    def load(self):
        if self.fail_at == "load":
            raise RuntimeError("load failed")

    def search(self, _query_embedding, top_k, filters=None):
        results = []
        for chunk in self.chunks:
            if filters and any(chunk.metadata.get(k) != v for k, v in filters.items()):
                continue
            results.append(SearchResult(chunk.chunk_id, 0.75, chunk.text, chunk.metadata))
        return results[:top_k]

    def delete_documents(self, _chunk_ids):
        return 0


class TestStoreFactory:
    __test__ = False

    def __init__(self, *, fail_at=None, memory=False):
        self.fail_at = fail_at
        self.memory = memory
        self.store = None
        self.dimension = "unset"
        self.index_dir = None

    def __call__(self, *, dimension, index_dir):
        self.dimension = dimension
        self.index_dir = index_dir
        if self.memory:
            self.store = MemoryVectorStore(dimension=dimension)
        else:
            self.store = TestFileStore(index_dir, fail_at=self.fail_at)
        return self.store


def _record(index: int, *, document_index: int | None = None, production=False) -> dict:
    document_index = document_index if document_index is not None else index % 5
    chunk_id = f"CH-{index:04d}"
    document_id = f"DOC-{document_index}"
    digest = hashlib.sha256(f"document-{document_index}".encode()).hexdigest()
    text = f"Exact frozen quoted passage {index}."
    origin = "controlled archive" if production else "UNKNOWN"
    custodian = "controlled evidence team" if production else "UNKNOWN"
    license_value = "authorized internal evaluation" if production else "UNKNOWN"
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
            "authors": ["Verified Author"] if production else ["Test Fixture Author"],
            "doi": f"10.1234/test.{document_index}" if production else "UNKNOWN",
            "url": None if production else "UNKNOWN",
            "loader_version": "2.0",
            "page": index + 1,
            "section": "Results",
            "char_start": 4,
            "char_end": 4 + len(text),
            "locator": {
                "document_id": document_id,
                "page": index + 1,
                "section": "Results",
                "chunk_id": chunk_id,
                "char_start": 4,
                "char_end": 4 + len(text),
            },
            "provenance": {
                "origin": origin,
                "custodian": custodian,
                "license_or_authorization": license_value,
            },
            "synthetic": False,
            "fixture": not production,
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


def _authorization(digest: str, **updates) -> ProductionBuildAuthorization:
    values = {
        "production_embedding_authorized": True,
        "embedding_model": "text-embedding-v4",
        "frozen_chunks_sha256": digest,
        "index_build_authorized": True,
        "mock_embedding_allowed": False,
        "local_qwen_allowed": False,
        "fallback_allowed": False,
        "captain_authorization_reference": "CAPTAIN-GATE-B2-TEST-CONTRACT",
    }
    values.update(updates)
    return ProductionBuildAuthorization(**values)


def _builder(embedder=None, factory=None, **kwargs):
    embedder = embedder or DeterministicFakeEmbedder()
    factory = factory or TestStoreFactory()
    return FrozenChunksIndexBuilder(
        embedder=embedder,
        vector_store_factory=factory,
        vector_store_backend=kwargs.pop("vector_store_backend", "test-only"),
        **kwargs,
    ), embedder, factory


def _build_test_only(tmp_path: Path, records: list[dict], **kwargs):
    chunks_path = tmp_path / "chunks.jsonl"
    digest = _write_records(chunks_path, records)
    builder, embedder, factory = _builder(**kwargs)
    result = builder.build(
        chunks_path,
        expected_sha256=digest,
        index_dir=tmp_path / "published-index",
        production=False,
    )
    return result, embedder, factory


def test_happy_path_loads_167_chunks_and_atomically_publishes_test_index(tmp_path):
    result, embedder, factory = _build_test_only(
        tmp_path, [_record(index) for index in range(167)]
    )
    assert result.record_count == 167
    assert result.document_count == 5
    assert result.embedding_dimension == 3
    assert result.production is False
    assert result.fake is True
    assert len(factory.store.chunks) == 167
    assert factory.store.persist_calls == 1
    assert embedder.calls == 1
    manifest = json.loads((result.index_dir / "index_manifest.json").read_text())
    assert manifest["ready"] is True
    assert manifest["production"] is False
    assert manifest["fake"] is True


def test_locator_normalizes_to_downstream_source_locator_without_loss(tmp_path):
    original = _record(7, document_index=2)
    frozen_path = tmp_path / "chunks.jsonl"
    digest = _write_records(frozen_path, [original])
    frozen = load_frozen_chunks(frozen_path, expected_sha256=digest)
    metadata = frozen.chunks[0].metadata
    assert metadata["source_locator"] == original["metadata"]["locator"]
    assert metadata["locator"] == metadata["source_locator"]


def test_end_to_end_builder_store_retrieval_hit_preserves_locator(tmp_path):
    original = _record(7, document_index=2, production=True)
    _, _, factory = _build_test_only(tmp_path, [original])

    class QueryEmbedding:
        def embed_texts(self, _texts):
            return [[1.0, 0.0, 0.0]]

    class Reranker:
        last_used_fallback = False

        def rerank(self, _query, _documents, top_k):
            return [(0, 0.9)][:top_k]

    retriever = LocalRAGRetriever(QueryEmbedding(), Reranker(), factory.store)
    hit = retriever.retrieve_hits("prime distribution")[0]
    locator = hit.source_locator
    expected = original["metadata"]["locator"]
    assert locator.document_id == expected["document_id"]
    assert locator.chunk_id == expected["chunk_id"]
    assert locator.page == expected["page"]
    assert locator.section == expected["section"]
    assert locator.char_start == expected["char_start"]
    assert locator.char_end == expected["char_end"]
    assert hit.quoted_text == original["text"]
    assert hit.content_hash == original["metadata"]["content_sha256"]


def test_conflicting_locator_representations_fail_closed(tmp_path):
    record = _record(1)
    record["metadata"]["source_locator"] = dict(record["metadata"]["locator"])
    record["metadata"]["source_locator"]["page"] += 1
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    with pytest.raises(FrozenChunkValidationError, match="conflicting locator.page"):
        load_frozen_chunks(path, expected_sha256=digest)


def test_identity_quote_hash_and_provenance_are_lossless(tmp_path):
    original = _record(7, document_index=2)
    _, _, factory = _build_test_only(tmp_path, [original])
    stored = factory.store.chunks[0]
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


@pytest.mark.parametrize("field", ["text", "quoted_text"])
def test_empty_text_or_quote_fails_closed(tmp_path, field):
    record = _record(1)
    if field == "text":
        record["text"] = "  "
    else:
        record["metadata"]["quoted_text"] = "  "
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    with pytest.raises(FrozenChunkValidationError):
        load_frozen_chunks(path, expected_sha256=digest)


@pytest.mark.parametrize(
    "mutation",
    [
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


def test_frozen_file_hash_mismatch_fails_closed(tmp_path):
    path = tmp_path / "chunks.jsonl"
    _write_records(path, [_record(1)])
    with pytest.raises(FrozenChunkValidationError, match="SHA-256 mismatch"):
        load_frozen_chunks(path, expected_sha256="0" * 64)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda m: m.update(authors=[]), "authors"),
        (lambda m: m.pop("authors"), "authors"),
        (lambda m: m.update(doi="UNKNOWN", url="UNKNOWN"), "DOI/URL"),
        (lambda m: m.update(doi="not-a-doi", url=None), "RetrievalHit"),
        (lambda m: m["provenance"].update(origin="UNKNOWN"), "origin"),
        (lambda m: m["provenance"].update(custodian="TBD"), "custodian"),
        (lambda m: m["provenance"].update(custodian="  pLaCeHoLdEr "), "custodian"),
    ],
)
def test_production_provenance_rejects_before_embedding(tmp_path, mutation, message):
    record = _record(1, production=True)
    mutation(record["metadata"])
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [record])
    embedder = ClaimedProductionEmbedder()
    builder, _, _ = _builder(
        embedder=embedder,
        vector_store_backend="zvec",
    )
    with pytest.raises(FrozenChunkBuildError, match=message):
        builder.build(
            path,
            expected_sha256=digest,
            index_dir=tmp_path / "index",
            production=True,
            authorization=_authorization(digest),
        )
    assert embedder.calls == 0


@pytest.mark.parametrize(
    "identity",
    [
        EmbeddingIdentity("custom", "text-embedding-v4", "1", fake=False),
        EmbeddingIdentity("bailian", "other-model", "1", fake=False),
        EmbeddingIdentity("bailian", "text-embedding-v4", "1", fake=True),
    ],
)
def test_production_embedder_identity_guard_rejects_before_call(tmp_path, identity):
    class MisreportedEmbedder(ClaimedProductionEmbedder):
        pass

    embedder = MisreportedEmbedder()
    embedder.identity = identity
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [_record(1, production=True)])
    builder, _, _ = _builder(embedder=embedder, vector_store_backend="zvec")
    with pytest.raises(FrozenChunkBuildError):
        builder.build(
            path,
            expected_sha256=digest,
            index_dir=tmp_path / "index",
            production=True,
            authorization=_authorization(digest),
        )
    assert embedder.calls == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"captain_authorization_reference": ""},
        {"index_build_authorized": False},
        {"production_embedding_authorized": False},
        {"fallback_allowed": True},
        {"local_qwen_allowed": True},
        {"mock_embedding_allowed": True},
        {"embedding_model": "other-model"},
    ],
)
def test_production_authorization_guard_rejects_before_call(tmp_path, updates):
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [_record(1, production=True)])
    embedder = ClaimedProductionEmbedder()
    builder, _, _ = _builder(embedder=embedder, vector_store_backend="zvec")
    with pytest.raises(FrozenChunkBuildError):
        builder.build(
            path,
            expected_sha256=digest,
            index_dir=tmp_path / "index",
            production=True,
            authorization=_authorization(digest, **updates),
        )
    assert embedder.calls == 0


def test_memory_vector_store_is_rejected_before_embedding(tmp_path):
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [_record(1, production=True)])
    embedder = ClaimedProductionEmbedder()
    factory = TestStoreFactory(memory=True)
    builder, _, _ = _builder(
        embedder=embedder, factory=factory, vector_store_backend="zvec"
    )
    with pytest.raises(FrozenChunkBuildError, match="MemoryVectorStore"):
        builder.build(
            path,
            expected_sha256=digest,
            index_dir=tmp_path / "index",
            production=True,
            authorization=_authorization(digest),
        )
    assert embedder.calls == 0


def test_mock_vector_store_environment_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCK_VECTOR_STORE", "true")
    path = tmp_path / "chunks.jsonl"
    digest = _write_records(path, [_record(1, production=True)])
    embedder = ClaimedProductionEmbedder()
    builder, _, _ = _builder(embedder=embedder, vector_store_backend="zvec")
    with pytest.raises(FrozenChunkBuildError, match="MOCK_VECTOR_STORE"):
        builder.build(
            path,
            expected_sha256=digest,
            index_dir=tmp_path / "index",
            production=True,
            authorization=_authorization(digest),
        )
    assert embedder.calls == 0


def test_fake_test_only_build_can_never_report_production(tmp_path):
    result, _, _ = _build_test_only(tmp_path, [_record(1)])
    assert result.production is False
    manifest = json.loads((result.index_dir / "index_manifest.json").read_text())
    assert manifest == {**manifest, "production": False, "fake": True}


@pytest.mark.parametrize("fail_at", ["add", "persist", "load"])
def test_build_failure_leaves_no_new_final_index(tmp_path, fail_at):
    target = tmp_path / "index"
    factory = TestStoreFactory(fail_at=fail_at)
    with pytest.raises(FrozenChunkBuildError):
        _build_test_only(tmp_path, [_record(1)], factory=factory)
    assert not target.exists()
    assert not list(tmp_path.glob(".*.staging-*"))


def test_validation_failure_leaves_no_new_final_index(tmp_path):
    def reject(_staging, _frozen):
        raise RuntimeError("validation failed")

    with pytest.raises(FrozenChunkBuildError, match="validation failed"):
        _build_test_only(tmp_path, [_record(1)], staging_validator=reject)
    assert not (tmp_path / "published-index").exists()


@pytest.mark.parametrize("corruption", ["count", "hash"])
def test_manifest_count_or_hash_mismatch_leaves_no_final_index(tmp_path, corruption):
    def corrupt(staging, _frozen):
        path = staging / "index_manifest.json"
        payload = json.loads(path.read_text())
        if corruption == "count":
            payload["record_count"] += 1
        else:
            payload["source_chunks_sha256"] = "0" * 64
        path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(FrozenChunkBuildError, match="count mismatch|hash mismatch"):
        _build_test_only(tmp_path, [_record(1)], staging_validator=corrupt)
    assert not (tmp_path / "published-index").exists()


def test_failure_preserves_existing_final_index(tmp_path):
    target = tmp_path / "published-index"
    target.mkdir()
    marker = target / "existing.marker"
    marker.write_text("keep", encoding="utf-8")
    factory = TestStoreFactory(fail_at="persist")
    with pytest.raises(FrozenChunkBuildError):
        _build_test_only(tmp_path, [_record(1)], factory=factory)
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not (target / "index_manifest.json").exists()


def test_success_replaces_existing_final_only_after_validation(tmp_path):
    target = tmp_path / "published-index"
    target.mkdir()
    (target / "old.marker").write_text("old", encoding="utf-8")
    result, _, _ = _build_test_only(tmp_path, [_record(1)])
    assert result.index_dir == target
    assert not (target / "old.marker").exists()
    assert (target / "index_manifest.json").is_file()
    assert not list(tmp_path.glob(".*.backup-*"))


def test_builder_never_calls_real_embedding_client(tmp_path, monkeypatch):
    from app.clients.embedding_client import EmbeddingClient

    real_calls = 0

    def forbidden_call(*_args, **_kwargs):
        nonlocal real_calls
        real_calls += 1
        raise AssertionError("real provider embedding must not be called")

    monkeypatch.setattr(EmbeddingClient, "embed_texts", forbidden_call)
    result, _, _ = _build_test_only(tmp_path, [_record(1)])
    assert result.record_count == 1
    assert real_calls == 0
