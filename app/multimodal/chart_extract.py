"""
图表提取：

1) JSON offline_fixture / preprocessed_input packet
2) PDF 内嵌 LEGEND/AXIS/SERIES 文本指令 → 明确降级为 preprocessed_input（非真实曲线解析）
3) 真实视觉路径见 qwen_vision + vision_schema（渲染页/图片 → 结构化 JSON）
"""

from __future__ import annotations

import json
import re
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
from app.multimodal.pdf_io import extract_page_text_blocks, load_source_bytes, open_pdf

_CONFIDENCE_PASS = 0.80
_CONFIDENCE_REVIEW = 0.50
_SERIES_LINE = re.compile(
    r"^SERIES\s+(?P<name>\S+)\s+x=(?P<x>[-+0-9.eE]+)\s+y=(?P<y>[-+0-9.eE]+)\s*$"
)
_AXIS_LINE = re.compile(
    r"^AXIS\s+(?P<name>[xy])\s+unit=(?P<unit>\S+)\s+min=(?P<min>[-+0-9.eE]+)\s+max=(?P<max>[-+0-9.eE]+)\s*$"
)
_LEGEND_LINE = re.compile(r"^LEGEND\s+(?P<items>.+)$")


def _require_bbox(raw: Any) -> BoundingBox:
    if not isinstance(raw, dict):
        raise ExtractionError("chart requires bbox object")
    box = BoundingBox.model_validate(raw)
    if box.x1 <= box.x0 or box.y1 <= box.y0:
        raise ExtractionError("illegal bbox: degenerate rectangle")
    return box


def _status(confidence: float) -> str:
    if confidence < _CONFIDENCE_REVIEW:
        return "failed"
    if confidence < _CONFIDENCE_PASS:
        return "needs_review"
    return "passed"


