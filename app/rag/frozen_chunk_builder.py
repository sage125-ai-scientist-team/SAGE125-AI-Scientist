"""Fail-closed adapter from frozen chunks to an atomically published index.

The adapter never loads source documents or chunks text.  Embedding is an
explicit dependency.  Gate B1 can therefore exercise the boundary with a fake
embedder while production eligibility remains locked behind a separate,
immutable Gate B2 authorization contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, Sequence, runtime_checkable

from app.contracts.rag import ScoreKind, SourceLocator, SourceRole, SourceType
from app.rag.chunker import Chunk
from app.rag.evidence import chunk_to_retrieval_hit
from app.rag.zvec_store import (
    MemoryVectorStore,
    VectorStoreProtocol,
    ZvecVectorStore,
    get_vector_store,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PLACEHOLDERS = {
    "UNKNOWN",
    "TBD",
    "N/A",
    "NA",
    "NONE",
    "NULL",
    "PLACEHOLDER",
    "UNSET",
}
_LOCATOR_FIELDS = (
    "document_id",
    "page",
    "section",
    "chunk_id",
    "char_start",
    "char_end",
)
_INDEX_MANIFEST = "index_manifest.json"
_CHUNKS_SIDECAR = "chunks.jsonl"


class FrozenChunkValidationError(ValueError):
    """Raised before embedding when frozen input cannot prove its identity."""


class FrozenChunkBuildError(RuntimeError):
    """Raised when authorization, embedding, validation, or publish fails closed."""


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


@dataclass(frozen=True)
class ProductionBuildAuthorization:
    """Captain-controlled Gate B2 inputs required for production eligibility."""

    production_embedding_authorized: bool
    embedding_model: str
    frozen_chunks_sha256: str
    index_build_authorized: bool
    mock_embedding_allowed: bool
    local_qwen_allowed: bool
    fallback_allowed: bool
    captain_authorization_reference: str


@runtime_checkable
class FrozenChunkEmbedder(Protocol):
    """Dependency-injection boundary used by the frozen-chunk builder."""

    @property
    def identity(self) -> EmbeddingIdentity:
        """Return exact backend/model identity without making a call."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts in order, returning one non-empty vector per text."""


@dataclass(frozen=True)
class FrozenChunkSet:
    """Validated, byte-identified frozen input."""

    path: Path
    sha256: str
    chunks: tuple[Chunk, ...]
    document_ids: tuple[str, ...]


@dataclass(frozen=True)
class FrozenIndexBuildResult:
    """Published result metadata; fake builds are always non-production."""

    index_dir: Path
    source_chunks_sha256: str
    record_count: int
    document_count: int
    embedding: EmbeddingIdentity
    embedding_dimension: int
    production: bool
    fake: bool


StagingValidator = Callable[[Path, FrozenChunkSet], None]


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


def _is_placeholder(value: object) -> bool:
    return not isinstance(value, str) or value.strip().upper() in _PLACEHOLDERS


def _is_explicit_placeholder(value: object) -> bool:
    return isinstance(value, str) and value.strip().upper() in _PLACEHOLDERS


def _normalized_locator(
    metadata: dict,
    *,
    document_id: str,
    chunk_id: str,
    line_number: int,
) -> dict:
    """Merge locator representations field-wise; conflicting values fail closed."""

    candidates: list[dict] = []
    for key in ("source_locator", "locator"):
        value = metadata.get(key)
        if value is not None and not isinstance(value, dict):
            raise FrozenChunkValidationError(
                f"line {line_number}: {key} must be an object"
            )
        if isinstance(value, dict):
            candidates.append(value)
    candidates.append({key: metadata.get(key) for key in _LOCATOR_FIELDS})

    merged: dict = {}
    for field in _LOCATOR_FIELDS:
        values = [candidate.get(field) for candidate in candidates]
        present = [value for value in values if value is not None]
        if present and any(value != present[0] for value in present[1:]):
            raise FrozenChunkValidationError(
                f"line {line_number}: conflicting locator.{field} values"
            )
        if present:
            merged[field] = present[0]
    merged.setdefault("document_id", document_id)
    merged.setdefault("chunk_id", chunk_id)
    try:
        locator = SourceLocator.model_validate(merged)
    except Exception as exc:
        raise FrozenChunkValidationError(f"line {line_number}: invalid locator") from exc
    if locator.document_id != document_id or locator.chunk_id != chunk_id:
        raise FrozenChunkValidationError(
            f"line {line_number}: locator identity mismatch"
        )
    return locator.model_dump(exclude_none=True, exclude_computed_fields=True)


