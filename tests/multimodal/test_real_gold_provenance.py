"""Tests for T06 provenance-locked real gold package."""

from __future__ import annotations

import hashlib
import json
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_manifest_schema_and_non_synthetic_flags() -> None:
    manifest = load_manifest(PACKAGE)
    assert manifest["gold_set_id"] == "zenodo_fish_spoilage_impedance"
    assert manifest["task"] == "T06"
    assert manifest["doi_or_accession"] == "10.5281/zenodo.13378442"
    assert manifest["source_landing_uri"] == "https://zenodo.org/records/13378442"
    assert manifest["source_version"]
    assert "creativecommons.org/licenses/by/4.0" in manifest["license_uri"]
    assert manifest["license_name"]
    assert manifest["is_synthetic"] is False
    assert manifest["is_provisional"] is False
    assert manifest["is_fixture"] is False
    assert "not synthetic" in manifest["non_synthetic_assertion"].lower()
    assert set(manifest["modalities"]) == {"table", "chart"}


def test_license_and_source_evidence_files_exist() -> None:
    assert (PACKAGE / "license_evidence.md").is_file()
    assert (PACKAGE / "raw" / "zenodo_record_13378442.json").is_file()
    landing = (PACKAGE / "raw" / "zenodo_landing_13378442.html").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "cc-by-4.0" in landing.lower() or "creative commons attribution 4.0" in landing.lower()
    record = json.loads(
        (PACKAGE / "raw" / "zenodo_record_13378442.json").read_text(encoding="utf-8")
    )
    assert record["metadata"]["license"]["id"] == "cc-by-4.0"


def test_sha256sums_match_actual_bytes() -> None:
    lines = (PACKAGE / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    checked = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        digest, rel = line.split(None, 1)
        path = PACKAGE / rel
        assert path.is_file(), rel
        assert _sha256(path) == digest, rel
        checked += 1
    assert checked >= 8


def test_two_real_non_text_modalities_present() -> None:
    assert (PACKAGE / "raw" / "fishtrial_resistance.csv").is_file()
    png = (PACKAGE / "raw" / "Picture1.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_gold_labels_map_to_source_and_have_required_fields() -> None:
    labels = list(iter_gold_labels(PACKAGE))
    assert labels
    modalities = {item["modality"] for item in labels}
    assert "table" in modalities and "chart" in modalities
    for item in labels:
        assert item["evaluation_case_id"] == "T06-GOLD-FISH-IMPEDANCE-001"
        assert item["source_file_sha256"]
        assert item["unit"]
        assert item["validation_status"] == "passed"
        assert item["confidence"] >= 0.9
        assert item["label_source"]
        if item["modality"] == "chart":
            assert item["axes"]
            assert item["legend_series"]
            assert item["bbox"]["coordinate_system"]
            assert item["tolerance"]["type"] == "relative"
            assert item["tolerance"]["value"] == 0.05


def test_contract_loader_accepts_real_gold_artifacts() -> None:
    table = load_resistance_table_artifact(PACKAGE)
    chart = load_chart_artifact(PACKAGE)
    assert table.modality == "table"
    assert chart.modality == "chart"
    assert table.provenance.source_type == "csv"
    assert table.validation_status == "passed"
    assert chart.legend


def test_chart_tolerance_is_not_always_pass() -> None:
    gold = 1000.0
    assert chart_point_within_tolerance(1000.0, gold, 0.05) is True
    assert chart_point_within_tolerance(1049.0, gold, 0.05) is True
    assert chart_point_within_tolerance(1060.0, gold, 0.05) is False
    assert relative_error(1060.0, gold) == pytest.approx(0.06)


def test_loader_rejects_when_manifest_marked_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    real = load_manifest(PACKAGE)

    def _fake_load(_package_dir=None):
        tainted = dict(real)
        tainted["is_synthetic"] = True
        return tainted

    monkeypatch.setattr(
        "app.multimodal.gold_package.load_manifest",
        _fake_load,
    )
    with pytest.raises(ValueError, match="synthetic"):
        load_resistance_table_artifact(PACKAGE)


def test_fetch_and_verify_script_validate_exit_zero() -> None:
    script = PACKAGE / "fetch_and_verify.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--validate"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


def test_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    import shutil

    work = tmp_path / "pkg"
    shutil.copytree(PACKAGE, work)
    target = work / "raw" / "fishtrial_resistance.csv"
    target.write_bytes(target.read_bytes() + b"\n#corrupt\n")
    proc = subprocess.run(
        [sys.executable, str(work / "fetch_and_verify.py"), "--validate"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "FAIL" in proc.stderr or "FAIL" in proc.stdout


def test_domain_mapping_present() -> None:
    mapping = json.loads((PACKAGE / "domain_mapping.json").read_text(encoding="utf-8"))
    assert mapping["evaluation_cases"][0]["evaluation_case_id"] == (
        "T06-GOLD-FISH-IMPEDANCE-001"
    )
