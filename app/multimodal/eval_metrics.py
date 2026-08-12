"""
T06 Wave B：评测脚本。

- synthetic_fixture_offline：使用仓库内合成夹具
- chart 使用 relative_error<=5%（零值用显式绝对容限）
- actual_gold：PR #29 未合入 integration 时保持 BLOCKED
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.multimodal.adapters import ChartAdapter, TableAdapter, TimeseriesAdapter
from app.multimodal.errors import ExtractionError
from app.multimodal.metrics_relative import evaluate_chart_series

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "multimodal" / "fixtures" / "wave_b"
GOLD_MANIFEST = FIXTURES / "GOLD_MANIFEST.json"


@dataclass
class CaseResult:
    case_id: str
    modality: str
    ok: bool
    cell_accuracy: float | None
    chart_pass_rate: float | None
    chart_meets_5pct: bool | None
    error_type: str | None
    duration_ms: float
    artifact_id: str | None
    needs_human_review: bool


def _cell_accuracy(pred_rows: list[list[str]], gold_rows: list[list[str]]) -> float:
    if not gold_rows:
        return 1.0
    total = 0
    correct = 0
    for pr, gr in zip(pred_rows, gold_rows, strict=False):
        n = max(len(pr), len(gr))
        for i in range(n):
            total += 1
            pv = pr[i] if i < len(pr) else None
            gv = gr[i] if i < len(gr) else None
            if pv == gv:
                correct += 1
    if len(gold_rows) > len(pred_rows):
        for gr in gold_rows[len(pred_rows) :]:
            total += len(gr)
    return correct / total if total else 0.0


def run_gold_evaluation() -> dict[str, Any]:
    started = time.perf_counter()
    if not GOLD_MANIFEST.is_file():
        return {
            "schema_version": "1.0",
            "evaluation_kind": "blocked",
            "actual_zenodo_gold": "BLOCKED_PR29_NOT_IN_BASE",
            "error": f"missing {GOLD_MANIFEST}",
        }
    manifest = json.loads(GOLD_MANIFEST.read_text(encoding="utf-8"))
    cases = manifest.get("cases") or []
    results: list[CaseResult] = []
    table_ad, chart_ad, ts_ad = TableAdapter(), ChartAdapter(), TimeseriesAdapter()
    chart_details: dict[str, Any] = {}

    for case in cases:
        case_id = case["case_id"]
        modality = case["modality"]
        source = str(FIXTURES / case["source"])
        gold = json.loads((FIXTURES / case["gold"]).read_text(encoding="utf-8"))
        t0 = time.perf_counter()
        try:
            if modality == "table":
                art = table_ad.process(source)
                acc = _cell_accuracy(art.data.rows, gold["data"]["rows"])
                ok = acc >= float(manifest.get("thresholds", {}).get("cell_accuracy_min", 0.95))
                results.append(
                    CaseResult(
                        case_id=case_id,
                        modality=modality,
                        ok=ok,
                        cell_accuracy=acc,
                        chart_pass_rate=None,
                        chart_meets_5pct=None,
                        error_type=None,
                        duration_ms=(time.perf_counter() - t0) * 1000.0,
                        artifact_id=art.artifact_id,
                        needs_human_review=not ok,
                    )
                )
            elif modality == "chart":
                art = chart_ad.process(source)
                detail = evaluate_chart_series(
                    art.data.rows,
                    gold["data"]["rows"],
                    relative_threshold=0.05,
                    zero_abs_tol=float(
                        manifest.get("thresholds", {}).get("zero_abs_tol", 1e-6)
                    ),
                )
                chart_details[case_id] = detail
                results.append(
                    CaseResult(
                        case_id=case_id,
                        modality=modality,
                        ok=bool(detail["meets_threshold"]),
                        cell_accuracy=None,
                        chart_pass_rate=float(detail["pass_rate"]),
                        chart_meets_5pct=bool(detail["meets_threshold"]),
                        error_type=None,
                        duration_ms=(time.perf_counter() - t0) * 1000.0,
                        artifact_id=art.artifact_id,
                        needs_human_review=bool(detail["needs_human_review"]),
                    )
                )
            elif modality == "timeseries":
                art = ts_ad.process(source)
                acc = _cell_accuracy(art.data.rows, gold["data"]["rows"])
                ok = acc >= float(manifest.get("thresholds", {}).get("cell_accuracy_min", 0.95))
                results.append(
                    CaseResult(
                        case_id=case_id,
                        modality=modality,
                        ok=ok,
                        cell_accuracy=acc,
                        chart_pass_rate=None,
                        chart_meets_5pct=None,
                        error_type=None,
                        duration_ms=(time.perf_counter() - t0) * 1000.0,
                        artifact_id=art.artifact_id,
                        needs_human_review=not ok,
                    )
                )
            else:
                raise ExtractionError(f"unknown modality {modality}")
        except Exception as exc:  # noqa: BLE001
            results.append(
                CaseResult(
                    case_id=case_id,
                    modality=modality,
                    ok=False,
                    cell_accuracy=None,
                    chart_pass_rate=None,
                    chart_meets_5pct=None,
                    error_type=type(exc).__name__,
                    duration_ms=(time.perf_counter() - t0) * 1000.0,
                    artifact_id=None,
                    needs_human_review=True,
                )
            )

    ok_cases = [r for r in results if r.ok]
    return {
        "schema_version": "1.0",
        "evaluation_kind": "synthetic_fixture_offline",
        "actual_zenodo_gold": "BLOCKED_PR29_PROVENANCE_DEPENDENCY_NOT_IN_BASE",
        "actual_gold_evaluation": "NOT_RUN_WAIT_PR29_MERGE",
        "dataset_manifest": str(GOLD_MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "dataset_kind": "synthetic_fixture",
        "sample_size": len(cases),
        "reproduction_command": "python -X utf8 -m app.multimodal.eval_metrics",
        "thresholds": {
            "cell_accuracy_min": float(
                manifest.get("thresholds", {}).get("cell_accuracy_min", 0.95)
            ),
            "chart_relative_error_max": 0.05,
            "zero_abs_tol": float(manifest.get("thresholds", {}).get("zero_abs_tol", 1e-6)),
            "zero_abs_tol_declared": True,
        },
        "overall": {
            "cases_ok": len(ok_cases),
            "cases_failed": len(results) - len(ok_cases),
            "meets_threshold": len(ok_cases) == len(cases) and len(cases) > 0,
        },
        "chart_point_details": chart_details,
        "cases": [asdict(r) for r in results],
        "duration_ms_total": (time.perf_counter() - started) * 1000.0,
        "resources_cost": "NOT_APPLICABLE_NO_PAID_CALLS_PHASE1",
        "known_limits": [
            "Zenodo real gold blocked until PR #29 merges into integration",
            "Phase-1 does not execute paid Qwen calls",
            "Chart metric is relative_error<=5% with declared zero absolute tolerance",
        ],
    }


def main() -> None:
    report = run_gold_evaluation()
    out_dir = ROOT / "docs" / "modules" / "T06" / "wave_b"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "metrics.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(out_path), "overall": report.get("overall")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
