"""T04 internal contracts for RAG configuration and retrieval results.

These models deliberately do not replace ``app.core.schemas.EvidenceCard``.
They define the boundary owned by T04; adapters to workflow/T01 are separate
production work.
"""

from __future__ import annotations

import re
from enum import Enum
from math import isfinite
from os import environ as process_environ
from pathlib import Path, PurePath
from typing import Any, Literal, Mapping, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
INDEX_DATA_ROOT_ENV = "SAGE_RAG_DATA_ROOT"
INDEX_SCHEMA_VERSION_ENV = "SAGE_RAG_SCHEMA_VERSION"


class SourceType(str, Enum):
    """Semantic type of the source content."""

    PAPER = "paper"
    BOOKLET = "booklet"
    WEB = "web"
    DATASET = "dataset"
    UNKNOWN = "unknown"


class SourceRole(str, Enum):
    """Operational provenance, independent from semantic source type."""

    USER_UPLOAD = "user_upload"
    QUESTION_SOURCE = "question_source"
    EXTERNAL_RETRIEVAL = "external_retrieval"
    SYSTEM_FIXTURE = "system_fixture"


class ScoreKind(str, Enum):
    """Scale carried by ``retrieval_score``; different kinds are not comparable."""

    VECTOR_SIMILARITY = "vector_similarity"
    VECTOR_DISTANCE = "vector_distance"
    RERANK_SCORE = "rerank_score"


class IndexHealth(str, Enum):
    """Read-only compatibility state reported for an index."""

    READY = "ready"
    DEGRADED = "degraded"
    MISSING = "missing"
    MIGRATION_REQUIRED = "migration_required"


class SourceRecord(BaseModel):
    """Stable registry record used by the future production source policy."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    content_hash: str
    source_type: SourceType
    source_role: SourceRole

    @field_validator("content_hash")
    @classmethod
    def _valid_content_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("content_hash must be a full SHA-256 hex digest")
        return normalized


@runtime_checkable
class SourcePolicy(Protocol):
    """Behavior required from a provenance-aware production ingestion policy."""

    def classify_source(
        self,
        *,
        filename: str,
        content_hash: str,
        registry: dict[str, SourceRecord],
    ) -> SourceRecord:
        """Return the registered identity; filename alone is never authoritative."""


class IndexConfig(BaseModel):
    """Single-root, serializable layout for the active local RAG index."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    data_root: Path = Field(default=Path("data"))
    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")

    @classmethod
    def resolve(
        cls,
        config: "IndexConfig | Mapping[str, Any] | None" = None,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "IndexConfig":
        """Resolve values with the contract precedence: env > config > default."""

        values = (
            config.model_dump(exclude_computed_fields=True)
            if isinstance(config, cls)
            else dict(config or {})
        )
        env = process_environ if environ is None else environ
        if env.get(INDEX_DATA_ROOT_ENV):
            values["data_root"] = env[INDEX_DATA_ROOT_ENV]
        if env.get(INDEX_SCHEMA_VERSION_ENV):
            values["schema_version"] = env[INDEX_SCHEMA_VERSION_ENV]
        return cls.model_validate(values)

    @field_validator("data_root", mode="before")
    @classmethod
    def _validate_data_root(cls, value: Any) -> Path:
        path = Path(value)
        if not str(path).strip() or str(path) == ".":
            raise ValueError("data_root must name a directory")
        if ".." in PurePath(path).parts:
            raise ValueError("data_root must not contain parent traversal")
        return path

    @computed_field
    @property
    def index_root(self) -> Path:
        return self.data_root / "index"

    @computed_field
    @property
    def user_library_root(self) -> Path:
        return self.index_root / "user_library"

    @computed_field
    @property
    def vector_index_dir(self) -> Path:
        return self.user_library_root / "zvec"

    @computed_field
    @property
    def chunks_manifest_path(self) -> Path:
        return self.user_library_root / "chunks.jsonl"

    @computed_field
    @property
    def migration_staging_dir(self) -> Path:
        return self.index_root / ".migration_staging"

    @computed_field
    @property
    def backup_dir(self) -> Path:
        return self.index_root / ".migration_backup"

    @computed_field
    @property
    def lock_path(self) -> Path:
        return self.index_root / ".rag-index.lock"

    @computed_field
    @property
    def config_version(self) -> str:
        """Compatibility alias used in diagnostics and migration manifests."""

        return self.schema_version


class MigrationDryRun(BaseModel):
    """Serializable migration proposal; constructing it performs no migration."""

    model_config = ConfigDict(extra="forbid")

    source: Path
    target: Path
    checksum: str
    rollback_available: bool
    dry_run: Literal[True] = True

    @field_validator("checksum")
    @classmethod
    def _valid_checksum(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("checksum must be a full SHA-256 hex digest")
        return normalized

    @model_validator(mode="after")
    def _distinct_paths(self) -> "MigrationDryRun":
        if self.source == self.target:
            raise ValueError("source and target must be different")
        return self


class SourceLocator(BaseModel):
    """Structured location of a quote inside one source document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1)
    chunk_id: str | None = Field(default=None, min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=1)

    @computed_field
    @property
    def source_id(self) -> str:
        return self.document_id

    @model_validator(mode="after")
    def _validate_locator(self) -> "SourceLocator":
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must be provided together")
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end <= self.char_start
        ):
            raise ValueError("char_end must be greater than char_start")
        if self.page is None and not any(
            (self.section, self.chunk_id, self.char_start is not None)
        ):
            raise ValueError("a non-page source requires section, chunk_id, or character range")
        return self


class RetrievalHit(BaseModel):
    """Lossless T04 retrieval result passed to downstream adapters."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    quoted_text: str = Field(min_length=1)
    retrieval_score: float
    score_kind: ScoreKind
    source_type: SourceType
    source_role: SourceRole
    source_locator: SourceLocator
    content_hash: str
    title: str = Field(min_length=1)
    doi: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("quoted_text", "title")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("content_hash")
    @classmethod
    def _valid_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_PATTERN.fullmatch(normalized):
            raise ValueError("content_hash must be a full SHA-256 hex digest")
        return normalized

    @field_validator("retrieval_score")
    @classmethod
    def _finite_score(cls, value: float) -> float:
        score = float(value)
        if not isfinite(score):
            raise ValueError("retrieval_score must be finite")
        return score

    @field_validator("doi")
    @classmethod
    def _valid_doi(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not _DOI_PATTERN.fullmatch(normalized):
            raise ValueError("doi must use the 10.xxxx/suffix form")
        return normalized

    @field_validator("url")
    @classmethod
    def _valid_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not normalized.lower().startswith(("https://", "http://")):
            raise ValueError("url must use http or https")
        return normalized

    @model_validator(mode="after")
    def _chunk_ids_agree(self) -> "RetrievalHit":
        locator_chunk = self.source_locator.chunk_id
        if locator_chunk is not None and locator_chunk != self.chunk_id:
            raise ValueError("source_locator.chunk_id must match chunk_id")
        return self


def coerce_retrieval_hit(value: Any) -> RetrievalHit:
    """Validate an adapter result at the T04 boundary without rewriting provenance."""

    return RetrievalHit.model_validate(value)
