"""Qwen 视觉图表结构化输出 schema 与解析（无编造数值）。"""

from __future__ import annotations

import json
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


def parse_vision_chart_json(
    raw: str,
    *,
    source_path: str,
    source_type: str,
    page: int,
    file_sha256: str,
    default_bbox: dict[str, float] | None = None,
) -> MultimodalArtifact:
    """
    Parse model JSON into MultimodalArtifact. Empty/invalid → fail-closed.
    """
    text = (raw or "").strip()
    if not text:
        raise ExtractionError("empty vision response")
    # Strip optional markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"vision response is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExtractionError("vision JSON root must be object")

    legend = payload.get("legend")
    if not isinstance(legend, list) or not legend:
        raise ExtractionError("vision chart missing legend")
    if any(not isinstance(x, str) or not x.strip() for x in legend):
        raise ExtractionError("legend entries must be non-empty strings")

    axes_raw = payload.get("axes")
    if not isinstance(axes_raw, list) or len(axes_raw) < 2:
        raise ExtractionError("vision chart requires x and y axes")
    axes: list[AxisSpec] = []
    for item in axes_raw:
        if not isinstance(item, dict):
            raise ExtractionError("axis entry must be object")
        unit = item.get("unit")
        if unit is None or str(unit).strip() == "":
            raise ExtractionError("axis unit unknown")
        axis = AxisSpec.model_validate(item)
        if axis.min_value is not None and axis.max_value is not None:
            if axis.max_value < axis.min_value:
                raise ExtractionError(f"axis {axis.name!r} inverted")
        axes.append(axis)
    names = {a.name for a in axes}
    if "x" not in names or "y" not in names:
        raise ExtractionError("axes must include x and y")

    series = payload.get("series")
    if not isinstance(series, list) or not series:
        raise ExtractionError("vision chart missing series")
    rows: list[list[str]] = []
    for s in series:
        if not isinstance(s, dict):
            raise ExtractionError("series entry must be object")
        name = s.get("name")
        if name not in legend:
            raise ExtractionError(f"series {name!r} not in legend")
        points = s.get("points")
        if not isinstance(points, list) or not points:
            raise ExtractionError(f"series {name!r} has no points")
        for p in points:
            if not isinstance(p, dict) or "x" not in p or "y" not in p:
                raise ExtractionError("points require x and y")
            try:
                x_v = float(p["x"])
                y_v = float(p["y"])
            except (TypeError, ValueError) as exc:
                raise ExtractionError("non-numeric point") from exc
            x_axis = next(a for a in axes if a.name == "x")
            y_axis = next(a for a in axes if a.name == "y")
            if x_axis.min_value is not None and x_v < x_axis.min_value:
                raise ExtractionError("x out of axis range")
            if x_axis.max_value is not None and x_v > x_axis.max_value:
                raise ExtractionError("x out of axis range")
            if y_axis.min_value is not None and y_v < y_axis.min_value:
                raise ExtractionError("y out of axis range")
            if y_axis.max_value is not None and y_v > y_axis.max_value:
                raise ExtractionError("y out of axis range")
            rows.append([str(name), str(p["x"]), str(p["y"])])

    try:
        confidence = float(payload.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise ExtractionError("confidence missing or invalid") from exc
    if confidence < 0.0 or confidence > 1.0:
        raise ExtractionError("confidence out of range")

    bbox_raw = payload.get("bbox") or default_bbox
    if not isinstance(bbox_raw, dict):
        raise ExtractionError("bbox missing")
    bbox = BoundingBox.model_validate(bbox_raw)
    if bbox.x1 <= bbox.x0 or bbox.y1 <= bbox.y0:
        raise ExtractionError("illegal bbox")

    if confidence < _CONFIDENCE_REVIEW:
        status = "failed"
    elif confidence < _CONFIDENCE_PASS:
        status = "needs_review"
    else:
        status = "passed"

    x_unit = next(a.unit for a in axes if a.name == "x")
    y_unit = next(a.unit for a in axes if a.name == "y")
    artifact_id = str(payload.get("artifact_id") or f"vision-chart-{file_sha256[:12]}")
    return MultimodalArtifact(
        artifact_id=artifact_id,
        modality="chart",
        provenance=Provenance(
            source_path=f"{source_path}#sha256={file_sha256}",
            source_type=source_type,  # type: ignore[arg-type]
            page=page,
            bbox=bbox,
        ),
        units=[str(x_unit), str(y_unit)],
        column_units=[
            ColumnUnitBinding(column="x", unit=str(x_unit)),
            ColumnUnitBinding(column="y", unit=str(y_unit)),
        ],
        axes=axes,
        legend=[str(x) for x in legend],
        data=TableData(headers=["series", "x", "y"], rows=rows),
        confidence=confidence,
        validation_status=status,  # type: ignore[arg-type]
    )


def mock_vision_chart_response(
    *,
    legend: list[str],
    axes: list[dict[str, Any]],
    series: list[dict[str, Any]],
    confidence: float = 0.88,
    bbox: dict[str, float] | None = None,
) -> str:
    """Deterministic mock JSON for offline tests (not actual)."""
    return json.dumps(
        {
            "legend": legend,
            "axes": axes,
            "series": series,
            "confidence": confidence,
            "bbox": bbox
            or {"x0": 10.0, "y0": 10.0, "x1": 400.0, "y1": 300.0},
        },
        ensure_ascii=False,
    )
