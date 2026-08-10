#!/usr/bin/env python3
"""Offline validate / isolated fetch for T06 provenance-locked gold package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SHA256SUMS_PATH = PACKAGE_DIR / "SHA256SUMS"
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"

ZENODO_FILES = {
    "raw/fishtrial_resistance.csv": (
        "https://zenodo.org/api/records/13378442/files/fishtrial_resistance.csv/content"
    ),
    "raw/fishtrial_capacitance.csv": (
        "https://zenodo.org/api/records/13378442/files/fishtrial_capacitance.csv/content"
    ),
    "raw/fishtrial_realz.csv": (
        "https://zenodo.org/api/records/13378442/files/fishtrial_realz.csv/content"
    ),
    "raw/fishtrial_imagz.csv": (
        "https://zenodo.org/api/records/13378442/files/fishtrial_imagz.csv/content"
    ),
    "raw/Picture1.png": (
        "https://zenodo.org/api/records/13378442/files/Picture1.png/content"
    ),
}

UA = {"User-Agent": "SAGE125-T06-gold-fetch/1.1"}

# Explicit inventory must match SHA256SUMS paths (excluding SHA256SUMS itself).
REQUIRED_INVENTORY = [
    "BYTE_SEMANTICS.md",
    "CONSISTENCY_MATRIX.md",
    "README.md",
    "VALIDATION_REPORT.md",
    "domain_mapping.json",
    "fetch_and_verify.py",
    "gold_labels.jsonl",
    "license_evidence.md",
    "manifest.json",
    "raw/Picture1.png",
    "raw/cc_by_4_0_legalcode.html",
    "raw/fishtrial_capacitance.csv",
    "raw/fishtrial_imagz.csv",
    "raw/fishtrial_realz.csv",
    "raw/fishtrial_resistance.csv",
    "raw/zenodo_landing_13378442.html",
    "raw/zenodo_record_13378442.json",
    "source_metadata.json",
]

FORBIDDEN_PLACEHOLDER_MARKERS = (
    "PENDING_CONFIRMATION",
    "<EMPTY_TEMP_DIR>",
    "<empty-temp>",
    "<filename>",
    "<sha>",
    "<url>",
    "TO_BE_FILLED",
    "PLACEHOLDER",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str, *, path: str | None = None, expected: str | None = None, actual: str | None = None) -> int:
    parts = [f"FAIL: {message}"]
    if path is not None:
        parts.append(f"path={path}")
    if expected is not None:
        parts.append(f"expected={expected}")
    if actual is not None:
        parts.append(f"actual={actual}")
    print(" ".join(parts), file=sys.stderr)
    return 1


def load_expected_sums(sums_path: Path) -> dict[str, str] | int:
    expected: dict[str, str] = {}
    lines = sums_path.read_bytes().splitlines()
    prev = ""
    for raw_line in lines:
        try:
            line = raw_line.decode("utf-8")
        except UnicodeDecodeError:
            return fail("SHA256SUMS is not UTF-8")
        if line.endswith("\r"):
            return fail("SHA256SUMS contains CR")
        if not line.strip():
            continue
        if "  " not in line:
            return fail("SHA256SUMS line must use two spaces between hash and path", path=line)
        digest, rel = line.split("  ", 1)
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            return fail("SHA256SUMS digest must be lowercase 64-hex", path=rel)
        if rel != rel.replace("\\", "/") or rel.startswith("/") or ".." in rel.split("/"):
            return fail("unsafe or non-POSIX path in SHA256SUMS", path=rel)
        if rel == "SHA256SUMS":
            return fail("SHA256SUMS must not list itself")
        if rel in expected:
            return fail("duplicate path in SHA256SUMS", path=rel)
        if prev and rel < prev:
            return fail("SHA256SUMS paths are not sorted", path=rel)
        expected[rel] = digest
        prev = rel
    return expected


def validate_package(root: Path) -> int:
    sums_path = root / "SHA256SUMS"
    if not sums_path.is_file():
        return fail("missing SHA256SUMS", path=str(sums_path))
    loaded = load_expected_sums(sums_path)
    if isinstance(loaded, int):
        return loaded
    expected = loaded
    if not expected:
        return fail("SHA256SUMS is empty")

    expected_paths = sorted(REQUIRED_INVENTORY)
    actual_paths = sorted(expected)
    if actual_paths != expected_paths:
        return fail(
            "SHA256SUMS inventory mismatch",
            expected=",".join(expected_paths),
            actual=",".join(actual_paths),
        )

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return fail("missing manifest.json")
    try:
        manifest = json.loads(manifest_path.read_bytes().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return fail(f"manifest parse error: {exc}")

    for key in (
        "is_synthetic",
        "is_provisional",
        "is_fixture",
        "license_name",
        "license_uri",
        "doi_or_accession",
        "source_landing_uri",
        "source_version",
        "non_synthetic_assertion",
        "modalities",
        "chart_error_policy_version",
        "controlled_artifact_applicable",
        "controlled_artifact_path",
        "controlled_artifact_na_reason",
        "reproducible_validate_command",
        "reproducible_fetch_command",
        "gold_label_count",
        "source_version_basis",
    ):
        if key not in manifest:
            return fail(f"manifest missing field: {key}")
    if manifest["is_synthetic"] or manifest["is_provisional"] or manifest["is_fixture"]:
        return fail("manifest marks package as synthetic/provisional/fixture")
    if "not synthetic" not in str(manifest["non_synthetic_assertion"]).lower():
        return fail("missing non-synthetic assertion")
    if set(manifest["modalities"]) != {"table", "chart"}:
        return fail("manifest modalities must be table+chart")
    if "manifest_sha256" in manifest or "sha256sums_sha256" in manifest:
        return fail("manifest must not embed self or SHA256SUMS hashes")
    if manifest.get("controlled_artifact_applicable") is not False:
        return fail("controlled_artifact_applicable must be false for public Zenodo package")
    if manifest.get("controlled_artifact_path") != "NOT_APPLICABLE":
        return fail("controlled_artifact_path must be NOT_APPLICABLE")
    if not str(manifest.get("controlled_artifact_na_reason") or "").strip():
        return fail("controlled_artifact_na_reason missing")
    if manifest.get("gold_label_count") != 100:
        return fail("manifest gold_label_count must be 100")
    fetch_cmd = str(manifest.get("reproducible_fetch_command") or "")
    if "--workdir" not in fetch_cmd or "mkdtemp" not in fetch_cmd:
        return fail("reproducible_fetch_command must create empty temp workdir via mkdtemp")
    for marker in FORBIDDEN_PLACEHOLDER_MARKERS:
        if marker in fetch_cmd or marker in str(manifest.get("reproducible_validate_command") or ""):
            return fail("manifest reproduce commands contain placeholder marker", actual=marker)
    for rel in (
        "README.md",
        "VALIDATION_REPORT.md",
        "CONSISTENCY_MATRIX.md",
        "manifest.json",
        "source_metadata.json",
    ):
        text = (root / rel).read_bytes().decode("utf-8", errors="replace")
        for marker in FORBIDDEN_PLACEHOLDER_MARKERS:
            if marker in text:
                return fail("formal package text contains placeholder marker", path=rel, actual=marker)

    for rel, digest in expected.items():
        path = root / rel
        if not path.is_file():
            return fail("missing inventoried file", path=rel)
        actual = sha256_file(path)
        if actual != digest:
            return fail("checksum mismatch", path=rel, expected=digest, actual=actual)

    # Reject unexpected files under package root (except .gitattributes and SHA256SUMS).
    # Ignore interpreter cache leftovers; validate itself must run with python -B.
    allowed = set(expected) | {"SHA256SUMS", ".gitattributes"}
    extras = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = rel.split("/")
        if "__pycache__" in parts or rel.endswith(".pyc"):
            continue
        if rel not in allowed:
            extras.append(rel)
    if extras:
        return fail("unexpected files in package", actual=",".join(sorted(extras)))

    png = (root / "raw" / "Picture1.png").read_bytes()
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        return fail("Picture1.png is not a PNG", path="raw/Picture1.png")

    labels_path = root / "gold_labels.jsonl"
    modalities: set[str] = set()
    label_count = 0
    seen_points: set[tuple[str, str]] = set()
    for line in labels_path.read_bytes().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line.decode("utf-8"))
        modalities.add(obj["modality"])
        label_count += 1
        if obj.get("confidence", 0) < 0.9:
            return fail("low confidence label", path=obj.get("record_id"))
        if obj["modality"] == "chart":
            tol = obj.get("tolerance") or {}
            if tol.get("relative_tolerance") != 0.05:
                return fail("chart relative tolerance must be 0.05", path=obj.get("record_id"))
            if "absolute_tolerance" not in tol:
                return fail("chart absolute_tolerance missing", path=obj.get("record_id"))
            key = (str(obj.get("series_id")), str(obj.get("point_id")))
            if key in seen_points:
                return fail("duplicate series_id/point_id", path=obj.get("record_id"))
            seen_points.add(key)
    if label_count != 100:
        return fail("gold label count must be 100", expected="100", actual=str(label_count))
    if "table" not in modalities or "chart" not in modalities:
        return fail(f"gold labels missing modalities: {sorted(modalities)}")

    domain = json.loads((root / "domain_mapping.json").read_bytes().decode("utf-8"))
    policy = domain.get("chart_error_policy") or {}
    if policy.get("eps_used") is not False:
        return fail("chart_error_policy.eps_used must be false")
    if policy.get("nonzero_relative_tolerance") != 0.05:
        return fail("chart_error_policy nonzero relative tolerance must be 0.05")
    if policy.get("zero_absolute_tolerance") != 0.0:
        return fail("chart_error_policy zero absolute tolerance must be 0.0")

    print("PASS: gold package validation succeeded")
    print(f"  root={root}")
    print(f"  files_checked={len(expected)}")
    print(f"  gold_labels={label_count}")
    print(f"  modalities={sorted(modalities)}")
    print(f"  doi={manifest['doi_or_accession']}")
    return 0


def _is_forbidden_workdir(workdir: Path) -> str | None:
    workdir = workdir.resolve()
    repo_root = PACKAGE_DIR.parents[4]  # .../docs/modules/T06/gold/<id>/<ver> -> repo?
    # PACKAGE_DIR = repo/docs/modules/T06/gold/zenodo.../v1.0.0
    # parents[0]=zenodo..., [1]=gold, [2]=T06, [3]=modules, [4]=docs, [5]=repo
    repo_root = PACKAGE_DIR.parents[5]
    if workdir == repo_root.resolve():
        return "workdir must not be repository root"
    if workdir == PACKAGE_DIR.resolve() or PACKAGE_DIR.resolve() in workdir.parents:
        return "workdir must not be inside the gold package"
    if (workdir / ".git").exists():
        return "workdir must not be a git directory"
    return None


def fetch_into(workdir: Path) -> int:
    workdir = workdir.resolve()
    reason = _is_forbidden_workdir(workdir)
    if reason:
        return fail(reason, path=str(workdir))
    if workdir.exists():
        if any(workdir.iterdir()):
            return fail("fetch workdir must be empty", path=str(workdir))
    else:
        workdir.mkdir(parents=True, exist_ok=False)

    expected = load_expected_sums(SHA256SUMS_PATH)
    if isinstance(expected, int):
        return expected

    # Copy frozen non-downloadable package files from the commit package.
    for rel in REQUIRED_INVENTORY:
        if rel.startswith("raw/fishtrial_") or rel == "raw/Picture1.png":
            continue
        src = PACKAGE_DIR / rel
        if not src.is_file():
            return fail("missing package file required for isolated fetch", path=rel)
        dest = workdir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())

    (workdir / "SHA256SUMS").write_bytes(SHA256SUMS_PATH.read_bytes())
    (workdir / ".gitattributes").write_bytes((PACKAGE_DIR / ".gitattributes").read_bytes())

    for rel, url in ZENODO_FILES.items():
        wanted = expected[rel]
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return fail(f"download HTTP {status}", path=rel)
            data = resp.read()
        actual = sha256_bytes(data)
        if actual != wanted:
            return fail("downloaded hash mismatch", path=rel, expected=wanted, actual=actual)
        dest = workdir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")
        part.write_bytes(data)
        if sha256_file(part) != wanted:
            part.unlink(missing_ok=True)
            return fail("part file hash mismatch", path=rel, expected=wanted)
        os.replace(part, dest)
        print(f"fetched {rel} sha256={actual}")

    # Do not regenerate derived scientific files during fetch; verify frozen copies.
    return validate_package(workdir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--workdir", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.fetch:
        if args.workdir is None:
            return fail("--fetch requires --workdir pointing to an empty temp directory")
        return fetch_into(args.workdir)
    return validate_package(PACKAGE_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
