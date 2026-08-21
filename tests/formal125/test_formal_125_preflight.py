"""Formal 125 preflight tests: catalog, locks, authorization, dry-run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.formal125.authorization import blocked_actual_run_exit, require_actual_authorization
from app.formal125.catalog import (
    AUTHORITATIVE_SOURCE_SHA256,
    build_catalog_lock,
    build_domain_map,
    build_formal_12_manifest,
    build_formal_5_manifest,
    build_manual_review_24_manifest,
)
from app.formal125.dry_run import run_formal_125_dry_run
from app.formal125.hashes import sha256_file
from app.formal125.preflight import (
    build_model_lock,
    build_output_contract,
    build_prompt_lock,
    install_source_catalog,
    locate_source_catalog,
)
from app.formal125.catalog import write_production_source


def test_catalog_is_exactly_125_contiguous_unique() -> None:
    source = locate_source_catalog()
    assert sha256_file(source) == AUTHORITATIVE_SOURCE_SHA256
    catalog = build_catalog_lock(source)
    assert catalog["question_count"] == 125
    ids = [item["question_id"] for item in catalog["questions"]]
    assert ids == [f"Q{i:03d}" for i in range(1, 126)]
    assert len(set(ids)) == 125
    assert all(item["evidence_eligible"] is False for item in catalog["questions"])
    assert all(item["original_title"] for item in catalog["questions"])
    q028 = next(item for item in catalog["questions"] if item["question_id"] == "Q028")
    assert "cancer" in q028["original_title"].lower()


def test_domain_map_covers_125_without_duplicates() -> None:
    catalog = build_catalog_lock(locate_source_catalog())
    domain_map = build_domain_map(catalog)
    assert domain_map["domain_count"] == 12
    assigned = []
    for domain in domain_map["domains"]:
        assigned.extend(domain["question_ids"])
    assert len(assigned) == 125
    assert len(set(assigned)) == 125
    assert domain_map["q028_domain_id"] == "biology"


def test_frozen_selections() -> None:
    catalog = build_catalog_lock(locate_source_catalog())
    five = build_formal_5_manifest(catalog)
    twelve = build_formal_12_manifest(catalog)
    review = build_manual_review_24_manifest(catalog)
    assert five["question_ids"] == ["Q001", "Q028", "Q050", "Q075", "Q107"]
    assert "Q028" in five["question_ids"]
    assert len(twelve["question_ids"]) == 12
    assert len(set(twelve["question_ids"])) == 12
    assert "Q028" in review["question_ids"]
    assert review["count"] >= 24


def test_prompt_lock_has_no_case_leaks() -> None:
    lock = build_prompt_lock()
    assert lock["prompt_count"] >= 8
    assert lock["hardcoded_case_leak_count"] == 0
    assert lock["cross_question_prompt_leak_count"] == 0
    assert "Q028" not in json.dumps(lock["prompts"])


def test_output_contract_has_nine_required_files() -> None:
    contract = build_output_contract()
    assert contract["required_file_count_per_question"] == 9
    assert "result.md" in contract["required_files"]
    assert "provider_audit.json" in contract["required_files"]


def test_actual_run_without_authorization_is_blocked(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        require_actual_authorization(None)
    code = blocked_actual_run_exit(authorization_path=None)
    assert code != 0
    missing = tmp_path / "missing.json"
    code = blocked_actual_run_exit(authorization_path=missing)
    assert code != 0


def test_125_id_dry_run_isolates_failures_without_provider(tmp_path: Path) -> None:
    catalog = build_catalog_lock(locate_source_catalog())
    source = write_production_source(catalog, tmp_path / "questions.json")
    result = run_formal_125_dry_run(
        source_path=source,
        run_root=tmp_path / "run",
        batch_id="formal125-test",
        lock_hashes={
            "catalog_hash": catalog["catalog_sha256"],
            "model_lock_hash": "a" * 64,
            "prompt_lock_hash": "b" * 64,
            "schema_lock_hash": "c" * 64,
        },
    )
    assert result.job_count == 125
    assert result.unique_workspace_count == 125
    assert result.unique_context_count == 125
    assert result.provider_call_count == 0
    assert result.official_result_count == 0
    assert result.actual_execution is False
    assert result.resume_status == "PASS"
    assert result.status_counts["failed"] >= 3
    assert result.status_counts["blocked"] >= 1
    assert result.status_counts["dry_run_complete"] == 121
    assert not (tmp_path / "run" / "official_results").exists()


def test_model_lock_forbids_openrouter_and_mock() -> None:
    lock = build_model_lock()
    assert lock["provider"] == "bailian"
    assert lock["openrouter_fallback_allowed"] is False
    assert lock["mock_fallback_allowed"] is False
    assert "DASHSCOPE_API_KEY" == lock["variable_names"]["api_key"]
    dumped = json.dumps(lock)
    assert "sk-" not in dumped
    assert lock["api_key_present"] in {True, False}


def test_install_source_catalog_is_byte_stable(tmp_path: Path) -> None:
    copied = install_source_catalog(tmp_path / "questions_125.source.json")
    assert sha256_file(copied) == AUTHORITATIVE_SOURCE_SHA256
