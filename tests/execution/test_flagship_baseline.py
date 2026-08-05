from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.contracts.execution import ArtifactManifest, DatasetManifest, MetricRecord
from app.execution.wdbc_baseline import (
    ARTIFACT_FILES,
    BaselineConfig,
    BaselineInputError,
    build_round2_plan,
    load_wdbc,
    run_baseline,
    stratified_split,
)
from app.execution.run_round1 import (
    FormalRunError,
    artifact_requirements,
    build_consumer_mapping,
    build_execution_spec,
    metric_requirements,
    validate_formal_result,
)


def _synthetic_wdbc_bytes() -> bytes:
    rows: list[str] = []
    labels = ["B"] * 357 + ["M"] * 212
    for index, label in enumerate(labels):
        signal = 0.0 if label == "B" else 5.0
        features = [
            f"{signal + ((index * (column + 3)) % 17) / 100:.4f}"
            for column in range(30)
        ]
        rows.append(",".join([str(1_000_000 + index), label, *features]))
    return ("\n".join(rows) + "\n").encode("utf-8")


def _config(raw: bytes, *, iterations: int = 300) -> BaselineConfig:
    return BaselineConfig(
        seed=125,
        test_fraction=0.2,
        learning_rate=0.05,
        iterations=iterations,
        l2=0.001,
        decision_threshold=0.5,
        recall_target=0.95,
        threshold_step=0.1,
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        expected_size_bytes=len(raw),
    )


def _write_dataset(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)


def _dataset_manifest() -> DatasetManifest:
    return DatasetManifest(
        dataset_id="uci-wdbc-diagnostic-17-1995-10-31",
        source_uri=(
            "https://archive.ics.uci.edu/ml/machine-learning-databases/"
            "breast-cancer-wisconsin/wdbc.data"
        ),
        license="CC-BY-4.0",
        version="1995-10-31",
        sha256="d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a",
        size_bytes=124103,
        workspace_relative_path="datasets/wdbc.data",
    )


def _artifact(
    artifact_id: str,
    *,
    kind: str,
    media_type: str,
) -> ArtifactManifest:
    return ArtifactManifest(
        artifact_id=artifact_id,
        relative_path=f"output/{artifact_id}",
        kind=kind,
        media_type=media_type,
        required=True,
        sha256="a" * 64,
        size_bytes=1,
        validation_status="valid",
        collected_at="2026-08-05T00:00:00Z",
    )


def test_baseline_is_deterministic_and_writes_complete_artifacts(tmp_path: Path) -> None:
    raw = _synthetic_wdbc_bytes()
    dataset = tmp_path / "wdbc.data"
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_dataset(dataset, raw)

    first_summary = run_baseline(dataset, first, _config(raw))
    second_summary = run_baseline(dataset, second, _config(raw))

    assert first_summary == second_summary
    assert set(first_summary["metrics"]) == {
        "balanced_accuracy",
        "malignant_recall",
    }
    assert all(0.0 <= value <= 1.0 for value in first_summary["metrics"].values())
    for relative_path in ARTIFACT_FILES.values():
        first_payload = (first / relative_path).read_bytes()
        second_payload = (second / relative_path).read_bytes()
        assert first_payload == second_payload
        assert first_payload
    assert not list(first.rglob("*.part"))
    assert (first / "output/predictions.csv").read_text(encoding="utf-8").startswith(
        "record_ordinal,actual_label,predicted_label,malignant_probability\n"
    )
    assert (first / "output/summary.svg").read_text(encoding="utf-8").startswith(
        '<svg xmlns="http://www.w3.org/2000/svg"'
    )
    for name, artifact_id in (
        ("balanced_accuracy", "balanced-accuracy"),
        ("malignant_recall", "malignant-recall"),
    ):
        payload = json.loads(
            (first / ARTIFACT_FILES[artifact_id]).read_text(encoding="utf-8")
        )
        assert payload["metric"]["name"] == name
        assert payload["metric"]["source"] == "observed"
        assert payload["metric"]["unit"] == "ratio"


def test_dataset_pin_and_schema_fail_closed_before_artifacts(tmp_path: Path) -> None:
    raw = _synthetic_wdbc_bytes()
    dataset = tmp_path / "wdbc.data"
    output = tmp_path / "output-root"
    _write_dataset(dataset, raw)

    wrong_pin = replace(_config(raw), expected_sha256="0" * 64)
    with pytest.raises(BaselineInputError, match="approved pin"):
        run_baseline(dataset, output, wrong_pin)
    assert not output.exists()

    malformed = raw.replace(b",B,", b",X,", 1)
    _write_dataset(dataset, malformed)
    with pytest.raises(BaselineInputError, match="labels"):
        run_baseline(dataset, output, _config(malformed))
    assert not output.exists()


