"""Persistent artifact registry with ownership and integrity enforcement."""

from __future__ import annotations

import hashlib
import hmac
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class ArtifactRegistryError(RuntimeError):
    pass


class ArtifactNotFound(ArtifactRegistryError):
    pass


class ArtifactPermissionDenied(ArtifactRegistryError):
    pass


class ArtifactIntegrityError(ArtifactRegistryError):
    pass


class ArtifactConflict(ArtifactRegistryError):
    pass


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    job_id: str
    question_id: str
    actor_id: str
    name: str
    artifact_type: str
    media_type: str
    size_bytes: int
    sha256: str
    status: str
    truth_status: str
    relative_path: str
    created_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SQLiteArtifactRegistry:
    def __init__(self, path: str | Path, *, root: str | Path) -> None:
        self.path = Path(path)
        self.root = Path(root).resolve(strict=False)
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                yield connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS artifacts (
                        artifact_id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        question_id TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        artifact_type TEXT NOT NULL,
                        media_type TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        sha256 TEXT NOT NULL,
                        status TEXT NOT NULL,
                        truth_status TEXT NOT NULL,
                        relative_path TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_artifacts_job_actor
                        ON artifacts(job_id, actor_id, created_at);
                    CREATE TABLE IF NOT EXISTS export_requests (
                        actor_id TEXT NOT NULL,
                        idempotency_key_hash TEXT NOT NULL,
                        job_id TEXT NOT NULL,
                        request_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY(actor_id, idempotency_key_hash)
                    );
                    """
                )

    def claim_export_request(
        self,
        *,
        actor_id: str,
        idempotency_key: str,
        job_id: str,
        request_hash: str,
    ) -> bool:
        """Claim one mutation key, or validate an exact replay.

        Returns ``True`` only when an identical request was already claimed.
        The raw key is never persisted.
        """
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        with self._write() as connection:
            row = connection.execute(
                """
                SELECT job_id, request_hash FROM export_requests
                WHERE actor_id = ? AND idempotency_key_hash = ?
                """,
                (actor_id, key_hash),
            ).fetchone()
            if row is not None:
                if not (
                    hmac.compare_digest(row["job_id"], job_id)
                    and hmac.compare_digest(row["request_hash"], request_hash)
                ):
                    raise ArtifactConflict(
                        "idempotency key already belongs to a different export"
                    )
                return True
            connection.execute(
                """
                INSERT INTO export_requests(
                    actor_id, idempotency_key_hash, job_id, request_hash, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (actor_id, key_hash, job_id, request_hash, _now()),
            )
        return False

    @staticmethod
    def _record(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(**dict(row))

    def _relative_path(self, path: Path) -> tuple[Path, str]:
        resolved = path.resolve(strict=True)
        try:
            relative = resolved.relative_to(self.root)
        except ValueError:
            raise ValueError("artifact path must remain inside artifact root") from None
        if not resolved.is_file():
            raise ValueError("artifact path must reference a regular file")
        return resolved, relative.as_posix()

    def register_file(
        self,
        *,
        artifact_id: str,
        job_id: str,
        question_id: str,
        actor_id: str,
        name: str,
        artifact_type: str,
        media_type: str,
        truth_status: str,
        path: str | Path,
    ) -> tuple[ArtifactRecord, bool]:
        values = {
            "artifact_id": artifact_id,
            "job_id": job_id,
            "question_id": question_id,
            "actor_id": actor_id,
            "name": name,
            "artifact_type": artifact_type,
            "media_type": media_type,
            "truth_status": truth_status,
        }
        if any(not str(value).strip() for value in values.values()):
            raise ValueError("artifact registry fields must be nonblank")
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("artifact name must be a controlled basename")
        resolved, relative = self._relative_path(Path(path))
        size_bytes = resolved.stat().st_size
        sha256 = _file_sha256(resolved)
        created_at = _now()
        with self._write() as connection:
            existing = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            if existing is not None:
                record = self._record(existing)
                expected = (
                    job_id,
                    question_id,
                    actor_id,
                    name,
                    artifact_type,
                    media_type,
                    size_bytes,
                    sha256,
                    truth_status,
                    relative,
                )
                actual = (
                    record.job_id,
                    record.question_id,
                    record.actor_id,
                    record.name,
                    record.artifact_type,
                    record.media_type,
                    record.size_bytes,
                    record.sha256,
                    record.truth_status,
                    record.relative_path,
                )
                if actual != expected:
                    raise ArtifactConflict("artifact ID already has different content")
                return record, True
            connection.execute(
                """
                INSERT INTO artifacts(
                    artifact_id, job_id, question_id, actor_id, name,
                    artifact_type, media_type, size_bytes, sha256, status,
                    truth_status, relative_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?)
                """,
                (
                    artifact_id,
                    job_id,
                    question_id,
                    actor_id,
                    name,
                    artifact_type,
                    media_type,
                    size_bytes,
                    sha256,
                    truth_status,
                    relative,
                    created_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            return self._record(row), False

    def list_for_job(self, job_id: str, *, actor_id: str) -> list[ArtifactRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM artifacts
                WHERE job_id = ? AND actor_id = ?
                ORDER BY artifact_type, artifact_id
                """,
                (job_id, actor_id),
            ).fetchall()
        return [self._record(row) for row in rows]

    def get(self, artifact_id: str, *, actor_id: str) -> ArtifactRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
        if row is None:
            raise ArtifactNotFound(artifact_id)
        record = self._record(row)
        if record.actor_id != actor_id:
            raise ArtifactPermissionDenied(artifact_id)
        return record

    def resolve_for_download(self, artifact_id: str, *, actor_id: str) -> Path:
        record = self.get(artifact_id, actor_id=actor_id)
        candidate = (self.root / record.relative_path).resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise ArtifactIntegrityError("artifact registry path escaped root") from None
        if not candidate.is_file():
            raise ArtifactIntegrityError("artifact file is missing")
        if candidate.stat().st_size != record.size_bytes:
            raise ArtifactIntegrityError("artifact size does not match registry")
        if _file_sha256(candidate) != record.sha256:
            raise ArtifactIntegrityError("artifact checksum does not match registry")
        return candidate
