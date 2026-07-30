"""Passing schema and fixture checks for the T04 internal RAG contract."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.contracts.rag import (
    INDEX_DATA_ROOT_ENV,
    INDEX_SCHEMA_VERSION_ENV,
    IndexConfig,
    IndexHealth,
    MigrationDryRun,
    RetrievalHit,
    ScoreKind,
    SourceLocator,
    SourceRole,
    SourceType,
)
from app.rag.library_manager import LibraryManager


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "initial_retrieval_gold.json"
SHA256 = "a" * 64


def test_index_config_derives_every_path_from_one_root():
    config = IndexConfig(data_root=Path("workspace-data"))
    assert config.index_root == Path("workspace-data/index")
    assert config.user_library_root == Path("workspace-data/index/user_library")
    assert config.vector_index_dir == Path("workspace-data/index/user_library/zvec")
    assert config.chunks_manifest_path == Path("workspace-data/index/user_library/chunks.jsonl")
    assert config.migration_staging_dir == Path("workspace-data/index/.migration_staging")
    assert config.backup_dir == Path("workspace-data/index/.migration_backup")
    assert config.lock_path == Path("workspace-data/index/.rag-index.lock")


def test_index_config_is_json_serializable_and_versioned():
    payload = json.loads(IndexConfig().model_dump_json())
    assert payload["schema_version"] == "1.0"
    assert payload["config_version"] == "1.0"
    assert Path(payload["vector_index_dir"]) == Path("data/index/user_library/zvec")


def test_index_config_rejects_parent_traversal():
    with pytest.raises(ValidationError, match="parent traversal"):
        IndexConfig(data_root="../data")


def test_index_config_resolution_precedence_is_env_config_default():
    config = IndexConfig.resolve(
        {"data_root": "configured-data", "schema_version": "2.0"},
        environ={
            INDEX_DATA_ROOT_ENV: "environment-data",
            INDEX_SCHEMA_VERSION_ENV: "3.0",
        },
    )
    assert config.data_root == Path("environment-data")
    assert config.schema_version == "3.0"

    configured = IndexConfig.resolve(
        {"data_root": "configured-data", "schema_version": "2.0"},
        environ={},
    )
    assert configured.data_root == Path("configured-data")
    assert configured.schema_version == "2.0"
    assert IndexConfig.resolve(environ={}) == IndexConfig()


def test_library_manager_uses_injected_index_config(tmp_path):
    config = IndexConfig(data_root=tmp_path / "configured-data")
    manager = LibraryManager(
        settings=SimpleNamespace(),
        uploads_dir=tmp_path / "uploads",
        index_config=config,
    )
    assert manager.index_dir == config.vector_index_dir
    assert manager.chunks_manifest_path == config.chunks_manifest_path


def test_index_health_has_four_exhaustive_states():
    assert set(IndexHealth) == {
        IndexHealth.READY,
        IndexHealth.DEGRADED,
        IndexHealth.MISSING,
        IndexHealth.MIGRATION_REQUIRED,
    }


def test_migration_dry_run_is_a_non_executing_serializable_contract():
    proposal = MigrationDryRun(
        source="data/index/zvec",
        target="data/index/user_library/zvec",
        checksum=SHA256.upper(),
        rollback_available=True,
    )
    assert proposal.checksum == SHA256
    assert proposal.dry_run is True
    payload = json.loads(proposal.model_dump_json())
    assert Path(payload.pop("source")) == Path("data/index/zvec")
    assert Path(payload.pop("target")) == Path("data/index/user_library/zvec")
    assert payload == {
        "checksum": SHA256,
        "rollback_available": True,
        "dry_run": True,
    }
    with pytest.raises(ValidationError):
        MigrationDryRun(
            source="same",
            target="same",
            checksum=SHA256,
            rollback_available=False,
        )


def test_source_type_and_source_role_are_orthogonal():
    assert set(SourceType) == {
        SourceType.PAPER,
        SourceType.BOOKLET,
        SourceType.WEB,
        SourceType.DATASET,
        SourceType.UNKNOWN,
    }
    assert SourceRole.USER_UPLOAD not in set(SourceType)


def test_pdf_locator_requires_positive_page():
    locator = SourceLocator(document_id="DOC-1", page=3, chunk_id="CH-1")
    assert locator.page == 3
    assert locator.source_id == "DOC-1"
    with pytest.raises(ValidationError):
        SourceLocator(document_id="DOC-1", page=0, chunk_id="CH-1")


def test_non_pdf_locator_requires_an_actual_location():
    with pytest.raises(ValidationError, match="non-page source"):
        SourceLocator(document_id="DOC-1")
    locator = SourceLocator(
        document_id="DOC-1", section="Methods", char_start=10, char_end=40
    )
    assert locator.page is None


def test_character_range_is_complete_and_ordered():
    with pytest.raises(ValidationError, match="provided together"):
        SourceLocator(document_id="DOC-1", chunk_id="CH-1", char_start=2)
    with pytest.raises(ValidationError, match="greater"):
        SourceLocator(
            document_id="DOC-1", chunk_id="CH-1", char_start=20, char_end=20
        )


def test_retrieval_hit_preserves_structured_provenance():
    hit = RetrievalHit(
        chunk_id="CH-1",
        quoted_text="Exact source passage.",
        retrieval_score=1.82,
        score_kind=ScoreKind.RERANK_SCORE,
        source_type=SourceType.PAPER,
        source_role=SourceRole.SYSTEM_FIXTURE,
        source_locator=SourceLocator(
            document_id="DOC-1", page=2, section="Results", chunk_id="CH-1"
        ),
        content_hash=SHA256.upper(),
        title="Offline contract fixture",
        doi="10.1234/fixture",
        url="https://example.invalid/fixture",
        metadata={"dataset_role": "contract_fixture"},
    )
    assert hit.content_hash == SHA256
    assert hit.source_locator.page == 2
    assert hit.quoted_text == "Exact source passage."
    assert hit.retrieval_score == 1.82


def test_retrieval_hit_rejects_blank_quote_bad_hash_and_mismatched_chunk():
    base = {
        "chunk_id": "CH-1",
        "quoted_text": "quote",
        "retrieval_score": 0.5,
        "score_kind": "vector_similarity",
        "source_type": "paper",
        "source_role": "system_fixture",
        "source_locator": SourceLocator(document_id="DOC-1", chunk_id="CH-1"),
        "content_hash": SHA256,
        "title": "Fixture",
    }
    with pytest.raises(ValidationError):
        RetrievalHit(**{**base, "quoted_text": "  "})
    with pytest.raises(ValidationError):
        RetrievalHit(**{**base, "content_hash": "abc"})
    with pytest.raises(ValidationError, match="finite"):
        RetrievalHit(**{**base, "retrieval_score": float("inf")})
    with pytest.raises(ValidationError, match="must match"):
        RetrievalHit(
            **{
                **base,
                "source_locator": SourceLocator(
                    document_id="DOC-1", chunk_id="CH-OTHER"
                ),
            }
        )


def test_initial_gold_set_has_exactly_twenty_provisional_contract_queries():
    records = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(records) == 20
    assert len({record["query_id"] for record in records}) == 20
    required = {
        "query_id", "query", "domain", "expected_source_type",
        "expected_fixture_ids", "forbidden_source_types", "annotation_status",
        "rationale", "version", "dataset_role",
        "expected_source_role",
    }
    for record in records:
        assert required <= record.keys()
        assert record["dataset_role"] == "contract_fixture"
        assert record["annotation_status"] == "provisional"
        assert record["version"] == "0.1"
        assert record["expected_fixture_ids"]
        assert "booklet" in record["forbidden_source_types"]
        assert record["expected_source_role"] == "system_fixture"
