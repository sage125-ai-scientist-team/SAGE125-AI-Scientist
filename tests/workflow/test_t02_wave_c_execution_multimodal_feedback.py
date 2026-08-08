"""T02 Wave C bounded execution and multimodal revision feedback tests."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.agents.experiment_designer import ExperimentDesignerAgent
from app.agents.hypothesis_generator import HypothesisGeneratorAgent
from app.agents.scientific_reviewer import ScientificReviewerAgent
from app.contracts.execution import (
    ArtifactRequirement,
    DatasetManifest,
    ExecutionResult,
    ExecutionSpec,
    MetricRequirement,
)
from app.contracts.multimodal import MultimodalArtifact, to_consumer_summary
from app.core.config import get_settings
from app.execution import EntrypointRegistry, LocalProcessRunner
from app.workflow import pipeline
from app.workflow.explainable_revision import (
    ExperimentRevisionContext,
    RevisionAwareExperimentDesignerAgent,
    ReviewFeedback,
    inject_revision_context,
)
from tests.helpers_questions_fixture import write_minimal_questions_fixture


def _wave_c_api() -> Any:
    try:
        return importlib.import_module("app.workflow.revision_feedback")
    except ModuleNotFoundError as exc:
        if exc.name == "app.workflow.revision_feedback":
            pytest.fail(
                "T02-C: bounded execution/multimodal feedback adapter is missing",
                pytrace=False,
            )
        raise


def _successful_execution(
    *,
    metric_count: int = 1,
    stdout: str = "raw-log-must-not-enter-prompt",
    stderr: str = "",
) -> ExecutionResult:
    metrics = [
        {
            "name": f"score-{index:03d}",
            "value": 0.875 + index / 10_000,
            "unit": "ratio",
            "source": "test",
            "artifact_id": "metrics-main",
            "validation_status": "valid",
            "round_index": 0,
        }
        for index in range(metric_count)
    ]
    return ExecutionResult.model_validate(
        {
            "execution_id": "execution-wave-c-success",
            "spec_id": "spec-wave-c-success",
            "question_id": "Q001",
            "round_index": 0,
            "mode": "test",
            "status": "succeeded",
            "entrypoint": "probe",
            "seed": 125,
            "process_started": True,
            "exit_code": 0,
            "timed_out": False,
            "process_reaped": True,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_bytes": len(stdout.encode("utf-8")),
            "stderr_bytes": len(stderr.encode("utf-8")),
            "workspace_uri": "workspace://execution-wave-c-success",
            "artifacts": [
                {
                    "artifact_id": "metrics-main",
                    "relative_path": "artifacts/metrics.json",
                    "kind": "metrics",
                    "media_type": "application/json",
                    "required": True,
                    "sha256": "1" * 64,
                    "size_bytes": 64,
                    "validation_status": "valid",
                    "collected_at": "2026-08-06T00:00:00+00:00",
                }
            ],
            "metrics": metrics,
            "cleanup_status": "preserved",
        }
    )


def _failed_execution() -> ExecutionResult:
    secret_log = "raw-timeout-log-must-not-enter-prompt"
    return ExecutionResult.model_validate(
        {
            "execution_id": "execution-wave-c-failed",
            "spec_id": "spec-wave-c-failed",
            "question_id": "Q001",
            "round_index": 1,
            "parent_execution_id": "execution-wave-c-success",
            "mode": "test",
            "status": "timed_out",
            "entrypoint": "probe",
            "seed": 125,
            "process_started": True,
            "exit_code": None,
            "timed_out": True,
            "process_reaped": True,
            "stderr": secret_log,
            "stderr_bytes": len(secret_log.encode("utf-8")),
            "cleanup_status": "succeeded",
            "error": {
                "code": "timeout",
                "message": "wall-clock limit exceeded while evaluating fold 4",
                "stage": "execution",
                "retryable": True,
            },
        }
    )


def _multimodal_artifact(
    artifact_id: str = "chart-wave-c",
    *,
    rows: int = 2,
    source_path: str = "fixtures/chart-page-7.csv",
    units: list[str] | None = None,
    confidence: float = 0.93,
    row_value: str = "0.875",
) -> MultimodalArtifact:
    return MultimodalArtifact.model_validate(
        {
            "artifact_id": artifact_id,
            "modality": "chart",
            "provenance": {
                "source_path": source_path,
                "source_type": "synthetic_fixture",
                "page": 7,
                "bbox": {"x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0},
            },
            "units": ["ratio"] if units is None else units,
            "column_units": [{"column": "score", "unit": "ratio"}],
            "axes": [
                {
                    "name": "y",
                    "label": "score",
                    "unit": "ratio",
                    "min_value": 0.0,
                    "max_value": 1.0,
                }
            ],
            "legend": ["candidate"],
            "data": {
                "headers": ["candidate", "score"],
                "rows": [[f"candidate-{index}", row_value] for index in range(rows)],
            },
            "confidence": confidence,
            "validation_status": "passed",
        }
    )


def _review_result() -> dict[str, Any]:
    return {
        "passed": False,
        "reviewer_comments": ["Revise using observed execution evidence."],
        "critical_issues": ["The stopping rule ignores the failed fold."],
        "required_revisions": ["Use the validated metric and chart provenance."],
        "risk_level": "high",
        "evidence_grounding_score": 0.5,
        "falsifiability_score": 0.4,
        "reproducibility_score": 0.5,
        "reference_reliability_score": 0.6,
    }


def _revision_context(feedback: Any | None) -> ExperimentRevisionContext:
    review = ReviewFeedback.from_review_result(_review_result())
    return ExperimentRevisionContext(
        previous_plan={"experiment_design": {"experiments": {}}},
        previous_plan_version={"version_id": "wave-c-context:v1"},
        parent_version_id="wave-c-context:v1",
        lineage=["wave-c-context:v1", "wave-c-context:v2"],
        reviewer_feedback=review,
        wave_c_feedback=feedback,
    )


def _prompt_input(feedback: Any) -> dict[str, Any]:
    return inject_revision_context(
        {
            "revision_iteration": 2,
            "review_result": _review_result(),
            "question_type": "general_scientific_unknown",
        },
        _revision_context(feedback),
    )


def _actual_execution_result(tmp_path: Path) -> ExecutionResult:
    dataset_bytes = b"sample,value\nalpha,1\nbeta,2\n"
    artifact_bytes = b'{"metric":{"name":"score","unit":"ratio","value":0.875}}\n'
    source_root = tmp_path / "source-data"
    source_root.mkdir()
    source = source_root / "dataset.csv"
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
            "spec_id": "spec-wave-c-actual",
            "question_id": "Q001",
            "round_index": 0,
            "mode": "actual",
            "entrypoint": "wave-c-probe",
            "argv": [
                "artifact",
                "artifacts/metrics.json",
                "--metric-name",
                "score",
                "--metric-value",
                "0.875",
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
        managed_root=tmp_path / "managed-root",
        dataset_resolver=lambda _manifest: source,
        dependency_version_provider=lambda names: {
            name: {"pydantic": "2.12.4", "pytest": "9.0.3"}[name]
            for name in names
        },
        git_provenance_provider=lambda: {
            "commit_sha": "1" * 40,
            "dirty": False,
            "available": True,
        },
    ).run(spec)
    assert result.actual_execution is True
    return result


def test_T02_C_001_success_execution_summary_is_bounded_and_sourced() -> None:
    api = _wave_c_api()
    projection = api.build_revision_feedback(
        execution_result=_successful_execution()
    )

    assert projection.execution.status == "succeeded"
    assert projection.execution.execution_id == "execution-wave-c-success"
    assert projection.execution.metrics[0].unit == "ratio"
    assert projection.execution.metrics[0].source == "test"
    assert projection.execution.metrics[0].validation_status == "valid"


def test_T02_C_002_failure_reason_enters_the_next_round_message() -> None:
    api = _wave_c_api()
    projection = api.build_revision_feedback(execution_result=_failed_execution())
    payload = json.loads(
        RevisionAwareExperimentDesignerAgent()
        .build_messages(_prompt_input(projection))[1]["content"]
    )
    failure = payload["revision_context"]["wave_c_feedback"]["execution"]["failure"]

    assert failure == {
        "code": "timeout",
        "message": "wall-clock limit exceeded while evaluating fold 4",
        "stage": "execution",
        "retryable": True,
    }


def test_T02_C_003_multimodal_uses_the_frozen_consumer_summary() -> None:
    api = _wave_c_api()
    artifact = _multimodal_artifact()
    expected = to_consumer_summary(artifact)
    projection = api.build_revision_feedback(multimodal_artifacts=[artifact])
    observed = projection.multimodal[0]

    assert observed.artifact_id == expected.artifact_id
    assert observed.source_path == expected.source_path
    assert observed.source_type == expected.source_type
    assert observed.page == expected.page
    assert observed.units == tuple(expected.units)
    assert observed.confidence == expected.confidence
    assert observed.validation_status == expected.validation_status
    assert observed.header_count == expected.header_count
    assert observed.row_count == expected.row_count


def test_T02_C_004_raw_rows_logs_and_binary_payloads_are_excluded() -> None:
    api = _wave_c_api()
    binary_marker = "data:application/octet-stream;base64,QUJDREVGRw=="
    projection = api.build_revision_feedback(
        execution_result=_successful_execution(
            stdout="stdout-secret-marker",
            stderr="stderr-secret-marker",
        ),
        multimodal_artifacts=[
            _multimodal_artifact(rows=100, row_value=binary_marker)
        ],
    )
    serialized = json.dumps(projection.model_dump(mode="json"), ensure_ascii=False)

    for forbidden in (
        "stdout-secret-marker",
        "stderr-secret-marker",
        binary_marker,
        "QUJDREVGRw==",
        '"rows"',
        '"axes"',
        '"legend"',
    ):
        assert forbidden not in serialized


def test_T02_C_005_large_inputs_have_explicit_caps_and_drop_counts() -> None:
    api = _wave_c_api()
    artifacts = [
        _multimodal_artifact(
            artifact_id=f"chart-{index:03d}",
            rows=4_000,
            units=[f"unit-{unit_index}" for unit_index in range(40)],
        )
        for index in range(api.MAX_MULTIMODAL_ARTIFACTS + 5)
    ]
    projection = api.build_revision_feedback(
        execution_result=_successful_execution(
            metric_count=api.MAX_EXECUTION_METRICS + 5
        ),
        multimodal_artifacts=artifacts,
    )
    serialized = json.dumps(
        projection.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )

    assert len(projection.execution.metrics) == api.MAX_EXECUTION_METRICS
    assert len(projection.multimodal) == api.MAX_MULTIMODAL_ARTIFACTS
    assert projection.dropped_counts.execution_metrics == 5
    assert projection.dropped_counts.multimodal_artifacts == 5
    assert projection.dropped_counts.multimodal_units > 0
    assert len(serialized.encode("utf-8")) <= api.MAX_PROJECTION_BYTES


def test_T02_C_006_feedback_changes_input_fingerprint_and_prompt_hash() -> None:
    api = _wave_c_api()
    first = api.build_revision_feedback(execution_result=_successful_execution())
    second = api.build_revision_feedback(execution_result=_failed_execution())
    first_input = _prompt_input(first)
    second_input = _prompt_input(second)
    agent = RevisionAwareExperimentDesignerAgent()

    first_hash = agent.hash_prompt(
        agent.system_prompt,
        agent.safe_summarize_input(first_input),
    )
    second_hash = agent.hash_prompt(
        agent.system_prompt,
        agent.safe_summarize_input(second_input),
    )

    assert first.fingerprint != second.fingerprint
    assert first_input["revision_feedback_fingerprint"] == first.fingerprint
    assert second_input["revision_feedback_fingerprint"] == second.fingerprint
    assert first_hash != second_hash


def test_T02_C_007_actual_results_drive_a_substantive_pipeline_revision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    api = _wave_c_api()
    actual = _actual_execution_result(tmp_path)
    chart = _multimodal_artifact()
    questions = write_minimal_questions_fixture(tmp_path / "questions.json")
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(questions))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("MOCK_REVIEW_FAIL", "true")
    monkeypatch.setattr(pipeline, "generate_run_id", lambda: "wave-c-production")
    get_settings.cache_clear()

    captured: dict[str, dict[str, Any]] = {}
    original_hypothesis = HypothesisGeneratorAgent.run
    original_experiment = ExperimentDesignerAgent.run
    original_reviewer = ScientificReviewerAgent.run

    def capture_hypothesis(self, input_data, state, step_index=0):
        if input_data.get("revision_iteration") == 2:
            captured["hypothesis"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
        return original_hypothesis(self, input_data, state, step_index)

    def adapt_experiment(self, input_data, state, step_index=0):
        result = original_experiment(self, input_data, state, step_index)
        if input_data.get("revision_iteration") == 2:
            captured["experiment"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
            feedback = input_data["revision_context"]["wave_c_feedback"]
            metric = feedback["execution"]["metrics"][0]
            visual = feedback["multimodal"][0]
            experiments = copy.deepcopy(result["experiments"])
            experiments["metrics"] = [
                *experiments["metrics"],
                (
                    f"observed {metric['name']}={metric['value']} {metric['unit']} "
                    f"from {feedback['execution']['execution_id']}"
                ),
            ]
            experiments["validation_protocol"] = (
                f"Stop if artifact {visual['artifact_id']} at "
                f"{visual['source_path']} is not {visual['validation_status']}."
            )
            experiments["stopping_conditions"] = [
                (
                    f"Stop when {visual['artifact_id']} validation status is not "
                    f"{visual['validation_status']}."
                )
            ]
            result["experiments"] = experiments
        return result

    def capture_reviewer(self, input_data, state, step_index=0):
        if input_data.get("revision_iteration") == 2:
            captured["reviewer"] = json.loads(
                self.build_messages(copy.deepcopy(input_data))[1]["content"]
            )
        return original_reviewer(self, input_data, state, step_index)

    monkeypatch.setattr(HypothesisGeneratorAgent, "run", capture_hypothesis)
    monkeypatch.setattr(ExperimentDesignerAgent, "run", adapt_experiment)
    monkeypatch.setattr(ScientificReviewerAgent, "run", capture_reviewer)
    try:
        _plan, state = pipeline.run_pipeline_with_state(
            "Q001",
            mock_mode=True,
            execution_result=actual,
            multimodal_artifacts=[chart],
        )
    finally:
        get_settings.cache_clear()

    assert set(captured) == {"hypothesis", "experiment", "reviewer"}
    for value in captured.values():
        feedback = value["revision_context"]["wave_c_feedback"]
        assert feedback["execution"]["actual_execution"] is True
        assert feedback["multimodal"][0]["artifact_id"] == "chart-wave-c"
    assert any(
        "observed score=0.875 ratio" in metric
        for metric in state.experiment_design["experiments"]["metrics"]
    )
    audit = next(
        event["revision_audit"]
        for event in state.agent_trace
        if event.get("revision_audit")
    )
    assert "evaluation_metrics" in audit["substantive_sections"]
    assert "stopping_conditions" in audit["substantive_sections"]
    assert api.MAX_PROJECTION_BYTES > 0


def test_T02_C_008_provenance_and_trace_identifiers_are_preserved() -> None:
    api = _wave_c_api()
    execution = _successful_execution()
    artifact = _multimodal_artifact()
    projection = api.build_revision_feedback(
        execution_result=execution,
        multimodal_artifacts=[artifact],
    )
    payload = projection.model_dump(mode="json")

    assert payload["execution"]["execution_id"] == execution.execution_id
    assert payload["execution"]["spec_id"] == execution.spec_id
    assert payload["execution"]["question_id"] == execution.question_id
    assert payload["execution"]["artifacts"][0]["artifact_id"] == "metrics-main"
    assert payload["execution"]["artifacts"][0]["sha256"] == "1" * 64
    assert payload["multimodal"][0]["artifact_id"] == artifact.artifact_id
    assert payload["multimodal"][0]["source_path"] == (
        artifact.provenance.source_path
    )
    assert payload["multimodal"][0]["confidence"] == artifact.confidence
    assert payload["multimodal"][0]["validation_status"] == "passed"


def test_T02_C_009_missing_optional_inputs_preserve_wave_a_b_shape() -> None:
    api = _wave_c_api()
    assert api.build_revision_feedback() is None
    context = _revision_context(None)
    payload = inject_revision_context(
        {"revision_iteration": 2, "review_result": _review_result()},
        context,
    )

    assert "revision_feedback_fingerprint" not in payload
    assert "wave_c_feedback" not in payload["revision_context"]
    assert ReviewFeedback.from_review_result(payload["review_result"])


def test_T02_C_010_invalid_conflicting_or_forged_inputs_are_rejected() -> None:
    api = _wave_c_api()
    with pytest.raises(TypeError):
        api.build_revision_feedback(
            execution_result={
                "execution_id": "fabricated",
                "actual_execution": True,
            }
        )

    first = _multimodal_artifact(artifact_id="duplicate")
    conflicting = _multimodal_artifact(
        artifact_id="duplicate",
        source_path="fixtures/conflicting-source.csv",
    )
    with pytest.raises(ValueError, match="duplicate"):
        api.build_revision_feedback(multimodal_artifacts=[first, conflicting])

    forged = _successful_execution().model_dump(mode="python")
    forged["actual_execution"] = True
    with pytest.raises(ValidationError, match="runner-owned truth"):
        ExecutionResult.model_validate(forged)

    projection = api.build_revision_feedback(execution_result=_successful_execution())
    forged_projection = projection.model_dump(mode="python")
    forged_projection["fingerprint"] = "0" * 64
    with pytest.raises(ValidationError, match="fingerprint"):
        api.RevisionFeedbackProjection.model_validate(forged_projection)


def test_T02_C_011_projection_and_fingerprint_are_deterministic() -> None:
    api = _wave_c_api()
    first = _multimodal_artifact("artifact-b")
    second = _multimodal_artifact("artifact-a")

    projection_a = api.build_revision_feedback(
        execution_result=_successful_execution(metric_count=3),
        multimodal_artifacts=[first, second],
    )
    projection_b = api.build_revision_feedback(
        execution_result=_successful_execution(metric_count=3),
        multimodal_artifacts=[second, first],
    )

    assert projection_a == projection_b
    assert projection_a.fingerprint == projection_b.fingerprint
    assert projection_a.model_dump_json() == projection_b.model_dump_json()


def test_T02_C_012_missing_units_or_confidence_are_never_invented() -> None:
    api = _wave_c_api()
    artifact = _multimodal_artifact(units=[], confidence=0.0)
    projection = api.build_revision_feedback(multimodal_artifacts=[artifact])

    assert projection.multimodal[0].units == ()
    assert projection.multimodal[0].confidence == 0.0
    assert "unknown" not in projection.model_dump_json().lower()

    invalid = artifact.model_dump(mode="python")
    invalid.pop("confidence")
    with pytest.raises(ValidationError):
        MultimodalArtifact.model_validate(invalid)
