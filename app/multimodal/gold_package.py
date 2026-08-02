"""Load and score T06 provenance-locked real gold packages."""

from __future__ import annotations

import csv
import json
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


def relative_error(predicted: float, gold: float, eps: float = 1e-12) -> float:
    """Return |pred-gold|/max(|gold|, eps). Not a constant pass."""
    return abs(predicted - gold) / max(abs(gold), eps)


def chart_point_within_tolerance(
    predicted: float,
    gold: float,
    relative_tolerance: float = 0.05,
) -> bool:
    """T06 chart DoD: relative error must be <= tolerance (default 5%)."""
    if relative_tolerance < 0:
        raise ValueError("relative_tolerance must be non-negative")
    return relative_error(predicted, gold) <= relative_tolerance


def load_manifest(package_dir: Path | None = None) -> dict[str, Any]:
    root = package_dir or DEFAULT_GOLD_ROOT
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def iter_gold_labels(package_dir: Path | None = None) -> Iterable[dict[str, Any]]:
    root = package_dir or DEFAULT_GOLD_ROOT
    for line in (root / "gold_labels.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def load_resistance_table_artifact(package_dir: Path | None = None) -> MultimodalArtifact:
    """Build a MultimodalArtifact from the real gold resistance CSV."""
    root = package_dir or DEFAULT_GOLD_ROOT
    manifest = load_manifest(root)
    if manifest.get("is_synthetic") or manifest.get("is_provisional") or manifest.get(
        "is_fixture"
    ):
        raise ValueError("refusing to load package marked synthetic/provisional/fixture")

    csv_path = root / "raw" / "fishtrial_resistance.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows_in = list(csv.reader(handle))
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
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows_in = list(csv.reader(handle))
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
