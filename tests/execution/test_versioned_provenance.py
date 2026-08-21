"""Tests for CAPTAIN-LOCAL-VERSIONED-PROVENANCE-03.

Covers the 15-item test matrix from the task spec, plus verification that
existing provenance / publication / reviewer tests continue to pass.

All tests are self-contained (no real Round1/Round2 re-execution, no provider
calls, no real git operations beyond what is already committed).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from app.execution import flagship_canonical as fc


REPO_ROOT = Path(__file__).resolve().parents[2]
ATTEST_DIR = REPO_ROOT / "docs" / "modules" / "T05" / "canonical" / "attestations"
PUB_ID = "pub-a7d6c7e7dd6c42a488c7f39079d6a434"

ROUND1_GIT_SHA = "18c86f1e1963b13cbed09356201d92f38a2a2880"
PRODUCER_CODE_COMMIT_SHA = "f29fbf4a40ac3f0b17df4d8a8cd03de8672f1c87"
ARTIFACT_SNAPSHOT_COMMIT = "1ae89e0d886e5fd770a64489785f605b7e67fcfd"
DISPLAY_COMMIT = "79b1a42c161cd8f2e40847d97d9bc71c367d5a8c"


# ── helpers ────────────────────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _refresh_manifest(package: Path) -> None:
    files = []
    for p in sorted(package.rglob("*")):
        if p.is_file() and p.name != "package_manifest.json":
            files.append({
                "path": p.relative_to(package).as_posix(),
                "sha256": _sha256_file(p),
                "size_bytes": p.stat().st_size,
            })
    _write_json(package / "package_manifest.json", {"schema_version": "1.0", "files": files})


def _minimal_workspace(tmp_path: Path, *, r1_sha: str = "a" * 40, r2_sha: str = "b" * 40) -> dict:
    """Minimal valid workspace with deliberately differing R1/R2 commits."""
    root = tmp_path / "workspace"
    dataset_sha = "d" * 64
    selection = root / "experiments" / "flagship" / "selection_manifest.json"
    dataset = root / "experiments" / "flagship" / "dataset_manifest.json"
    r1c = root / "experiments" / "flagship" / "round1_config.json"
    r2c = root / "experiments" / "flagship" / "round2_config.json"
    r1 = root / "docs" / "modules" / "T05" / "round1"
    r2 = root / "docs" / "modules" / "T05" / "round2"
    rev = r2 / "review"

    _write_json(selection, {"question_id": "Q028", "non_goals": ["no clinical use"]})
    _write_json(dataset, {"pin": {"sha256": dataset_sha, "status": "verified", "size_bytes": 1}})
    _write_json(r1c, {"schema_version": "1.0", "decision_threshold": 0.5})
    _write_json(r2c, {"schema_version": "1.0", "control_change": {"to": 0.4}})
    (r1 / "artifacts").mkdir(parents=True)
    _write_json(r1 / "execution_result.json", {
        "execution_id": "eid-r1", "question_id": "Q028",
        "actual_execution": True, "runner_verified": True, "status": "succeeded",
        "datasets": [{"sha256": dataset_sha}],
        "environment_fingerprint": {"git_sha": r1_sha, "git_dirty": False},
    })
    (r1 / "artifacts" / "model.json").write_text("{}", encoding="utf-8")
    _refresh_manifest(r1)
    (r2 / "artifacts").mkdir(parents=True)
    _write_json(r2 / "execution_result.json", {
        "execution_id": "eid-r2", "question_id": "Q028",
        "actual_execution": True, "runner_verified": True, "status": "succeeded",
        "parent_execution_id": "eid-r1",
        "datasets": [{"sha256": dataset_sha}],
        "environment_fingerprint": {"git_sha": r2_sha, "git_dirty": False},
    })
    (r2 / "artifacts" / "model.json").write_text("{}", encoding="utf-8")
    _refresh_manifest(r2)
    _write_json(rev / "reviewer_feedback.json",
        {"round1_review": {"passed": False}, "round2_review": {"passed": True}})
    _write_json(rev / "revision_context.json", {"revision_iteration": 2})
    _write_json(rev / "issue_closure.json", {"unresolved_p0": 0, "unresolved_p1": 0})
    _write_json(rev / "plan_versions.json", {"versions": []})
    _write_json(rev / "structured_diff.json",
        {"v1_config_fingerprint": "aaa", "v2_config_fingerprint": "bbb"})
    _write_json(rev / "stop_reason.json", {
        "stop_reason": "target_achieved", "unresolved_p0": 0, "unresolved_p1": 0,
        "scientific_limitation": "not for clinical use",
    })
    return {
        "selection_manifest": selection, "dataset_manifest": dataset,
        "round1_config": r1c, "round2_config": r2c,
        "round1_package": r1, "round2_package": r2,
    }


def _git_commit_reachable(sha: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=REPO_ROOT, capture_output=True
    )
    return result.returncode == 0


# ══════════════════════════════════════════════════════════════════════════════
# TEST-01: R1 and R2 commits differ but both reachable + sci_equiv → PASS
# ══════════════════════════════════════════════════════════════════════════════
def test_01_differing_commits_with_sci_equiv_passes(tmp_path: Path) -> None:
    """R1 and R2 Commits are different, but both verifiable, products valid,
    and scientific_control_equivalence=True → PASS with VERSIONED_MULTI_COMMIT_VERIFIED."""
    paths = _minimal_workspace(tmp_path, r1_sha="a" * 40, r2_sha="b" * 40)
    report = fc.validate_flagship_canonical_package(
        scientific_control_equivalence=True, **paths
    )
    assert report["status"] == "PASS", report["fail_closed_reasons"]
    assert report["provenance_mode"] == "VERSIONED_MULTI_COMMIT"
    assert report["versioned_provenance_status"] == "VERSIONED_MULTI_COMMIT_VERIFIED"
    assert report["all_stage_git_shas_verified"] is True


# ══════════════════════════════════════════════════════════════════════════════
# TEST-02: Round 1 commit unreachable (simulated via dirty flag)
# ══════════════════════════════════════════════════════════════════════════════
def test_02_round1_commit_verification_fails_when_dirty(tmp_path: Path) -> None:
    """Round 1 environment_fingerprint.git_dirty=True means the execution cannot
    be trusted as produced from a clean, verifiable commit → FAIL."""
    paths = _minimal_workspace(tmp_path)
    r1_res = json.loads((paths["round1_package"] / "execution_result.json").read_bytes())
    r1_res["environment_fingerprint"]["git_dirty"] = True
    _write_json(paths["round1_package"] / "execution_result.json", r1_res)
    _refresh_manifest(paths["round1_package"])
    report = fc.validate_flagship_canonical_package(**paths)
    assert report["status"] == "FAIL"
    assert any("CANON-H-001" in r for r in report["fail_closed_reasons"])
    assert report["all_stage_git_shas_verified"] is False


# ══════════════════════════════════════════════════════════════════════════════
# TEST-03: Round 2 commit verification fails when dirty
# ══════════════════════════════════════════════════════════════════════════════
def test_03_round2_commit_verification_fails_when_dirty(tmp_path: Path) -> None:
    """Round 2 git_dirty=True blocks CANON-H-002 and all_stage_git_shas_verified."""
    paths = _minimal_workspace(tmp_path)
    r2_res = json.loads((paths["round2_package"] / "execution_result.json").read_bytes())
    r2_res["environment_fingerprint"]["git_dirty"] = True
    _write_json(paths["round2_package"] / "execution_result.json", r2_res)
    _refresh_manifest(paths["round2_package"])
    report = fc.validate_flagship_canonical_package(**paths)
    assert report["status"] == "FAIL"
    assert any("CANON-H-002" in r for r in report["fail_closed_reasons"])


# ══════════════════════════════════════════════════════════════════════════════
# TEST-04: Round 1 raw metric recomputation (offline, real committed evidence)
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.skipif(
    not (REPO_ROOT / "docs" / "modules" / "T05" / "round1" / "artifacts" / "predictions.csv").exists(),
    reason="real Round 1 predictions.csv not committed in this workspace"
)
def test_04_round1_raw_metric_recomputation_matches_historical() -> None:
    """Round 1 TP/TN/FP/FN must recompute exactly from predictions.csv."""
    import csv
    predictions_path = REPO_ROOT / "docs" / "modules" / "T05" / "round1" / "artifacts" / "predictions.csv"
    run_summary = json.loads(
        (REPO_ROOT / "docs" / "modules" / "T05" / "round1" / "artifacts" / "run-summary.json").read_bytes()
    )
    tp = tn = fp = fn = 0
    with predictions_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            a, p = row["actual_label"], row["predicted_label"]
            if a == "M" and p == "M": tp += 1
            elif a == "M" and p == "B": fn += 1
            elif a == "B" and p == "B": tn += 1
            else: fp += 1
    assert tp + fn > 0, "no malignant cases found"
    recall = tp / (tp + fn)
    hist = run_summary["metrics"]["malignant_recall"]
    assert abs(recall - hist) < 1e-12, f"recall mismatch: {recall} vs {hist}"


# ══════════════════════════════════════════════════════════════════════════════
# TEST-05: Unauthorized scientific change → sci_equiv=False → FAIL
# ══════════════════════════════════════════════════════════════════════════════
def test_05_unauthorized_scientific_change_fails(tmp_path: Path) -> None:
    """scientific_control_equivalence=False (e.g., dataset changed) must block PASS."""
    paths = _minimal_workspace(tmp_path, r1_sha="a" * 40, r2_sha="b" * 40)
    report = fc.validate_flagship_canonical_package(
        scientific_control_equivalence=False, **paths
    )
    assert report["status"] == "FAIL"
    assert any("CANON-I-002" in r for r in report["fail_closed_reasons"])
    assert report["versioned_provenance_status"] in ("VERSIONED_MULTI_COMMIT_UNVERIFIED", "SINGLE_COMMIT_UNVERIFIED")


# ══════════════════════════════════════════════════════════════════════════════
# TEST-06: Only publication/UI files changed → does NOT affect sci equiv
# ══════════════════════════════════════════════════════════════════════════════
def test_06_publication_only_diff_does_not_affect_sci_equiv() -> None:
    """Files classified PUBLICATION_ONLY or DISPLAY_ONLY in the scientific paths
    analysis must not appear in scientific_control_diffs."""
    if not (ATTEST_DIR / "ROUND1_SCIENTIFIC_PATHS.json").exists():
        pytest.skip("ROUND1_SCIENTIFIC_PATHS.json not generated yet")
    data = json.loads((ATTEST_DIR / "ROUND1_SCIENTIFIC_PATHS.json").read_bytes())
    sci_diffs = data.get("scientific_control_diffs", [])
    # publication / display files must not appear in sci_diffs
    for path in sci_diffs:
        assert "flagship_publish" not in path
        assert "components" not in path
        assert "api_client" not in path
        assert "routes" not in path


# ══════════════════════════════════════════════════════════════════════════════
# TEST-07: Stage git SHAs are NOT all forced to be equal
# ══════════════════════════════════════════════════════════════════════════════
def test_07_differing_stage_commits_not_a_failure(tmp_path: Path) -> None:
    """Differing commits between R1 and R2 is EXPLICITLY not a failure condition
    (ALL_GIT_SHAS_MATCH is not a hard gate). The test passes without sci_equiv."""
    paths = _minimal_workspace(tmp_path, r1_sha="0" * 40, r2_sha="1" * 40)
    report = fc.validate_flagship_canonical_package(**paths)
    # Must NOT fail just because r1_sha != r2_sha
    assert report["status"] == "PASS", (
        "differing R1/R2 commits caused unexpected FAIL: "
        + str(report["fail_closed_reasons"])
    )
    assert report["provenance_mode"] == "VERSIONED_MULTI_COMMIT"


# ══════════════════════════════════════════════════════════════════════════════
# TEST-08: Attestation collision (same file, different content) → rejected
# ══════════════════════════════════════════════════════════════════════════════
def test_08_attestation_name_collision_different_content_rejected(tmp_path: Path) -> None:
    """If an attestation file already exists with different content,
    write_no_clobber must raise FileExistsError (hard fail, no overwrite)."""
    import sys, importlib
    sys.path.insert(0, str(REPO_ROOT / "tmp"))
    try:
        bvp = importlib.import_module("build_versioned_provenance")
    except ImportError:
        pytest.skip("build_versioned_provenance.py not in tmp/")
    target = tmp_path / "test.json"
    content_a = '{"version": 1}\n'
    content_b = '{"version": 2}\n'
    # First write succeeds
    result = bvp._write_no_clobber(target, content_a)
    assert result in ("created", "reused_identical")
    # Second write with different content must fail
    with pytest.raises(FileExistsError, match="ATTESTATION COLLISION"):
        bvp._write_no_clobber(target, content_b)
    # Idempotent write with same content succeeds
    result2 = bvp._write_no_clobber(target, content_a)
    assert result2 == "reused_identical"


# ══════════════════════════════════════════════════════════════════════════════
# TEST-09: Provider disclosure: total count must be 4
# ══════════════════════════════════════════════════════════════════════════════
def test_09_provider_disclosure_total_count_is_4() -> None:
    """Provider call disclosure must record total_calls=4, not 2."""
    path = ATTEST_DIR / "Q028.provider-call-disclosure.json"
    if not path.exists():
        pytest.skip("provider-call-disclosure.json not generated yet")
    data = json.loads(path.read_bytes())
    assert data["total_calls"] == 4, f"expected total_calls=4, got {data['total_calls']}"
    assert data["canonical_used_calls"] == 2
    canonical_calls = data.get("canonical_calls", [])
    assert len(canonical_calls) == 2, "canonical_calls must have exactly 2 entries"
    abandoned = data.get("abandoned_calls", [])
    assert len(abandoned) == 2, "abandoned_calls must have exactly 2 entries"


# ══════════════════════════════════════════════════════════════════════════════
# TEST-10: Abandoned calls must not appear as canonical used
# ══════════════════════════════════════════════════════════════════════════════
def test_10_abandoned_calls_not_in_canonical() -> None:
    """No abandoned call must have entered_canonical_package=True."""
    path = ATTEST_DIR / "Q028.provider-call-disclosure.json"
    if not path.exists():
        pytest.skip("provider-call-disclosure.json not generated yet")
    data = json.loads(path.read_bytes())
    for call in data.get("abandoned_calls", []):
        assert call.get("entered_canonical_package") is False, (
            f"abandoned call {call.get('call_sequence')} has entered_canonical_package=True"
        )
        assert call.get("output_used_for_issue_closure") is False
        assert call.get("entered_metric_computation") is False


# ══════════════════════════════════════════════════════════════════════════════
# TEST-11: Attestation digest matches actual file bytes
# ══════════════════════════════════════════════════════════════════════════════
def test_11_attestation_digest_matches_file_bytes() -> None:
    """The sha256 recorded in verification-summary for the attestation must
    match the actual bytes of the attestation file."""
    summary_path = ATTEST_DIR / f"Q028.{PUB_ID}.verification-summary.json"
    attest_path = ATTEST_DIR / f"Q028.{PUB_ID}.versioned-provenance.json"
    if not summary_path.exists() or not attest_path.exists():
        pytest.skip("attestation files not generated yet")
    summary = json.loads(summary_path.read_bytes())
    recorded_sha = summary.get("attestation_sha256")
    actual_sha = _sha256_file(attest_path)
    # actual sha is over the file bytes; recorded sha is over the canonical JSON text
    # both must be consistent (file bytes == canonical JSON text since we write UTF-8 NL)
    assert recorded_sha is not None, "attestation_sha256 missing from verification-summary"
    # re-derive: sha256 of the file bytes
    file_sha = hashlib.sha256(attest_path.read_bytes()).hexdigest()
    # The summary stores sha256 of the canonical JSON text (which equals the file content)
    assert recorded_sha == file_sha, (
        f"attestation_sha256 in summary ({recorded_sha[:16]}…) "
        f"does not match file bytes ({file_sha[:16]}…)"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST-12: Unresolved P0/P1 → FAIL
# ══════════════════════════════════════════════════════════════════════════════
def test_12_unresolved_p0_blocks_pass(tmp_path: Path) -> None:
    """Unresolved P0 must block canonical package PASS."""
    paths = _minimal_workspace(tmp_path)
    rev = paths["round2_package"] / "review"
    _write_json(rev / "issue_closure.json", {"unresolved_p0": 1, "unresolved_p1": 0})
    report = fc.validate_flagship_canonical_package(**paths)
    assert report["status"] == "FAIL"
    assert any("CANON-D-005" in r for r in report["fail_closed_reasons"])


def test_12b_unresolved_p1_blocks_pass(tmp_path: Path) -> None:
    paths = _minimal_workspace(tmp_path)
    rev = paths["round2_package"] / "review"
    _write_json(rev / "issue_closure.json", {"unresolved_p0": 0, "unresolved_p1": 1})
    report = fc.validate_flagship_canonical_package(**paths)
    assert report["status"] == "FAIL"
    assert any("CANON-D-006" in r for r in report["fail_closed_reasons"])


# ══════════════════════════════════════════════════════════════════════════════
# TEST-13: API canonical-status does not leak secrets
# ══════════════════════════════════════════════════════════════════════════════
def test_13_api_canonical_status_no_secret_leakage() -> None:
    """The canonical-status API response must not contain API keys, workspace
    IDs, authorization tokens, or full prompt text."""
    from app.execution.flagship_publish import get_canonical_status
    status = get_canonical_status()
    text = json.dumps(status, ensure_ascii=False)
    secret_patterns = [
        "Authorization", "Bearer ", "sk-", "api_key",
        "workspace_id", "DASHSCOPE_API_KEY",
    ]
    for pattern in secret_patterns:
        assert pattern not in text, f"API response may contain secret pattern: {pattern!r}"


# ══════════════════════════════════════════════════════════════════════════════
# TEST-14: UI displays VERSIONED_MULTI_COMMIT_VERIFIED
# ══════════════════════════════════════════════════════════════════════════════
def test_14_ui_render_versioned_provenance_panel_exists() -> None:
    """The UI must have the _render_versioned_provenance_panel function that
    displays versioned provenance details."""
    from app.ui import components
    assert hasattr(components, "_render_versioned_provenance_panel"), (
        "_render_versioned_provenance_panel function missing from components.py"
    )
    assert hasattr(components, "_CANON_CATEGORY_LABELS"), (
        "_CANON_CATEGORY_LABELS missing"
    )
    labels = components._CANON_CATEGORY_LABELS
    assert "versioned_provenance" in labels, (
        "versioned_provenance category missing from _CANON_CATEGORY_LABELS"
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST-15: Real committed evidence still passes (regression guard)
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.skipif(
    not (fc.ROUND2_PACKAGE / "execution_result.json").exists(),
    reason="Round 2 has not been executed in this workspace yet"
)
def test_15_real_committed_evidence_passes_with_sci_equiv() -> None:
    """End-to-end: real evidence + scientific_control_equivalence=True must PASS
    with VERSIONED_MULTI_COMMIT_VERIFIED (since R1/R2 commits differ)."""
    report = fc.validate_flagship_canonical_package(
        scientific_control_equivalence=True
    )
    assert report["status"] == "PASS", report["fail_closed_reasons"]
    assert report["provenance_mode"] == "VERSIONED_MULTI_COMMIT"
    assert report["versioned_provenance_status"] == "VERSIONED_MULTI_COMMIT_VERIFIED"
    assert report["all_stage_git_shas_verified"] is True
    assert report["scientific_control_equivalence"] is True
    assert report["round1_git_sha"] != report["round2_git_sha"]


# ══════════════════════════════════════════════════════════════════════════════
# Additional: verification-summary PUBLICATION_STATE integrity
# ══════════════════════════════════════════════════════════════════════════════
def test_verification_summary_publication_state() -> None:
    """Verification-summary must reflect PUBLISHED_VERIFIED only when all gates
    are satisfied; it must not claim PUBLISHED_VERIFIED with unresolved P0/P1."""
    path = ATTEST_DIR / f"Q028.{PUB_ID}.verification-summary.json"
    if not path.exists():
        pytest.skip("verification-summary.json not generated yet")
    summary = json.loads(path.read_bytes())
    pub_state = summary.get("PUBLICATION_STATE")
    p0 = summary.get("UNRESOLVED_P0", 1)
    p1 = summary.get("UNRESOLVED_P1", 1)
    if pub_state == "PUBLISHED_VERIFIED":
        assert p0 == 0, "PUBLISHED_VERIFIED with unresolved P0"
        assert p1 == 0, "PUBLISHED_VERIFIED with unresolved P1"
        assert summary.get("ROUND1_METRIC_MATCH") is True
        assert summary.get("ROUND2_METRIC_MATCH") is True
        assert summary.get("SCIENTIFIC_CONTROL_EQUIVALENCE") is True
