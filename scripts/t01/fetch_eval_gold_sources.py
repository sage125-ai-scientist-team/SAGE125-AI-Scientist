"""
按 SOURCES_INDEX.json 重拉 publisher PDF / Europe PMC XML，并核对 SHA-256。

用途：
    T09 复现实验：仓库默认提交 XML + meta；大型 PDF 可按需下载并以哈希验收。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path


def _sha256_file(path: Path) -> str:
    """
    计算文件 SHA-256 hex。

    参数：
        path: 文件路径。

    返回：
        小写 hex。
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path) -> None:
    """
    下载 URL 到目标路径。

    参数：
        url: 远程地址。
        dest: 本地路径。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SAGE125-T01-eval-gold-fetch/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        dest.write_bytes(response.read())


def main(argv: list[str] | None = None) -> int:
    """
    CLI：按索引拉取并校验源文件。

    参数：
        argv: 可选参数列表。

    返回：
        退出码。
    """
    parser = argparse.ArgumentParser(description="Fetch/verify T01 eval_gold sources")
    parser.add_argument(
        "--package",
        default="docs/modules/T01/eval_gold/v1",
        help="eval_gold package directory",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also download publisher PDFs and verify pdf_sha256",
    )
    args = parser.parse_args(argv)
    package = Path(args.package)
    index_path = package / "sources" / "SOURCES_INDEX.json"
    if not index_path.is_file():
        print(f"ERROR: missing {index_path}", file=sys.stderr)
        return 2
    rows = json.loads(index_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for row in rows:
        pmcid = row["pmcid"]
        xml_path = package / "sources" / f"{pmcid}.xml"
        expected_xml = row["xml_sha256"]
        if not xml_path.is_file():
            xml_url = (
                f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
            )
            print(f"fetch xml {pmcid}")
            _download(xml_url, xml_path)
        actual_xml = _sha256_file(xml_path)
        if actual_xml != expected_xml:
            errors.append(f"{pmcid} xml mismatch: {actual_xml} != {expected_xml}")
        else:
            print(f"OK xml {pmcid}")

        if args.pdf:
            pdf_path = package / "sources" / f"{pmcid}.pdf"
            pdf_url = row.get("pdf_url")
            if not pdf_url:
                errors.append(f"{pmcid}: missing pdf_url in SOURCES_INDEX")
                continue
            if not pdf_path.is_file():
                print(f"fetch pdf {pmcid}")
                _download(pdf_url, pdf_path)
            actual_pdf = _sha256_file(pdf_path)
            if actual_pdf != row["pdf_sha256"]:
                errors.append(
                    f"{pmcid} pdf mismatch: {actual_pdf} != {row['pdf_sha256']}"
                )
            else:
                print(f"OK pdf {pmcid}")

    if errors:
        print("RESULT=FAIL")
        for item in errors:
            print(f"- {item}")
        return 1
    print("RESULT=SOURCE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
