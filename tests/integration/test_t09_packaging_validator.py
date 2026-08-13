"""Regression tests for T09's offline Wave C packaging validator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.eval.validate_t09_packaging import validate


def manifest(root: Path, entries: list[dict[str, str]], count: int | None = None) -> Path:
    """Create an isolated manifest for one controlled package test."""
    target = root / "manifest.json"
    target.write_text(json.dumps({"expected_file_count": count or len(entries), "files": entries}), encoding="utf-8")
    return target


def entry(path: Path, relative: str = "artifact.txt") -> dict[str, str]:
    """Build a valid inventory entry from raw bytes in the temporary package."""
    return {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "provenance": "test"}


def test_valid_inventory_passes(tmp_path: Path) -> None:
    """A matching count, provenance and raw checksum passes."""
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("verified", encoding="utf-8")
    assert validate(manifest(tmp_path, [entry(artifact)]), tmp_path)["passed"] is True


def test_count_missing_duplicate_path_and_drift_fail(tmp_path: Path) -> None:
    """Count, missing file, duplicate path and checksum drift fail closed."""
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("verified", encoding="utf-8")
    good = entry(artifact)
    bad_hash = dict(good, sha256="0" * 64)
    report = validate(manifest(tmp_path, [good, good, bad_hash], count=2), tmp_path)
    assert {"file_count", "entry:duplicate", "entry:sha256_drift"} <= set(report["errors"])


def test_path_escape_and_missing_provenance_fail(tmp_path: Path) -> None:
    """Escaping paths and absent provenance cannot enter the package."""
    report = validate(
        manifest(tmp_path, [{"path": "../outside", "sha256": "0" * 64, "provenance": ""}]),
        tmp_path,
    )
    assert {"entry:path", "entry:provenance"} <= set(report["errors"])
