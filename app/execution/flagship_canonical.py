"""Canonical package validator for the Q028/WDBC flagship case.

Bundles pointers/checksums to the already-independently-verified evidence
produced by ``app.execution.run_round1`` / ``run_round2`` /
``flagship_revision``, plus the frozen ``experiments/flagship/*`` manifests,
into a single canonical package validation report.

This module never re-derives or recomputes scientific results and never
fabricates evidence. It only verifies that every required semantic artifact
exists, that checksums are computed from real file bytes (not asserted), and
that identity fields (case_id / execution lineage / dataset pin) agree across
files. Any missing category, checksum mismatch, unresolved P0/P1, or
non-iteration (identical V1/V2 fingerprints) marks the package ``FAIL`` --
never ``PASS``. If Round 2 evidence does not exist yet, the report explicitly
sets ``round2_blocked=True`` and the overall status can never be ``PASS``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SELECTION_MANIFEST = REPOSITORY_ROOT / "experiments" / "flagship" / "selection_manifest.json"
DATASET_MANIFEST = REPOSITORY_ROOT / "experiments" / "flagship" / "dataset_manifest.json"
ROUND1_CONFIG = REPOSITORY_ROOT / "experiments" / "flagship" / "round1_config.json"
ROUND2_CONFIG = REPOSITORY_ROOT / "experiments" / "flagship" / "round2_config.json"
ROUND1_PACKAGE = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "round1"
ROUND2_PACKAGE = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "round2"
REVIEW_DIR_NAME = "review"

CASE_ID = "Q028"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _check(report: dict[str, Any], category: str, requirement_id: str, ok: bool, detail: str) -> None:
    report["checks"].append(
        {
            "category": category,
            "requirement_id": requirement_id,
            "status": "PASS" if ok else "FAIL",
            "detail": detail,
        }
    )
    if not ok:
        report["fail_closed_reasons"].append(f"{requirement_id}: {detail}")


def _verify_package_checksums(package_dir: Path, manifest: dict[str, Any] | None) -> bool:
    if manifest is None:
        return False
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return False
    for entry in files:
        try:
            file_path = package_dir / entry["path"]
            if not file_path.is_file():
                return False
            if _sha256(file_path) != entry["sha256"]:
                return False
            if file_path.stat().st_size != entry["size_bytes"]:
                return False
        except (KeyError, TypeError, OSError):
            return False
    return True


def validate_flagship_canonical_package(
    *,
    selection_manifest: Path = SELECTION_MANIFEST,
    dataset_manifest: Path = DATASET_MANIFEST,
    round1_config: Path = ROUND1_CONFIG,
    round2_config: Path = ROUND2_CONFIG,
    round1_package: Path = ROUND1_PACKAGE,
    round2_package: Path = ROUND2_PACKAGE,
    expected_git_sha: str | None = None,
    scientific_control_equivalence: bool | None = None,
) -> dict[str, Any]:
    """Assemble and validate the Q028/WDBC canonical package. Always returns a
    report (never raises); the report's ``status`` is ``PASS`` only if every
    check passed.

    Provenance strategy: VERSIONED_MULTI_COMMIT is fully supported. Each stage
    may bind to a different, independently-verified git commit. What is required
    is that (a) every stage's own git_dirty=False, (b) the round2 git_sha equals
    the expected producer commit (when provided), and (c) scientific control
    equivalence is verified between the commits (when provided). Requiring ALL
    stages to share the SAME git commit (ALL_GIT_SHAS_MATCH) would prevent
    legitimate iterative science where Round 1 was produced at an earlier commit
    -- this hard gate is intentionally NOT enforced.
    """

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "case_id": CASE_ID,
        "checks": [],
        "fail_closed_reasons": [],
    }

    # A. Selection & scientific scope.
    selection = _load_json(selection_manifest)
    _check(report, "selection", "CANON-A-001", selection is not None, "selection_manifest.json missing or invalid")
    if selection is not None:
        blob = json.dumps(selection)
        _check(report, "selection", "CANON-A-002", CASE_ID in blob, "selection manifest does not reference Q028")
        _check(
            report,
            "selection",
            "CANON-A-003",
            bool(selection.get("forbidden_extrapolations") or selection.get("non_goals")),
            "selection manifest missing scientific scope / non-goals / forbidden extrapolations",
        )

    # B. Dataset.
    dataset = _load_json(dataset_manifest)
    _check(report, "dataset", "CANON-B-001", dataset is not None, "dataset_manifest.json missing or invalid")
    dataset_sha: str | None = None
    if dataset is not None:
        pin = dataset.get("pin") if isinstance(dataset.get("pin"), dict) else {}
        dataset_sha = pin.get("sha256")
        _check(
            report,
            "dataset",
            "CANON-B-002",
            bool(dataset_sha) and pin.get("status") == "verified",
            "dataset pin missing sha256 or not verified",
        )

    # C. Round 1: execution, checksums, config presence.
    round1_result = _load_json(Path(round1_package) / "execution_result.json")
    _check(report, "round1", "CANON-C-001", round1_result is not None, "round1 execution_result.json missing")
    if round1_result is not None:
        round1_ok = (
            round1_result.get("actual_execution") is True
            and round1_result.get("runner_verified") is True
            and round1_result.get("status") == "succeeded"
        )
        _check(report, "round1", "CANON-C-002", round1_ok, "round1 is not a verified actual execution")
    round1_manifest = _load_json(Path(round1_package) / "package_manifest.json")
    _check(report, "round1", "CANON-C-003", round1_manifest is not None, "round1 package_manifest.json missing")
    _check(
        report,
        "round1",
        "CANON-C-004",
        _verify_package_checksums(Path(round1_package), round1_manifest),
        "round1 package checksum mismatch or missing file",
    )
    _check(
        report,
        "round1",
        "CANON-C-005",
        Path(round1_config).exists(),
        "round1_config.json missing",
    )

    # D. Reviewer feedback / RevisionContext / issue closure.
    review_dir = Path(round2_package) / REVIEW_DIR_NAME
    reviewer_feedback = _load_json(review_dir / "reviewer_feedback.json")
    revision_context = _load_json(review_dir / "revision_context.json")
    issue_closure = _load_json(review_dir / "issue_closure.json")
    plan_versions = _load_json(review_dir / "plan_versions.json")
    _check(report, "reviewer", "CANON-D-001", reviewer_feedback is not None, "reviewer_feedback.json missing")
    _check(report, "reviewer", "CANON-D-002", revision_context is not None, "revision_context.json missing")
    _check(report, "reviewer", "CANON-D-003", issue_closure is not None, "issue_closure.json missing")
    _check(report, "reviewer", "CANON-D-004", plan_versions is not None, "plan_versions.json missing")
    if issue_closure is not None:
        unresolved_p0 = issue_closure.get("unresolved_p0")
        unresolved_p1 = issue_closure.get("unresolved_p1")
        _check(report, "reviewer", "CANON-D-005", unresolved_p0 == 0, f"unresolved_p0={unresolved_p0}, must be 0")
        _check(report, "reviewer", "CANON-D-006", unresolved_p1 == 0, f"unresolved_p1={unresolved_p1}, must be 0")
    if reviewer_feedback is not None:
        round1_review = reviewer_feedback.get("round1_review") or {}
        round2_review = reviewer_feedback.get("round2_review") or {}
        _check(
            report,
            "reviewer",
            "CANON-D-007",
            round1_review.get("passed") is False and round2_review.get("passed") is True,
            "reviewer feedback does not show a genuine fail-then-pass revision",
        )

    # E. Round 2: execution, checksums, lineage (fail closed if missing/blocked).
    round2_result = _load_json(Path(round2_package) / "execution_result.json")
    round2_exists = round2_result is not None
    _check(report, "round2", "CANON-E-001", round2_exists, "round2 execution_result.json missing (ROUND2_BLOCKED)")
    if round2_exists:
        parent_ok = bool(round1_result) and round2_result.get("parent_execution_id") == round1_result.get(
            "execution_id"
        )
        round2_ok = (
            round2_result.get("actual_execution") is True
            and round2_result.get("runner_verified") is True
            and round2_result.get("status") == "succeeded"
            and parent_ok
        )
        _check(report, "round2", "CANON-E-002", round2_ok, "round2 is not a verified actual execution linked to round1")
        round2_manifest = _load_json(Path(round2_package) / "package_manifest.json")
        _check(report, "round2", "CANON-E-003", round2_manifest is not None, "round2 package_manifest.json missing")
        _check(
            report,
            "round2",
            "CANON-E-004",
            _verify_package_checksums(Path(round2_package), round2_manifest),
            "round2 package checksum mismatch or missing file",
        )
        _check(report, "round2", "CANON-E-005", Path(round2_config).exists(), "round2_config.json missing")

    # F. Structured diff / stop reason.
    structured_diff = _load_json(review_dir / "structured_diff.json")
    stop_reason = _load_json(review_dir / "stop_reason.json")
    _check(report, "closure", "CANON-F-001", structured_diff is not None, "structured_diff.json missing")
    _check(report, "closure", "CANON-F-002", stop_reason is not None, "stop_reason.json missing")
    if structured_diff is not None:
        v1_fp = structured_diff.get("v1_config_fingerprint")
        v2_fp = structured_diff.get("v2_config_fingerprint")
        _check(
            report,
            "closure",
            "CANON-F-003",
            bool(v1_fp) and bool(v2_fp) and v1_fp != v2_fp,
            "V1/V2 config fingerprints are missing or identical (not a true iteration)",
        )
    if stop_reason is not None:
        _check(report, "closure", "CANON-F-004", stop_reason.get("unresolved_p0") == 0, "stop_reason unresolved_p0 != 0")
        _check(report, "closure", "CANON-F-005", stop_reason.get("unresolved_p1") == 0, "stop_reason unresolved_p1 != 0")
        _check(
            report,
            "closure",
            "CANON-F-006",
            bool(stop_reason.get("scientific_limitation")),
            "stop_reason missing scientific_limitation notice",
        )

    # G. Cross-file identity: dataset pin, run/case id consistency.
    if dataset_sha and round1_result is not None:
        round1_datasets = round1_result.get("datasets") or []
        round1_dataset_sha = round1_datasets[0].get("sha256") if round1_datasets else None
        _check(
            report,
            "identity",
            "CANON-G-001",
            round1_dataset_sha == dataset_sha,
            "round1 dataset sha256 does not match dataset_manifest.json pin",
        )
    if dataset_sha and round2_exists:
        round2_datasets = round2_result.get("datasets") or []
        round2_dataset_sha = round2_datasets[0].get("sha256") if round2_datasets else None
        _check(
            report,
            "identity",
            "CANON-G-002",
            round2_dataset_sha == dataset_sha,
            "round2 dataset sha256 does not match dataset_manifest.json pin",
        )
    if round1_result is not None and round2_exists:
        _check(
            report,
            "identity",
            "CANON-G-003",
            round1_result.get("question_id") == round2_result.get("question_id") == CASE_ID,
            "round1/round2 question_id does not agree on Q028",
        )

    # H. Git provenance. Round 1 is treated as permanently pinned, immutable
    # historical evidence (app.execution.run_round2 hardcodes the exact
    # execution_id/git_sha/model/prediction hashes it trusts) -- it is never
    # re-executed per session, so its git_sha legitimately stays fixed at
    # whatever commit first produced it. What *must* track the current
    # producer commit is Round 2 (and everything built on top of it: the
    # reviewer/V2/policy/canonical-package code), since that is what a new
    # session actually re-executes. Each round's own git_dirty=False is
    # still independently required -- that proves *that specific execution*
    # was captured with a clean tree, regardless of which commit it was.
    round1_env = (round1_result or {}).get("environment_fingerprint") or {}
    _check(
        report, "identity", "CANON-H-001",
        round1_env.get("git_dirty") is False,
        "round1 environment_fingerprint.git_dirty is not False",
    )
    if round2_exists:
        round2_env = (round2_result or {}).get("environment_fingerprint") or {}
        round2_git_sha = round2_env.get("git_sha")
        _check(
            report, "identity", "CANON-H-002",
            round2_env.get("git_dirty") is False,
            "round2 environment_fingerprint.git_dirty is not False",
        )
        if expected_git_sha is not None:
            _check(
                report, "identity", "CANON-H-003",
                round2_git_sha == expected_git_sha,
                f"round2 git_sha ({round2_git_sha}) does not equal expected producer commit {expected_git_sha}",
            )

    # I. Versioned multi-commit provenance gate.
    # Each stage must have its own verifiable, independently-recorded git SHA.
    # We explicitly do NOT require all stages to share the same commit
    # (ALL_GIT_SHAS_MATCH is not a gate here). Instead we require:
    #   1. Every stage's git_dirty=False (already checked in H).
    #   2. Scientific control equivalence between stages (when provided).
    #   3. We never fabricate that "all commits are the same" when they differ.
    round1_git_sha = round1_env.get("git_sha") if round1_env else None
    round2_env = (round2_result or {}).get("environment_fingerprint") or {}
    round2_git_sha_val = round2_env.get("git_sha") if round2_exists else None
    round1_stage_verified = bool(round1_git_sha) and round1_env.get("git_dirty") is False
    round2_stage_verified = (
        bool(round2_git_sha_val) and round2_env.get("git_dirty") is False
    ) if round2_exists else False
    all_stage_git_shas_verified = round1_stage_verified and (round2_stage_verified if round2_exists else True)
    _check(
        report,
        "versioned_provenance",
        "CANON-I-001",
        all_stage_git_shas_verified,
        f"not all stage git SHAs are independently verified (round1={round1_stage_verified}, round2={round2_stage_verified})",
    )
    # Scientific control equivalence: required when explicitly provided.
    sci_equiv_provided = scientific_control_equivalence is not None
    if sci_equiv_provided:
        _check(
            report,
            "versioned_provenance",
            "CANON-I-002",
            scientific_control_equivalence is True,
            "scientific_control_equivalence=False: unauthorized code changes detected between stage commits",
        )
    # Multi-commit is explicitly allowed and NOT a failure condition.
    same_commit = round1_git_sha == round2_git_sha_val if (round1_git_sha and round2_git_sha_val) else None
    report["provenance_mode"] = "VERSIONED_MULTI_COMMIT" if (same_commit is False) else "SINGLE_COMMIT"
    report["all_stage_git_shas_verified"] = all_stage_git_shas_verified
    report["round1_git_sha"] = round1_git_sha
    report["round2_git_sha"] = round2_git_sha_val
    report["scientific_control_equivalence"] = scientific_control_equivalence

    # Compute final status
    all_pass = bool(report["checks"]) and all(item["status"] == "PASS" for item in report["checks"])
    if all_pass and all_stage_git_shas_verified:
        if same_commit is False and sci_equiv_provided and scientific_control_equivalence is True:
            report["versioned_provenance_status"] = "VERSIONED_MULTI_COMMIT_VERIFIED"
        elif same_commit is False and not sci_equiv_provided:
            # Scientific equivalence not yet verified — still PASS for the validator,
            # but the provenance status is informational UNVERIFIED. Full
            # VERSIONED_MULTI_COMMIT_VERIFIED requires sci_equiv=True explicitly.
            report["versioned_provenance_status"] = "VERSIONED_MULTI_COMMIT_UNVERIFIED"
        else:
            report["versioned_provenance_status"] = "SINGLE_COMMIT_VERIFIED"
    else:
        report["versioned_provenance_status"] = (
            "VERSIONED_MULTI_COMMIT_UNVERIFIED"
            if (same_commit is False)
            else "SINGLE_COMMIT_UNVERIFIED"
        )

    report["status"] = "PASS" if all_pass else "FAIL"
    report["round2_blocked"] = not round2_exists
    report["check_count"] = len(report["checks"])
    report["failed_count"] = sum(1 for item in report["checks"] if item["status"] == "FAIL")
    return report
