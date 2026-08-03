"""Stable document identity and duplicate detection for T04 ingestion."""

from __future__ import annotations

import re
from dataclasses import dataclass


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_sha256(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError("content_sha256 must be a full SHA-256 hex digest")
    return normalized


def normalize_doi(value: str | None) -> str | None:
    """Normalize a DOI without inventing or resolving external metadata."""
    if value is None:
        return None
    normalized = str(value).strip()
    lowered = normalized.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lowered.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break
    normalized = normalized.lower()
    if not normalized:
        return None
    if not _DOI_RE.fullmatch(normalized):
        raise ValueError("doi must be a valid DOI identifier")
    return normalized


def document_identity(*, doi: str | None, content_sha256: str) -> str:
    """Prefer a normalized DOI identity and otherwise use byte identity."""
    normalized_doi = normalize_doi(doi)
    digest = normalize_sha256(content_sha256)
    return f"doi:{normalized_doi}" if normalized_doi else f"sha256:{digest}"


@dataclass(frozen=True)
class DocumentRecord:
    filename: str
    content_sha256: str
    doi: str | None
    identity: str


@dataclass(frozen=True)
class RegistrationResult:
    record: DocumentRecord
    duplicate: bool
    duplicate_reason: str | None = None


class DocumentRegistry:
    """In-memory identity registry suitable for manifest-backed callers."""

    def __init__(self) -> None:
        self._by_identity: dict[str, DocumentRecord] = {}
        self._by_hash: dict[str, DocumentRecord] = {}

    def register(
        self, *, filename: str, content_sha256: str, doi: str | None = None
    ) -> RegistrationResult:
        digest = normalize_sha256(content_sha256)
        normalized_doi = normalize_doi(doi)
        identity = document_identity(doi=normalized_doi, content_sha256=digest)

        existing = self._by_identity.get(identity)
        reason = (
            "doi"
            if existing is not None and normalized_doi
            else "content_sha256" if existing is not None else None
        )
        if existing is None:
            existing = self._by_hash.get(digest)
            if existing is not None:
                reason = "content_sha256"
        if existing is not None:
            return RegistrationResult(
                record=existing,
                duplicate=True,
                duplicate_reason=reason,
            )

        record = DocumentRecord(
            filename=str(filename),
            content_sha256=digest,
            doi=normalized_doi,
            identity=identity,
        )
        self._by_identity[identity] = record
        self._by_hash[digest] = record
        return RegistrationResult(record=record, duplicate=False)
