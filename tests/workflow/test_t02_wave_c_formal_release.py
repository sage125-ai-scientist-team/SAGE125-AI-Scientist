"""Fail-closed tests for the Captain-authorized T02 Wave C formal runner."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

import app.workflow.preflight as preflight_module
import app.workflow.wave_c_release as release
from app.contracts.execution import (
    ArtifactRequirement,
    DatasetManifest,
    ExecutionResult,
    ExecutionSpec,
    MetricRequirement,
)
from app.contracts.multimodal import MultimodalArtifact
from app.contracts.revision import PlanVersion
from app.execution import EntrypointRegistry, LocalProcessRunner
from app.workflow.explainable_revision import (
    RevisionChange,
    StructuredRevisionDiff,
    build_experiment_revision_context,
    issues_for_revision,
)
from app.workflow.revision_feedback import build_revision_feedback


GIT_SHA = "1" * 40


def _actual_execution_result(
    tmp_path: Path,
    *,
    question_id: str = "Q028",
    metric_value: float = 0.875,
) -> ExecutionResult:
    case_root = tmp_path / f"actual-{question_id}-{str(metric_value).replace('.', '-')}"
    case_root.mkdir(parents=True)
    dataset_bytes = b"sample,value\nalpha,1\nbeta,2\n"
    artifact_bytes = json.dumps(
        {"metric": {"name": "score", "unit": "ratio", "value": metric_value}},
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    source = case_root / "dataset.csv"
    source.write_bytes(dataset_bytes)
    dataset = DatasetManifest(
        dataset_id="dataset-primary",
        source_uri="fixture://source/dataset.csv",
        license="CC-BY-4.0",
        version="2026.08-wave-c",
        sha256=hashlib.sha256(dataset_bytes).hexdigest(),
        size_bytes=len(dataset_bytes),
        workspace_relative_path="datasets/dataset-primary.csv",
    )
    artifact = ArtifactRequirement(
        artifact_id="metrics-primary",
        relative_path="artifacts/metrics.json",
        kind="metrics",
        media_type="application/json",
        required=True,
        expected_sha256=hashlib.sha256(artifact_bytes).hexdigest(),
        max_bytes=65_536,
    )
    metric = MetricRequirement(
        name="score",
        unit="ratio",
        artifact_id="metrics-primary",
        required=True,
    )
    spec = ExecutionSpec.model_validate(
        {
            "spec_id": f"spec-{question_id}-{metric_value}",
            "question_id": question_id,
            "round_index": 0,
            "mode": "actual",
            "entrypoint": "wave-c-probe",
            "argv": [
                "artifact",
                "artifacts/metrics.json",
                "--metric-name",
                "score",
                "--metric-value",
                str(metric_value),
                "--metric-unit",
                "ratio",
            ],
            "datasets": [dataset],
            "required_artifacts": [artifact],
            "required_metrics": [metric],
            "seed": 125,
            "resources": {
                "timeout_seconds": 5.0,
                "max_stdout_bytes": 4_096,
                "max_stderr_bytes": 4_096,
                "max_artifact_bytes": 65_536,
                "network_access": "not_requested",
            },
            "environment": {
                "variables": {},
                "dependency_allowlist": ["pydantic", "pytest"],
            },
            "cleanup_policy": "preserve",
        }
    )
    registry = EntrypointRegistry()
    registry.register_python(
        "wave-c-probe",
        Path("tests/execution/fixtures/probe.py").resolve(),
        entrypoint_class="scientific",
    )
    result = LocalProcessRunner(
        registry=registry,
        managed_root=case_root / "managed-root",
        dataset_resolver=lambda _manifest: source,
        dependency_version_provider=lambda names: {
            name: {"pydantic": "2.12.4", "pytest": "9.0.3"}[name]
            for name in names
        },
        git_provenance_provider=lambda: {
            "commit_sha": GIT_SHA,
            "dirty": False,
            "available": True,
        },
    ).run(spec)
    assert result.actual_execution is True
    return result


def _untrusted_execution_variant(
    result: ExecutionResult,
    **updates: Any,
) -> ExecutionResult:
    payload = result.model_dump(mode="python")
    for field_name in (
        "runner_verified",
        "datasets_validated",
        "artifacts_validated",
        "metrics_validated",
        "provenance_complete",
        "scientific_result_usable",
        "actual_execution",
    ):
        payload[field_name] = False
    payload["resource_enforcement"] = None
    payload.update(updates)
    return ExecutionResult.model_validate(payload)


def _multimodal_artifact(
    *,
    artifact_id: str = "chart-q028",
    source_path: str = "C:/temp/run-a/source.csv",
    source_type: str = "csv",
    validation_status: str = "passed",
    value: str = "0.875",
) -> MultimodalArtifact:
    return MultimodalArtifact.model_validate(
        {
            "artifact_id": artifact_id,
            "modality": "table",
            "provenance": {
                "source_path": source_path,
                "source_type": source_type,
                "page": 1,
                "bbox": None,
            },
            "units": ["ratio"],
            "column_units": [{"column": "score", "unit": "ratio"}],
            "axes": None,
            "legend": ["score"],
            "data": {"headers": ["score"], "rows": [[value]]},
            "confidence": 1.0,
            "validation_status": validation_status,
        }
    )


def _formal_case_input(
    result: ExecutionResult,
    artifact: MultimodalArtifact,
    *,
    question_id: str = "Q028",
    pairing_policy_reference: str | None = "FROZEN_V1",
    canonical_input: dict[str, Any] | None = None,
    t05_source_commit: str = GIT_SHA,
    t06_source_commit: str = GIT_SHA,
    t06_source_run_id: str | None = None,
    pairing_id: str | None = None,
    allow_cross_run_pairing: bool = False,
    authorized_source_commits: tuple[str, ...] = (),
    attested_integration_tip: str | None = None,
    execution_publicly_verified: bool = True,
    multimodal_actual: bool = True,
    multimodal_mock: bool = False,
    multimodal_provenance_complete: bool = True,
) -> Any:
    case_spec = next(
        item for item in release.FORMAL_CASE_SPECS if item[1] == question_id
    )
    canonical_payload = canonical_input or {
        "id": question_id,
        "question": "controlled",
    }
    canonical_input_sha256 = release.canonical_sha256(canonical_payload)
    input_identity = canonical_input_sha256
    effective_pairing_id = pairing_id or f"pairing-{question_id.casefold()}-v1"
    effective_t06_run_id = t06_source_run_id or result.execution_id
    execution_hash = release.execution_result_hash(result)
    artifact_hash = release.multimodal_artifact_hash(artifact)
    return release.FormalCaseInput(
        question_id=question_id,
        logical_labels=case_spec[2],
        shared_run=case_spec[3],
        execution=release.FormalExecutionInput(
            execution_result=result,
            source_path=f"docs/modules/T05/round1/{question_id}/execution_result.json",
            source_commit=t05_source_commit,
            source_run_id=result.execution_id,
            input_identity=input_identity,
            canonical_input_sha256=canonical_input_sha256,
            pairing_id=effective_pairing_id,
            source_hash=execution_hash,
            public_loader_reference="app.execution.public_verified_loader",
            publicly_verified=execution_publicly_verified,
            checksum_verification="PASS",
        ),
        multimodal=(
            release.FormalMultimodalInput(
                artifact=artifact,
                question_id=question_id,
                source_path=(
                    f"docs/modules/T06/formal/{question_id}/table_artifact.json"
                ),
                source_commit=t06_source_commit,
                source_run_id=effective_t06_run_id,
                input_identity=input_identity,
                canonical_input_sha256=canonical_input_sha256,
                pairing_id=effective_pairing_id,
                source_hash=artifact_hash,
                artifact_checksum="3" * 64,
                checksum_verification="PASS",
                actual=multimodal_actual,
                mock_mode=multimodal_mock,
                provenance_complete=multimodal_provenance_complete,
            ),
        ),
        input_identity=input_identity,
        canonical_input_sha256=canonical_input_sha256,
        pairing=release.FormalPairingMetadata(
            policy_reference=pairing_policy_reference,
            authority_provenance=release.PAIRING_AUTHORITY_URL,
            question_id=question_id,
            input_identity=input_identity,
            canonical_input_sha256=canonical_input_sha256,
            pairing_id=effective_pairing_id,
            case_run_id=result.execution_id,
            allow_cross_run_pairing=allow_cross_run_pairing,
            authorized_source_commits=authorized_source_commits,
            attested_integration_tip=attested_integration_tip,
            reviewer_feedback=release.FormalReviewerFeedbackBinding(
                question_id=question_id,
                source_run_id=result.execution_id,
                target_version_id=f"{result.execution_id}:v2",
                lineage=(
                    f"{result.execution_id}:v1",
                    f"{result.execution_id}:v2",
                ),
                feedback_fingerprint="4" * 64,
                provenance_complete=True,
            ),
        )
        if pairing_policy_reference is not None
        else None,
    )


def _authority_payload(*, login: str = release.CAPTAIN_LOGIN) -> dict[str, Any]:
    return {
        "user": {"login": login},
        "html_url": release.CAPTAIN_AUTHORITY_URL,
        "created_at": "2026-08-14T08:13:44Z",
        "body": "\n".join(
            (
                "RANDOM_CASE_IDS=[Q095,Q045,Q100]",
                "RANDOM_CASE_SEED=20260814",
                "Q028_FLAGSHIP_SHARED_RUN_ALLOWED=YES",
                "METRIC004_RANDOM_CASE_COUNT_CONFIRMED=YES",
                "C007_LOGICAL_CASE_OBLIGATIONS=5",
                "C007_UNIQUE_ACTUAL_RUNS=4",
                "AUTHORIZED_BY_CAPTAIN=YES",
                "FROZEN_MODEL_POLICY=TIERED_ROUTE_ALLOWED",
                "AUTHORIZED_MODELS=[",
                "  qwen3.6-flash,",
                "  qwen3.7-plus,",
                "  qwen3.7-max",
                "]",
                "C007_ACTUAL_REQUIREMENT=T05_EXECUTION_RESULT_REQUIRED",
                "T06_MULTIMODAL_EVIDENCE_REQUIRED=YES",
            )
        ),
    }


def _pairing_authority_payload(
    *,
    login: str = release.CAPTAIN_LOGIN,
) -> dict[str, Any]:
    return {
        "user": {"login": login},
        "html_url": release.PAIRING_AUTHORITY_URL,
        "created_at": "2026-08-15T00:00:00Z",
        "body": "\n".join(
            (
                "AUTHORIZED_BY_CAPTAIN=YES",
                f"CAPTAIN_ACCOUNT={release.CAPTAIN_LOGIN}",
                "PR=#37",
                f"BOUND_HEAD={release.PAIRING_AUTHORITY_BOUND_HEAD}",
                "C007_ACTUAL_REQUIREMENT=T05_EXECUTION_RESULT_REQUIRED",
                "T06_MULTIMODAL_EVIDENCE_REQUIRED=YES",
                "C007_CROSS_OWNER_PAIRING_POLICY=FROZEN_V1",
            )
        ),
    }


def test_verify_captain_authority_checks_publisher_and_all_frozen_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed.append(command)
        payload = (
            _pairing_authority_payload()
            if str(release.PAIRING_AUTHORITY_COMMENT_ID) in command[-1]
            else _authority_payload()
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(release.subprocess, "run", fake_run)

    result = release.verify_captain_authority()

    assert result["verified"] is True
    assert result["login"] == "liuyanbo12"
    assert result["timestamp"] == "2026-08-14T08:13:44Z"
    assert result["FROZEN_MODEL_POLICY"] == "TIERED_ROUTE_ALLOWED"
    assert result["AUTHORIZED_MODELS"] == [
        "qwen3.6-flash",
        "qwen3.7-plus",
        "qwen3.7-max",
    ]
    assert result["C007_ACTUAL_REQUIREMENT"] == (
        "T05_EXECUTION_RESULT_REQUIRED"
    )
    assert result["T06_MULTIMODAL_EVIDENCE_REQUIRED"] == "YES"
    assert result["C007_CROSS_OWNER_PAIRING_POLICY"] == "FROZEN_V1"
    assert result["pairing_authority_ready"] is True
    assert result["pairing_authority_required"] is False
    assert result["pairing_policy"] == "FROZEN_V1"
    assert observed == [
        [
            "gh",
            "api",
            "repos/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
            "issues/comments/5291084709",
        ],
        [
            "gh",
            "api",
            "repos/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
            "issues/comments/5300864125",
        ],
    ]

    def wrong_publisher(
        command: list[str], **_kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        payload = (
            _pairing_authority_payload(login="not-the-captain")
            if str(release.PAIRING_AUTHORITY_COMMENT_ID) in command[-1]
            else _authority_payload(login="not-the-captain")
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(release.subprocess, "run", wrong_publisher)
    with pytest.raises(ValueError, match="publisher"):
        release.verify_captain_authority()


def test_exact_captain_authority_fields_are_accepted_without_compatibility() -> None:
    authority = release.resolve_formal_acceptance_authority(
        {
            "FROZEN_MODEL_POLICY": "TIERED_ROUTE_ALLOWED",
            "AUTHORIZED_MODELS": [
                "qwen3.6-flash",
                "qwen3.7-plus",
                "qwen3.7-max",
            ],
            "C007_ACTUAL_REQUIREMENT": "T05_EXECUTION_RESULT_REQUIRED",
            "T06_MULTIMODAL_EVIDENCE_REQUIRED": "YES",
            "C007_CROSS_OWNER_PAIRING_POLICY": "FROZEN_V1",
        }
    )

    assert authority.ready is True
    assert authority.status == "AUTHORIZED"
    assert authority.compatibility_path == "CAPTAIN_EXACT"
    assert authority.frozen_model_policy == "TIERED_ROUTE_ALLOWED"
    assert authority.authorized_models == (
        "qwen3.6-flash",
        "qwen3.7-plus",
        "qwen3.7-max",
    )
    assert authority.actual_requirement == "T05_EXECUTION_RESULT_REQUIRED"
    assert authority.multimodal_required is True
    assert authority.pairing_policy_reference == "FROZEN_V1"
    assert authority.pairing_authority_ready is True
    assert authority.pairing_authority_required is False


@pytest.mark.parametrize(
    ("overrides", "expected_blocker"),
    [
        (
            {"FROZEN_MODEL_POLICY": "UNKNOWN_POLICY"},
            "FROZEN_MODEL_POLICY_INVALID",
        ),
        (
            {
                "AUTHORIZED_MODELS": [
                    "qwen3.6-flash",
                    "qwen3.7-plus",
                    "unauthorized-model",
                ]
            },
            "AUTHORIZED_MODELS_INVALID",
        ),
        (
            {"T06_MULTIMODAL_EVIDENCE_REQUIRED": None},
            "T06_MULTIMODAL_EVIDENCE_REQUIRED",
        ),
        (
            {
                "C007_ACTUAL_REQUIREMENT": None,
                "C007_ACTUAL_REQUIRMENT": "T05_EXECUTION_RESULT_REQUIRED",
            },
            "C007_ACTUAL_REQUIREMENT",
        ),
        (
            {"C007_CROSS_OWNER_PAIRING_POLICY": None},
            "C007_CROSS_OWNER_PAIRING_POLICY",
        ),
        (
            {"C007_CROSS_OWNER_PAIRING_POLICY": "UNKNOWN_POLICY"},
            "C007_CROSS_OWNER_PAIRING_POLICY_INVALID",
        ),
    ],
)
def test_exact_authority_parser_fails_closed(
    overrides: dict[str, Any],
    expected_blocker: str,
) -> None:
    payload: dict[str, Any] = {
        "FROZEN_MODEL_POLICY": "TIERED_ROUTE_ALLOWED",
        "AUTHORIZED_MODELS": [
            "qwen3.6-flash",
            "qwen3.7-plus",
            "qwen3.7-max",
        ],
        "C007_ACTUAL_REQUIREMENT": "T05_EXECUTION_RESULT_REQUIRED",
        "T06_MULTIMODAL_EVIDENCE_REQUIRED": "YES",
        "C007_CROSS_OWNER_PAIRING_POLICY": "FROZEN_V1",
    }
    payload.update(overrides)

    authority = release.resolve_formal_acceptance_authority(payload)

    assert authority.ready is False
    assert authority.status == "BLOCKED_AUTHORITY_REQUIRED"
    assert expected_blocker in authority.missing_fields


def test_frozen_v1_authority_is_ready_when_case_inputs_are_not_ready() -> None:
    authority = release.resolve_formal_acceptance_authority(
        {
            "FROZEN_MODEL_POLICY": "TIERED_ROUTE_ALLOWED",
            "AUTHORIZED_MODELS": list(release.AUTHORIZED_MODEL_IDENTITIES),
            "C007_ACTUAL_REQUIREMENT": "T05_EXECUTION_RESULT_REQUIRED",
            "T06_MULTIMODAL_EVIDENCE_REQUIRED": "YES",
            "C007_CROSS_OWNER_PAIRING_POLICY": "FROZEN_V1",
        }
    )
    eligibility = release._missing_formal_case_eligibility("Q028")

    assert authority.pairing_policy_reference == "FROZEN_V1"
    assert authority.pairing_authority_ready is True
    assert authority.pairing_authority_required is False
    assert eligibility.pairing_policy == "FROZEN_V1"
    assert eligibility.pairing_authority_ready is True
    assert eligibility.pairing_authority_required is False
    assert eligibility.t05_ready is False
    assert eligibility.t06_ready is False
    assert eligibility.pairing_ready is False
    assert "PAIRING_AUTHORITY_REQUIRED" not in eligibility.blockers

    readiness = release.build_formal_readiness_status(
        authority,
        {
            question_id: release._missing_formal_case_eligibility(question_id)
            for question_id in ("Q028", "Q095", "Q045", "Q100")
        },
    )
    assert readiness == {
        "PAIRING_AUTHORITY_READY": "YES",
        "PAIRING_AUTHORITY_REQUIRED": "NO",
        "PAIRING_POLICY": "FROZEN_V1",
        "ALL_T05_READY": "NO",
        "ALL_T06_READY": "NO",
        "ALL_PAIRINGS_READY": "NO",
        "ALL_CASES_READY_FOR_RERUN": "NO",
    }


def test_legacy_authority_alias_is_explicit_and_cannot_override_exact() -> None:
    legacy = release.resolve_formal_acceptance_authority(
        {
            "FROZEN_MODEL_POLICY": (
                "TIERED_QWEN3_6_FLASH_QWEN3_7_PLUS_QWEN3_7_MAX"
            ),
            "C007_ACTUAL_EXECUTION_REQUIREMENT": (
                "T05_T06_MULTIMODAL_REQUIRED"
            ),
            "C007_CROSS_OWNER_PAIRING_POLICY": "FROZEN_V1",
        }
    )
    exact = release.resolve_formal_acceptance_authority(
        {
            "FROZEN_MODEL_POLICY": "TIERED_ROUTE_ALLOWED",
            "AUTHORIZED_MODELS": [
                "qwen3.6-flash",
                "qwen3.7-plus",
                "qwen3.7-max",
            ],
            "C007_ACTUAL_REQUIREMENT": "T05_EXECUTION_RESULT_REQUIRED",
            "T06_MULTIMODAL_EVIDENCE_REQUIRED": "YES",
            "C007_CROSS_OWNER_PAIRING_POLICY": "FROZEN_V1",
            "C007_ACTUAL_EXECUTION_REQUIREMENT": "REAL_PROVIDER_CALLS_ONLY",
        }
    )

    assert legacy.ready is True
    assert legacy.compatibility_path == "LEGACY_ALIAS"
    assert exact.ready is True
    assert exact.compatibility_path == "CAPTAIN_EXACT"
    assert exact.actual_requirement == "T05_EXECUTION_RESULT_REQUIRED"


def test_frozen_random_selection_is_exact_and_excludes_q028() -> None:
    items = [{"id": f"Q{index:03d}"} for index in range(1, 126)]

    assert release.reproduce_random_selection(items) == ["Q095", "Q045", "Q100"]

    missing = [item for item in items if item["id"] != "Q100"]
    with pytest.raises(ValueError, match="population"):
        release.reproduce_random_selection(missing)


def test_missing_formal_inputs_block_before_provider_and_write_four_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    items = [
        {
            "id": f"Q{index:03d}",
            "question": f"Canonical question {index}",
            "domain": "test-only-canonical-shape",
        }
        for index in range(1, 126)
    ]
    by_id = {item["id"]: item for item in items}
    by_id["Q028"]["question"] = release.Q028_QUESTION
    source = {
        "source_document_url": release.SOURCE_DOCUMENT_URL,
        "source_document_filename": "sjtu-booklet.pdf",
        "source_document_sha256": release.SOURCE_DOCUMENT_SHA256,
        "source_catalog_sha256": release.canonical_sha256(items),
        "source_record_count": 125,
        "removed_count": 0,
        "fallback_used": False,
        "layout_repairs": [],
        "quality_issues": [],
    }
    flagship = tmp_path / "flagship.json"
    flagship.write_text('{"question_id":"Q028"}\n', encoding="utf-8")
    config = {
        "provider": "qwen",
        "models": {"fast": "qwen-fast"},
        "use_local_rag": False,
        "use_deep_research": False,
        "use_open_literature": True,
        "reviewer_auto_revision": True,
        "mock_mode": False,
        "random_seed": release.FORMAL_RANDOM_SEED,
    }
    monkeypatch.setattr(
        release,
        "verify_captain_authority",
        lambda: {
            "verified": True,
            "FROZEN_MODEL_POLICY": "TIERED_ROUTE_ALLOWED",
            "AUTHORIZED_MODELS": list(release.AUTHORIZED_MODEL_IDENTITIES),
            "C007_ACTUAL_REQUIREMENT": "T05_EXECUTION_RESULT_REQUIRED",
            "T06_MULTIMODAL_EVIDENCE_REQUIRED": "YES",
            "C007_CROSS_OWNER_PAIRING_POLICY": "FROZEN_V1",
        },
    )
    monkeypatch.setattr(release, "_current_git_sha", lambda: GIT_SHA)
    monkeypatch.setattr(
        release,
        "load_canonical_catalog",
        lambda _path: (items, source),
    )
    monkeypatch.setattr(
        release,
        "reproduce_random_selection",
        lambda _items: list(release.FORMAL_RANDOM_CASE_IDS),
    )
    monkeypatch.setattr(release, "FLAGSHIP_SOURCE", str(flagship))
    monkeypatch.setattr(
        release,
        "Q028_CANONICAL_INPUT_HASH",
        release.canonical_sha256(by_id["Q028"]),
    )
    monkeypatch.setattr(release, "_release_config", lambda: config)
    monkeypatch.setattr(
        preflight_module,
        "run_real_preflight",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("formal input gate must run before Provider preflight")
        ),
    )

    def forbidden_actual_call(**_kwargs: Any) -> Any:
        raise AssertionError("provider-blocked formal mode must not call the pipeline")

    monkeypatch.setattr(release, "execute_formal_case", forbidden_actual_call)
    output = tmp_path / "evidence"

    summary = release.run_formal_release(tmp_path / "unused.pdf", output)

    raw = json.loads((output / "raw_results.json").read_text(encoding="utf-8"))
    matrix = json.loads(
        (output / "regression_matrix.json").read_text(encoding="utf-8")
    )
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert summary["raw_status"] == "BLOCKED"
    assert summary["actual_run_count"] == 0
    assert len(raw["records"]) == 4
    assert [record["question_id"] for record in raw["records"]] == [
        "Q028",
        "Q095",
        "Q045",
        "Q100",
    ]
    assert sum(record["question_id"] == "Q028" for record in raw["records"]) == 1
    assert all(record["status"] == "CASE_BLOCKED" for record in raw["records"])
    assert all(record["execution_mode"] == "real" for record in raw["records"])
    assert all(record["mock_mode"] is False for record in raw["records"])
    assert all(
        record["failure"]["stage"] == "formal_input_eligibility"
        for record in raw["records"]
    )
    assert all(
        record["failure"]["state"]["provider_calls"] == 0
        and record["failure"]["state"]["pipeline_real_calls"] == 0
        for record in raw["records"]
    )
    preflight = json.loads(
        (output / "provider_preflight.json").read_text(encoding="utf-8")
    )
    assert preflight["status"] == "BLOCKED_FORMAL_INPUTS"
    assert preflight["connectivity"] == {"checked": False, "ok": None}
    assert preflight["provider_calls"] == 0
    assert len(matrix["rows"]) == 5
    assert matrix["rows"][0]["shared_run"] is True
    assert matrix["rows"][1]["shared_run"] is True
    assert matrix["result"] == "BLOCKED"
    assert metrics["random_case_ids"] == ["Q095", "Q045", "Q100"]
    assert metrics["random_case_executed"] == 0
    assert metrics["random_case_passed"] == 0
    assert (output / "checksums.json").is_file()
    reproduction = (output / "reproduction.md").read_text(encoding="utf-8")
    assert "--execute-release" in reproduction
    assert "fixture" in reproduction


def test_mixed_model_call_evidence_preserves_all_identities_and_counts() -> None:
    calls = [
        {"provider": "bailian_qwen", "model": "qwen3.6-flash", "mock": False},
        {"provider": "bailian_qwen", "model": "qwen3.7-plus", "mock": False},
        {"provider": "bailian_qwen", "model": "qwen3.7-max", "mock": False},
        {"provider": "bailian_qwen", "model": "qwen3.7-plus", "mock": False},
    ]

    identities, counts = release.summarize_actual_model_calls(calls)

    assert identities == ("qwen3.6-flash", "qwen3.7-max", "qwen3.7-plus")
    assert counts == {
        "qwen3.6-flash": 1,
        "qwen3.7-max": 1,
        "qwen3.7-plus": 2,
    }
    assert sum(counts.values()) == len(calls)


def test_post_run_materialization_failure_preserves_real_call_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import app.core.config as config_module
    import app.workflow.artifacts as artifacts_module
    import app.workflow.pipeline as pipeline_module

    run_id = "formal-materialization-failure"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "agent_trace.json").write_text("[]\n", encoding="utf-8")
    calls = [
        {
            "call_id": f"materialization-call-{index}",
            "agent_name": stage,
            "provider": "bailian_qwen",
            "model": model,
            "mock": False,
            "status": "success",
            "started_at": f"2026-08-15T00:00:0{index}+00:00",
            "ended_at": f"2026-08-15T00:00:0{index + 1}+00:00",
        }
        for index, (stage, model) in enumerate(
            (
                ("HypothesisGenerator", "qwen3.6-flash"),
                ("ExperimentDesigner", "qwen3.7-plus"),
                ("ScientificReviewer", "qwen3.7-max"),
            )
        )
    ]
    state = SimpleNamespace(
        run_id=run_id,
        llm_calls=calls,
        mock_mode=False,
        run_mode="real",
        agent_trace=[{"revision_audit": {"schema_version": 1}}],
    )
    plan = SimpleNamespace(actual_execution=False, validation_status="needs_data")
    monkeypatch.setattr(
        pipeline_module,
        "run_pipeline_with_state",
        lambda *_args, **_kwargs: (plan, state),
    )
    monkeypatch.setattr(artifacts_module, "resolve_artifact_base", lambda _path: tmp_path)
    monkeypatch.setattr(
        config_module,
        "get_settings",
        lambda: SimpleNamespace(export_dir=str(tmp_path)),
    )
    monkeypatch.setattr(
        release,
        "_consumer_from_trace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("controlled materialization failure")
        ),
    )
    config = {
        "provider": "bailian_qwen",
        "models": {
            "fast": "qwen3.6-flash",
            "balanced": "qwen3.7-plus",
            "strong": "qwen3.7-max",
        },
    }
    formal_input = _formal_case_input(
        _actual_execution_result(tmp_path),
        _multimodal_artifact(),
    )

    record = release.execute_formal_case(
        case_spec=release.FORMAL_CASE_SPECS[0],
        canonical_input={"id": "Q028", "question": "controlled"},
        questions_path=tmp_path / "questions.json",
        git_sha=GIT_SHA,
        config=config,
        frozen_model_policy="TIERED_ROUTE_ALLOWED",
        actual_execution_requirement="T05_EXECUTION_RESULT_REQUIRED",
        formal_input=formal_input,
    )

    assert record.status == "RUN_FAILED"
    assert record.llm_call_count == 3
    assert record.provider == "bailian_qwen"
    assert record.model == "mixed"
    assert record.model_identities == (
        "qwen3.6-flash",
        "qwen3.7-max",
        "qwen3.7-plus",
    )
    assert record.model_call_counts == {
        "qwen3.6-flash": 1,
        "qwen3.7-max": 1,
        "qwen3.7-plus": 1,
    }
    assert record.model_route is not None
    assert record.model_route.total_model_calls == 3
    assert record.model_route.ledger_complete is True


def test_acceptance_predicates_are_explicit_and_fail_closed() -> None:
    assert release.validation_status_qualified("validated") is True
    assert release.validation_status_qualified("needs_data") is False
    assert release.validation_status_qualified(None) is False

    assert release.actual_execution_requirement_qualified(
        "T05_EXECUTION_RESULT_REQUIRED",
        actual_execution=True,
        multimodal_evidence_present=True,
        real_provider_call_count=1,
    ) is True
    assert release.actual_execution_requirement_qualified(
        "T05_EXECUTION_RESULT_REQUIRED",
        actual_execution=False,
        multimodal_evidence_present=True,
        real_provider_call_count=1,
    ) is False
    assert release.actual_execution_requirement_qualified(
        "T05_EXECUTION_RESULT_REQUIRED",
        actual_execution=True,
        multimodal_evidence_present=False,
        real_provider_call_count=1,
    ) is False


def test_missing_acceptance_authority_requires_explicit_blocked_status() -> None:
    authority = release.resolve_formal_acceptance_authority({"verified": True})

    assert authority.status == "BLOCKED_AUTHORITY_REQUIRED"
    assert authority.ready is False
    assert set(authority.missing_fields) == {
        "FROZEN_MODEL_POLICY",
        "AUTHORIZED_MODELS",
        "C007_ACTUAL_REQUIREMENT",
        "T06_MULTIMODAL_EVIDENCE_REQUIRED",
        "C007_CROSS_OWNER_PAIRING_POLICY",
    }


def test_success_record_rejects_truthy_needs_data_and_unqualified_execution() -> None:
    now = datetime.now(timezone.utc)
    config = {"provider": "bailian_qwen", "models": {"fast": "qwen3.6-flash"}}
    payload = {
        "case_key": "Q028_FLAGSHIP_SHARED",
        "requirement_labels": ("Q028_REGRESSION", "FLAGSHIP"),
        "question_id": "Q028",
        "canonical_input": {"id": "Q028"},
        "input_hash": release.canonical_sha256({"id": "Q028"}),
        "shared_run": True,
        "git_sha": GIT_SHA,
        "config": config,
        "config_hash": release.canonical_sha256(config),
        "status": "SUCCEEDED",
        "actual_run_id": "actual-run",
        "provider": "bailian_qwen",
        "model": "qwen3.6-flash",
        "model_identities": ("qwen3.6-flash",),
        "model_call_counts": {"qwen3.6-flash": 1},
        "frozen_model_policy": "TIERED_ROUTE_ALLOWED",
        "model_policy_qualified": True,
        "actual_execution_requirement": "T05_EXECUTION_RESULT_REQUIRED",
        "actual_execution": False,
        "actual_execution_qualified": False,
        "multimodal_evidence_present": False,
        "started_at": now,
        "ended_at": now,
        "llm_call_count": 1,
        "v1_version_id": "actual-run:v1",
        "v2_version_id": "actual-run:v2",
        "v1_prompt_hash": "a" * 64,
        "v2_prompt_hash": "b" * 64,
        "feedback_fingerprint": "c" * 64,
        "revision_context_fingerprint": "d" * 64,
        "revision_context": {"present": True},
        "structured_diff": {"changes": [{"present": True}]},
        "diff_hash": "e" * 64,
        "lineage": {"versions": ["v1", "v2"]},
        "lineage_hash": "f" * 64,
        "unresolved_p0": 0,
        "unresolved_p1": 0,
        "validation_status": "needs_data",
        "execution_status": "succeeded",
        "artifact_checksums": {"artifact": "0" * 64},
        "result": "PASS",
    }

    with pytest.raises(ValueError, match="complete readiness evidence"):
        release.FormalActualRunRecord.model_validate(payload)


def test_per_case_typed_input_requires_t05_t06_and_exact_shared_identity(
    tmp_path: Path,
) -> None:
    result = _actual_execution_result(tmp_path)
    artifact = _multimodal_artifact()
    valid = _formal_case_input(result, artifact)

    assert release.assess_formal_case_input(valid).eligible_for_provider_run is True
    assert valid.execution.execution_result is result
    assert valid.multimodal[0].artifact is artifact
    assert valid.logical_labels == ("Q028_REGRESSION", "FLAGSHIP")
    assert valid.shared_run is True

    missing_t05 = valid.model_copy(update={"execution": None})
    missing_t06 = valid.model_copy(update={"multimodal": ()})
    assert "T05_INPUT_REQUIRED" in release.assess_formal_case_input(
        missing_t05
    ).blockers
    assert "T06_INPUT_REQUIRED" in release.assess_formal_case_input(
        missing_t06
    ).blockers

    with pytest.raises(ValidationError, match="logical labels"):
        release.FormalCaseInput.model_validate(
            {
                **valid.model_dump(mode="python"),
                "logical_labels": ("Q028_REGRESSION", "Q028_REGRESSION"),
            }
        )
    with pytest.raises(ValidationError, match="question"):
        release.FormalCaseInput.model_validate(
            {**valid.model_dump(mode="python"), "question_id": "Q095"}
        )


def test_frozen_v1_pairing_record_enforces_identity_checksums_and_reviewer_lineage(
    tmp_path: Path,
) -> None:
    canonical_input = {"id": "Q028", "question": "controlled"}
    result = _actual_execution_result(tmp_path)
    value = _formal_case_input(
        result,
        _multimodal_artifact(),
        canonical_input=canonical_input,
    )

    eligibility = release.assess_formal_case_input(
        value,
        canonical_input=canonical_input,
    )

    assert eligibility.eligible_for_provider_run is True
    assert eligibility.pairing_authority_ready is True
    assert eligibility.pairing_authority_required is False
    assert eligibility.pairing_ready is True
    assert eligibility.pairing_record is not None
    assert eligibility.pairing_record.model_dump(mode="json") == {
        "policy": "C007_CROSS_OWNER_PAIRING_POLICY=FROZEN_V1",
        "question_id": "Q028",
        "canonical_input_sha256": release.canonical_sha256(canonical_input),
        "pairing_id": "pairing-q028-v1",
        "t05_run_id": result.execution_id,
        "t06_run_id": result.execution_id,
        "t05_source_commit": GIT_SHA,
        "t06_source_commit": GIT_SHA,
        "reviewer_run_id": result.execution_id,
        "reviewer_target_version_id": f"{result.execution_id}:v2",
        "cross_run": "SAME_RUN",
        "cross_commit": "SAME_COMMIT",
        "checksum_verification": "PASS",
        "pairing_result": "PASS",
        "fail_reason": None,
    }

    wrong_input = release.assess_formal_case_input(
        value,
        canonical_input={"id": "Q028", "question": "different"},
    )
    assert "PAIRING_CANONICAL_INPUT_SHA256_MISMATCH" in wrong_input.blockers

    checksum_failed = value.model_copy(
        update={
            "multimodal": (
                value.multimodal[0].model_copy(
                    update={"checksum_verification": "FAIL"}
                ),
            )
        }
    )
    checksum_eligibility = release.assess_formal_case_input(checksum_failed)
    assert "PAIRING_CHECKSUM_VERIFICATION_FAILED" in (
        checksum_eligibility.blockers
    )
    assert checksum_eligibility.pairing_record is not None
    assert checksum_eligibility.pairing_record.checksum_verification == "FAIL"

    reviewer = value.pairing.reviewer_feedback.model_copy(
        update={"source_run_id": "cross-run-reviewer"}
    )
    reviewer_failed = value.model_copy(
        update={
            "pairing": value.pairing.model_copy(
                update={"reviewer_feedback": reviewer}
            )
        }
    )
    reviewer_eligibility = release.assess_formal_case_input(reviewer_failed)
    assert "PAIRING_REVIEWER_LINEAGE_MISMATCH" in reviewer_eligibility.blockers


def test_frozen_v1_cross_run_is_default_deny_and_requires_case_pairing_id(
    tmp_path: Path,
) -> None:
    result = _actual_execution_result(tmp_path)
    artifact = _multimodal_artifact()
    denied = _formal_case_input(
        result,
        artifact,
        t06_source_run_id="t06-separate-run",
    )

    denied_eligibility = release.assess_formal_case_input(denied)

    assert denied_eligibility.pairing_record is not None
    assert denied_eligibility.pairing_record.cross_run == "DIFFERENT_RUN"
    assert "PAIRING_CROSS_RUN_NOT_AUTHORIZED" in denied_eligibility.blockers

    allowed = _formal_case_input(
        result,
        artifact,
        t06_source_run_id="t06-separate-run",
        allow_cross_run_pairing=True,
        pairing_id="captain-frozen-pairing-q028",
    )
    allowed_eligibility = release.assess_formal_case_input(allowed)

    assert allowed_eligibility.pairing_ready is True
    assert allowed_eligibility.pairing_record is not None
    assert allowed_eligibility.pairing_record.cross_run == "DIFFERENT_RUN"
    assert allowed_eligibility.pairing_record.pairing_result == "PASS"

    mismatched_pairing_id = allowed.model_copy(
        update={
            "multimodal": (
                allowed.multimodal[0].model_copy(
                    update={"pairing_id": "not-captain-frozen"}
                ),
            )
        }
    )
    mismatch = release.assess_formal_case_input(mismatched_pairing_id)
    assert "PAIRING_ID_MISMATCH" in mismatch.blockers


def test_frozen_v1_cross_commit_requires_exact_machine_authorization(
    tmp_path: Path,
) -> None:
    result = _actual_execution_result(tmp_path)
    artifact = _multimodal_artifact()
    t06_commit = "2" * 40
    denied = _formal_case_input(
        result,
        artifact,
        t06_source_commit=t06_commit,
    )

    denied_eligibility = release.assess_formal_case_input(
        denied,
        commit_ancestor_verifier=lambda _commit, _tip: False,
    )

    assert denied_eligibility.pairing_record is not None
    assert denied_eligibility.pairing_record.cross_commit == "DIFFERENT_COMMIT"
    assert "PAIRING_CROSS_COMMIT_NOT_AUTHORIZED" in denied_eligibility.blockers

    allowlisted = _formal_case_input(
        result,
        artifact,
        t06_source_commit=t06_commit,
        authorized_source_commits=(GIT_SHA, t06_commit),
    )
    allowlisted_eligibility = release.assess_formal_case_input(allowlisted)

    assert allowlisted_eligibility.pairing_ready is True
    assert allowlisted_eligibility.pairing_record is not None
    assert allowlisted_eligibility.pairing_record.cross_commit == (
        "DIFFERENT_COMMIT"
    )

    attested = _formal_case_input(
        result,
        artifact,
        t06_source_commit=t06_commit,
        attested_integration_tip="3" * 40,
    )
    verified: list[tuple[str, str]] = []

    def is_ancestor(commit: str, tip: str) -> bool:
        verified.append((commit, tip))
        return True

    attested_eligibility = release.assess_formal_case_input(
        attested,
        commit_ancestor_verifier=is_ancestor,
    )
    assert attested_eligibility.pairing_ready is True
    assert verified == [(GIT_SHA, "3" * 40), (t06_commit, "3" * 40)]


def test_formal_input_set_requires_one_eligible_bundle_per_frozen_case(
    tmp_path: Path,
) -> None:
    values = tuple(
        _formal_case_input(
            _actual_execution_result(tmp_path, question_id=question_id),
            _multimodal_artifact(
                artifact_id=f"chart-{question_id.casefold()}",
                source_path=f"C:/formal/{question_id}/source.csv",
            ),
            question_id=question_id,
        )
        for _, question_id, _, _ in release.FORMAL_CASE_SPECS
    )

    indexed, eligibility, ready = release._assess_formal_input_set(values)

    assert tuple(indexed) == ("Q028", "Q095", "Q045", "Q100")
    assert ready is True
    assert all(item.eligible_for_provider_run for item in eligibility.values())

    incomplete = (*values[:-1], values[0])
    _, blocked, ready = release._assess_formal_input_set(incomplete)
    assert ready is False
    assert "FORMAL_CASE_INPUT_DUPLICATE" in blocked["Q028"].blockers
    assert "FORMAL_CASE_INPUT_REQUIRED" in blocked["Q100"].blockers
    assert all(not item.eligible_for_provider_run for item in blocked.values())


def test_persisted_execution_without_public_loader_is_explicitly_blocked(
    tmp_path: Path,
) -> None:
    result = _actual_execution_result(tmp_path)

    resolution = release.resolve_public_execution_result(
        result.model_dump(mode="json")
    )

    assert resolution.execution_result is None
    assert resolution.eligible_for_c007 is False
    assert resolution.blocker == "T05_PUBLIC_LOADER_REQUIRED"


@pytest.mark.parametrize(
    ("mutator", "expected_blocker"),
    [
        (
            lambda value: value.model_copy(
                update={"execution": value.execution.model_copy(
                    update={"publicly_verified": False}
                )}
            ),
            "T05_PUBLIC_LOADER_REQUIRED",
        ),
        (
            lambda value: value.model_copy(
                update={"execution": value.execution.model_copy(
                    update={
                        "execution_result": _untrusted_execution_variant(
                            value.execution.execution_result,
                            mode="mock",
                            process_started=False,
                            exit_code=None,
                            process_reaped=False,
                            artifacts=[],
                            metrics=[],
                        )
                    }
                )}
            ),
            "T05_ACTUAL_EXECUTION_REQUIRED",
        ),
        (
            lambda value: value.model_copy(
                update={"execution": value.execution.model_copy(
                    update={
                        "execution_result": _untrusted_execution_variant(
                            value.execution.execution_result,
                            status="failed",
                            metrics=[],
                            error={
                                "code": "internal_error",
                                "message": "controlled failure",
                                "stage": "execution",
                                "retryable": False,
                            },
                        )
                    }
                )}
            ),
            "T05_SUCCESS_STATUS_REQUIRED",
        ),
        (
            lambda value: value.model_copy(
                update={"multimodal": (
                    value.multimodal[0].model_copy(
                        update={
                            "artifact": _multimodal_artifact(
                                source_type="real_fixture"
                            )
                        }
                    ),
                )}
            ),
            "T06_FIXTURE_NOT_ALLOWED",
        ),
        (
            lambda value: value.model_copy(
                update={"multimodal": (
                    value.multimodal[0].model_copy(
                        update={"provenance_complete": False}
                    ),
                )}
            ),
            "T06_PROVENANCE_REQUIRED",
        ),
        (
            lambda value: value.model_copy(update={"pairing": None}),
            "PAIRING_METADATA_REQUIRED",
        ),
    ],
)
def test_formal_eligibility_gate_rejects_unqualified_inputs(
    tmp_path: Path,
    mutator: Any,
    expected_blocker: str,
) -> None:
    value = _formal_case_input(
        _actual_execution_result(tmp_path),
        _multimodal_artifact(),
    )

    eligibility = release.assess_formal_case_input(mutator(value))

    assert eligibility.eligible_for_provider_run is False
    assert expected_blocker in eligibility.blockers


def test_dedicated_hashes_are_deterministic_sensitive_and_path_stable(
    tmp_path: Path,
) -> None:
    first_result = _actual_execution_result(tmp_path, metric_value=0.875)
    second_result = _actual_execution_result(tmp_path, metric_value=0.625)
    first_artifact = _multimodal_artifact(
        source_path="C:/temp/machine-a/run/source.csv"
    )
    same_artifact_new_root = _multimodal_artifact(
        source_path="D:/other/machine-b/run/source.csv"
    )
    changed_artifact = _multimodal_artifact(
        value="0.625",
        validation_status="needs_review",
    )

    assert release.execution_result_hash(first_result) != (
        release.execution_result_hash(second_result)
    )
    assert release.execution_summary_hash(first_result) != (
        release.execution_summary_hash(second_result)
    )
    assert release.multimodal_artifact_hash(first_artifact) == (
        release.multimodal_artifact_hash(same_artifact_new_root)
    )
    assert release.multimodal_consumer_summary_hash(first_artifact) == (
        release.multimodal_consumer_summary_hash(same_artifact_new_root)
    )
    assert release.multimodal_artifact_hash(first_artifact) != (
        release.multimodal_artifact_hash(changed_artifact)
    )
    assert release.multimodal_consumer_summary_hash(first_artifact) != (
        release.multimodal_consumer_summary_hash(changed_artifact)
    )


def test_formal_runner_passes_exact_validated_typed_inputs_to_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import app.workflow.pipeline as pipeline_module

    result = _actual_execution_result(tmp_path)
    artifact = _multimodal_artifact()
    formal_input = _formal_case_input(result, artifact)
    captured: dict[str, Any] = {}

    def controlled_pipeline(*_args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        raise RuntimeError("controlled post-bridge stop")

    monkeypatch.setattr(pipeline_module, "run_pipeline_with_state", controlled_pipeline)
    record = release.execute_formal_case(
        case_spec=release.FORMAL_CASE_SPECS[0],
        canonical_input={"id": "Q028", "question": "controlled"},
        questions_path=tmp_path / "questions.json",
        git_sha=GIT_SHA,
        config={"provider": "bailian_qwen"},
        frozen_model_policy="TIERED_ROUTE_ALLOWED",
        actual_execution_requirement="T05_EXECUTION_RESULT_REQUIRED",
        formal_input=formal_input,
    )

    assert captured["execution_result"] is result
    assert captured["multimodal_artifacts"] == (artifact,)
    assert record.status == "RUN_FAILED"


def test_invalid_formal_input_fails_before_pipeline_or_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import app.workflow.pipeline as pipeline_module

    value = _formal_case_input(
        _actual_execution_result(tmp_path),
        _multimodal_artifact(),
    ).model_copy(update={"pairing": None})
    calls = {"pipeline": 0}

    def forbidden_pipeline(*_args: Any, **_kwargs: Any) -> Any:
        calls["pipeline"] += 1
        raise AssertionError("invalid formal input reached pipeline")

    monkeypatch.setattr(pipeline_module, "run_pipeline_with_state", forbidden_pipeline)
    record = release.execute_formal_case(
        case_spec=release.FORMAL_CASE_SPECS[0],
        canonical_input={"id": "Q028", "question": "controlled"},
        questions_path=tmp_path / "questions.json",
        git_sha=GIT_SHA,
        config={"provider": "bailian_qwen"},
        frozen_model_policy="TIERED_ROUTE_ALLOWED",
        actual_execution_requirement="T05_EXECUTION_RESULT_REQUIRED",
        formal_input=value,
    )

    assert calls == {"pipeline": 0}
    assert record.status == "CASE_BLOCKED"
    assert record.failure is not None
    assert record.failure.stage == "formal_input_eligibility"
    assert "PAIRING_METADATA_REQUIRED" in record.failure.state["blockers"]


def test_context_binding_and_deterministic_impact_trace(
    tmp_path: Path,
) -> None:
    result = _actual_execution_result(tmp_path)
    artifact = _multimodal_artifact()
    formal_input = _formal_case_input(result, artifact)
    feedback = build_revision_feedback(
        execution_result=result,
        multimodal_artifacts=[artifact],
    )
    assert feedback is not None
    review = release.ReviewFeedback(
        passed=False,
        reviewer_comments=["Use actual execution and multimodal evidence."],
        critical_issues=["Missing evidence-bound metrics."],
        required_revisions=["Bind actual sources to the plan."],
        risk_level="high",
        evidence_grounding_score=0.4,
        falsifiability_score=0.4,
        reproducibility_score=0.4,
        reference_reliability_score=0.4,
    )
    previous = PlanVersion.create(
        run_id="impact-run",
        version_number=1,
        revision_iteration=1,
        experiment_design={"experiments": {"metrics": ["baseline"]}},
        review_feedback=review,
    )
    issues = issues_for_revision(review, opened_in_version=1)
    context = build_experiment_revision_context(
        previous_version=previous,
        unresolved_issues=issues,
        failure_reasons=[],
        wave_c_feedback=feedback,
        generated_at="2026-08-15T00:00:00+00:00",
    )
    hashes = release.compute_formal_input_hashes(formal_input)
    binding = release.build_revision_context_binding(
        formal_input,
        hashes,
        context,
    )
    execution_change = RevisionChange(
        change_id="change-execution",
        issue_id=issues[0].issue_id,
        reason="bind observed execution metric",
        before="baseline",
        after=f"observed score from {result.execution_id}",
        evidence_refs=[result.execution_id],
        affected_plan_section="evaluation_metrics",
        closure_status="resolved",
    )
    multimodal_change = RevisionChange(
        change_id="change-multimodal",
        issue_id=issues[0].issue_id,
        reason="bind multimodal validation",
        before="none",
        after=f"stop unless {artifact.artifact_id} remains passed",
        evidence_refs=[artifact.artifact_id],
        affected_plan_section="stopping_conditions",
        closure_status="resolved",
    )
    diff = StructuredRevisionDiff(
        changes=(execution_change, multimodal_change),
        substantive_sections=("evaluation_metrics", "stopping_conditions"),
    )
    trace = release.build_formal_impact_trace(
        formal_input=formal_input,
        input_hashes=hashes,
        context_binding=binding,
        next_prompt_hashes={
            "hypothesis_generator": "4" * 64,
            "experiment_designer": "5" * 64,
            "scientific_reviewer": "6" * 64,
        },
        v2_version_id="impact-run:v2",
        structured_diff=diff,
    )

    assert binding.execution_result_hash == hashes.execution_result_hash
    assert binding.multimodal_artifact_hashes == hashes.multimodal_artifact_hashes
    assert trace.execution_impact.impact_status == "PROVEN"
    assert trace.execution_impact.linked_change_ids == ("change-execution",)
    assert trace.multimodal_impact[0].impact_status == "PROVEN"
    assert trace.multimodal_impact[0].linked_change_ids == (
        "change-multimodal",
    )

    unproven = release.build_formal_impact_trace(
        formal_input=formal_input,
        input_hashes=hashes,
        context_binding=binding,
        next_prompt_hashes={"experiment_designer": "7" * 64},
        v2_version_id="impact-run:v2",
        structured_diff=StructuredRevisionDiff(
            changes=(
                RevisionChange(
                    change_id="unrelated",
                    issue_id=issues[0].issue_id,
                    reason="unrelated change",
                    before="one",
                    after="two",
                    evidence_refs=["EV-UNRELATED"],
                    affected_plan_section="control_groups",
                    closure_status="resolved",
                ),
            ),
            substantive_sections=("control_groups",),
        ),
    )
    assert unproven.execution_impact.impact_status == "UNPROVEN"
    assert unproven.multimodal_impact[0].impact_status == "UNPROVEN"


def test_tiered_model_route_ledger_and_unauthorized_calls() -> None:
    calls = [
        {
            "call_id": "call-fast-v1",
            "agent_name": "HypothesisGenerator",
            "provider": "bailian_qwen",
            "model_name_internal": "qwen3.6-flash",
            "mock": False,
            "status": "success",
            "started_at": "2026-08-15T00:00:00+00:00",
            "ended_at": "2026-08-15T00:00:01+00:00",
        },
        {
            "call_id": "call-plus-v1",
            "agent_name": "ExperimentDesigner",
            "provider": "bailian_qwen",
            "model_name_internal": "qwen3.7-plus",
            "mock": False,
            "status": "success",
            "started_at": "2026-08-15T00:00:01+00:00",
            "ended_at": "2026-08-15T00:00:02+00:00",
        },
        {
            "call_id": "call-max-v1",
            "agent_name": "ScientificReviewer",
            "provider": "bailian_qwen",
            "model_name_internal": "qwen3.7-max",
            "mock": False,
            "status": "success",
            "started_at": "2026-08-15T00:00:02+00:00",
            "ended_at": "2026-08-15T00:00:03+00:00",
        },
    ]
    route = release.build_model_route_audit(
        calls,
        authorized_models=release.AUTHORIZED_MODEL_IDENTITIES,
    )

    assert route.total_model_calls == 3
    assert route.per_model_call_counts == {
        "qwen3.6-flash": 1,
        "qwen3.7-max": 1,
        "qwen3.7-plus": 1,
    }
    assert route.stage_model_mapping == {
        "ExperimentDesigner": ("qwen3.7-plus",),
        "HypothesisGenerator": ("qwen3.6-flash",),
        "ScientificReviewer": ("qwen3.7-max",),
    }
    assert route.unauthorized_model_calls == 0
    assert route.qualified is True

    unauthorized_calls = copy.deepcopy(calls)
    unauthorized_calls.append(
        {
            **calls[0],
            "call_id": "call-unauthorized",
            "model_name_internal": "qwen-unauthorized",
        }
    )
    rejected = release.build_model_route_audit(
        unauthorized_calls,
        authorized_models=release.AUTHORIZED_MODEL_IDENTITIES,
    )
    assert rejected.unauthorized_model_calls == 1
    assert rejected.unauthorized_call_ids == ("call-unauthorized",)
    assert rejected.qualified is False
