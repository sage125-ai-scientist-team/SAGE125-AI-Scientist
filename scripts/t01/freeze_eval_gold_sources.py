"""
重新获取并冻结 T01 eval_gold 源 XML 的规范字节。

字节语义（canonical bytes）：
    - XML = Europe PMC ``fullTextXML`` HTTP 响应体原样落盘（``Path.write_bytes``）；
    - 不做换行转换、不写 BOM、不美化；
    - Git 侧以 ``-text`` 存储，禁止 autocrlf 改写；
    - ``SOURCES_INDEX.json`` / pair ``source_file_sha256.xml`` / 校验器均对该字节做 SHA-256。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = REPO / "docs" / "modules" / "T01" / "eval_gold" / "v1"


def _sha256_bytes(data: bytes) -> str:
    """计算字节串 SHA-256 hex。"""
    return hashlib.sha256(data).hexdigest()


def _download_bytes(url: str) -> bytes:
    """
    下载 URL 原始字节。

    参数：
        url: 远程地址。

    返回：
        响应体 bytes。
    """
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SAGE125-T01-eval-gold-freeze/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def freeze_xml(package: Path) -> list[dict]:
    """
    按现有 meta 重新拉取 XML 并回写哈希。

    参数：
        package: eval_gold/v1 目录。

    返回：
        更新后的 SOURCES_INDEX 行。
    """
    sources = package / "sources"
    rows: list[dict] = []
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for meta_path in sorted(sources.glob("PMC*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        pmcid = meta["pmcid"]
        xml_url = meta.get("xml_url") or (
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
        )
        print(f"freeze xml {pmcid} <- {xml_url}")
        data = _download_bytes(xml_url)
        xml_path = sources / f"{pmcid}.xml"
        xml_path.write_bytes(data)
        meta["xml_sha256"] = _sha256_bytes(data)
        meta["xml_bytes"] = len(data)
        meta["xml_byte_semantics"] = (
            "europepmc_fullTextXML_http_response_body_raw;"
            "no_newline_conversion;no_bom;git_-text"
        )
        meta["xml_frozen_at_utc"] = retrieved
        meta["xml_url"] = xml_url
        # Keep existing pdf hashes; do not re-fetch PDF here.
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rows.append(meta)
        print(f"  sha256={meta['xml_sha256']} bytes={meta['xml_bytes']}")

    index_path = sources / "SOURCES_INDEX.json"
    index_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return rows


def sync_pair_xml_hashes(package: Path, rows: list[dict]) -> None:
    """
    将 pairs.json 内 source_file_sha256.xml 与冻结索引对齐。

    参数：
        package: 包目录。
        rows: SOURCES_INDEX 行。
    """
    by_pmc = {row["pmcid"]: row for row in rows}
    pairs_path = package / "pairs.json"
    doc = json.loads(pairs_path.read_text(encoding="utf-8"))
    for pair in doc.get("pairs") or []:
        pmcid = pair.get("pmcid") or pair.get("source_id")
        if pmcid not in by_pmc:
            continue
        row = by_pmc[pmcid]
        hashes = dict(pair.get("source_file_sha256") or {})
        hashes["xml"] = row["xml_sha256"]
        hashes["xml_path"] = row["xml_path"]
        hashes["pdf"] = row["pdf_sha256"]
        hashes["pdf_path"] = row["pdf_path"]
        pair["source_file_sha256"] = hashes
        # Preserve CC-BY attribution text; refresh freeze stamp in data_version.
        pair["data_version"] = (
            f"europepmc-xml-frozen@{row['xml_frozen_at_utc'][:10]}"
            f"+pdf-sha256={row['pdf_sha256'][:12]}"
        )
    pairs_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI：冻结 XML 规范字节。"""
    parser = argparse.ArgumentParser(description="Freeze eval_gold XML canonical bytes")
    parser.add_argument("--package", default=str(DEFAULT_PACKAGE))
    args = parser.parse_args(argv)
    package = Path(args.package)
    if not package.is_dir():
        print(f"ERROR: package missing: {package}", file=sys.stderr)
        return 2
    rows = freeze_xml(package)
    sync_pair_xml_hashes(package, rows)
    print(f"RESULT=FROZEN count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
