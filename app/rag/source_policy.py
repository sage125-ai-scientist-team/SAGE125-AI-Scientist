"""Production source classification policy for T04 RAG ingestion."""

from __future__ import annotations

import re

from app.contracts.rag import SourceRecord, SourceRole, SourceType


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class RegistrySourcePolicy:
    """Classify sources by registered content identity, never by filename."""

    def classify_source(
        self,
        *,
        filename: str,
        content_hash: str,
        registry: dict[str, SourceRecord],
    ) -> SourceRecord:
        """Return the registered source or a safe unknown user-upload record."""

        del filename  # Filenames and extensions are intentionally non-authoritative.
        normalized_hash = content_hash.strip().lower()
        if not _SHA256_PATTERN.fullmatch(normalized_hash):
            raise ValueError("content_hash must be a full SHA-256 hex digest")

        normalized_registry: dict[str, SourceRecord] = {}
        for raw_key, raw_record in registry.items():
            key = str(raw_key).strip().lower()
            if not _SHA256_PATTERN.fullmatch(key):
                raise ValueError("registry key must be a full SHA-256 hex digest")
            record = SourceRecord.model_validate(raw_record)
            if key != record.content_hash:
                raise ValueError(
                    "registry key must match SourceRecord.content_hash"
                )
            normalized_registry[key] = record

        registered = normalized_registry.get(normalized_hash)
        if registered is not None:
            return registered

        return SourceRecord(
            source_id=f"SOURCE-{normalized_hash[:16]}",
            content_hash=normalized_hash,
            source_type=SourceType.UNKNOWN,
            source_role=SourceRole.USER_UPLOAD,
        )
