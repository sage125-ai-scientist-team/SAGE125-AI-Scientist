"""
T01 → T08 生产证据读端口（公共 import 面）。

T08 仅应依赖本模块导出的函数/类型；不得修改 ``app/evidence/**`` 实现细节，
也不得扫描 ``evidence_cards.json`` / workflow 临时目录冒充权威源。
"""

from __future__ import annotations

from app.contracts.evidence import EvidenceBundle
from app.evidence.store import (
    EvidenceBundleStore,
    EvidencePortError,
    SqliteEvidenceBundleStore,
    default_store_path,
    get_default_store,
)


def mark_evidence_pending(
    *,
    run_id: str,
    question_id: str,
    store: EvidenceBundleStore | None = None,
) -> None:
    """
    将 ``run_id+question_id`` 标记为 pending（生成中）。

    参数：
        run_id: 运行 ID。
        question_id: 题目 ID。
        store: 可选自定义 store；默认进程 store。

    返回：
        None。

    异常：
        EvidencePortError: identity 非法或存储故障。
    """
    backend = store or get_default_store()
    backend.mark_pending(run_id=run_id, question_id=question_id)


def save_evidence_bundle(
    *,
    run_id: str,
    question_id: str,
    bundle: EvidenceBundle,
    store: EvidenceBundleStore | None = None,
) -> EvidenceBundle:
    """
    在 T01 校验后主动持久化 EvidenceBundle（ready）。

    参数：
        run_id: 运行 ID。
        question_id: 题目 ID。
        bundle: 非空 EvidenceBundle。
        store: 可选自定义 store。

    返回：
        已持久化的 EvidenceBundle。

    异常：
        EvidencePortError: 冲突 / 非法契约 / 可重试存储故障。
    """
    backend = store or get_default_store()
    return backend.save_bundle(
        run_id=run_id,
        question_id=question_id,
        bundle=bundle,
    )


def mark_evidence_failed(
    *,
    run_id: str,
    question_id: str,
    failure_code: str,
    failure_summary: str = "",
    store: EvidenceBundleStore | None = None,
) -> None:
    """
    将 identity 标记为稳定失败（供 T08 映射非重试错误）。

    参数：
        run_id: 运行 ID。
        question_id: 题目 ID。
        failure_code: owner 稳定失败码。
        failure_summary: 可选摘要。
        store: 可选自定义 store。

    返回：
        None。
    """
    backend = store or get_default_store()
    backend.mark_failed(
        run_id=run_id,
        question_id=question_id,
        failure_code=failure_code,
        failure_summary=failure_summary,
    )


def get_evidence_bundle(
    *,
    run_id: str,
    question_id: str,
    store: EvidenceBundleStore | None = None,
) -> EvidenceBundle:
    """
    生产只读入口：按 identity 返回权威 EvidenceBundle。

    参数：
        run_id: 运行 ID。
        question_id: 题目 ID。
        store: 可选自定义 store。

    返回：
        EvidenceBundle（hash + Schema 重验后）。

    异常：
        EvidencePortError:
            - ``not_found`` / ``not_ready`` / ``invalid_contract`` /
              ``identity_mismatch`` / ``conflict`` /
              ``retryable_upstream_failure`` / ``non_retryable_upstream_failure`` /
              ``unavailable``
    """
    backend = store or get_default_store()
    return backend.get_evidence_bundle(run_id=run_id, question_id=question_id)


__all__ = [
    "EvidenceBundleStore",
    "EvidencePortError",
    "SqliteEvidenceBundleStore",
    "default_store_path",
    "get_evidence_bundle",
    "get_default_store",
    "mark_evidence_failed",
    "mark_evidence_pending",
    "save_evidence_bundle",
]
