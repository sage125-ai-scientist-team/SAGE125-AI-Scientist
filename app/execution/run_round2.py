"""Controlled WDBC Round 2 threshold-sensitivity execution and evidence checks.

Round 2 is a paired post-hoc sensitivity analysis over the committed Round 1
holdout.  It changes only the decision threshold from 0.5 to 0.4.  Persisted
Round 1 runner truth is verified as immutable parent evidence, but is never
re-attested by this module.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import sys
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

if __package__ in {None, ""}:  # Permit the registered file to run as a script.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.contracts.execution import (
    ArtifactManifest,
    ArtifactRequirement,
    DatasetManifest,
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
from app.execution.security import (
    SecurityViolation,
    ensure_regular_file,
    ensure_secure_root,
    file_sha256,
    read_verified_bytes,
    secure_relative_path,
)
from app.execution.wdbc_baseline import (
    BaselineConfig,
    _evaluate,
    _fit_logistic,
    _probabilities,
    load_wdbc,
    stratified_split,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROUND1_PACKAGE_PATH = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "round1"
ROUND2_CONFIG_PATH = REPOSITORY_ROOT / "experiments" / "flagship" / "round2_config.json"
DATASET_MANIFEST_PATH = REPOSITORY_ROOT / "experiments" / "flagship" / "dataset_manifest.json"
ENTRYPOINT_PATH = Path(__file__).resolve()
ENTRYPOINT_ID = "wdbc-round2-threshold-sensitivity"

ROUND1_EXECUTION_ID = "execution-5577816b92ac434c99b9c0ffcda21660"
ROUND1_SOURCE_SHA = "18c86f1e1963b13cbed09356201d92f38a2a2880"
DATASET_SHA256 = "d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a"
DATASET_SIZE_BYTES = 124103
MODEL_SHA256 = "ce343d6a617a2bda65405c1372a2454a4140e82725a09c885913fd511590aca8"
PREDICTIONS_SHA256 = "05008c6176640bbb1134e3f113d985543aa4819ba455a8e610d7e908a8e9275b"

_MAX_EVIDENCE_FILE_BYTES = 20_000_000
_FLOAT_POLICY = {"atol": 1e-12, "rtol": 1e-12, "equal_nan": False}
_ROUND1_FILES = {
    "artifacts/confusion-matrix.csv",
    "artifacts/metrics-balanced-accuracy.json",
    "artifacts/metrics-malignant-recall.json",
    "artifacts/model.json",
    "artifacts/predictions.csv",
    "artifacts/round2-plan.json",
    "artifacts/run-summary.json",
    "artifacts/summary.svg",
    "consumer_mapping.json",
    "execution_result.json",
    "execution_spec.json",
    "run_metadata.json",
    "stderr.log",
    "stdout.log",
}
_ARTIFACT_DECLARATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("balanced-accuracy", "output/metrics-balanced-accuracy.json", "metrics", "application/json"),
    ("confusion-matrix", "output/confusion-matrix.csv", "table", "text/csv"),
    ("false-negative-rate", "output/metrics-false-negative-rate.json", "metrics", "application/json"),
    ("malignant-recall", "output/metrics-malignant-recall.json", "metrics", "application/json"),
    ("model", "output/model.json", "model", "application/json"),
    ("predictions", "output/predictions.csv", "table", "text/csv"),
    ("run-summary", "output/run-summary.json", "raw", "application/json"),
    ("summary-plot", "output/summary.svg", "plot", "image/svg+xml"),
)
_CANONICAL_CONFIG: dict[str, Any] = {
    "schema_version": "1.0",
    "question_id": "Q028",
    "round_index": 2,
    "based_on_round": 1,
    "evaluation_scope": "paired_post_hoc_holdout_sensitivity",
    "control_change": {"field": "decision_threshold", "from": 0.5, "to": 0.4},
    "seed": 125,
    "test_fraction": 0.2,
    "optimizer": {
        "name": "full_batch_logistic_regression",
        "learning_rate": 0.05,
        "iterations": 2000,
        "l2": 0.001,
    },
    "required_metrics": [
        "balanced_accuracy",
        "malignant_recall",
        "false_negative_rate",
    ],
    "robustness": {"fold_count": 5, "seed": 125, "thresholds": [0.5, 0.4]},
}
_ROUND2_PACKAGE_FILES = {
    "execution_spec.json",
    "execution_result.json",
    "run_metadata.json",
    "package_manifest.json",
    "consumer_mapping.json",
    "stdout.log",
    "stderr.log",
    "artifacts/metrics-balanced-accuracy.json",
    "artifacts/metrics-false-negative-rate.json",
    "artifacts/metrics-malignant-recall.json",
    "artifacts/confusion-matrix.csv",
    "artifacts/predictions.csv",
    "artifacts/model.json",
    "artifacts/run-summary.json",
    "artifacts/summary.svg",
    "comparison/two-round-comparison.json",
    "comparison/two-round-comparison.csv",
    "comparison/changed-predictions.csv",
    "comparison/two-round-comparison.svg",
    "comparison/control-invariants.json",
    "robustness/robustness-folds.csv",
    "robustness/robustness-summary.json",
    "robustness/robustness-comparison.svg",
    "reproduction/reproduction_report.json",
    "reproduction/reproduction_report.md",
    "reproduction/environment_fingerprint.json",
    "reproduction/artifact_comparison.json",
}
_SCIENTIFIC_ROUND2_FILES = {
    relative
    for relative in _ROUND2_PACKAGE_FILES
    if relative.startswith(("artifacts/", "comparison/", "robustness/"))
}
_FIXTURE_LABELS = ["SYNTHETIC_TEST_FIXTURE_ONLY", "NOT_FORMAL_SCIENTIFIC_EVIDENCE"]


class Round2ConfigError(ValueError):
    """The Round 2 configuration is missing, malformed, or out of policy."""


class Round2EvidenceError(RuntimeError):
    """Required immutable parent or formal execution evidence is invalid."""


class Round2ControlDriftError(Round2EvidenceError):
    """A Round 2 scientific control other than the threshold changed."""


class Round2ReproductionError(Round2EvidenceError):
    """Two Round 2 packages disagree on scientific evidence."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        allow_inf_nan=False,
    )


class _ControlChange(_StrictModel):
    field: Literal["decision_threshold"]
    from_threshold: float = Field(alias="from")
    to: float

    @field_validator("from_threshold", "to")
    @classmethod
    def _finite_threshold(cls, value: float) -> float:
        if not math.isfinite(value) or not 0.0 < value < 1.0:
            raise ValueError("threshold must be finite and strictly between zero and one")
        return value


class _Optimizer(_StrictModel):
    name: Literal["full_batch_logistic_regression"]
    learning_rate: float
    iterations: int
    l2: float

    @field_validator("learning_rate", "l2")
    @classmethod
    def _finite_optimizer_number(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("optimizer values must be finite")
        return value


class _Robustness(_StrictModel):
    fold_count: int
    seed: int
    thresholds: list[float]

    @field_validator("thresholds")
    @classmethod
    def _finite_thresholds(cls, value: list[float]) -> list[float]:
        if len(value) != 2 or any(
            not math.isfinite(item) or not 0.0 < item < 1.0 for item in value
        ):
            raise ValueError("robustness thresholds must be finite probabilities")
        return value


class _Round2Config(_StrictModel):
    schema_version: Literal["1.0"]
    question_id: Literal["Q028"]
    round_index: Literal[2]
    based_on_round: Literal[1]
    evaluation_scope: Literal["paired_post_hoc_holdout_sensitivity"]
    control_change: _ControlChange
    seed: int
    test_fraction: float
    optimizer: _Optimizer
    required_metrics: list[
        Literal[
            "balanced_accuracy",
            "malignant_recall",
            "false_negative_rate",
        ]
    ]
    robustness: _Robustness

    @field_validator("test_fraction")
    @classmethod
    def _finite_fraction(cls, value: float) -> float:
        if not math.isfinite(value) or not 0.0 < value < 1.0:
            raise ValueError("test fraction must be finite and between zero and one")
        return value


_ExecutionEnvironmentBase = ExecutionSpec.model_fields["environment"].annotation


class _Round2ExecutionEnvironment(_ExecutionEnvironmentBase):
    """Execution environment view with the contract's mapping-style access."""

    def __getitem__(self, key: str) -> Any:
        if key not in {"variables", "dependency_allowlist"}:
            raise KeyError(key)
        return getattr(self, key)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _strict_json_bytes(raw: bytes) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 byte-order marks are forbidden")
    value = json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda _token: (_ for _ in ()).throw(
            ValueError("non-finite JSON number")
        ),
    )
    if not isinstance(value, dict):
        raise ValueError("JSON document must contain an object")
    return value


