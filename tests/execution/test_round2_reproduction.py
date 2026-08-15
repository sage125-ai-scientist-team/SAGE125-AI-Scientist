from __future__ import annotations

import csv
import hashlib
import importlib
import inspect
import json
import math
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
ROUND1_PACKAGE = ROOT / "docs" / "modules" / "T05" / "round1"
ROUND2_MODULE = "app.execution.run_round2"
ROUND1_EXECUTION_ID = "execution-5577816b92ac434c99b9c0ffcda21660"
DATASET_ID = "uci-wdbc-diagnostic-17-1995-10-31"
DATASET_SHA256 = (
    "d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a"
)
SYNTHETIC_TEST_FIXTURE_ONLY = "SYNTHETIC_TEST_FIXTURE_ONLY"
NOT_FORMAL_SCIENTIFIC_EVIDENCE = "NOT_FORMAL_SCIENTIFIC_EVIDENCE"
PACKAGE_FILES = {
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
SCIENTIFIC_FILES = {
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


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


def _manifest(package: Path) -> dict[str, dict[str, Any]]:
    return {
        item["path"]: item
        for item in _load_json(package / "package_manifest.json")["files"]
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


def _synthetic_round2_package(root: Path, *, environment: str) -> Path:
    package = root
    package.mkdir(parents=True)
    fixture_labels = [SYNTHETIC_TEST_FIXTURE_ONLY, NOT_FORMAL_SCIENTIFIC_EVIDENCE]
    dataset = {
        "schema_version": "1.0",
        "dataset_id": DATASET_ID,
        "source_uri": "https://example.invalid/wdbc.data",
        "license": "CC-BY-4.0",
        "version": "1995-10-31",
        "sha256": DATASET_SHA256,
        "size_bytes": 124103,
        "workspace_relative_path": "datasets/wdbc.data",
    }
    artifacts = [
        {
            "artifact_id": artifact_id,
            "relative_path": relative_path,
            "validation_status": "valid",
        }
        for artifact_id, relative_path in (
            ("balanced-accuracy", "output/metrics-balanced-accuracy.json"),
            ("confusion-matrix", "output/confusion-matrix.csv"),
            ("false-negative-rate", "output/metrics-false-negative-rate.json"),
            ("malignant-recall", "output/metrics-malignant-recall.json"),
            ("model", "output/model.json"),
            ("predictions", "output/predictions.csv"),
            ("run-summary", "output/run-summary.json"),
            ("summary-plot", "output/summary.svg"),
        )
    ]
    metrics = [
        {
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
    _write_json(
        package / "execution_spec.json",
        {
            "schema_version": "1.0",
            "spec_id": "wdbc-round2-threshold-sensitivity-v1",
            "question_id": "Q028",
            "round_index": 2,
            "parent_execution_id": ROUND1_EXECUTION_ID,
            "mode": "actual",
            "entrypoint": "wdbc-round2-threshold-sensitivity",
            "seed": 125,
            "datasets": [dataset],
            "fixture_labels": fixture_labels,
        },
    )
    _write_json(
        package / "execution_result.json",
        {
            "schema_version": "1.0",
            "execution_id": f"synthetic-{environment}",
            "spec_id": "wdbc-round2-threshold-sensitivity-v1",
            "question_id": "Q028",
            "round_index": 2,
            "parent_execution_id": ROUND1_EXECUTION_ID,
            "mode": "actual",
            "status": "succeeded",
            "actual_execution": True,
            "runner_verified": True,
            "datasets": [dataset],
            "artifacts": artifacts,
            "metrics": metrics,
            "fixture_labels": fixture_labels,
        },
    )
    _write_json(
        package / "run_metadata.json",
        {
            "schema_version": "1.0",
            "round_index": 2,
            "parent_execution_id": ROUND1_EXECUTION_ID,
            "evaluation_scope": "paired_post_hoc_holdout_sensitivity",
            "formal_round2_executed": True,
            "actual_execution": True,
            "runner_verified": True,
            "dataset": dataset,
            "seed": 125,
            "test_fraction": 0.2,
            "environment": environment,
            "execution_id": f"synthetic-{environment}",
            "workspace_uri": f"workspace://synthetic-{environment}",
            "timestamp": f"2026-08-12T00:00:0{environment[-1]}Z",
            "fixture_labels": fixture_labels,
        },
    )
    _write_json(
        package / "consumer_mapping.json",
        {"schema_version": "1.0", "artifacts": artifacts, "metrics": metrics},
    )
    _write_text(package / "stdout.log", "")
    _write_text(package / "stderr.log", "")
    for metric in metrics:
        _write_json(
            package
            / "artifacts"
            / f"metrics-{metric['name'].replace('_', '-')}.json",
            {"schema_version": "1.0", "metric": metric, "fixture_labels": fixture_labels},
        )
    _write_text(
        package / "artifacts" / "confusion-matrix.csv",
        "actual_label,predicted_B,predicted_M\nB,71,0\nM,2,40\n",
    )
    _write_text(
        package / "artifacts" / "predictions.csv",
        "record_ordinal,actual_label,predicted_label,malignant_probability\n"
        "38,M,M,0.414262720944\n",
    )
    _write_json(
        package / "artifacts" / "model.json",
        {
            "schema_version": "1.0",
            "algorithm": "standardized_full_batch_logistic_regression",
            "feature_means": [0.0, 1.0],
            "feature_scales": [1.0, 2.0],
            "coefficients": [0.25, -0.5],
            "bias": -0.1,
            "parameters": {
                "seed": 125,
                "test_fraction": 0.2,
                "learning_rate": 0.05,
                "iterations": 2000,
                "l2": 0.001,
                "decision_threshold": 0.4,
            },
            "train_ordinals": [1, 2, 3, 4],
            "holdout_ordinals": [38],
            "fixture_labels": fixture_labels,
        },
    )
    _write_json(
        package / "artifacts" / "run-summary.json",
        {
            "schema_version": "1.0",
            "confusion": {
                "true_negative": 71,
                "false_positive": 0,
                "false_negative": 2,
                "true_positive": 40,
            },
            "metrics": {item["name"]: item["value"] for item in metrics},
            "fixture_labels": fixture_labels,
        },
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg"><title>'
        "paired post-hoc holdout sensitivity; not for clinical use; "
        f"{SYNTHETIC_TEST_FIXTURE_ONLY}</title></svg>\n"
    )
    _write_text(package / "artifacts" / "summary.svg", svg)
    comparison = {
        "schema_version": "1.0",
        "evaluation_scope": "paired_post_hoc_holdout_sensitivity",
        "thresholds": {"round1": 0.5, "round2": 0.4},
        "changed_prediction_count": 1,
        "changed_ordinals": [38],
        "round2_confusion": {
            "true_negative": 71,
            "false_positive": 0,
            "false_negative": 2,
            "true_positive": 40,
        },
        "round2_metrics": {item["name"]: item["value"] for item in metrics},
        "fixture_labels": fixture_labels,
    }
    _write_json(package / "comparison" / "two-round-comparison.json", comparison)
    _write_text(
        package / "comparison" / "two-round-comparison.csv",
        "round,threshold,balanced_accuracy,malignant_recall,false_negative_rate\n"
        "1,0.5,0.9642857142857143,0.9285714285714286,0.07142857142857142\n"
        "2,0.4,0.9761904761904762,0.9523809523809523,0.047619047619047616\n",
    )
    _write_text(
        package / "comparison" / "changed-predictions.csv",
        "record_ordinal,actual_label,round1_predicted_label,"
        "round2_predicted_label,malignant_probability\n"
        "38,M,B,M,0.414262720944\n",
    )
    _write_text(package / "comparison" / "two-round-comparison.svg", svg)
    _write_json(
        package / "comparison" / "control-invariants.json",
        {
            "schema_version": "1.0",
            "only_permitted_change": "decision_threshold",
            "all_controls_unchanged": True,
            "fixture_labels": fixture_labels,
        },
    )
    _write_text(
        package / "robustness" / "robustness-folds.csv",
        "fold,threshold,balanced_accuracy,malignant_recall,false_negative_rate,tn,fp,fn,tp\n"
        "1,0.5,0.9,0.9,0.1,4,0,1,4\n1,0.4,1.0,1.0,0.0,4,0,0,5\n",
    )
    _write_json(
        package / "robustness" / "robustness-summary.json",
        {
            "schema_version": "1.0",
            "evaluation_scope": "deterministic_internal_stratified_5fold_robustness",
            "fold_count": 5,
            "seed": 125,
            "fixture_labels": fixture_labels,
        },
    )
    _write_text(package / "robustness" / "robustness-comparison.svg", svg)
    _write_json(
        package / "reproduction" / "reproduction_report.json",
        {
            "schema_version": "1.0",
            "scientific_match": True,
            "byte_identical_claim": False,
            "fixture_labels": fixture_labels,
        },
    )
    _write_text(
        package / "reproduction" / "reproduction_report.md",
        f"# Synthetic reproduction report\n\n{SYNTHETIC_TEST_FIXTURE_ONLY}. "
        "Paired internal sensitivity analysis; not independent, external, "
        "or clinical validation.\n",
    )
    _write_json(
        package / "reproduction" / "environment_fingerprint.json",
        {
            "schema_version": "1.0",
            "environment": environment,
            "python": f"3.12.{environment[-1]}",
            "numpy": f"2.2.{environment[-1]}",
            "fixture_labels": fixture_labels,
        },
    )
    _write_json(
        package / "reproduction" / "artifact_comparison.json",
        {
            "schema_version": "1.0",
            "scientific_files": sorted(SCIENTIFIC_FILES),
            "scientific_match": True,
            "fixture_labels": fixture_labels,
        },
    )
    _refresh_manifest(package)
    actual_files = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    assert actual_files == PACKAGE_FILES
    return package


def _block_formal_runner(module: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = getattr(module, "LocalProcessRunner", None)
    if runner is None:
        pytest.fail("formal runner reference must be patchable", pytrace=False)

    def blocked(*_args: object, **_kwargs: object) -> None:
        pytest.fail("FORMAL_ROUND2_EXECUTION_VIOLATION", pytrace=False)

    monkeypatch.setattr(runner, "run", blocked)


PACKAGE_CASES = [
    pytest.param("destination", id="T05-C-R2-PACKAGE-001"),
    pytest.param("reparse", id="T05-C-R2-PACKAGE-002"),
    pytest.param("staging", id="T05-C-R2-PACKAGE-003"),
    pytest.param("atomic", id="T05-C-R2-PACKAGE-004"),
    pytest.param("cleanup", id="T05-C-R2-PACKAGE-005"),
    pytest.param("manifest-coverage", id="T05-C-R2-PACKAGE-006"),
    pytest.param("manifest-hash", id="T05-C-R2-PACKAGE-007"),
    pytest.param("manifest-size", id="T05-C-R2-PACKAGE-008"),
    pytest.param("json", id="T05-C-R2-PACKAGE-009"),
    pytest.param("csv", id="T05-C-R2-PACKAGE-010"),
    pytest.param("svg", id="T05-C-R2-PACKAGE-011"),
    pytest.param("metadata", id="T05-C-R2-PACKAGE-012"),
    pytest.param("result", id="T05-C-R2-PACKAGE-013"),
    pytest.param("comparison", id="T05-C-R2-PACKAGE-014"),
]


@pytest.mark.parametrize("case", PACKAGE_CASES)
def test_round2_package_contract(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _future_module()
    before = _snapshot_tree(ROUND1_PACKAGE)
    if case in {"destination", "reparse"}:
        destination = tmp_path / "round2"
        if case == "destination":
            destination.mkdir()
        else:
            monkeypatch.setattr(
                module.Path,
                "is_symlink",
                lambda value: value == destination,
            )
        _block_formal_runner(module, monkeypatch)
        with pytest.raises(module.Round2EvidenceError, match="destination"):
            module.run_formal_round2(
                cache_root=tmp_path / "cache",
                package_dir=destination,
                offline=True,
                round1_package_dir=ROUND1_PACKAGE,
            )
        assert not list(tmp_path.rglob("*.part"))
    elif case in {"staging", "atomic", "cleanup"}:
        source = inspect.getsource(module.run_formal_round2)
        compact = "".join(source.split())
        if case == "staging":
            assert ".part" in source and ("uuid" in source or "secrets" in source)
            assert source.count(".part") == 1
        elif case == "atomic":
            assert "os.replace(" in compact or ".replace(" in compact
        else:
            assert "try:" in source and ("rmtree(" in compact or "unlink(" in compact)
            assert "formal_round2_executed" in source
    else:
        first = _synthetic_round2_package(tmp_path / "first", environment="A1")
        second = _synthetic_round2_package(tmp_path / "second", environment="B2")
        report = module.compare_reproduction_packages(first, second)
        if case == "manifest-coverage":
            assert set(_manifest(first)) == PACKAGE_FILES - {"package_manifest.json"}
            assert report["manifest_complete"] is True
        elif case == "manifest-hash":
            assert all(
                item["sha256"] == hashlib.sha256((first / name).read_bytes()).hexdigest()
                for name, item in _manifest(first).items()
            )
        elif case == "manifest-size":
            assert all(
                item["size_bytes"] == (first / name).stat().st_size
                for name, item in _manifest(first).items()
            )
        elif case == "json":
            for path in first.rglob("*.json"):
                raw = path.read_bytes()
                assert not raw.startswith(b"\xef\xbb\xbf")
                assert raw.endswith(b"\n") and b"\r\n" not in raw
                value = json.loads(
                    raw.decode("utf-8"),
                    parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
                    object_pairs_hook=lambda pairs: _reject_duplicate_pairs(pairs),
                )
                assert json.dumps(value, sort_keys=True, allow_nan=False)
        elif case == "csv":
            for path in first.rglob("*.csv"):
                raw = path.read_bytes()
                assert not raw.startswith(b"\xef\xbb\xbf")
                assert b"\r\n" not in raw and raw.endswith(b"\n")
                with path.open(encoding="utf-8", newline="") as stream:
                    assert next(csv.reader(stream))
        elif case == "svg":
            for path in first.rglob("*.svg"):
                text = path.read_text(encoding="utf-8").lower()
                assert text.startswith("<svg")
                assert "paired" in text
                assert "not for clinical use" in text
        elif case == "metadata":
            metadata = _load_json(first / "run_metadata.json")
            assert metadata["round_index"] == 2
            assert metadata["parent_execution_id"] == ROUND1_EXECUTION_ID
            assert metadata["evaluation_scope"] == "paired_post_hoc_holdout_sensitivity"
            assert metadata["formal_round2_executed"] is True
            assert metadata["actual_execution"] is True
        elif case == "result":
            result = _load_json(first / "execution_result.json")
            assert result["actual_execution"] is True
            assert result["runner_verified"] is True
            assert {item["artifact_id"] for item in result["artifacts"]} == {
                "balanced-accuracy",
                "confusion-matrix",
                "false-negative-rate",
                "malignant-recall",
                "model",
                "predictions",
                "run-summary",
                "summary-plot",
            }
            assert {item["name"]: item["artifact_id"] for item in result["metrics"]} == {
                "balanced_accuracy": "balanced-accuracy",
                "false_negative_rate": "false-negative-rate",
                "malignant_recall": "malignant-recall",
            }
        else:
            comparison = _load_json(first / "comparison" / "two-round-comparison.json")
            changes = first / "comparison" / "changed-predictions.csv"
            controls = _load_json(first / "comparison" / "control-invariants.json")
            assert comparison["changed_prediction_count"] == 1
            assert changes.read_text(encoding="utf-8").splitlines()[-1].startswith("38,M,B,M,")
            assert controls["only_permitted_change"] == "decision_threshold"
            assert report["scientific_match"] is True
    assert _snapshot_tree(ROUND1_PACKAGE) == before


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


SECURITY_CASES = [
    pytest.param("content", id="T05-C-R2-SECURITY-001"),
    pytest.param("fail-closed", id="T05-C-R2-SECURITY-002"),
]


@pytest.mark.parametrize("case", SECURITY_CASES)
def test_round2_package_security(case: str, tmp_path: Path) -> None:
    module = _future_module()
    primary = _synthetic_round2_package(tmp_path / "primary", environment="A1")
    secondary = _synthetic_round2_package(tmp_path / "secondary", environment="B2")
    before = _snapshot_tree(ROUND1_PACKAGE)
    if case == "content":
        forbidden = (
            "authorization: bearer",
            "api_key=",
            "cookie:",
            "private key",
            "raw_wdbc",
            "cure_all_cancers",
            "patient_diagnosis",
        )
        for package in (primary, secondary):
            for path in package.rglob("*"):
                if path.is_file():
                    raw = path.read_bytes()
                    text = raw.decode("utf-8").lower()
                    assert not any(marker in text for marker in forbidden)
                    assert not any(part.endswith(":\\") for part in text.split())
                    assert b".part" not in raw
        assert module.compare_reproduction_packages(primary, secondary)[
            "scientific_match"
        ] is True
    else:
        (secondary / "artifacts" / "predictions.csv").unlink()
        with pytest.raises(module.Round2ReproductionError):
            module.compare_reproduction_packages(primary, secondary)
        assert not (tmp_path / "published-round2").exists()
        assert not list(tmp_path.rglob("*.part"))
        assert not list(tmp_path.rglob("*.lock"))
    assert _snapshot_tree(ROUND1_PACKAGE) == before


def _synthetic_wdbc(path: Path) -> None:
    rows = []
    for ordinal in range(30):
        label = "B" if ordinal % 2 == 0 else "M"
        center = 0.0 if label == "B" else 4.0
        features = [
            f"{center + ((ordinal + 1) * (column + 3) % 13) / 100:.4f}"
            for column in range(30)
        ]
        rows.append(",".join([str(900000 + ordinal), label, *features]))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


ROBUST_CASES = [
    pytest.param("fold-count", id="T05-C-R2-ROBUST-001"),
    pytest.param("seed", id="T05-C-R2-ROBUST-002"),
    pytest.param("determinism", id="T05-C-R2-ROBUST-003"),
    pytest.param("coverage", id="T05-C-R2-ROBUST-004"),
    pytest.param("disjoint", id="T05-C-R2-ROBUST-005"),
    pytest.param("stratified", id="T05-C-R2-ROBUST-006"),
    pytest.param("thresholds", id="T05-C-R2-ROBUST-007"),
    pytest.param("fold-train-only", id="T05-C-R2-ROBUST-008"),
    pytest.param("fold-metrics", id="T05-C-R2-ROBUST-009"),
    pytest.param("aggregate", id="T05-C-R2-ROBUST-010"),
    pytest.param("no-selection", id="T05-C-R2-ROBUST-011"),
    pytest.param("scope", id="T05-C-R2-ROBUST-012"),
]


@pytest.mark.parametrize("case", ROBUST_CASES)
def test_round2_internal_robustness(case: str, tmp_path: Path) -> None:
    module = _future_module()
    dataset = tmp_path / "synthetic-wdbc.data"
    _synthetic_wdbc(dataset)
    config = _canonical_config()
    result = module.run_robustness_analysis(dataset, config)
    assert SYNTHETIC_TEST_FIXTURE_ONLY in result["fixture_labels"]
    assert NOT_FORMAL_SCIENTIFIC_EVIDENCE in result["fixture_labels"]
    folds = result["folds"]
    if case == "fold-count":
        assert result["fold_count"] == 5
        assert {fold["fold_index"] for fold in folds} == {1, 2, 3, 4, 5}
    elif case == "seed":
        assert result["seed"] == 125
    elif case == "determinism":
        assert module.run_robustness_analysis(dataset, config) == result
    elif case == "coverage":
        test_ordinals = [ordinal for fold in folds for ordinal in fold["test_ordinals"]]
        assert sorted(test_ordinals) == list(range(1, 31))
        assert len(set(test_ordinals)) == 30
    elif case == "disjoint":
        assert all(
            set(fold["train_ordinals"]).isdisjoint(fold["test_ordinals"])
            for fold in folds
        )
    elif case == "stratified":
        assert all(set(fold["test_labels"]) == {"B", "M"} for fold in folds)
        label_counts = [
            abs(fold["test_labels"].count("B") - fold["test_labels"].count("M"))
            for fold in folds
        ]
        assert max(label_counts) <= 1
    elif case == "thresholds":
        assert result["thresholds"] == [0.5, 0.4]
        assert all(
            [item["threshold"] for item in fold["evaluations"]] == [0.5, 0.4]
            for fold in folds
        )
    elif case == "fold-train-only":
        assert all(fold["fit_scope"] == "fold_train_only" for fold in folds)
        assert all(
            set(fold["fit_ordinals"]) == set(fold["train_ordinals"])
            for fold in folds
        )
    elif case == "fold-metrics":
        for fold in folds:
            for evaluation in fold["evaluations"]:
                assert set(evaluation["metrics"]) == {
                    "balanced_accuracy",
                    "malignant_recall",
                    "false_negative_rate",
                }
                assert set(evaluation["confusion"]) == {
                    "true_negative",
                    "false_positive",
                    "false_negative",
                    "true_positive",
                }
                assert all(math.isfinite(value) for value in evaluation["metrics"].values())
    elif case == "aggregate":
        for threshold in ("0.5", "0.4"):
            for metric in (
                "balanced_accuracy",
                "malignant_recall",
                "false_negative_rate",
            ):
                summary = result["aggregate"][threshold][metric]
                assert set(summary) == {"mean", "std", "min", "max", "fold_count"}
                assert summary["fold_count"] == 5
    elif case == "no-selection":
        assert result["threshold_selection_performed"] is False
        assert result["excluded_folds"] == []
        assert result["reported_fold_indices"] == [1, 2, 3, 4, 5]
    else:
        assert result["evaluation_scope"] == (
            "deterministic_internal_stratified_5fold_robustness"
        )
        assert "external" not in result["evaluation_scope"]
        assert "sklearn" not in inspect.getsource(module).lower()


REPRO_CASES = [
    pytest.param("dataset", id="T05-C-R2-REPRO-001"),
    pytest.param("split", id="T05-C-R2-REPRO-002"),
    pytest.param("predictions", id="T05-C-R2-REPRO-003"),
    pytest.param("metrics", id="T05-C-R2-REPRO-004"),
    pytest.param("model", id="T05-C-R2-REPRO-005"),
    pytest.param("artifacts", id="T05-C-R2-REPRO-006"),
    pytest.param("metadata", id="T05-C-R2-REPRO-007"),
    pytest.param("environment", id="T05-C-R2-REPRO-008"),
    pytest.param("mismatch", id="T05-C-R2-REPRO-009"),
    pytest.param("five-runs", id="T05-C-R2-STABILITY-001"),
    pytest.param("residue", id="T05-C-R2-STABILITY-002"),
    pytest.param("report", id="T05-C-R2-STABILITY-003"),
]


@pytest.mark.parametrize("case", REPRO_CASES)
def test_round2_reproduction_and_stability(case: str, tmp_path: Path) -> None:
    module = _future_module()
    primary = _synthetic_round2_package(tmp_path / "environment-a", environment="A1")
    secondary = _synthetic_round2_package(tmp_path / "environment-b", environment="B2")
    before = _snapshot_tree(ROUND1_PACKAGE)
    report = module.compare_reproduction_packages(primary, secondary)
    if case == "dataset":
        assert report["dataset_pin_match"] is True
        assert report["dataset_pin"] == {
            "dataset_id": DATASET_ID,
            "sha256": DATASET_SHA256,
            "size_bytes": 124103,
        }
    elif case == "split":
        assert report["split_match"] is True
        assert report["ordinal_match"] is True
    elif case == "predictions":
        assert report["predictions_match"] is True
        assert report["probability_comparison"] == {
            "match": True,
            "atol": 1e-12,
            "rtol": 1e-12,
            "equal_nan": False,
        }
    elif case == "metrics":
        assert report["confusion_match"] is True
        assert report["metrics_match"] is True
    elif case == "model":
        assert report["model_parameters_match"] is True
        assert report["model_arrays_match"] is True
    elif case == "artifacts":
        assert report["scientific_match"] is True
        assert set(report["scientific_files_compared"]) == SCIENTIFIC_FILES
    elif case == "metadata":
        assert report["scientific_match"] is True
        assert set(report["permitted_metadata_differences"]) == {
            "execution_id",
            "timestamp",
            "workspace_uri",
        }
    elif case == "environment":
        assert report["environment_versions_recorded"] is True
        assert report["byte_identical_claim"] is False
        assert report["structural_and_numeric_comparison"] is True
    elif case == "mismatch":
        mutations = (
            ("dataset", "run_metadata.json", ("dataset", "sha256"), "0" * 64),
            ("split", "artifacts/model.json", ("holdout_ordinals",), [39]),
            ("probability", "artifacts/predictions.csv", (), None),
            ("model", "artifacts/model.json", ("bias",), 99.0),
            ("metric", "artifacts/run-summary.json", ("metrics", "malignant_recall"), 0.1),
        )
        for index, (label, relative, keys, replacement) in enumerate(mutations):
            candidate = _synthetic_round2_package(
                tmp_path / f"mismatch-{index}", environment=f"C{index}"
            )
            path = candidate / relative
            if label == "probability":
                text = path.read_text(encoding="utf-8").replace(
                    "0.414262720944", "0.414262720945"
                )
                _write_text(path, text)
            else:
                value = _load_json(path)
                target: Any = value
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = replacement
                _write_json(path, value)
            _refresh_manifest(candidate)
            with pytest.raises(module.Round2ReproductionError, match=label):
                module.compare_reproduction_packages(primary, candidate)
    elif case == "five-runs":
        repeats = [
            _synthetic_round2_package(
                tmp_path / f"repeat-{index}", environment=f"R{index}"
            )
            for index in range(5)
        ]
        for candidate in repeats:
            comparison = module.compare_reproduction_packages(primary, candidate)
            assert comparison["scientific_match"] is True
            assert set(comparison["scientific_files_compared"]) == SCIENTIFIC_FILES
    elif case == "residue":
        assert report["network_calls"] == 0
        assert not list(tmp_path.rglob("*.part"))
        assert not list(tmp_path.rglob("*.lock"))
        assert report["child_process_residue"] is False
        assert report["workspace_residue"] is False
    else:
        path = secondary / "reproduction" / "reproduction_report.md"
        text = path.read_text(encoding="utf-8").lower()
        assert "paired internal sensitivity" in text
        assert "not independent" in text
        assert "external" in text and "clinical" in text
        assert all(marker not in text for marker in ("token", "cookie", "private key"))
        assert report["scientific_match"] is True
    assert _snapshot_tree(ROUND1_PACKAGE) == before
