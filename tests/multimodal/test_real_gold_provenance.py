"""Tests for T06 provenance-locked real gold package remediation."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.multimodal.gold_package import (
    DEFAULT_GOLD_ROOT,
    chart_point_within_tolerance,
    iter_gold_labels,
    load_chart_artifact,
    load_manifest,
    load_resistance_table_artifact,
    relative_error,
)

PACKAGE = DEFAULT_GOLD_ROOT
SCRIPT = PACKAGE / "fetch_and_verify.py"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_manifest_schema_and_non_synthetic_flags() -> None:
    manifest = load_manifest(PACKAGE)
    assert manifest["gold_set_id"] == "zenodo_fish_spoilage_impedance"
    assert manifest["doi_or_accession"] == "10.5281/zenodo.13378442"
    assert manifest["is_synthetic"] is False
    assert manifest["is_provisional"] is False
    assert manifest["is_fixture"] is False
    assert "manifest_sha256" not in manifest
    assert set(manifest["modalities"]) == {"table", "chart"}
    assert manifest["controlled_artifact_applicable"] is False
    assert manifest["controlled_artifact_path"] == "NOT_APPLICABLE"
    assert "public" in manifest["controlled_artifact_na_reason"].lower()
    assert "mkdtemp" in manifest["reproducible_fetch_command"]
    assert "<EMPTY_TEMP_DIR>" not in manifest["reproducible_fetch_command"]
    assert "<empty-temp>" not in manifest["reproducible_fetch_command"]
    assert "PENDING_CONFIRMATION" not in json.dumps(manifest)


def test_sha256sums_match_worktree_bytes() -> None:
    lines = (PACKAGE / "SHA256SUMS").read_bytes().decode("utf-8").splitlines()
    checked = 0
    prev = ""
    for line in lines:
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        assert rel >= prev
        prev = rel
        assert _sha256(PACKAGE / rel) == digest
        checked += 1
    assert checked == 18


def test_zenodo_csv_bytes_contain_crlf_source_newlines() -> None:
    csv_bytes = (PACKAGE / "raw" / "fishtrial_resistance.csv").read_bytes()
    assert b"\r\n" in csv_bytes
    assert _sha256(PACKAGE / "raw" / "fishtrial_resistance.csv") == (
        "86b01101eb00e72ab67413742adeb0fb2396cbb3bfb00e93909e7446b560f919"
    )


def test_two_real_modalities_and_labels() -> None:
    assert (PACKAGE / "raw" / "Picture1.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    labels = list(iter_gold_labels(PACKAGE))
    assert len(labels) == 100
    assert {"table", "chart"} <= {x["modality"] for x in labels}


def test_contract_loader_accepts_real_gold_artifacts() -> None:
    table = load_resistance_table_artifact(PACKAGE)
    chart = load_chart_artifact(PACKAGE)
    assert table.modality == "table"
    assert chart.modality == "chart"


def test_chart_nonzero_relative_policy() -> None:
    gold = 1000.0
    assert chart_point_within_tolerance(1000.0, gold) is True
    assert chart_point_within_tolerance(1050.0, gold) is True  # exactly 5%
    assert chart_point_within_tolerance(1050.1, gold) is False
    assert relative_error(-1050.0, -1000.0) == pytest.approx(0.05)
    assert chart_point_within_tolerance(-1050.0, -1000.0) is True
    with pytest.raises(ValueError):
        relative_error(1.0, 0.0)


def test_chart_zero_gold_absolute_policy() -> None:
    assert chart_point_within_tolerance(0.0, 0.0, absolute_tolerance=0.0) is True
    assert chart_point_within_tolerance(0.0, 0.0, absolute_tolerance=1e-9) is True
    assert chart_point_within_tolerance(1e-12, 0.0, absolute_tolerance=0.0) is False
    with pytest.raises(ValueError):
        chart_point_within_tolerance(0.0, 0.0, absolute_tolerance=None)
    with pytest.raises(ValueError):
        chart_point_within_tolerance(0.0, 0.0, absolute_tolerance=float("nan"))
    with pytest.raises(ValueError):
        chart_point_within_tolerance(0.0, 0.0, absolute_tolerance=-1.0)
    # near-zero nonzero still uses relative path
    tiny = 1e-12
    assert chart_point_within_tolerance(tiny * 1.04, tiny) is True
    assert chart_point_within_tolerance(tiny * 1.06, tiny) is False


def test_loader_rejects_when_manifest_marked_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    real = load_manifest(PACKAGE)

    def _fake_load(_package_dir=None):
        tainted = dict(real)
        tainted["is_synthetic"] = True
        return tainted

    monkeypatch.setattr("app.multimodal.gold_package.load_manifest", _fake_load)
    with pytest.raises(ValueError, match="synthetic"):
        load_resistance_table_artifact(PACKAGE)


def test_validate_exit_zero_and_clean() -> None:
    before = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--validate"],
        check=False,
        capture_output=True,
        text=True,
    )
    after = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout
    assert before == after


def test_validate_fails_on_raw_byte_change(tmp_path: Path) -> None:
    work = tmp_path / "pkg"
    shutil.copytree(PACKAGE, work)
    target = work / "raw" / "fishtrial_resistance.csv"
    target.write_bytes(target.read_bytes() + b"X")
    proc = subprocess.run(
        [sys.executable, "-B", str(work / "fetch_and_verify.py"), "--validate"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "FAIL" in proc.stderr


def test_validate_fails_on_derived_newline_change(tmp_path: Path) -> None:
    work = tmp_path / "pkg"
    shutil.copytree(PACKAGE, work)
    path = work / "manifest.json"
    data = path.read_bytes().replace(b"\n", b"\r\n")
    path.write_bytes(data)
    proc = subprocess.run(
        [sys.executable, "-B", str(work / "fetch_and_verify.py"), "--validate"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0


def test_validate_fails_on_duplicate_or_missing_inventory(tmp_path: Path) -> None:
    work = tmp_path / "pkg"
    shutil.copytree(PACKAGE, work)
    sums = (work / "SHA256SUMS").read_bytes().decode("utf-8").splitlines()
    # duplicate first path
    first = sums[0]
    (work / "SHA256SUMS").write_bytes(("\n".join(sums + [first]) + "\n").encode("utf-8"))
    proc = subprocess.run(
        [sys.executable, "-B", str(work / "fetch_and_verify.py"), "--validate"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0


def test_domain_mapping_chart_policy() -> None:
    mapping = json.loads((PACKAGE / "domain_mapping.json").read_bytes().decode("utf-8"))
    policy = mapping["chart_error_policy"]
    assert policy["eps_used"] is False
    assert policy["nonzero_relative_tolerance"] == 0.05
    assert policy["zero_absolute_tolerance"] == 0.0