def _finalize(
    *,
    artifact_id: str,
    source_path: str,
    source_type: str,
    page: int,
    bbox: BoundingBox,
    axes: list[AxisSpec],
    legend: list[str],
    rows: list[list[str]],
    confidence: float,
    file_sha256: str | None = None,
) -> MultimodalArtifact:
    axis_names = {a.name for a in axes}
    if "x" not in axis_names or "y" not in axis_names:
        raise ExtractionError("axes must include named x and y")
    for a in axes:
        if not a.unit or not str(a.unit).strip():
            raise ExtractionError("axis unit unknown: refuse silent values")
        if a.min_value is not None and a.max_value is not None and a.max_value < a.min_value:
            raise ExtractionError(f"axis {a.name!r} inverted")
    if not legend:
        raise ExtractionError("missing legend: refuse to invent series labels")
    path_out = source_path
    if file_sha256:
        path_out = f"{source_path}#sha256={file_sha256}"
    x_unit = next(a.unit for a in axes if a.name == "x")
    y_unit = next(a.unit for a in axes if a.name == "y")
    return MultimodalArtifact(
        artifact_id=artifact_id,
        modality="chart",
        provenance=Provenance(
            source_path=path_out,
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
        legend=legend,
        data=TableData(headers=["series", "x", "y"], rows=rows),
        confidence=confidence,
        validation_status=_status(confidence),  # type: ignore[arg-type]
    )


def extract_chart_from_preprocessed_pdf_directives(
    source_path: str, *, page: int = 1
) -> MultimodalArtifact:
    """
    Parse embedded LEGEND/AXIS/SERIES text directives.

    This is NOT real curve/bar chart vision. Marked as synthetic_fixture /
    preprocessed_input semantics (source_type=synthetic_fixture).
    """
    meta = load_source_bytes(source_path)
    doc = open_pdf(source_path)
    try:
        blocks = extract_page_text_blocks(doc, page)
    finally:
        doc.close()
    if not blocks:
        raise ExtractionError("PDF page has no text blocks for preprocessed chart parse")

    legend: list[str] = []
    axes: list[AxisSpec] = []
    rows: list[list[str]] = []
    union_bbox = None
    for block in blocks:
        for line in str(block["text"]).splitlines():
            line = line.strip()
            if not line:
                continue
            m = _LEGEND_LINE.match(line)
            if m:
                legend = [x.strip() for x in m.group("items").split(",") if x.strip()]
                continue
            m = _AXIS_LINE.match(line)
            if m:
                axes.append(
                    AxisSpec(
                        name=m.group("name"),
                        label=m.group("name"),
                        unit=m.group("unit"),
                        min_value=float(m.group("min")),
                        max_value=float(m.group("max")),
                    )
                )
                continue
            m = _SERIES_LINE.match(line)
            if m:
                name = m.group("name")
                if legend and name not in legend:
                    raise ExtractionError(f"series {name!r} not in legend")
                x_v, y_v = float(m.group("x")), float(m.group("y"))
                rows.append([name, m.group("x"), m.group("y")])
                bb = block["bbox"]
                if union_bbox is None:
                    union_bbox = dict(bb)
                else:
                    union_bbox["x0"] = min(union_bbox["x0"], bb["x0"])
                    union_bbox["y0"] = min(union_bbox["y0"], bb["y0"])
                    union_bbox["x1"] = max(union_bbox["x1"], bb["x1"])
                    union_bbox["y1"] = max(union_bbox["y1"], bb["y1"])
                for a in axes:
                    if a.name == "x" and a.min_value is not None and a.max_value is not None:
                        if x_v < a.min_value or x_v > a.max_value:
                            raise ExtractionError("x value outside declared axis range")
                    if a.name == "y" and a.min_value is not None and a.max_value is not None:
                        if y_v < a.min_value or y_v > a.max_value:
                            raise ExtractionError("y value outside declared axis range")

    if not legend:
        raise ExtractionError("missing legend on preprocessed PDF chart page")
    if len(axes) < 2:
        raise ExtractionError("preprocessed PDF chart missing x/y AXIS directives")
    if not rows:
        raise ExtractionError("preprocessed PDF chart missing SERIES points")
    if union_bbox is None:
        raise ExtractionError("preprocessed PDF chart bbox unavailable")

    # Cap confidence: never claim high-confidence "vision" for directive packets.
    confidence = 0.55
    return _finalize(
        artifact_id=f"preprocessed-chart-{meta.sha256[:12]}-{page}",
        source_path=source_path,
        source_type="synthetic_fixture",
        page=page,
        bbox=_require_bbox(union_bbox),
        axes=axes,
        legend=legend,
        rows=rows,
        confidence=confidence,
        file_sha256=meta.sha256,
    )


# Backward-compatible name — explicitly demoted.
def extract_chart_from_pdf(source_path: str, *, page: int = 1) -> MultimodalArtifact:
    return extract_chart_from_preprocessed_pdf_directives(source_path, page=page)


def extract_chart_from_packet(source_path: str) -> MultimodalArtifact:
    packet = json.loads(Path(source_path).read_text(encoding="utf-8"))
    if not isinstance(packet, dict):
        raise ExtractionError("chart packet root must be object")
    kind = str(packet.get("input_kind") or "").strip()
    if kind not in {"offline_fixture", "preprocessed_input"}:
        raise ExtractionError(
            "JSON chart packet must set input_kind=offline_fixture|preprocessed_input"
        )
    required = ("page", "bbox", "axes", "legend", "series", "confidence")
    missing = [k for k in required if k not in packet]
    if missing:
        raise ExtractionError(f"chart packet missing fields: {missing}")
    legend = packet["legend"]
    if not isinstance(legend, list) or not legend:
        raise ExtractionError("missing legend")
    axes = [AxisSpec.model_validate(a) for a in packet["axes"]]
    rows: list[list[str]] = []
    for s in packet["series"]:
        name = s["name"]
        if name not in legend:
            raise ExtractionError(f"series name {name!r} not in legend")
        for p in s["points"]:
            rows.append([str(name), str(p["x"]), str(p["y"])])
    meta = load_source_bytes(source_path)
    return _finalize(
        artifact_id=str(packet.get("artifact_id") or f"chart-{meta.sha256[:12]}"),
        source_path=source_path,
        source_type=str(packet.get("source_type", "synthetic_fixture")),
        page=int(packet["page"]),
        bbox=_require_bbox(packet["bbox"]),
        axes=axes,
        legend=[str(x) for x in legend],
        rows=rows,
        confidence=float(packet["confidence"]),
        file_sha256=meta.sha256,
    )


def extract_chart_artifact(source_path: str, **kwargs: Any) -> MultimodalArtifact:
    """
    Non-vision chart entrypoints only.
    Raster images must go through QwenVisionAdapter / run_qwen_vision_*.
    """
    suffix = Path(source_path).suffix.lower()
    if suffix == ".pdf":
        return extract_chart_from_preprocessed_pdf_directives(source_path, **kwargs)
    if suffix == ".json":
        return extract_chart_from_packet(source_path)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ExtractionError(
            "raster chart requires Qwen vision path (QwenVisionAdapter); "
            "ChartAdapter will not pretend to parse pixels"
        )
    raise ExtractionError(f"unsupported chart source type: {suffix!r}")
