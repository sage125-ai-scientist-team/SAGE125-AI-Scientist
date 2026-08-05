"""Atomic local-index rebuild with validation, backup, and recovery."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from app.contracts.rag import IndexConfig


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BuildIndex = Callable[[Path], None]
ValidateIndex = Callable[[Path], None]
MovePath = Callable[[Path, Path], None]


class IndexRebuildError(RuntimeError):
    """Raised when a rebuild cannot complete without risking the current index."""


class IndexRebuildLockTimeout(IndexRebuildError):
    """Raised when another rebuild owns the exclusive writer lock."""


def _remove_tree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _move_path(source: Path, target: Path) -> None:
    source.replace(target)


def validate_index_tree(path: Path) -> None:
    """Validate the complete user-library index before it can become current."""
    vector_dir = path / "zvec"
    manifest_path = path / "chunks.jsonl"
    if not vector_dir.is_dir():
        raise IndexRebuildError("staging vector index is missing")
    if not any(item.is_file() for item in vector_dir.rglob("*")):
        raise IndexRebuildError("staging vector index is empty")
    if not manifest_path.is_file():
        raise IndexRebuildError("staging chunks manifest is missing")

    chunk_count = 0
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise IndexRebuildError(f"cannot read staging chunks manifest: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IndexRebuildError(
                f"invalid staging chunks manifest at line {line_number}"
            ) from exc
        if not isinstance(record, dict) or not str(record.get("chunk_id") or ""):
            raise IndexRebuildError(
                f"staging chunks manifest line {line_number} must contain chunk_id"
            )
        metadata = record.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise IndexRebuildError(
                f"staging chunks manifest line {line_number} metadata must be an object"
            )
        for field in ("content_sha256", "source_hash"):
            value = metadata.get(field)
            if value is not None and not _SHA256_RE.fullmatch(str(value).lower()):
                raise IndexRebuildError(
                    f"staging chunks manifest line {line_number} has invalid {field}"
                )
        chunk_count += 1
    if chunk_count == 0:
        raise IndexRebuildError("staging chunks manifest contains no chunks")

    build_manifest = path / "index_manifest.json"
    if build_manifest.exists():
        try:
            payload = json.loads(build_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexRebuildError("staging index manifest is invalid") from exc
        if not isinstance(payload, dict):
            raise IndexRebuildError("staging index manifest must be an object")
        declared_count = payload.get("chunk_count")
        if declared_count is not None and int(declared_count) != chunk_count:
            raise IndexRebuildError("staging index manifest chunk_count mismatch")


class IndexRebuilder:
    """Build off-path, validate, then replace the current index under one lock."""

    def __init__(
        self,
        config: IndexConfig,
        *,
        build: BuildIndex,
        validate: ValidateIndex = validate_index_tree,
        lock_timeout: float = 0.0,
        poll_interval: float = 0.05,
        move: MovePath = _move_path,
    ) -> None:
        if lock_timeout < 0:
            raise ValueError("lock_timeout must be non-negative")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.config = config
        self.build = build
        self.validate = validate
        self.lock_timeout = lock_timeout
        self.poll_interval = poll_interval
        self.move = move
        self.target = config.user_library_root
        self.staging = config.index_root / ".rebuild-staging"
        self.backup = config.index_root / ".rebuild-backup"

    @contextmanager
    def _lock(self) -> Iterator[None]:
        lock_path = self.config.lock_path
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.lock_timeout
        descriptor = -1
        while descriptor < 0:
            try:
                descriptor = os.open(
                    lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except FileExistsError as exc:
                if time.monotonic() >= deadline:
                    raise IndexRebuildLockTimeout(
                        f"index rebuild lock timeout: {lock_path}"
                    ) from exc
                time.sleep(min(self.poll_interval, max(0.0, deadline - time.monotonic())))
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            descriptor = -1
            yield
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def _cleanup_staging_unlocked(self) -> bool:
        existed = self.staging.exists() or self.staging.is_symlink()
        if existed:
            _remove_tree(self.staging)
        return existed

    def cleanup_staging(self) -> bool:
        """Remove a staging tree left by a terminated process."""
        with self._lock():
            return self._cleanup_staging_unlocked()

    def _restore_backup(self) -> None:
        if self.target.exists() or self.target.is_symlink():
            _remove_tree(self.target)
        if self.backup.exists():
            self.move(self.backup, self.target)

    def rebuild(self) -> dict[str, object]:
        """Build and validate staging, then switch while retaining a backup."""
        with self._lock():
            self._cleanup_staging_unlocked()
            self.staging.mkdir(parents=True)
            had_current = self.target.exists()
            moved_current = False
            try:
                self.build(self.staging)
                self.validate(self.staging)

                if self.backup.exists() or self.backup.is_symlink():
                    _remove_tree(self.backup)
                if had_current:
                    self.move(self.target, self.backup)
                    moved_current = True
                try:
                    self.move(self.staging, self.target)
                    self.validate(self.target)
                except Exception:
                    if moved_current:
                        self._restore_backup()
                    raise
            except Exception as exc:
                self._cleanup_staging_unlocked()
                if moved_current and not self.target.exists() and self.backup.exists():
                    self.move(self.backup, self.target)
                if isinstance(exc, IndexRebuildError):
                    raise
                raise IndexRebuildError(f"index rebuild failed: {exc}") from exc

            return {
                "status": "rebuilt",
                "target": str(self.target),
                "backup": str(self.backup) if moved_current else None,
                "rollback_available": moved_current,
            }

    def rollback(self) -> dict[str, object]:
        """Restore the validated backup and discard the current rebuilt index."""
        with self._lock():
            if not self.backup.is_dir():
                raise IndexRebuildError("rebuild backup is unavailable")
            self.validate(self.backup)
            discarded = self.config.index_root / ".rebuild-discarded"
            if discarded.exists() or discarded.is_symlink():
                _remove_tree(discarded)
            moved_current = False
            try:
                if self.target.exists():
                    self.move(self.target, discarded)
                    moved_current = True
                self.move(self.backup, self.target)
            except Exception as exc:
                if moved_current and not self.target.exists() and discarded.exists():
                    self.move(discarded, self.target)
                raise IndexRebuildError(f"index rollback failed: {exc}") from exc
            _remove_tree(discarded)
            return {
                "status": "rolled_back",
                "target": str(self.target),
                "rollback_available": False,
            }
