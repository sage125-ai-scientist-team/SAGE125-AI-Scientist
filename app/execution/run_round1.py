"""Run and package the formal WDBC Round 1 through the controlled runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.contracts.execution import (
    ArtifactManifest,
    ArtifactRequirement,
    ExecutionResult,
    ExecutionSpec,
    MetricRecord,
    MetricRequirement,
    ResourceLimitRequest,
)
from app.execution.datasets import (
    WDBC_DATASET_ID,
    DatasetAdapter,
    get_default_dataset_registry,
)
from app.execution.registry import EntrypointRegistry
from app.execution.runner import LocalProcessRunner


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT_PATH = Path(__file__).with_name("wdbc_baseline.py")
CONFIG_PATH = REPOSITORY_ROOT / "experiments" / "flagship" / "round1_config.json"
DATASET_MANIFEST_PATH = (
    REPOSITORY_ROOT / "experiments" / "flagship" / "dataset_manifest.json"
)
ENTRYPOINT_ID = "wdbc-round1-baseline"

_ARTIFACT_DECLARATIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "balanced-accuracy",
        "output/metrics-balanced-accuracy.json",
        "metrics",
        "application/json",
    ),
    (
        "confusion-matrix",
        "output/confusion-matrix.csv",
        "table",
        "text/csv",
    ),
    (
        "malignant-recall",
        "output/metrics-malignant-recall.json",
        "metrics",
        "application/json",
    ),
    ("model", "output/model.json", "model", "application/json"),
    ("predictions", "output/predictions.csv", "table", "text/csv"),
    ("round2-plan", "output/round2-plan.json", "report", "application/json"),
    ("run-summary", "output/run-summary.json", "raw", "application/json"),
    ("summary-plot", "output/summary.svg", "plot", "image/svg+xml"),
)

_CONSUMER_UNITS: dict[str, str] = {
    "balanced-accuracy": "ratio",
    "confusion-matrix": "count",
    "malignant-recall": "ratio",
    "model": "parameter",
    "predictions": "row",
    "round2-plan": "configuration-change",
    "run-summary": "run",
    "summary-plot": "figure",
}


class FormalRunError(RuntimeError):
    """Formal execution evidence was incomplete and must not be published."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_round1_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = _read_json_object(path)
    if config.get("schema_version") != "1.0":
        raise ValueError("Round 1 config schema version must be 1.0")
    if config.get("question_id") != "Q028" or config.get("round_index") != 1:
        raise ValueError("Round 1 config must target Q028 and round 1")
    if type(config.get("seed")) is not int or config["seed"] < 0:
        raise ValueError("Round 1 seed must be a nonnegative integer")
    optimizer = config.get("optimizer")
    trigger = config.get("round2_trigger")
    if not isinstance(optimizer, Mapping) or not isinstance(trigger, Mapping):
        raise ValueError("optimizer and round2_trigger must be JSON objects")
    if config.get("required_metrics") != [
        "balanced_accuracy",
        "malignant_recall",
    ]:
        raise ValueError("Round 1 metrics must remain pinned")
    return config


def artifact_requirements() -> list[ArtifactRequirement]:
    return [
        ArtifactRequirement(
            artifact_id=artifact_id,
            relative_path=relative_path,
            kind=kind,
            media_type=media_type,
            required=True,
            max_bytes=10_000_000,
        )
        for artifact_id, relative_path, kind, media_type in _ARTIFACT_DECLARATIONS
    ]


def metric_requirements() -> list[MetricRequirement]:
    return [
        MetricRequirement(
            name="balanced_accuracy",
            unit="ratio",
            artifact_id="balanced-accuracy",
            required=True,
        ),
        MetricRequirement(
            name="malignant_recall",
            unit="ratio",
            artifact_id="malignant-recall",
            required=True,
        ),
    ]


