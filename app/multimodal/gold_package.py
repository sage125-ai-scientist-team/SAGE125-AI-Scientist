"""Load and score T06 provenance-locked real gold packages."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

from app.contracts.multimodal import (
    AxisSpec,
    BoundingBox,
    ColumnUnitBinding,
    MultimodalArtifact,
    Provenance,
    TableData,
)

DEFAULT_GOLD_ROOT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "modules"
    / "T06"
    / "gold"
    / "zenodo_fish_spoilage_impedance"
    / "v1.0.0"
)

CHART_ERROR_POLICY_VERSION = "t06-chart-error-v1"
NONZERO_RELATIVE_TOLERANCE = 0.05


def relative_error(predicted: float, gold: float) -> float:
    """Return abs(pred-gold)/abs(gold). Undefined for gold == 0."""
    if gold == 0:
        raise ValueError("relative_error is undefined for gold == 0")
    return abs(predicted - gold) / abs(gold)


def chart_point_within_tolerance(
    predicted: float,
    gold: float,
    *,
    relative_tolerance: float = NONZERO_RELATIVE_TOLERANCE,
    absolute_tolerance: float | None = None,
) -> bool:
    """Apply T06 chart error policy v1 (EPS_USED=NO)."""
    if math.isnan(predicted) or math.isnan(gold):
        raise ValueError("NaN is not allowed in chart metric comparison")
    if math.isinf(predicted) or math.isinf(gold):
        raise ValueError("Infinity is not allowed in chart metric comparison")
    if relative_tolerance < 0:
        raise ValueError("relative_tolerance must be non-negative")
    if gold != 0:
        return relative_error(predicted, gold) <= relative_tolerance
    if absolute_tolerance is None:
        raise ValueError("absolute_tolerance is required when gold == 0")
    if math.isnan(absolute_tolerance) or math.isinf(absolute_tolerance):
        raise ValueError("absolute_tolerance must be finite")
    if absolute_tolerance < 0:
        raise ValueError("absolute_tolerance must be non-negative")
    return abs(predicted - gold) <= absolute_tolerance


def load_manifest(package_dir: Path | None = None) -> dict[str, Any]:
    root = package_dir or DEFAULT_GOLD_ROOT
    return json.loads((root / "manifest.json").read_bytes().decode("utf-8"))


def iter_gold_labels(package_dir: Path | None = None) -> Iterable[dict[str, Any]]:
    root = package_dir or DEFAULT_GOLD_ROOT
    for line in (root / "gold_labels.jsonl").read_bytes().splitlines():
        if line.strip():
            yield json.loads(line.decode("utf-8"))


def load_resistance_table_artifact(package_dir: Path | None = None) -> MultimodalArtifact:
    """Build a MultimodalArtifact from the real gold resistance CSV."""
    root = package_dir or DEFAULT_GOLD_ROOT
    manifest = load_manifest(root)
    if manifest.get("is_synthetic") or manifest.get("is_provisional") or manifest.get(
        "is_fixture"
    ):
        raise ValueError("refusing to load package marked synthetic/provisional/fixture")

    csv_path = root / "raw" / "fishtrial_resistance.csv"
    text = csv_path.read_bytes().decode("utf-8")
    rows_in = list(csv.reader(text.splitlines()))
    headers = [c.strip() for c in rows_in[0]]
    body = [[c.strip() for c in row] for row in rows_in[1:] if any(c.strip() for c in row)]

    return MultimodalArtifact(
        artifact_id="T06-GOLD-FISH-IMPEDANCE-001-table-resistance",
        modality="table",
        provenance=Provenance(
            source_path=str(csv_path.as_posix()),
            source_type="csv",
            page=1,
            bbox=None,
        ),
        units=["s", "ohm"],
        column_units=[
            ColumnUnitBinding(column=headers[0], unit="s"),
            ColumnUnitBinding(column=headers[1], unit="ohm"),
        ],
        axes=None,
        legend=[],
        data=TableData(headers=headers, rows=body),
        confidence=1.0,
        validation_status="passed",
    )


def load_chart_artifact(package_dir: Path | None = None) -> MultimodalArtifact:
    """Build a chart MultimodalArtifact bound to Picture1.png + resistance series."""
    root = package_dir or DEFAULT_GOLD_ROOT
    manifest = load_manifest(root)
    if manifest.get("is_synthetic") or manifest.get("is_provisional") or manifest.get(
        "is_fixture"
    ):
        raise ValueError("refusing to load package marked synthetic/provisional/fixture")

    png_path = root / "raw" / "Picture1.png"
    csv_path = root / "raw" / "fishtrial_resistance.csv"
    text = csv_path.read_bytes().decode("utf-8")
    rows_in = list(csv.reader(text.splitlines()))
    headers = [c.strip() for c in rows_in[0]]
    body = [[c.strip() for c in row] for row in rows_in[1:] if any(c.strip() for c in row)]

    return MultimodalArtifact(
        artifact_id="T06-GOLD-FISH-IMPEDANCE-001-chart-picture1",
        modality="chart",
        provenance=Provenance(
            source_path=str(png_path.as_posix()),
            source_type="user_upload",
            page=1,
            bbox=BoundingBox(x0=0.0, y0=0.0, x1=370.0, y1=592.0),
        ),
        units=["s", "ohm"],
        column_units=[
            ColumnUnitBinding(column=headers[0], unit="s"),
            ColumnUnitBinding(column=headers[1], unit="ohm"),
        ],
        axes=[
            AxisSpec(name="x", label=headers[0], unit="s"),
            AxisSpec(name="y", label=headers[1], unit="ohm"),
        ],
        legend=["resistance", "capacitance", "impedance_real", "impedance_imaginary"],
        data=TableData(headers=headers, rows=body),
        confidence=1.0,
        validation_status="passed",
    )
