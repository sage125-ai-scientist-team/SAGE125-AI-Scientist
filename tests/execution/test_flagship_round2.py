from __future__ import annotations

import csv
import copy
import hashlib
import importlib
import inspect
import json
import math
import shutil
import socket
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts.execution import DatasetManifest, ExecutionResult


ROOT = Path(__file__).resolve().parents[2]
ROUND1_PACKAGE = ROOT / "docs" / "modules" / "T05" / "round1"
ROUND2_PACKAGE = ROOT / "docs" / "modules" / "T05" / "round2"
ROUND2_CONFIG = ROOT / "experiments" / "flagship" / "round2_config.json"
ROUND2_MODULE = "app.execution.run_round2"
DATASET_MANIFEST = ROOT / "experiments" / "flagship" / "dataset_manifest.json"
SELECTION_MANIFEST = ROOT / "experiments" / "flagship" / "selection_manifest.json"
ROUND1_EXECUTION_ID = "execution-5577816b92ac434c99b9c0ffcda21660"
ROUND1_SOURCE_SHA = "18c86f1e1963b13cbed09356201d92f38a2a2880"
DATASET_ID = "uci-wdbc-diagnostic-17-1995-10-31"
DATASET_SHA256 = (
    "d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a"
)
MODEL_SHA256 = (
    "ce343d6a617a2bda65405c1372a2454a4140e82725a09c885913fd511590aca8"
)
PREDICTIONS_SHA256 = (
    "05008c6176640bbb1134e3f113d985543aa4819ba455a8e610d7e908a8e9275b"
)
EXPECTED_ARTIFACT_IDS = {
    "balanced-accuracy",
    "confusion-matrix",
    "false-negative-rate",
    "malignant-recall",
    "model",
    "predictions",
    "run-summary",
    "summary-plot",
}
EXPECTED_METRIC_LINKS = {
    "balanced_accuracy": "balanced-accuracy",
    "false_negative_rate": "false-negative-rate",
    "malignant_recall": "malignant-recall",
}


def _snapshot_tree(root: Path) -> dict[str, tuple[str, int]]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_size,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="session", autouse=True)
def _round1_package_is_immutable() -> object:
    before = _snapshot_tree(ROUND1_PACKAGE)
    yield
    after = _snapshot_tree(ROUND1_PACKAGE)
    if after != before:
        pytest.fail("ROUND1_PACKAGE_MUTATED", pytrace=False)


@pytest.fixture(autouse=True)
def _deny_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*_args: object, **_kwargs: object) -> None:
        pytest.fail("NETWORK_VIOLATION", pytrace=False)

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)


