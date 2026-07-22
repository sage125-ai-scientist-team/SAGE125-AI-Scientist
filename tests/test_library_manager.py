"""本地用户文献库的隔离、去重、配额和删除契约。"""

from __future__ import annotations

import json
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

from app.rag.library_manager import LibraryManager


_DiskUsage = namedtuple("_DiskUsage", "total used free")


def _settings(**overrides):
    values = {
        "max_upload_mb": 2,
        "library_max_batch_files": 10,
        "library_max_batch_mb": 4,
        "library_max_files": 20,
        "library_max_raw_mb": 4,
        "library_max_index_mb": 4,
        "library_max_chunks": 100,
        "library_max_chunks_per_file": 10,
        "library_min_free_mb": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _IndexLedger:
    """记录 fake index/delete 调用，避免测试触发真实 embedding。"""

    def __init__(self):
        self.index_calls: list[dict] = []
        self.chunk_ids: set[str] = set()
        self.delete_calls: list[list[str]] = []
        self.persist_calls = 0

    def indexing_service_factory(self, *, index_dir):
        ledger = self

        class _Indexer:
            def index_files(
                self,
                paths,
                *,
                is_user_upload,
                metadata_overrides,
                max_chunks,
            ):
                document_id = metadata_overrides["library_document_id"]
                chunk_ids = [f"{document_id}-C1", f"{document_id}-C2"]
                ledger.index_calls.append(
                    {
                        "index_dir": index_dir,
                        "paths": list(paths),
                        "is_user_upload": is_user_upload,
                        "metadata_overrides": dict(metadata_overrides),
                        "max_chunks": max_chunks,
                        "chunk_ids": chunk_ids,
                    }
                )
                ledger.chunk_ids.update(chunk_ids)
                return {
                    "status": "ok",
                    "chunks": len(chunk_ids),
                    "chunk_ids": chunk_ids,
                    "errors": [],
                }

        return _Indexer()

    def vector_store_factory(self, *, index_dir):
        ledger = self

        class _Store:
            def delete_documents(self, chunk_ids):
                ids = [str(x) for x in chunk_ids]
                ledger.delete_calls.append(ids)
                before = len(ledger.chunk_ids)
                ledger.chunk_ids.difference_update(ids)
                return before - len(ledger.chunk_ids)

            def persist(self):
                ledger.persist_calls += 1

        return _Store()


def _manager(tmp_path: Path, ledger: _IndexLedger, *, settings=None, free_bytes=10 * 1024**3):
    uploads = tmp_path / "uploads"
    index_dir = tmp_path / "user-index" / "zvec"
    return LibraryManager(
        settings=settings or _settings(),
        uploads_dir=uploads,
        index_dir=index_dir,
        manifest_path=uploads / ".library_manifest.json",
        indexing_service_factory=ledger.indexing_service_factory,
        vector_store_factory=ledger.vector_store_factory,
        disk_usage_fn=lambda _path: _DiskUsage(20 * 1024**3, 1 * 1024**3, free_bytes),
    )


def test_booklet_is_rejected_and_user_documents_use_dedicated_scope(tmp_path):
    ledger = _IndexLedger()
    manager = _manager(tmp_path, ledger)

    rejected = manager.ingest_files([("sjtu-booklet.pdf", b"%PDF-1.4\n%%EOF")])
    assert rejected["status"] == "failed"
    assert rejected["documents"] == []
    assert ledger.index_calls == []
    assert manager.get_status()["usage"]["file_count"] == 0

    accepted = manager.ingest_files([("paper.txt", b"user supplied scientific evidence")])
    assert accepted["status"] == "ok"
    assert len(ledger.index_calls) == 1
    call = ledger.index_calls[0]
    assert Path(call["index_dir"]) == tmp_path / "user-index" / "zvec"
    assert call["is_user_upload"] is True
    assert call["metadata_overrides"]["source_role"] == "user_literature"
    assert call["metadata_overrides"]["source_path"].startswith("library://DOC-")
    assert "sjtu-booklet" not in json.dumps(call, ensure_ascii=False).lower()


def test_same_content_different_name_is_deduplicated_across_restart(tmp_path):
    ledger = _IndexLedger()
    content = b"the same reusable literature"

    first = _manager(tmp_path, ledger).ingest_files([("first.txt", content)])
    assert first["status"] == "ok"
    assert first["duplicates"] == []
    assert len(ledger.index_calls) == 1

    second_manager = _manager(tmp_path, ledger)
    second = second_manager.ingest_files([("renamed.txt", content)])
    assert second["status"] == "ok"
    assert second["files"] == []
    assert second["duplicates"] == ["renamed.txt"]
    assert len(ledger.index_calls) == 1, "重复内容不得再次 embedding/index"

    status = second_manager.get_status()
    assert status["usage"]["file_count"] == 1
    assert status["usage"]["indexed_file_count"] == 1
    assert status["usage"]["chunk_count"] == 2
    assert len(status["documents"]) == 1
    assert status["documents"][0]["name"] == "first.txt"
    public_blob = json.dumps(status, ensure_ascii=False)
    assert "stored_name" not in public_blob
    assert "sha256" not in public_blob
    assert str(tmp_path) not in public_blob


def test_batch_raw_capacity_and_low_disk_are_rejected_without_indexing(tmp_path):
    batch_ledger = _IndexLedger()
    batch_manager = _manager(
        tmp_path / "batch",
        batch_ledger,
        settings=_settings(library_max_batch_files=1),
    )
    batch = batch_manager.ingest_files([("a.txt", b"a"), ("b.txt", b"b")])
    assert batch["status"] == "failed"
    assert batch_ledger.index_calls == []
    assert batch_manager.get_status()["usage"]["file_count"] == 0

    capacity_ledger = _IndexLedger()
    capacity_manager = _manager(
        tmp_path / "capacity",
        capacity_ledger,
        settings=_settings(library_max_raw_mb=1, library_max_batch_mb=2),
    )
    assert capacity_manager.ingest_files([("first.txt", b"x" * 700_000)])["status"] == "ok"
    over_capacity = capacity_manager.ingest_files([("second.txt", b"y" * 400_000)])
    assert over_capacity["status"] == "failed"
    assert any("容量" in message for message in over_capacity["rejected"])
    assert len(capacity_ledger.index_calls) == 1
    assert capacity_manager.get_status()["usage"]["file_count"] == 1

    low_disk_ledger = _IndexLedger()
    content = b"cannot fit below reserve"
    reserve = 1024**2
    low_disk_manager = _manager(
        tmp_path / "low-disk",
        low_disk_ledger,
        settings=_settings(library_min_free_mb=1),
        free_bytes=reserve + len(content) - 1,
    )
    low_disk = low_disk_manager.ingest_files([("paper.txt", content)])
    assert low_disk["status"] == "failed"
    assert any("磁盘" in message for message in low_disk["rejected"])
    assert low_disk_ledger.index_calls == []
    assert low_disk_manager.get_status()["usage"]["file_count"] == 0


def test_delete_removes_raw_vectors_manifest_and_is_idempotent(tmp_path):
    ledger = _IndexLedger()
    manager = _manager(tmp_path, ledger)
    result = manager.ingest_files([("delete-me.txt", b"private reusable literature")])
    document = result["documents"][0]
    document_id = document["document_id"]
    raw_files_before = [p for p in (tmp_path / "uploads").iterdir() if not p.name.startswith(".")]

    assert len(raw_files_before) == 1
    expected_chunk_ids = set(ledger.index_calls[0]["chunk_ids"])
    assert ledger.chunk_ids == expected_chunk_ids

    deleted = manager.delete_document(document_id)
    assert deleted["status"] == "ok"
    assert deleted["deleted"] is True
    assert len(ledger.delete_calls) == 1
    assert set(ledger.delete_calls[0]) == expected_chunk_ids
    assert ledger.chunk_ids == set()
    assert ledger.persist_calls == 1
    assert not raw_files_before[0].exists()

    status = manager.get_status()
    assert status["usage"]["file_count"] == 0
    assert status["usage"]["chunk_count"] == 0
    manifest = json.loads((tmp_path / "uploads" / ".library_manifest.json").read_text(encoding="utf-8"))
    assert manifest["documents"] == []

    repeated = manager.delete_document(document_id)
    assert repeated == {"status": "not_found", "document_id": document_id, "deleted": False}
    assert len(ledger.delete_calls) == 1


def test_index_failure_keeps_original_and_reports_partial(tmp_path):
    """嵌入/索引失败时原文件仍永久保留，但接口不得误报完全成功。"""
    ledger = _IndexLedger()

    def failing_factory(*, index_dir):
        class _FailingIndexer:
            def index_files(self, paths, **kwargs):
                return {
                    "status": "failed",
                    "chunks": 0,
                    "chunk_ids": [],
                    "errors": ["embedding temporarily unavailable"],
                }

        return _FailingIndexer()

    uploads = tmp_path / "uploads"
    manager = LibraryManager(
        settings=_settings(),
        uploads_dir=uploads,
        index_dir=tmp_path / "user-index" / "zvec",
        manifest_path=uploads / ".library_manifest.json",
        indexing_service_factory=failing_factory,
        vector_store_factory=ledger.vector_store_factory,
        disk_usage_fn=lambda _path: _DiskUsage(20 * 1024**3, 1 * 1024**3, 10 * 1024**3),
    )

    result = manager.ingest_files([("keep-me.txt", b"private literature remains on disk")])
    assert result["status"] == "partial"
    assert result["files"] == ["keep-me.txt"]
    assert any("原文件已保留" in message for message in result["errors"])
    status = manager.get_status()
    assert status["usage"]["file_count"] == 1
    assert status["usage"]["failed_file_count"] == 1
    assert status["documents"][0]["status"] == "index_failed"
    assert len([path for path in uploads.iterdir() if not path.name.startswith(".")]) == 1


def test_failed_document_can_retry_from_retained_original_without_reupload(tmp_path):
    ledger = _IndexLedger()

    def failing_factory(*, index_dir):
        class _FailingIndexer:
            def index_files(self, paths, **kwargs):
                return {
                    "status": "failed",
                    "chunks": 0,
                    "chunk_ids": [],
                    "errors": ["temporary embedding connection error"],
                }

        return _FailingIndexer()

    uploads = tmp_path / "uploads"
    manager = LibraryManager(
        settings=_settings(),
        uploads_dir=uploads,
        index_dir=tmp_path / "user-index" / "zvec",
        manifest_path=uploads / ".library_manifest.json",
        indexing_service_factory=failing_factory,
        vector_store_factory=ledger.vector_store_factory,
        disk_usage_fn=lambda _path: _DiskUsage(20 * 1024**3, 1 * 1024**3, 10 * 1024**3),
    )
    content = b"retained literature can be indexed later"
    initial = manager.ingest_files([("retry-me.txt", content)])
    document_id = initial["documents"][0]["document_id"]
    raw_path = next(path for path in uploads.iterdir() if not path.name.startswith("."))
    raw_name = raw_path.name

    # Simulate restoring connectivity without asking the caller for file bytes again.
    manager.indexing_service_factory = ledger.indexing_service_factory
    retried = manager.retry_document(document_id)

    assert retried["status"] == "ok"
    assert retried["retried"] is True
    assert retried["chunks_added"] == 2
    assert retried["document"]["status"] == "indexed"
    assert raw_path.name == raw_name
    assert raw_path.read_bytes() == content
    assert len(ledger.index_calls) == 1
    assert ledger.index_calls[0]["paths"] == [str(raw_path.resolve())]
    manifest = json.loads((uploads / ".library_manifest.json").read_text(encoding="utf-8"))
    record = manifest["documents"][0]
    assert record["retry_count"] == 1
    assert record["status"] == "indexed"
    assert record["error"] == ""

    # A repeated request is an idempotent no-op and does not embed twice.
    repeated = manager.retry_document(document_id)
    assert repeated["status"] == "ok"
    assert repeated["retried"] is False
    assert repeated["chunks_added"] == 0
    assert len(ledger.index_calls) == 1


def test_retry_revalidates_retained_file_and_keeps_chunk_quota(tmp_path):
    ledger = _IndexLedger()

    def failing_factory(*, index_dir):
        class _FailingIndexer:
            def index_files(self, paths, **kwargs):
                return {"status": "failed", "chunks": 0, "chunk_ids": [], "errors": ["offline"]}

        return _FailingIndexer()

    uploads = tmp_path / "uploads"
    settings = _settings()
    manager = LibraryManager(
        settings=settings,
        uploads_dir=uploads,
        index_dir=tmp_path / "user-index" / "zvec",
        manifest_path=uploads / ".library_manifest.json",
        indexing_service_factory=failing_factory,
        vector_store_factory=ledger.vector_store_factory,
        disk_usage_fn=lambda _path: _DiskUsage(20 * 1024**3, 1 * 1024**3, 10 * 1024**3),
    )
    content = b"hash protected retained source"
    initial = manager.ingest_files([("protected.txt", content)])
    document_id = initial["documents"][0]["document_id"]
    raw_path = next(path for path in uploads.iterdir() if not path.name.startswith("."))
    manager.indexing_service_factory = ledger.indexing_service_factory

    raw_path.write_bytes(b"x" * len(content))
    invalid = manager.retry_document(document_id)
    assert invalid["status"] == "failed"
    assert invalid["retried"] is False
    assert "校验失败" in invalid["message"]
    assert ledger.index_calls == []

    raw_path.write_bytes(content)
    settings.library_max_chunks = 0
    over_quota = manager.retry_document(document_id)
    assert over_quota["status"] == "failed"
    assert "chunk" in over_quota["message"]
    assert ledger.index_calls == []
    assert raw_path.read_bytes() == content


def test_retry_failed_documents_retries_only_failed_records(tmp_path):
    ledger = _IndexLedger()
    should_fail = {"value": True}

    def switching_factory(*, index_dir):
        if not should_fail["value"]:
            return ledger.indexing_service_factory(index_dir=index_dir)

        class _FailingIndexer:
            def index_files(self, paths, **kwargs):
                return {"status": "failed", "chunks": 0, "chunk_ids": [], "errors": ["offline"]}

        return _FailingIndexer()

    uploads = tmp_path / "uploads"
    manager = LibraryManager(
        settings=_settings(),
        uploads_dir=uploads,
        index_dir=tmp_path / "user-index" / "zvec",
        manifest_path=uploads / ".library_manifest.json",
        indexing_service_factory=switching_factory,
        vector_store_factory=ledger.vector_store_factory,
        disk_usage_fn=lambda _path: _DiskUsage(20 * 1024**3, 1 * 1024**3, 10 * 1024**3),
    )
    first = manager.ingest_files([("a.txt", b"first failed source")])
    second = manager.ingest_files([("b.txt", b"second failed source")])
    assert first["status"] == second["status"] == "partial"

    should_fail["value"] = False
    result = manager.retry_failed_documents()
    assert result["status"] == "ok"
    assert result["attempted_count"] == 2
    assert result["retried_count"] == 2
    assert result["succeeded_count"] == 2
    assert result["failed_count"] == 0
    assert result["chunks_added"] == 4
    assert len(ledger.index_calls) == 2
    assert result["library"]["usage"]["indexed_file_count"] == 2
    assert result["library"]["usage"]["failed_file_count"] == 0

    no_op = manager.retry_failed_documents()
    assert no_op["status"] == "ok"
    assert no_op["attempted_count"] == 0
    assert no_op["results"] == []


def test_retry_unknown_document_is_side_effect_free(tmp_path):
    ledger = _IndexLedger()
    manager = _manager(tmp_path, ledger)

    result = manager.retry_document("DOC-does-not-exist")

    assert result == {
        "status": "not_found",
        "document_id": "DOC-does-not-exist",
        "retried": False,
        "chunks_added": 0,
    }
    assert ledger.index_calls == []
    assert manager.get_status()["usage"]["file_count"] == 0