def _validated_chunk(record: object, *, line_number: int) -> Chunk:
    if not isinstance(record, dict):
        raise FrozenChunkValidationError(f"line {line_number}: record must be an object")
    chunk_id = _required_text(
        record.get("chunk_id"), field="chunk_id", line_number=line_number
    )
    text = _required_text(record.get("text"), field="text", line_number=line_number)
    metadata_value = record.get("metadata")
    if not isinstance(metadata_value, dict):
        raise FrozenChunkValidationError(f"line {line_number}: metadata must be an object")
    metadata = dict(metadata_value)

    document_id = _required_text(
        metadata.get("document_id") or metadata.get("doc_id"),
        field="document_id",
        line_number=line_number,
    )
    if metadata.get("document_id") not in (None, document_id) or metadata.get(
        "doc_id"
    ) not in (None, document_id):
        raise FrozenChunkValidationError(
            f"line {line_number}: document identities disagree"
        )
    source_id = _required_text(
        metadata.get("source_id"), field="source_id", line_number=line_number
    )
    _required_text(
        metadata.get("source_name"), field="source_name", line_number=line_number
    )
    _required_text(metadata.get("title"), field="title", line_number=line_number)
    _required_text(
        metadata.get("loader_version"),
        field="loader_version",
        line_number=line_number,
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
            raise FrozenChunkValidationError(
                f"line {line_number}: content identities disagree"
            )

    try:
        source_type = SourceType(str(metadata.get("source_type")))
        source_role = SourceRole(str(metadata.get("source_role")))
    except ValueError as exc:
        raise FrozenChunkValidationError(
            f"line {line_number}: invalid source_type/source_role"
        ) from exc

    locator = _normalized_locator(
        metadata,
        document_id=document_id,
        chunk_id=chunk_id,
        line_number=line_number,
    )
    quoted_text = _required_text(
        metadata.get("quoted_text"), field="quoted_text", line_number=line_number
    )
    if quoted_text != text:
        raise FrozenChunkValidationError(
            f"line {line_number}: quoted_text differs from text"
        )
    if metadata.get("chunk_id") is not None and metadata.get("chunk_id") != chunk_id:
        raise FrozenChunkValidationError(
            f"line {line_number}: chunk identities disagree"
        )

    provenance = metadata.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise FrozenChunkValidationError(f"line {line_number}: provenance is required")
    for field in ("origin", "custodian", "license_or_authorization"):
        if (
            field not in provenance
            or not isinstance(provenance[field], str)
            or not provenance[field].strip()
        ):
            raise FrozenChunkValidationError(
                f"line {line_number}: provenance.{field} is required"
            )

    metadata.update(
        chunk_id=chunk_id,
        document_id=document_id,
        source_id=source_id,
        content_sha256=content_hash,
        source_type=source_type.value,
        source_role=source_role.value,
        source_locator=dict(locator),
        locator=dict(locator),
    )
    return Chunk(chunk_id=chunk_id, text=text, metadata=metadata)


def load_frozen_chunks(path: str | Path, *, expected_sha256: str) -> FrozenChunkSet:
    """Load frozen JSONL only after byte and record validation succeeds."""

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
            raise FrozenChunkValidationError(
                f"line {line_number}: malformed JSON"
            ) from exc
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


def _validate_production_provenance(frozen: FrozenChunkSet) -> None:
    """Prove downstream RetrievalHit eligibility before any embedding call."""

    for position, chunk in enumerate(frozen.chunks, start=1):
        metadata = chunk.metadata
        authors = metadata.get("authors")
        if not isinstance(authors, list) or not authors:
            raise FrozenChunkBuildError(
                f"chunk {position}: production authors must be a non-empty list"
            )
        if any(_is_placeholder(author) for author in authors):
            raise FrozenChunkBuildError(
                f"chunk {position}: production authors contain a placeholder"
            )
        doi = metadata.get("doi")
        url = metadata.get("url")
        if _is_explicit_placeholder(doi) or _is_explicit_placeholder(url):
            raise FrozenChunkBuildError(
                f"chunk {position}: production DOI/URL contains a placeholder"
            )
        if not str(doi or "").strip() and not str(url or "").strip():
            raise FrozenChunkBuildError(
                f"chunk {position}: production DOI or URL is required"
            )
        provenance = metadata["provenance"]
        for field in ("origin", "custodian", "license_or_authorization"):
            if _is_placeholder(provenance.get(field)):
                raise FrozenChunkBuildError(
                    f"chunk {position}: production provenance.{field} is a placeholder"
                )
        if metadata["source_type"] != SourceType.PAPER.value or metadata[
            "source_role"
        ] != SourceRole.EXTERNAL_RETRIEVAL.value:
            raise FrozenChunkBuildError(
                f"chunk {position}: production evidence taxonomy is required"
            )
        try:
            chunk_to_retrieval_hit(
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": metadata,
                },
                score=0.0,
                score_kind=ScoreKind.VECTOR_SIMILARITY,
            )
        except (TypeError, ValueError) as exc:
            raise FrozenChunkBuildError(
                f"chunk {position}: cannot adapt to RetrievalHit: {exc}"
            ) from exc


