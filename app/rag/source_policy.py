"""Production source classification policy for T04 RAG ingestion."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from app.contracts.rag import SourceRecord, SourceRole, SourceType


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_BOOKLET_REGISTRY_PATH = Path(__file__).with_name("booklet_registry.json")


def _normalize_hash(value: str, *, label: str) -> str:
    normalized = str(value).strip().lower()
    if not _SHA256_PATTERN.fullmatch(normalized):
        raise ValueError(f"{label} must be a full SHA-256 hex digest")
    return normalized


def _load_registry(path: Path) -> dict[str, SourceRecord]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"source registry cannot be loaded: {path}") from exc
    if payload.get("version") != 1 or not isinstance(payload.get("sources"), list):
        raise ValueError("source registry must contain version=1 and a sources list")

    loaded: dict[str, SourceRecord] = {}
    for raw_record in payload["sources"]:
        record = SourceRecord.model_validate(raw_record)
        existing = loaded.get(record.content_hash)
        if existing is not None and existing != record:
            raise ValueError("source registry contains conflicting content hashes")
        loaded[record.content_hash] = record
    return loaded


class RegistrySourcePolicy:
    """Classify sources by registered content identity, never by filename."""

    def __init__(
        self,
        registry: Mapping[str, SourceRecord] | None = None,
        *,
        booklet_hashes: Iterable[str] | None = None,
    ) -> None:
        self._stable_registry = _load_registry(DEFAULT_BOOKLET_REGISTRY_PATH)
        for raw_key, raw_record in (registry or {}).items():
            key = _normalize_hash(raw_key, label="registry key")
            record = SourceRecord.model_validate(raw_record)
            if key != record.content_hash:
                raise ValueError("registry key must match SourceRecord.content_hash")
            existing = self._stable_registry.get(key)
            if existing is not None and existing != record:
                raise ValueError("injected registry conflicts with stable source identity")
            self._stable_registry[key] = record

        for raw_hash in booklet_hashes or ():
            content_hash = _normalize_hash(
                raw_hash, label="booklet content hash"
            )
            booklet = SourceRecord(
                source_id=f"SOURCE-BOOKLET-{content_hash[:16]}",
                content_hash=content_hash,
                source_type=SourceType.BOOKLET,
                source_role=SourceRole.QUESTION_SOURCE,
            )
            existing = self._stable_registry.get(content_hash)
            if existing is not None and existing != booklet:
                raise ValueError("booklet content hash conflicts with source registry")
            self._stable_registry[content_hash] = booklet

    def classify_source(
        self,
        *,
        filename: str,
        content_hash: str,
        registry: dict[str, SourceRecord],
    ) -> SourceRecord:
        """Return the registered source or a safe unknown user-upload record."""

        del filename  # Classification is based on stable content identity only.
        normalized_hash = _normalize_hash(content_hash, label="content_hash")

        normalized_registry: dict[str, SourceRecord] = {}
        for raw_key, raw_record in registry.items():
            key = _normalize_hash(raw_key, label="registry key")
            record = SourceRecord.model_validate(raw_record)
            if key != record.content_hash:
                raise ValueError(
                    "registry key must match SourceRecord.content_hash"
                )
            normalized_registry[key] = record

        stable = self._stable_registry.get(normalized_hash)
        runtime = normalized_registry.get(normalized_hash)
        if stable is not None and runtime is not None and stable != runtime:
            raise ValueError("runtime registry conflicts with stable source identity")
        registered = stable or runtime
        if registered is not None:
            return registered

        return SourceRecord(
            source_id=f"SOURCE-{normalized_hash[:16]}",
            content_hash=normalized_hash,
            source_type=SourceType.UNKNOWN,
            source_role=SourceRole.USER_UPLOAD,
        )
