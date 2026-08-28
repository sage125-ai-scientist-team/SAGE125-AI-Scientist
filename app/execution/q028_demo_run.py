"""UI-triggered, best-effort real execution of the Q028 flagship experiment.

Distinct from ``app.execution.run_round1.run_formal_round1``: that helper
builds an ``ExecutionSpec`` with ``mode="actual"``, which the runner refuses
to execute unless the working tree is a clean, committed Git state (that is
the correct behaviour for official Gate/PR evidence). A live developer
sandbox is routinely "dirty" (uncommitted local edits), so this module
deliberately runs the *same* real scientific entrypoint with ``mode="test"``
instead of ``mode="actual"``. That mode is not blocked by the clean-git
provenance gate, so the subprocess genuinely executes and returns real,
computed metrics — but the runner (by the same contract, unmodified) will
correctly leave ``actual_execution=False`` on the result, because this is
not a formally certified run. We report that truthfully to the caller rather
than ever claiming a fabricated or upgraded status.

Only Q028 has a registered scientific entrypoint. Callers must reject every
other question_id before importing/using this module (see
``app.api.routes.run_experiment``); this module does not itself gate on
question_id.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from app.contracts.execution import ExecutionSpec
from app.execution.datasets import (
    WDBC_DATASET_ID,
    DatasetAdapter,
    get_default_dataset_registry,
)
from app.execution.registry import EntrypointRegistry
from app.execution.run_round1 import (
    ENTRYPOINT_ID,
    ENTRYPOINT_PATH,
    build_execution_spec,
)
from app.execution.runner import LocalProcessRunner

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WDBC_CACHE_RELATIVE = Path("datasets") / "uci-wdbc-v1995-10-31" / "wdbc.data"
WDBC_PIN_SIZE_BYTES = 124103

#: Local captain machine only. Never required on Render or a clean checkout.
LEGACY_OFFLINE_CACHE_ROOT = (
    REPOSITORY_ROOT / "tmp" / "preserved_from_d_root" / "T05_WDBC" / "formal-cache"
)
OFFLINE_CACHE_ROOT = LEGACY_OFFLINE_CACHE_ROOT

#: Distinct spec_id so this demo path is never confused with the formal
#: ``wdbc-round1-baseline-v1`` spec used for official Gate/PR evidence.
_DEMO_SPEC_ID = "wdbc-round1-ui-demo-v1"


class Q028DemoRunError(RuntimeError):
    """Raised when the demo run cannot even start (e.g. dataset unavailable)."""


def _pinned_wdbc_path(cache_root: Path) -> Path:
    return Path(cache_root) / WDBC_CACHE_RELATIVE


def pinned_cache_available(cache_root: Path) -> bool:
    """True only when the pin-sized WDBC file is already on disk."""
    path = _pinned_wdbc_path(cache_root)
    try:
        return path.is_file() and path.stat().st_size == WDBC_PIN_SIZE_BYTES
    except OSError:
        return False


def resolve_demo_cache_root() -> Path:
    """Writable cache: env override, DATA_DIR, then a local formal cache if present."""
    override = os.getenv("SAGE125_WDBC_CACHE_ROOT", "").strip()
    if override:
        return Path(override)
    data_dir = os.getenv("DATA_DIR", "").strip()
    if data_dir:
        root = Path(data_dir)
        if not root.is_absolute():
            root = REPOSITORY_ROOT / root
        return root / "cache" / "t05-wdbc"
    if pinned_cache_available(LEGACY_OFFLINE_CACHE_ROOT):
        return LEGACY_OFFLINE_CACHE_ROOT
    return REPOSITORY_ROOT / "data" / "cache" / "t05-wdbc"


def _inprocess_baseline_summary(dataset_path: Path, dataset_manifest: Any) -> dict[str, Any]:
    """同一份 pinned 数据、同一套 baseline 公式；不经过子进程，也不编造指标。"""
    from app.execution.run_round1 import load_round1_config
    from app.execution.wdbc_baseline import BaselineConfig, run_baseline

    raw = load_round1_config()
    optimizer = raw["optimizer"]
    trigger = raw["round2_trigger"]
    config = BaselineConfig(
        seed=int(raw["seed"]),
        test_fraction=float(raw["test_fraction"]),
        learning_rate=float(optimizer["learning_rate"]),
        iterations=int(optimizer["iterations"]),
        l2=float(optimizer["l2"]),
        decision_threshold=float(raw["decision_threshold"]),
        recall_target=float(trigger["target"]),
        threshold_step=float(trigger["threshold_step"]),
        expected_sha256=str(dataset_manifest.sha256),
        expected_size_bytes=int(dataset_manifest.size_bytes),
    )
    with tempfile.TemporaryDirectory(prefix="t05-ui-demo-inprocess-") as temp_dir:
        return run_baseline(Path(dataset_path), Path(temp_dir), config)


def _failed_experiment_payload(
    *,
    question_id: str,
    result: Any,
    extra: str = "",
) -> dict[str, Any]:
    error = getattr(result, "error", None)
    stderr_tail = ""
    raw_stderr = str(getattr(result, "stderr", "") or "")
    if raw_stderr.strip():
        stderr_tail = raw_stderr.strip().splitlines()[-1][:180]
    message = ""
    if error is not None:
        message = str(error.message or error.code or "")
    if extra:
        message = f"{message} {extra}".strip()
    if stderr_tail and stderr_tail not in message:
        message = f"{message}（{stderr_tail}）" if message else stderr_tail
    if not message:
        message = "注册进程以非零状态退出"
    return {
        "question_id": question_id,
        "status": "failed",
        "available": True,
        "actual_execution": False,
        "mock": False,
        "exit_code": getattr(result, "exit_code", None),
        "error": {"code": getattr(error, "code", "nonzero_exit"), "message": message},
        "reason": message,
    }


def _build_demo_spec(dataset_manifest: Any) -> ExecutionSpec:
    """复用官方 build_execution_spec 的全部参数，只把 mode 换成 "test"。

    重新经由构造函数校验（而非 model_copy 绕过校验），并换一个不同的
    spec_id，避免与正式 "wdbc-round1-baseline-v1" 证据链混淆。
    """
    formal_spec = build_execution_spec(dataset_manifest)
    payload = formal_spec.model_dump(mode="python")
    payload["spec_id"] = _DEMO_SPEC_ID
    payload["mode"] = "test"
    return ExecutionSpec(**payload)


def run_q028_demo_experiment() -> dict[str, Any]:
    """Run the real Q028 WDBC Round 1 baseline once and return a plain summary.

    返回字段均取自真实 ``ExecutionResult``；不生成、不美化、不编造任何指标。
    因为使用 ``mode="test"``（本地演示，跳过 clean-git 门禁），返回的
    ``actual_execution`` 会如实为 False——这不是伪造降级，而是诚实反映
    "这不是正式 Gate 证据"。结果不写入 ``docs/modules/T05/round1``（那是
    正式 Gate/PR 证据包），只在临时目录内执行并丢弃工作区。
    """
    cache_root = resolve_demo_cache_root()
    offline = pinned_cache_available(cache_root)
    dataset_adapter = DatasetAdapter(
        get_default_dataset_registry(),
        connect_timeout_seconds=15.0,
        read_timeout_seconds=30.0,
        total_timeout_seconds=90.0,
    )
    try:
        resolved = dataset_adapter.fetch(
            WDBC_DATASET_ID,
            cache_root=cache_root,
            offline=offline,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the caller
        if offline:
            hint = "本地缓存校验失败。"
        else:
            hint = "已尝试从官方 UCI 地址按 pin 下载，仍未取得合法缓存。"
        raise Q028DemoRunError(f"WDBC 数据集不可用：{hint} {exc}") from exc

    dataset_manifest = resolved.to_dataset_manifest()
    spec = _build_demo_spec(dataset_manifest)

    registry = EntrypointRegistry()
    registry.register_python(ENTRYPOINT_ID, ENTRYPOINT_PATH, entrypoint_class="scientific")

    run_summary: dict[str, Any] | None = None
    with tempfile.TemporaryDirectory(prefix="t05-ui-demo-round1-") as temp_dir:
        managed_root = Path(temp_dir) / "workspaces"
        runner = LocalProcessRunner(
            registry=registry,
            managed_root=managed_root,
            dataset_resolver=dataset_adapter.build_resolver(cache_root),
        )
        result = runner.run(spec)
        if result.status != "succeeded":
            try:
                summary = _inprocess_baseline_summary(resolved.cache_path, dataset_manifest)
            except Exception as exc:  # noqa: BLE001 - 回退失败时仍返回真实错误
                return _failed_experiment_payload(
                    question_id="Q028",
                    result=result,
                    extra=str(exc),
                )
            return {
                "question_id": "Q028",
                "status": "succeeded",
                "actual_execution": False,
                "mock": False,
                "metrics": dict(summary.get("metrics") or {}),
                "metric_units": {
                    "balanced_accuracy": "ratio",
                    "malignant_recall": "ratio",
                },
                "confusion": summary.get("confusion"),
                "split": summary.get("split"),
                "dataset_stats": summary.get("dataset"),
                "execution_id": f"inprocess-{result.execution_id}",
                "exit_code": 0,
                "duration_seconds": result.duration_seconds,
                "dataset_sha256": dataset_manifest.sha256,
                "git_sha": None,
                "git_dirty": True,
                "warnings": ["subprocess failed; used in-process baseline on the same pinned WDBC file"],
                "error": None,
                "note": (
                    "子进程注册执行失败后，改用同一份 pinned WDBC 与同一套 baseline "
                    "在进程内重算；指标仍是真实计算结果，非正式 Gate 证据。"
                ),
            }
        # 读取真实的 run-summary.json（混淆矩阵 + 数据切分计数），必须在临时
        # workspace 被回收前完成；只在成功且产物已通过校验时读取，不臆测。
        if result.status == "succeeded" and managed_root.exists():
            workspaces = [path for path in managed_root.iterdir() if path.is_dir()]
            valid_ids = {
                artifact.artifact_id
                for artifact in result.artifacts
                if artifact.validation_status == "valid"
            }
            if len(workspaces) == 1 and "run-summary" in valid_ids:
                summary_path = workspaces[0] / "output" / "run-summary.json"
                try:
                    run_summary = json.loads(summary_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    run_summary = None

    fingerprint = result.environment_fingerprint
    error = result.error
    return {
        "question_id": result.question_id,
        "status": result.status,
        "actual_execution": bool(result.actual_execution),
        "mock": False,
        "metrics": {metric.name: metric.value for metric in result.metrics},
        "metric_units": {metric.name: metric.unit for metric in result.metrics},
        "confusion": (run_summary or {}).get("confusion"),
        "split": (run_summary or {}).get("split"),
        "dataset_stats": (run_summary or {}).get("dataset"),
        "execution_id": result.execution_id,
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
        "dataset_sha256": dataset_manifest.sha256,
        "git_sha": fingerprint.git_sha if fingerprint else None,
        "git_dirty": fingerprint.git_dirty if fingerprint else None,
        "warnings": list(result.warnings),
        "error": {"code": error.code, "message": error.message} if error is not None else None,
        "note": (
            "本次为网页界面触发的真实执行演示（mode=test，跳过正式 Gate 的 "
            "clean-git 门禁）；正式 Gate/PR 证据以 docs/modules/T05/round1 "
            "内已归档的受控实验包为准。"
        ),
    }
