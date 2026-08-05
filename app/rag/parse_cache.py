"""Versioned, content-addressed cache for document parsing results."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from app.rag.document_loader import Document
from app.rag.document_registry import normalize_sha256


def parse_cache_key(*, content_sha256: str, loader_version: str) -> str:
    digest = normalize_sha256(content_sha256)
    version = str(loader_version or "").strip()
    if not version:
        raise ValueError("loader_version must not be blank")
    return hashlib.sha256(f"{digest}:{version}".encode("utf-8")).hexdigest()


class ParseCache:
    """Persist parsed Documents using atomic per-entry JSON replacement."""

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)

    def _entry_path(self, *, content_sha256: str, loader_version: str) -> Path:
        key = parse_cache_key(
            content_sha256=content_sha256,
            loader_version=loader_version,
        )
        return self.cache_dir / f"{key}.json"

    def get(
        self, *, content_sha256: str, loader_version: str
    ) -> list[Document] | None:
        path = self._entry_path(
            content_sha256=content_sha256,
            loader_version=loader_version,
        )
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("content_sha256") != normalize_sha256(content_sha256):
                return None
            if payload.get("loader_version") != str(loader_version).strip():
                return None
            return [
                Document(text=str(item["text"]), metadata=dict(item["metadata"]))
                for item in payload["documents"]
            ]
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def put(
        self,
        *,
        content_sha256: str,
        loader_version: str,
        documents: list[Document],
    ) -> Path:
        digest = normalize_sha256(content_sha256)
        version = str(loader_version or "").strip()
        if not version:
            raise ValueError("loader_version must not be blank")
        path = self._entry_path(content_sha256=digest, loader_version=version)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "content_sha256": digest,
            "loader_version": version,
            "documents": [
                {"text": document.text, "metadata": document.metadata}
                for document in documents
            ],
        }
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)
        return path