def _verified_unpinned_bytes(path: Path, *, stage: str) -> bytes:
    digest = file_sha256(
        path,
        max_bytes=_MAX_EVIDENCE_FILE_BYTES,
        stage=stage,
        invalid_code="artifact_invalid",
    )
    return read_verified_bytes(
        path,
        expected_sha256=digest.sha256,
        expected_size=digest.size_bytes,
        max_bytes=_MAX_EVIDENCE_FILE_BYTES,
        stage=stage,
        invalid_code="artifact_invalid",
    )


def load_round2_config(path: Path = ROUND2_CONFIG_PATH) -> dict[str, Any]:
    """Load the one reviewed Round 2 configuration with strict JSON semantics."""

    try:
        parsed = _strict_json_bytes(_verified_unpinned_bytes(Path(path), stage="round2-config"))
        _Round2Config.model_validate(parsed)
        if parsed != _CANONICAL_CONFIG:
            raise ValueError("configuration differs from the reviewed control")
    except (OSError, UnicodeError, ValueError, ValidationError, SecurityViolation):
        raise Round2ConfigError("Round 2 configuration is missing or invalid") from None
    return parsed


def _load_integrity_package(
    package_dir: Path,
    *,
    expected_files: set[str] | None = None,
    error_type: type[Round2EvidenceError] = Round2EvidenceError,
) -> tuple[Path, dict[str, bytes]]:
    try:
        root = ensure_secure_root(package_dir, create=False, stage="evidence")
        manifest = _strict_json_bytes(
            _verified_unpinned_bytes(root / "package_manifest.json", stage="evidence")
        )
        if set(manifest) != {"schema_version", "files"} or manifest["schema_version"] != "1.0":
            raise ValueError("manifest shape")
        entries = manifest["files"]
        if not isinstance(entries, list):
            raise ValueError("manifest entries")
        indexed: dict[str, tuple[str, int]] = {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size_bytes"}:
                raise ValueError("manifest entry shape")
            relative = entry["path"]
            digest = entry["sha256"]
            size = entry["size_bytes"]
            if (
                not isinstance(relative, str)
                or relative in indexed
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
                or type(size) is not int
                or size < 0
                or size > _MAX_EVIDENCE_FILE_BYTES
            ):
                raise ValueError("manifest entry value")
            indexed[relative] = (digest, size)
        if expected_files is not None and set(indexed) != expected_files:
            raise ValueError("manifest coverage")

        actual: set[str] = set()
        for candidate in root.rglob("*"):
            if candidate.is_symlink():
                raise ValueError("indirection")
            if candidate.is_file():
                actual.add(candidate.relative_to(root).as_posix())
        if actual != set(indexed) | {"package_manifest.json"}:
            raise ValueError("unindexed package content")

        payloads: dict[str, bytes] = {}
        for relative, (digest, size) in indexed.items():
            source = secure_relative_path(
                root,
                relative,
                must_exist=True,
                require_file=True,
                stage="evidence",
                invalid_code="artifact_invalid",
            )
            payloads[relative] = read_verified_bytes(
                source,
                expected_sha256=digest,
                expected_size=size,
                max_bytes=_MAX_EVIDENCE_FILE_BYTES,
                containment_root=root,
                stage="evidence",
                invalid_code="artifact_invalid",
            )
        return root, payloads
    except (OSError, UnicodeError, ValueError, SecurityViolation):
        raise error_type("evidence package manifest or content is invalid") from None


def _json_payload(
    payloads: Mapping[str, bytes],
    relative: str,
    *,
    error_type: type[Round2EvidenceError] = Round2EvidenceError,
) -> dict[str, Any]:
    try:
        return _strict_json_bytes(payloads[relative])
    except (KeyError, UnicodeError, ValueError):
        raise error_type("required JSON evidence is invalid") from None


def _prediction_rows(
    raw: bytes,
    *,
    error_type: type[Round2EvidenceError] = Round2EvidenceError,
) -> list[dict[str, Any]]:
    expected_header = [
        "record_ordinal",
        "actual_label",
        "predicted_label",
        "malignant_probability",
    ]
    try:
        if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
            raise ValueError("invalid encoding marker")
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8", errors="strict"), newline=""))
        if reader.fieldnames != expected_header:
            raise ValueError("prediction header")
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for item in reader:
            if set(item) != set(expected_header) or None in item:
                raise ValueError("prediction row")
            ordinal = int(item["record_ordinal"])
            probability = float(item["malignant_probability"])
            if (
                ordinal in seen
                or ordinal < 0
                or item["actual_label"] not in {"B", "M"}
                or item["predicted_label"] not in {"B", "M"}
                or not math.isfinite(probability)
                or not 0.0 <= probability <= 1.0
            ):
                raise ValueError("prediction value")
            seen.add(ordinal)
            rows.append(
                {
                    "record_ordinal": ordinal,
                    "actual_label": item["actual_label"],
                    "predicted_label": item["predicted_label"],
                    "malignant_probability": probability,
                }
            )
        if not rows:
            raise ValueError("empty predictions")
        return rows
    except (UnicodeError, ValueError, TypeError, csv.Error):
        raise error_type("predictions evidence is invalid") from None


def _same_number(left: Any, right: Any) -> bool:
    return (
        type(left) in {int, float}
        and type(right) in {int, float}
        and math.isfinite(float(left))
        and math.isfinite(float(right))
        and math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    )


def _same_numeric_sequence(left: Any, right: Any) -> bool:
    return (
        isinstance(left, list)
        and isinstance(right, list)
        and len(left) == len(right)
        and all(_same_number(a, b) for a, b in zip(left, right, strict=True))
    )


def load_round1_reference(package_dir: Path = ROUND1_PACKAGE_PATH) -> dict[str, Any]:
    """Verify and load the immutable Round 1 parent without restoring runner trust."""

    _, payloads = _load_integrity_package(Path(package_dir), expected_files=_ROUND1_FILES)
    try:
        spec = _json_payload(payloads, "execution_spec.json")
        result = _json_payload(payloads, "execution_result.json")
        metadata = _json_payload(payloads, "run_metadata.json")
        model = _json_payload(payloads, "artifacts/model.json")
        summary = _json_payload(payloads, "artifacts/run-summary.json")
        plan = _json_payload(payloads, "artifacts/round2-plan.json")
        predictions = _prediction_rows(payloads["artifacts/predictions.csv"])

        trusted = (
            result.get("execution_id") == ROUND1_EXECUTION_ID
            and result.get("question_id") == "Q028"
            and result.get("round_index") == 1
            and result.get("parent_execution_id") is None
            and result.get("mode") == "actual"
            and result.get("status") == "succeeded"
            and result.get("actual_execution") is True
            and result.get("runner_verified") is True
            and result.get("scientific_result_usable") is True
            and result.get("datasets_validated") is True
            and result.get("artifacts_validated") is True
            and result.get("metrics_validated") is True
            and result.get("provenance_complete") is True
            and result.get("process_started") is True
            and result.get("process_reaped") is True
            and result.get("process_alive_after_cleanup") is False
            and result.get("exit_code") == 0
            and result.get("error") is None
            and isinstance(result.get("environment_fingerprint"), dict)
            and result["environment_fingerprint"].get("git_dirty") is False
            and result["environment_fingerprint"].get("git_sha") == ROUND1_SOURCE_SHA
            and metadata.get("formal_round1_executed") is True
            and metadata.get("git_dirty") is False
            and metadata.get("git_sha") == ROUND1_SOURCE_SHA
        )
        if not trusted:
            raise ValueError("persisted parent trust")
        if spec.get("question_id") != "Q028" or spec.get("round_index") != 1:
            raise ValueError("parent specification identity")

        datasets = (spec.get("datasets"), result.get("datasets"))
        if not all(isinstance(items, list) and len(items) == 1 for items in datasets):
            raise ValueError("parent dataset count")
        dataset = datasets[0][0]
        if dataset != datasets[1][0] or dataset != metadata.get("dataset"):
            raise ValueError("parent dataset disagreement")
        pin = {
            "dataset_id": WDBC_DATASET_ID,
            "sha256": DATASET_SHA256,
            "size_bytes": DATASET_SIZE_BYTES,
        }
        if any(dataset.get(key) != value for key, value in pin.items()):
            raise ValueError("parent dataset pin")

        artifact_index = {
            item.get("artifact_id"): item
            for item in result.get("artifacts", [])
            if isinstance(item, dict)
        }
        if (
            artifact_index.get("model", {}).get("sha256") != MODEL_SHA256
            or artifact_index.get("predictions", {}).get("sha256") != PREDICTIONS_SHA256
            or artifact_index.get("model", {}).get("validation_status") != "valid"
            or artifact_index.get("predictions", {}).get("validation_status") != "valid"
        ):
            raise ValueError("parent artifact pins")
        if len(predictions) != 113 or any(
            row["predicted_label"]
            != ("M" if row["malignant_probability"] >= 0.5 else "B")
            for row in predictions
        ):
            raise ValueError("parent predictions")

        expected_parameters = {
            "seed": 125,
            "test_fraction": 0.2,
            "learning_rate": 0.05,
            "iterations": 2000,
            "l2": 0.001,
            "decision_threshold": 0.5,
        }
        if (
            model.get("algorithm") != "standardized_full_batch_logistic_regression"
            or model.get("parameters") != expected_parameters
            or summary.get("parameters") != expected_parameters
        ):
            raise ValueError("parent model controls")
        expected_plan = {
            "schema_version": "1.0",
            "based_on_round": 1,
            "evidence": {"malignant_recall": 0.9285714285714286, "target": 0.95},
            "change": {"field": "decision_threshold", "from": 0.5, "to": 0.4},
            "fixed_controls": {"seed": 125, "test_fraction": 0.2},
            "rationale": "Round 1 malignant recall was below the predeclared target.",
            "formal_round2_executed": False,
        }
        if plan != expected_plan:
            raise ValueError("parent trigger plan")
    except (KeyError, TypeError, ValueError, Round2EvidenceError):
        raise Round2EvidenceError("Round 1 parent evidence is invalid") from None

    return {
        "execution_spec": spec,
        "execution_result": result,
        "run_metadata": metadata,
        "dataset_manifest": dataset,
        "model": model,
        "run_summary": summary,
        "round2_plan": plan,
        "predictions": predictions,
        "evidence_origin": "persisted_round1_reference_only",
        "runner_truth_restored": False,
    }


def _evaluate_prediction_rows(
    rows: Sequence[Mapping[str, Any]], threshold: float
) -> tuple[dict[str, int], dict[str, float]]:
    confusion = {
        "true_negative": 0,
        "false_positive": 0,
        "false_negative": 0,
        "true_positive": 0,
    }
    for row in rows:
        actual = row["actual_label"]
        predicted = "M" if float(row["malignant_probability"]) >= threshold else "B"
        key = {
            ("B", "B"): "true_negative",
            ("B", "M"): "false_positive",
            ("M", "B"): "false_negative",
            ("M", "M"): "true_positive",
        }[(actual, predicted)]
        confusion[key] += 1
    malignant_total = confusion["true_positive"] + confusion["false_negative"]
    benign_total = confusion["true_negative"] + confusion["false_positive"]
    if malignant_total == 0 or benign_total == 0:
        raise Round2EvidenceError("paired evidence must contain both labels")
    recall = confusion["true_positive"] / malignant_total
    specificity = confusion["true_negative"] / benign_total
    return confusion, {
        "balanced_accuracy": (recall + specificity) / 2.0,
        "malignant_recall": recall,
        "false_negative_rate": 1.0 - recall,
    }


def derive_paired_comparison(
    round1_reference: Mapping[str, Any], *, threshold: float
) -> dict[str, Any]:
    """Purely recompute Round 2 labels and metrics from Round 1 probabilities."""

    if type(threshold) is not float or not math.isfinite(threshold) or threshold != 0.4:
        raise Round2ConfigError("paired comparison threshold must be the reviewed value")
    try:
        rows = round1_reference["predictions"]
        if not isinstance(rows, list) or not rows:
            raise ValueError("predictions")
        changed: list[dict[str, Any]] = []
        for row in rows:
            round2_label = "M" if row["malignant_probability"] >= threshold else "B"
            if round2_label != row["predicted_label"]:
                changed.append(
                    {
                        "record_ordinal": row["record_ordinal"],
                        "actual_label": row["actual_label"],
                        "round1_predicted_label": row["predicted_label"],
                        "round2_predicted_label": round2_label,
                        "malignant_probability": row["malignant_probability"],
                    }
                )
        confusion, metrics = _evaluate_prediction_rows(rows, threshold)
        return {
            "schema_version": "1.0",
            "evaluation_scope": "paired_post_hoc_holdout_sensitivity",
            "record_ordinals": [row["record_ordinal"] for row in rows],
            "actual_labels": [row["actual_label"] for row in rows],
            "malignant_probabilities": [row["malignant_probability"] for row in rows],
            "thresholds": {"round1": 0.5, "round2": threshold},
            "changed_predictions": changed,
            "changed_prediction_count": len(changed),
            "changed_ordinals": [item["record_ordinal"] for item in changed],
            "round2_confusion": confusion,
            "round2_metrics": metrics,
        }
    except (KeyError, TypeError, ValueError):
        raise Round2EvidenceError("paired Round 1 evidence is invalid") from None


def _load_round2_control_package(package_dir: Path) -> dict[str, Any]:
    _, payloads = _load_integrity_package(Path(package_dir))
    try:
        model = _json_payload(payloads, "artifacts/model.json")
    except Round2EvidenceError:
        raise Round2ControlDriftError(
            "feature scaling control contains invalid numeric evidence"
        ) from None
    return {
        "execution_spec": _json_payload(payloads, "execution_spec.json"),
        "execution_result": _json_payload(payloads, "execution_result.json"),
        "run_metadata": _json_payload(payloads, "run_metadata.json"),
        "model": model,
        "run_summary": _json_payload(payloads, "artifacts/run-summary.json"),
        "predictions": _prediction_rows(payloads["artifacts/predictions.csv"]),
    }


def validate_control_invariants(
    round1_reference: Mapping[str, Any], round2_package_dir: Path
) -> dict[str, Any]:
    """Prove that the formal comparison changed only the decision threshold."""

    current = _load_round2_control_package(Path(round2_package_dir))
    reference_dataset = round1_reference["dataset_manifest"]
    metadata = current["run_metadata"]
    result = current["execution_result"]
    spec = current["execution_spec"]
    model = current["model"]
    predictions = current["predictions"]
    reference_model = round1_reference["model"]
    reference_predictions = round1_reference["predictions"]

    dataset_views = [metadata.get("dataset")]
    dataset_views.extend(result.get("datasets", []))
    dataset_views.extend(spec.get("datasets", []))
    if not dataset_views or any(view != reference_dataset for view in dataset_views):
        raise Round2ControlDriftError("dataset control changed")
    if result.get("question_id") != "Q028" or spec.get("question_id") != "Q028":
        raise Round2ControlDriftError("question control changed")
    if result.get("seed") != 125 or spec.get("seed") != 125:
        raise Round2ControlDriftError("seed control changed")
    parameters = model.get("parameters")
    if not isinstance(parameters, dict):
        raise Round2ControlDriftError("model controls are missing")
    if not _same_number(parameters.get("test_fraction"), 0.2):
        raise Round2ControlDriftError("test fraction control changed")
    if model.get("algorithm") != reference_model.get("algorithm"):
        raise Round2ControlDriftError("optimizer control changed")
    if not _same_number(parameters.get("learning_rate"), 0.05):
        raise Round2ControlDriftError("learning rate control changed")
    if parameters.get("iterations") != 2000:
        raise Round2ControlDriftError("iterations control changed")
    if not _same_number(parameters.get("l2"), 0.001):
        raise Round2ControlDriftError("l2 control changed")

    holdout = [row["record_ordinal"] for row in reference_predictions]
    train = sorted(set(range(1, 570)) - set(holdout))
    if model.get("train_ordinals") != train:
        raise Round2ControlDriftError("train indices control changed")
    if model.get("holdout_ordinals") != holdout:
        raise Round2ControlDriftError("holdout ordinals control changed")
    if not (
        _same_numeric_sequence(model.get("feature_means"), reference_model.get("feature_means"))
        and _same_numeric_sequence(model.get("feature_scales"), reference_model.get("feature_scales"))
    ):
        raise Round2ControlDriftError("feature scaling control changed")
    if not (
        _same_numeric_sequence(model.get("coefficients"), reference_model.get("coefficients"))
        and _same_number(model.get("bias"), reference_model.get("bias"))
    ):
        raise Round2ControlDriftError("model parameter control changed")

    if len(predictions) != len(reference_predictions):
        raise Round2ControlDriftError("probabilities control changed")
    for before, after in zip(reference_predictions, predictions, strict=True):
        if (
            before["record_ordinal"] != after["record_ordinal"]
            or before["actual_label"] != after["actual_label"]
            or not _same_number(before["malignant_probability"], after["malignant_probability"])
        ):
            raise Round2ControlDriftError("probabilities control changed")

    if not _same_number(parameters.get("decision_threshold"), 0.4):
        raise Round2ControlDriftError("threshold control is invalid")
    if metadata.get("controls") != _CANONICAL_CONFIG:
        raise Round2ControlDriftError("control declaration changed")
    if (
        result.get("round_index") != 2
        or spec.get("round_index") != 2
        or result.get("parent_execution_id") != ROUND1_EXECUTION_ID
        or spec.get("parent_execution_id") != ROUND1_EXECUTION_ID
    ):
        raise Round2ControlDriftError("round linkage control changed")

    comparison = derive_paired_comparison(round1_reference, threshold=0.4)
    expected_labels = {
        item["record_ordinal"]: item["round2_predicted_label"]
        for item in comparison["changed_predictions"]
    }
    for row in predictions:
        expected = expected_labels.get(
            row["record_ordinal"],
            next(
                item["predicted_label"]
                for item in reference_predictions
                if item["record_ordinal"] == row["record_ordinal"]
            ),
        )
        if row["predicted_label"] != expected:
            raise Round2ControlDriftError("probabilities or threshold labels changed")
    return {
        "schema_version": "1.0",
        "only_permitted_change": "decision_threshold",
        "all_controls_unchanged": True,
        "threshold_change": {"from": 0.5, "to": 0.4},
        "changed_prediction_count": comparison["changed_prediction_count"],
        "changed_ordinals": comparison["changed_ordinals"],
        "changed_probability_interval": "[0.4,0.5)",
        "float_comparison": dict(_FLOAT_POLICY),
    }


def _load_robustness_rows(dataset_path: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Load a WDBC-shaped local file without weakening the formal dataset pin."""

    try:
        raw = _verified_unpinned_bytes(Path(dataset_path), stage="round2-robustness")
        if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
            raise ValueError("invalid encoding marker")
        reader = csv.reader(io.StringIO(raw.decode("utf-8", errors="strict"), newline=""))
        features: list[list[float]] = []
        labels: list[int] = []
        text_labels: list[str] = []
        identifiers: set[str] = set()
        for row in reader:
            if len(row) != 32 or not row[0] or row[0] in identifiers or row[1] not in {"B", "M"}:
                raise ValueError("invalid WDBC row")
            values = [float(value) for value in row[2:]]
            if len(values) != 30 or any(not math.isfinite(value) for value in values):
                raise ValueError("invalid WDBC feature")
            identifiers.add(row[0])
            features.append(values)
            labels.append(1 if row[1] == "M" else 0)
            text_labels.append(row[1])
        if len(features) < 10 or set(labels) != {0, 1}:
            raise ValueError("insufficient stratified rows")
        return (
            np.asarray(features, dtype=np.float64),
            np.asarray(labels, dtype=np.int64),
            text_labels,
        )
    except (OSError, UnicodeError, ValueError, SecurityViolation, csv.Error):
        raise Round2EvidenceError("robustness dataset is missing or invalid") from None


def _deterministic_stratified_folds(
    labels: np.ndarray, *, fold_count: int, seed: int
) -> list[np.ndarray]:
    generator = np.random.default_rng(seed)
    buckets: list[list[int]] = [[] for _ in range(fold_count)]
    for label in (0, 1):
        members = np.flatnonzero(labels == label)
        if len(members) < fold_count:
            raise Round2EvidenceError("each robustness label must cover every fold")
        shuffled = generator.permutation(members)
        for index, member in enumerate(shuffled):
            buckets[index % fold_count].append(int(member))
    return [np.asarray(sorted(bucket), dtype=np.int64) for bucket in buckets]


def run_robustness_analysis(
    dataset_path: Path, config: Mapping[str, Any]
) -> dict[str, Any]:
    """Run the predeclared deterministic, internal five-fold robustness analysis."""

    try:
        parsed = dict(config)
        _Round2Config.model_validate(parsed)
        if parsed != _CANONICAL_CONFIG:
            raise ValueError("unreviewed robustness control")
    except (TypeError, ValueError, ValidationError):
        raise Round2ConfigError("Round 2 robustness configuration is invalid") from None

    features, labels, text_labels = _load_robustness_rows(Path(dataset_path))
    robustness = parsed["robustness"]
    fold_count = robustness["fold_count"]
    seed = robustness["seed"]
    thresholds = list(robustness["thresholds"])
    test_folds = _deterministic_stratified_folds(labels, fold_count=fold_count, seed=seed)
    all_indices = np.arange(len(labels), dtype=np.int64)
    optimizer = parsed["optimizer"]
    folds: list[dict[str, Any]] = []

    for fold_index, test_indices in enumerate(test_folds, start=1):
        train_indices = np.setdiff1d(all_indices, test_indices, assume_unique=True)
        weights, bias, means, scales = _fit_logistic(
            features[train_indices],
            labels[train_indices],
            learning_rate=optimizer["learning_rate"],
            iterations=optimizer["iterations"],
            l2=optimizer["l2"],
        )
        probabilities = _probabilities(features[test_indices], weights, bias, means, scales)
        if not np.all(np.isfinite(probabilities)):
            raise Round2EvidenceError("robustness probabilities are non-finite")
        evaluations: list[dict[str, Any]] = []
        for threshold in thresholds:
            predicted = (probabilities >= threshold).astype(np.int64)
            evaluated = _evaluate(labels[test_indices], predicted)
            recall = float(evaluated["malignant_recall"])
            metrics = {
                "balanced_accuracy": float(evaluated["balanced_accuracy"]),
                "malignant_recall": recall,
                "false_negative_rate": 1.0 - recall,
            }
            if any(not math.isfinite(value) for value in metrics.values()):
                raise Round2EvidenceError("robustness metrics are non-finite")
            evaluations.append(
                {
                    "threshold": threshold,
                    "metrics": metrics,
                    "confusion": {
                        key: int(value) for key, value in evaluated["confusion"].items()
                    },
                }
            )
        train_ordinals = [int(index) + 1 for index in train_indices]
        test_ordinals = [int(index) + 1 for index in test_indices]
        folds.append(
            {
                "fold_index": fold_index,
                "train_count": len(train_ordinals),
                "test_count": len(test_ordinals),
                "train_ordinals": train_ordinals,
                "test_ordinals": test_ordinals,
                "test_labels": [text_labels[int(index)] for index in test_indices],
                "fit_scope": "fold_train_only",
                "fit_ordinals": train_ordinals,
                "evaluations": evaluations,
            }
        )

    aggregate: dict[str, dict[str, dict[str, float | int]]] = {}
    for threshold_index, threshold in enumerate(thresholds):
        threshold_summary: dict[str, dict[str, float | int]] = {}
        for metric in ("balanced_accuracy", "malignant_recall", "false_negative_rate"):
            values = np.asarray(
                [fold["evaluations"][threshold_index]["metrics"][metric] for fold in folds],
                dtype=np.float64,
            )
            threshold_summary[metric] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=0)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "fold_count": fold_count,
            }
        aggregate[str(threshold)] = threshold_summary

    return {
        "schema_version": "1.0",
        "evaluation_scope": "deterministic_internal_stratified_5fold_robustness",
        "fold_count": fold_count,
        "seed": seed,
        "thresholds": thresholds,
        "threshold_selection_performed": False,
        "excluded_folds": [],
        "reported_fold_indices": list(range(1, fold_count + 1)),
        "aggregate_ddof": 0,
        "aggregate": aggregate,
        "folds": folds,
        "fixture_labels": list(_FIXTURE_LABELS),
    }


def _package_dataset_pin(
    spec: Mapping[str, Any], result: Mapping[str, Any], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    try:
        spec_datasets = spec["datasets"]
        result_datasets = result["datasets"]
        dataset = metadata["dataset"]
        if (
            not isinstance(spec_datasets, list)
            or len(spec_datasets) != 1
            or not isinstance(result_datasets, list)
            or len(result_datasets) != 1
            or dataset != spec_datasets[0]
            or dataset != result_datasets[0]
        ):
            raise ValueError("dataset views disagree")
        pin = {
            "dataset_id": dataset["dataset_id"],
            "sha256": dataset["sha256"],
            "size_bytes": dataset["size_bytes"],
        }
        if (
            not isinstance(pin["dataset_id"], str)
            or not isinstance(pin["sha256"], str)
            or len(pin["sha256"]) != 64
            or type(pin["size_bytes"]) is not int
            or pin["size_bytes"] < 1
        ):
            raise ValueError("dataset pin invalid")
        return pin
    except (KeyError, TypeError, ValueError):
        raise Round2ReproductionError("dataset evidence differs or is invalid") from None


def _reproduction_view(package_dir: Path) -> dict[str, Any]:
    _, payloads = _load_integrity_package(
        Path(package_dir),
        expected_files=_ROUND2_PACKAGE_FILES - {"package_manifest.json"},
        error_type=Round2ReproductionError,
    )
    for relative, raw in payloads.items():
        lowered = raw.lower()
        if any(
            marker in lowered
            for marker in (
                b"authorization: bearer",
                b"api_key=",
                b"cookie:",
                b"private key",
                b"raw_wdbc",
                b"cure_all_cancers",
                b"patient_diagnosis",
            )
        ):
            raise Round2ReproductionError("package content violates evidence policy")
        if relative.endswith(".json"):
            try:
                _strict_json_bytes(raw)
            except (UnicodeError, ValueError):
                raise Round2ReproductionError(
                    f"JSON reproduction evidence is invalid: {relative}"
                ) from None
        elif relative.endswith(".csv"):
            try:
                if raw.startswith(b"\xef\xbb\xbf") or b"\r\n" in raw or not raw.endswith(b"\n"):
                    raise ValueError("CSV serialization")
                rows = list(csv.reader(io.StringIO(raw.decode("utf-8", errors="strict"), newline="")))
                if not rows or not rows[0]:
                    raise ValueError("CSV content")
            except (UnicodeError, ValueError, csv.Error):
                raise Round2ReproductionError(
                    f"CSV reproduction evidence is invalid: {relative}"
                ) from None
        elif relative.endswith(".svg"):
            try:
                text = raw.decode("utf-8", errors="strict").lower()
                if not text.startswith("<svg") or "paired" not in text or "not for clinical use" not in text:
                    raise ValueError("SVG content")
            except (UnicodeError, ValueError):
                raise Round2ReproductionError(
                    f"SVG reproduction evidence is invalid: {relative}"
                ) from None
    spec = _json_payload(payloads, "execution_spec.json", error_type=Round2ReproductionError)
    result = _json_payload(payloads, "execution_result.json", error_type=Round2ReproductionError)
    metadata = _json_payload(payloads, "run_metadata.json", error_type=Round2ReproductionError)
    model = _json_payload(payloads, "artifacts/model.json", error_type=Round2ReproductionError)
    summary = _json_payload(
        payloads, "artifacts/run-summary.json", error_type=Round2ReproductionError
    )
    environment = _json_payload(
        payloads,
        "reproduction/environment_fingerprint.json",
        error_type=Round2ReproductionError,
    )
    predictions = _prediction_rows(
        payloads["artifacts/predictions.csv"], error_type=Round2ReproductionError
    )
    comparison = _json_payload(
        payloads,
        "comparison/two-round-comparison.json",
        error_type=Round2ReproductionError,
    )
    if not (
        spec.get("question_id") == result.get("question_id") == "Q028"
        and spec.get("round_index") == result.get("round_index") == metadata.get("round_index") == 2
        and spec.get("parent_execution_id")
        == result.get("parent_execution_id")
        == metadata.get("parent_execution_id")
        == ROUND1_EXECUTION_ID
        and result.get("status") == "succeeded"
        and result.get("actual_execution") is True
        and result.get("runner_verified") is True
        and metadata.get("actual_execution") is True
        and metadata.get("formal_round2_executed") is True
        and metadata.get("evaluation_scope") == "paired_post_hoc_holdout_sensitivity"
        and comparison.get("evaluation_scope") == "paired_post_hoc_holdout_sensitivity"
    ):
        raise Round2ReproductionError("formal reproduction metadata is invalid")
    expected_parameters = {
        "seed": 125,
        "test_fraction": 0.2,
        "learning_rate": 0.05,
        "iterations": 2000,
        "l2": 0.001,
        "decision_threshold": 0.4,
    }
    if (
        spec.get("seed") != 125
        or metadata.get("seed") != 125
        or not _same_number(metadata.get("test_fraction"), 0.2)
        or model.get("algorithm") != "standardized_full_batch_logistic_regression"
        or model.get("parameters") != expected_parameters
        or (
            "controls" in metadata
            and metadata.get("controls") != _CANONICAL_CONFIG
        )
    ):
        raise Round2ReproductionError("model control evidence is invalid")
    train = model.get("train_ordinals")
    holdout = model.get("holdout_ordinals")
    if (
        not isinstance(train, list)
        or not isinstance(holdout, list)
        or not train
        or not holdout
        or any(type(value) is not int or value < 0 for value in train + holdout)
        or len(set(train)) != len(train)
        or len(set(holdout)) != len(holdout)
        or not set(train).isdisjoint(holdout)
        or [row["record_ordinal"] for row in predictions] != holdout
    ):
        raise Round2ReproductionError("split or ordinal evidence is invalid")
    confusion = summary.get("confusion")
    metrics = summary.get("metrics")
    if (
        not isinstance(confusion, dict)
        or set(confusion)
        != {"true_negative", "false_positive", "false_negative", "true_positive"}
        or any(type(value) is not int or value < 0 for value in confusion.values())
        or not isinstance(metrics, dict)
        or set(metrics)
        != {"balanced_accuracy", "malignant_recall", "false_negative_rate"}
        or any(
            type(value) not in {int, float}
            or not math.isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
            for value in metrics.values()
        )
    ):
        raise Round2ReproductionError("metric evidence is invalid")
    artifact_index = {
        item.get("artifact_id"): item
        for item in result.get("artifacts", [])
        if isinstance(item, dict)
    }
    metric_index = {
        item.get("name"): item
        for item in result.get("metrics", [])
        if isinstance(item, dict)
    }
    expected_artifacts = {item[0] for item in _ARTIFACT_DECLARATIONS}
    expected_metrics = {
        "balanced_accuracy": "balanced-accuracy",
        "false_negative_rate": "false-negative-rate",
        "malignant_recall": "malignant-recall",
    }
    if (
        set(artifact_index) != expected_artifacts
        or any(item.get("validation_status") != "valid" for item in artifact_index.values())
        or set(metric_index) != set(expected_metrics)
        or any(
            metric_index[name].get("artifact_id") != artifact_id
            or metric_index[name].get("validation_status") != "valid"
            or not _same_number(metric_index[name].get("value"), metrics[name])
            for name, artifact_id in expected_metrics.items()
        )
    ):
        raise Round2ReproductionError("artifact or metric schema is invalid")
    pin = _package_dataset_pin(spec, result, metadata)
    if pin != {
        "dataset_id": WDBC_DATASET_ID,
        "sha256": DATASET_SHA256,
        "size_bytes": DATASET_SIZE_BYTES,
    }:
        raise Round2ReproductionError("dataset pin is not the reviewed WDBC snapshot")
    return {
        "payloads": payloads,
        "spec": spec,
        "result": result,
        "metadata": metadata,
        "model": model,
        "summary": summary,
        "environment": environment,
        "predictions": predictions,
        "dataset_pin": pin,
    }


def compare_reproduction_packages(primary_dir: Path, candidate_dir: Path) -> dict[str, Any]:
    """Fail closed unless two packages have the same scientific evidence."""

    primary = _reproduction_view(Path(primary_dir))
    candidate = _reproduction_view(Path(candidate_dir))
    if primary["dataset_pin"] != candidate["dataset_pin"]:
        raise Round2ReproductionError("dataset pin mismatch")

    primary_model = primary["model"]
    candidate_model = candidate["model"]
    split_fields = ("train_ordinals", "holdout_ordinals")
    if any(primary_model.get(field) != candidate_model.get(field) for field in split_fields):
        raise Round2ReproductionError("split mismatch")

    primary_rows = primary["predictions"]
    candidate_rows = candidate["predictions"]
    if len(primary_rows) != len(candidate_rows):
        raise Round2ReproductionError("prediction ordinal mismatch")
    for left, right in zip(primary_rows, candidate_rows, strict=True):
        if (
            left["record_ordinal"] != right["record_ordinal"]
            or left["actual_label"] != right["actual_label"]
            or left["predicted_label"] != right["predicted_label"]
        ):
            raise Round2ReproductionError("prediction ordinal or label mismatch")
        if left["malignant_probability"] != right["malignant_probability"]:
            raise Round2ReproductionError("probability mismatch")

    if primary_model.get("parameters") != candidate_model.get("parameters"):
        raise Round2ReproductionError("model parameters mismatch")
    for field in ("bias", "feature_means", "feature_scales", "coefficients"):
        left = primary_model.get(field)
        right = candidate_model.get(field)
        matches = _same_number(left, right) if field == "bias" else _same_numeric_sequence(left, right)
        if not matches:
            raise Round2ReproductionError("model arrays mismatch")

    primary_summary = primary["summary"]
    candidate_summary = candidate["summary"]
    if primary_summary.get("confusion") != candidate_summary.get("confusion"):
        raise Round2ReproductionError("metric confusion mismatch")
    left_metrics = primary_summary.get("metrics")
    right_metrics = candidate_summary.get("metrics")
    if (
        not isinstance(left_metrics, dict)
        or not isinstance(right_metrics, dict)
        or set(left_metrics) != set(right_metrics)
        or any(not _same_number(left_metrics[key], right_metrics[key]) for key in left_metrics)
    ):
        raise Round2ReproductionError("metric mismatch")

    differing_scientific = sorted(
        relative
        for relative in _SCIENTIFIC_ROUND2_FILES
        if primary["payloads"][relative] != candidate["payloads"][relative]
    )
    if differing_scientific:
        raise Round2ReproductionError(
            "scientific artifact mismatch: " + ", ".join(differing_scientific)
        )
    environment_versions_recorded = all(
        isinstance(view["environment"].get(key), str) and bool(view["environment"][key])
        for view in (primary, candidate)
        for key in ("python", "numpy")
    )
    if not environment_versions_recorded:
        raise Round2ReproductionError("environment versions are missing")
    environment_differences = sorted(
        key
        for key in set(primary["environment"]) | set(candidate["environment"])
        if primary["environment"].get(key) != candidate["environment"].get(key)
    )
    exact_matches = [
        "question_id",
        "round_index",
        "parent_execution_id",
        "dataset_pin",
        "split",
        "record_ordinals",
        "actual_labels",
        "predicted_labels",
        "confusion",
        "scientific_artifacts",
    ]
    numeric_matches = [
        "malignant_probabilities",
        "feature_means",
        "feature_scales",
        "coefficients",
        "bias",
        "metrics",
    ]
    permitted_differences = ["execution_id", "timestamp", "workspace_uri"]
    return {
        "schema_version": "1.0",
        "reproduction_valid": True,
        "exact_matches": exact_matches,
        "numeric_matches": numeric_matches,
        "allowed_differences": permitted_differences,
        "environment_differences": environment_differences,
        "mismatches": [],
        "tolerance_policy": dict(_FLOAT_POLICY),
        "byte_identical_claim_allowed": False,
        "scientific_content_equivalent": True,
        "manifest_complete": True,
        "dataset_pin_match": True,
        "dataset_pin": primary["dataset_pin"],
        "split_match": True,
        "ordinal_match": True,
        "predictions_match": True,
        "probability_comparison": {"match": True, **_FLOAT_POLICY},
        "confusion_match": True,
        "metrics_match": True,
        "model_parameters_match": True,
        "model_arrays_match": True,
        "scientific_match": True,
        "scientific_files_compared": sorted(_SCIENTIFIC_ROUND2_FILES),
        "permitted_metadata_differences": permitted_differences,
        "environment_versions_recorded": True,
        "byte_identical_claim": False,
        "structural_and_numeric_comparison": True,
        "network_calls": 0,
        "child_process_residue": False,
        "workspace_residue": False,
    }


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
            name=name,
            unit="ratio",
            artifact_id=artifact_id,
            required=True,
        )
        for name, artifact_id in (
            ("balanced_accuracy", "balanced-accuracy"),
            ("false_negative_rate", "false-negative-rate"),
            ("malignant_recall", "malignant-recall"),
        )
    ]


def build_execution_spec(
    dataset_manifest: DatasetManifest, round1_reference: Mapping[str, Any]
) -> ExecutionSpec:
    config = load_round2_config()
    if dataset_manifest.model_dump(mode="json") != round1_reference.get("dataset_manifest"):
        raise Round2EvidenceError("dataset manifest differs from the Round 1 parent")
    optimizer = config["optimizer"]
    specification = ExecutionSpec(
        spec_id="wdbc-round2-threshold-sensitivity-v1",
        question_id="Q028",
        round_index=2,
        parent_execution_id=round1_reference["execution_result"]["execution_id"],
        mode="actual",
        entrypoint=ENTRYPOINT_ID,
        argv=[
            "--scientific-child",
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
            str(config["control_change"]["to"]),
            "--expected-sha256",
            dataset_manifest.sha256,
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
        environment={"variables": {}, "dependency_allowlist": ["numpy", "pydantic"]},
        cleanup_policy="preserve",
    )
    environment = _Round2ExecutionEnvironment.model_validate(
        specification.environment.model_dump(mode="python")
    )
    object.__setattr__(specification, "environment", environment)
    return specification


def _validate_formal_result(result: ExecutionResult) -> None:
    if not all(
        (
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
    ):
        raise Round2EvidenceError("controlled runner did not produce trusted Round 2 evidence")


def run_formal_round2(
    *,
    cache_root: Path,
    package_dir: Path,
    offline: bool,
    round1_package_dir: Path = ROUND1_PACKAGE_PATH,
) -> ExecutionResult:
    """Execute and atomically publish formal Round 2 evidence when authorized."""

    package_dir = Path(package_dir)
    if package_dir.exists() or package_dir.is_symlink():
        raise Round2EvidenceError("formal Round 2 destination already exists or is unsafe")
    package_parent = ensure_secure_root(
        package_dir.parent, create=True, stage="round2-destination"
    )
    package_dir = package_parent / package_dir.name
    staging = package_dir.with_name(f".{package_dir.name}.{uuid.uuid4().hex}.part")
    try:
        reference = load_round1_reference(round1_package_dir)
        load_round2_config()
        dataset_record = _strict_json_bytes(_verified_unpinned_bytes(DATASET_MANIFEST_PATH, stage="dataset"))
        pin = dataset_record.get("pin")
        if not isinstance(pin, dict) or pin.get("status") != "verified":
            raise Round2EvidenceError("dataset pin is not verified")
        adapter = DatasetAdapter(get_default_dataset_registry())
        resolved = adapter.fetch(WDBC_DATASET_ID, cache_root=cache_root, offline=offline)
        dataset_manifest = resolved.to_dataset_manifest()
        if (
            dataset_manifest.sha256 != pin.get("sha256")
            or dataset_manifest.size_bytes != pin.get("size_bytes")
        ):
            raise Round2EvidenceError("resolved dataset disagrees with the reviewed pin")
        spec = build_execution_spec(dataset_manifest, reference)
        registry = EntrypointRegistry()
        registry.register_python(
            ENTRYPOINT_ID,
            ENTRYPOINT_PATH,
            entrypoint_class="scientific",
        )
        with tempfile.TemporaryDirectory(prefix="t05-round2-") as temporary:
            managed_root = Path(temporary) / "workspaces"
            runner = LocalProcessRunner(
                registry=registry,
                managed_root=managed_root,
                dataset_resolver=adapter.build_resolver(cache_root),
            )
            result = runner.run(spec)
            _validate_formal_result(result)
            workspaces = [item for item in managed_root.iterdir() if item.is_dir()]
            if len(workspaces) != 1:
                raise Round2EvidenceError("controlled runner workspace evidence is incomplete")
            staging.mkdir()
            _assemble_formal_package(
                staging,
                workspace=workspaces[0],
                dataset_path=resolved.cache_path,
                spec=spec,
                result=result,
                reference=reference,
                formal_round2_executed=True,
            )
            os.replace(staging, package_dir)
            return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.artifact-part")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _csv_bytes(header: Sequence[object], rows: Sequence[Sequence[object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_package_manifest(package_dir: Path) -> None:
    entries = []
    for path in sorted(package_dir.rglob("*")):
        if path.is_symlink():
            raise Round2EvidenceError("formal package contains unsafe indirection")
        if path.is_file() and path.name != "package_manifest.json":
            relative = path.relative_to(package_dir).as_posix()
            digest = file_sha256(
                path,
                max_bytes=_MAX_EVIDENCE_FILE_BYTES,
                stage="round2-package",
                invalid_code="artifact_invalid",
            )
            entries.append(
                {
                    "path": relative,
                    "sha256": digest.sha256,
                    "size_bytes": digest.size_bytes,
                }
            )
    expected = _ROUND2_PACKAGE_FILES - {"package_manifest.json"}
    if {entry["path"] for entry in entries} != expected:
        raise Round2EvidenceError("formal package file coverage is incomplete")
    _atomic_write(
        package_dir / "package_manifest.json",
        _json_bytes({"schema_version": "1.0", "files": entries}),
    )


def _scientific_child(args: argparse.Namespace) -> int:
    config = BaselineConfig(
        seed=args.seed,
        test_fraction=args.test_fraction,
        learning_rate=args.learning_rate,
        iterations=args.iterations,
        l2=args.l2,
        decision_threshold=args.decision_threshold,
        recall_target=0.95,
        threshold_step=0.1,
        expected_sha256=args.expected_sha256,
        expected_size_bytes=args.expected_size_bytes,
    )
    dataset = load_wdbc(args.dataset, config)
    train_indices, test_indices = stratified_split(
        dataset.labels, test_fraction=config.test_fraction, seed=config.seed
    )
    weights, bias, means, scales = _fit_logistic(
        dataset.features[train_indices],
        dataset.labels[train_indices],
        learning_rate=config.learning_rate,
        iterations=config.iterations,
        l2=config.l2,
    )
    probabilities = _probabilities(
        dataset.features[test_indices], weights, bias, means, scales
    )
    predicted = (probabilities >= config.decision_threshold).astype(np.int64)
    evaluation = _evaluate(dataset.labels[test_indices], predicted)
    recall = float(evaluation["malignant_recall"])
    metrics = {
        "balanced_accuracy": float(evaluation["balanced_accuracy"]),
        "malignant_recall": recall,
        "false_negative_rate": 1.0 - recall,
    }
    parameters = {
        "seed": config.seed,
        "test_fraction": config.test_fraction,
        "learning_rate": config.learning_rate,
        "iterations": config.iterations,
        "l2": config.l2,
        "decision_threshold": config.decision_threshold,
    }
    holdout_ordinals = [int(item) for item in test_indices]
    model = {
        "schema_version": "1.0",
        "algorithm": "standardized_full_batch_logistic_regression",
        "bias": bias,
        "coefficients": weights.tolist(),
        "feature_means": means.tolist(),
        "feature_scales": scales.tolist(),
        "parameters": parameters,
        "holdout_ordinals": holdout_ordinals,
        "train_ordinals": sorted(set(range(1, 570)) - set(holdout_ordinals)),
    }
    summary = {
        "schema_version": "1.0",
        "dataset": {
            "row_count": int(dataset.features.shape[0]),
            "feature_count": int(dataset.features.shape[1]),
            "sha256": dataset.sha256,
            "size_bytes": dataset.size_bytes,
        },
        "parameters": parameters,
        "split": {"train_count": len(train_indices), "test_count": len(test_indices)},
        "confusion": evaluation["confusion"],
        "metrics": metrics,
    }
    for name, artifact_id in (
        ("balanced_accuracy", "balanced-accuracy"),
        ("false_negative_rate", "false-negative-rate"),
        ("malignant_recall", "malignant-recall"),
    ):
        relative = dict((item[0], item[1]) for item in _ARTIFACT_DECLARATIONS)[artifact_id]
        _atomic_write(
            Path(relative),
            _json_bytes(
                {
                    "schema_version": "1.0",
                    "metric": {
                        "name": name,
                        "value": metrics[name],
                        "unit": "ratio",
                        "source": "observed",
                    },
                }
            ),
        )
    prediction_stream = io.StringIO(newline="")
    prediction_writer = csv.writer(prediction_stream, lineterminator="\n")
    prediction_writer.writerow(
        ["record_ordinal", "actual_label", "predicted_label", "malignant_probability"]
    )
    for ordinal, actual, label, probability in zip(
        test_indices,
        dataset.labels[test_indices],
        predicted,
        probabilities,
        strict=True,
    ):
        prediction_writer.writerow(
            [
                int(ordinal),
                "M" if int(actual) else "B",
                "M" if int(label) else "B",
                format(float(probability), ".12g"),
            ]
        )
    confusion_stream = io.StringIO(newline="")
    confusion_writer = csv.writer(confusion_stream, lineterminator="\n")
    confusion_writer.writerow(["actual_label", "predicted_label", "count"])
    counts = evaluation["confusion"]
    confusion_writer.writerows(
        [
            ["B", "B", counts["true_negative"]],
            ["B", "M", counts["false_positive"]],
            ["M", "B", counts["false_negative"]],
            ["M", "M", counts["true_positive"]],
        ]
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg"><title>WDBC Round 2 paired '
        "post-hoc holdout sensitivity; not independent validation; "
        "not for clinical use</title></svg>\n"
    )
    _atomic_write(Path("output/confusion-matrix.csv"), confusion_stream.getvalue().encode("utf-8"))
    _atomic_write(Path("output/model.json"), _json_bytes(model))
    _atomic_write(Path("output/predictions.csv"), prediction_stream.getvalue().encode("utf-8"))
    _atomic_write(Path("output/run-summary.json"), _json_bytes(summary))
    _atomic_write(Path("output/summary.svg"), svg.encode("utf-8"))
    print(json.dumps(summary, allow_nan=False, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0


def _assemble_formal_package(
    staging: Path,
    *,
    workspace: Path,
    dataset_path: Path,
    spec: ExecutionSpec,
    result: ExecutionResult,
    reference: Mapping[str, Any],
    formal_round2_executed: bool,
) -> None:
    """Assemble one verified formal execution and its derived internal analyses."""

    if not formal_round2_executed:
        raise Round2EvidenceError("formal Round 2 execution attestation is required")
    staging = ensure_secure_root(staging, create=False, stage="round2-package")
    workspace = ensure_secure_root(workspace, create=False, stage="round2-package")
    dataset_path = ensure_regular_file(dataset_path, stage="round2-package")
    spec_payload = spec.model_dump(mode="json")
    result_payload = result.model_dump(mode="json")
    dataset = result_payload["datasets"][0]
    metadata = {
        "schema_version": "1.0",
        "question_id": "Q028",
        "round_index": 2,
        "parent_execution_id": ROUND1_EXECUTION_ID,
        "evaluation_scope": "paired_post_hoc_holdout_sensitivity",
        "formal_round2_executed": True,
        "actual_execution": result.actual_execution,
        "runner_verified": result.runner_verified,
        "dataset": dataset,
        "seed": result.seed,
        "test_fraction": _CANONICAL_CONFIG["test_fraction"],
        "controls": _CANONICAL_CONFIG,
        "execution_id": result.execution_id,
        "workspace_uri": result.workspace_uri,
        "timestamp": result.finished_at,
    }
    consumer_mapping = {
        "schema_version": "1.0",
        "artifacts": [item.model_dump(mode="json") for item in result.artifacts],
        "metrics": [item.model_dump(mode="json") for item in result.metrics],
    }
    for relative, payload in (
        ("execution_spec.json", _json_bytes(spec_payload)),
        ("execution_result.json", _json_bytes(result_payload)),
        ("run_metadata.json", _json_bytes(metadata)),
        ("consumer_mapping.json", _json_bytes(consumer_mapping)),
        ("stdout.log", result.stdout.encode("utf-8")),
        ("stderr.log", result.stderr.encode("utf-8")),
    ):
        _atomic_write(staging / relative, payload)

    for artifact in result.artifacts:
        source = secure_relative_path(
            workspace,
            artifact.relative_path,
            must_exist=True,
            require_file=True,
            stage="round2-package",
            invalid_code="artifact_invalid",
        )
        payload = read_verified_bytes(
            source,
            expected_sha256=artifact.sha256,
            expected_size=artifact.size_bytes,
            max_bytes=_MAX_EVIDENCE_FILE_BYTES,
            containment_root=workspace,
            stage="round2-package",
            invalid_code="artifact_invalid",
        )
        _atomic_write(staging / "artifacts" / Path(artifact.relative_path).name, payload)

    comparison = derive_paired_comparison(reference, threshold=0.4)
    round1_metrics = reference["run_summary"]["metrics"]
    comparison_rows = [
        [
            1,
            0.5,
            round1_metrics["balanced_accuracy"],
            round1_metrics["malignant_recall"],
            1.0 - round1_metrics["malignant_recall"],
        ],
        [
            2,
            0.4,
            comparison["round2_metrics"]["balanced_accuracy"],
            comparison["round2_metrics"]["malignant_recall"],
            comparison["round2_metrics"]["false_negative_rate"],
        ],
    ]
    changed_rows = [
        [
            item["record_ordinal"],
            item["actual_label"],
            item["round1_predicted_label"],
            item["round2_predicted_label"],
            format(float(item["malignant_probability"]), ".12g"),
        ]
        for item in comparison["changed_predictions"]
    ]
    paired_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg"><title>WDBC Round 2 paired '
        "post-hoc holdout sensitivity; not independent validation; "
        "not for clinical use</title></svg>\n"
    ).encode("utf-8")
    _atomic_write(
        staging / "comparison" / "two-round-comparison.json", _json_bytes(comparison)
    )
    _atomic_write(
        staging / "comparison" / "two-round-comparison.csv",
        _csv_bytes(
            [
                "round",
                "threshold",
                "balanced_accuracy",
                "malignant_recall",
                "false_negative_rate",
            ],
            comparison_rows,
        ),
    )
    _atomic_write(
        staging / "comparison" / "changed-predictions.csv",
        _csv_bytes(
            [
                "record_ordinal",
                "actual_label",
                "round1_predicted_label",
                "round2_predicted_label",
                "malignant_probability",
            ],
            changed_rows,
        ),
    )
    _atomic_write(staging / "comparison" / "two-round-comparison.svg", paired_svg)

    robustness = run_robustness_analysis(dataset_path, _CANONICAL_CONFIG)
    robustness["fixture_labels"] = []
    fold_rows = []
    for fold in robustness["folds"]:
        for evaluation in fold["evaluations"]:
            metrics = evaluation["metrics"]
            confusion = evaluation["confusion"]
            fold_rows.append(
                [
                    fold["fold_index"],
                    evaluation["threshold"],
                    metrics["balanced_accuracy"],
                    metrics["malignant_recall"],
                    metrics["false_negative_rate"],
                    confusion["true_negative"],
                    confusion["false_positive"],
                    confusion["false_negative"],
                    confusion["true_positive"],
                ]
            )
    robustness_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg"><title>WDBC Round 2 paired '
        "post-hoc holdout sensitivity robustness; not independent validation; "
        "not for clinical use</title></svg>\n"
    ).encode("utf-8")
    _atomic_write(
        staging / "robustness" / "robustness-folds.csv",
        _csv_bytes(
            [
                "fold",
                "threshold",
                "balanced_accuracy",
                "malignant_recall",
                "false_negative_rate",
                "tn",
                "fp",
                "fn",
                "tp",
            ],
            fold_rows,
        ),
    )
    _atomic_write(
        staging / "robustness" / "robustness-summary.json", _json_bytes(robustness)
    )
    _atomic_write(
        staging / "robustness" / "robustness-comparison.svg", robustness_svg
    )

    placeholder_controls = {
        "schema_version": "1.0",
        "only_permitted_change": "decision_threshold",
        "all_controls_unchanged": False,
        "validation_status": "pending",
    }
    _atomic_write(
        staging / "comparison" / "control-invariants.json",
        _json_bytes(placeholder_controls),
    )
    fingerprint = result_payload.get("environment_fingerprint") or {}
    dependencies = fingerprint.get("dependencies") or {}
    environment = {
        "schema_version": "1.0",
        "python": fingerprint.get("python_version", "unavailable"),
        "numpy": dependencies.get("numpy", "unavailable"),
        "fingerprint": fingerprint,
    }
    reproduction = {
        "schema_version": "1.0",
        "comparison_status": "awaiting_independent_clean_environment_package",
        "scientific_match": None,
        "byte_identical_claim": False,
        "structural_and_numeric_comparison": True,
        "formal_round2_executed": True,
    }
    reproduction_markdown = (
        "# Round 2 reproduction report\n\n"
        "This package records a paired internal sensitivity analysis. It is not independent "
        "external validation and is not for clinical use. A second clean-environment package "
        "must be compared before scientific reproduction is claimed.\n"
    ).encode("utf-8")
    artifact_comparison = {
        "schema_version": "1.0",
        "scientific_files": sorted(_SCIENTIFIC_ROUND2_FILES),
        "scientific_match": None,
        "comparison_status": "not_performed_single_execution",
        "float_comparison": _FLOAT_POLICY,
    }
    _atomic_write(
        staging / "reproduction" / "environment_fingerprint.json",
        _json_bytes(environment),
    )
    _atomic_write(
        staging / "reproduction" / "reproduction_report.json",
        _json_bytes(reproduction),
    )
    _atomic_write(
        staging / "reproduction" / "reproduction_report.md", reproduction_markdown
    )
    _atomic_write(
        staging / "reproduction" / "artifact_comparison.json",
        _json_bytes(artifact_comparison),
    )
    _write_package_manifest(staging)
    controls = validate_control_invariants(reference, staging)
    _atomic_write(
        staging / "comparison" / "control-invariants.json", _json_bytes(controls)
    )
    _write_package_manifest(staging)
    _load_integrity_package(
        staging, expected_files=_ROUND2_PACKAGE_FILES - {"package_manifest.json"}
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scientific-child", action="store_true")
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-size-bytes", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--test-fraction", type=float)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--l2", type=float)
    parser.add_argument("--decision-threshold", type=float)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--package-dir", type=Path)
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.scientific_child:
        return _scientific_child(args)
    if args.cache_root is None or args.package_dir is None:
        raise SystemExit("--cache-root and --package-dir are required")
    result = run_formal_round2(
        cache_root=args.cache_root,
        package_dir=args.package_dir,
        offline=args.offline,
    )
    print(
        json.dumps(
            {
                "actual_execution": result.actual_execution,
                "artifact_count": len(result.artifacts),
                "metric_count": len(result.metrics),
                "status": result.status,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
