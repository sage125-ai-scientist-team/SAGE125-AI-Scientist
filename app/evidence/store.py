"""
T01 EvidenceBundle 持久化存储（stdlib SQLite）。

本模块是 T08 production evidence adapter 的唯一权威真源读/写后端之一。
T08 不得扫描 ``evidence_cards.json``、workflow 临时目录或旧 exports 冒充本端口。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional, Protocol

from app.contracts.evidence import EvidenceBundle

StatusLiteral = Literal["pending", "ready", "failed"]

_IDENTITY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SCHEMA_VERSION = "t01.evidence_bundle_store.v1"
_DEFAULT_TIMEOUT_S = 30.0


class EvidencePortError(RuntimeError):
    """
    T01 owner 读/写端口错误，携带稳定 category 供 T08 HTTP 映射。

    参数：
        category: 错误类别（not_found / not_ready / ...）。
        message: 人类可读说明（不得含绝对路径或密钥）。
        retryable: 是否可重试的上游/存储故障。
    """

    def __init__(
        self,
        category: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable


class EvidenceBundleStore(Protocol):
    """
    T01 公共持久化边界（Protocol）。

    实现必须支持进程重启后按 ``run_id + question_id`` 恢复读取。
    """

    def mark_pending(self, *, run_id: str, question_id: str) -> None:
        """将 identity 标记为 pending（生成中）。"""

    def save_bundle(
        self,
        *,
        run_id: str,
        question_id: str,
        bundle: EvidenceBundle,
    ) -> EvidenceBundle:
        """校验并持久化 ready bundle；同 payload 幂等，异 payload 冲突。"""

    def mark_failed(
        self,
        *,
        run_id: str,
        question_id: str,
        failure_code: str,
        failure_summary: str = "",
    ) -> None:
        """将 identity 标记为稳定失败。"""

    def get_evidence_bundle(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> EvidenceBundle:
        """读取并重验 hash/Schema 后返回 EvidenceBundle。"""


def _utc_now_iso() -> str:
    """
    返回 UTC ISO8601 时间戳字符串。

    返回：
        带 ``Z`` 后缀的时间戳。
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _validate_identity_token(name: str, value: str) -> str:
    """
    校验 identity 令牌格式。

    参数：
        name: 字段名（用于错误消息）。
        value: 原始令牌。

    返回：
        strip 后的合法令牌。

    异常：
        EvidencePortError(invalid_contract): 空或非法字符。
    """
    token = (value or "").strip()
    if not token or not _IDENTITY_RE.fullmatch(token):
        raise EvidencePortError(
            "invalid_contract",
            f"invalid {name}: must be 1..128 of [A-Za-z0-9._:-]",
            retryable=False,
        )
    return token


def _canonical_payload_bytes(bundle: EvidenceBundle) -> bytes:
    """
    生成确定性 canonical JSON 字节（排序键、无多余空白）。

    参数：
        bundle: 已通过契约校验的 EvidenceBundle。

    返回：
        UTF-8 JSON 字节。
    """
    payload = bundle.model_dump(mode="json")
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    """
    计算 SHA-256 十六进制摘要。

    参数：
        data: 原始字节。

    返回：
        小写 hex digest。
    """
    return hashlib.sha256(data).hexdigest()


def default_store_path() -> Path:
    """
    解析默认 SQLite 文件路径。

    环境变量 ``T01_EVIDENCE_STORE_PATH`` 优先；否则使用
    ``exports/evidence_bundle_store/evidence_bundles.sqlite3``（已被 .gitignore）。

    返回：
        SQLite 文件 Path（尚未保证父目录存在）。
    """
    override = os.environ.get("T01_EVIDENCE_STORE_PATH", "").strip()
    if override:
        return Path(override)
    return (
        Path(__file__).resolve().parents[2]
        / "exports"
        / "evidence_bundle_store"
        / "evidence_bundles.sqlite3"
    )


