"""Fail-closed adapter from a frozen chunk manifest to the vector-store boundary.

This module deliberately does not choose an embedding implementation.  Gate B1
callers must inject one explicitly; the existing PDF ingestion path remains
unchanged.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable

from app.contracts.rag import SourceLocator, SourceRole, SourceType
from app.rag.chunker import Chunk
from app.rag.zvec_store import VectorStoreProtocol, get_vector_store


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FrozenChunkValidationError(ValueError):
    """Raised before indexing when frozen input cannot prove its identity."""


class FrozenChunkBuildError(RuntimeError):
    """Raised when injected embedding or vector persistence fails closed."""


@dataclass(frozen=True)
class EmbeddingIdentity:
    """Auditable identity supplied by an injected embedding implementation."""

    backend: str
    model: str
    version: str
    fake: bool = False

    def __post_init__(self) -> None:
        for name in ("backend", "model", "version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"embedding {name} must not be blank")


@runtime_checkable
class FrozenChunkEmbedder(Protocol):
    """Dependency-injection boundary used by the frozen-chunk builder."""

    @property
    def identity(self) -> EmbeddingIdentity:
        """Return the exact backend/model identity without making a call."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts in input order, returning one non-empty vector per text."""


@dataclass(frozen=True)
class FrozenChunkSet:
    """Validated, byte-identified frozen input."""

    path: Path
    sha256: str
    chunks: tuple[Chunk, ...]
    document_ids: tuple[str, ...]


@dataclass(frozen=True)
class FrozenIndexBuildResult:
    """Result metadata; fake builds are always explicitly non-production."""

    index_dir: Path
    source_chunks_sha256: str
    record_count: int
    document_count: int
    embedding: EmbeddingIdentity
    embedding_dimension: int
    production: bool
    fake: bool


def _full_sha256(value: object, *, field: str, line_number: int) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise FrozenChunkValidationError(
            f"line {line_number}: {field} must be a full SHA-256 digest"
        )
    return normalized


