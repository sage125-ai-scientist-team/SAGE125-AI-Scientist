"""Deterministic WDBC Round 1 baseline executed by the controlled runner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


ARTIFACT_FILES: dict[str, str] = {
    "balanced-accuracy": "output/metrics-balanced-accuracy.json",
    "confusion-matrix": "output/confusion-matrix.csv",
    "malignant-recall": "output/metrics-malignant-recall.json",
    "model": "output/model.json",
    "predictions": "output/predictions.csv",
    "round2-plan": "output/round2-plan.json",
    "run-summary": "output/run-summary.json",
    "summary-plot": "output/summary.svg",
}


class BaselineInputError(ValueError):
    """The staged WDBC input or baseline configuration is invalid."""


@dataclass(frozen=True, slots=True)
class BaselineConfig:
    seed: int
    test_fraction: float
    learning_rate: float
    iterations: int
    l2: float
    decision_threshold: float
    recall_target: float
    threshold_step: float
    expected_sha256: str
    expected_size_bytes: int


@dataclass(frozen=True, slots=True)
class WDBCDataset:
    identifiers: tuple[str, ...]
    labels: np.ndarray
    features: np.ndarray
    sha256: str
    size_bytes: int


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.part")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_wdbc(path: Path, config: BaselineConfig) -> WDBCDataset:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) != config.expected_size_bytes or digest != config.expected_sha256:
        raise BaselineInputError("staged WDBC input does not match the approved pin")
    if b"\x00" in raw:
        raise BaselineInputError("staged WDBC input contains NUL bytes")

    identifiers: list[str] = []
    labels: list[int] = []
    features: list[list[float]] = []
    rows = csv.reader(io.StringIO(raw.decode("utf-8", errors="strict")))
    for row_index, row in enumerate(rows, start=1):
        if len(row) != 32:
            raise BaselineInputError(f"row {row_index} does not contain 32 columns")
        identifier = row[0].strip()
        label = row[1].strip()
        if not identifier or identifier in identifiers:
            raise BaselineInputError("WDBC identifiers must be nonblank and unique")
        if label not in {"B", "M"}:
            raise BaselineInputError("WDBC labels must be B or M")
        try:
            row_features = [float(value) for value in row[2:]]
        except ValueError:
            raise BaselineInputError("WDBC features must be numeric") from None
        if not all(math.isfinite(value) for value in row_features):
            raise BaselineInputError("WDBC features must be finite")
        identifiers.append(identifier)
        labels.append(1 if label == "M" else 0)
        features.append(row_features)

    if len(identifiers) != 569:
        raise BaselineInputError("WDBC input must contain exactly 569 records")
    if labels.count(0) != 357 or labels.count(1) != 212:
        raise BaselineInputError("WDBC label counts do not match the approved snapshot")
    return WDBCDataset(
        identifiers=tuple(identifiers),
        labels=np.asarray(labels, dtype=np.int64),
        features=np.asarray(features, dtype=np.float64),
        sha256=digest,
        size_bytes=len(raw),
    )


def stratified_split(
    labels: np.ndarray,
    *,
    test_fraction: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 < test_fraction < 1.0:
        raise BaselineInputError("test_fraction must be between zero and one")
    rng = random.Random(seed)
    train: list[int] = []
    test: list[int] = []
    for label in (0, 1):
        indices = [int(index) for index in np.flatnonzero(labels == label)]
        if len(indices) < 2:
            raise BaselineInputError("each class requires at least two records")
        rng.shuffle(indices)
        test_count = max(1, min(len(indices) - 1, round(len(indices) * test_fraction)))
        test.extend(indices[:test_count])
        train.extend(indices[test_count:])
    return (
        np.asarray(sorted(train), dtype=np.int64),
        np.asarray(sorted(test), dtype=np.int64),
    )


def _fit_logistic(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    learning_rate: float,
    iterations: int,
    l2: float,
) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    if learning_rate <= 0.0 or iterations <= 0 or l2 < 0.0:
        raise BaselineInputError("optimizer parameters are invalid")
    means = features.mean(axis=0)
    scales = features.std(axis=0)
    scales = np.where(scales == 0.0, 1.0, scales)
    normalized = (features - means) / scales
    weights = np.zeros(normalized.shape[1], dtype=np.float64)
    bias = 0.0
    targets = labels.astype(np.float64)
    for _ in range(iterations):
        logits = np.clip(normalized @ weights + bias, -40.0, 40.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        error = probabilities - targets
        gradient = normalized.T @ error / len(targets) + l2 * weights
        bias_gradient = float(error.mean())
        weights -= learning_rate * gradient
        bias -= learning_rate * bias_gradient
    return weights, bias, means, scales


def _probabilities(
    features: np.ndarray,
    weights: np.ndarray,
    bias: float,
    means: np.ndarray,
    scales: np.ndarray,
) -> np.ndarray:
    normalized = (features - means) / scales
    logits = np.clip(normalized @ weights + bias, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-logits))


def _evaluate(labels: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    true_positive = int(np.sum((labels == 1) & (predictions == 1)))
    false_negative = int(np.sum((labels == 1) & (predictions == 0)))
    true_negative = int(np.sum((labels == 0) & (predictions == 0)))
    false_positive = int(np.sum((labels == 0) & (predictions == 1)))
    malignant_recall = true_positive / (true_positive + false_negative)
    benign_recall = true_negative / (true_negative + false_positive)
    return {
        "balanced_accuracy": (malignant_recall + benign_recall) / 2.0,
        "malignant_recall": malignant_recall,
        "confusion": {
            "false_negative": false_negative,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "true_positive": true_positive,
        },
    }


def build_round2_plan(metrics: dict[str, float], config: BaselineConfig) -> dict[str, Any]:
    recall = metrics["malignant_recall"]
    if recall < config.recall_target:
        next_threshold = max(0.05, config.decision_threshold - config.threshold_step)
        change = {
            "field": "decision_threshold",
            "from": config.decision_threshold,
            "to": next_threshold,
        }
        rationale = "Round 1 malignant recall was below the predeclared target."
    else:
        next_l2 = config.l2 * 0.5
        change = {"field": "l2", "from": config.l2, "to": next_l2}
        rationale = "Round 1 met recall target; Round 2 will test lower regularization."
    return {
        "schema_version": "1.0",
        "based_on_round": 1,
        "evidence": {
            "malignant_recall": recall,
            "target": config.recall_target,
        },
        "change": change,
        "fixed_controls": {
            "seed": config.seed,
            "test_fraction": config.test_fraction,
        },
        "rationale": rationale,
        "formal_round2_executed": False,
    }


def _metric_payload(name: str, value: float) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "metric": {
            "name": name,
            "source": "observed",
            "unit": "ratio",
            "value": value,
        },
    }


def _predictions_csv(
    indices: np.ndarray,
    labels: np.ndarray,
    predictions: np.ndarray,
    probabilities: np.ndarray,
) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        ["record_ordinal", "actual_label", "predicted_label", "malignant_probability"]
    )
    for index, actual, predicted, probability in zip(
        indices, labels, predictions, probabilities, strict=True
    ):
        writer.writerow(
            [
                int(index),
                "M" if int(actual) == 1 else "B",
                "M" if int(predicted) == 1 else "B",
                format(float(probability), ".12g"),
            ]
        )
    return stream.getvalue().encode("utf-8")


def _confusion_csv(confusion: dict[str, int]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["actual_label", "predicted_label", "count"])
    writer.writerow(["B", "B", confusion["true_negative"]])
    writer.writerow(["B", "M", confusion["false_positive"]])
    writer.writerow(["M", "B", confusion["false_negative"]])
    writer.writerow(["M", "M", confusion["true_positive"]])
    return stream.getvalue().encode("utf-8")


def _summary_svg(metrics: dict[str, float]) -> bytes:
    balanced = metrics["balanced_accuracy"]
    recall = metrics["malignant_recall"]
    balanced_width = round(360 * balanced, 3)
    recall_width = round(360 * recall, 3)
    document = f"""<svg xmlns="http://www.w3.org/2000/svg" width="560" height="220" viewBox="0 0 560 220" role="img" aria-labelledby="title desc">
  <title id="title">WDBC Round 1 observed metrics</title>
  <desc id="desc">Balanced accuracy {balanced:.6f}; malignant recall {recall:.6f}.</desc>
  <rect width="560" height="220" fill="white"/>
  <text x="24" y="32" font-family="sans-serif" font-size="18">WDBC Round 1</text>
  <text x="24" y="76" font-family="sans-serif" font-size="14">Balanced accuracy</text>
  <rect x="168" y="60" width="360" height="20" fill="#e5e7eb"/>
  <rect x="168" y="60" width="{balanced_width}" height="20" fill="#2563eb"/>
  <text x="168" y="100" font-family="monospace" font-size="13">{balanced:.6f}</text>
  <text x="24" y="146" font-family="sans-serif" font-size="14">Malignant recall</text>
  <rect x="168" y="130" width="360" height="20" fill="#e5e7eb"/>
  <rect x="168" y="130" width="{recall_width}" height="20" fill="#dc2626"/>
  <text x="168" y="170" font-family="monospace" font-size="13">{recall:.6f}</text>
  <text x="24" y="205" font-family="sans-serif" font-size="11">Observed on a deterministic stratified holdout; not for clinical use.</text>
