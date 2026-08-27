"""Rebuild the UI question index from the official catalog only."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog.official import load_official_catalog, validate_catalog
from app.ui.ui_index import UI_INDEX_PATH, build_ui_question_index


def main() -> int:
    catalog = load_official_catalog()
    validate_catalog(
        {
            "catalog_source": "official",
            "catalog_version": catalog.version,
            "questions": [
                {
                    "question_id": item.question_id,
                    "title_en": item.title_en,
                    "domain": item.domain,
                    "title_zh": item.title_zh,
                }
                for item in catalog.list_questions()
            ],
        }
    )
    if UI_INDEX_PATH.exists():
        backup_dir = Path.home() / "AppData" / "Local" / "Temp" / "sage125-catalog-restore-14"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(UI_INDEX_PATH, backup_dir / f"ui_question_index.{stamp}.json")
    tmp = UI_INDEX_PATH.with_suffix(".json.tmp")
    index = build_ui_question_index()
    blob = json.dumps(index, ensure_ascii=False)
    if "[PREVIEW-SEED]" in blob or "placeholder question" in blob.lower():
        raise SystemExit("rebuilt UI index still contains preview markers")
    tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(UI_INDEX_PATH)
    print(f"UI_INDEX_PATH={UI_INDEX_PATH}")
    print(f"question_count={index.get('question_count')}")
    print(f"catalog_digest={index.get('catalog_digest')}")
    print("UI_INDEX_REBUILD_STATUS=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
