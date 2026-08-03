"""Persistence port and SQLite adapter for immutable T03 feedback records."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from app.contracts.validation import (
    AuditLineage,
    AuditLineageEvent,
    FeedbackDecision,
    FeedbackRecord,
)
from app.feedback.errors import (
    CorruptFeedbackSnapshot,
    FeedbackConflict,
    FeedbackNotFound,
    FeedbackStorageError,
    FingerprintConflict,
    IdempotencyConflict,
    LineageNotFound,
    UnsupportedFeedbackSchema,
)


@runtime_checkable
class FeedbackStore(Protocol):
    """Storage adapter implemented by the Wave B persistence layer."""

    def save_feedback(self, record: FeedbackRecord) -> FeedbackRecord:
        """Persist one immutable submission or return its idempotent match."""
        ...

    def get_feedback(self, feedback_id: str) -> FeedbackRecord:
        """Return one immutable feedback record or raise ``KeyError``."""
        ...

    def save_decision(self, decision: FeedbackDecision) -> FeedbackDecision:
        """Create one decision; reject attempts to overwrite an existing one."""
        ...

    def get_decision(self, feedback_id: str) -> FeedbackDecision | None:
        """Return the decision for a feedback record when one exists."""
        ...

    def save_decision_and_append(
        self,
        lineage_id: str,
        decision: FeedbackDecision,
        event: AuditLineageEvent,
    ) -> tuple[FeedbackDecision, AuditLineage]:
        """Atomically create a decision and bind its audit event."""
        ...

    def save_lineage(self, lineage: AuditLineage) -> AuditLineage:
        """Create one lineage; reject replacement of an existing lineage."""
        ...

    def append_lineage_event(
        self,
        lineage_id: str,
        event: AuditLineageEvent,
    ) -> AuditLineage:
        """Atomically append one event and return the new lineage snapshot."""
        ...

    def get_lineage(self, lineage_id: str) -> AuditLineage:
        """Return one lineage or raise ``KeyError``."""
        ...

    def get_lineage_by_feedback(self, feedback_id: str) -> AuditLineage:
        """Resolve the unique lineage for one feedback record."""
        ...


def _canonical_payload(value: FeedbackRecord | FeedbackDecision | AuditLineage) -> str:
    """Serialize through the public v1 JSON shape, never Python internals."""
    return json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _feedback_snapshot(payload: str) -> FeedbackRecord:
    try:
        return FeedbackRecord.model_validate_json(payload)
    except (ValidationError, ValueError) as exc:
        raise CorruptFeedbackSnapshot("stored feedback snapshot is invalid") from exc


def _decision_snapshot(payload: str) -> FeedbackDecision:
    try:
        return FeedbackDecision.model_validate_json(payload)
    except (ValidationError, ValueError, AttributeError) as exc:
        raise CorruptFeedbackSnapshot("stored decision snapshot is invalid") from exc


def _lineage_snapshot(payload: str) -> AuditLineage:
    try:
        return AuditLineage.model_validate_json(payload)
    except (ValidationError, ValueError) as exc:
        raise CorruptFeedbackSnapshot("stored lineage snapshot is invalid") from exc


def _same_request(left: FeedbackRecord, right: FeedbackRecord) -> bool:
    """Compare the semantic request while ignoring server-generated envelope fields."""
    fields = (
        "run_id",
        "question_id",
        "target_version_id",
        "feedback",
        "source",
        "metadata",
    )
    return all(
        left.model_dump(mode="json")[field] == right.model_dump(mode="json")[field]
        for field in fields
    )


class SQLiteFeedbackStore:
    """Durable create-only feedback store with atomic lineage updates.

    Each operation owns a short SQLite transaction. WAL and ``BEGIN IMMEDIATE``
    make duplicate or concurrent submissions deterministic across threads and
    processes. Every read is validated back through the frozen v1 contracts.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.path = Path(path) if str(path) != ":memory:" else None
        self.timeout_seconds = timeout_seconds
        self._anchor: sqlite3.Connection | None = None
        if str(path) == ":memory:":
            self._database = (
                f"file:t03-feedback-{uuid.uuid4().hex}?mode=memory&cache=shared"
            )
            self._uri = True
            self._anchor = self._new_connection()
        else:
            self._database = str(self.path)
            self._uri = False
        self.initialize()

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database,
            timeout=self.timeout_seconds,
            uri=self._uri,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            f"PRAGMA busy_timeout = {max(1, int(self.timeout_seconds * 1000))}"
        )
        return connection

    def _connect(self) -> sqlite3.Connection:
        return self._new_connection()

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _write_transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create or safely reopen the Wave B schema."""
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._read_connection() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                schema_version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                if schema_version > 1:
                    raise UnsupportedFeedbackSchema(
                        "future feedback database schema is unsupported"
                    )
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS feedback_records (
                        feedback_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        question_id TEXT NOT NULL,
                        target_version_id TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL UNIQUE,
                        idempotency_key_hash TEXT UNIQUE,
                        payload_json TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_feedback_run_question
                        ON feedback_records(run_id, question_id);
                    CREATE INDEX IF NOT EXISTS idx_feedback_target_version
                        ON feedback_records(target_version_id);

                    CREATE TABLE IF NOT EXISTS feedback_idempotency_keys (
                        key_hash TEXT PRIMARY KEY,
                        request_fingerprint TEXT NOT NULL,
                        feedback_id TEXT NOT NULL
                            REFERENCES feedback_records(feedback_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_feedback_idempotency_record
                        ON feedback_idempotency_keys(feedback_id);

                    CREATE TABLE IF NOT EXISTS feedback_decisions (
                        decision_id TEXT PRIMARY KEY,
                        feedback_id TEXT NOT NULL UNIQUE
                            REFERENCES feedback_records(feedback_id),
                        payload_json TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS feedback_lineages (
                        lineage_id TEXT PRIMARY KEY,
                        feedback_id TEXT NOT NULL UNIQUE
                            REFERENCES feedback_records(feedback_id),
                        payload_json TEXT NOT NULL
                    );
                    """
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO feedback_idempotency_keys(
                        key_hash, request_fingerprint, feedback_id
                    )
                    SELECT idempotency_key_hash, request_fingerprint, feedback_id
                    FROM feedback_records
                    WHERE idempotency_key_hash IS NOT NULL
                    """
                )
                connection.execute("PRAGMA user_version = 1")
                connection.commit()
        except UnsupportedFeedbackSchema:
            raise
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to initialize feedback storage") from exc

    def close(self) -> None:
        """Release the keeper connection used only by shared in-memory stores."""
        if self._anchor is not None:
            self._anchor.close()
            self._anchor = None

    @staticmethod
    def _feedback_by(
        connection: sqlite3.Connection,
        column: str,
        value: str,
    ) -> FeedbackRecord | None:
        if column not in {
            "feedback_id",
            "request_fingerprint",
            "idempotency_key_hash",
        }:
            raise ValueError("unsupported feedback lookup")
        row = connection.execute(
            f"SELECT payload_json FROM feedback_records WHERE {column} = ?",
            (value,),
        ).fetchone()
        return None if row is None else _feedback_snapshot(row["payload_json"])

    @classmethod
    def _bind_idempotency_key(
        cls,
        connection: sqlite3.Connection,
        record: FeedbackRecord,
        key_hash: str | None,
    ) -> None:
        if key_hash is None:
            return
        row = connection.execute(
            """
            SELECT request_fingerprint, feedback_id
            FROM feedback_idempotency_keys
            WHERE key_hash = ?
            """,
            (key_hash,),
        ).fetchone()
        if row is not None:
            if (
                row["request_fingerprint"] != record.request_fingerprint
                or row["feedback_id"] != record.feedback_id
            ):
                raise IdempotencyConflict(
                    "idempotency key was already used for another request"
                )
            return
        connection.execute(
            """
            INSERT INTO feedback_idempotency_keys(
                key_hash, request_fingerprint, feedback_id
            ) VALUES (?, ?, ?)
            """,
            (key_hash, record.request_fingerprint, record.feedback_id),
        )

    @classmethod
    def _resolve_feedback_duplicate(
        cls,
        connection: sqlite3.Connection,
        record: FeedbackRecord,
    ) -> FeedbackRecord | None:
        by_id = cls._feedback_by(connection, "feedback_id", record.feedback_id)
        if by_id is not None:
            if _canonical_payload(by_id) == _canonical_payload(record):
                cls._bind_idempotency_key(
                    connection,
                    by_id,
                    record.idempotency_key_hash,
                )
                return by_id
            raise FeedbackConflict("feedback_id already identifies another snapshot")

        if record.idempotency_key_hash is not None:
            alias = connection.execute(
                """
                SELECT request_fingerprint, feedback_id
                FROM feedback_idempotency_keys
                WHERE key_hash = ?
                """,
                (record.idempotency_key_hash,),
            ).fetchone()
            if alias is not None:
                by_key = cls._feedback_by(
                    connection,
                    "feedback_id",
                    alias["feedback_id"],
                )
                if by_key is None:
                    raise CorruptFeedbackSnapshot(
                        "idempotency key references missing feedback"
                    )
                if (
                    alias["request_fingerprint"] == record.request_fingerprint
                    and by_key.request_fingerprint == record.request_fingerprint
                    and _same_request(by_key, record)
                ):
                    return by_key
                raise IdempotencyConflict(
                    "idempotency key was already used for another request"
                )

        by_fingerprint = cls._feedback_by(
            connection,
            "request_fingerprint",
            record.request_fingerprint,
        )
        if by_fingerprint is not None:
            if _same_request(by_fingerprint, record):
                cls._bind_idempotency_key(
                    connection,
                    by_fingerprint,
                    record.idempotency_key_hash,
                )
                return by_fingerprint
            raise FingerprintConflict(
                "request fingerprint collides with different feedback"
            )
        return None

    @classmethod
    def _save_feedback_in_transaction(
        cls,
        connection: sqlite3.Connection,
        record: FeedbackRecord,
    ) -> tuple[FeedbackRecord, bool]:
        # Round-trip before the write so corrupt/mutable callers cannot cross the port.
        snapshot = _feedback_snapshot(_canonical_payload(record))
        duplicate = cls._resolve_feedback_duplicate(connection, snapshot)
        if duplicate is not None:
            return duplicate, False
        connection.execute(
            """
            INSERT INTO feedback_records(
                feedback_id, run_id, question_id, target_version_id,
                request_fingerprint, idempotency_key_hash, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.feedback_id,
                snapshot.run_id,
                snapshot.question_id,
                snapshot.target_version_id,
                snapshot.request_fingerprint,
                snapshot.idempotency_key_hash,
                _canonical_payload(snapshot),
            ),
        )
        cls._bind_idempotency_key(
            connection,
            snapshot,
            snapshot.idempotency_key_hash,
        )
        return snapshot, True

    def save_feedback(self, record: FeedbackRecord) -> FeedbackRecord:
        try:
            with self._write_transaction() as connection:
                saved, _ = self._save_feedback_in_transaction(connection, record)
                return saved
        except (FeedbackConflict, CorruptFeedbackSnapshot):
            raise
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to save feedback") from exc

    def get_feedback(self, feedback_id: str) -> FeedbackRecord:
        try:
            with self._read_connection() as connection:
                record = self._feedback_by(connection, "feedback_id", feedback_id)
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to read feedback") from exc
        if record is None:
            raise FeedbackNotFound(f"feedback not found: {feedback_id}")
        return record

    @staticmethod
    def _decision_by_feedback(
        connection: sqlite3.Connection,
        feedback_id: str,
    ) -> FeedbackDecision | None:
        row = connection.execute(
            "SELECT payload_json FROM feedback_decisions WHERE feedback_id = ?",
            (feedback_id,),
        ).fetchone()
        return None if row is None else _decision_snapshot(row["payload_json"])

    @staticmethod
    def _decision_by_id(
        connection: sqlite3.Connection,
        decision_id: str,
    ) -> FeedbackDecision | None:
        row = connection.execute(
            "SELECT payload_json FROM feedback_decisions WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        return None if row is None else _decision_snapshot(row["payload_json"])

    @classmethod
    def _save_decision_in_transaction(
        cls,
        connection: sqlite3.Connection,
        decision: FeedbackDecision,
    ) -> tuple[FeedbackDecision, bool]:
        snapshot = _decision_snapshot(_canonical_payload(decision))
        record = cls._feedback_by(connection, "feedback_id", snapshot.feedback_id)
        if record is None:
            raise FeedbackNotFound(
                f"feedback not found: {snapshot.feedback_id}"
            )
        if record.target_version_id != snapshot.target_version_id:
            raise FeedbackConflict("decision targets a different feedback version")

        by_feedback = cls._decision_by_feedback(connection, snapshot.feedback_id)
        if by_feedback is not None:
            if _canonical_payload(by_feedback) == _canonical_payload(snapshot):
                return by_feedback, False
            raise FeedbackConflict("feedback already has another decision")
        by_id = cls._decision_by_id(connection, snapshot.decision_id)
        if by_id is not None:
            if _canonical_payload(by_id) == _canonical_payload(snapshot):
                return by_id, False
            raise FeedbackConflict("decision_id already identifies another snapshot")
        connection.execute(
            """
            INSERT INTO feedback_decisions(decision_id, feedback_id, payload_json)
            VALUES (?, ?, ?)
            """,
            (snapshot.decision_id, snapshot.feedback_id, _canonical_payload(snapshot)),
        )
        return snapshot, True

    def save_decision(self, decision: FeedbackDecision) -> FeedbackDecision:
        try:
            with self._write_transaction() as connection:
                saved, _ = self._save_decision_in_transaction(connection, decision)
                return saved
        except (FeedbackConflict, FeedbackNotFound, CorruptFeedbackSnapshot):
            raise
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to save feedback decision") from exc

    def get_decision(self, feedback_id: str) -> FeedbackDecision | None:
        try:
            with self._read_connection() as connection:
                return self._decision_by_feedback(connection, feedback_id)
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to read feedback decision") from exc

    @staticmethod
    def _lineage_by_id(
        connection: sqlite3.Connection,
        lineage_id: str,
    ) -> AuditLineage | None:
        row = connection.execute(
            "SELECT payload_json FROM feedback_lineages WHERE lineage_id = ?",
            (lineage_id,),
        ).fetchone()
        return None if row is None else _lineage_snapshot(row["payload_json"])

    @staticmethod
    def _lineage_by_feedback(
        connection: sqlite3.Connection,
        feedback_id: str,
    ) -> AuditLineage | None:
        row = connection.execute(
            "SELECT payload_json FROM feedback_lineages WHERE feedback_id = ?",
            (feedback_id,),
        ).fetchone()
        return None if row is None else _lineage_snapshot(row["payload_json"])

    @classmethod
    def _save_lineage_in_transaction(
        cls,
        connection: sqlite3.Connection,
        lineage: AuditLineage,
    ) -> tuple[AuditLineage, bool]:
        snapshot = _lineage_snapshot(_canonical_payload(lineage))
        record = cls._feedback_by(connection, "feedback_id", snapshot.feedback_id)
        if record is None:
            raise FeedbackNotFound(
                f"feedback not found: {snapshot.feedback_id}"
            )
        if (
            snapshot.run_id != record.run_id
            or snapshot.question_id != record.question_id
            or snapshot.target_version_id != record.target_version_id
            or snapshot.feedback_sha256 != record.fingerprint()
        ):
            raise FeedbackConflict("lineage does not match its feedback snapshot")

        by_feedback = cls._lineage_by_feedback(connection, snapshot.feedback_id)
        if by_feedback is not None:
            if _canonical_payload(by_feedback) == _canonical_payload(snapshot):
                return by_feedback, False
            raise FeedbackConflict("feedback already has another lineage")
        by_id = cls._lineage_by_id(connection, snapshot.lineage_id)
        if by_id is not None:
            if _canonical_payload(by_id) == _canonical_payload(snapshot):
                return by_id, False
            raise FeedbackConflict("lineage_id already identifies another snapshot")
        connection.execute(
            """
            INSERT INTO feedback_lineages(lineage_id, feedback_id, payload_json)
            VALUES (?, ?, ?)
            """,
            (snapshot.lineage_id, snapshot.feedback_id, _canonical_payload(snapshot)),
        )
        return snapshot, True

    def save_lineage(self, lineage: AuditLineage) -> AuditLineage:
        try:
            with self._write_transaction() as connection:
                saved, _ = self._save_lineage_in_transaction(connection, lineage)
                return saved
        except (FeedbackConflict, FeedbackNotFound, CorruptFeedbackSnapshot):
            raise
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to save feedback lineage") from exc

    def save_submission(
        self,
        record: FeedbackRecord,
        lineage: AuditLineage,
    ) -> tuple[FeedbackRecord, AuditLineage]:
        """Atomically save one feedback record and its starting lineage.

        This is a concrete adapter capability, intentionally not a new required
        method on the frozen ``FeedbackStore`` protocol.
        """
        if lineage.feedback_id != record.feedback_id:
            raise FeedbackConflict("submission lineage references another feedback")
        try:
            with self._write_transaction() as connection:
                saved_record, created = self._save_feedback_in_transaction(
                    connection,
                    record,
                )
                if not created:
                    existing_lineage = self._lineage_by_feedback(
                        connection,
                        saved_record.feedback_id,
                    )
                    if existing_lineage is None:
                        raise FeedbackStorageError(
                            "deduplicated feedback is missing its lineage"
                        )
                    return saved_record, existing_lineage
                saved_lineage, _ = self._save_lineage_in_transaction(
                    connection,
                    lineage,
                )
                return saved_record, saved_lineage
        except (
            FeedbackConflict,
            FeedbackNotFound,
            FeedbackStorageError,
            CorruptFeedbackSnapshot,
        ):
            raise
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to save feedback submission") from exc

    def save_decision_and_append(
        self,
        lineage_id: str,
        decision: FeedbackDecision,
        event: AuditLineageEvent,
    ) -> tuple[FeedbackDecision, AuditLineage]:
        try:
            with self._write_transaction() as connection:
                lineage = self._lineage_by_id(connection, lineage_id)
                if lineage is None:
                    raise LineageNotFound(f"lineage not found: {lineage_id}")
                saved_decision, _ = self._save_decision_in_transaction(
                    connection,
                    decision,
                )
                if lineage.decision_id is not None:
                    if (
                        lineage.decision_id == saved_decision.decision_id
                        and lineage.decision_sha256 == saved_decision.fingerprint()
                    ):
                        existing_event = next(
                            (
                                item
                                for item in lineage.events
                                if item.event_type == "feedback_decided"
                            ),
                            None,
                        )
                        if existing_event != event:
                            raise FeedbackConflict(
                                "decision retry event conflicts with audit history"
                            )
                        return saved_decision, lineage
                    raise FeedbackConflict("lineage already contains another decision")
                updated = lineage.bind_decision(saved_decision, event)
                connection.execute(
                    "UPDATE feedback_lineages SET payload_json = ? WHERE lineage_id = ?",
                    (_canonical_payload(updated), lineage_id),
                )
                return saved_decision, _lineage_snapshot(_canonical_payload(updated))
        except (
            FeedbackConflict,
            FeedbackNotFound,
            LineageNotFound,
            CorruptFeedbackSnapshot,
        ):
            raise
        except ValueError as exc:
            raise FeedbackConflict(
                "decision audit event conflicts with its lineage"
            ) from exc
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to save decision audit event") from exc

    def append_lineage_event(
        self,
        lineage_id: str,
        event: AuditLineageEvent,
    ) -> AuditLineage:
        try:
            with self._write_transaction() as connection:
                lineage = self._lineage_by_id(connection, lineage_id)
                if lineage is None:
                    raise LineageNotFound(f"lineage not found: {lineage_id}")
                existing = next(
                    (item for item in lineage.events if item.event_id == event.event_id),
                    None,
                )
                if existing is not None:
                    if existing == event:
                        return lineage
                    raise FeedbackConflict("event_id already identifies another event")
                updated = lineage.append(event)
                connection.execute(
                    "UPDATE feedback_lineages SET payload_json = ? WHERE lineage_id = ?",
                    (_canonical_payload(updated), lineage_id),
                )
                return _lineage_snapshot(_canonical_payload(updated))
        except (
            FeedbackConflict,
            LineageNotFound,
            CorruptFeedbackSnapshot,
        ):
            raise
        except ValueError as exc:
            raise FeedbackConflict(
                "audit event conflicts with its lineage"
            ) from exc
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to append feedback lineage") from exc

    def get_lineage(self, lineage_id: str) -> AuditLineage:
        try:
            with self._read_connection() as connection:
                lineage = self._lineage_by_id(connection, lineage_id)
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to read feedback lineage") from exc
        if lineage is None:
            raise LineageNotFound(f"lineage not found: {lineage_id}")
        return lineage

    def get_lineage_by_feedback(self, feedback_id: str) -> AuditLineage:
        try:
            with self._read_connection() as connection:
                lineage = self._lineage_by_feedback(connection, feedback_id)
        except sqlite3.Error as exc:
            raise FeedbackStorageError("unable to read feedback lineage") from exc
        if lineage is None:
            raise LineageNotFound(
                f"lineage not found for feedback: {feedback_id}"
            )
        return lineage


__all__ = ["FeedbackStore", "SQLiteFeedbackStore"]
