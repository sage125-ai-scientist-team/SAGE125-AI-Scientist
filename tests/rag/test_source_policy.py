"""Production SourcePolicy behavior and LibraryManager integration."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from app.contracts.rag import SourceRecord, SourceRole, SourceType
from app.rag.library_manager import LibraryManager
from app.rag.source_policy import RegistrySourcePolicy


def test_registry_source_policy_returns_registered_identity():
    content_hash = "a" * 64
    registered = SourceRecord(
        source_id="SOURCE-REGISTERED",
        content_hash=content_hash,
        source_type=SourceType.BOOKLET,
        source_role=SourceRole.QUESTION_SOURCE,
    )

    result = RegistrySourcePolicy().classify_source(
        filename="renamed.pdf",
        content_hash=content_hash.upper(),
        registry={content_hash: registered},
    )

    assert result is registered


def test_fresh_policies_recognize_renamed_booklet_from_stable_hash():
    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()

    original = RegistrySourcePolicy().classify_source(
        filename="sjtu-booklet.pdf",
        content_hash=content_hash,
        registry={},
    )
    renamed = RegistrySourcePolicy().classify_source(
        filename="renamed_booklet.pdf",
        content_hash=content_hash,
        registry={},
    )

    assert original.source_type is SourceType.BOOKLET
    assert original.source_role is SourceRole.QUESTION_SOURCE
    assert renamed == original


def test_registry_source_policy_uses_safe_default_for_unregistered_content():
    content_hash = "e" * 64

    result = RegistrySourcePolicy().classify_source(
        filename="definitely-a-paper.pdf",
        content_hash=content_hash,
        registry={},
    )

    assert result.source_type is SourceType.UNKNOWN
    assert result.source_role is SourceRole.USER_UPLOAD


def test_registry_source_policy_rejects_invalid_hash_and_registry_mismatch():
    policy = RegistrySourcePolicy()
    with pytest.raises(ValueError, match="full SHA-256"):
        policy.classify_source(filename="x.pdf", content_hash="bad", registry={})

    record = SourceRecord(
        source_id="SOURCE-X",
        content_hash="c" * 64,
        source_type=SourceType.PAPER,
        source_role=SourceRole.EXTERNAL_RETRIEVAL,
    )
    with pytest.raises(ValueError, match="must match"):
        policy.classify_source(
            filename="x.pdf",
            content_hash="c" * 64,
            registry={"d" * 64: record},
        )


def test_library_manager_calls_policy_and_persists_source_record(tmp_path):
    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    calls = []
    captured_metadata = {}

    class RecordingPolicy:
        def classify_source(self, *, filename, content_hash, registry):
            calls.append((filename, content_hash, registry))
            return SourceRecord(
                source_id="SOURCE-POLICY",
                content_hash=content_hash,
                source_type=SourceType.UNKNOWN,
                source_role=SourceRole.USER_UPLOAD,
            )

    class CapturingIndexingService:
        def __init__(self, **_kwargs):
            pass

        def index_files(self, _paths, *, metadata_overrides, **_kwargs):
            captured_metadata.update(metadata_overrides)
            return {"status": "ok", "chunks": 1, "chunk_ids": ["CH-POLICY"]}

    uploads_dir = tmp_path / "uploads"
    manifest_path = uploads_dir / ".library_manifest.json"
    manager = LibraryManager(
        settings=SimpleNamespace(
            max_upload_mb=25,
            library_max_files=500,
            library_max_total_mb=2048,
            library_max_chunks=100000,
            library_max_chunks_per_file=5000,
            library_max_index_mb=4096,
            library_min_free_mb=0,
            library_min_free_percent=0,
        ),
        uploads_dir=uploads_dir,
        index_dir=tmp_path / "index" / "user_library" / "zvec",
        manifest_path=manifest_path,
        indexing_service_factory=CapturingIndexingService,
        source_policy=RecordingPolicy(),
    )

    result = manager.ingest_files([("paper.pdf", pdf_bytes)])

    assert result["status"] == "ok"
    assert calls == [("paper.pdf", content_hash, {})]
    document = json.loads(manifest_path.read_text(encoding="utf-8"))["documents"][0]
    assert document["source_id"] == "SOURCE-POLICY"
    assert document["content_hash"] == content_hash
    assert document["source_type"] == SourceType.UNKNOWN.value
    assert document["source_role"] == SourceRole.USER_UPLOAD.value
    assert captured_metadata["source_id"] == "SOURCE-POLICY"
    assert captured_metadata["content_sha256"] == content_hash
    assert captured_metadata["source_type"] == SourceType.UNKNOWN.value
    assert captured_metadata["source_role"] == SourceRole.USER_UPLOAD.value
    assert "user_literature" not in captured_metadata.values()