</svg>
"""
    return document.encode("utf-8")


def run_baseline(dataset_path: Path, output_root: Path, config: BaselineConfig) -> dict[str, Any]:
    dataset = load_wdbc(dataset_path, config)
    train_indices, test_indices = stratified_split(
        dataset.labels,
        test_fraction=config.test_fraction,
        seed=config.seed,
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
    predictions = (probabilities >= config.decision_threshold).astype(np.int64)
    evaluation = _evaluate(dataset.labels[test_indices], predictions)
    metrics = {
        "balanced_accuracy": float(evaluation["balanced_accuracy"]),
        "malignant_recall": float(evaluation["malignant_recall"]),
    }
    round2_plan = build_round2_plan(metrics, config)
    run_summary = {
        "schema_version": "1.0",
        "dataset": {
            "feature_count": int(dataset.features.shape[1]),
            "row_count": int(dataset.features.shape[0]),
            "sha256": dataset.sha256,
            "size_bytes": dataset.size_bytes,
        },
        "parameters": {
            "decision_threshold": config.decision_threshold,
            "iterations": config.iterations,
            "l2": config.l2,
            "learning_rate": config.learning_rate,
            "seed": config.seed,
            "test_fraction": config.test_fraction,
        },
        "split": {
            "test_count": len(test_indices),
            "train_count": len(train_indices),
        },
        "confusion": evaluation["confusion"],
        "metrics": metrics,
    }
    model = {
        "schema_version": "1.0",
        "algorithm": "standardized_full_batch_logistic_regression",
        "bias": bias,
        "coefficients": weights.tolist(),
        "feature_means": means.tolist(),
        "feature_scales": scales.tolist(),
        "parameters": run_summary["parameters"],
    }

    payloads = {
        "balanced-accuracy": _json_bytes(
            _metric_payload("balanced_accuracy", metrics["balanced_accuracy"])
        ),
        "confusion-matrix": _confusion_csv(evaluation["confusion"]),
        "malignant-recall": _json_bytes(
            _metric_payload("malignant_recall", metrics["malignant_recall"])
        ),
        "model": _json_bytes(model),
        "predictions": _predictions_csv(
            test_indices,
            dataset.labels[test_indices],
            predictions,
            probabilities,
        ),
        "round2-plan": _json_bytes(round2_plan),
        "run-summary": _json_bytes(run_summary),
        "summary-plot": _summary_svg(metrics),
    }
    for artifact_id, relative_path in ARTIFACT_FILES.items():
        _atomic_write(output_root / relative_path, payloads[artifact_id])
    return run_summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-size-bytes", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--test-fraction", type=float, required=True)
    parser.add_argument("--learning-rate", type=float, required=True)
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument("--l2", type=float, required=True)
    parser.add_argument("--decision-threshold", type=float, required=True)
    parser.add_argument("--recall-target", type=float, required=True)
    parser.add_argument("--threshold-step", type=float, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config = BaselineConfig(
        seed=args.seed,
        test_fraction=args.test_fraction,
        learning_rate=args.learning_rate,
        iterations=args.iterations,
        l2=args.l2,
        decision_threshold=args.decision_threshold,
        recall_target=args.recall_target,
        threshold_step=args.threshold_step,
        expected_sha256=args.expected_sha256,
        expected_size_bytes=args.expected_size_bytes,
    )
    summary = run_baseline(args.dataset, Path.cwd(), config)
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
