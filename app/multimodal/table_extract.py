"""
T06 Wave B：表格提取——真实 PDF（PyMuPDF find_tables）+ 显式 offline_fixture packet。
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
from app.multimodal.pdf_io import extract_pdf_tables, load_source_bytes, open_pdf

_CONFIDENCE_PASS = 0.80
_CONFIDENCE_REVIEW = 0.50


def _require_bbox(raw: Any) -> BoundingBox:
    if not isinstance(raw, dict):
        raise ExtractionError("table requires bbox object")
    try:
        box = BoundingBox.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"illegal bbox: {exc}") from exc
    if box.x1 <= box.x0 or box.y1 <= box.y0:
        raise ExtractionError("illegal bbox: degenerate rectangle")
    return box


def _expand_merged_cells(
    headers: list[str],
    rows: list[list[str]],
    merged: list[dict[str, Any]],
) -> list[list[str]]:
    if not merged:
        return [list(r) for r in rows]
    grid = [list(r) for r in rows]
    n_rows, n_cols = len(grid), len(headers)
    for spec in merged:
        try:
            r0, c0 = int(spec["row"]), int(spec["col"])
            rs, cs = int(spec.get("row_span", 1)), int(spec.get("col_span", 1))
            value = str(spec["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExtractionError(f"invalid merged_cells entry: {exc}") from exc
        if rs < 1 or cs < 1 or r0 < 0 or c0 < 0 or r0 + rs > n_rows or c0 + cs > n_cols:
            raise ExtractionError("merged cell out of bounds or invalid span")
        for r in range(r0, r0 + rs):
            for c in range(c0, c0 + cs):
                cur = grid[r][c]
                if cur not in ("", value):
                    raise ExtractionError(f"merged cell conflict at ({r},{c})")
                grid[r][c] = value
    return grid


def _status_from_confidence(confidence: float) -> str:
    if confidence < _CONFIDENCE_REVIEW:
        return "failed"
    if confidence < _CONFIDENCE_PASS:
        return "needs_review"
    return "passed"


def _norm_cell(value: str) -> str:
    """Normalize PDF-extracted cell text without inventing new values."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    text = text.replace(" _", " ").replace("_ ", " ").strip(" _")
    return text


def _build_artifact(
    *,
    artifact_id: str,
    source_path: str,
    source_type: str,
    page: int,
    bbox: BoundingBox,
    headers: list[str],
    rows: list[list[str]],
    column_units: list[ColumnUnitBinding],
    legend: list[str],
    confidence: float,
    file_sha256: str | None,
) -> MultimodalArtifact:
    if len(headers) != len(set(headers)):
        raise ExtractionError("duplicate headers are structurally ambiguous")
    for i, row in enumerate(rows):
        if len(row) != len(headers):
            raise ExtractionError(f"row {i} width mismatch")
    status = _status_from_confidence(confidence)
    return MultimodalArtifact(
        artifact_id=artifact_id,
        modality="table",
        provenance=Provenance(
            source_path=source_path,
            source_type=source_type,  # type: ignore[arg-type]
            page=page,
            bbox=bbox,
        ),
        units=[b.unit for b in column_units],
        column_units=column_units,
        axes=None,
        legend=legend,
        data=TableData(headers=headers, rows=rows),
        confidence=confidence,
        validation_status=status,  # type: ignore[arg-type]
    )


def extract_table_from_pdf(
    source_path: str,
    *,
    page: int = 1,
    table_index: int = 0,
    column_units: list[dict[str, str]] | None = None,
) -> MultimodalArtifact:
    meta = load_source_bytes(source_path)
    doc = open_pdf(source_path)
    try:
        tables = extract_pdf_tables(doc, page)
    finally:
        doc.close()
    if not tables:
        raise ExtractionError("no tables detected on PDF page (fail-closed)")
    if table_index < 0 or table_index >= len(tables):
        raise ExtractionError(f"table_index {table_index} out of range")
    chosen = tables[table_index]
    headers = [_norm_cell(h) for h in chosen["headers"]]
    rows = [[_norm_cell(c) for c in row] for row in chosen["rows"]]
    # Drop fully empty trailing rows from detector noise.
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not headers or any(not h for h in headers):
        raise ExtractionError("PDF table headers incomplete")
    bindings: list[ColumnUnitBinding] = []
    for item in column_units or []:
        if "column" not in item or "unit" not in item or not str(item["unit"]).strip():
            raise ExtractionError("column_units need non-empty column/unit")
        bindings.append(
            ColumnUnitBinding(column=str(item["column"]), unit=str(item["unit"]).strip())
        )
    # Heuristic confidence: structure ok but OCR-less PDF table → slightly below 1
    confidence = 0.86 if rows else 0.4
    digest = meta.sha256[:12]
    return _build_artifact(
        artifact_id=f"pdf-table-{digest}-{page}-{table_index}",
        source_path=source_path,
        source_type="pdf",
        page=page,
        bbox=_require_bbox(chosen["bbox"]),
        headers=headers,
        rows=rows,
        column_units=bindings,
        legend=list(headers),
        confidence=confidence,
        file_sha256=meta.sha256,
    )


def extract_table_from_packet(source_path: str) -> MultimodalArtifact:
    path = Path(source_path)
    packet = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(packet, dict):
        raise ExtractionError("packet root must be object")
    kind = str(packet.get("input_kind") or "").strip()
    if kind not in {"offline_fixture", "preprocessed_input"}:
        raise ExtractionError(
            "JSON table packet must set input_kind=offline_fixture|preprocessed_input; "
            "unlabeled packets cannot claim raw PDF/vision extraction"
        )
    required = ("page", "bbox", "headers", "rows", "confidence")
    missing = [k for k in required if k not in packet]
    if missing:
        raise ExtractionError(f"table packet missing fields: {missing}")
    headers = packet["headers"]
    rows = packet["rows"]
    if not isinstance(headers, list) or not headers:
        raise ExtractionError("headers must be non-empty list")
    merged = packet.get("merged_cells") or []
    expanded = _expand_merged_cells(headers, rows, merged)
    column_units = []
    for item in packet.get("column_units") or []:
        column_units.append(
            ColumnUnitBinding(column=str(item["column"]), unit=str(item["unit"]).strip())
        )
    confidence = float(packet["confidence"])
    meta = load_source_bytes(source_path)
    source_type = packet.get("source_type", "synthetic_fixture")
    return _build_artifact(
        artifact_id=str(packet.get("artifact_id") or f"table-{meta.sha256[:12]}"),
        source_path=source_path,
        source_type=source_type,
        page=int(packet["page"]),
        bbox=_require_bbox(packet["bbox"]),
        headers=list(headers),
        rows=expanded,
        column_units=column_units,
        legend=list(packet.get("legend") or []),
        confidence=confidence,
        file_sha256=meta.sha256,
    )


def extract_table_artifact(source_path: str, **kwargs: Any) -> MultimodalArtifact:
    suffix = Path(source_path).suffix.lower()
    if suffix == ".pdf":
        return extract_table_from_pdf(source_path, **kwargs)
    if suffix == ".json":
        return extract_table_from_packet(source_path)
    raise ExtractionError(f"unsupported table source type: {suffix!r}")
