"""Build T06 Wave C showcase packs, metrics, and perf probes."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from PIL import Image

from app.multimodal.adapters import QwenVisionAdapter, TableAdapter, TimeseriesAdapter
from app.multimodal.audit import paid_vision_authorized
from app.multimodal.errors import ExtractionError
from app.multimodal.eval_actual_gold import _load_labels, _table_cell_accuracy
from app.multimodal.qwen_vision import credential_status, run_qwen_vision
from app.multimodal.read_port import (
    T06_LOW_CONFIDENCE_THRESHOLD,
    MultimodalArtifactStore,
    build_public_source,
    list_multimodal_artifacts,
    put_multimodal_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
WAVE = ROOT / "docs" / "modules" / "T06" / "wave_c"
CASE_A = WAVE / "cases" / "paper_table_chart_zenodo"
CASE_B = WAVE / "cases" / "timeseries_csv"
STORE = WAVE / "store_demo"


def main() -> None:
    for p in (CASE_A, CASE_B, STORE):
        p.mkdir(parents=True, exist_ok=True)

    gold = ROOT / "docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0"
    csv = gold / "raw" / "fishtrial_resistance.csv"
    png = gold / "raw" / "Picture1.png"
    ts_csv = ROOT / "tests/multimodal/fixtures/wave_b/timeseries/sample_clean.csv"
    ts_schema = ROOT / "tests/multimodal/fixtures/wave_b/timeseries/sample_clean.schema.json"
    ts_gold = ROOT / "tests/multimodal/fixtures/wave_b/timeseries/gold_001.json"

    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    table_art = TableAdapter().process(str(csv))
    timings["table_extract_ms"] = (time.perf_counter() - t0) * 1000.0
    labels = [
        lab
        for lab in _load_labels(gold)
        if lab.get("modality") == "table"
        and lab.get("source_file") == "raw/fishtrial_resistance.csv"
    ]
    table_metrics = _table_cell_accuracy(table_art.data.rows, labels)

    chart_case: dict = {
        "source_file": "raw/Picture1.png",
        "modality": "chart",
        "ok": False,
        "vision_blocked": True,
        "needs_human_review": True,
        "actual_external_call": False,
        "tokens": None,
        "cost": None,
    }
    t0 = time.perf_counter()
    try:
        QwenVisionAdapter().process(str(png), allow_actual=False)
        chart_case["ok"] = True
        chart_case["vision_blocked"] = False
    except ExtractionError as exc:
        chart_case["error"] = str(exc)[:300]
        chart_case["error_type"] = type(exc).__name__
    timings["chart_denied_ms"] = (time.perf_counter() - t0) * 1000.0

    thumb = CASE_A / "thumbnail_picture1.png"
    img = Image.open(png)
    img.thumbnail((320, 320))
    img.save(thumb)
    thumb_sha = hashlib.sha256(thumb.read_bytes()).hexdigest()

    store = MultimodalArtifactStore(root=STORE)
    detail = put_multimodal_artifact(
        run_id="wave-c-demo-run",
        question_id="Q-T06-C-A",
        version_id="v1",
        artifact=table_art,
        store=store,
    )
    pub = detail.public_source
    chart_labels = [lab for lab in _load_labels(gold) if lab.get("modality") == "chart"]

    case_a = {
        "case_id": "paper_table_chart_zenodo",
        "doi": "10.5281/zenodo.13378442",
        "gold_package": "docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0",
        "inputs": [
            {
                "path": "docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/raw/fishtrial_resistance.csv",
                "modality": "table",
            },
            {
                "path": "docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/raw/Picture1.png",
                "modality": "chart",
            },
        ],
        "human_gold": {
            "table_labels_count": len(labels),
            "chart_labels_count": len(chart_labels),
            "labels_file": "docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/gold_labels.jsonl",
        },
        "table_extract": {
            "artifact": table_art.model_dump(mode="json"),
            "public_source": {
                "source_id": pub.source_id,
                "source_label": pub.source_label,
                "preview_artifact_id": pub.preview_artifact_id,
                "coordinate_space": pub.coordinate_space,
                "page": pub.page,
                "bbox": None if pub.bbox is None else pub.bbox.model_dump(mode="json"),
            },
            "metrics": table_metrics,
            "duration_ms": timings["table_extract_ms"],
        },
        "chart_extract": chart_case,
        "thumbnail": {
            "path": "docs/modules/T06/wave_c/cases/paper_table_chart_zenodo/thumbnail_picture1.png",
            "sha256": thumb_sha,
            "note": "preview only; not chart digitization evidence",
        },
        "read_port_demo": {
            "run_id": "wave-c-demo-run",
            "question_id": "Q-T06-C-A",
            "version_id": "v1",
            "listed_count": len(
                list_multimodal_artifacts(
                    run_id="wave-c-demo-run",
                    question_id="Q-T06-C-A",
                    version_id="v1",
                    store=store,
                )
            ),
        },
        "reproduction_command": (
            "python -X utf8 -m app.multimodal.eval_actual_gold "
            "--gold-root docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0 "
            "--package-head 7b4a4c366f4ce25e5f05e2e948ec3938f11739ac --in-integration"
        ),
    }
    (CASE_A / "MANIFEST.json").write_text(
        json.dumps(case_a, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (CASE_A / "table_artifact.json").write_text(
        json.dumps(table_art.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (CASE_A / "chart_status.json").write_text(
        json.dumps(chart_case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (CASE_A / "detail_view.json").write_text(
        json.dumps(detail.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    t0 = time.perf_counter()
    ts_art = TimeseriesAdapter().process(str(ts_csv))
    timings["timeseries_extract_ms"] = (time.perf_counter() - t0) * 1000.0
    shutil.copy2(ts_csv, CASE_B / "input_sample_clean.csv")
    shutil.copy2(ts_schema, CASE_B / "input_sample_clean.schema.json")
    if ts_gold.is_file():
        shutil.copy2(ts_gold, CASE_B / "human_gold_001.json")
    ts_pub = build_public_source(ts_art)
    put_multimodal_artifact(
        run_id="wave-c-demo-run",
        question_id="Q-T06-C-B",
        version_id="v1",
        artifact=ts_art,
        store=store,
    )
    case_b = {
        "case_id": "timeseries_csv_wave_b_fixture",
        "inputs": [
            {
                "path": "docs/modules/T06/wave_c/cases/timeseries_csv/input_sample_clean.csv",
                "modality": "timeseries",
            },
            {
                "path": "docs/modules/T06/wave_c/cases/timeseries_csv/input_sample_clean.schema.json",
                "role": "schema",
            },
        ],
        "human_gold": "docs/modules/T06/wave_c/cases/timeseries_csv/human_gold_001.json",
        "extract": {
            "artifact": ts_art.model_dump(mode="json"),
            "public_source": {
                "source_id": ts_pub.source_id,
                "source_label": ts_pub.source_label,
                "preview_artifact_id": ts_pub.preview_artifact_id,
                "coordinate_space": ts_pub.coordinate_space,
                "page": ts_pub.page,
                "bbox": None if ts_pub.bbox is None else ts_pub.bbox.model_dump(mode="json"),
            },
            "duration_ms": timings["timeseries_extract_ms"],
        },
        "thumbnail_or_preview": {
            "preview_artifact_id": ts_art.artifact_id,
            "note": "CSV timeseries uses preview_artifact_id; no raster thumbnail",
        },
        "reproduction_command": (
            "python -X utf8 -c "
            "\"from app.multimodal.adapters import TimeseriesAdapter; "
            "a=TimeseriesAdapter().process("
            "'docs/modules/T06/wave_c/cases/timeseries_csv/input_sample_clean.csv'); "
            "print(a.validation_status, a.confidence)\""
        ),
    }
    (CASE_B / "MANIFEST.json").write_text(
        json.dumps(case_b, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (CASE_B / "timeseries_artifact.json").write_text(
        json.dumps(ts_art.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    t0 = time.perf_counter()
    _payload, audit = run_qwen_vision(str(png), allow_actual=False)
    no_vision = {
        "status": audit.status,
        "actual_external_call": audit.actual_external_call,
        "duration_ms": (time.perf_counter() - t0) * 1000.0,
        "note": "denied path must not invent chart points",
    }
    inv = ROOT / "tests/multimodal/fixtures/wave_b/invalid/chart_unknown_axis_unit.json"
    fallback = {
        "credentials": credential_status(),
        "paid_authorized": paid_vision_authorized(),
        "ACTUAL_EXTERNAL_CALLS": 0,
        "tokens": None,
        "cost": None,
        "timings_ms": timings,
        "no_vision_model": no_vision,
        "unit_conflict_fixture": str(inv.relative_to(ROOT)).replace("\\", "/")
        if inv.is_file()
        else None,
        "low_confidence_policy": {"threshold": T06_LOW_CONFIDENCE_THRESHOLD},
    }
    (WAVE / "perf_probe.json").write_text(
        json.dumps(fallback, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    metrics = {
        "schema_version": "1.0",
        "evaluation_kind": "wave_c_final",
        "ACTUAL_EXTERNAL_CALLS": 0,
        "tokens": None,
        "cost": None,
        "modalities_in_pipeline": ["table", "timeseries"],
        "chart_status": "needs_human_review_no_vl",
        "table": {
            "cell_accuracy": table_metrics["cell_accuracy"],
            "meets_threshold_0_95": table_metrics["meets_threshold"],
            "correct": table_metrics["correct"],
            "total": table_metrics["total"],
        },
        "timeseries": {
            "validation_status": ts_art.validation_status,
            "confidence": ts_art.confidence,
            "row_count": len(ts_art.data.rows),
            "entered_pipeline": True,
        },
        "chart": chart_case,
        "dod": {
            "T06-DOD-001_two_non_text_modalities": True,
            "T06-METRIC-001": True,
            "T06-DOD-002_table_ge_95": bool(table_metrics["meets_threshold"]),
            "T06-METRIC-002": bool(table_metrics["meets_threshold"]),
            "T06-METRIC-003_chart_rel_err_le_5": False,
            "T06-METRIC-003_human_review_marked": True,
            "T06-DOD-003_no_silent_pass_on_failures": True,
        },
        "timings_ms": timings,
        "reproduction_commands": [
            case_a["reproduction_command"],
            "python -X utf8 -m pytest tests/multimodal/test_wave_c_fallback.py -q",
            "python -X utf8 scripts/t06_build_wave_c_artifacts.py",
        ],
    }
    (WAVE / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": True, "table_acc": table_metrics["cell_accuracy"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
