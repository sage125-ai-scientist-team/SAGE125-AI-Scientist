"""Validated migration of the legacy local RAG index into ``IndexConfig`` layout."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.contracts.rag import IndexConfig, MigrationDryRun


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MIGRATION_RECORD = "migration.json"


class IndexMigrationError(RuntimeError):
    """Raised when migration safety checks fail."""


def _legacy_paths(config: IndexConfig) -> tuple[Path, Path]:
    return config.index_root / "zvec", config.index_root / "chunks.jsonl"


def _validate_manifest(path: Path) -> int:
    """Validate JSONL structure and any hash fields exposed by the manifest."""

    if not path.is_file():
        raise IndexMigrationError(f"legacy chunks manifest is missing: {path}")
    count = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise IndexMigrationError(f"cannot read chunks manifest: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IndexMigrationError(
                f"invalid JSON in chunks manifest at line {line_number}"
            ) from exc
        if not isinstance(record, dict) or not str(record.get("chunk_id") or ""):
            raise IndexMigrationError(
                f"chunks manifest line {line_number} must contain chunk_id"
            )
        metadata = record.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise IndexMigrationError(
                f"chunks manifest line {line_number} metadata must be an object"
            )
        for field in ("source_hash", "content_sha256"):
            value = metadata.get(field)
            if value is not None and not _SHA256_PATTERN.fullmatch(str(value).lower()):
                raise IndexMigrationError(
                    f"chunks manifest line {line_number} has invalid {field}"
                )
        count += 1
    if count == 0:
        raise IndexMigrationError("chunks manifest contains no chunk records")
    return count


def _index_checksum(vector_dir: Path, manifest_path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        (path for path in vector_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(vector_dir).as_posix(),
    )
    if not files:
        raise IndexMigrationError(f"legacy vector index is empty: {vector_dir}")
    for path in files:
        relative = path.relative_to(vector_dir).as_posix()
        digest.update(b"vector\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    digest.update(b"manifest\0chunks.jsonl\0")
    digest.update(manifest_path.read_bytes())
    return digest.hexdigest()


def _assert_absent(path: Path, label: str) -> None:
    if path.exists():
        raise IndexMigrationError(f"{label} already exists: {path}")


@contextmanager
def _migration_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise IndexMigrationError(f"migration lock already exists: {path}") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def plan_index_migration(
    config: IndexConfig,
    *,
    expected_checksum: str | None = None,
) -> MigrationDryRun:
    """Validate legacy inputs and return a non-mutating migration plan."""

    source, source_manifest = _legacy_paths(config)
    if not source.is_dir():
        raise IndexMigrationError(f"legacy vector index is missing: {source}")
    _validate_manifest(source_manifest)
    _assert_absent(config.vector_index_dir, "target vector index")
    _assert_absent(config.chunks_manifest_path, "target chunks manifest")
    _assert_absent(config.migration_staging_dir, "migration staging directory")
    _assert_absent(config.backup_dir, "migration backup directory")
    checksum = _index_checksum(source, source_manifest)
    if expected_checksum is not None and checksum != expected_checksum.lower():
        raise IndexMigrationError(
            f"legacy index checksum mismatch: expected {expected_checksum.lower()}, got {checksum}"
        )
    return MigrationDryRun(
        source=source,
        target=config.vector_index_dir,
        checksum=checksum,
        rollback_available=False,
    )


def migrate_index(
    config: IndexConfig,
    *,
    dry_run: bool = True,
    expected_checksum: str | None = None,
) -> MigrationDryRun | dict[str, Any]:
    """Plan or execute a checked migration without rebuilding the index."""

    plan = plan_index_migration(config, expected_checksum=expected_checksum)
    if dry_run:
        return plan

    source, source_manifest = _legacy_paths(config)
    staging_vector = config.migration_staging_dir / "zvec"
    staging_manifest = config.migration_staging_dir / "chunks.jsonl"
    backup_vector = config.backup_dir / "zvec"
    backup_manifest = config.backup_dir / "chunks.jsonl"

    with _migration_lock(config.lock_path):
        # Re-plan under the lock so a stale dry-run cannot authorize a changed source.
        plan = plan_index_migration(config, expected_checksum=plan.checksum)
        try:
            config.migration_staging_dir.mkdir(parents=True)
            shutil.copytree(source, staging_vector)
            shutil.copy2(source_manifest, staging_manifest)
            _validate_manifest(staging_manifest)
            staged_checksum = _index_checksum(staging_vector, staging_manifest)
            if staged_checksum != plan.checksum:
                raise IndexMigrationError("staged index checksum differs from legacy source")

            config.backup_dir.mkdir(parents=True)
            source.replace(backup_vector)
            source_manifest.replace(backup_manifest)
            config.user_library_root.mkdir(parents=True, exist_ok=True)
            staging_vector.replace(config.vector_index_dir)
            staging_manifest.replace(config.chunks_manifest_path)
            (config.backup_dir / _MIGRATION_RECORD).write_text(
                json.dumps(
                    {
                        "schema_version": config.schema_version,
                        "checksum": plan.checksum,
                        "source": str(source),
                        "target": str(config.vector_index_dir),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            config.migration_staging_dir.rmdir()
        except Exception:
            if backup_vector.exists():
                if config.vector_index_dir.exists():
                    shutil.rmtree(config.vector_index_dir)
                if config.chunks_manifest_path.exists():
                    config.chunks_manifest_path.unlink()
                migration_record = config.backup_dir / _MIGRATION_RECORD
                if migration_record.exists():
                    migration_record.unlink()
            if not source.exists() and backup_vector.exists():
                backup_vector.replace(source)
            if not source_manifest.exists() and backup_manifest.exists():
                backup_manifest.replace(source_manifest)
            if config.migration_staging_dir.exists():
                shutil.rmtree(config.migration_staging_dir)
            if config.backup_dir.exists() and not any(config.backup_dir.iterdir()):
                config.backup_dir.rmdir()
            raise

    return {
        "status": "migrated",
        "source": str(source),
        "target": str(config.vector_index_dir),
        "checksum": plan.checksum,
        "rollback_available": True,
        "dry_run": False,
    }


def rollback_index_migration(config: IndexConfig) -> dict[str, Any]:
    """Restore the legacy layout when the migrated target is still unchanged."""

    source, source_manifest = _legacy_paths(config)
    backup_vector = config.backup_dir / "zvec"
    backup_manifest = config.backup_dir / "chunks.jsonl"
    record_path = config.backup_dir / _MIGRATION_RECORD
    if not record_path.is_file() or not backup_vector.is_dir() or not backup_manifest.is_file():
        raise IndexMigrationError("migration backup is incomplete; rollback is unavailable")
    _assert_absent(source, "legacy vector index")
    _assert_absent(source_manifest, "legacy chunks manifest")
    if not config.vector_index_dir.is_dir() or not config.chunks_manifest_path.is_file():
        raise IndexMigrationError("migrated target is incomplete; refusing rollback")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    target_checksum = _index_checksum(config.vector_index_dir, config.chunks_manifest_path)
    if target_checksum != record.get("checksum"):
        raise IndexMigrationError("migrated target changed after migration; refusing rollback")

    with _migration_lock(config.lock_path):
        shutil.rmtree(config.vector_index_dir)
        config.chunks_manifest_path.unlink()
        backup_vector.replace(source)
        backup_manifest.replace(source_manifest)
        record_path.unlink()
        config.backup_dir.rmdir()
        try:
            config.user_library_root.rmdir()
        except OSError:
            pass

    return {
        "status": "rolled_back",
        "source": str(config.vector_index_dir),
        "target": str(source),
        "checksum": target_checksum,
        "rollback_available": False,
        "dry_run": False,
    }
