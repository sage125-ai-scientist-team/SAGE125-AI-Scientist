"""
T06 Wave B：图表结构化提取（确定性；缺图例/错误轴 fail-closed）。

不根据像素视觉猜测数值；仅接受显式 chart 包 JSON。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.contracts.multimodal import (
    AxisSpec,
    BoundingBox,
    ColumnUnitBinding,
    MultimodalArtifact,
    Provenance,
    TableData,
)
from app.multimodal.errors import ExtractionError

_CONFIDENCE_PASS = 0.80
_CONFIDENCE_REVIEW = 0.50


def _require_bbox(raw: Any) -> BoundingBox:
    if not isinstance(raw, dict):
        raise ExtractionError("chart packet requires bbox object")
    try:
        box = BoundingBox.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"illegal bbox: {exc}") from exc
    if box.x1 <= box.x0 or box.y1 <= box.y0:
        raise ExtractionError("illegal bbox: degenerate rectangle")
    return box


def load_chart_packet(source_path: str) -> dict[str, Any]:
    path = Path(source_path)
    if not path.is_file():
        raise ExtractionError(f"chart source not found: {source_path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"chart packet is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExtractionError("chart packet root must be an object")
    return payload


def extract_chart_artifact(source_path: str) -> MultimodalArtifact:
    packet = load_chart_packet(source_path)
    required = ("page", "bbox", "axes", "legend", "series", "confidence")
    missing = [k for k in required if k not in packet]
    if missing:
        raise ExtractionError(f"chart packet missing fields: {missing}")

    page = int(packet["page"])
    if page < 1:
        raise ExtractionError("page must be >= 1")
    bbox = _require_bbox(packet["bbox"])

    legend = packet["legend"]
    if not isinstance(legend, list) or not legend:
        raise ExtractionError("missing legend: refuse to invent series labels")
    if any(not isinstance(x, str) or not x.strip() for x in legend):
        raise ExtractionError("legend entries must be non-empty strings")

    axes_raw = packet["axes"]
    if not isinstance(axes_raw, list) or len(axes_raw) < 2:
        raise ExtractionError("chart requires at least x and y axes")
    axes: list[AxisSpec] = []
    for item in axes_raw:
        if not isinstance(item, dict):
            raise ExtractionError("axis entry must be object")
        unit = item.get("unit")
        if unit is None or str(unit).strip() == "":
            raise ExtractionError("axis unit unknown: refuse silent values")
        try:
            axis = AxisSpec.model_validate(item)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"invalid axis: {exc}") from exc
        if axis.min_value is not None and axis.max_value is not None:
            if axis.max_value < axis.min_value:
                raise ExtractionError(f"axis {axis.name!r} has inverted range")
        axes.append(axis)

    axis_names = {a.name for a in axes}
    if "x" not in axis_names or "y" not in axis_names:
        raise ExtractionError("axes must include named x and y")

    series = packet["series"]
    if not isinstance(series, list) or not series:
        raise ExtractionError("series values missing")

    headers = ["series", "x", "y"]
    rows: list[list[str]] = []
    for s in series:
        if not isinstance(s, dict):
            raise ExtractionError("series entry must be object")
        name = s.get("name")
        if name not in legend:
            raise ExtractionError(
                f"series name {name!r} not in legend {legend!r}"
            )
        points = s.get("points")
        if not isinstance(points, list) or not points:
            raise ExtractionError(f"series {name!r} has no points")
        for p in points:
            if not isinstance(p, dict) or "x" not in p or "y" not in p:
                raise ExtractionError("points require explicit x and y")
            try:
                x_v = float(p["x"])
                y_v = float(p["y"])
            except (TypeError, ValueError) as exc:
                raise ExtractionError(f"non-numeric point in series {name!r}") from exc
            x_axis = next(a for a in axes if a.name == "x")
            y_axis = next(a for a in axes if a.name == "y")
            if x_axis.min_value is not None and x_v < x_axis.min_value:
                raise ExtractionError("x value outside declared axis range")
            if x_axis.max_value is not None and x_v > x_axis.max_value:
                raise ExtractionError("x value outside declared axis range")
            if y_axis.min_value is not None and y_v < y_axis.min_value:
                raise ExtractionError("y value outside declared axis range")
            if y_axis.max_value is not None and y_v > y_axis.max_value:
                raise ExtractionError("y value outside declared axis range")
            rows.append([str(name), str(p["x"]), str(p["y"])])

    confidence = float(packet["confidence"])
    if confidence < 0.0 or confidence > 1.0:
        raise ExtractionError("confidence must be in [0, 1]")
    if confidence < _CONFIDENCE_REVIEW:
        status = "failed"
    elif confidence < _CONFIDENCE_PASS:
        status = "needs_review"
    else:
        status = "passed"

    source_type = packet.get("source_type", "pdf")
    if source_type not in ("pdf", "synthetic_fixture", "real_fixture", "csv", "user_upload"):
        raise ExtractionError(f"unsupported source_type: {source_type!r}")

    digest = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()[:12]
    artifact_id = str(packet.get("artifact_id") or f"chart-{digest}")
    x_unit = next(a.unit for a in axes if a.name == "x") or ""
    y_unit = next(a.unit for a in axes if a.name == "y") or ""
    column_units = [
        ColumnUnitBinding(column="x", unit=str(x_unit)),
        ColumnUnitBinding(column="y", unit=str(y_unit)),
    ]
    return MultimodalArtifact(
        artifact_id=artifact_id,
        modality="chart",
        provenance=Provenance(
            source_path=source_path,
            source_type=source_type,  # type: ignore[arg-type]
            page=page,
            bbox=bbox,
        ),
        units=[str(x_unit), str(y_unit)],
        column_units=column_units,
        axes=axes,
        legend=[str(x) for x in legend],
        data=TableData(headers=headers, rows=rows),
        confidence=confidence,
        validation_status=status,  # type: ignore[arg-type]
    )