def _future_module() -> Any:
    try:
        return importlib.import_module(ROUND2_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == ROUND2_MODULE:
            pytest.fail(
                "required module 'app.execution.run_round2' is not implemented",
                pytrace=False,
            )
        raise


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_json_with_nonfinite_token(
    path: Path,
    payload: dict[str, Any],
    *,
    sentinel_path: tuple[str | int, ...],
    token: str,
) -> None:
    if token not in {"NaN", "Infinity", "-Infinity"}:
        raise AssertionError("unsupported non-finite JSON token")

    copied = copy.deepcopy(payload)
    current: Any = copied
    for key in sentinel_path[:-1]:
        current = current[key]

    sentinel = "__T05_NONFINITE_JSON_TOKEN__"
    current[sentinel_path[-1]] = sentinel
    encoded = json.dumps(
        copied,
        allow_nan=False,
        sort_keys=True,
        ensure_ascii=False,
    )
    quoted_sentinel = json.dumps(sentinel)
    if encoded.count(quoted_sentinel) != 1:
        raise AssertionError("non-finite JSON sentinel was not unique")

    invalid_json = encoded.replace(quoted_sentinel, token, 1)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(invalid_json)
        handle.write("\n")


def _predictions() -> list[dict[str, str]]:
    with (ROUND1_PACKAGE / "artifacts" / "predictions.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        return list(csv.DictReader(stream))


def _confusion(
    rows: list[dict[str, str]], threshold: float
) -> tuple[dict[str, int], dict[str, float]]:
    counts = {
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
        counts[key] += 1
    tnr = counts["true_negative"] / (
        counts["true_negative"] + counts["false_positive"]
    )
    recall = counts["true_positive"] / (
        counts["true_positive"] + counts["false_negative"]
    )
    metrics = {
        "balanced_accuracy": (tnr + recall) / 2,
        "malignant_recall": recall,
        "false_negative_rate": 1 - recall,
    }
    return counts, metrics


def _canonical_config() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "question_id": "Q028",
        "round_index": 2,
        "based_on_round": 1,
        "evaluation_scope": "paired_post_hoc_holdout_sensitivity",
        "control_change": {
            "field": "decision_threshold",
            "from": 0.5,
            "to": 0.4,
        },
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


def _refresh_manifest(package: Path) -> None:
    files = []
    for path in sorted(package.rglob("*")):
        if path.is_file() and path.name != "package_manifest.json":
            files.append(
                {
                    "path": path.relative_to(package).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size_bytes": path.stat().st_size,
                }
            )
    _write_json(package / "package_manifest.json", {"schema_version": "1.0", "files": files})


def _copy_round1(tmp_path: Path) -> Path:
    destination = tmp_path / "round1-reference"
    shutil.copytree(ROUND1_PACKAGE, destination)
    return destination


def _round2_control_fixture(tmp_path: Path) -> Path:
    package = tmp_path / "round2-control-fixture"
    shutil.copytree(ROUND1_PACKAGE, package)

    result = _load_json(package / "execution_result.json")
    result.update(
        {
            "round_index": 2,
            "parent_execution_id": ROUND1_EXECUTION_ID,
            "spec_id": "wdbc-round2-threshold-sensitivity-v1",
            "entrypoint": "wdbc-round2-threshold-sensitivity",
        }
    )
    result["metrics"] = [
        {
            "schema_version": "1.0",
            "name": name,
            "value": value,
            "unit": "ratio",
            "source": "observed",
            "artifact_id": artifact_id,
            "validation_status": "valid",
            "round_index": 2,
        }
        for name, artifact_id, value in (
            ("balanced_accuracy", "balanced-accuracy", 0.9761904761904762),
            ("false_negative_rate", "false-negative-rate", 0.047619047619047616),
            ("malignant_recall", "malignant-recall", 0.9523809523809523),
        )
    ]
    _write_json(package / "execution_result.json", result)

    spec = _load_json(package / "execution_spec.json")
    spec.update(
        {
            "round_index": 2,
            "parent_execution_id": ROUND1_EXECUTION_ID,
            "spec_id": "wdbc-round2-threshold-sensitivity-v1",
            "entrypoint": "wdbc-round2-threshold-sensitivity",
        }
    )
    _write_json(package / "execution_spec.json", spec)

    metadata = _load_json(package / "run_metadata.json")
    metadata.update(
        {
            "round_index": 2,
            "parent_execution_id": ROUND1_EXECUTION_ID,
            "evaluation_scope": "paired_post_hoc_holdout_sensitivity",
            "formal_round1_executed": False,
            "formal_round2_executed": True,
            "controls": _canonical_config(),
            "fixture_labels": [
                "SYNTHETIC_TEST_FIXTURE_ONLY",
                "NOT_FORMAL_SCIENTIFIC_EVIDENCE",
            ],
        }
    )
    _write_json(package / "run_metadata.json", metadata)

    model_path = package / "artifacts" / "model.json"
    model = _load_json(model_path)
    model["parameters"]["decision_threshold"] = 0.4
    rows = _predictions()
    holdout = [int(row["record_ordinal"]) for row in rows]
    model["holdout_ordinals"] = holdout
    model["train_ordinals"] = sorted(set(range(1, 570)) - set(holdout))
    _write_json(model_path, model)

    predictions_path = package / "artifacts" / "predictions.csv"
    with predictions_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["predicted_label"] = (
                "M" if float(row["malignant_probability"]) >= 0.4 else "B"
            )
            writer.writerow(row)

    summary_path = package / "artifacts" / "run-summary.json"
    summary = _load_json(summary_path)
    summary["parameters"]["decision_threshold"] = 0.4
    summary["confusion"] = {
        "true_negative": 71,
        "false_positive": 0,
        "false_negative": 2,
        "true_positive": 40,
    }
    summary["metrics"] = {
        "balanced_accuracy": 0.9761904761904762,
        "malignant_recall": 0.9523809523809523,
        "false_negative_rate": 0.047619047619047616,
    }
    _write_json(summary_path, summary)
    _refresh_manifest(package)
    return package


ORACLE_CASES = [
    pytest.param("manifest", id="T05-C-R2-ORACLE-001"),
    pytest.param("execution", id="T05-C-R2-ORACLE-002"),
    pytest.param("controls", id="T05-C-R2-ORACLE-003"),
    pytest.param("predictions", id="T05-C-R2-ORACLE-004"),
    pytest.param("interval", id="T05-C-R2-ORACLE-005"),
    pytest.param("threshold-05", id="T05-C-R2-ORACLE-006"),
    pytest.param("threshold-04", id="T05-C-R2-ORACLE-007"),
    pytest.param("pins-and-flags", id="T05-C-R2-ORACLE-008"),
]


@pytest.mark.parametrize("case", ORACLE_CASES)
def test_committed_round1_oracle(case: str) -> None:
    if case == "manifest":
        manifest = _load_json(ROUND1_PACKAGE / "package_manifest.json")
        indexed = {item["path"]: item for item in manifest["files"]}
        actual = {
            path.relative_to(ROUND1_PACKAGE).as_posix(): path
            for path in ROUND1_PACKAGE.rglob("*")
            if path.is_file() and path.name != "package_manifest.json"
        }
        assert len(indexed) == 14
        assert set(indexed) == set(actual)
        for name, path in actual.items():
            assert indexed[name]["size_bytes"] == path.stat().st_size
            assert indexed[name]["sha256"] == hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    elif case == "execution":
        result = _load_json(ROUND1_PACKAGE / "execution_result.json")
        assert result["execution_id"] == ROUND1_EXECUTION_ID
        assert result["actual_execution"] is True
        assert result["runner_verified"] is True
        assert result["status"] == "succeeded"
        assert result["mode"] == "actual"
        assert result["round_index"] == 1
        assert result["parent_execution_id"] is None
        assert result["environment_fingerprint"]["git_dirty"] is False
        assert result["environment_fingerprint"]["git_sha"] == ROUND1_SOURCE_SHA
    elif case == "controls":
        config = _load_json(ROOT / "experiments" / "flagship" / "round1_config.json")
        model = _load_json(ROUND1_PACKAGE / "artifacts" / "model.json")
        summary = _load_json(ROUND1_PACKAGE / "artifacts" / "run-summary.json")
        expected = {
            "seed": 125,
            "test_fraction": 0.2,
            "learning_rate": 0.05,
            "iterations": 2000,
            "l2": 0.001,
            "decision_threshold": 0.5,
        }
        flattened = {
            "seed": config["seed"],
            "test_fraction": config["test_fraction"],
            **{key: config["optimizer"][key] for key in ("learning_rate", "iterations", "l2")},
            "decision_threshold": config["decision_threshold"],
        }
        assert flattened == expected
        assert model["parameters"] == expected
        assert summary["parameters"] == expected
        assert model["algorithm"] == "standardized_full_batch_logistic_regression"
    elif case == "predictions":
        path = ROUND1_PACKAGE / "artifacts" / "predictions.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            assert reader.fieldnames == [
                "record_ordinal",
                "actual_label",
                "predicted_label",
                "malignant_probability",
            ]
        assert len(rows) == 113
        ordinals = [int(row["record_ordinal"]) for row in rows]
        assert len(set(ordinals)) == 113
        assert all(row["actual_label"] in {"B", "M"} for row in rows)
        assert all(row["predicted_label"] in {"B", "M"} for row in rows)
        probabilities = [float(row["malignant_probability"]) for row in rows]
        assert all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities)
    elif case == "interval":
        rows = [
            row
            for row in _predictions()
            if 0.4 <= float(row["malignant_probability"]) < 0.5
        ]
        assert rows == [
            {
                "record_ordinal": "38",
                "actual_label": "M",
                "predicted_label": "B",
                "malignant_probability": "0.414262720944",
            }
        ]
    elif case == "threshold-05":
        counts, metrics = _confusion(_predictions(), 0.5)
        summary = _load_json(ROUND1_PACKAGE / "artifacts" / "run-summary.json")
        assert counts == {
            "true_negative": 71,
            "false_positive": 0,
            "false_negative": 3,
            "true_positive": 39,
        }
        assert metrics == pytest.approx(
            {
                "balanced_accuracy": 0.9642857142857143,
                "malignant_recall": 0.9285714285714286,
                "false_negative_rate": 0.07142857142857142,
            }
        )
        assert summary["confusion"] == counts
        assert summary["metrics"] == {
            key: metrics[key] for key in ("balanced_accuracy", "malignant_recall")
        }
    elif case == "threshold-04":
        counts, metrics = _confusion(_predictions(), 0.4)
        assert counts == {
            "true_negative": 71,
            "false_positive": 0,
            "false_negative": 2,
            "true_positive": 40,
        }
        assert metrics == pytest.approx(
            {
                "balanced_accuracy": 0.9761904761904762,
                "malignant_recall": 0.9523809523809523,
                "false_negative_rate": 0.047619047619047616,
            }
        )
    else:
        manifest = _load_json(ROUND1_PACKAGE / "package_manifest.json")
        indexed = {item["path"]: item for item in manifest["files"]}
        dataset = _load_json(DATASET_MANIFEST)
        selection = _load_json(SELECTION_MANIFEST)
        plan = _load_json(ROUND1_PACKAGE / "artifacts" / "round2-plan.json")
        assert indexed["artifacts/model.json"]["sha256"] == MODEL_SHA256
        assert indexed["artifacts/predictions.csv"]["sha256"] == PREDICTIONS_SHA256
        assert dataset["dataset_id"] == DATASET_ID
        assert dataset["pin"] == {
            **dataset["pin"],
            "sha256": DATASET_SHA256,
            "size_bytes": 124103,
        }
        assert dataset["storage_policy"]["raw_data_committed"] is False
        assert selection["catalog_redistributed"] is False
        assert selection["original_question_text_embedded"] is False
        assert plan["formal_round2_executed"] is False
        if ROUND2_PACKAGE.exists():
            # Formal Round 2 has since been executed via run_formal_round2().
            # This branch no longer asserts absence; it asserts the produced
            # package is a genuine, verified, lineage-correct execution and
            # never a fabricated or copied result.
            round2_result = _load_json(ROUND2_PACKAGE / "execution_result.json")
            metadata_round2 = _load_json(ROUND2_PACKAGE / "run_metadata.json")
            assert round2_result["actual_execution"] is True
            assert round2_result["runner_verified"] is True
            assert round2_result["status"] == "succeeded"
            assert round2_result["round_index"] == 2
            assert round2_result["parent_execution_id"] == ROUND1_EXECUTION_ID
            assert round2_result["environment_fingerprint"]["git_dirty"] is False
            assert metadata_round2["formal_round2_executed"] is True
            assert metadata_round2["controls"]["question_id"] == "Q028"


CONFIG_CASES = [
    pytest.param("canonical", id="T05-C-R2-CONFIG-001"),
    pytest.param("missing", id="T05-C-R2-CONFIG-002"),
    pytest.param("duplicate", id="T05-C-R2-CONFIG-003"),
    pytest.param("required-missing", id="T05-C-R2-CONFIG-004"),
    pytest.param("extra", id="T05-C-R2-CONFIG-005"),
    pytest.param("numeric-types", id="T05-C-R2-CONFIG-006"),
    pytest.param("identity-drift", id="T05-C-R2-CONFIG-007"),
    pytest.param("control-drift", id="T05-C-R2-CONFIG-008"),
]


@pytest.mark.parametrize("case", CONFIG_CASES)
def test_round2_config_contract(case: str, tmp_path: Path) -> None:
    if case == "missing" and not ROUND2_CONFIG.exists():
        pytest.fail(
            "required config 'experiments/flagship/round2_config.json' is not implemented",
            pytrace=False,
        )
    module = _future_module()
    path = tmp_path / "round2-config.json"
    canonical = _canonical_config()

    if case == "canonical":
        _write_json(path, canonical)
        assert module.load_round2_config(path) == canonical
        assert module.ROUND1_PACKAGE_PATH == ROUND1_PACKAGE
        assert module.ROUND2_CONFIG_PATH == ROUND2_CONFIG
        assert module.ENTRYPOINT_ID == "wdbc-round2-threshold-sensitivity"
        return
    if case == "missing":
        path = tmp_path / "absent.json"
        variants: list[Path] = [path]
    elif case == "duplicate":
        path.write_text(
            json.dumps(canonical)[:-1] + ',"seed":126}\n',
            encoding="utf-8",
            newline="\n",
        )
        variants = [path]
    elif case == "required-missing":
        variants = []
        for field in canonical:
            value = dict(canonical)
            value.pop(field)
            candidate = tmp_path / f"missing-{field}.json"
            _write_json(candidate, value)
            variants.append(candidate)
    elif case == "extra":
        canonical["actual_execution"] = True
        canonical["metrics"] = {"malignant_recall": 1.0}
        canonical["host_path"] = "host-specific"
        _write_json(path, canonical)
        variants = [path]
    elif case == "numeric-types":
        variants = []
        changes: list[Callable[[dict[str, Any]], None]] = [
            lambda value: value.__setitem__("seed", True),
            lambda value: value.__setitem__("test_fraction", float("nan")),
            lambda value: value["control_change"].__setitem__("to", float("inf")),
            lambda value: value["optimizer"].__setitem__("l2", float("-inf")),
            lambda value: value["control_change"].__setitem__("to", 1.0),
            lambda value: value["control_change"].__setitem__("from", 0.0),
        ]
        for index, change in enumerate(changes):
            value = _canonical_config()
            change(value)
            candidate = tmp_path / f"numeric-{index}.json"
            nonfinite = {
                1: (("test_fraction",), "NaN"),
                2: (("control_change", "to"), "Infinity"),
                3: (("optimizer", "l2"), "-Infinity"),
            }.get(index)
            if nonfinite is None:
                _write_json(candidate, value)
            else:
                sentinel_path, token = nonfinite
                _write_json_with_nonfinite_token(
                    candidate,
                    value,
                    sentinel_path=sentinel_path,
                    token=token,
                )
            variants.append(candidate)
    elif case == "identity-drift":
        variants = []
        for field, replacement in (
            ("question_id", "Q029"),
            ("round_index", 3),
            ("based_on_round", 0),
            ("evaluation_scope", "independent_test"),
        ):
            value = _canonical_config()
            value[field] = replacement
            candidate = tmp_path / f"identity-{field}.json"
            _write_json(candidate, value)
            variants.append(candidate)
    else:
        variants = []
        changes = [
            lambda value: value["control_change"].__setitem__("field", "l2"),
            lambda value: value.__setitem__("seed", 126),
            lambda value: value.__setitem__("test_fraction", 0.25),
            lambda value: value["optimizer"].__setitem__("iterations", 1999),
            lambda value: value["required_metrics"].reverse(),
            lambda value: value["robustness"]["thresholds"].reverse(),
        ]
        for index, change in enumerate(changes):
            value = _canonical_config()
            change(value)
            candidate = tmp_path / f"control-{index}.json"
            _write_json(candidate, value)
            variants.append(candidate)

    for candidate in variants:
        with pytest.raises(module.Round2ConfigError) as captured:
            module.load_round2_config(candidate)
        assert str(tmp_path.resolve()) not in str(captured.value)


PARENT_CASES = [
    pytest.param("canonical", id="T05-C-R2-PARENT-001"),
    pytest.param("missing", id="T05-C-R2-PARENT-002"),
    pytest.param("manifest", id="T05-C-R2-PARENT-003"),
    pytest.param("untrusted", id="T05-C-R2-PARENT-004"),
    pytest.param("question", id="T05-C-R2-PARENT-005"),
    pytest.param("execution-state", id="T05-C-R2-PARENT-006"),
    pytest.param("dataset-pin", id="T05-C-R2-PARENT-007"),
    pytest.param("trigger-plan", id="T05-C-R2-PARENT-008"),
]


@pytest.mark.parametrize("case", PARENT_CASES)
def test_round1_parent_evidence_contract(case: str, tmp_path: Path) -> None:
    module = _future_module()
    if case == "canonical":
        reference = module.load_round1_reference(ROUND1_PACKAGE)
        assert reference["execution_result"]["execution_id"] == ROUND1_EXECUTION_ID
        assert reference["dataset_manifest"]["sha256"] == DATASET_SHA256
        return
    if case == "missing":
        package = tmp_path / "absent-parent"
    else:
        package = _copy_round1(tmp_path)
        if case == "manifest":
            with (package / "stdout.log").open("ab") as stream:
                stream.write(b"tamper")
        elif case == "untrusted":
            payload = _load_json(package / "execution_result.json")
            payload["actual_execution"] = False
            payload["runner_verified"] = False
            _write_json(package / "execution_result.json", payload)
            _refresh_manifest(package)
        elif case == "question":
            payload = _load_json(package / "execution_result.json")
            payload["question_id"] = "Q029"
            _write_json(package / "execution_result.json", payload)
            _refresh_manifest(package)
        elif case == "execution-state":
            payload = _load_json(package / "execution_result.json")
            payload.update({"round_index": 2, "status": "failed", "mode": "dry_run"})
            _write_json(package / "execution_result.json", payload)
            _refresh_manifest(package)
        elif case == "dataset-pin":
            payload = _load_json(package / "execution_result.json")
            payload["datasets"][0]["sha256"] = "0" * 64
            _write_json(package / "execution_result.json", payload)
            _refresh_manifest(package)
        else:
            payload = _load_json(package / "artifacts" / "round2-plan.json")
            payload["evidence"]["malignant_recall"] = 0.95
            payload["change"]["to"] = 0.3
            _write_json(package / "artifacts" / "round2-plan.json", payload)
            _refresh_manifest(package)
    with pytest.raises(module.Round2EvidenceError) as captured:
        module.load_round1_reference(package)
    assert str(tmp_path.resolve()) not in str(captured.value)


CONTROL_CASES = [
    pytest.param("dataset-id", id="T05-C-R2-CONTROL-001"),
    pytest.param("dataset-sha", id="T05-C-R2-CONTROL-002"),
    pytest.param("dataset-size", id="T05-C-R2-CONTROL-003"),
    pytest.param("question", id="T05-C-R2-CONTROL-004"),
    pytest.param("seed", id="T05-C-R2-CONTROL-005"),
    pytest.param("test-fraction", id="T05-C-R2-CONTROL-006"),
    pytest.param("optimizer", id="T05-C-R2-CONTROL-007"),
    pytest.param("learning-rate", id="T05-C-R2-CONTROL-008"),
    pytest.param("iterations", id="T05-C-R2-CONTROL-009"),
    pytest.param("l2", id="T05-C-R2-CONTROL-010"),
    pytest.param("train-indices", id="T05-C-R2-CONTROL-011"),
    pytest.param("holdout-ordinals", id="T05-C-R2-CONTROL-012"),
    pytest.param("feature-scaling", id="T05-C-R2-CONTROL-013"),
    pytest.param("model", id="T05-C-R2-CONTROL-014"),
    pytest.param("probabilities", id="T05-C-R2-CONTROL-015"),
    pytest.param("threshold-only", id="T05-C-R2-CONTROL-016"),
]


def _mutate_control(package: Path, case: str) -> None:
    metadata_path = package / "run_metadata.json"
    result_path = package / "execution_result.json"
    model_path = package / "artifacts" / "model.json"
    predictions_path = package / "artifacts" / "predictions.csv"
    metadata = _load_json(metadata_path)
    result = _load_json(result_path)
    model = _load_json(model_path)
    if case == "dataset-id":
        metadata["dataset"]["dataset_id"] = "other-dataset"
    elif case == "dataset-sha":
        metadata["dataset"]["sha256"] = "0" * 64
    elif case == "dataset-size":
        metadata["dataset"]["size_bytes"] = 124102
    elif case == "question":
        result["question_id"] = "Q029"
    elif case == "seed":
        result["seed"] = 126
    elif case == "test-fraction":
        model["parameters"]["test_fraction"] = 0.25
    elif case == "optimizer":
        model["algorithm"] = "different_optimizer"
    elif case == "learning-rate":
        model["parameters"]["learning_rate"] = 0.051
    elif case == "iterations":
        model["parameters"]["iterations"] = 2001
    elif case == "l2":
        model["parameters"]["l2"] = 0.002
    elif case == "train-indices":
        model["train_ordinals"][0] = 999
    elif case == "holdout-ordinals":
        model["holdout_ordinals"][0] = 999
    elif case == "feature-scaling":
        model["feature_means"][0] += 1e-6
        model["feature_scales"][0] = float("nan")
    elif case == "model":
        model["coefficients"][0] += 1e-6
        model["bias"] += 1e-6
    else:
        with predictions_path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        rows[0]["malignant_probability"] = "0.5"
        with predictions_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    _write_json(metadata_path, metadata)
    _write_json(result_path, result)
    if case == "feature-scaling":
        _write_json_with_nonfinite_token(
            model_path,
            model,
            sentinel_path=("feature_scales", 0),
            token="NaN",
        )
    else:
        _write_json(model_path, model)
    _refresh_manifest(package)


@pytest.mark.parametrize("case", CONTROL_CASES)
def test_round2_control_invariants(case: str, tmp_path: Path) -> None:
    module = _future_module()
    reference = module.load_round1_reference(ROUND1_PACKAGE)
    package = _round2_control_fixture(tmp_path)
    before = _snapshot_tree(ROUND1_PACKAGE)
    if case == "threshold-only":
        report = module.validate_control_invariants(reference, package)
        assert report["only_permitted_change"] == "decision_threshold"
        assert report["threshold_change"] == {"from": 0.5, "to": 0.4}
        assert report["changed_prediction_count"] == 1
        assert report["changed_ordinals"] == [38]
        assert report["changed_probability_interval"] == "[0.4,0.5)"
        assert report["float_comparison"] == {
            "atol": 1e-12,
            "rtol": 1e-12,
            "equal_nan": False,
        }
    else:
        _mutate_control(package, case)
        with pytest.raises(module.Round2ControlDriftError, match=case.split("-")[0]):
            module.validate_control_invariants(reference, package)
    assert _snapshot_tree(ROUND1_PACKAGE) == before


PAIRED_CASES = [
    pytest.param("ordinals", id="T05-C-R2-PAIRED-001"),
    pytest.param("labels", id="T05-C-R2-PAIRED-002"),
    pytest.param("probabilities", id="T05-C-R2-PAIRED-003"),
    pytest.param("threshold", id="T05-C-R2-PAIRED-004"),
    pytest.param("changed-count", id="T05-C-R2-PAIRED-005"),
    pytest.param("changed-ordinal", id="T05-C-R2-PAIRED-006"),
    pytest.param("changed-interval", id="T05-C-R2-PAIRED-007"),
    pytest.param("confusion", id="T05-C-R2-PAIRED-008"),
    pytest.param("balanced-accuracy", id="T05-C-R2-PAIRED-009"),
    pytest.param("recall", id="T05-C-R2-PAIRED-010"),
    pytest.param("false-negative-rate", id="T05-C-R2-PAIRED-011"),
    pytest.param("scope", id="T05-C-R2-PAIRED-012"),
]


@pytest.mark.parametrize("case", PAIRED_CASES)
def test_paired_threshold_contract(case: str) -> None:
    module = _future_module()
    reference = module.load_round1_reference(ROUND1_PACKAGE)
    comparison = module.derive_paired_comparison(reference, threshold=0.4)
    rows = _predictions()
    if case == "ordinals":
        assert comparison["record_ordinals"] == [
            int(row["record_ordinal"]) for row in rows
        ]
    elif case == "labels":
        assert comparison["actual_labels"] == [row["actual_label"] for row in rows]
    elif case == "probabilities":
        assert comparison["malignant_probabilities"] == pytest.approx(
            [float(row["malignant_probability"]) for row in rows], abs=1e-12, rel=1e-12
        )
        assert all(math.isfinite(value) for value in comparison["malignant_probabilities"])
    elif case == "threshold":
        assert comparison["thresholds"] == {"round1": 0.5, "round2": 0.4}
    elif case == "changed-count":
        assert len(comparison["changed_predictions"]) == 1
    elif case == "changed-ordinal":
        assert [item["record_ordinal"] for item in comparison["changed_predictions"]] == [38]
    elif case == "changed-interval":
        assert all(
            0.4 <= item["malignant_probability"] < 0.5
            for item in comparison["changed_predictions"]
        )
    elif case == "confusion":
        assert comparison["round2_confusion"] == {
            "true_negative": 71,
            "false_positive": 0,
            "false_negative": 2,
            "true_positive": 40,
        }
    elif case == "balanced-accuracy":
        assert comparison["round2_metrics"]["balanced_accuracy"] == pytest.approx(
            0.9761904761904762
        )
    elif case == "recall":
        assert comparison["round2_metrics"]["malignant_recall"] == pytest.approx(
            0.9523809523809523
        )
    elif case == "false-negative-rate":
        assert comparison["round2_metrics"]["false_negative_rate"] == pytest.approx(
            0.047619047619047616
        )
    else:
        assert comparison["evaluation_scope"] == (
            "paired_post_hoc_holdout_sensitivity"
        )
        claims = json.dumps(comparison, sort_keys=True).lower()
        assert "independent_test" not in claims
        assert "external_validation" not in claims
        assert "clinical_validation" not in claims


SPEC_CASES = [
    pytest.param("spec-id", id="T05-C-R2-SPEC-001"),
    pytest.param("question", id="T05-C-R2-SPEC-002"),
    pytest.param("round", id="T05-C-R2-SPEC-003"),
    pytest.param("parent", id="T05-C-R2-SPEC-004"),
    pytest.param("mode", id="T05-C-R2-SPEC-005"),
    pytest.param("entrypoint", id="T05-C-R2-SPEC-006"),
    pytest.param("resources", id="T05-C-R2-SPEC-007"),
    pytest.param("dataset", id="T05-C-R2-SPEC-008"),
    pytest.param("artifacts", id="T05-C-R2-SPEC-009"),
    pytest.param("metrics", id="T05-C-R2-SPEC-010"),
]


@pytest.mark.parametrize("case", SPEC_CASES)
def test_round2_execution_spec_contract(case: str) -> None:
    module = _future_module()
    reference = module.load_round1_reference(ROUND1_PACKAGE)
    round1_spec = _load_json(ROUND1_PACKAGE / "execution_spec.json")
    dataset = DatasetManifest.model_validate(round1_spec["datasets"][0])
    spec = module.build_execution_spec(dataset, reference)
    if case == "spec-id":
        assert spec.spec_id == "wdbc-round2-threshold-sensitivity-v1"
    elif case == "question":
        assert spec.question_id == "Q028"
    elif case == "round":
        assert spec.round_index == 2
    elif case == "parent":
        assert spec.parent_execution_id == ROUND1_EXECUTION_ID
    elif case == "mode":
        assert spec.mode == "actual"
    elif case == "entrypoint":
        assert module.ENTRYPOINT_ID == "wdbc-round2-threshold-sensitivity"
        assert spec.entrypoint == module.ENTRYPOINT_ID
        source = inspect.getsource(module.run_formal_round2)
        assert 'entrypoint_class="scientific"' in source.replace(" ", "")
    elif case == "resources":
        assert spec.seed == 125
        assert spec.resources.timeout_seconds == 120
        assert spec.resources.network_access == "deny"
        assert spec.cleanup_policy == "preserve"
        assert spec.environment["dependency_allowlist"] == ["numpy", "pydantic"]
    elif case == "dataset":
        assert len(spec.datasets) == 1
        assert spec.datasets[0].model_dump(mode="json") == dataset.model_dump(mode="json")
    elif case == "artifacts":
        requirements = module.artifact_requirements()
        assert {item.artifact_id for item in requirements} == EXPECTED_ARTIFACT_IDS
        assert all(item.required for item in requirements)
    else:
        requirements = module.metric_requirements()
        assert {item.name: item.artifact_id for item in requirements} == EXPECTED_METRIC_LINKS
        assert all(item.required and item.unit == "ratio" for item in requirements)


TRUST_CASES = [
    pytest.param("runner-attested-success", id="T05-C-R2-TRUST-001"),
    pytest.param("fail-closed-paths", id="T05-C-R2-TRUST-002"),
]


@pytest.mark.parametrize("case", TRUST_CASES)
def test_round2_execution_trust_contract(case: str) -> None:
    module = _future_module()
    assert inspect.isfunction(module.run_formal_round2)
    assert inspect.signature(module.run_formal_round2).parameters["offline"].kind is (
        inspect.Parameter.KEYWORD_ONLY
    )
    payload = _load_json(ROUND1_PACKAGE / "execution_result.json")
    if case == "runner-attested-success":
        assert payload["runner_verified"] is True
        assert payload["actual_execution"] is True
        assert payload["status"] == "succeeded"
        assert all(item["source"] == "observed" for item in payload["metrics"])
        with pytest.raises(ValidationError, match="runner-owned truth"):
            ExecutionResult.model_validate(payload)
    else:
        for status in ("rejected", "failed", "timed_out"):
            candidate = dict(payload)
            candidate["status"] = status
            candidate["runner_verified"] = False
            candidate["actual_execution"] = False
            candidate["metrics"] = []
            assert candidate["actual_execution"] is False
            assert candidate["metrics"] == []
        for exception in (
            module.Round2ConfigError,
            module.Round2EvidenceError,
            module.Round2ControlDriftError,
            module.Round2ReproductionError,
        ):
            assert issubclass(exception, Exception)
