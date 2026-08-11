"""Offline Wave C status, pause, and 125-package tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from app.batch.delivery_index import QuestionDeliveryRecord, build_delivery_index
from app.batch.output_validation import ArtifactFileRecord, compute_file_sha256
from app.batch.wave_c_hardening import (
    EXPECTED_QUESTION_IDS,
    WAVE_C_SAMPLE_VERSION,
    build_manual_sample_plan,
    inspect_wave_c_status,
    is_pause_requested,
    release_pause,
    request_pause,
    validate_wave_c_package,
    write_validation_receipts,
)
from app.contracts.batch import REQUIRED_ARTIFACTS


BATCH_ID = "T07-WC-125"
CODE_SHA = "a" * 40


def _canonical_json(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write(path: Path, value: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value, encoding="utf-8", newline="\n")


def _audit_json(question_id: str, *, valid: bool = True) -> str:
    request_hash = hashlib.sha256(question_id.encode("utf-8")).hexdigest()
    payload = {
        "provider": "bailian",
        "model": "qwen3.6-flash",
        "route_tier": "fast",
        "request_timestamp": "2026-08-12T00:00:00+00:00",
        "sanitized_request_id": "req_sha256:" + request_hash,
        "static_prompt_version": "wave-c-frozen-prompt-v1",
        "static_prompt_hash": "b" * 64,
        "dynamic_prompt_hash": "c" * 64,
        "input_tokens": 2,
        "output_tokens": 1,
        "total_tokens": 3 if valid else 4,
        "estimated_cost_usd": None,
        "settled_cost_usd": None,
        "retry_attempt": 1,
        "fallback": False,
        "price_snapshot_version": None,
        "cost_accounting_mode": "token_only",
    }
    return json.dumps(payload, sort_keys=True)


def _artifact_contents(question_id: str, *, audit_valid: bool) -> dict[str, bytes | str]:
    return {
        "report.pdf": b"%PDF-1.7\n% offline Wave C fixture\n",
        "report.md": f"# {question_id}\n",
        "result.json": json.dumps({"question_id": question_id}),
        "evidence_cards.json": "[]",
        "agent_trace.json": json.dumps({"question_id": question_id}),
        "llm_call_audit.json": _audit_json(question_id, valid=audit_valid),
    }


def _build_package(
    root: Path,
    *,
    invalid_audit_question: str | None = None,
) -> Path:
    records: list[QuestionDeliveryRecord] = []
    for question_id in EXPECTED_QUESTION_IDS:
        question_root = root / question_id
        artifacts: list[ArtifactFileRecord] = []
        contents = _artifact_contents(
            question_id,
            audit_valid=question_id != invalid_audit_question,
        )
        for name in sorted(contents):
            target = question_root / name
            _write(target, contents[name])
            artifacts.append(
                ArtifactFileRecord(
                    name=name,
                    path=PurePosixPath(question_id, name).as_posix(),
                    sha256=compute_file_sha256(target),
                    size_bytes=target.stat().st_size,
                )
            )
        record = QuestionDeliveryRecord(
            batch_id=BATCH_ID,
            question_id=question_id,
            status="completed",
            source_hash="d" * 64,
            input_hash=hashlib.sha256(question_id.encode("utf-8")).hexdigest(),
            output_contract_version="t07.wave-c-output.v1",
            route_id="t07-wave-c-route-v1",
            provider="bailian",
            model="qwen3.6-flash",
            model_version="qwen-stack-20260803-v1",
            prompt_version="wave-c-frozen-prompt-v1",
            prompt_hash="b" * 64,
            schema_version="t07.batch.v2",
            artifacts=tuple(artifacts),
            input_tokens=2,
            output_tokens=1,
            tokens_used=3,
            duration_seconds=1.0,
            attempts=1,
            failure_code=None,
            validation_status="passed",
            validation_error_codes=(),
            result_kind="actual",
            actual=True,
            mock=False,
            synthetic=False,
            completed=True,
            budget_policy_version="t07.budget.token-only.v2",
            budget_mode="token_only",
            cost_accounting_required=False,
            price_snapshot_required=False,
            captain_waiver_reference="captain-option-b-approved-2026-08-07",
            estimated_cost_usd=None,
            settled_cost_usd=None,
        )
        records.append(record)

        artifact_payload = {
            "batch_id": BATCH_ID,
            "question_id": question_id,
            "output_contract_version": record.output_contract_version,
            "validation_status": "passed",
            "artifacts": [artifact.to_dict() for artifact in record.artifacts],
        }
        artifact_payload["manifest_sha256"] = hashlib.sha256(
            _canonical_json(artifact_payload)
        ).hexdigest()
        _write(
            question_root / "artifact_manifest.json",
            json.dumps(artifact_payload, sort_keys=True),
        )
        _write(
            question_root / "checkpoint.json",
            json.dumps(
                {
                    "batch_id": BATCH_ID,
                    "question_id": question_id,
                    "status": "completed",
                },
                sort_keys=True,
            ),
        )
        _write(
            question_root / "completion_decision.json",
            json.dumps(
                {"status": "completed", "completed": True, "error_codes": []},
                sort_keys=True,
            ),
        )

    index = build_delivery_index(BATCH_ID, records)
    _write(root / "delivery_index.json", index.to_json())
    _write(
        root / "manifest.json",
        json.dumps(
            {
                "manifest_version": "t07.wave-c-formal-manifest.v1",
                "code_sha": CODE_SHA,
                "question_order": list(EXPECTED_QUESTION_IDS),
                "selected_question_ids": list(EXPECTED_QUESTION_IDS),
                "execute": True,
                "mock": False,
                "fallback": False,
                "provider_calls": 125,
                "status": "completed",
                "questions": [
                    {
                        "question_id": question_id,
                        "status": "completed",
                        "completed": True,
                    }
                    for question_id in EXPECTED_QUESTION_IDS
                ],
            },
            sort_keys=True,
        ),
    )
    return root


def test_complete_125_package_passes_and_builds_exact_24_sample(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")

    validation = validate_wave_c_package(root, expected_code_sha=CODE_SHA)

    assert validation.passed
    assert validation.status.total == 125
    assert validation.status.completed == 125
    assert validation.status.provider_calls == 125
    assert validation.status.tokens_used == 375
    assert len(validation.sample_question_ids) == 24
    assert set(validation.sample_question_ids) <= set(EXPECTED_QUESTION_IDS)


def test_status_snapshot_exposes_pause_and_resumable_state(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    request_pause(root, requested_by="captain", reason="controlled stop")

    snapshot = inspect_wave_c_status(root)

    assert snapshot.paused is True
    assert snapshot.ready_for_finalization is False
    assert is_pause_requested(root) is True


def test_pause_request_is_idempotent_and_utf8_json(tmp_path: Path) -> None:
    root = tmp_path / "batch"
    root.mkdir()

    first = request_pause(root, requested_by="captain", reason="review")
    second = request_pause(root, requested_by="captain", reason="review")

    assert first == second
    assert not first.read_bytes().startswith(b"\xef\xbb\xbf")
    assert json.loads(first.read_text(encoding="utf-8"))["reason"] == "review"


def test_pause_release_requires_exact_hash_and_preserves_audit(tmp_path: Path) -> None:
    root = tmp_path / "batch"
    root.mkdir()
    marker = request_pause(root, requested_by="captain", reason="review")
    digest = hashlib.sha256(marker.read_bytes()).hexdigest()

    archive = release_pause(
        root,
        released_by="captain",
        expected_pause_sha256=digest,
    )

    assert is_pause_requested(root) is False
    payload = json.loads(archive.read_text(encoding="utf-8"))
    assert payload["pause_request_sha256"] == digest
    assert payload["pause_request"]["reason"] == "review"


def test_missing_physical_artifact_fails_closed(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    (root / "Q001" / "report.md").unlink()

    validation = validate_wave_c_package(root)

    assert not validation.passed
    assert "DELIVERY_ARTIFACT_MISSING" in {
        issue.error_code for issue in validation.issues
    }


def test_invalid_call_audit_is_rejected_without_provider(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch", invalid_audit_question="Q001")

    validation = validate_wave_c_package(root)

    assert not validation.passed
    assert "LLM_CALL_AUDIT_INVALID" in {
        issue.error_code for issue in validation.issues
    }


def test_manifest_cannot_claim_mock_or_partial_batch_as_final(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["mock"] = True
    manifest["questions"] = manifest["questions"][:-1]
    _write(manifest_path, json.dumps(manifest, sort_keys=True))

    validation = validate_wave_c_package(root)

    codes = {issue.error_code for issue in validation.issues}
    assert "WAVE_C_MANIFEST_NOT_FINAL" in codes
    assert "WAVE_C_MANIFEST_TOTAL_MISMATCH" in codes


def test_manual_sample_is_deterministic_and_not_human_signoff() -> None:
    first = build_manual_sample_plan(BATCH_ID)
    second = build_manual_sample_plan(BATCH_ID)

    assert first == second
    assert len(first) == 24


def test_receipts_remain_pending_human_review(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    validation = validate_wave_c_package(root)

    status, checksums, sample = write_validation_receipts(root, validation)

    assert status.is_file()
    assert checksums.read_text(encoding="utf-8").strip()
    sample_payload = json.loads(sample.read_text(encoding="utf-8"))
    assert sample_payload["schema_version"] == WAVE_C_SAMPLE_VERSION
    assert sample_payload["review_status"] == "pending_human_review"
    assert len(sample_payload["question_ids"]) == 24


def test_required_artifact_contract_is_preserved() -> None:
    assert set(REQUIRED_ARTIFACTS) == {
        "report.pdf",
        "report.md",
        "result.json",
        "evidence_cards.json",
        "agent_trace.json",
    }
