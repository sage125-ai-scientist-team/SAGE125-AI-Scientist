"""Migration command safety and rollback behavior."""

from __future__ import annotations

import json

import pytest

from app.contracts.rag import IndexConfig, MigrationDryRun
from app.rag.index_migration import (
    IndexMigrationError,
    migrate_index,
    rollback_index_migration,
)


def _legacy_index(config: IndexConfig) -> None:
    vector_dir = config.index_root / "zvec"
    vector_dir.mkdir(parents=True)
    (vector_dir / "vectors.bin").write_bytes(b"offline-vector-fixture")
    (config.index_root / "chunks.jsonl").write_text(
        json.dumps(
            {
                "chunk_id": "CH-fixture",
                "text": "fixture",
                "metadata": {
                    "source_hash": "a" * 64,
                    "content_sha256": "b" * 64,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_migration_dry_run_validates_without_writing(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _legacy_index(config)

    plan = migrate_index(config)

    assert isinstance(plan, MigrationDryRun)
    assert plan.dry_run is True
    assert plan.source == config.index_root / "zvec"
    assert plan.target == config.vector_index_dir
    assert len(plan.checksum) == 64
    assert not config.vector_index_dir.exists()
    assert not config.migration_staging_dir.exists()
    assert not config.backup_dir.exists()
    assert not config.lock_path.exists()


def test_migration_rejects_target_conflict_and_checksum_mismatch(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _legacy_index(config)
    config.vector_index_dir.mkdir(parents=True)

    with pytest.raises(IndexMigrationError, match="target vector index already exists"):
        migrate_index(config)

    config.vector_index_dir.rmdir()
    with pytest.raises(IndexMigrationError, match="checksum mismatch"):
        migrate_index(config, expected_checksum="0" * 64)


def test_migration_rejects_invalid_manifest_hash(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _legacy_index(config)
    (config.index_root / "chunks.jsonl").write_text(
        json.dumps(
            {
                "chunk_id": "CH-invalid",
                "metadata": {"content_sha256": "not-a-sha256"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(IndexMigrationError, match="invalid content_sha256"):
        migrate_index(config)


def test_apply_migration_and_rollback_restore_legacy_layout(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _legacy_index(config)
    dry_run = migrate_index(config)

    result = migrate_index(config, dry_run=False, expected_checksum=dry_run.checksum)

    assert result["status"] == "migrated"
    assert result["rollback_available"] is True
    assert result["dry_run"] is False
    assert config.vector_index_dir.joinpath("vectors.bin").is_file()
    assert config.chunks_manifest_path.is_file()
    assert not (config.index_root / "zvec").exists()
    assert config.backup_dir.joinpath("migration.json").is_file()
    assert not config.lock_path.exists()

    rollback = rollback_index_migration(config)

    assert rollback["status"] == "rolled_back"
    assert (config.index_root / "zvec" / "vectors.bin").is_file()
    assert (config.index_root / "chunks.jsonl").is_file()
    assert not config.vector_index_dir.exists()
    assert not config.backup_dir.exists()
    assert not config.lock_path.exists()


def test_rollback_refuses_a_changed_migrated_target(tmp_path):
    config = IndexConfig(data_root=tmp_path / "data")
    _legacy_index(config)
    migrate_index(config, dry_run=False)
    (config.vector_index_dir / "vectors.bin").write_bytes(b"changed-after-migration")

    with pytest.raises(IndexMigrationError, match="changed after migration"):
        rollback_index_migration(config)

    assert config.vector_index_dir.is_dir()
    assert config.backup_dir.is_dir()
