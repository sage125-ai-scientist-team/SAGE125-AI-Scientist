"""Offline Wave C status, pause, and 125-package tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path, PurePosixPath

import pytest

from app.batch.delivery_index import (
    DeliveryIndex,
    QuestionDeliveryRecord,
    build_delivery_index,
)
from app.batch.output_validation import ArtifactFileRecord, compute_file_sha256
from app.batch.wave_c_hardening import (
    EXPECTED_QUESTION_IDS,
    TRUSTED_RECEIPT_ARTIFACTS,
    WAVE_C_SAMPLE_VERSION,
    WAVE_C_TRUSTED_RECEIPTS_VERSION,
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


def _valid_pdf(question_id: str) -> bytes:
    unique = hashlib.sha256(question_id.encode("utf-8")).hexdigest()
    return (
        "%PDF-1.7\n"
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R >> endobj\n"
        f"4 0 obj << /Length 90 >> stream\nBT /F1 12 Tf ({question_id} {unique}) "
        "Tj ET\nendstream endobj\n"
        "xref\n0 5\n0000000000 65535 f \n"
        "trailer << /Root 1 0 R /Size 5 >>\nstartxref\n128\n%%EOF\n"
    ).encode("ascii")


def _artifact_contents(
    question_id: str,
    *,
    audit_valid: bool,
    credible: bool,
) -> dict[str, bytes | str]:
    if not credible:
        return {
            "report.pdf": b"%PDF-1.7\n% offline Wave C fixture\n",
            "report.md": f"# {question_id}\n",
            "result.json": json.dumps({"question_id": question_id}),
            "evidence_cards.json": "[]",
            "agent_trace.json": json.dumps({"question_id": question_id}),
            "llm_call_audit.json": _audit_json(question_id, valid=audit_valid),
        }
    unique = hashlib.sha256(question_id.encode("utf-8")).hexdigest()
    evidence_id = f"EV-{unique[:16]}"
    question_text = f"Authoritative question {question_id} token {unique}"
    quote = f"Verified passage {unique} establishes evidence for {question_id}."
    card = {
        "id": evidence_id,
        "evidence_id": evidence_id,
        "batch_id": BATCH_ID,
        "question_id": question_id,
        "run_id": f"run-{question_id}",
        "version_id": f"run-{question_id}",
        "source_id": f"paper-{question_id}",
        "source_type": "paper",
        "title": f"Source {unique[:20]}",
        "quoted_text": quote,
        "locator": {"document": f"paper-{question_id}", "page": 1},
        "content_hash": "sha256:" + hashlib.sha256(quote.encode()).hexdigest(),
        "source_content_hash": hashlib.sha256(
            f"source-{question_id}".encode()
        ).hexdigest(),
        "verification_status": "pending",
    }
    fields = {
        "Title": f"Study {unique[:20]}",
        "Abstract": f"Finding {unique[20:52]}",
    }
    plan = {
        "question_id": question_id,
        "input_question": question_text,
        "actual_execution": True,
        "generated_hypotheses": [
            {
                "hypothesis": f"Mechanism {unique[12:60]}",
                "supporting_evidence_ids": [evidence_id],
                "contradicted_by_evidence_ids": [],
            }
        ],
        "reference_ids": [evidence_id],
        "references": [card],
    }
    return {
        "report.pdf": _valid_pdf(question_id),
        "report.md": f"# {fields['Title']}\n\n{fields['Abstract']}\n",
        "result.json": json.dumps(
            {
                "batch_id": BATCH_ID,
                "question_id": question_id,
                "source_hash": "d" * 64,
                "input_hash": hashlib.sha256(question_id.encode()).hexdigest(),
                "fields": fields,
                "research_plan": plan,
            }
        ),
        "evidence_cards.json": json.dumps([card]),
        "agent_trace.json": json.dumps(
            {"batch_id": BATCH_ID, "question_id": question_id}
        ),
        "llm_call_audit.json": _audit_json(question_id, valid=audit_valid),
    }


def _build_package(
    root: Path,
    *,
    invalid_audit_question: str | None = None,
    credible: bool = True,
) -> Path:
    records: list[QuestionDeliveryRecord] = []
    for question_id in EXPECTED_QUESTION_IDS:
        question_root = root / question_id
        artifacts: list[ArtifactFileRecord] = []
        contents = _artifact_contents(
            question_id,
            audit_valid=question_id != invalid_audit_question,
            credible=credible,
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
                {
                    "status": "completed",
                    "completed": True,
                    "conditions": {
                        "12_t01_evidence_precheck": True,
                        "13_t03_quality_gates": True,
                    },
                    "error_codes": [],
                    "issues": [],
                },
                sort_keys=True,
            ),
        )
        _write(
            question_root / "quality_gate_results.json",
            json.dumps(
                [
                    {
                        "schema_version": 1,
                        "gate_id": "t01-evidence-precheck",
                        "passed": True,
                        "severity": "P3",
                        "findings": [],
                        "errors": [],
                        "warnings": [],
                        "score": 1.0,
                    },
                    {
                        "schema_version": 1,
                        "gate_id": "t03-quality-gates",
                        "passed": True,
                        "severity": "P3",
                        "findings": [],
                        "errors": [],
                        "warnings": [],
                        "score": 1.0,
                    },
                ],
                sort_keys=True,
            ),
        )
        _write(question_root / "validation_report.json", "{}")

    index = build_delivery_index(BATCH_ID, records)
    _write(root / "delivery_index.json", index.to_json())
    _write(
        root / "manifest.json",
        json.dumps(
            {
                "manifest_version": "t07.wave-c-formal-manifest.v1",
                "freeze_id": BATCH_ID,
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


def _write_trusted_receipts(
    root: Path,
    receipt_root: Path,
) -> tuple[Path, str]:
    index = DeliveryIndex.from_json(
        (root / "delivery_index.json").read_text(encoding="utf-8")
    )
    questions = []
    for record in index.records:
        question_root = root / record.question_id
        result = json.loads(
            (question_root / "result.json").read_text(encoding="utf-8")
        )
        question_text = result.get("research_plan", {}).get("input_question", "")
        questions.append(
            {
                "question_id": record.question_id,
                "source_hash": record.source_hash,
                "input_hash": record.input_hash,
                "question_text_sha256": hashlib.sha256(
                    question_text.encode("utf-8")
                ).hexdigest(),
                "artifact_sha256": {
                    name: compute_file_sha256(question_root / name)
                    for name in sorted(TRUSTED_RECEIPT_ARTIFACTS)
                },
            }
        )
    payload = {
        "schema_version": WAVE_C_TRUSTED_RECEIPTS_VERSION,
        "batch_id": index.batch_id,
        "code_sha": CODE_SHA,
        "manifest_sha256": compute_file_sha256(root / "manifest.json"),
        "delivery_index_sha256": compute_file_sha256(
            root / "delivery_index.json"
        ),
        "questions": questions,
    }
    path = receipt_root / "trusted_wave_c_receipts.json"
    _write(path, json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return path, compute_file_sha256(path)


def _rewrite_indexed_json_artifact(
    root: Path,
    question_id: str,
    name: str,
    payload: object,
) -> None:
    target = root / question_id / name
    _write(target, json.dumps(payload, ensure_ascii=False, sort_keys=True))
    index_path = root / "delivery_index.json"
    index = DeliveryIndex.from_json(index_path.read_text(encoding="utf-8"))
    records = []
    for record in index.records:
        if record.question_id != question_id:
            records.append(record)
            continue
        artifacts = tuple(
            replace(
                artifact,
                sha256=compute_file_sha256(target),
                size_bytes=target.stat().st_size,
            )
            if artifact.name == name
            else artifact
            for artifact in record.artifacts
        )
        records.append(replace(record, artifacts=artifacts))
    rebuilt = build_delivery_index(index.batch_id, records)
    _write(index_path, rebuilt.to_json())

    record = next(item for item in rebuilt.records if item.question_id == question_id)
    artifact_path = root / question_id / "artifact_manifest.json"
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact_payload["artifacts"] = [
        artifact.to_dict() for artifact in record.artifacts
    ]
    digest_payload = {
        "batch_id": artifact_payload.get("batch_id"),
        "question_id": artifact_payload.get("question_id"),
        "output_contract_version": artifact_payload.get(
            "output_contract_version"
        ),
        "validation_status": artifact_payload.get("validation_status"),
        "artifacts": artifact_payload.get("artifacts"),
    }
    artifact_payload["manifest_sha256"] = hashlib.sha256(
        _canonical_json(digest_payload)
    ).hexdigest()
    _write(artifact_path, json.dumps(artifact_payload, sort_keys=True))


def _validate_with_trust(root: Path, trusted_root: Path):
    path, digest = _write_trusted_receipts(root, trusted_root)
    return validate_wave_c_package(
        root,
        expected_code_sha=CODE_SHA,
        trusted_receipts_path=path,
        expected_trusted_receipts_sha256=digest,
    )


def test_complete_125_package_passes_and_builds_exact_24_sample(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    trusted_path, trusted_sha256 = _write_trusted_receipts(
        root,
        tmp_path / "trusted",
    )

    validation = validate_wave_c_package(
        root,
        expected_code_sha=CODE_SHA,
        trusted_receipts_path=trusted_path,
        expected_trusted_receipts_sha256=trusted_sha256,
    )

    assert validation.passed
    assert validation.trusted_receipts_verified is True
    assert validation.trusted_receipts_sha256 == trusted_sha256
    assert validation.status.total == 125
    assert validation.status.completed == 125
    assert validation.status.provider_calls == 125
    assert validation.status.tokens_used == 375
    assert len(validation.sample_question_ids) == 24
    assert set(validation.sample_question_ids) <= set(EXPECTED_QUESTION_IDS)


def test_self_claimed_actual_shell_package_fails_closed(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch", credible=False)
    trusted_path, trusted_sha256 = _write_trusted_receipts(
        root,
        tmp_path / "trusted",
    )

    validation = validate_wave_c_package(
        root,
        expected_code_sha=CODE_SHA,
        trusted_receipts_path=trusted_path,
        expected_trusted_receipts_sha256=trusted_sha256,
    )

    assert not validation.passed
    codes = {issue.error_code for issue in validation.issues}
    assert "WAVE_C_EVIDENCE_EMPTY" in codes
    assert "WAVE_C_REPORT_PDF_INVALID" in codes


def test_final_package_requires_external_hash_bound_receipts(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")

    validation = validate_wave_c_package(root, expected_code_sha=CODE_SHA)

    assert not validation.passed
    assert validation.trusted_receipts_verified is False
    assert "WAVE_C_TRUSTED_RECEIPTS_REQUIRED" in {
        issue.error_code for issue in validation.issues
    }


def test_unknown_supporting_evidence_id_fails_closed(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    result_path = root / "Q001" / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["research_plan"]["generated_hypotheses"][0][
        "supporting_evidence_ids"
    ] = ["EV-UNKNOWN"]
    _rewrite_indexed_json_artifact(root, "Q001", "result.json", result)

    validation = _validate_with_trust(root, tmp_path / "trusted")

    assert not validation.passed
    assert "WAVE_C_EVIDENCE_BINDING_INVALID" in {
        issue.error_code for issue in validation.issues
    }


def test_cross_question_evidence_id_reuse_fails_closed(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    q001_cards = json.loads(
        (root / "Q001" / "evidence_cards.json").read_text(encoding="utf-8")
    )
    reused_id = q001_cards[0]["evidence_id"]
    q002_cards_path = root / "Q002" / "evidence_cards.json"
    q002_cards = json.loads(q002_cards_path.read_text(encoding="utf-8"))
    q002_cards[0]["id"] = reused_id
    q002_cards[0]["evidence_id"] = reused_id
    _rewrite_indexed_json_artifact(
        root,
        "Q002",
        "evidence_cards.json",
        q002_cards,
    )
    q002_result_path = root / "Q002" / "result.json"
    q002_result = json.loads(q002_result_path.read_text(encoding="utf-8"))
    q002_result["research_plan"]["generated_hypotheses"][0][
        "supporting_evidence_ids"
    ] = [reused_id]
    q002_result["research_plan"]["reference_ids"] = [reused_id]
    q002_result["research_plan"]["references"] = q002_cards
    _rewrite_indexed_json_artifact(root, "Q002", "result.json", q002_result)

    validation = _validate_with_trust(root, tmp_path / "trusted")

    assert not validation.passed
    assert "WAVE_C_CROSS_QUESTION_EVIDENCE_REUSE" in {
        issue.error_code for issue in validation.issues
    }


def test_cross_question_similarity_above_point_nine_fails_closed(
    tmp_path: Path,
) -> None:
    root = _build_package(tmp_path / "batch")
    q001_result = json.loads(
        (root / "Q001" / "result.json").read_text(encoding="utf-8")
    )
    q002_result_path = root / "Q002" / "result.json"
    q002_result = json.loads(q002_result_path.read_text(encoding="utf-8"))
    q002_result["fields"] = dict(q001_result["fields"])
    q002_result["research_plan"]["generated_hypotheses"][0]["hypothesis"] = (
        q001_result["research_plan"]["generated_hypotheses"][0]["hypothesis"]
    )
    _rewrite_indexed_json_artifact(root, "Q002", "result.json", q002_result)

    validation = _validate_with_trust(root, tmp_path / "trusted")

    assert not validation.passed
    assert "WAVE_C_HIGH_CROSS_QUESTION_SIMILARITY" in {
        issue.error_code for issue in validation.issues
    }


def test_failed_t01_receipt_fails_closed_even_when_hash_bound(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    gate_path = root / "Q001" / "quality_gate_results.json"
    gates = json.loads(gate_path.read_text(encoding="utf-8"))
    gates[0].update(
        {
            "passed": False,
            "severity": "P1",
            "errors": ["T01 rejected evidence"],
            "score": 0.0,
        }
    )
    _write(gate_path, json.dumps(gates, sort_keys=True))

    validation = _validate_with_trust(root, tmp_path / "trusted")

    assert not validation.passed
    assert "WAVE_C_QUALITY_GATE_RECEIPT_INVALID" in {
        issue.error_code for issue in validation.issues
    }


@pytest.mark.parametrize(
    "budget_updates",
    (
        {
            "budget_policy_version": None,
            "budget_mode": None,
            "cost_accounting_required": None,
            "price_snapshot_required": None,
            "captain_waiver_reference": None,
        },
        {
            "budget_mode": "token_and_cost",
            "cost_accounting_required": True,
            "price_snapshot_required": True,
        },
    ),
    ids=("missing", "token_and_cost"),
)
def test_invalid_budget_mode_cannot_widen_to_price_snapshot(
    tmp_path: Path,
    budget_updates: dict[str, object],
) -> None:
    root = _build_package(tmp_path / "batch")
    audit_path = root / "Q001" / "llm_call_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit.update(
        {
            "cost_accounting_mode": "price_snapshot",
            "estimated_cost_usd": "0.001",
            "price_snapshot_version": "test-prices-v1",
        }
    )
    _rewrite_indexed_json_artifact(root, "Q001", "llm_call_audit.json", audit)

    index_path = root / "delivery_index.json"
    index = DeliveryIndex.from_json(index_path.read_text(encoding="utf-8"))
    records = tuple(
        replace(record, **budget_updates)
        if record.question_id == "Q001"
        else record
        for record in index.records
    )
    _write(index_path, build_delivery_index(index.batch_id, records).to_json())

    validation = _validate_with_trust(root, tmp_path / "trusted")

    assert not validation.passed
    assert "WAVE_C_BUDGET_MODE_INVALID" in {
        issue.error_code for issue in validation.issues
    }


def test_status_rejects_q999_even_with_rebuilt_index_checksum(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    index_path = root / "delivery_index.json"
    index = DeliveryIndex.from_json(index_path.read_text(encoding="utf-8"))
    original = index.records[0]
    q999_artifacts = tuple(
        replace(
            artifact,
            path=artifact.path.replace("Q001/", "Q999/", 1),
        )
        for artifact in original.artifacts
    )
    q999 = replace(
        original,
        question_id="Q999",
        artifacts=q999_artifacts,
    )
    rebuilt = build_delivery_index(BATCH_ID, (q999, *index.records[1:]))
    _write(index_path, rebuilt.to_json())

    snapshot = inspect_wave_c_status(root)

    assert snapshot.ready_for_finalization is False
    assert "WAVE_C_STATUS_QUESTION_SET_MISMATCH" in snapshot.structural_error_codes


def test_status_rejects_manifest_index_identity_mismatch(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["freeze_id"] = "OTHER-BATCH"
    _write(manifest_path, json.dumps(manifest, sort_keys=True))

    snapshot = inspect_wave_c_status(root)

    assert snapshot.ready_for_finalization is False
    assert "WAVE_C_STATUS_MANIFEST_INDEX_MISMATCH" in (
        snapshot.structural_error_codes
    )


def test_status_rejects_manifest_question_status_mismatch(tmp_path: Path) -> None:
    root = _build_package(tmp_path / "batch")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["questions"][0]["status"] = "failed"
    manifest["questions"][0]["completed"] = False
    _write(manifest_path, json.dumps(manifest, sort_keys=True))

    snapshot = inspect_wave_c_status(root)

    assert snapshot.ready_for_finalization is False
    assert "WAVE_C_STATUS_MANIFEST_QUESTION_MISMATCH" in (
        snapshot.structural_error_codes
    )


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
