"""Wave B physical artifact and actual-completion validation tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.batch.errors import BatchRunnerError
from app.contracts.batch import (
    REQUIRED_ARTIFACTS,
    STANDARD_OUTPUT_FIELDS,
    BatchJob,
    JobStatus,
    ModelRoute,
    OutputContract,
    ResultKind,
    SourceKind,
)


def _apis():
    import app.batch.output_layout as output_layout
    import app.batch.output_validation as output_validation

    return output_layout, output_validation


def _job(
    *,
    batch_id: str = "batch-five",
    question_id: str = "Q001",
    status: JobStatus = JobStatus.COMPLETED,
    missing_field: str | None = None,
) -> BatchJob:
    fields = {
        name: f"Synthetic value for {name}"
        for name in STANDARD_OUTPUT_FIELDS
        if name != missing_field
    }
    artifacts = {
        name: f"{batch_id}/{question_id}/{name}"
        for name in REQUIRED_ARTIFACTS
    }
    input_hash = "b" * 64
    return BatchJob(
        batch_id=batch_id,
        question_id=question_id,
        source_hash="a" * 64,
        input_hash=input_hash,
        workspace=f"{batch_id}/{question_id}/workspace",
        context_id=f"ctx:{batch_id}:{question_id}:{input_hash[:16]}",
        cache_namespace=f"cache:{batch_id}:{question_id}:{input_hash[:16]}",
        status=status,
        result_kind=ResultKind.ACTUAL,
        attempt=1,
        model_route=ModelRoute(
            route_id="formal-test-route",
            provider="test-provider",
            model="test-model",
            model_version="test-model-v1",
            prompt_version="test-prompt-v1",
            prompt_hash="c" * 64,
        ),
        output_contract=OutputContract(fields=fields, artifacts=artifacts),
    )


def _identity(job: BatchJob) -> dict[str, Any]:
    return {
        "batch_id": job.batch_id,
        "question_id": job.question_id,
        "attempt": job.attempt,
        "source_hash": job.source_hash,
        "input_hash": job.input_hash,
        "status": job.status.value,
    }


def _materialize(tmp_path: Path, job: BatchJob):
    layout, _ = _apis()
    paths = layout.build_question_output_paths(
        tmp_path / job.batch_id,
        job.question_id,
    )
    layout.create_question_output_directory(paths)
    paths.report_pdf.write_bytes(b"%PDF-1.7\n% synthetic test document\n")
    paths.report_md.write_text("# Synthetic report\n", encoding="utf-8")
    identity = _identity(job)
    paths.result_json.write_text(
        json.dumps(
            {**identity, "fields": job.output_contract.fields},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    paths.evidence_cards_json.write_text(
        json.dumps(
            [
                {
                    **identity,
                    "evidence_id": f"EV-{job.question_id}-001",
                    "source": {
                        "kind": "doi",
                        "reference": "10.0000/synthetic",
                    },
                }
            ],
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    paths.agent_trace_json.write_text(
        json.dumps(identity, sort_keys=True),
        encoding="utf-8",
    )
    return paths


def _rewrite_json(path: Path, **changes: Any) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        payload[0].update(changes)
    else:
        payload.update(changes)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_all_five_required_artifacts_pass_validation(tmp_path: Path) -> None:
    _, validation_api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)

    physical = validation_api.validate_required_artifacts(job, paths)
    completed = validation_api.validate_actual_completion(
        job,
        SourceKind.PRODUCTION,
        physical,
    )

    assert physical.passed is True
    assert completed.validation_status == "passed"
    assert {artifact.name for artifact in completed.artifacts} == set(
        REQUIRED_ARTIFACTS
    )


@pytest.mark.parametrize("artifact_name", REQUIRED_ARTIFACTS)
def test_each_missing_required_artifact_fails(
    tmp_path: Path,
    artifact_name: str,
) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    paths.path_for(artifact_name).unlink()

    result = api.validate_required_artifacts(job, paths)

    assert result.validation_status == "failed"
    assert "REQUIRED_ARTIFACT_MISSING" in result.error_codes


def test_empty_artifact_fails(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    paths.report_md.write_bytes(b"")

    result = api.validate_required_artifacts(job, paths)

    assert "ARTIFACT_EMPTY" in result.error_codes


def test_directory_cannot_masquerade_as_artifact(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    paths.report_md.unlink()
    paths.report_md.mkdir()

    result = api.validate_required_artifacts(job, paths)

    assert "OUTPUT_PATH_INVALID" in result.error_codes


@pytest.mark.parametrize(
    "artifact_name",
    ["result.json", "evidence_cards.json", "agent_trace.json"],
)
def test_each_corrupt_json_artifact_fails(
    tmp_path: Path,
    artifact_name: str,
) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    paths.path_for(artifact_name).write_text("{broken", encoding="utf-8")

    result = api.validate_required_artifacts(job, paths)

    assert "ARTIFACT_JSON_INVALID" in result.error_codes


@pytest.mark.parametrize(
    "artifact_name",
    ["result.json", "evidence_cards.json", "agent_trace.json"],
)
def test_question_identity_is_checked_in_every_json_artifact(
    tmp_path: Path,
    artifact_name: str,
) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    _rewrite_json(paths.path_for(artifact_name), question_id="Q999")

    result = api.validate_required_artifacts(job, paths)

    assert "ARTIFACT_QUESTION_MISMATCH" in result.error_codes


@pytest.mark.parametrize(
    "artifact_name",
    ["result.json", "evidence_cards.json", "agent_trace.json"],
)
def test_batch_identity_is_checked_in_every_json_artifact(
    tmp_path: Path,
    artifact_name: str,
) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    _rewrite_json(paths.path_for(artifact_name), batch_id="another-batch")

    result = api.validate_required_artifacts(job, paths)

    assert "ARTIFACT_BATCH_MISMATCH" in result.error_codes


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("attempt", 9),
        ("source_hash", "d" * 64),
        ("input_hash", "e" * 64),
        ("status", "failed"),
    ],
)
def test_job_provenance_is_checked_in_all_json_artifacts(
    tmp_path: Path,
    field: str,
    wrong_value: Any,
) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    for artifact_name in (
        "result.json",
        "evidence_cards.json",
        "agent_trace.json",
    ):
        _rewrite_json(paths.path_for(artifact_name), **{field: wrong_value})

    result = api.validate_required_artifacts(job, paths)

    assert "ARTIFACT_PROVENANCE_MISMATCH" in result.error_codes


def test_plain_text_renamed_as_pdf_fails(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    paths.report_pdf.write_text("not a PDF", encoding="utf-8")

    result = api.validate_required_artifacts(job, paths)

    assert "PDF_SIGNATURE_INVALID" in result.error_codes


def test_symlink_artifact_is_rejected(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    external = tmp_path / "external.md"
    external.write_text("outside", encoding="utf-8")
    paths.report_md.unlink()
    try:
        os.symlink(external, paths.report_md)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    result = api.validate_required_artifacts(job, paths)

    assert "ARTIFACT_SYMLINK_REJECTED" in result.error_codes


def test_symlink_artifact_detection_is_verified_without_os_privilege(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    original = Path.is_symlink

    def simulated_symlink(candidate: Path) -> bool:
        return candidate == paths.report_md or original(candidate)

    monkeypatch.setattr(Path, "is_symlink", simulated_symlink)

    result = api.validate_required_artifacts(job, paths)

    assert "ARTIFACT_SYMLINK_REJECTED" in result.error_codes


@pytest.mark.parametrize(
    ("result_kind", "mock"),
    [
        (ResultKind.MOCK, True),
        (ResultKind.PLANNED, False),
        (ResultKind.EXPECTED, False),
    ],
)
def test_non_actual_completed_fails_completion_gate(
    tmp_path: Path,
    result_kind: ResultKind,
    mock: bool,
) -> None:
    _, api = _apis()
    job = _job().model_copy(update={"result_kind": result_kind, "mock": mock})
    paths = _materialize(tmp_path, job)

    physical = api.validate_required_artifacts(job, paths)
    result = api.validate_actual_completion(
        job,
        SourceKind.PRODUCTION,
        physical,
    )

    assert "ACTUAL_STATUS_INVALID" in result.error_codes


def test_synthetic_actual_completed_fails_completion_gate(
    tmp_path: Path,
) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)

    physical = api.validate_required_artifacts(job, paths)
    result = api.validate_actual_completion(
        job,
        SourceKind.SYNTHETIC,
        physical,
    )

    assert "ACTUAL_STATUS_INVALID" in result.error_codes


def test_non_completed_status_fails_actual_completion_gate(
    tmp_path: Path,
) -> None:
    _, api = _apis()
    job = _job(status=JobStatus.GATES_PENDING)
    paths = _materialize(tmp_path, job)
    physical = api.validate_required_artifacts(job, paths)

    result = api.validate_actual_completion(
        job,
        SourceKind.PRODUCTION,
        physical,
    )

    assert "ACTUAL_STATUS_INVALID" in result.error_codes


def test_missing_standard_output_field_fails(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job(
        status=JobStatus.GATES_PENDING,
        missing_field="References",
    )
    paths = _materialize(tmp_path, job)

    result = api.validate_required_artifacts(job, paths)

    assert "OUTPUT_CONTRACT_INCOMPLETE" in result.error_codes


def test_cross_question_declared_artifact_path_fails(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job()
    artifacts = dict(job.output_contract.artifacts)
    artifacts["report.md"] = "batch-five/Q002/report.md"
    job = job.model_copy(
        update={
            "output_contract": job.output_contract.model_copy(
                update={"artifacts": artifacts}
            )
        }
    )
    paths = _materialize(tmp_path, job)

    result = api.validate_required_artifacts(job, paths)

    assert "OUTPUT_PATH_INVALID" in result.error_codes


def test_file_hash_change_is_detected(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    validation = api.validate_required_artifacts(job, paths)
    manifest = api.build_artifact_manifest(job, paths, validation)
    before = next(
        artifact.sha256
        for artifact in manifest.artifacts
        if artifact.name == "report.md"
    )

    paths.report_md.write_text("# Mutated synthetic report\n", encoding="utf-8")

    assert api.compute_file_sha256(paths.report_md) != before


def test_manifest_checksum_excludes_its_own_digest(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    validation = api.validate_required_artifacts(job, paths)

    first = api.build_artifact_manifest(job, paths, validation)
    second = api.build_artifact_manifest(job, paths, validation)

    assert first == second
    assert len(first.manifest_sha256) == 64


def test_failed_validation_cannot_build_manifest(tmp_path: Path) -> None:
    _, api = _apis()
    job = _job()
    paths = _materialize(tmp_path, job)
    paths.report_pdf.unlink()
    validation = api.validate_required_artifacts(job, paths)

    with pytest.raises(BatchRunnerError) as captured:
        api.build_artifact_manifest(job, paths, validation)

    assert captured.value.error_code == "OUTPUT_CONTRACT_INCOMPLETE"