def test_stratified_split_is_repeatable_disjoint_and_class_preserving() -> None:
    labels = np.asarray([0] * 357 + [1] * 212, dtype=np.int64)
    first_train, first_test = stratified_split(labels, test_fraction=0.2, seed=125)
    second_train, second_test = stratified_split(labels, test_fraction=0.2, seed=125)

    assert np.array_equal(first_train, second_train)
    assert np.array_equal(first_test, second_test)
    assert set(first_train).isdisjoint(set(first_test))
    assert sorted(np.concatenate((first_train, first_test)).tolist()) == list(range(569))
    assert set(labels[first_train]) == {0, 1}
    assert set(labels[first_test]) == {0, 1}


def test_round2_plan_is_evidence_based_but_not_executed() -> None:
    raw = _synthetic_wdbc_bytes()
    plan = build_round2_plan({"malignant_recall": 0.8}, _config(raw))

    assert plan["based_on_round"] == 1
    assert plan["evidence"] == {"malignant_recall": 0.8, "target": 0.95}
    assert plan["change"] == {
        "field": "decision_threshold",
        "from": 0.5,
        "to": 0.4,
    }
    assert plan["fixed_controls"] == {"seed": 125, "test_fraction": 0.2}
    assert plan["formal_round2_executed"] is False


def test_round1_spec_declares_actual_scientific_outputs_and_units() -> None:
    spec = build_execution_spec(_dataset_manifest())
    declarations = {item.artifact_id: item for item in artifact_requirements()}
    metrics = {item.name: item for item in metric_requirements()}

    assert spec.mode == "actual"
    assert spec.round_index == 1
    assert spec.seed == 125
    assert spec.cleanup_policy == "preserve"
    assert spec.resources.network_access == "deny"
    assert declarations["predictions"].media_type == "text/csv"
    assert declarations["confusion-matrix"].media_type == "text/csv"
    assert declarations["summary-plot"].media_type == "image/svg+xml"
    assert metrics["balanced_accuracy"].unit == "ratio"
    assert metrics["malignant_recall"].unit == "ratio"


def test_consumer_mapping_exposes_media_type_unit_and_validation() -> None:
    artifacts = [
        _artifact("predictions", kind="table", media_type="text/csv"),
        _artifact("summary-plot", kind="plot", media_type="image/svg+xml"),
        _artifact("balanced-accuracy", kind="metrics", media_type="application/json"),
    ]
    metrics = [
        MetricRecord(
            name="balanced_accuracy",
            value=0.9,
            unit="ratio",
            source="observed",
            artifact_id="balanced-accuracy",
            validation_status="valid",
            round_index=1,
        )
    ]

    mapping = build_consumer_mapping(artifacts, metrics)
    by_id = {item["artifact_id"]: item for item in mapping["artifact_contract"]}
    assert by_id["predictions"] == {
        "artifact_id": "predictions",
        "kind": "table",
        "media_type": "text/csv",
        "unit": "row",
        "validation_status": "valid",
    }
    assert by_id["summary-plot"]["unit"] == "figure"
    assert by_id["balanced-accuracy"]["unit"] == "ratio"
    assert mapping["metric_contract"][0]["validation_status"] == "valid"


def test_formal_result_validation_rejects_untrusted_execution() -> None:
    untrusted = SimpleNamespace(
        status="succeeded",
        mode="actual",
        entrypoint_class="scientific",
        process_started=True,
        process_reaped=True,
        process_alive_after_cleanup=False,
        exit_code=0,
        runner_verified=True,
        datasets_validated=True,
        artifacts_validated=True,
        metrics_validated=True,
        provenance_complete=False,
        scientific_result_usable=False,
        actual_execution=False,
        environment_fingerprint=SimpleNamespace(git_dirty=True),
        error=None,
        artifacts=[],
        metrics=[],
    )

    with pytest.raises(FormalRunError, match="trusted formal evidence"):
        validate_formal_result(untrusted)


def test_load_wdbc_rejects_wrong_row_count_with_matching_pin(tmp_path: Path) -> None:
    raw = _synthetic_wdbc_bytes().splitlines(keepends=True)[:-1]
    shortened = b"".join(raw)
    dataset = tmp_path / "wdbc.data"
    _write_dataset(dataset, shortened)

    with pytest.raises(BaselineInputError, match="exactly 569"):
        load_wdbc(dataset, _config(shortened))
