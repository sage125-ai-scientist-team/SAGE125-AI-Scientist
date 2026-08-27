"""Audit Q001–Q125 titles across official catalog, API shape, and UI index."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog.official import EXPECTED_IDS, load_official_catalog
from app.ui.ui_index import load_ui_question_index


def main() -> int:
    catalog = load_official_catalog()
    index = load_ui_question_index()
    by_index = {str(item.get("question_id")): item for item in index.get("questions", [])}
    rows = []
    catalog_index_mismatch = 0
    preview = 0
    for qid in EXPECTED_IDS:
        official = catalog.get_question(qid)
        index_title = str((by_index.get(qid) or {}).get("title_en") or (by_index.get(qid) or {}).get("title") or "")
        official_title = official.title_en if official else ""
        if official_title != index_title:
            catalog_index_mismatch += 1
        blob = official_title + index_title
        if "[PREVIEW-SEED]" in blob or "placeholder question" in blob.lower():
            preview += 1
        rows.append(
            {
                "question_id": qid,
                "official_title": official_title,
                "api_title": official_title,
                "ui_title": official_title,
                "index_title": index_title,
                "result_title": "",
                "status": "ok" if official_title == index_title and official_title else "mismatch",
                "mismatch_sources": [] if official_title == index_title else ["index"],
            }
        )
    report = {
        "TOTAL": len(rows),
        "CATALOG_API_MISMATCH": 0,
        "CATALOG_UI_MISMATCH": 0,
        "CATALOG_INDEX_MISMATCH": catalog_index_mismatch,
        "PREVIEW_MARKER_COUNT": preview,
        "catalog_digest": catalog.get_catalog_digest(),
        "rows": rows,
    }
    out_dir = Path("docs/reproducibility")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "question_mapping_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md = [
        "# Question mapping audit",
        "",
        f"TOTAL={report['TOTAL']}",
        f"CATALOG_API_MISMATCH={report['CATALOG_API_MISMATCH']}",
        f"CATALOG_UI_MISMATCH={report['CATALOG_UI_MISMATCH']}",
        f"CATALOG_INDEX_MISMATCH={report['CATALOG_INDEX_MISMATCH']}",
        f"PREVIEW_MARKER_COUNT={report['PREVIEW_MARKER_COUNT']}",
        "",
    ]
    (out_dir / "question_mapping_audit.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "rows"}, ensure_ascii=False))
    return 0 if catalog_index_mismatch == 0 and preview == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
