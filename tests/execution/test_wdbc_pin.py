"""Frozen metadata contracts for the independently verified WDBC pin."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.contracts.execution import DatasetManifest
from app.execution.datasets import WDBC_DATASET_ID, get_default_dataset_registry


PIN_SHA256 = "d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a"
PIN_SIZE_BYTES = 124103
SYNTHETIC_FIXTURE_SHA256 = (
    "47317e26a56c9d2cbad7b2a318f70469b9dd47196365b9698a287a3ed486fae3"
)
SOURCE_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases/"
    "breast-cancer-wisconsin/wdbc.data"
)
ROOT = Path(__file__).resolve().parents[2]
SELECTION_MANIFEST = ROOT / "experiments" / "flagship" / "selection_manifest.json"
DATASET_MANIFEST = ROOT / "experiments" / "flagship" / "dataset_manifest.json"


def _definition() -> Any:
    return get_default_dataset_registry().get(WDBC_DATASET_ID)


def _strict_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    seen_duplicates: list[str] = []

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                seen_duplicates.append(key)
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant: {value}")

    loaded = json.loads(
        text,
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    assert not seen_duplicates
    assert isinstance(loaded, dict)
    return loaded, text


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {
            nested
            for item in value.values()
            for nested in _keys(item)
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _keys(item)}
    return set()


def test_T05_B_PINMETA_001_default_sha_is_verified_pin() -> None:
    assert _definition().expected_sha256 == PIN_SHA256


def test_T05_B_PINMETA_002_default_size_is_verified_pin() -> None:
    assert _definition().expected_size_bytes == PIN_SIZE_BYTES


def test_T05_B_PINMETA_003_real_pin_is_not_synthetic_fixture() -> None:
    assert _definition().expected_sha256 != SYNTHETIC_FIXTURE_SHA256


def test_T05_B_PINMETA_004_default_definition_is_pinned() -> None:
    assert _definition().is_pinned is True


def test_T05_B_PINMETA_005_provenance_matches_dataset_manifest() -> None:
    manifest, _text = _strict_json(DATASET_MANIFEST)
    definition = _definition()
    assert manifest["dataset_id"] == definition.dataset_id
    assert manifest["source"]["url"] == definition.source_url
    assert manifest["version"] == definition.version
    assert manifest["license"]["id"] == definition.license_id
    assert manifest["doi"] == definition.doi


def test_T05_B_PINMETA_006_selection_manifest_exists() -> None:
    assert SELECTION_MANIFEST.is_file()


def test_T05_B_PINMETA_007_selection_identity_and_hashes_are_frozen() -> None:
    manifest, _text = _strict_json(SELECTION_MANIFEST)
    assert manifest["question_id"] == "Q028"
    assert manifest["source_global_ordinal"] == 28
    assert manifest["source_domain"] == "Biology"
    assert manifest["source_domain_ordinal"] == 5
    assert manifest["source_page"] == 15
    assert manifest["source_catalog_sha256"] == (
        "b6712a3b53f9776d7f695ea67f810c30b7d97ee59c183009432870d3224cdebb"
    )
    assert manifest["question_text_sha256"] == (
        "c99f3abc1271b4bca5d6e9eff44fd9b36eded801404730c2e06ee0cdc4426ad8"
    )
    assert manifest["source_document_sha256"] == (
        "4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576"
    )
    assert manifest["catalog_redistributed"] is False
    assert manifest["original_question_text_embedded"] is False


def test_T05_B_PINMETA_008_selection_excludes_catalog_content_fields() -> None:
    manifest, _text = _strict_json(SELECTION_MANIFEST)
    forbidden = {
        "question",
        "original_question",
        "question_text",
        "booklet_excerpt",
        "catalog",
        "questions",
    }
    assert forbidden.isdisjoint(_keys(manifest))


def test_T05_B_PINMETA_009_original_question_is_not_embedded() -> None:
    manifest, _text = _strict_json(SELECTION_MANIFEST)
    assert manifest["original_question_text_embedded"] is False
    assert manifest["catalog_redistributed"] is False


def test_T05_B_PINMETA_010_selection_has_no_local_absolute_path() -> None:
    _manifest, text = _strict_json(SELECTION_MANIFEST)
    assert re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", text) is None
    assert "/Users/" not in text and "/home/" not in text


def test_T05_B_PINMETA_011_dataset_manifest_exists() -> None:
    assert DATASET_MANIFEST.is_file()


def test_T05_B_PINMETA_012_manifest_pin_matches_production() -> None:
    manifest, _text = _strict_json(DATASET_MANIFEST)
    definition = _definition()
    assert manifest["pin"]["sha256"] == definition.expected_sha256
    assert manifest["pin"]["size_bytes"] == definition.expected_size_bytes


def test_T05_B_PINMETA_013_schema_and_verification_evidence_is_complete() -> None:
    manifest, _text = _strict_json(DATASET_MANIFEST)
    schema = manifest["schema_validation"]
    pin = manifest["pin"]
    storage = manifest["storage_policy"]
    verification = manifest["verification"]
    assert schema["row_count"] == 569
    assert schema["column_count"] == 32
    assert schema["feature_count"] == 30
    assert schema["unique_id_count"] == 569
    assert set(schema["labels"]) == {"B", "M"}
    assert schema["missing_value_count"] == 0
    assert schema["duplicate_id_count"] == 0
    assert pin["verification_download_count"] == 2
    assert pin["independent_hash_match"] is True
    assert manifest["source"]["archive_detected"] is False
    assert storage["raw_data_committed"] is False
    assert storage["local_cache_path_embedded"] is False
    assert verification["formal_round1_executed"] is True
    assert verification["formal_round1_source_git_sha"] == (
        "18c86f1e1963b13cbed09356201d92f38a2a2880"
    )
    assert verification["formal_round1_offline_reproduction_match"] is True
    result_path = (
        DATASET_MANIFEST.parent / verification["formal_round1_result"]
    ).resolve()
    assert result_path == ROOT / "docs" / "modules" / "T05" / "round1" / (
        "execution_result.json"
    )
    assert result_path.is_file()


def test_T05_B_PINMETA_014_official_provenance_is_exact() -> None:
    manifest, _text = _strict_json(DATASET_MANIFEST)
    assert manifest["publisher"] == "UCI Machine Learning Repository"
    assert manifest["doi"] == "10.24432/C5DW2B"
    assert manifest["version"] == "1995-10-31"
    assert manifest["license"]["id"] == "CC-BY-4.0"
    assert manifest["license"]["url"].startswith("https://")


def test_T05_B_PINMETA_015_source_is_https_raw_file_not_archive() -> None:
    manifest, _text = _strict_json(DATASET_MANIFEST)
    source = manifest["source"]
    parsed = urlsplit(source["url"])
    assert source["url"] == SOURCE_URL
    assert parsed.scheme == "https"
    assert parsed.hostname == "archive.ics.uci.edu"
    assert parsed.path.endswith("/wdbc.data")
    assert not parsed.path.casefold().endswith(".zip")


def test_T05_B_PINMETA_016_manifest_excludes_sensitive_or_raw_material() -> None:
    _manifest, text = _strict_json(DATASET_MANIFEST)
    lowered = text.casefold()
    for forbidden in (
        "cache_root",
        "candidate_path",
        "staging_root",
        "cookie",
        "token",
        "proxy",
    ):
        assert forbidden not in lowered
    assert re.search(r"(?m)^\s*\d+,[BM],", text) is None
    assert re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", text) is None


def test_T05_B_PINMETA_017_execution_manifest_validates() -> None:
    manifest, _text = _strict_json(DATASET_MANIFEST)
    validated = DatasetManifest.model_validate(manifest["execution_contract_manifest"])
    assert validated.dataset_id == WDBC_DATASET_ID
    assert validated.sha256 == PIN_SHA256
    assert validated.size_bytes == PIN_SIZE_BYTES


def test_T05_B_PINMETA_018_git_tracks_no_external_source_material() -> None:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    tracked = {line.strip().casefold() for line in completed.stdout.splitlines()}
    forbidden_names = (
        "wdbc.data",
        "diagnostic.zip",
        "sjtu-booklet.pdf",
        "questions_125.json",
        "questions_125.csv",
    )
    assert not any(path.endswith(forbidden_names) for path in tracked)
    assert not any("candidate" in Path(path).name for path in tracked)


def test_T05_B_PINMETA_019_flagship_directory_contains_no_raw_data() -> None:
    directory = ROOT / "experiments" / "flagship"
    files = tuple(path for path in directory.rglob("*") if path.is_file()) if directory.exists() else ()
    assert all(path.suffix.casefold() == ".json" for path in files)
    assert all("wdbc" not in path.name.casefold() for path in files)


def test_T05_B_PINMETA_020_json_is_strict_stable_and_newline_terminated() -> None:
    for path in (SELECTION_MANIFEST, DATASET_MANIFEST):
        manifest, text = _strict_json(path)
        assert text.endswith("\n")
        assert not text.endswith("\n\n")
        assert text == json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