def build_execution_spec(dataset_manifest: object) -> ExecutionSpec:
    config = load_round1_config()
    optimizer = config["optimizer"]
    trigger = config["round2_trigger"]
    return ExecutionSpec(
        spec_id="wdbc-round1-baseline-v1",
        question_id="Q028",
        round_index=1,
        mode="actual",
        entrypoint=ENTRYPOINT_ID,
        argv=[
            "--dataset",
            "datasets/wdbc.data",
            "--seed",
            str(config["seed"]),
            "--test-fraction",
            str(config["test_fraction"]),
            "--learning-rate",
            str(optimizer["learning_rate"]),
            "--iterations",
            str(optimizer["iterations"]),
            "--l2",
            str(optimizer["l2"]),
            "--decision-threshold",
            str(config["decision_threshold"]),
            "--recall-target",
            str(trigger["target"]),
            "--threshold-step",
            str(trigger["threshold_step"]),
            "--expected-sha256",
            str(dataset_manifest.sha256),
            "--expected-size-bytes",
            str(dataset_manifest.size_bytes),
        ],
        datasets=[dataset_manifest],
        required_artifacts=artifact_requirements(),
        required_metrics=metric_requirements(),
        seed=config["seed"],
        resources=ResourceLimitRequest(
            timeout_seconds=120,
            max_stdout_bytes=1_048_576,
            max_stderr_bytes=1_048_576,
            max_artifact_bytes=20_000_000,
            network_access="deny",
        ),
        environment={
            "variables": {},
            "dependency_allowlist": ["numpy", "pydantic"],
        },
        cleanup_policy="preserve",
    )


def validate_formal_result(result: ExecutionResult) -> None:
    required_truth = (
        result.status == "succeeded",
        result.mode == "actual",
        result.entrypoint_class == "scientific",
        result.process_started,
        result.process_reaped,
        not result.process_alive_after_cleanup,
        result.exit_code == 0,
        result.runner_verified,
        result.datasets_validated,
        result.artifacts_validated,
        result.metrics_validated,
        result.provenance_complete,
        result.scientific_result_usable,
        result.actual_execution,
        result.environment_fingerprint is not None,
        result.environment_fingerprint is not None
        and not result.environment_fingerprint.git_dirty,
        result.error is None,
    )
    if not all(required_truth):
        error_code = result.error.code if result.error is not None else "none"
        raise FormalRunError(
            "controlled execution did not produce trusted formal evidence "
            f"(status={result.status}, error={error_code})"
        )
    if any(item.validation_status != "valid" for item in result.artifacts):
        raise FormalRunError("one or more formal artifacts failed validation")
    if any(item.validation_status != "valid" for item in result.metrics):
        raise FormalRunError("one or more formal metrics failed validation")


def build_consumer_mapping(
    artifacts: Sequence[ArtifactManifest],
    metrics: Sequence[MetricRecord],
) -> dict[str, object]:
    """Make CSV/SVG media types and units explicit for downstream T06 wiring."""

    metric_units = {metric.artifact_id: metric.unit for metric in metrics}
    return {
        "schema_version": "1.0",
        "artifact_contract": [
            {
                "artifact_id": artifact.artifact_id,
                "kind": artifact.kind,
                "media_type": artifact.media_type,
                "unit": metric_units.get(
                    artifact.artifact_id,
                    _CONSUMER_UNITS[artifact.artifact_id],
                ),
                "validation_status": artifact.validation_status,
            }
            for artifact in sorted(artifacts, key=lambda item: item.artifact_id)
        ],
        "metric_contract": [
            {
                "artifact_id": metric.artifact_id,
                "name": metric.name,
                "source": metric.source,
                "unit": metric.unit,
                "validation_status": metric.validation_status,
            }
            for metric in sorted(metrics, key=lambda item: item.name)
        ],
    }


def _copy_validated_artifacts(
    workspace: Path,
    staging: Path,
    artifacts: Sequence[ArtifactManifest],
) -> None:
    workspace_resolved = workspace.resolve(strict=True)
    artifact_root = staging / "artifacts"
    artifact_root.mkdir(parents=True)
    for artifact in artifacts:
        if artifact.validation_status != "valid":
            raise FormalRunError(f"artifact {artifact.artifact_id} is not valid")
        source = workspace / Path(*artifact.relative_path.split("/"))
        if source.is_symlink() or not source.is_file():
            raise FormalRunError(f"artifact {artifact.artifact_id} is not regular")
        resolved = source.resolve(strict=True)
        if not resolved.is_relative_to(workspace_resolved):
            raise FormalRunError(f"artifact {artifact.artifact_id} escaped workspace")
        size = resolved.stat().st_size
        digest = _sha256(resolved)
        if size != artifact.size_bytes or digest != artifact.sha256:
            raise FormalRunError(
                f"artifact {artifact.artifact_id} integrity changed after validation"
            )
        destination = artifact_root / resolved.name
        with resolved.open("rb") as source_stream, destination.open("xb") as output:
            shutil.copyfileobj(source_stream, output)


