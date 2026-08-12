"""T06：原始 PDF/图片输入 I/O（PyMuPDF），含字节哈希与页渲染。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.multimodal.errors import ExtractionError

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover
    raise ImportError("pymupdf is required for T06 PDF extraction") from exc


@dataclass(frozen=True)
class SourceBytes:
    path: str
    sha256: str
    size_bytes: int
    suffix: str


def load_source_bytes(source_path: str) -> SourceBytes:
    path = Path(source_path)
    if not path.is_file():
        raise ExtractionError(f"source not found: {source_path}")
    data = path.read_bytes()
    return SourceBytes(
        path=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        suffix=path.suffix.lower(),
    )


def open_pdf(source_path: str) -> Any:
    meta = load_source_bytes(source_path)
    if meta.suffix != ".pdf":
        raise ExtractionError(f"expected .pdf, got {meta.suffix!r}")
    try:
        return fitz.open(source_path)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"failed to open PDF: {exc}") from exc


def page_count(doc: Any) -> int:
    return int(doc.page_count)


def render_page_png_bytes(doc: Any, page_number: int, *, dpi: int = 120) -> bytes:
    """Render 1-based page to PNG bytes (for vision path / audit input hash)."""
    if page_number < 1 or page_number > doc.page_count:
        raise ExtractionError(f"page {page_number} out of range 1..{doc.page_count}")
    page = doc.load_page(page_number - 1)
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")


def extract_pdf_tables(doc: Any, page_number: int) -> list[dict[str, Any]]:
    """
    Extract tables from a PDF page using PyMuPDF find_tables.

    Returns list of {headers, rows, bbox} in PDF user space.
    """
    if page_number < 1 or page_number > doc.page_count:
        raise ExtractionError(f"page {page_number} out of range")
    page = doc.load_page(page_number - 1)
    try:
        finder = page.find_tables()
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError(f"PDF table find failed: {exc}") from exc
    tables = getattr(finder, "tables", None) or []
    out: list[dict[str, Any]] = []
    for table in tables:
        try:
            raw = table.extract()
            bbox = tuple(float(x) for x in table.bbox)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"PDF table extract failed: {exc}") from exc
        if not raw or len(raw) < 1:
            continue
        headers = [str(c or "").strip() for c in raw[0]]
        if not any(headers):
            continue
        rows: list[list[str]] = []
        for row in raw[1:]:
            rows.append([str(c or "").strip() for c in row])
        out.append(
            {
                "headers": headers,
                "rows": rows,
                "bbox": {
                    "x0": bbox[0],
                    "y0": bbox[1],
                    "x1": bbox[2],
                    "y1": bbox[3],
                },
            }
        )
    return out


def extract_page_text_blocks(doc: Any, page_number: int) -> list[dict[str, Any]]:
    if page_number < 1 or page_number > doc.page_count:
        raise ExtractionError(f"page {page_number} out of range")
    page = doc.load_page(page_number - 1)
    blocks = page.get_text("dict").get("blocks", [])
    out: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox")
        lines: list[str] = []
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(str(s.get("text", "")) for s in spans).strip()
            if text:
                lines.append(text)
        if not lines or not bbox:
            continue
        out.append(
            {
                "text": "\n".join(lines),
                "bbox": {
                    "x0": float(bbox[0]),
                    "y0": float(bbox[1]),
                    "x1": float(bbox[2]),
                    "y1": float(bbox[3]),
                },
            }
        )
    return out
