"""Tests for the Q028/WDBC canonical package validator.

Covers both the happy path against the real, already-executed evidence
committed in this workspace, and every required fail-closed scenario
(missing selection/dataset/round1/round2/reviewer artifacts, checksum
mismatch, run/case id mismatch, unresolved P0/P1, identical V1/V2
fingerprints, missing stop reason / scientific scope).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.execution import flagship_canonical as fc


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _minimal_valid_workspace(tmp_path: Path) -> dict[str, Path]:
    """Build a complete, self-consistent, minimal fixture workspace that the
    validator should accept as PASS -- and that tests then selectively break."""
    root = tmp_path / "workspace"
    selection = root / "experiments" / "flagship" / "selection_manifest.json"
    dataset = root / "experiments" / "flagship" / "dataset_manifest.json"
    round1_config = root / "experiments" / "flagship" / "round1_config.json"
    round2_config = root / "experiments" / "flagship" / "round2_config.json"
    round1_package = root / "docs" / "modules" / "T05" / "round1"
    round2_package = root / "docs" / "modules" / "T05" / "round2"
    review_dir = round2_package / "review"

    dataset_sha = "d" * 64

    _write_json(selection, {"question_id": "Q028", "non_goals": ["cure_all_cancers"]})
    _write_json(
        dataset,
        {"dataset_id": "uci-wdbc", "pin": {"sha256": dataset_sha, "status": "verified", "size_bytes": 1}},
    )
    _write_json(round1_config, {"schema_version": "1.0", "decision_threshold": 0.5})
    _write_json(round2_config, {"schema_version": "1.0", "control_change": {"to": 0.4}})

    (round1_package / "artifacts").mkdir(parents=True)
    _write_json(
        round1_package / "execution_result.json",
        {
            "execution_id": "execution-round1",
            "question_id": "Q028",
            "actual_execution": True,
            "runner_verified": True,
            "status": "succeeded",
            "datasets": [{"sha256": dataset_sha}],
        },
    )
    (round1_package / "artifacts" / "model.json").write_text("{}", encoding="utf-8")
    _refresh_manifest(round1_package)

    (round2_package / "artifacts").mkdir(parents=True)
    _write_json(
        round2_package / "execution_result.json",
        {
            "execution_id": "execution-round2",
            "question_id": "Q028",
            "actual_execution": True,
            "runner_verified": True,
            "status": "succeeded",
            "parent_execution_id": "execution-round1",
            "datasets": [{"sha256": dataset_sha}],
        },
    )
    (round2_package / "artifacts" / "model.json").write_text("{}", encoding="utf-8")
    _refresh_manifest(round2_package)

    _write_json(
        review_dir / "reviewer_feedback.json",
        {
            "round1_review": {"passed": False},
            "round2_review": {"passed": True},
        },
    )
    _write_json(review_dir / "revision_context.json", {"revision_iteration": 2})
    _write_json(review_dir / "issue_closure.json", {"unresolved_p0": 0, "unresolved_p1": 0})
    _write_json(review_dir / "plan_versions.json", {"versions": []})
    _write_json(
        review_dir / "structured_diff.json",
        {"v1_config_fingerprint": "aaa", "v2_config_fingerprint": "bbb"},
    )
    _write_json(
        review_dir / "stop_reason.json",
        {
            "stop_reason": "target_achieved",
            "unresolved_p0": 0,
            "unresolved_p1": 0,
            "scientific_limitation": "not for clinical use",
        },
    )

    return {
        "selection_manifest": selection,
        "dataset_manifest": dataset,
        "round1_config": round1_config,
        "round2_config": round2_config,
        "round1_package": round1_package,
        "round2_package": round2_package,
    }


def _validate(paths: dict[str, Path]) -> dict:
    return fc.validate_flagship_canonical_package(**paths)


def test_real_committed_evidence_passes_canonical_validation() -> None:
    """End-to-end sanity check against the real evidence in this workspace."""
    report = fc.validate_flagship_canonical_package()
    assert report["case_id"] == "Q028"
    assert report["check_count"] > 0
    if report["status"] != "PASS":
        pytest.fail(f"unexpected FAIL: {report['fail_closed_reasons']}")
    assert report["round2_blocked"] is False


def test_minimal_fixture_workspace_passes(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    report = _validate(paths)
    assert report["status"] == "PASS"
    assert report["failed_count"] == 0


def test_missing_selection_manifest_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    paths["selection_manifest"].unlink()
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-A-001" in reason for reason in report["fail_closed_reasons"])


def test_missing_dataset_manifest_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    paths["dataset_manifest"].unlink()
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-B-001" in reason for reason in report["fail_closed_reasons"])


def test_missing_round1_execution_result_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    (paths["round1_package"] / "execution_result.json").unlink()
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-C-001" in reason for reason in report["fail_closed_reasons"])


def test_missing_round2_marks_round2_blocked_and_fails(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    shutil.rmtree(paths["round2_package"])
    report = _validate(paths)
    assert report["round2_blocked"] is True
    assert report["status"] == "FAIL"
    assert any("ROUND2_BLOCKED" in reason for reason in report["fail_closed_reasons"])


def test_checksum_mismatch_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    (paths["round1_package"] / "artifacts" / "model.json").write_text('{"tampered": true}', encoding="utf-8")
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-C-004" in reason for reason in report["fail_closed_reasons"])


def test_run_lineage_mismatch_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    result = json.loads((paths["round2_package"] / "execution_result.json").read_text(encoding="utf-8"))
    result["parent_execution_id"] = "execution-someone-else"
    _write_json(paths["round2_package"] / "execution_result.json", result)
    _refresh_manifest(paths["round2_package"])
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-E-002" in reason for reason in report["fail_closed_reasons"])


def test_dataset_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    result = json.loads((paths["round1_package"] / "execution_result.json").read_text(encoding="utf-8"))
    result["datasets"] = [{"sha256": "0" * 64}]
    _write_json(paths["round1_package"] / "execution_result.json", result)
    _refresh_manifest(paths["round1_package"])
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-G-001" in reason for reason in report["fail_closed_reasons"])


def test_unresolved_p0_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    review_dir = paths["round2_package"] / "review"
    _write_json(review_dir / "issue_closure.json", {"unresolved_p0": 1, "unresolved_p1": 0})
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-D-005" in reason for reason in report["fail_closed_reasons"])


def test_unresolved_p1_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    review_dir = paths["round2_package"] / "review"
    _write_json(review_dir / "issue_closure.json", {"unresolved_p0": 0, "unresolved_p1": 2})
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-D-006" in reason for reason in report["fail_closed_reasons"])


def test_identical_v1_v2_fingerprints_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    review_dir = paths["round2_package"] / "review"
    _write_json(
        review_dir / "structured_diff.json",
        {"v1_config_fingerprint": "same", "v2_config_fingerprint": "same"},
    )
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-F-003" in reason for reason in report["fail_closed_reasons"])


def test_missing_stop_reason_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    (paths["round2_package"] / "review" / "stop_reason.json").unlink()
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-F-002" in reason for reason in report["fail_closed_reasons"])


def test_missing_scientific_scope_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    _write_json(paths["selection_manifest"], {"question_id": "Q028"})
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-A-003" in reason for reason in report["fail_closed_reasons"])


def test_reviewer_feedback_not_a_genuine_revision_fails_closed(tmp_path: Path) -> None:
    paths = _minimal_valid_workspace(tmp_path)
    review_dir = paths["round2_package"] / "review"
    _write_json(
        review_dir / "reviewer_feedback.json",
        {"round1_review": {"passed": True}, "round2_review": {"passed": True}},
    )
    report = _validate(paths)
    assert report["status"] == "FAIL"
    assert any("CANON-D-007" in reason for reason in report["fail_closed_reasons"])