class SqliteEvidenceBundleStore:
    """
    stdlib SQLite 实现的 EvidenceBundleStore。

    唯一 identity：``run_id + question_id``。
    写路径使用 ``BEGIN IMMEDIATE``，降低五并发覆盖风险。
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """
        初始化存储并确保表结构存在。

        参数：
            db_path: 可选 SQLite 路径；默认 ``default_store_path()``。
        """
        self.db_path = Path(db_path) if db_path is not None else default_store_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # 并发安全依赖 SQLite BEGIN IMMEDIATE，不使用进程内大锁串行化写路径。
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """
        打开带超时的 SQLite 连接。

        返回：
            sqlite3.Connection。

        异常：
            EvidencePortError(retryable_upstream_failure): 打不开文件时。
        """
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=_DEFAULT_TIMEOUT_S,
                isolation_level=None,
                check_same_thread=False,
            )
        except sqlite3.Error as exc:
            raise EvidencePortError(
                "retryable_upstream_failure",
                "sqlite connect failed",
                retryable=True,
            ) from exc
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
        except sqlite3.Error:
            # WAL 不可用时仍可继续（例如部分只读文件系统），写路径靠 IMMEDIATE。
            pass
        return conn

    def _ensure_schema(self) -> None:
        """
        创建 evidence_bundles 表（若不存在）。

        异常：
            EvidencePortError: 存储初始化失败。
        """
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS evidence_bundles (
                        run_id TEXT NOT NULL,
                        question_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        payload_json TEXT,
                        payload_sha256 TEXT,
                        failure_code TEXT,
                        failure_summary TEXT,
                        schema_version TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (run_id, question_id)
                    )
                    """
                )
                conn.execute("COMMIT")
        except EvidencePortError:
            raise
        except sqlite3.Error as exc:
            raise EvidencePortError(
                "retryable_upstream_failure",
                "sqlite schema init failed",
                retryable=True,
            ) from exc

    def mark_pending(self, *, run_id: str, question_id: str) -> None:
        """
        将记录标记为 ``pending``（清空 payload）。

        参数：
            run_id: 运行 ID。
            question_id: 题目 ID。

        异常：
            EvidencePortError(invalid_contract): identity 非法。
            EvidencePortError(retryable_upstream_failure): 存储故障。
        """
        run_id = _validate_identity_token("run_id", run_id)
        question_id = _validate_identity_token("question_id", question_id)
        now = _utc_now_iso()
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO evidence_bundles (
                        run_id, question_id, status, payload_json, payload_sha256,
                        failure_code, failure_summary, schema_version,
                        created_at, updated_at
                    ) VALUES (?, ?, 'pending', NULL, NULL, NULL, NULL, ?, ?, ?)
                    ON CONFLICT(run_id, question_id) DO UPDATE SET
                        status='pending',
                        payload_json=NULL,
                        payload_sha256=NULL,
                        failure_code=NULL,
                        failure_summary=NULL,
                        schema_version=excluded.schema_version,
                        updated_at=excluded.updated_at
                    """,
                    (run_id, question_id, _SCHEMA_VERSION, now, now),
                )
                conn.execute("COMMIT")
        except EvidencePortError:
            raise
        except sqlite3.Error as exc:
            raise EvidencePortError(
                "retryable_upstream_failure",
                "sqlite mark_pending failed",
                retryable=True,
            ) from exc

    def mark_failed(
        self,
        *,
        run_id: str,
        question_id: str,
        failure_code: str,
        failure_summary: str = "",
    ) -> None:
        """
        将记录标记为稳定 ``failed``。

        参数：
            run_id: 运行 ID。
            question_id: 题目 ID。
            failure_code: owner 稳定失败码（非空）。
            failure_summary: 可选摘要（不得含绝对路径/密钥）。

        异常：
            EvidencePortError(invalid_contract): 参数非法。
            EvidencePortError(retryable_upstream_failure): 存储故障。
        """
        run_id = _validate_identity_token("run_id", run_id)
        question_id = _validate_identity_token("question_id", question_id)
        code = (failure_code or "").strip()
        if not code or len(code) > 128:
            raise EvidencePortError(
                "invalid_contract",
                "failure_code must be 1..128 chars",
                retryable=False,
            )
        summary = (failure_summary or "").strip()[:500]
        now = _utc_now_iso()
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO evidence_bundles (
                        run_id, question_id, status, payload_json, payload_sha256,
                        failure_code, failure_summary, schema_version,
                        created_at, updated_at
                    ) VALUES (?, ?, 'failed', NULL, NULL, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, question_id) DO UPDATE SET
                        status='failed',
                        payload_json=NULL,
                        payload_sha256=NULL,
                        failure_code=excluded.failure_code,
                        failure_summary=excluded.failure_summary,
                        schema_version=excluded.schema_version,
                        updated_at=excluded.updated_at
                    """,
                    (
                        run_id,
                        question_id,
                        code,
                        summary,
                        _SCHEMA_VERSION,
                        now,
                        now,
                    ),
                )
                conn.execute("COMMIT")
        except EvidencePortError:
            raise
        except sqlite3.Error as exc:
            raise EvidencePortError(
                "retryable_upstream_failure",
                "sqlite mark_failed failed",
                retryable=True,
            ) from exc

    def save_bundle(
        self,
        *,
        run_id: str,
        question_id: str,
        bundle: EvidenceBundle,
    ) -> EvidenceBundle:
        """
        持久化 ready EvidenceBundle。

        语义：
        - 同 identity + 同 payload SHA → 幂等返回已存 bundle；
        - 同 identity + 不同 payload → ``conflict``（non-retryable）；
        - production 成功路径禁止空 evidences（由契约强制）。

        参数：
            run_id: 运行 ID。
            question_id: 题目 ID。
            bundle: EvidenceBundle。

        返回：
            持久化后的 EvidenceBundle（契约校验后的副本）。

        异常：
            EvidencePortError: 见 category。
        """
        run_id = _validate_identity_token("run_id", run_id)
        question_id = _validate_identity_token("question_id", question_id)
        if not isinstance(bundle, EvidenceBundle):
            raise EvidencePortError(
                "invalid_contract",
                "bundle must be EvidenceBundle",
                retryable=False,
            )
        try:
            validated = EvidenceBundle.model_validate(bundle.model_dump(mode="python"))
        except Exception as exc:  # noqa: BLE001 — surface as invalid_contract
            raise EvidencePortError(
                "invalid_contract",
                "bundle failed schema validation",
                retryable=False,
            ) from exc
        if not validated.evidences:
            raise EvidencePortError(
                "invalid_contract",
                "production success must not persist empty evidences",
                retryable=False,
            )
        payload = _canonical_payload_bytes(validated)
        digest = _sha256_hex(payload)
        payload_text = payload.decode("utf-8")
        now = _utc_now_iso()

        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT status, payload_sha256, payload_json
                    FROM evidence_bundles
                    WHERE run_id=? AND question_id=?
                    """,
                    (run_id, question_id),
                ).fetchone()
                if row is not None and row["status"] == "ready":
                    if row["payload_sha256"] == digest:
                        conn.execute("COMMIT")
                        return EvidenceBundle.model_validate(
                            json.loads(row["payload_json"])
                        )
                    conn.execute("ROLLBACK")
                    raise EvidencePortError(
                        "conflict",
                        "ready bundle already exists with different payload",
                        retryable=False,
                    )
                if row is None:
                    try:
                        conn.execute(
                            """
                            INSERT INTO evidence_bundles (
                                run_id, question_id, status, payload_json,
                                payload_sha256, failure_code, failure_summary,
                                schema_version, created_at, updated_at
                            ) VALUES (?, ?, 'ready', ?, ?, NULL, NULL, ?, ?, ?)
                            """,
                            (
                                run_id,
                                question_id,
                                payload_text,
                                digest,
                                _SCHEMA_VERSION,
                                now,
                                now,
                            ),
                        )
                    except sqlite3.IntegrityError:
                        row2 = conn.execute(
                            """
                            SELECT status, payload_sha256, payload_json
                            FROM evidence_bundles
                            WHERE run_id=? AND question_id=?
                            """,
                            (run_id, question_id),
                        ).fetchone()
                        if row2 is None:
                            conn.execute("ROLLBACK")
                            raise EvidencePortError(
                                "retryable_upstream_failure",
                                "sqlite concurrent insert race",
                                retryable=True,
                            )
                        if (
                            row2["status"] == "ready"
                            and row2["payload_sha256"] == digest
                        ):
                            conn.execute("COMMIT")
                            return EvidenceBundle.model_validate(
                                json.loads(row2["payload_json"])
                            )
                        conn.execute("ROLLBACK")
                        raise EvidencePortError(
                            "conflict",
                            "ready bundle already exists with different payload",
                            retryable=False,
                        )
                else:
                    conn.execute(
                        """
                        UPDATE evidence_bundles
                        SET status='ready',
                            payload_json=?,
                            payload_sha256=?,
                            failure_code=NULL,
                            failure_summary=NULL,
                            schema_version=?,
                            updated_at=?
                        WHERE run_id=? AND question_id=?
                          AND status != 'ready'
                        """,
                        (
                            payload_text,
                            digest,
                            _SCHEMA_VERSION,
                            now,
                            run_id,
                            question_id,
                        ),
                    )
                    if conn.total_changes == 0:
                        row3 = conn.execute(
                            """
                            SELECT status, payload_sha256, payload_json
                            FROM evidence_bundles
                            WHERE run_id=? AND question_id=?
                            """,
                            (run_id, question_id),
                        ).fetchone()
                        if (
                            row3 is not None
                            and row3["status"] == "ready"
                            and row3["payload_sha256"] == digest
                        ):
                            conn.execute("COMMIT")
                            return EvidenceBundle.model_validate(
                                json.loads(row3["payload_json"])
                            )
                        conn.execute("ROLLBACK")
                        raise EvidencePortError(
                            "conflict",
                            "ready bundle already exists with different payload",
                            retryable=False,
                        )
                conn.execute("COMMIT")
        except EvidencePortError:
            raise
        except sqlite3.Error as exc:
            raise EvidencePortError(
                "retryable_upstream_failure",
                "sqlite save_bundle failed",
                retryable=True,
            ) from exc
        return validated

    def get_evidence_bundle(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> EvidenceBundle:
        """
        按 identity 读取 ready bundle，并重验 SHA-256 与 Schema。

        参数：
            run_id: 运行 ID。
            question_id: 题目 ID。

        返回：
            EvidenceBundle。

        异常：
            EvidencePortError(not_found|not_ready|invalid_contract|...)。
        """
        run_id = _validate_identity_token("run_id", run_id)
        question_id = _validate_identity_token("question_id", question_id)
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT run_id, question_id, status, payload_json, payload_sha256,
                           failure_code, failure_summary
                    FROM evidence_bundles
                    WHERE run_id=? AND question_id=?
                    """,
                    (run_id, question_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise EvidencePortError(
                "retryable_upstream_failure",
                "sqlite get_evidence_bundle failed",
                retryable=True,
            ) from exc

        if row is None:
            raise EvidencePortError(
                "not_found",
                "no evidence record for identity",
                retryable=False,
            )
        if row["run_id"] != run_id or row["question_id"] != question_id:
            raise EvidencePortError(
                "identity_mismatch",
                "stored identity does not match request",
                retryable=False,
            )
        status = row["status"]
        if status == "pending":
            raise EvidencePortError(
                "not_ready",
                "evidence bundle pending",
                retryable=False,
            )
        if status == "failed":
            code = row["failure_code"] or "owner_failed"
            summary = row["failure_summary"] or ""
            raise EvidencePortError(
                "non_retryable_upstream_failure",
                f"evidence bundle failed: {code}"
                + (f" ({summary})" if summary else ""),
                retryable=False,
            )
        if status != "ready":
            raise EvidencePortError(
                "unavailable",
                f"unknown evidence status: {status}",
                retryable=False,
            )
        raw = row["payload_json"]
        expected = row["payload_sha256"]
        if not raw or not expected:
            raise EvidencePortError(
                "invalid_contract",
                "ready record missing payload or hash",
                retryable=False,
            )
        data = raw.encode("utf-8")
        actual = _sha256_hex(data)
        if actual != expected:
            raise EvidencePortError(
                "invalid_contract",
                "payload hash mismatch (tamper or corruption)",
                retryable=False,
            )
        try:
            parsed: dict[str, Any] = json.loads(raw)
            bundle = EvidenceBundle.model_validate(parsed)
        except Exception as exc:  # noqa: BLE001
            raise EvidencePortError(
                "invalid_contract",
                "payload failed schema validation",
                retryable=False,
            ) from exc
        if not bundle.evidences:
            raise EvidencePortError(
                "invalid_contract",
                "production success must not return empty bundle",
                retryable=False,
            )
        return bundle

    def get_record_status(
        self,
        *,
        run_id: str,
        question_id: str,
    ) -> Optional[StatusLiteral]:
        """
        返回记录状态或 None（不存在）。

        参数：
            run_id: 运行 ID。
            question_id: 题目 ID。

        返回：
            ``pending`` / ``ready`` / ``failed`` / ``None``。
        """
        run_id = _validate_identity_token("run_id", run_id)
        question_id = _validate_identity_token("question_id", question_id)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status FROM evidence_bundles
                WHERE run_id=? AND question_id=?
                """,
                (run_id, question_id),
            ).fetchone()
        if row is None:
            return None
        return str(row["status"])  # type: ignore[return-value]


_GLOBAL_STORE: SqliteEvidenceBundleStore | None = None
_GLOBAL_LOCK = threading.Lock()


def get_default_store() -> SqliteEvidenceBundleStore:
    """
    返回进程内默认 store 单例（指向默认路径；数据在 SQLite 文件中）。

    返回：
        SqliteEvidenceBundleStore。
    """
    global _GLOBAL_STORE
    with _GLOBAL_LOCK:
        if _GLOBAL_STORE is None:
            _GLOBAL_STORE = SqliteEvidenceBundleStore()
        return _GLOBAL_STORE


def reset_default_store_for_tests() -> None:
    """
    测试辅助：丢弃默认 store 单例（不删除文件）。

    返回：
        None。
    """
    global _GLOBAL_STORE
    with _GLOBAL_LOCK:
        _GLOBAL_STORE = None
