"""可恢复的 API Job 状态存储。

SQLite 是当前无需新增依赖的最小持久化实现。每个操作使用独立连接，
配合 WAL 与 busy_timeout 支持 API 线程和后台 worker 并发访问。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from app.api.contracts import JobCreateRequest, JobStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_request(request: JobCreateRequest) -> tuple[str, str]:
    payload = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _key_hash(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class JobStoreError(RuntimeError):
    pass


class JobNotFound(JobStoreError):
    pass


class IdempotencyConflict(JobStoreError):
    pass


class InvalidTransition(JobStoreError):
    pass


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    correlation_id: str
    kind: str
    question_id: str
    mode: str
    status: str
    stage: str
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None
    attempt: int
    max_attempts: int
    upstream_run_id: str | None
    error_code: str | None
    error_message: str | None
    retryable: bool
    request_payload: dict[str, Any]


class JobStore(Protocol):
    def initialize(self) -> None: ...
    def create_job(
        self,
        *,
        request: JobCreateRequest,
        correlation_id: str,
        idempotency_key: str | None = None,
        requested_by: str = "anonymous",
    ) -> tuple[JobRecord, bool]: ...
    def get_job(self, job_id: str) -> JobRecord: ...
    def claim_queue_capacity_retry(
        self,
        job_id: str,
        *,
        expected_updated_at: str,
    ) -> tuple[JobRecord, bool]: ...
    def mark_queue_retry_submitted(self, job_id: str) -> JobRecord: ...
    def list_jobs(
        self,
        *,
        question_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 20,
    ) -> list[JobRecord]: ...
    def transition(
        self,
        job_id: str,
        to_status: JobStatus | str,
        *,
        stage: str | None = None,
        actor: str,
        source: str,
        upstream_run_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        retryable: bool = False,
        increment_attempt: bool = False,
    ) -> JobRecord: ...
    def begin_attempt(self, job_id: str) -> JobRecord: ...
    def update_progress(self, job_id: str, stage: str) -> JobRecord: ...
    def recover_interrupted_jobs(self) -> list[str]: ...


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    JobStatus.QUEUED.value: {
        JobStatus.RUNNING.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.RUNNING.value: {
        JobStatus.WAITING_FEEDBACK.value,
        JobStatus.RETRYING.value,
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.TIMED_OUT.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.WAITING_FEEDBACK.value: {
        JobStatus.QUEUED.value,
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.RETRYING.value: {
        JobStatus.QUEUED.value,
        JobStatus.RUNNING.value,
        JobStatus.FAILED.value,
        JobStatus.TIMED_OUT.value,
        JobStatus.CANCELLED.value,
    },
    JobStatus.COMPLETED.value: set(),
    JobStatus.FAILED.value: set(),
    JobStatus.TIMED_OUT.value: set(),
    JobStatus.CANCELLED.value: set(),
}


class SQLiteJobStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    attempt INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    idempotency_key_hash TEXT UNIQUE,
                    request_hash TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    upstream_run_id TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    retryable INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_question_updated
                    ON jobs(question_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_jobs_status_updated
                    ON jobs(status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS job_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(job_id),
                    event_type TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT,
                    stage TEXT,
                    actor TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            correlation_id=row["correlation_id"],
            kind=row["kind"],
            question_id=row["question_id"],
            mode=row["mode"],
            status=row["status"],
            stage=row["stage"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            attempt=int(row["attempt"]),
            max_attempts=int(row["max_attempts"]),
            upstream_run_id=row["upstream_run_id"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            retryable=bool(row["retryable"]),
            request_payload=json.loads(row["request_json"]),
        )

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection,
        *,
        job_id: str,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        stage: str | None,
        actor: str,
        source: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO job_events(
                job_id, event_type, from_status, to_status, stage,
                actor, source, created_at, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                event_type,
                from_status,
                to_status,
                stage,
                actor,
                source,
                _now(),
                json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
            ),
        )

    def create_job(
        self,
        *,
        request: JobCreateRequest,
        correlation_id: str,
        idempotency_key: str | None = None,
        requested_by: str = "anonymous",
    ) -> tuple[JobRecord, bool]:
        request_json, request_hash = _canonical_request(request)
        idempotency_hash = _key_hash(idempotency_key)
        created_at = _now()
        job_id = str(uuid.uuid4())
        max_attempts = 2 if request.mode == "mock" else 1

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_hash:
                existing = connection.execute(
                    "SELECT * FROM jobs WHERE idempotency_key_hash = ?",
                    (idempotency_hash,),
                ).fetchone()
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise IdempotencyConflict(
                            "相同 Idempotency-Key 已用于不同请求。"
                        )
                    return self._record(existing), True

            connection.execute(
                """
                INSERT INTO jobs(
                    job_id, correlation_id, kind, question_id, mode, status,
                    stage, created_at, updated_at, attempt, max_attempts,
                    idempotency_key_hash, request_hash, request_json, requested_by
                ) VALUES (?, ?, 'research_run', ?, ?, 'queued', 'queued', ?, ?, 0, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    correlation_id,
                    request.question_id,
                    request.mode,
                    created_at,
                    created_at,
                    max_attempts,
                    idempotency_hash,
                    request_hash,
                    request_json,
                    requested_by,
                ),
            )
            self._insert_event(
                connection,
                job_id=job_id,
                event_type="created",
                from_status=None,
                to_status=JobStatus.QUEUED.value,
                stage="queued",
                actor=requested_by,
                source="api",
            )
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._record(row), False

    def get_job(self, job_id: str) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise JobNotFound(job_id)
        return self._record(row)

    @staticmethod
    def _queue_retry_rejection_reasons(
        row: sqlite3.Row,
        *,
        expected_updated_at: str,
    ) -> list[str]:
        reasons: list[str] = []
        if row["status"] != JobStatus.FAILED.value:
            reasons.append("status")
        if row["stage"] != "queue_rejected":
            reasons.append("stage")
        if row["error_code"] != "QUEUE_CAPACITY_EXCEEDED":
            reasons.append("error_code")
        if not bool(row["retryable"]):
            reasons.append("retryable")
        if int(row["attempt"]) != 0:
            reasons.append("attempt")
        if row["started_at"] is not None:
            reasons.append("started_at")
        if row["upstream_run_id"] is not None:
            reasons.append("upstream_run_id")
        if row["updated_at"] != expected_updated_at:
            reasons.append("stale_retry_snapshot")
        return reasons

    def claim_queue_capacity_retry(
        self,
        job_id: str,
        *,
        expected_updated_at: str,
    ) -> tuple[JobRecord, bool]:
        """原子认领从未执行过的容量拒绝 Job。

        该入口刻意不加入通用状态机，避免任意 failed Job 被重新执行。
        expected_updated_at 防止同一批并发请求在首次认领失败后再次认领。
        """
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise JobNotFound(job_id)

            reasons = self._queue_retry_rejection_reasons(
                row,
                expected_updated_at=expected_updated_at,
            )
            if reasons:
                self._insert_event(
                    connection,
                    job_id=job_id,
                    event_type="queue_retry_rejected",
                    from_status=row["status"],
                    to_status=row["status"],
                    stage=row["stage"],
                    actor="api",
                    source="idempotency",
                    details={"reasons": reasons},
                )
                current = connection.execute(
                    "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
                ).fetchone()
                return self._record(current), False

            timestamp = _now()
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, stage = ?, updated_at = ?, finished_at = NULL,
                    error_code = NULL, error_message = NULL, retryable = 0
                WHERE job_id = ?
                """,
                (
                    JobStatus.RETRYING.value,
                    "queue_retry_claimed",
                    timestamp,
                    job_id,
                ),
            )
            self._insert_event(
                connection,
                job_id=job_id,
                event_type="queue_retry_claimed",
                from_status=JobStatus.FAILED.value,
                to_status=JobStatus.RETRYING.value,
                stage="queue_retry_claimed",
                actor="api",
                source="idempotency",
                details={"expected_updated_at": expected_updated_at},
            )
            claimed = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._record(claimed), True

    def mark_queue_retry_submitted(self, job_id: str) -> JobRecord:
        """审计容量重试已进入队列；worker 已推进时不回写旧状态。"""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise JobNotFound(job_id)

            advanced = not (
                row["status"] == JobStatus.RETRYING.value
                and row["stage"] == "queue_retry_claimed"
            )
            stage = row["stage"]
            if not advanced:
                stage = "queue_retry_submitted"
                connection.execute(
                    "UPDATE jobs SET stage = ?, updated_at = ? WHERE job_id = ?",
                    (stage, _now(), job_id),
                )
            self._insert_event(
                connection,
                job_id=job_id,
                event_type="queue_retry_submitted",
                from_status=row["status"],
                to_status=row["status"],
                stage=stage,
                actor="api",
                source="queue",
                details={"state_already_advanced": advanced},
            )
            current = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._record(current)

    def list_jobs(
        self,
        *,
        question_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 20,
    ) -> list[JobRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if question_id:
            clauses.append("question_id = ?")
            params.append(question_id)
        if status:
            clauses.append("status = ?")
            params.append(status.value if isinstance(status, JobStatus) else str(status))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit), 100)))
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM jobs {where} ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._record(row) for row in rows]

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        self.get_job(job_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY event_id",
                (job_id,),
            ).fetchall()
        return [
            {
                **dict(row),
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]

    def transition(
        self,
        job_id: str,
        to_status: JobStatus | str,
        *,
        stage: str | None = None,
        actor: str,
        source: str,
        upstream_run_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        retryable: bool = False,
        increment_attempt: bool = False,
    ) -> JobRecord:
        target = to_status.value if isinstance(to_status, JobStatus) else str(to_status)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise JobNotFound(job_id)
            current = row["status"]
            if target not in _ALLOWED_TRANSITIONS.get(current, set()):
                self._insert_event(
                    connection,
                    job_id=job_id,
                    event_type="transition_rejected",
                    from_status=current,
                    to_status=current,
                    stage=row["stage"],
                    actor=actor,
                    source=source,
                    details={"requested_status": target},
                )
                connection.commit()
                raise InvalidTransition(f"{current} -> {target}")

            timestamp = _now()
            next_stage = stage or target
            started_at = (
                timestamp if target == JobStatus.RUNNING.value and not row["started_at"]
                else row["started_at"]
            )
            finished_at = (
                timestamp
                if target
                in {
                    JobStatus.COMPLETED.value,
                    JobStatus.FAILED.value,
                    JobStatus.TIMED_OUT.value,
                    JobStatus.CANCELLED.value,
                }
                else None
            )
            attempt = int(row["attempt"]) + (1 if increment_attempt else 0)
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, stage = ?, updated_at = ?, started_at = ?,
                    finished_at = ?, attempt = ?, upstream_run_id = COALESCE(?, upstream_run_id),
                    error_code = ?, error_message = ?, retryable = ?
                WHERE job_id = ?
                """,
                (
                    target,
                    next_stage,
                    timestamp,
                    started_at,
                    finished_at,
                    attempt,
                    upstream_run_id,
                    error_code,
                    error_message,
                    int(retryable),
                    job_id,
                ),
            )
            self._insert_event(
                connection,
                job_id=job_id,
                event_type="transition",
                from_status=current,
                to_status=target,
                stage=next_stage,
                actor=actor,
                source=source,
                details={
                    "attempt": attempt,
                    "error_code": error_code,
                    "retryable": retryable,
                },
            )
            updated = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._record(updated)

    def begin_attempt(self, job_id: str) -> JobRecord:
        return self.transition(
            job_id,
            JobStatus.RUNNING,
            stage="initializing",
            actor="worker",
            source="queue",
            increment_attempt=True,
        )

    def update_progress(self, job_id: str, stage: str) -> JobRecord:
        stage = str(stage or "running")[:128]
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise JobNotFound(job_id)
            if row["status"] != JobStatus.RUNNING.value:
                return self._record(row)
            timestamp = _now()
            if row["stage"] != stage:
                connection.execute(
                    "UPDATE jobs SET stage = ?, updated_at = ? WHERE job_id = ?",
                    (stage, timestamp, job_id),
                )
                self._insert_event(
                    connection,
                    job_id=job_id,
                    event_type="progress",
                    from_status=row["status"],
                    to_status=row["status"],
                    stage=stage,
                    actor="worker",
                    source="upstream_progress",
                )
            updated = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._record(updated)

    def recover_interrupted_jobs(self) -> list[str]:
        candidates = self.list_jobs(limit=100)
        recovered: list[str] = []
        for job in candidates:
            if job.status == JobStatus.QUEUED.value:
                recovered.append(job.job_id)
            elif job.status == JobStatus.RETRYING.value:
                self.transition(
                    job.job_id,
                    JobStatus.QUEUED,
                    actor="system",
                    source="startup_recovery",
                )
                recovered.append(job.job_id)
            elif job.status == JobStatus.RUNNING.value:
                if job.mode == "mock" and job.attempt < job.max_attempts:
                    self.transition(
                        job.job_id,
                        JobStatus.RETRYING,
                        actor="system",
                        source="startup_recovery",
                        error_code="PROCESS_RESTARTED",
                        error_message="服务重启，Mock 任务将进行有限重试。",
                        retryable=True,
                    )
                    self.transition(
                        job.job_id,
                        JobStatus.QUEUED,
                        actor="system",
                        source="startup_recovery",
                    )
                    recovered.append(job.job_id)
                else:
                    self.transition(
                        job.job_id,
                        JobStatus.FAILED,
                        actor="system",
                        source="startup_recovery",
                        error_code="PROCESS_RESTARTED_UNSAFE_TO_RETRY",
                        error_message="服务重启后无法安全恢复该任务，请显式重新提交。",
                        retryable=True,
                    )
        return recovered
