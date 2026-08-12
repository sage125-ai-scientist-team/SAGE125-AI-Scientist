"""
表格提取：真实 PDF（PyMuPDF）+ offline_fixture packet。

- 单位无法可靠提取 → needs_review
- confidence 由可解释检查计算，不固定高分
- 文件 SHA-256 写入 provenance.source_path 的 #sha256= 后缀，并进入 EvidenceCard locator
"""

from __future__ import annotations

import json
import re
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
_UNIT_IN_HEADER = re.compile(
    r"^(?P<name>.+?)\s*[\(\[](?P<unit>[^\)\]]+)[\)\]]\s*$"
)


def _require_bbox(raw: Any) -> BoundingBox:
    if not isinstance(raw, dict):
        raise ExtractionError("table requires bbox object")
    box = BoundingBox.model_validate(raw)
    if box.x1 <= box.x0 or box.y1 <= box.y0:
        raise ExtractionError("illegal bbox: degenerate rectangle")
    return box


def _norm_cell(value: str) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    return text.replace(" _", " ").replace("_ ", " ").strip(" _")


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


def _detect_probable_merges(rows: list[list[str]]) -> list[dict[str, Any]]:
    """Heuristic: identical non-empty adjacent cells in a row → probable merge marker."""
    found: list[dict[str, Any]] = []
    for r_i, row in enumerate(rows):
        c = 0
        while c < len(row):
            val = row[c]
            span = 1
            while c + span < len(row) and row[c + span] == val and val != "":
                span += 1
            if span > 1:
                found.append(
                    {
                        "row": r_i,
                        "col": c,
                        "row_span": 1,
                        "col_span": span,
                        "value": val,
                        "detection": "adjacent_identical_heuristic",
                    }
                )
            c += span
    return found


def _units_from_headers(headers: list[str]) -> tuple[list[str], list[ColumnUnitBinding]]:
    clean_headers: list[str] = []
    bindings: list[ColumnUnitBinding] = []
    for h in headers:
        m = _UNIT_IN_HEADER.match(h)
        if m:
            name = m.group("name").strip()
            unit = m.group("unit").strip()
            clean_headers.append(name)
            if unit:
                bindings.append(ColumnUnitBinding(column=name, unit=unit))
        else:
            clean_headers.append(h)
    return clean_headers, bindings


