"""
校验 T01 eval_gold 包结构与（可选）正式评测就绪门禁。

用途：
    - 脚手架阶段：确认 T09 所需 provenance 字段齐全；
    - 正式阶段：``--require-ready`` 拒绝 provisional/synthetic/fixture。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
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


def _sha256_file(path: Path) -> str:
    """
    计算文件 SHA-256 hex。

    参数：
        path: 文件路径。

    返回：
        小写 hex 摘要。
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    """
    加载 JSON 对象。

    参数：
        path: JSON 路径。

    返回：
        dict。
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _git_head(repo_root: Path) -> str:
    """
    读取当前 HEAD commit。

    参数：
        repo_root: 仓库根。

    返回：
        commit sha 或 unknown。
    """
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"


def write_checksums(package_dir: Path) -> Path:
    """
    回填 manifest 的 git_commit / pair_count，再写入 checksums.sha256。

    参数：
        package_dir: eval_gold/v1 目录。

    返回：
        checksums 路径。

    说明：
        SHA-256 权威清单是 ``checksums.sha256``（含 manifest.json）。
        先冻结 manifest 元数据，再哈希，避免自指循环。
    """
    manifest_path = package_dir / "manifest.json"
    pairs_path = package_dir / "pairs.json"
    manifest = _load_json(manifest_path)
    pairs_doc = _load_json(pairs_path)
    pairs = pairs_doc.get("pairs") or []
    provenance = dict(manifest.get("provenance") or {})
    repo_root = package_dir.resolve()
    while not (repo_root / ".git").exists() and repo_root != repo_root.parent:
        repo_root = repo_root.parent
    provenance["git_commit"] = _git_head(repo_root)
    provenance["file_sha256_catalog"] = (
        "docs/modules/T01/eval_gold/v1/checksums.sha256"
    )
    labels = dict(provenance.get("labels_expected_results_domain_mapping") or {})
    labels["current_pair_count"] = int(pairs_doc.get("pair_count") or len(pairs))
    provenance["labels_expected_results_domain_mapping"] = labels
    provenance["file_sha256"] = {
        "_note": "Authoritative digests are listed in checksums.sha256"
    }
    manifest["provenance"] = provenance
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    targets = [
        "manifest.json",
        "pairs.json",
        "REPRODUCE.md",
        "CURATION_CHECKLIST.md",
        "pair.example.json",
    ]
    hashes: dict[str, str] = {}
    for name in targets:
        path = package_dir / name
        if path.is_file():
            hashes[name] = _sha256_file(path)

    checksums_path = package_dir / "checksums.sha256"
    lines = [f"{digest}  {name}" for name, digest in sorted(hashes.items())]
    checksums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums_path


def validate_package(package_dir: Path, *, require_ready: bool = False) -> int:
    """
    校验 eval_gold 包。

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
            # checksums.sha256 自指时跳过严格自洽（内容含自身 hash 时会漂移）
            if name == "checksums.sha256":
                continue
            actual = _sha256_file(path)
            if actual != expected:
                errors.append(f"checksum mismatch for {name}: {actual} != {expected}")

    print(f"package={package_dir}")
    print(f"ready_for_t09_formal_eval={ready}")
    print(f"not_synthetic_provisional_fixture={not_fixture_flag}")
    print(f"pair_count={len(pairs)}")
    print(f"evaluation_tier={manifest.get('evaluation_tier')}")
    print(f"git_commit={provenance.get('git_commit')}")

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
        help="Recompute checksums and refresh manifest provenance hashes/commit",
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
        write_checksums(package_dir)
        print(f"wrote checksums under {package_dir}")
    return validate_package(package_dir, require_ready=args.require_ready)


if __name__ == "__main__":
    raise SystemExit(main())
