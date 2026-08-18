"""Acceptance tests for the reproducible T03 Wave C calibration bundle."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = ROOT / "docs" / "modules" / "T03" / "wave_c"
SCRIPT = BUNDLE_DIR / "run_calibration.py"
MANIFEST = BUNDLE_DIR / "calibration_manifest.json"
RAW_RESULTS = BUNDLE_DIR / "calibration_raw_results.json"
METRICS = BUNDLE_DIR / "calibration_metrics.json"
QUESTION_IDS = (
    "Q001",
    "Q012",
    "Q018",
    "Q024",
    "Q028",
    "Q035",
    "Q042",
    "Q051",
    "Q063",
    "Q077",
    "Q089",
    "Q102",
)


def _load_harness():
    spec = importlib.util.spec_from_file_location("t03_wave_c_calibration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = _load_harness()


def _one_millisecond_timer():
    value = 0

    def tick() -> int:
        nonlocal value
        value += 1_000_000
        return value

    return tick


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_freezes_twelve_representative_contract_fixtures() -> None:
    manifest = HARNESS.load_manifest(MANIFEST)

    assert manifest["dataset_mode"] == "contract_fixture"
    assert manifest["production_pipeline_connected"] is False
    assert manifest["question_text_is_source_booklet_content"] is False
    assert manifest["selection_source"] == "docs/modules/T01/domain_audit_12.json"
    assert manifest["selection_source_not_live_pipeline_traces"] is True
    assert tuple(manifest["question_ids"]) == QUESTION_IDS
    assert len(manifest["questions"]) == 12
    assert len(
        {
            question["negative_case"]["mutation"]
            for question in manifest["questions"]
        }
    ) == 12


def test_every_positive_fixture_is_a_complete_frozen_validation_context() -> None:
    manifest = HARNESS.load_manifest(MANIFEST)

    for question in manifest["questions"]:
        context = HARNESS.build_contract_fixture_context(question)
        payload = context.model_dump(mode="json")
        assert payload["research_plan"]["references"]
        assert payload["research_plan"]["generated_hypotheses"]
        assert payload["research_plan"]["datasets"]["source"]
        assert payload["research_plan"]["datasets"]["target"]
        assert payload["research_plan"]["experiments"]["baselines"]
        assert payload["research_plan"]["experiments"]["metrics"]
        assert payload["research_plan"]["reproducibility_checklist"]
        assert payload["evidence_cards"]
        assert payload["agent_trace"]
        assert payload["execution_metadata"]["mode"] == "contract_fixture"
        assert (
            payload["execution_metadata"]["production_pipeline_connected"]
            is False
        )
        assert payload["question_item"]["source"] == "contract_fixture"
        assert len(context.fingerprint()) == 64


def test_calibration_has_no_false_blocks_false_passes_or_code_misses() -> None:
    manifest = HARNESS.load_manifest(MANIFEST)
    raw, metrics = HARNESS.run_calibration(
        manifest,
        timer_ns=_one_millisecond_timer(),
    )

    assert len(raw["cases"]) == 24
    assert metrics["question_count"] == 12
    assert metrics["positive_case_count"] == 12
    assert metrics["negative_case_count"] == 12
    assert metrics["actual_pass_count"] == 12
    assert metrics["actual_block_count"] == 12
    assert metrics["false_block_count"] == 0
    assert metrics["false_pass_count"] == 0
    assert metrics["expectation_mismatch_count"] == 0
    assert all(case["expectations_met"] for case in raw["cases"])
    assert {case["duration_ms"] for case in raw["cases"]} == {1.0}


def test_q028_flagship_fixture_blocks_a_fabricated_metric() -> None:
    manifest = HARNESS.load_manifest(MANIFEST)
    raw, _ = HARNESS.run_calibration(
        manifest,
        timer_ns=_one_millisecond_timer(),
    )
    q028 = {
        case["case_kind"]: case
        for case in raw["cases"]
        if case["question_id"] == "Q028"
    }

    assert q028["positive"]["actual_status"] == "passed"
    assert q028["positive"]["actual_finding_codes"] == []
    assert q028["negative"]["actual_status"] == "blocked"
    assert "RESULTS_INTEGRITY_ERROR" in q028["negative"][
        "actual_finding_codes"
    ]


def test_recorded_artifacts_match_reproduced_semantics_and_report_timings() -> None:
    manifest = HARNESS.load_manifest(MANIFEST)
    reproduced_raw, reproduced_metrics = HARNESS.run_calibration(
        manifest,
        timer_ns=_one_millisecond_timer(),
    )
    recorded_raw = _read_json(RAW_RESULTS)
    recorded_metrics = _read_json(METRICS)

    assert HARNESS.without_observed_timings(
        recorded_raw
    ) == HARNESS.without_observed_timings(reproduced_raw)
    assert HARNESS.without_observed_timings(
        recorded_metrics
    ) == HARNESS.without_observed_timings(reproduced_metrics)
    assert recorded_metrics["duration_ms"]["total"] > 0
    assert recorded_metrics["duration_ms"]["p95"] > 0
    assert all(case["duration_ms"] > 0 for case in recorded_raw["cases"])
    assert recorded_raw["production_pipeline_connected"] is False
    assert recorded_metrics["production_pipeline_connected"] is False


def test_recorded_artifact_verifier_rejects_metric_tampering(tmp_path) -> None:
    manifest = HARNESS.load_manifest(MANIFEST)
    raw, metrics = HARNESS.run_calibration(
        manifest,
        timer_ns=_one_millisecond_timer(),
    )
    tampered = _read_json(METRICS)
    tampered["false_pass_count"] = 99
    tampered_metrics = tmp_path / "calibration_metrics.json"
    tampered_metrics.write_text(
        json.dumps(tampered, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="stale or altered"):
        HARNESS.verify_recorded_artifacts(
            raw,
            metrics,
            raw_path=RAW_RESULTS,
            metrics_path=tampered_metrics,
        )


def test_reproduction_cli_verify_only_succeeds_without_writing() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--verify-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    metrics = json.loads(completed.stdout)
    assert metrics["case_count"] == 24
    assert metrics["expectation_mismatch_count"] == 0