def _score_table_confidence(
    *,
    headers: list[str],
    rows: list[list[str]],
    column_units: list[ColumnUnitBinding],
    merged_marked: bool,
) -> tuple[float, str, list[str]]:
    notes: list[str] = []
    score = 0.45
    if headers and all(h.strip() for h in headers):
        score += 0.15
    else:
        notes.append("weak_headers")
    if rows and all(len(r) == len(headers) for r in rows):
        score += 0.15
    else:
        notes.append("row_width_issue")
    empty_cells = sum(1 for r in rows for c in r if not str(c).strip())
    total = max(1, sum(len(r) for r in rows))
    empty_ratio = empty_cells / total
    if empty_ratio < 0.1:
        score += 0.10
    elif empty_ratio > 0.4:
        score -= 0.10
        notes.append("many_empty_cells")
    if column_units:
        score += 0.15
        notes.append("units_present")
    else:
        notes.append("units_missing")
        score -= 0.05
    if merged_marked:
        notes.append("merged_cells_detected_or_declared")
        score -= 0.05
    score = max(0.0, min(1.0, score))
    if not column_units:
        # Force review when units unknown
        status = "needs_review"
        score = min(score, 0.79)
    elif score < _CONFIDENCE_REVIEW:
        status = "failed"
    elif score < _CONFIDENCE_PASS:
        status = "needs_review"
    else:
        status = "passed"
    return score, status, notes


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
    status: str,
    file_sha256: str,
) -> MultimodalArtifact:
    if len(headers) != len(set(headers)):
        raise ExtractionError("duplicate headers are structurally ambiguous")
    for i, row in enumerate(rows):
        if len(row) != len(headers):
            raise ExtractionError(f"row {i} width mismatch")
    return MultimodalArtifact(
        artifact_id=artifact_id,
        modality="table",
        provenance=Provenance(
            source_path=f"{source_path}#sha256={file_sha256}",
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
    raw_headers = [_norm_cell(h) for h in chosen["headers"]]
    rows = [[_norm_cell(c) for c in row] for row in chosen["rows"]]
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not raw_headers or any(not h for h in raw_headers):
        raise ExtractionError("PDF table headers incomplete")

    headers, inferred_units = _units_from_headers(raw_headers)
    bindings: list[ColumnUnitBinding] = list(inferred_units)
    for item in column_units or []:
        if "column" not in item or "unit" not in item or not str(item["unit"]).strip():
            raise ExtractionError("column_units need non-empty column/unit")
        bindings.append(
            ColumnUnitBinding(column=str(item["column"]), unit=str(item["unit"]).strip())
        )
    # Deduplicate by column name (caller overrides inferred)
    by_col: dict[str, ColumnUnitBinding] = {b.column: b for b in bindings}
    bindings = list(by_col.values())

    merges = _detect_probable_merges(rows)
    confidence, status, notes = _score_table_confidence(
        headers=headers,
        rows=rows,
        column_units=bindings,
        merged_marked=bool(merges),
    )
    legend = list(headers) + [f"note:{n}" for n in notes]
    if merges:
        legend.append(f"probable_merges:{len(merges)}")

    return _build_artifact(
        artifact_id=f"pdf-table-{meta.sha256[:12]}-{page}-{table_index}",
        source_path=source_path,
        source_type="pdf",
        page=page,
        bbox=_require_bbox(chosen["bbox"]),
        headers=headers,
        rows=rows,
        column_units=bindings,
        legend=legend,
        confidence=confidence,
        status=status,
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
            "JSON table packet must set input_kind=offline_fixture|preprocessed_input"
        )
    required = ("page", "bbox", "headers", "rows", "confidence")
    missing = [k for k in required if k not in packet]
    if missing:
        raise ExtractionError(f"table packet missing fields: {missing}")
    headers = [_norm_cell(h) for h in packet["headers"]]
    rows = [[_norm_cell(c) for c in row] for row in packet["rows"]]
    merged = packet.get("merged_cells") or []
    expanded = _expand_merged_cells(headers, rows, merged)
    column_units = []
    for item in packet.get("column_units") or []:
        column_units.append(
            ColumnUnitBinding(column=str(item["column"]), unit=str(item["unit"]).strip())
        )
    confidence = float(packet["confidence"])
    if not column_units:
        status = "needs_review"
        confidence = min(confidence, 0.79)
    elif confidence < _CONFIDENCE_REVIEW:
        status = "failed"
    elif confidence < _CONFIDENCE_PASS:
        status = "needs_review"
    else:
        status = "passed"
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
        legend=list(packet.get("legend") or [])
        + ([f"merged_cells:{len(merged)}"] if merged else []),
        confidence=confidence,
        status=status,
        file_sha256=meta.sha256,
    )


def extract_table_from_csv(source_path: str) -> MultimodalArtifact:
    """
    Scientific table deposited as CSV (e.g. Zenodo gold).

    Units inferred from header parentheses; missing units → needs_review.
    """
    import csv

    meta = load_source_bytes(source_path)
    with Path(source_path).open("r", encoding="utf-8", newline="") as fh:
        rows_raw = list(csv.reader(fh))
    if not rows_raw:
        raise ExtractionError("CSV table is empty")
    raw_headers = [_norm_cell(h) for h in rows_raw[0]]
    if not raw_headers or any(not h for h in raw_headers):
        raise ExtractionError("CSV table headers incomplete")
    body = [[_norm_cell(c) for c in row] for row in rows_raw[1:]]
    body = [r for r in body if any(c.strip() for c in r)]
    # Pad / trim rows to header width without inventing values beyond empty cells
    norm_rows: list[list[str]] = []
    for i, row in enumerate(body):
        if len(row) < len(raw_headers):
            row = row + [""] * (len(raw_headers) - len(row))
        elif len(row) > len(raw_headers):
            raise ExtractionError(f"CSV row {i} wider than header")
        norm_rows.append(row)
    headers, inferred = _units_from_headers(raw_headers)
    merges = _detect_probable_merges(norm_rows)
    confidence, status, notes = _score_table_confidence(
        headers=headers,
        rows=norm_rows,
        column_units=inferred,
        merged_marked=bool(merges),
    )
    # CSV tables have no page geometry; use a non-degenerate placeholder bbox
    # and keep page=1 with explicit note (fail-closed would block all CSV gold).
    legend = list(headers) + [f"note:{n}" for n in notes] + ["geometry:csv_no_page_bbox"]
    return _build_artifact(
        artifact_id=f"csv-table-{meta.sha256[:12]}",
        source_path=source_path,
        source_type="csv",
        page=1,
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0),
        headers=headers,
        rows=norm_rows,
        column_units=inferred,
        legend=legend,
        confidence=confidence,
        status=status,
        file_sha256=meta.sha256,
    )


def extract_table_artifact(source_path: str, **kwargs: Any) -> MultimodalArtifact:
    suffix = Path(source_path).suffix.lower()
    if suffix == ".pdf":
        return extract_table_from_pdf(source_path, **kwargs)
    if suffix == ".json":
        return extract_table_from_packet(source_path)
    if suffix == ".csv":
        return extract_table_from_csv(source_path)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ExtractionError(
            "scanned/raster table image requires vision path; fail-closed in TableAdapter"
        )
    raise ExtractionError(f"unsupported table source type: {suffix!r}")
