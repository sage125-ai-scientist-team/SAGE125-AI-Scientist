#!/usr/bin/env python3
"""Fetch and/or validate the frozen T06 real gold package bytes.

Uses only the Python standard library. Intended to run from a clean temp dir
or from the repository root.

Examples:
  python docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --validate
  python docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --fetch --workdir %TEMP%\\t06-gold-repro
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
RAW_DIR = PACKAGE_DIR / "raw"
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
SHA256SUMS_PATH = PACKAGE_DIR / "SHA256SUMS"

ZENODO_FILES = {
    "fishtrial_resistance.csv": (
        "https://zenodo.org/api/records/13378442/files/fishtrial_resistance.csv/content"
    ),
    "fishtrial_capacitance.csv": (
        "https://zenodo.org/api/records/13378442/files/fishtrial_capacitance.csv/content"
    ),
    "fishtrial_realz.csv": (
        "https://zenodo.org/api/records/13378442/files/fishtrial_realz.csv/content"
    ),
    "fishtrial_imagz.csv": (
        "https://zenodo.org/api/records/13378442/files/fishtrial_imagz.csv/content"
    ),
    "Picture1.png": (
        "https://zenodo.org/api/records/13378442/files/Picture1.png/content"
    ),
}

UA = {"User-Agent": "SAGE125-T06-gold-fetch/1.0"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_expected_sums() -> dict[str, str]:
    expected: dict[str, str] = {}
    for line in SHA256SUMS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, rel = line.split(None, 1)
        expected[rel.replace("\\", "/")] = digest
    return expected


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def validate_package(root: Path) -> int:
    expected = load_expected_sums()
    if not expected:
        return fail("SHA256SUMS is empty")

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return fail(f"missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for key in (
        "is_synthetic",
        "is_provisional",
        "is_fixture",
        "license_name",
        "license_uri",
        "doi_or_accession",
        "source_landing_uri",
        "source_version",
    ):
        if key not in manifest:
            return fail(f"manifest missing field: {key}")

    if manifest["is_synthetic"] or manifest["is_provisional"] or manifest["is_fixture"]:
        return fail("manifest marks package as synthetic/provisional/fixture")

    if manifest.get("license_name") != "Creative Commons Attribution 4.0 International":
        return fail("unexpected license_name")
    if "creativecommons.org/licenses/by/4.0" not in manifest.get("license_uri", ""):
        return fail("unexpected license_uri")

    mismatches = []
    for rel, digest in expected.items():
        path = root / rel
        if not path.is_file():
            mismatches.append(f"missing {rel}")
            continue
        actual = sha256_file(path)
        if actual != digest:
            mismatches.append(f"{rel}: expected {digest}, got {actual}")
    if mismatches:
        return fail("checksum mismatch:\n  " + "\n  ".join(mismatches))

    # Modality presence
    if not (root / "raw" / "fishtrial_resistance.csv").is_file():
        return fail("missing table modality file")
    if not (root / "raw" / "Picture1.png").is_file():
        return fail("missing chart modality file")
    png = (root / "raw" / "Picture1.png").read_bytes()
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        return fail("Picture1.png is not a PNG")

    labels_path = root / "gold_labels.jsonl"
    modalities = set()
    label_count = 0
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        modalities.add(obj["modality"])
        label_count += 1
        if obj.get("confidence", 0) < 0.9:
            return fail(f"low confidence label: {obj.get('record_id')}")
    if "table" not in modalities or "chart" not in modalities:
        return fail(f"gold labels missing modalities: {sorted(modalities)}")
    if label_count < 10:
        return fail(f"too few gold labels: {label_count}")

    print("PASS: gold package validation succeeded")
    print(f"  root={root}")
    print(f"  files_checked={len(expected)}")
    print(f"  gold_labels={label_count}")
    print(f"  modalities={sorted(modalities)}")
    print(f"  doi={manifest['doi_or_accession']}")
    return 0


def fetch_into(workdir: Path) -> int:
    workdir.mkdir(parents=True, exist_ok=True)
    raw = workdir / "raw"
    raw.mkdir(exist_ok=True)

    # Copy package metadata from repo package dir
    for name in (
        "manifest.json",
        "SHA256SUMS",
        "gold_labels.jsonl",
        "domain_mapping.json",
        "source_metadata.json",
        "README.md",
        "license_evidence.md",
        "VALIDATION_REPORT.md",
        "fetch_and_verify.py",
        "MANIFEST.sha256",
    ):
        src = PACKAGE_DIR / name
        if src.is_file():
            (workdir / name).write_bytes(src.read_bytes())

    expected = load_expected_sums()
    for filename, url in ZENODO_FILES.items():
        rel = f"raw/{filename}"
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        actual = sha256_bytes(data)
        wanted = expected.get(rel)
        if wanted is None:
            return fail(f"no expected checksum for {rel}")
        if actual != wanted:
            return fail(
                f"downloaded {rel} hash mismatch: expected {wanted}, got {actual}"
            )
        (raw / filename).write_bytes(data)
        print(f"fetched {rel} sha256={actual}")

    # Evidence snapshots are committed; copy if present for offline validate.
    for name in (
        "zenodo_record_13378442.json",
        "zenodo_landing_13378442.html",
        "cc_by_4_0_legalcode.html",
    ):
        src = RAW_DIR / name
        if src.is_file():
            (raw / name).write_bytes(src.read_bytes())

    return validate_package(workdir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true", help="Validate package in-repo")
    parser.add_argument("--fetch", action="store_true", help="Re-download Zenodo bytes and verify")
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="Directory for --fetch reproduction (default: package dir itself)",
    )
    args = parser.parse_args(argv)

    if not args.validate and not args.fetch:
        args.validate = True

    if args.fetch:
        workdir = args.workdir or PACKAGE_DIR
        return fetch_into(workdir)

    return validate_package(PACKAGE_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