def _validate_production_authorization(
    authorization: ProductionBuildAuthorization | None,
    *,
    expected_sha256: str,
    embedding: EmbeddingIdentity,
    vector_store_backend: str,
) -> None:
    if authorization is None:
        raise FrozenChunkBuildError("production build authorization is required")
    if not authorization.production_embedding_authorized:
        raise FrozenChunkBuildError("production embedding is not authorized")
    if not authorization.index_build_authorized:
        raise FrozenChunkBuildError("production index build is not authorized")
    if authorization.mock_embedding_allowed:
        raise FrozenChunkBuildError("production authorization must forbid mock embedding")
    if authorization.local_qwen_allowed:
        raise FrozenChunkBuildError("production authorization must forbid local_qwen")
    if authorization.fallback_allowed:
        raise FrozenChunkBuildError("production authorization must forbid fallback")
    if not str(authorization.captain_authorization_reference or "").strip() or _is_placeholder(
        authorization.captain_authorization_reference
    ):
        raise FrozenChunkBuildError("captain authorization reference is required")
    authorized_hash = _full_sha256(
        authorization.frozen_chunks_sha256,
        field="authorization.frozen_chunks_sha256",
        line_number=0,
    )
    if authorized_hash != expected_sha256:
        raise FrozenChunkBuildError("authorization frozen chunks SHA-256 mismatch")
    if authorization.embedding_model != "text-embedding-v4":
        raise FrozenChunkBuildError("production model must be text-embedding-v4")
    if embedding.backend != "bailian" or embedding.model != "text-embedding-v4":
        raise FrozenChunkBuildError(
            "production embedder must be bailian text-embedding-v4"
        )
    if embedding.fake:
        raise FrozenChunkBuildError("fake embedding cannot create a production index")
    if vector_store_backend != "zvec":
        raise FrozenChunkBuildError("production vector store backend must be zvec")
    if os.getenv("MOCK_VECTOR_STORE", "").strip().lower() in {"1", "true", "yes"}:
        raise FrozenChunkBuildError("MOCK_VECTOR_STORE is forbidden for production")


