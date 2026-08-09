"""
Evaluate T06 extractors against a provenance-locked Zenodo gold package (PR #29).

Does NOT copy gold bytes into the Wave B branch. Caller passes an external package root
(e.g. a checkout of t06/real-gold-provenance).

Usage:
  python -X utf8 -m app.multimodal.eval_actual_gold --gold-root <path> --package-head <sha>
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from app.multimodal.adapters import ChartAdapter, QwenVisionAdapter, TableAdapter
from app.multimodal.errors import ExtractionError
from app.multimodal.metrics_relative import relative_or_absolute_error

ROOT = Path(__file__).resolve().parents[2]


def _load_labels(gold_root: Path) -> list[dict[str, Any]]:
    path = gold_root / "gold_labels.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _table_cell_accuracy(
    artifact_rows: list[list[str]],
    labels: list[dict[str, Any]],
) -> dict[str, Any]:
    total = 0
    correct = 0
    misses: list[dict[str, Any]] = []
    for lab in labels:
        r = int(lab["table_row"])
        c = int(lab["table_column"])
        expected = str(lab["raw_text_value"])
        total += 1
        try:
            got = artifact_rows[r][c]
        except (IndexError, TypeError):
            got = None
        if got == expected:
            correct += 1
        else:
            misses.append(
                {
                    "record_id": lab.get("record_id"),
                    "row": r,
                    "col": c,
                    "expected": expected,
                    "predicted": got,
                }
            )
    acc = correct / total if total else 0.0
    return {
        "cell_accuracy": acc,
        "correct": correct,
        "total": total,
        "meets_threshold": acc >= 0.95,
        "misses": misses[:20],
        "miss_count": len(misses),
    }


def _chart_series_from_labels(labels: list[dict[str, Any]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for lab in labels:
        exp = lab.get("expected_structured_output") or {}
        series = str(lab.get("legend_series") or exp.get("series_id") or "series")
        x = exp.get("x")
        y = exp.get("y")
        if x is None or y is None:
            continue
        rows.append([series, str(x), str(y)])
    return rows


def evaluate_actual_gold(
    gold_root: Path,
    *,
    package_head: str,
    allow_vision_actual: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    gold_root = gold_root.resolve()
    labels = _load_labels(gold_root)
    table_labels = [l for l in labels if l.get("modality") == "table"]
    chart_labels = [l for l in labels if l.get("modality") == "chart"]
    by_source: dict[str, list[dict[str, Any]]] = {}
    for lab in table_labels:
        by_source.setdefault(str(lab["source_file"]), []).append(lab)

    table_ad = TableAdapter()
    table_cases: list[dict[str, Any]] = []
    for rel, labs in sorted(by_source.items()):
        src = gold_root / rel
        t0 = time.perf_counter()
        try:
            art = table_ad.process(str(src))
            metrics = _table_cell_accuracy(art.data.rows, labs)
            table_cases.append(
                {
                    "source_file": rel.replace("\\", "/"),
                    "modality": "table",
                    "ok": bool(metrics["meets_threshold"]),
                    "artifact_id": art.artifact_id,
                    "validation_status": art.validation_status,
                    "confidence": art.confidence,
                    "units": list(art.units),
                    "sha_in_path": "#sha256=" in art.provenance.source_path,
                    "duration_ms": (time.perf_counter() - t0) * 1000.0,
                    **metrics,
                }
            )
        except Exception as exc:  # noqa: BLE001
            table_cases.append(
                {
                    "source_file": rel.replace("\\", "/"),
                    "modality": "table",
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                    "duration_ms": (time.perf_counter() - t0) * 1000.0,
                    "needs_human_review": True,
                }
            )

    # Chart: real PNG requires vision. Without credentials/auth → fail-closed honestly.
    chart_png = gold_root / "raw" / "Picture1.png"
    chart_case: dict[str, Any] = {
        "source_file": "raw/Picture1.png",
        "modality": "chart",
        "gold_point_count": len(chart_labels),
    }
    t0 = time.perf_counter()
    vision = QwenVisionAdapter()
    try:
        if not chart_png.is_file():
            raise ExtractionError("chart PNG missing from gold package")
        art = vision.process(
            str(chart_png),
            allow_actual=allow_vision_actual,
        )
        # If denied path fell through incorrectly for raster, process would raise.
        gold_rows = _chart_series_from_labels(chart_labels)
        pred_rows = art.data.rows
        # Align by series+x when possible
        gold_map = {(r[0], float(r[1])): float(r[2]) for r in gold_rows}
        point_results = []
        for pr in pred_rows:
            key = (pr[0], float(pr[1]))
            if key not in gold_map:
                point_results.append(
                    {
                        "series": pr[0],
                        "x": pr[1],
                        "predicted": float(pr[2]),
                        "gold": None,
                        "pass_threshold": False,
                        "needs_human_review": True,
                        "reason": "no_matching_gold_point",
                    }
                )
                continue
            err = relative_or_absolute_error(
                float(pr[2]),
                gold_map[key],
                relative_threshold=0.05,
                zero_abs_tol=0.0,
            )
            point_results.append(
                {
                    "series": pr[0],
                    "x": pr[1],
                    "predicted": float(pr[2]),
                    "gold": gold_map[key],
                    "relative_error": err.relative_error,
                    "absolute_error": err.absolute_error,
                    "pass_threshold": err.pass_threshold,
                    "needs_human_review": err.needs_human_review,
                    "reason": err.reason,
                }
            )
        pass_n = sum(1 for p in point_results if p["pass_threshold"])
        chart_case.update(
            {
                "ok": bool(point_results) and pass_n == len(point_results),
                "artifact_id": art.artifact_id,
                "validation_status": art.validation_status,
                "pass_count": pass_n,
                "point_count": len(point_results),
                "pass_rate": (pass_n / len(point_results)) if point_results else 0.0,
                "points": point_results[:30],
                "vision_audit_status": getattr(vision.last_audit, "status", None),
                "actual_external_call": getattr(
                    vision.last_audit, "actual_external_call", False
                ),
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
            }
        )
    except Exception as exc:  # noqa: BLE001
        # Expected without paid vision: raster requires successful VL parse.
        chart_case.update(
            {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc)[:400],
                "needs_human_review": True,
                "vision_blocked": True,
                "vision_audit_status": getattr(
                    getattr(vision, "last_audit", None), "status", None
                ),
                "actual_external_call": False,
                "duration_ms": (time.perf_counter() - t0) * 1000.0,
                "note": (
                    "Chart PNG requires Qwen VL; without credentials/authorization "
                    "actual chart digitization remains blocked (not fabricated)."
                ),
            }
        )

    table_ok = all(c.get("ok") for c in table_cases) and bool(table_cases)
    return {
        "schema_version": "1.0",
        "evaluation_kind": "actual_zenodo_gold_external_package",
        "ACTUAL_GOLD_IN_INTEGRATION": "NO",
        "gold_package_root": str(gold_root).replace("\\", "/"),
        "gold_package_head_sha": package_head,
        "gold_set_id": "zenodo_fish_spoilage_impedance",
        "doi": "10.5281/zenodo.13378442",
        "thresholds": {
            "cell_accuracy_min": 0.95,
            "chart_relative_error_max": 0.05,
            "zero_abs_tol": 0.0,
            "zero_abs_tol_source": "domain_mapping.chart_error_policy",
        },
        "reproduction_command": (
            "python -X utf8 -m app.multimodal.eval_actual_gold "
            f"--gold-root <path-to-package> --package-head {package_head}"
        ),
        "table_cases": table_cases,
        "chart_case": chart_case,
        "overall": {
            "table_files_ok": sum(1 for c in table_cases if c.get("ok")),
            "table_files_total": len(table_cases),
            "table_meets_threshold": table_ok,
            "chart_meets_threshold": bool(chart_case.get("ok")),
            "meets_full_wave_b_gold_bar": table_ok and bool(chart_case.get("ok")),
        },
        "duration_ms_total": (time.perf_counter() - started) * 1000.0,
        "known_limits": [
            "Gold package not yet in integration (PR #29 unmerged)",
            "Chart PNG evaluation requires authorized Qwen VL credentials",
            "No tokens/cost invented when vision is not called",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-root", required=True)
    parser.add_argument("--package-head", required=True)
    parser.add_argument("--allow-vision-actual", action="store_true")
    parser.add_argument(
        "--out",
        default=str(ROOT / "docs" / "modules" / "T06" / "wave_b" / "actual_gold_metrics.json"),
    )
    args = parser.parse_args()
    report = evaluate_actual_gold(
        Path(args.gold_root),
        package_head=args.package_head,
        allow_vision_actual=args.allow_vision_actual,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(out),
                "overall": report["overall"],
                "ACTUAL_GOLD_IN_INTEGRATION": report["ACTUAL_GOLD_IN_INTEGRATION"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
