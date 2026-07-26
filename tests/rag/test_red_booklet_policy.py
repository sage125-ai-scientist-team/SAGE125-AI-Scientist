"""Red test: registered booklet identity must survive a filename change."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from app.contracts.rag import SourceRecord, SourceRole, SourceType
from app.rag.library_manager import LibraryManager


def test_renamed_registered_booklet_is_not_treated_as_user_evidence(tmp_path):
    """Expected red until LibraryManager implements the SourcePolicy behavior."""

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
    manager = LibraryManager(
        settings=SimpleNamespace(),
        uploads_dir=tmp_path / "uploads",
        index_dir=tmp_path / "index" / "user_library" / "zvec",
        manifest_path=tmp_path / "uploads" / ".library_manifest.json",
    )

    classified = manager.classify_source(
        filename="paper.pdf",
        content_hash=content_hash,
        registry=registry,
    )
    assert classified.source_type is SourceType.BOOKLET
    assert classified.source_role is SourceRole.QUESTION_SOURCE
