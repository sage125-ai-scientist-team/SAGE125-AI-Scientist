"""Red test: registered booklet identity must survive a filename change."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from app.contracts.rag import SourceRecord, SourceRole, SourceType
from app.rag.library_manager import LibraryManager


def test_renamed_registered_booklet_is_not_treated_as_user_evidence(tmp_path):
    """An ingest hash must resolve registry identity independently of filename."""

    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    registry = {
        content_hash: SourceRecord(
            source_id="SOURCE-BOOKLET-125",
            content_hash=content_hash,
            source_type=SourceType.BOOKLET,
            source_role=SourceRole.QUESTION_SOURCE,
        )
    }
    captured_metadata = {}

    class CapturingIndexingService:
        def __init__(self, **_kwargs):
            pass

        def index_files(self, _paths, *, metadata_overrides, **_kwargs):
            captured_metadata.update(metadata_overrides)
            return {"status": "ok", "chunks": 1, "chunk_ids": ["CH-BOOKLET"]}

    uploads_dir = tmp_path / "uploads"
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
        manifest_path=uploads_dir / ".library_manifest.json",
        indexing_service_factory=CapturingIndexingService,
        source_registry=registry,
    )

    result = manager.ingest_files([("renamed booklet.pdf", pdf_bytes)])

    assert result["status"] == "ok"
    assert captured_metadata["content_sha256"] == content_hash
    assert captured_metadata["source_type"] == SourceType.BOOKLET.value
    assert captured_metadata["source_type"] != SourceType.PAPER.value
    assert captured_metadata["source_role"] == SourceRole.QUESTION_SOURCE.value
    assert captured_metadata["source_role"] != "user_literature"