def _required_text(value: object, *, field: str, line_number: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FrozenChunkValidationError(
            f"line {line_number}: {field} must be non-empty text"
        )
    return value


def _validated_chunk(record: object, *, line_number: int) -> Chunk:
    if not isinstance(record, dict):
        raise FrozenChunkValidationError(f"line {line_number}: record must be an object")
    chunk_id = _required_text(record.get("chunk_id"), field="chunk_id", line_number=line_number)
    text = _required_text(record.get("text"), field="text", line_number=line_number)
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise FrozenChunkValidationError(f"line {line_number}: metadata must be an object")
    metadata = dict(metadata)

    document_id = _required_text(
        metadata.get("document_id") or metadata.get("doc_id"),
        field="document_id",
        line_number=line_number,
    )
    if metadata.get("document_id") not in (None, document_id) or metadata.get("doc_id") not in (None, document_id):
        raise FrozenChunkValidationError(f"line {line_number}: document identities disagree")
    source_id = _required_text(metadata.get("source_id"), field="source_id", line_number=line_number)
    _required_text(metadata.get("source_name"), field="source_name", line_number=line_number)
    _required_text(metadata.get("title"), field="title", line_number=line_number)
    _required_text(
        metadata.get("loader_version"), field="loader_version", line_number=line_number
    )

    content_hash = _full_sha256(
        metadata.get("content_sha256") or metadata.get("content_hash"),
        field="content_hash",
        line_number=line_number,
    )
    for alias in ("content_sha256", "content_hash", "source_sha256"):
        if metadata.get(alias) is not None and _full_sha256(
            metadata[alias], field=alias, line_number=line_number
        ) != content_hash:
            raise FrozenChunkValidationError(f"line {line_number}: content identities disagree")

    try:
        source_type = SourceType(str(metadata.get("source_type")))
        source_role = SourceRole(str(metadata.get("source_role")))
    except ValueError as exc:
        raise FrozenChunkValidationError(
            f"line {line_number}: invalid source_type/source_role"
        ) from exc

    locator_value = metadata.get("locator")
    if not isinstance(locator_value, dict):
        raise FrozenChunkValidationError(f"line {line_number}: locator is required")
    try:
        locator = SourceLocator.model_validate(locator_value)
    except Exception as exc:
        raise FrozenChunkValidationError(f"line {line_number}: invalid locator") from exc
    if locator.document_id != document_id or locator.chunk_id != chunk_id:
        raise FrozenChunkValidationError(f"line {line_number}: locator identity mismatch")
    if metadata.get("page") is not None and locator.page != metadata.get("page"):
        raise FrozenChunkValidationError(f"line {line_number}: locator page mismatch")

    quoted_text = _required_text(
        metadata.get("quoted_text"), field="quoted_text", line_number=line_number
    )
    if quoted_text != text:
        raise FrozenChunkValidationError(f"line {line_number}: quoted_text differs from text")
    if metadata.get("chunk_id") is not None and metadata.get("chunk_id") != chunk_id:
        raise FrozenChunkValidationError(f"line {line_number}: chunk identities disagree")

    provenance = metadata.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise FrozenChunkValidationError(f"line {line_number}: provenance is required")
    for field in ("origin", "custodian", "license_or_authorization"):
        if field not in provenance or not isinstance(provenance[field], str) or not provenance[field].strip():
            raise FrozenChunkValidationError(
                f"line {line_number}: provenance.{field} is required"
            )

    metadata.update(
        document_id=document_id,
        source_id=source_id,
        content_sha256=content_hash,
        source_type=source_type.value,
        source_role=source_role.value,
    )
    return Chunk(chunk_id=chunk_id, text=text, metadata=metadata)


def load_frozen_chunks(path: str | Path, *, expected_sha256: str) -> FrozenChunkSet:
    """Load a frozen JSONL file only after byte and record validation succeeds."""

    source = Path(path)
    expected = _full_sha256(expected_sha256, field="expected_sha256", line_number=0)
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise FrozenChunkValidationError(f"cannot read frozen chunks: {exc}") from exc
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise FrozenChunkValidationError(
            f"frozen chunks SHA-256 mismatch: expected {expected}, got {actual}"
        )

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FrozenChunkValidationError("frozen chunks must be UTF-8") from exc
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise FrozenChunkValidationError(f"line {line_number}: blank JSONL line")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FrozenChunkValidationError(f"line {line_number}: malformed JSON") from exc
        chunk = _validated_chunk(record, line_number=line_number)
        if chunk.chunk_id in seen:
            raise FrozenChunkValidationError(
                f"line {line_number}: duplicate chunk_id {chunk.chunk_id}"
            )
        seen.add(chunk.chunk_id)
        chunks.append(chunk)
    if not chunks:
        raise FrozenChunkValidationError("frozen chunks contains no records")
    document_ids = tuple(sorted({str(c.metadata["document_id"]) for c in chunks}))
    return FrozenChunkSet(source, actual, tuple(chunks), document_ids)


class FrozenChunksIndexBuilder:
    """Build existing vector-store records without loading or rechunking sources."""

    def __init__(
        self,
        *,
        embedder: FrozenChunkEmbedder,
        vector_store_factory=get_vector_store,
    ) -> None:
        if not isinstance(embedder, FrozenChunkEmbedder):
            raise TypeError("embedder must implement FrozenChunkEmbedder")
        self.embedder = embedder
        self.vector_store_factory = vector_store_factory

    def build(
        self,
        chunks_path: str | Path,
        *,
        expected_sha256: str,
        index_dir: str | Path,
        production: bool,
    ) -> FrozenIndexBuildResult:
        frozen = load_frozen_chunks(chunks_path, expected_sha256=expected_sha256)
        identity = self.embedder.identity
        if production and identity.fake:
            raise FrozenChunkBuildError(
                "fake embedding cannot create a production index"
            )
        try:
            vectors = self.embedder.embed_texts([chunk.text for chunk in frozen.chunks])
        except Exception as exc:
            raise FrozenChunkBuildError(f"embedding failed: {exc}") from exc
        if len(vectors) != len(frozen.chunks) or not vectors:
            raise FrozenChunkBuildError("embedding count must equal frozen chunk count")
        dimension = len(vectors[0])
        if dimension <= 0 or any(len(vector) != dimension for vector in vectors):
            raise FrozenChunkBuildError("embedding vectors must have one non-zero dimension")

        target = Path(index_dir)
        try:
            store: VectorStoreProtocol = self.vector_store_factory(
                dimension=dimension, index_dir=str(target)
            )
            store.add_documents(list(frozen.chunks), vectors)
            store.persist()
        except Exception as exc:
            raise FrozenChunkBuildError(f"index write failed: {exc}") from exc
        return FrozenIndexBuildResult(
            index_dir=target,
            source_chunks_sha256=frozen.sha256,
            record_count=len(frozen.chunks),
            document_count=len(frozen.document_ids),
            embedding=identity,
            embedding_dimension=dimension,
            production=bool(production and not identity.fake),
            fake=identity.fake,
        )
