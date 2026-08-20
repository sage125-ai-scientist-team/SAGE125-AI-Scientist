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

#: Pinned dataset copy preserved from an earlier controlled fetch. Reused here
#: so the UI-triggered demo run stays fully offline (no network access).
OFFLINE_CACHE_ROOT = (
    REPOSITORY_ROOT / "tmp" / "preserved_from_d_root" / "T05_WDBC" / "formal-cache"
)

#: Distinct spec_id so this demo path is never confused with the formal
#: ``wdbc-round1-baseline-v1`` spec used for official Gate/PR evidence.
_DEMO_SPEC_ID = "wdbc-round1-ui-demo-v1"


class Q028DemoRunError(RuntimeError):
    """Raised when the demo run cannot even start (e.g. dataset unavailable)."""


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
    try:
        dataset_adapter = DatasetAdapter(get_default_dataset_registry())
        resolved = dataset_adapter.fetch(
            WDBC_DATASET_ID, cache_root=OFFLINE_CACHE_ROOT, offline=True
        )
    except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the caller
        raise Q028DemoRunError(f"WDBC 数据集离线缓存不可用：{exc}") from exc

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
            dataset_resolver=dataset_adapter.build_resolver(OFFLINE_CACHE_ROOT),
        )
        result = runner.run(spec)
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
