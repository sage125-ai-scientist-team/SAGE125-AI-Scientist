"""
校验（默认）或按需重拉 T01 eval_gold 源文件，并核对 SHA-256。

规范字节语义：
    - 权威 XML 字节 = 仓库内 ``sources/PMC*.xml`` 冻结快照（Europe PMC fullTextXML
      响应体原样；见 ``freeze_eval_gold_sources.py`` / meta ``xml_byte_semantics``）；
    - 默认模式 **只读校验**，不会覆盖已有 XML（避免远端漂移导致 exit 1）；
    - SHA-256 始终对磁盘原始字节计算（``read_bytes``），与索引同一语义。
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
    计算文件原始字节 SHA-256 hex。

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
    下载 URL 原始字节到目标路径（不改换行）。

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
    CLI：校验冻结源；可选 ``--refetch-missing`` 仅补齐缺失文件。

    参数：
        argv: 可选参数列表。

    返回：
        0 成功；1 哈希不一致；2 路径/索引错误。
    """
    parser = argparse.ArgumentParser(
        description="Verify frozen T01 eval_gold sources (canonical bytes)"
    )
    parser.add_argument(
        "--package",
        default="docs/modules/T01/eval_gold/v1",
        help="eval_gold package directory",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also verify publisher PDFs (download only if missing)",
    )
    parser.add_argument(
        "--refetch-missing",
        action="store_true",
        help="If a frozen XML/PDF is missing, download once then verify hash",
    )
    args = parser.parse_args(argv)
    package = Path(args.package)
    index_path = package / "sources" / "SOURCES_INDEX.json"
    if not index_path.is_file():
        print(f"ERROR: missing {index_path}", file=sys.stderr)
        return 2

    rows = json.loads(index_path.read_text(encoding="utf-8"))
    print("byte_semantics=raw_file_bytes_sha256")
    print("xml_authority=committed_frozen_snapshot_under_sources/")
    errors: list[str] = []

    for row in rows:
        pmcid = row["pmcid"]
        xml_path = package / "sources" / f"{pmcid}.xml"
        expected_xml = row["xml_sha256"]
        if not xml_path.is_file():
            if not args.refetch_missing:
                errors.append(
                    f"{pmcid}: frozen XML missing at {xml_path}; "
                    "restore from git or pass --refetch-missing"
                )
                continue
            xml_url = row.get("xml_url") or (
                f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
            )
            print(f"fetch-missing xml {pmcid}")
            _download(xml_url, xml_path)
        actual_xml = _sha256_file(xml_path)
        if actual_xml != expected_xml:
            errors.append(
                f"{pmcid} xml mismatch: {actual_xml} != {expected_xml} "
                "(canonical bytes are the committed frozen snapshot; "
                "do not re-download over a good checkout; "
                "maintainers re-freeze via freeze_eval_gold_sources.py)"
            )
        else:
            print(f"OK xml {pmcid} sha256={actual_xml}")

        if args.pdf:
            pdf_path = package / "sources" / f"{pmcid}.pdf"
            pdf_url = row.get("pdf_url")
            if not pdf_url:
                errors.append(f"{pmcid}: missing pdf_url in SOURCES_INDEX")
                continue
            if not pdf_path.is_file():
                if not args.refetch_missing:
                    errors.append(
                        f"{pmcid}: pdf missing; pass --refetch-missing to download"
                    )
                    continue
                print(f"fetch-missing pdf {pmcid}")
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