def _package_index(staging: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for path in sorted(staging.rglob("*")):
        if not path.is_file() or path.name == "package_manifest.json":
            continue
        files.append(
            {
                "path": path.relative_to(staging).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return {"schema_version": "1.0", "files": files}


def publish_formal_package(
    package_dir: Path,
    workspace: Path,
    spec: ExecutionSpec,
    result: ExecutionResult,
) -> None:
    if package_dir.exists() or package_dir.is_symlink():
        raise FormalRunError("formal package destination already exists")
    package_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = package_dir.with_name(f".{package_dir.name}.{uuid.uuid4().hex}.part")
    staging.mkdir()
    try:
        _copy_validated_artifacts(workspace, staging, result.artifacts)
        _write_json(staging / "execution_spec.json", spec.model_dump(mode="json"))
        _write_json(staging / "execution_result.json", result.model_dump(mode="json"))
        _write_json(
            staging / "consumer_mapping.json",
            build_consumer_mapping(result.artifacts, result.metrics),
        )
        fingerprint = result.environment_fingerprint
        assert fingerprint is not None
        _write_json(
            staging / "run_metadata.json",
            {
                "schema_version": "1.0",
                "actual_execution": result.actual_execution,
                "dataset": spec.datasets[0].model_dump(mode="json"),
                "entrypoint_class": result.entrypoint_class,
                "execution_id": result.execution_id,
                "formal_round1_executed": True,
                "git_sha": fingerprint.git_sha,
                "git_dirty": fingerprint.git_dirty,
                "question_id": result.question_id,
                "round_index": result.round_index,
                "seed": result.seed,
            },
        )
        (staging / "stdout.log").write_text(
            result.stdout,
            encoding="utf-8",
            newline="\n",
        )
        (staging / "stderr.log").write_text(
            result.stderr,
            encoding="utf-8",
            newline="\n",
        )
        _write_json(staging / "package_manifest.json", _package_index(staging))
        os.replace(staging, package_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def run_formal_round1(
    *,
    cache_root: Path,
    package_dir: Path,
    offline: bool,
) -> ExecutionResult:
    load_round1_config()
    dataset_record = _read_json_object(DATASET_MANIFEST_PATH)
    expected_pin = dataset_record.get("pin")
    if not isinstance(expected_pin, Mapping) or expected_pin.get("status") != "verified":
        raise FormalRunError("dataset manifest does not carry a verified pin")

    dataset_adapter = DatasetAdapter(get_default_dataset_registry())
    resolved = dataset_adapter.fetch(
        WDBC_DATASET_ID,
        cache_root=cache_root,
        offline=offline,
    )
    dataset_manifest = resolved.to_dataset_manifest()
    if (
        dataset_manifest.sha256 != expected_pin.get("sha256")
        or dataset_manifest.size_bytes != expected_pin.get("size_bytes")
    ):
        raise FormalRunError("resolved dataset disagrees with the reviewed manifest")

    spec = build_execution_spec(dataset_manifest)
    registry = EntrypointRegistry()
    registry.register_python(
        ENTRYPOINT_ID,
        ENTRYPOINT_PATH,
        entrypoint_class="scientific",
    )
    with tempfile.TemporaryDirectory(prefix="t05-round1-") as temporary:
        managed_root = Path(temporary) / "workspaces"
        runner = LocalProcessRunner(
            registry=registry,
            managed_root=managed_root,
            dataset_resolver=dataset_adapter.build_resolver(cache_root),
        )
        result = runner.run(spec)
        validate_formal_result(result)
        workspaces = [path for path in managed_root.iterdir() if path.is_dir()]
        if len(workspaces) != 1:
            raise FormalRunError("controlled runner did not preserve exactly one workspace")
        publish_formal_package(package_dir, workspaces[0], spec, result)
        return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_formal_round1(
        cache_root=args.cache_root,
        package_dir=args.package_dir,
        offline=args.offline,
    )
    fingerprint = result.environment_fingerprint
    assert fingerprint is not None
    print(
        json.dumps(
            {
                "actual_execution": result.actual_execution,
                "artifact_count": len(result.artifacts),
                "git_sha": fingerprint.git_sha,
                "metric_count": len(result.metrics),
                "status": result.status,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
