"""
T06 Wave B：合成 gold 指标计算（明确 synthetic_fixture；非 Zenodo actual）。

真实 Zenodo gold 仅存在于未合并 PR #29，本脚本不得复制 #29 资产。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.multimodal.adapters import ChartAdapter, TableAdapter, TimeseriesAdapter
from app.multimodal.errors import ExtractionError

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "multimodal" / "fixtures" / "wave_b"
GOLD_MANIFEST = FIXTURES / "GOLD_MANIFEST.json"


@dataclass
class CaseResult:
    case_id: str
    modality: str
    ok: bool
    cell_accuracy: float | None
    numeric_mae: float | None
    error_type: str | None
    duration_ms: float
    artifact_id: str | None


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
    # unmatched gold rows
    if len(gold_rows) > len(pred_rows):
        for gr in gold_rows[len(pred_rows) :]:
            total += len(gr)
    return correct / total if total else 0.0


def _numeric_mae(pred_rows: list[list[str]], gold_rows: list[list[str]]) -> float | None:
    errs: list[float] = []
    for pr, gr in zip(pred_rows, gold_rows, strict=False):
        for pv, gv in zip(pr, gr, strict=False):
            try:
                errs.append(abs(float(pv) - float(gv)))
            except ValueError:
                continue
    if not errs:
        return None
    return sum(errs) / len(errs)


def run_gold_evaluation() -> dict[str, Any]:
    started = time.perf_counter()
    if not GOLD_MANIFEST.is_file():
        return {
            "schema_version": "1.0",
            "evaluation_kind": "blocked",
            "actual_zenodo_gold": "BLOCKED_PR29_NOT_IN_BASE",
            "synthetic_fixture_eval": "unavailable_missing_manifest",
            "error": f"missing {GOLD_MANIFEST}",
        }
    manifest = json.loads(GOLD_MANIFEST.read_text(encoding="utf-8"))
    cases = manifest.get("cases") or []
    results: list[CaseResult] = []
    table_ad = TableAdapter()
    chart_ad = ChartAdapter()
    ts_ad = TimeseriesAdapter()

    for case in cases:
        case_id = case["case_id"]
        modality = case["modality"]
        source = str(FIXTURES / case["source"])
        gold_path = FIXTURES / case["gold"]
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        t0 = time.perf_counter()
        try:
            if modality == "table":
                art = table_ad.process(source)
            elif modality == "chart":
                art = chart_ad.process(source)
            elif modality == "timeseries":
                art = ts_ad.process(source)
            else:
                raise ExtractionError(f"unknown modality {modality}")
            pred_rows = art.data.rows
            gold_rows = gold["data"]["rows"]
            acc = _cell_accuracy(pred_rows, gold_rows)
            mae = _numeric_mae(pred_rows, gold_rows)
            results.append(
                CaseResult(
                    case_id=case_id,
                    modality=modality,
                    ok=True,
                    cell_accuracy=acc,
                    numeric_mae=mae,
                    error_type=None,
                    duration_ms=(time.perf_counter() - t0) * 1000.0,
                    artifact_id=art.artifact_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 — record failure type
            results.append(
                CaseResult(
                    case_id=case_id,
                    modality=modality,
                    ok=False,
                    cell_accuracy=None,
                    numeric_mae=None,
                    error_type=type(exc).__name__,
                    duration_ms=(time.perf_counter() - t0) * 1000.0,
                    artifact_id=None,
                )
            )

    ok_cases = [r for r in results if r.ok]
    overall_acc = (
        sum(r.cell_accuracy or 0.0 for r in ok_cases) / len(ok_cases)
        if ok_cases
        else 0.0
    )
    thresholds = manifest.get("thresholds") or {}
    cell_threshold = float(thresholds.get("cell_accuracy_min", 0.99))
    report = {
        "schema_version": "1.0",
        "evaluation_kind": "synthetic_fixture_offline",
        "actual_zenodo_gold": "BLOCKED_PR29_PROVENANCE_DEPENDENCY_NOT_IN_BASE",
        "dataset_manifest": str(GOLD_MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "dataset_kind": "synthetic_fixture",
        "sample_size": len(cases),
        "reproduction_command": (
            "python -X utf8 -m app.multimodal.eval_metrics"
        ),
        "thresholds": {"cell_accuracy_min": cell_threshold},
        "overall": {
            "cell_accuracy": overall_acc,
            "cases_ok": len(ok_cases),
            "cases_failed": len(results) - len(ok_cases),
            "meets_threshold": overall_acc >= cell_threshold and len(ok_cases) == len(cases),
        },
        "by_modality": {},
        "cases": [r.__dict__ for r in results],
        "duration_ms_total": (time.perf_counter() - started) * 1000.0,
        "resources_cost": "NOT_APPLICABLE_NO_PAID_CALLS",
        "known_limits": [
            "Zenodo real gold package lives only on PR #29 fixed Head and is not in integration base",
            "This report evaluates synthetic_fixture packets only",
            "No paid Qwen/Bailian calls were performed",
        ],
    }
    by_mod: dict[str, list[CaseResult]] = {}
    for r in results:
        by_mod.setdefault(r.modality, []).append(r)
    for mod, items in by_mod.items():
        ok = [x for x in items if x.ok and x.cell_accuracy is not None]
        report["by_modality"][mod] = {
            "n": len(items),
            "cell_accuracy": (
                sum(x.cell_accuracy or 0.0 for x in ok) / len(ok) if ok else None
            ),
            "failures": [x.case_id for x in items if not x.ok],
        }
    return report


def main() -> None:
    report = run_gold_evaluation()
    out_dir = ROOT / "docs" / "modules" / "T06" / "wave_b"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "metrics.json"
    out_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"wrote": str(out_path), "overall": report.get("overall")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
