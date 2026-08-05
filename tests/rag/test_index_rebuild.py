"""Atomic index rebuild, rollback, cleanup, and writer-lock tests."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from app.contracts.rag import IndexConfig
from app.rag.index_rebuild import (
    IndexRebuildError,
    IndexRebuildLockTimeout,
    IndexRebuilder,
)


def _write_index(path: Path, marker: str, *, valid: bool = True) -> None:
    vector_dir = path / "zvec"
    vector_dir.mkdir(parents=True)
    (vector_dir / "vectors.bin").write_bytes(marker.encode("utf-8"))
    manifest = path / "chunks.jsonl"
    if valid:
        manifest.write_text(
            json.dumps(
                {
                    "chunk_id": f"CH-{marker}",
                    "text": marker,
                    "metadata": {"content_sha256": "a" * 64},
                }
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        manifest.write_text("not-json\n", encoding="utf-8")


def _marker(path: Path) -> str:
    return (path / "zvec" / "vectors.bin").read_text(encoding="utf-8")


def test_rebuild_from_empty_index(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    rebuilder = IndexRebuilder(config, build=lambda path: _write_index(path, "new"))

    result = rebuilder.rebuild()

    assert result["status"] == "rebuilt"
    assert result["rollback_available"] is False
    assert _marker(config.user_library_root) == "new"
    assert not rebuilder.staging.exists()
    assert not config.lock_path.exists()


def test_damaged_current_index_is_replaced_only_after_staging_validates(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _write_index(config.user_library_root, "damaged", valid=False)
    rebuilder = IndexRebuilder(config, build=lambda path: _write_index(path, "healthy"))

    result = rebuilder.rebuild()

    assert result["rollback_available"] is True
    assert _marker(config.user_library_root) == "healthy"
    assert _marker(rebuilder.backup) == "damaged"


def test_build_interruption_keeps_current_and_cleans_staging(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _write_index(config.user_library_root, "current")

    def interrupted(path: Path) -> None:
        (path / "partial").write_text("partial", encoding="utf-8")
        raise RuntimeError("builder interrupted")

    rebuilder = IndexRebuilder(config, build=interrupted)
    with pytest.raises(IndexRebuildError, match="builder interrupted"):
        rebuilder.rebuild()

    assert _marker(config.user_library_root) == "current"
    assert not rebuilder.staging.exists()


def test_validation_failure_keeps_current_index(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _write_index(config.user_library_root, "current")
    rebuilder = IndexRebuilder(
        config,
        build=lambda path: _write_index(path, "invalid", valid=False),
    )

    with pytest.raises(IndexRebuildError, match="invalid staging chunks manifest"):
        rebuilder.rebuild()

    assert _marker(config.user_library_root) == "current"
    assert not rebuilder.backup.exists()


def test_switch_failure_automatically_restores_current(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _write_index(config.user_library_root, "current")

    def fail_staging_move(source: Path, target: Path) -> None:
        if source.name == ".rebuild-staging":
            raise OSError("simulated switch failure")
        source.replace(target)

    rebuilder = IndexRebuilder(
        config,
        build=lambda path: _write_index(path, "new"),
        move=fail_staging_move,
    )
    with pytest.raises(IndexRebuildError, match="simulated switch failure"):
        rebuilder.rebuild()

    assert _marker(config.user_library_root) == "current"
    assert not rebuilder.staging.exists()


def test_successful_rebuild_can_rollback(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _write_index(config.user_library_root, "old")
    rebuilder = IndexRebuilder(config, build=lambda path: _write_index(path, "new"))
    rebuilder.rebuild()

    result = rebuilder.rollback()

    assert result["status"] == "rolled_back"
    assert _marker(config.user_library_root) == "old"
    assert not rebuilder.backup.exists()


def test_crashed_staging_can_be_cleaned(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    rebuilder = IndexRebuilder(config, build=lambda path: _write_index(path, "new"))
    rebuilder.staging.mkdir(parents=True)
    (rebuilder.staging / "partial").write_text("partial", encoding="utf-8")

    assert rebuilder.cleanup_staging() is True
    assert not rebuilder.staging.exists()
    assert rebuilder.cleanup_staging() is False


def test_concurrent_rebuild_is_rejected_by_writer_lock(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    entered = threading.Event()
    release = threading.Event()
    errors: list[Exception] = []

    def slow_build(path: Path) -> None:
        entered.set()
        release.wait(timeout=2)
        _write_index(path, "first")

    first = IndexRebuilder(config, build=slow_build)

    def run_first() -> None:
        try:
            first.rebuild()
        except Exception as exc:  # pragma: no cover - asserted through errors
            errors.append(exc)

    thread = threading.Thread(target=run_first)
    thread.start()
    assert entered.wait(timeout=1)
    second = IndexRebuilder(
        config,
        build=lambda path: _write_index(path, "second"),
        lock_timeout=0.05,
        poll_interval=0.01,
    )
    with pytest.raises(IndexRebuildLockTimeout):
        second.rebuild()
    release.set()
    thread.join(timeout=2)

    assert errors == []
    assert not thread.is_alive()
    assert _marker(config.user_library_root) == "first"


def test_lock_timeout_waits_then_leaves_lock_untouched(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    config.lock_path.parent.mkdir(parents=True)
    config.lock_path.write_text("other-writer", encoding="utf-8")
    rebuilder = IndexRebuilder(
        config,
        build=lambda path: _write_index(path, "new"),
        lock_timeout=0.06,
        poll_interval=0.01,
    )

    started = time.monotonic()
    with pytest.raises(IndexRebuildLockTimeout, match="lock timeout"):
        rebuilder.rebuild()

    assert time.monotonic() - started >= 0.05
    assert config.lock_path.read_text(encoding="utf-8") == "other-writer"
