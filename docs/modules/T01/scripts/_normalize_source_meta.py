"""为 sources/*.meta.json 补齐 pdf_url / xml_url 并重写 SOURCES_INDEX。"""

from __future__ import annotations

import json
from pathlib import Path

SRC = Path("docs/modules/T01/eval_gold/v1/sources")
PDF_URLS = {
    "PMC2082661": (
        "https://journals.plos.org/plosone/article/file?"
        "id=10.1371/journal.pone.0001248&type=printable"
    ),
    "PMC5444614": (
        "https://journals.plos.org/ploscompbiol/article/file?"
        "id=10.1371/journal.pcbi.1005425&type=printable"
    ),
    "PMC4341466": "https://cdn.elifesciences.org/articles/05033/elife-05033-v1.pdf",
    "PMC5021692": "https://www.frontiersin.org/articles/10.3389/fncom.2016.00094/pdf",
    "PMC5021260": (
        "https://journals.plos.org/plosmedicine/article/file?"
        "id=10.1371/journal.pmed.1003052&type=printable"
    ),
}


def main() -> None:
    """规范化 meta 与索引。"""
    # Fix medicine PDF URL to match the DOI actually downloaded
    PDF_URLS["PMC5021260"] = (
        "https://journals.plos.org/plosmedicine/article/file?"
        "id=10.1371/journal.pmed.1002120&type=printable"
    )
    rows = []
    for path in sorted(SRC.glob("PMC*.meta.json")):
        row = json.loads(path.read_text(encoding="utf-8-sig"))
        pmcid = row["pmcid"]
        row["pdf_url"] = PDF_URLS[pmcid]
        row["xml_url"] = (
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
        )
        path.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rows.append(row)
    (SRC / "SOURCES_INDEX.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"normalized {len(rows)} sources")


if __name__ == "__main__":
    main()
