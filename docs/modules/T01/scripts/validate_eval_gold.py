"""
校验 T01 eval_gold 包结构与正式评测就绪门禁。

说明：
    - ``--require-ready`` **只读**，不改写任何文件；
    - ``provenance.git_commit`` 语义 = **payload commit**（冻结金标内容的提交），
      不是“包含 manifest 自身的最终 tip SHA”；
    - ``--write-checksums`` 可配合 ``--payload-commit`` 写入该字段后重算清单。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_MANIFEST_TOP = {
    "schema_version",
    "package_id",
    "evaluation_tier",
    "ready_for_t09_formal_eval",
    "not_synthetic_provisional_fixture",
    "provenance",
}

REQUIRED_PROVENANCE = {
    "source_uri",
    "data_version",
    "license_or_authorization",
    "file_sha256",
    "repository_path",
    "reproduce_command",
    "git_commit",
    "labels_expected_results_domain_mapping",
    "declaration_not_synthetic_provisional_fixture",
}

REQUIRED_PAIR_FIELDS = {
    "claim_id",
    "claim",
    "evidence_id",
    "source_uri",
    "data_version",
    "license_or_authorization",
    "quote",
    "locator",
    "authors",
    "expected_decision",
    "domain",
    "provisional",
    "synthetic",
    "fixture",
    "evaluation_tier",
}

CHECKSUM_TARGETS = [
    "manifest.json",
    "pairs.json",
    "REPRODUCE.md",
    "CURATION_CHECKLIST.md",
    "T09_HANDOFF.md",
    "T09_HANDOFF_MESSAGE.md",
    "FINAL_PROVENANCE_PACKAGE.md",
    "pair.example.json",
    "domain_mapping_eval_gold.json",
    "sources/SOURCES_INDEX.json",
]


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


def _load_json(path: Path) -> dict[str, Any]:
    """
    以 UTF-8（允 BOM）加载 JSON 对象。

    参数：
        path: JSON 路径。

    返回：
        dict。
    """
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _dump_json(path: Path, data: dict[str, Any]) -> None:
    """
    以 UTF-8（无 BOM）+ LF + 尾换行写入 JSON。

    参数：
        path: 目标路径。
        data: 对象。
    """
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.encode("utf-8"))


def write_checksums(
    package_dir: Path,
    *,
    payload_commit: str | None = None,
) -> Path:
    """
    写入 checksums.sha256；可选更新 payload commit 字段。

    参数：
        package_dir: eval_gold/v1。
        payload_commit: 若提供，写入 ``provenance.git_commit``（payload 语义）。

    返回：
        checksums 路径。

    说明：
        **不会**自动写成当前 HEAD。manifest 无法可靠自指最终 tip SHA。
    """
    manifest_path = package_dir / "manifest.json"
    pairs_path = package_dir / "pairs.json"
    manifest = _load_json(manifest_path)
    pairs_doc = _load_json(pairs_path)
    pairs = pairs_doc.get("pairs") or []
    provenance = dict(manifest.get("provenance") or {})
    if payload_commit:
        provenance["git_commit"] = payload_commit
        provenance["git_commit_semantics"] = (
            "payload_commit — SHA of the commit that freezes gold content "
            "(pairs/sources/domain mapping). Not the tip commit that only "
            "updates this manifest field/checksums."
        )
    provenance["file_sha256_catalog"] = (
        "docs/modules/T01/eval_gold/v1/checksums.sha256"
    )
    labels = dict(provenance.get("labels_expected_results_domain_mapping") or {})
    labels["current_pair_count"] = int(pairs_doc.get("pair_count") or len(pairs))
    provenance["labels_expected_results_domain_mapping"] = labels
    provenance["file_sha256"] = {
        "_note": "Authoritative package digests are listed in checksums.sha256; "
        "source XML/PDF digests are in sources/SOURCES_INDEX.json"
    }
    manifest["provenance"] = provenance
    _dump_json(manifest_path, manifest)

    hashes: dict[str, str] = {}
    for name in CHECKSUM_TARGETS:
        path = package_dir / name
        if path.is_file():
            hashes[name] = _sha256_file(path)

    checksums_path = package_dir / "checksums.sha256"
    lines = [f"{digest}  {name}" for name, digest in sorted(hashes.items())]
    checksums_path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return checksums_path


def validate_package(package_dir: Path, *, require_ready: bool = False) -> int:
    """
    只读校验 eval_gold 包。

    参数：
        package_dir: 包目录。
        require_ready: 是否强制正式评测就绪。

    返回：
        进程退出码（0 成功）。
    """
    errors: list[str] = []
    manifest_path = package_dir / "manifest.json"
    pairs_path = package_dir / "pairs.json"
    if not manifest_path.is_file():
        print("ERROR: manifest.json missing", file=sys.stderr)
        return 2
    if not pairs_path.is_file():
        print("ERROR: pairs.json missing", file=sys.stderr)
        return 2

    manifest = _load_json(manifest_path)
    missing_top = REQUIRED_MANIFEST_TOP - set(manifest)
    if missing_top:
        errors.append(f"manifest missing top fields: {sorted(missing_top)}")

    provenance = manifest.get("provenance") or {}
    missing_prov = REQUIRED_PROVENANCE - set(provenance)
    if missing_prov:
        errors.append(f"provenance missing fields: {sorted(missing_prov)}")

    pairs_doc = _load_json(pairs_path)
    pairs = pairs_doc.get("pairs")
    if not isinstance(pairs, list):
        errors.append("pairs.json.pairs must be a list")
        pairs = []

    ready = bool(manifest.get("ready_for_t09_formal_eval"))
    not_fixture_flag = bool(manifest.get("not_synthetic_provisional_fixture"))

    domain_doc = provenance.get("labels_expected_results_domain_mapping") or {}
    domain_path = domain_doc.get("domain_mapping_doc")
    if domain_path:
        repo_root = package_dir.resolve()
        while not (repo_root / ".git").exists() and repo_root != repo_root.parent:
            repo_root = repo_root.parent
        candidate = Path(domain_path)
        if not candidate.is_file():
            candidate = repo_root / domain_path
        if not candidate.is_file():
            candidate = package_dir / Path(domain_path).name
        if candidate.is_file():
            mapping = _load_json(candidate)
            if mapping.get("depends_on_harness_fixture"):
                errors.append(
                    "domain mapping must not depend on harness fixture "
                    f"({domain_path})"
                )
            linked = mapping.get("rows") or mapping.get("mappings") or []
            for row in linked:
                for claim_id in row.get("linked_gold_claim_ids") or []:
                    if str(claim_id).startswith("CLAIM-"):
                        errors.append(
                            "domain mapping references harness fixture claim id "
                            f"{claim_id} in {domain_path}"
                        )
        elif ready:
            errors.append(f"domain mapping doc missing: {domain_path}")

    if ready:
        if not pairs:
            errors.append("ready_for_t09_formal_eval=true but pairs is empty")
        if not not_fixture_flag:
            errors.append(
                "ready_for_t09_formal_eval=true requires "
                "not_synthetic_provisional_fixture=true"
            )
        for index, pair in enumerate(pairs):
            missing = REQUIRED_PAIR_FIELDS - set(pair)
            if missing:
                errors.append(f"pair[{index}] missing fields: {sorted(missing)}")
                continue
            if pair.get("provisional") is not False:
                errors.append(f"pair[{index}] provisional must be false")
            if pair.get("synthetic") is not False:
                errors.append(f"pair[{index}] synthetic must be false")
            if pair.get("fixture") is not False:
                errors.append(f"pair[{index}] fixture must be false")
            if pair.get("evaluation_tier") != "actual_gold":
                errors.append(f"pair[{index}] evaluation_tier must be actual_gold")
            quote = str(pair.get("quote") or "").strip()
            if not quote:
                errors.append(f"pair[{index}] quote empty")
            if quote.startswith("10.") and "/" in quote and " " not in quote:
                errors.append(f"pair[{index}] DOI-only quote forbidden")
            claim_id = str(pair.get("claim_id") or "")
            if claim_id.startswith("CLAIM-"):
                errors.append(
                    f"pair[{index}] claim_id looks like harness fixture id: {claim_id}"
                )

    if require_ready and not ready:
        errors.append("--require-ready set but ready_for_t09_formal_eval=false")

    checksums_path = package_dir / "checksums.sha256"
    if checksums_path.is_file():
        for line in checksums_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            expected, name = parts[0], parts[-1]
            path = package_dir / name
            if not path.is_file():
                errors.append(f"checksum target missing: {name}")
                continue
            if name == "checksums.sha256":
                continue
            actual = _sha256_file(path)
            if actual != expected:
                errors.append(f"checksum mismatch for {name}: {actual} != {expected}")
    elif ready:
        errors.append("checksums.sha256 missing")

    # Cross-check frozen XML hashes vs index (same raw-byte semantics)
    index_path = package_dir / "sources" / "SOURCES_INDEX.json"
    if index_path.is_file():
        raw_index = json.loads(index_path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw_index, list):
            errors.append("SOURCES_INDEX.json must be a JSON list")
        else:
            for row in raw_index:
                pmcid = row.get("pmcid")
                xml_path = package_dir / "sources" / f"{pmcid}.xml"
                if not xml_path.is_file():
                    errors.append(f"frozen xml missing: {pmcid}")
                    continue
                actual = _sha256_file(xml_path)
                if actual != row.get("xml_sha256"):
                    errors.append(
                        f"index/xml mismatch for {pmcid}: "
                        f"{actual} != {row.get('xml_sha256')}"
                    )

    print(f"package={package_dir}")
    print(f"ready_for_t09_formal_eval={ready}")
    print(f"not_synthetic_provisional_fixture={not_fixture_flag}")
    print(f"pair_count={len(pairs)}")
    print(f"evaluation_tier={manifest.get('evaluation_tier')}")
    print(f"payload_commit={provenance.get('git_commit')}")
    print(
        "git_commit_semantics="
        + str(
            provenance.get("git_commit_semantics")
            or "payload_commit (see provenance.git_commit_semantics)"
        )
    )

    if errors:
        print("RESULT=FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    if ready:
        print("RESULT=ACTUAL_GOLD_OK")
    else:
        print("RESULT=STRUCTURE_OK")
        print(
            "NOTE: scaffold only; harness evidence_gold_set.json remains excluded "
            "from T09 actual gold."
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """
    CLI 入口。

    参数：
        argv: 参数列表。

    返回：
        退出码。
    """
    parser = argparse.ArgumentParser(description="Validate T01 eval_gold package")
    parser.add_argument(
        "--package",
        default="docs/modules/T01/eval_gold/v1",
        help="Path to eval_gold package directory",
    )
    parser.add_argument(
        "--write-checksums",
        action="store_true",
        help="Recompute checksums (does not auto-set tip HEAD as git_commit)",
    )
    parser.add_argument(
        "--payload-commit",
        default=None,
        help="When writing checksums, set provenance.git_commit to this payload SHA",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Fail unless package is marked ready for T09 formal eval",
    )
    args = parser.parse_args(argv)
    package_dir = Path(args.package)
    if not package_dir.is_dir():
        print(f"ERROR: package dir not found: {package_dir}", file=sys.stderr)
        return 2
    if args.write_checksums:
        write_checksums(package_dir, payload_commit=args.payload_commit)
        print(f"wrote checksums under {package_dir}")
    return validate_package(package_dir, require_ready=args.require_ready)


if __name__ == "__main__":
    raise SystemExit(main())
