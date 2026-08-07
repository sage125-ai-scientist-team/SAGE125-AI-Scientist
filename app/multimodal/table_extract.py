"""
T06 Wave B：表格结构化提取（确定性、可复核、无 OCR 静默编造）。

输入为显式表格包 JSON（含 page/bbox/表头/单元格/合并单元/单位），
模拟 PDF 版面抽取结果；缺字段或非法 bbox 时 fail-closed。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.contracts.multimodal import (
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
        raise ExtractionError("table packet requires bbox object")
    try:
        box = BoundingBox.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 — surface as extraction failure
        raise ExtractionError(f"illegal bbox: {exc}") from exc
    if box.x1 <= box.x0 or box.y1 <= box.y0:
        raise ExtractionError("illegal bbox: degenerate rectangle")
    return box


def _expand_merged_cells(
    headers: list[str],
    rows: list[list[str]],
    merged: list[dict[str, Any]],
) -> list[list[str]]:
    """将合并单元格声明展开为矩形填充；冲突时失败。"""
    if not merged:
        return [list(r) for r in rows]
    grid = [list(r) for r in rows]
    n_rows = len(grid)
    n_cols = len(headers)
    for spec in merged:
        try:
            r0 = int(spec["row"])
            c0 = int(spec["col"])
            rs = int(spec.get("row_span", 1))
            cs = int(spec.get("col_span", 1))
            value = str(spec["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExtractionError(f"invalid merged_cells entry: {exc}") from exc
        if rs < 1 or cs < 1:
            raise ExtractionError("merged cell spans must be >= 1")
        if r0 < 0 or c0 < 0 or r0 + rs > n_rows or c0 + cs > n_cols:
            raise ExtractionError("merged cell out of table bounds")
        for r in range(r0, r0 + rs):
            for c in range(c0, c0 + cs):
                current = grid[r][c]
                if current not in ("", value) and current is not None:
                    raise ExtractionError(
                        f"merged cell conflict at ({r},{c}): "
                        f"{current!r} vs {value!r}"
                    )
                grid[r][c] = value
    return grid


def load_table_packet(source_path: str) -> dict[str, Any]:
    path = Path(source_path)
    if not path.is_file():
        raise ExtractionError(f"table source not found: {source_path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"table packet is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExtractionError("table packet root must be an object")
    return payload


def extract_table_artifact(source_path: str) -> MultimodalArtifact:
    """从表格包构建 MultimodalArtifact；安全失败，不编造单元格。"""
    packet = load_table_packet(source_path)
    required = ("page", "bbox", "headers", "rows", "confidence")
    missing = [k for k in required if k not in packet]
    if missing:
        raise ExtractionError(f"table packet missing fields: {missing}")

    page = int(packet["page"])
    if page < 1:
        raise ExtractionError("page must be >= 1")
    bbox = _require_bbox(packet["bbox"])

    headers = packet["headers"]
    rows = packet["rows"]
    if not isinstance(headers, list) or not headers:
        raise ExtractionError("headers must be a non-empty list")
    if any(not isinstance(h, str) or not h.strip() for h in headers):
        raise ExtractionError("headers must be non-empty strings")
    if len(headers) != len(set(headers)):
        raise ExtractionError("duplicate headers are structurally ambiguous")
    if not isinstance(rows, list):
        raise ExtractionError("rows must be a list")
    for i, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(headers):
            raise ExtractionError(
                f"row {i} width mismatch or non-list (expected {len(headers)})"
            )
        if any(not isinstance(cell, str) for cell in row):
            raise ExtractionError(f"row {i} contains non-string cells")

    merged = packet.get("merged_cells") or []
    if not isinstance(merged, list):
        raise ExtractionError("merged_cells must be a list")
    expanded = _expand_merged_cells(headers, rows, merged)

    column_units_raw = packet.get("column_units") or []
    column_units: list[ColumnUnitBinding] = []
    for item in column_units_raw:
        if not isinstance(item, dict) or "column" not in item or "unit" not in item:
            raise ExtractionError("column_units entries need column and unit")
        unit = str(item["unit"]).strip()
        if not unit:
            raise ExtractionError("unit must not be empty or guessed")
        column_units.append(
            ColumnUnitBinding(column=str(item["column"]), unit=unit)
        )

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
    artifact_id = str(packet.get("artifact_id") or f"table-{digest}")

    units = [b.unit for b in column_units]
    return MultimodalArtifact(
        artifact_id=artifact_id,
        modality="table",
        provenance=Provenance(
            source_path=source_path,
            source_type=source_type,  # type: ignore[arg-type]
            page=page,
            bbox=bbox,
        ),
        units=units,
        column_units=column_units,
        axes=None,
        legend=list(packet.get("legend") or []),
        data=TableData(headers=list(headers), rows=expanded),
        confidence=confidence,
        validation_status=status,  # type: ignore[arg-type]
    )
