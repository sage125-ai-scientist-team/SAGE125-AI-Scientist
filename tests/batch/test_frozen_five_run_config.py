"""Frozen production-source and five-question mapping tests for T07-WB5."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.batch.errors import BatchRunnerError
from app.batch.five_run_preflight import (
    compute_canonical_question_input_hash,
    load_and_map_authoritative_questions,
    load_frozen_run_config,
    verify_authoritative_sources,
    verify_frozen_code_files,
    verify_frozen_question_text,
)


QUESTION_IDS = ("Q001", "Q028", "Q050", "Q075", "Q107")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_fixture_repo(root: Path) -> tuple[list[dict], dict]:
    pdf = b"%PDF-1.7\ntrusted-test-booklet"
    pdf_path = root / "data/raw/sjtu-booklet.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(pdf)

    questions = [
        {
            "id": f"Q{index:03d}",
            "domain": f"domain-{index % 5}",
            "question": f"Authoritative question {index}?",
        }
        for index in range(1, 126)
    ]
    source_bytes = json.dumps(
        questions,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    source_path = root / "data/processed/questions_125.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(source_bytes)

    prompt = b"PROMPT = 'frozen'\r\n"
    normalized_prompt = b"PROMPT = 'frozen'\n"
    prompt_path = root / "app/agents/prompts.py"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_bytes(prompt)

    schemas = []
    for index in range(4):
        payload = f"SCHEMA_{index} = {index}\n".encode()
        path = root / f"schemas/schema_{index}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        schemas.append(
            {
                "name": f"schema-{index}",
                "path": path.relative_to(root).as_posix(),
                "size": len(payload),
                "sha256": _sha(payload),
            }
        )

    selected = {record["id"]: record for record in questions}
    config = {
        "freeze_id": "T07-WB5-TEST-v1",
        "frozen_at": "2026-08-03T00:00:00+00:00",
        "source_kind": "production",
        "authoritative_pdf": {
            "path": pdf_path.relative_to(root).as_posix(),
            "size": len(pdf),
            "sha256": _sha(pdf),
        },
        "production_question_source": {
            "path": source_path.relative_to(root).as_posix(),
            "size": len(source_bytes),
            "sha256": _sha(source_bytes),
        },
        "question_id_field": "id",
        "questions": [
            {
                "question_id": question_id,
                "domain": selected[question_id]["domain"],
                "question": selected[question_id]["question"],
                "canonical_input_hash": compute_canonical_question_input_hash(
                    selected[question_id]
                ),
                "mapping_status": "verified",
            }
            for question_id in QUESTION_IDS
        ],
        "provider": {
            "name": "bailian",
            "route_id": "test-route",
            "models": {"strong": "qwen3.7-max"},
            "model_version": "test-model-v1",
            "configuration_environment_variables": ["DASHSCOPE_API_KEY"],
        },
        "prompt": {
            "version": "test-prompt-v1",
            "path": prompt_path.relative_to(root).as_posix(),
            "size": None,
            "hash_mode": "utf8_lf_normalized_text_sha256",
            "sha256": _sha(normalized_prompt),
        },
        "batch_schema": "t07.batch.v1",
        "checkpoint_schema": "t07.checkpoint.v1",
        "schema_files": schemas,
        "approved_t01_commit": "a" * 40,
        "t01_public_interface": "app.evidence.precheck_bundle_for_validation",
        "t03_public_interfaces": [
            "app.contracts.validation.ValidationContext",
            "app.workflow.quality_gates.run_all_quality_gates",
        ],
        "budgets": {
            "per_question": {
                "token_limit": 200000,
                "cost_limit_usd": "3.00",
            },
            "batch": {
                "token_limit": 1000000,
                "cost_limit_usd": "15.00",
            },
            "max_output_tokens_per_call": 8192,
            "exhausted_error_code": "BUDGET_EXHAUSTED",
        },
        "price_snapshot": None,
    }
    return questions, config


def _write_config(root: Path, payload: dict) -> Path:
    path = root / "freeze.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_all_frozen_hashes_and_five_id_mappings_pass(tmp_path: Path) -> None:
    _, payload = _write_fixture_repo(tmp_path)
    config = load_frozen_run_config(_write_config(tmp_path, payload))

    provenance = verify_authoritative_sources(config, tmp_path)
    mapped = load_and_map_authoritative_questions(config, tmp_path)

    assert provenance.passed
    assert verify_frozen_question_text(config, mapped) == ()
    assert verify_frozen_code_files(config, tmp_path) == ()
    assert tuple(mapped) == QUESTION_IDS


def test_prompt_hash_normalizes_crlf_and_cr_to_lf(tmp_path: Path) -> None:
    _, payload = _write_fixture_repo(tmp_path)
    prompt_path = tmp_path / payload["prompt"]["path"]
    config = load_frozen_run_config(_write_config(tmp_path, payload))

    assert verify_frozen_code_files(config, tmp_path) == ()

    prompt_path.write_bytes(b"PROMPT = 'frozen'\r")

    assert verify_frozen_code_files(config, tmp_path) == ()


@pytest.mark.parametrize("field", ["size", "sha256"])
def test_any_authoritative_size_or_hash_change_fails(
    tmp_path: Path,
    field: str,
) -> None:
    _, payload = _write_fixture_repo(tmp_path)
    payload["authoritative_pdf"][field] = (
        payload["authoritative_pdf"][field] + 1
        if field == "size"
        else "f" * 64
    )
    config = load_frozen_run_config(_write_config(tmp_path, payload))

    result = verify_authoritative_sources(config, tmp_path)

    assert not result.passed
    assert f"SOURCE_{field.upper()}_MISMATCH" in result.error_codes


def test_synthetic_source_is_rejected_without_fallback(tmp_path: Path) -> None:
    _, payload = _write_fixture_repo(tmp_path)
    payload["source_kind"] = "synthetic"

    with pytest.raises(BatchRunnerError) as captured:
        load_frozen_run_config(_write_config(tmp_path, payload))

    assert captured.value.error_code == "SYNTHETIC_SOURCE_REJECTED"


@pytest.mark.parametrize("field", ["domain", "question"])
def test_frozen_question_or_domain_change_fails(
    tmp_path: Path,
    field: str,
) -> None:
    _, payload = _write_fixture_repo(tmp_path)
    config = load_frozen_run_config(_write_config(tmp_path, payload))
    mapped = load_and_map_authoritative_questions(config, tmp_path)
    forged = dict(mapped)
    forged["Q028"] = {**forged["Q028"], field: "changed"}

    issues = verify_frozen_question_text(config, forged)

    assert "FROZEN_QUESTION_MISMATCH" in {issue.code for issue in issues}


def test_id_mapping_uses_record_id_not_array_position(tmp_path: Path) -> None:
    questions, payload = _write_fixture_repo(tmp_path)
    source = tmp_path / payload["production_question_source"]["path"]
    forged = deepcopy(questions)
    forged[0]["id"] = "Q028"
    source_bytes = json.dumps(
        forged,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    source.write_bytes(source_bytes)
    payload["production_question_source"].update(
        size=len(source_bytes),
        sha256=_sha(source_bytes),
    )
    config = load_frozen_run_config(_write_config(tmp_path, payload))

    with pytest.raises(BatchRunnerError) as captured:
        load_and_map_authoritative_questions(config, tmp_path)

    assert captured.value.error_code == "QUESTION_ID_DUPLICATE"


def test_unverified_null_mapping_is_parseable_but_fails_closed(
    tmp_path: Path,
) -> None:
    _, payload = _write_fixture_repo(tmp_path)
    payload["questions"][0].update(
        domain=None,
        question=None,
        canonical_input_hash=None,
        mapping_status="not_evaluated_authoritative_source_missing",
    )
    config = load_frozen_run_config(_write_config(tmp_path, payload))
    mapped = load_and_map_authoritative_questions(config, tmp_path)

    issues = verify_frozen_question_text(config, mapped)

    assert "FROZEN_QUESTION_NOT_EVALUATED" in {issue.code for issue in issues}