def _write_chunks_sidecar(path: Path, frozen: FrozenChunkSet) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in frozen.chunks:
            handle.write(
                json.dumps(
                    {
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "metadata": chunk.metadata,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )


def _write_index_manifest(
    path: Path,
    *,
    frozen: FrozenChunkSet,
    identity: EmbeddingIdentity,
    dimension: int,
    production: bool,
    ready: bool,
) -> None:
    payload = {
        "production": production,
        "fake": identity.fake,
        "ready": ready,
        "source_chunks_sha256": frozen.sha256,
        "record_count": len(frozen.chunks),
        "document_count": len(frozen.document_ids),
        "embedding_backend": identity.backend,
        "embedding_model": identity.model,
        "embedding_version": identity.version,
        "embedding_dimension": dimension,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _validate_staging_tree(staging: Path, frozen: FrozenChunkSet) -> None:
    vector_dir = staging / "zvec"
    if not vector_dir.is_dir() or not any(path.is_file() for path in vector_dir.rglob("*")):
        raise FrozenChunkBuildError("staging vector index is missing or empty")
    chunks_path = staging / _CHUNKS_SIDECAR
    manifest_path = staging / _INDEX_MANIFEST
    if not chunks_path.is_file() or not manifest_path.is_file():
        raise FrozenChunkBuildError("staging index sidecars are missing")
    records = []
    try:
        for line in chunks_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrozenChunkBuildError("staging index sidecars are invalid") from exc
    if len(records) != len(frozen.chunks) or manifest.get("record_count") != len(
        frozen.chunks
    ):
        raise FrozenChunkBuildError("staging index record count mismatch")
    if manifest.get("source_chunks_sha256") != frozen.sha256:
        raise FrozenChunkBuildError("staging index frozen chunks hash mismatch")
    expected = {chunk.chunk_id: chunk for chunk in frozen.chunks}
    if set(record.get("chunk_id") for record in records) != set(expected):
        raise FrozenChunkBuildError("staging index chunk identities mismatch")
    for record in records:
        chunk = expected[record["chunk_id"]]
        metadata = record.get("metadata") or {}
        if record.get("text") != chunk.text or metadata.get("document_id") != chunk.metadata[
            "document_id"
        ] or metadata.get("content_sha256") != chunk.metadata["content_sha256"]:
            raise FrozenChunkBuildError("staging index metadata identity mismatch")


def _publish_staging(staging: Path, target: Path) -> None:
    """Publish by same-filesystem directory rename, restoring an existing target."""

    backup = target.with_name(f".{target.name}.backup-{uuid.uuid4().hex}")
    moved_current = False
    try:
        if target.exists():
            os.replace(target, backup)
            moved_current = True
        os.replace(staging, target)
    except Exception:
        if moved_current and not target.exists() and backup.exists():
            os.replace(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


class FrozenChunksIndexBuilder:
    """Build a frozen chunk set off-path, validate it, then publish by rename."""

    def __init__(
        self,
        *,
        embedder: FrozenChunkEmbedder,
        vector_store_factory=get_vector_store,
        vector_store_backend: str = "zvec",
        staging_validator: StagingValidator | None = None,
    ) -> None:
        if not isinstance(embedder, FrozenChunkEmbedder):
            raise TypeError("embedder must implement FrozenChunkEmbedder")
        self.embedder = embedder
        self.vector_store_factory = vector_store_factory
        self.vector_store_backend = str(vector_store_backend).strip().lower()
        self.staging_validator = staging_validator

    def build(
        self,
        chunks_path: str | Path,
        *,
        expected_sha256: str,
        index_dir: str | Path,
        production: bool,
        authorization: ProductionBuildAuthorization | None = None,
    ) -> FrozenIndexBuildResult:
        expected = _full_sha256(
            expected_sha256, field="expected_sha256", line_number=0
        )
        frozen = load_frozen_chunks(chunks_path, expected_sha256=expected)
        identity = self.embedder.identity
        if production:
            _validate_production_authorization(
                authorization,
                expected_sha256=expected,
                embedding=identity,
                vector_store_backend=self.vector_store_backend,
            )
            _validate_production_provenance(frozen)

        target = Path(index_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.name}.staging-{uuid.uuid4().hex}")
        staging.mkdir()
        try:
            store: VectorStoreProtocol = self.vector_store_factory(
                dimension=None, index_dir=str(staging / "zvec")
            )
            if production and isinstance(store, MemoryVectorStore):
                raise FrozenChunkBuildError(
                    "MemoryVectorStore is forbidden for production"
                )
            if production and not isinstance(store, ZvecVectorStore):
                raise FrozenChunkBuildError(
                    "production vector store must be ZvecVectorStore"
                )
            try:
                vectors = self.embedder.embed_texts(
                    [chunk.text for chunk in frozen.chunks]
                )
            except Exception as exc:
                raise FrozenChunkBuildError(f"embedding failed: {exc}") from exc
            if len(vectors) != len(frozen.chunks) or not vectors:
                raise FrozenChunkBuildError(
                    "embedding count must equal frozen chunk count"
                )
            dimension = len(vectors[0])
            if dimension <= 0 or any(len(vector) != dimension for vector in vectors):
                raise FrozenChunkBuildError(
                    "embedding vectors must have one non-zero dimension"
                )

            try:
                store.add_documents(list(frozen.chunks), vectors)
                store.persist()
            except Exception as exc:
                raise FrozenChunkBuildError(f"index write failed: {exc}") from exc
            _write_chunks_sidecar(staging / _CHUNKS_SIDECAR, frozen)
            _write_index_manifest(
                staging / _INDEX_MANIFEST,
                frozen=frozen,
                identity=identity,
                dimension=dimension,
                production=bool(production),
                ready=False,
            )
            if self.staging_validator is not None:
                try:
                    self.staging_validator(staging, frozen)
                except FrozenChunkBuildError:
                    raise
                except Exception as exc:
                    raise FrozenChunkBuildError(
                        f"staging index validation failed: {exc}"
                    ) from exc
            _validate_staging_tree(staging, frozen)
            try:
                store.load()
                smoke = store.search(vectors[0], top_k=1)
            except Exception as exc:
                raise FrozenChunkBuildError(f"staging index smoke load failed: {exc}") from exc
            if not smoke or smoke[0].chunk_id not in {
                chunk.chunk_id for chunk in frozen.chunks
            }:
                raise FrozenChunkBuildError("staging index smoke result is invalid")
            _write_index_manifest(
                staging / _INDEX_MANIFEST,
                frozen=frozen,
                identity=identity,
                dimension=dimension,
                production=bool(production),
                ready=True,
            )
            try:
                _publish_staging(staging, target)
            except Exception as exc:
                raise FrozenChunkBuildError(f"atomic index publish failed: {exc}") from exc
        finally:
            if staging.exists():
                shutil.rmtree(staging)

        return FrozenIndexBuildResult(
            index_dir=target,
            source_chunks_sha256=frozen.sha256,
            record_count=len(frozen.chunks),
            document_count=len(frozen.document_ids),
            embedding=identity,
            embedding_dimension=dimension,
            production=bool(production),
            fake=identity.fake,
        )
