"""Red test: registered booklet identity must survive a filename change."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from app.contracts.rag import SourceRole, SourceType
from app.rag.library_manager import LibraryManager


def test_fresh_manager_excludes_renamed_booklet_by_stable_content_identity(
    tmp_path,
):
    """A cold-start manager rejects a renamed booklet using only its hash."""

    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
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
    )

    renamed = manager.ingest_files([("renamed_booklet.pdf", pdf_bytes)])

    assert renamed["status"] == "failed"
    assert captured_metadata == {}
    classified = manager.source_policy.classify_source(
        filename="another_name.pdf", content_hash=content_hash, registry={}
    )
    assert classified.source_type is SourceType.BOOKLET
    assert classified.source_role is SourceRole.QUESTION_SOURCE
    assert manager.get_status()["documents"] == []
    assert manager.get_status()["usage"]["file_count"] == 0
