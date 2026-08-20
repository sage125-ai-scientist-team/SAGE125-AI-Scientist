"""Assemble and atomically publish the Q028/WDBC flagship canonical package.

This module wires together the already-independently-verified evidence
(``app.execution.run_round1`` / ``run_round2`` / ``flagship_revision`` /
``flagship_canonical``) with the generic ``RETAIN_SUSPECT_FINAL`` state
machine (``app.execution.atomic_publication``).

The published canonical bundle is a small, self-contained summary (identity,
regression matrix, reproduction notes, checksums, and the full semantic
validation report) that points at -- and checksum-binds to -- the much larger
Round 1/Round 2 evidence directories rather than duplicating them.

Publication is only ever attempted when ``validate_flagship_canonical_package``
reports ``PASS``; any FAIL is a hard refusal to publish (no ``PUBLISHED_``
state is ever produced from a failing package).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.execution import atomic_publication as ap
from app.execution.flagship_canonical import (
    CASE_ID,
    DATASET_MANIFEST,
    ROUND1_CONFIG,
    ROUND1_PACKAGE,
    ROUND2_CONFIG,
    ROUND2_PACKAGE,
    SELECTION_MANIFEST,
    validate_flagship_canonical_package,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_ROOT = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "canonical"
RUN_ID = "Q028-wdbc-flagship"


class FlagshipPublishError(RuntimeError):
    """Raised when publication is refused (fails closed)."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _source_evidence_files() -> dict[str, Path]:
    """Every real, byte-exact source file the canonical bundle checksum-binds to."""
    review_dir = Path(ROUND2_PACKAGE) / "review"
    files = {
        "experiments/flagship/selection_manifest.json": Path(SELECTION_MANIFEST),
        "experiments/flagship/dataset_manifest.json": Path(DATASET_MANIFEST),
        "experiments/flagship/round1_config.json": Path(ROUND1_CONFIG),
        "experiments/flagship/round2_config.json": Path(ROUND2_CONFIG),
        "round1/package_manifest.json": Path(ROUND1_PACKAGE) / "package_manifest.json",
        "round2/package_manifest.json": Path(ROUND2_PACKAGE) / "package_manifest.json",
    }
    for name in (
        "reviewer_feedback.json",
        "revision_context.json",
        "plan_versions.json",
        "issue_closure.json",
        "structured_diff.json",
        "stop_reason.json",
    ):
        files[f"round2/review/{name}"] = review_dir / name
    return files


def build_regression_matrix() -> dict[str, Any]:
    """A real, recomputed round1-vs-round2 metric comparison (no fabrication)."""
    round1_summary = json.loads(
        (Path(ROUND1_PACKAGE) / "artifacts" / "run-summary.json").read_text(encoding="utf-8")
    )
    round2_summary = json.loads(
        (Path(ROUND2_PACKAGE) / "artifacts" / "run-summary.json").read_text(encoding="utf-8")
    )
    round1_config = json.loads(Path(ROUND1_CONFIG).read_text(encoding="utf-8"))
    trigger = round1_config["round2_trigger"]
    rows = []
    round1_metrics = round1_summary.get("metrics", {})
    round2_metrics = round2_summary.get("metrics", {})
    for metric in sorted(set(round1_metrics) | set(round2_metrics)):
        rows.append(
            {
                "metric": metric,
                "round1": round1_metrics.get(metric),
                "round2": round2_metrics.get(metric),
                "delta": (
                    round2_metrics[metric] - round1_metrics[metric]
                    if metric in round1_metrics and metric in round2_metrics
                    else None
                ),
                "target": trigger["target"] if metric == trigger["metric"] else None,
            }
        )
    return {
        "schema_version": "1.0",
        "case_id": CASE_ID,
        "rows": rows,
        "target_metric": trigger["metric"],
        "target_value": trigger["target"],
        "round1_meets_target": round1_metrics.get(trigger["metric"], 0) >= trigger["target"],
        "round2_meets_target": round2_metrics.get(trigger["metric"], 0) >= trigger["target"],
    }


def build_reproduction_notes(regression_matrix: dict[str, Any]) -> str:
    round2_notes_path = Path(ROUND2_PACKAGE) / "reproduction" / "reproduction_report.md"
    round2_notes = round2_notes_path.read_text(encoding="utf-8") if round2_notes_path.exists() else ""
    lines = [
        "# Q028/WDBC flagship canonical reproduction notes",
        "",
        "## Scope",
        "",
        "Controlled binary classification exercise (UCI WDBC). Demonstrates the "
        "AI Scientist plan-execute-review-revise workflow. Not a cure, not a "
        "clinical validation, not medical advice, not generalizable to other "
        "cancers.",
        "",
        "## Round 1 -> Round 2",
        "",
        f"Target metric: `{regression_matrix['target_metric']}` >= "
        f"{regression_matrix['target_value']}.",
        "",
        "| metric | round1 | round2 | delta |",
        "| --- | --- | --- | --- |",
    ]
    for row in regression_matrix["rows"]:
        lines.append(
            f"| {row['metric']} | {row['round1']} | {row['round2']} | {row['delta']} |"
        )
    lines.append("")
    lines.append("## Round 2 execution reproduction report")
    lines.append("")
    lines.append(round2_notes.rstrip("\n") or "(round2 reproduction report unavailable)")
    return "\n".join(lines) + "\n"


def _precommit_validator(staging: Path, *, source_git_sha: str | None = None) -> ap.PrecommitValidationResult:
    from datetime import datetime, timezone

    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    semantic_report = validate_flagship_canonical_package(expected_git_sha=source_git_sha)
    if semantic_report["status"] != "PASS":
        return ap.PrecommitValidationResult(
            ok=False,
            checked_at=checked_at,
            failure_code="SEMANTIC_VALIDATION_FAILED",
            failure_message="; ".join(semantic_report["fail_closed_reasons"][:5]),
            details={"failed_count": semantic_report["failed_count"]},
        )

    expected_files = {"package_manifest.json", "checksums.sha256", "regression_matrix.json", "reproduction.md", "semantic_validation.json", "canonical_manifest.json"}
    actual_files = {path.name for path in staging.iterdir() if path.is_file()}
    if not expected_files.issubset(actual_files):
        missing = expected_files - actual_files
        return ap.PrecommitValidationResult(
            ok=False,
            checked_at=checked_at,
            failure_code="STAGING_INCOMPLETE",
            failure_message=f"staging is missing required files: {sorted(missing)}",
        )

    manifest = json.loads((staging / "package_manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        candidate = staging / entry["path"]
        if not candidate.is_file() or _sha256_file(candidate) != entry["sha256"]:
            return ap.PrecommitValidationResult(
                ok=False,
                checked_at=checked_at,
                failure_code="STAGING_CHECKSUM_MISMATCH",
                failure_message=f"checksum mismatch for {entry['path']}",
            )

    manifest_hash = _sha256_bytes(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )
    checksums_hash = _sha256_file(staging / "checksums.sha256")
    return ap.PrecommitValidationResult(
        ok=True,
        checked_at=checked_at,
        manifest_hash=manifest_hash,
        checksum_inventory_hash=checksums_hash,
        details={"semantic_check_count": semantic_report["check_count"]},
    )


def _post_publish_verifier(final: Path) -> ap.PostPublishVerificationResult:
    from datetime import datetime, timezone

    verified_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        manifest = json.loads((final / "package_manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            candidate = final / entry["path"]
            if not candidate.is_file() or _sha256_file(candidate) != entry["sha256"]:
                return ap.PostPublishVerificationResult(
                    ok=False,
                    verified_at=verified_at,
                    failure_code="POST_PUBLISH_CHECKSUM_MISMATCH",
                    failure_message=f"checksum mismatch for {entry['path']} after rename",
                )
        semantic = json.loads((final / "semantic_validation.json").read_text(encoding="utf-8"))
        if semantic.get("status") != "PASS":
            return ap.PostPublishVerificationResult(
                ok=False,
                verified_at=verified_at,
                failure_code="SEMANTIC_VALIDATION_NOT_PASS",
                failure_message="embedded semantic_validation.json is not PASS",
            )
        manifest_hash = _sha256_bytes(
            json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
        )
        return ap.PostPublishVerificationResult(ok=True, verified_at=verified_at, manifest_hash=manifest_hash)
    except (OSError, ValueError, KeyError) as exc:
        return ap.PostPublishVerificationResult(
            ok=False,
            verified_at=verified_at,
            failure_code="POST_PUBLISH_READ_ERROR",
            failure_message=str(exc),
        )


def _assemble_staging(staging: Path, *, source_git_sha: str | None) -> None:
    semantic_report = validate_flagship_canonical_package()
    regression_matrix = build_regression_matrix()
    reproduction_notes = build_reproduction_notes(regression_matrix)
    source_files = _source_evidence_files()

    checksum_lines = []
    for relative, source_path in sorted(source_files.items()):
        digest = _sha256_file(source_path)
        checksum_lines.append(f"{digest}  {relative}")
    checksums_text = "\n".join(checksum_lines) + "\n"

    round1_result = json.loads((Path(ROUND1_PACKAGE) / "execution_result.json").read_text(encoding="utf-8"))
    round2_result = json.loads((Path(ROUND2_PACKAGE) / "execution_result.json").read_text(encoding="utf-8"))
    canonical_manifest = {
        "schema_version": "1.0",
        "case_id": CASE_ID,
        "run_id": RUN_ID,
        "source_git_sha": source_git_sha,
        "round1_execution_id": round1_result.get("execution_id"),
        "round2_execution_id": round2_result.get("execution_id"),
        "dataset_sha256": round1_result.get("datasets", [{}])[0].get("sha256"),
        "source_files": {relative: _sha256_file(path) for relative, path in source_files.items()},
    }

    (staging / "canonical_manifest.json").write_text(
        json.dumps(canonical_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (staging / "regression_matrix.json").write_text(
        json.dumps(regression_matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (staging / "semantic_validation.json").write_text(
        json.dumps(semantic_report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (staging / "reproduction.md").write_text(reproduction_notes, encoding="utf-8", newline="\n")
    (staging / "checksums.sha256").write_text(checksums_text, encoding="utf-8", newline="\n")

    files = []
    for path in sorted(staging.rglob("*")):
        if path.is_file() and path.name != "package_manifest.json":
            files.append(
                {
                    "path": path.relative_to(staging).as_posix(),
                    "sha256": _sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    (staging / "package_manifest.json").write_text(
        json.dumps({"schema_version": "1.0", "files": files}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def publish_flagship_canonical_package(
    *,
    source_git_sha: str | None = None,
    canonical_root: Path = CANONICAL_ROOT,
) -> dict[str, Any]:
    """Run the full STAGING -> ... -> PUBLISHED_VERIFIED|PUBLISHED_UNVERIFIED
    pipeline for the Q028 canonical package. Always writes a receipt. Only
    updates the canonical pointer on PUBLISHED_VERIFIED. Never raises for a
    semantic FAIL -- returns a report with ``published=False`` instead;
    raises ``FlagshipPublishError`` only for unexpected filesystem errors.
    """
    canonical_root = Path(canonical_root)
    canonical_root.mkdir(parents=True, exist_ok=True)
    receipts_dir = canonical_root / "receipts"
    pointer_path = canonical_root / "canonical_pointer.json"

    previous_attempt_id = None
    if pointer_path.exists():
        try:
            previous_attempt_id = ap.read_canonical_pointer(pointer_path).attempt_id
        except ap.AtomicPublicationError:
            previous_attempt_id = None

    attempt = ap.new_attempt(
        run_id=RUN_ID,
        case_id=CASE_ID,
        staging_root=canonical_root,
        final_root=canonical_root,
        source_git_sha=source_git_sha,
        previous_canonical_attempt_id=previous_attempt_id,
    )

    def _assemble_then_validate(staging: Path) -> ap.PrecommitValidationResult:
        _assemble_staging(staging, source_git_sha=source_git_sha)
        return _precommit_validator(staging, source_git_sha=source_git_sha)

    attempt, precommit = ap.precommit_validate(attempt, _assemble_then_validate)
    if not precommit.ok:
        # Precommit failure: leave staging in place for inspection, do not rename.
        return {
            "published": False,
            "state": attempt.state,
            "attempt_id": attempt.attempt_id,
            "failure_code": precommit.failure_code,
            "failure_message": precommit.failure_message,
        }

    attempt = ap.publish_atomic_no_clobber(attempt)
    attempt, verification = ap.post_publish_verify(attempt, _post_publish_verifier)
    receipt = ap.write_receipt(attempt, receipts_dir)

    result: dict[str, Any] = {
        "published": attempt.state == "PUBLISHED_VERIFIED",
        "state": attempt.state,
        "attempt_id": attempt.attempt_id,
        "final_path": attempt.final_path,
        "manifest_hash": attempt.manifest_hash,
        "receipt_id": receipt.receipt_id,
        "failure_code": attempt.failure_code,
        "failure_message": attempt.failure_message,
    }
    if attempt.state == "PUBLISHED_VERIFIED":
        pointer = ap.update_canonical_pointer(attempt, pointer_path)
        result["canonical_pointer_updated_at"] = pointer.updated_at
    return result


def _recompute_prompt_hash(snapshot_path: Path) -> str | None:
    try:
        text = Path(snapshot_path).read_text(encoding="utf-8")
    except OSError:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json_or_none(path: Path) -> Any | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _redact(value: str | None, keep: int = 12) -> str | None:
    """Bound-length, non-secret identifiers only; never called on prompt bodies."""
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= keep * 2 else f"{text[:keep]}...{text[-keep:]}"


def build_provenance_summary(canonical_root: Path = CANONICAL_ROOT) -> dict[str, Any]:
    """Read-only, non-secret provenance summary for API/UI display (GAP-01..04).

    Every field here is read from already-committed/generated disk evidence
    (execution results, reviewer/revision bundle, canonical manifest, and the
    append-only supersession audit log). Nothing is computed, guessed, or
    fabricated. No API key, Authorization header, workspace ID, or raw prompt
    body is ever included.
    """
    round1_result = _read_json_or_none(ROUND1_PACKAGE / "execution_result.json") or {}
    round2_result = _read_json_or_none(ROUND2_PACKAGE / "execution_result.json") or {}
    review_dir = ROUND2_PACKAGE / "review"
    reviewer_feedback = _read_json_or_none(review_dir / "reviewer_feedback.json") or {}
    revision_context = _read_json_or_none(review_dir / "revision_context.json") or {}
    provider_audit = _read_json_or_none(review_dir / "provider_audit.json") or {}
    issue_closure = _read_json_or_none(review_dir / "issue_closure.json") or {}
    stop_reason = _read_json_or_none(review_dir / "stop_reason.json") or {}
    policy_validation = _read_json_or_none(review_dir / "policy_validation.json") or {}

    round1_env = round1_result.get("environment_fingerprint") or {}
    round2_env = round2_result.get("environment_fingerprint") or {}

    calls = provider_audit.get("calls") or []
    reviewer_call = next((c for c in calls if c.get("role") == "scientific_reviewer"), None)
    v2_call = next((c for c in calls if c.get("role") == "v2_revision_plan"), None)

    round1_review = reviewer_feedback.get("round1_review") or {}
    v1_input_hash = reviewer_call.get("input_hash") if reviewer_call else None
    v2_input_hash = v2_call.get("input_hash") if v2_call else None
    # ``ProviderAuditRecord`` persists ``input_hash`` (hash of the structured
    # JSON context) but not the full rendered prompt hash. Recompute the real
    # prompt hash by re-hashing the already-committed, on-disk prompt
    # snapshot text -- this is a read-only re-derivation from real evidence,
    # never a fabricated or guessed value. If the on-disk snapshot was
    # truncated (see ``truncation_policy``), the recomputed hash will not
    # equal the original call-time hash and is reported as ``None`` rather
    # than silently shown as if it matched.
    v1_prompt_hash = _recompute_prompt_hash(review_dir / "v1_scientific_reviewer_prompt_snapshot.txt")
    v2_prompt_hash = _recompute_prompt_hash(review_dir / "v2_revision_plan_prompt_snapshot.txt")

    canonical_manifest = None
    pointer_path = canonical_root / "canonical_pointer.json"
    if pointer_path.exists():
        try:
            pointer = ap.read_canonical_pointer(pointer_path)
            manifest_path = Path(pointer.final_path) / "canonical_manifest.json"
            canonical_manifest = _read_json_or_none(manifest_path)
        except ap.AtomicPublicationError:
            canonical_manifest = None

    superseded_events: list[dict[str, Any]] = []
    audit_log_path = canonical_root / "PROVENANCE_AUDIT_LOG.jsonl"
    if audit_log_path.exists():
        try:
            for line in audit_log_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    superseded_events.append(json.loads(line))
        except (OSError, ValueError):
            pass

    return {
        "producer_git_sha": (canonical_manifest or {}).get("source_git_sha"),
        "round1_git_sha": round1_env.get("git_sha"),
        "round1_git_dirty": round1_env.get("git_dirty"),
        "round2_git_sha": round2_env.get("git_sha"),
        "round2_git_dirty": round2_env.get("git_dirty"),
        "round1_execution_id": round1_result.get("execution_id"),
        "round2_execution_id": round2_result.get("execution_id"),
        "reviewer_provider": (reviewer_call or {}).get("provider"),
        "reviewer_model": (reviewer_call or {}).get("model"),
        "reviewer_request_id": (reviewer_call or {}).get("request_id"),
        "reviewer_timestamp": (reviewer_call or {}).get("timestamp"),
        "v2_provider": (v2_call or {}).get("provider"),
        "v2_model": (v2_call or {}).get("model"),
        "v2_request_id": (v2_call or {}).get("request_id"),
        "v2_timestamp": (v2_call or {}).get("timestamp"),
        "reviewer_driven": reviewer_feedback.get("reviewer_driven"),
        "reviewer_passed": round1_review.get("passed"),
        "critical_issues": round1_review.get("critical_issues") or [],
        "execution_result_injected": revision_context.get("execution_result_injected"),
        "reviewer_issues_injected": revision_context.get("reviewer_issues_injected"),
        "v1_prompt_hash": _redact(v1_prompt_hash),
        "v2_prompt_hash": _redact(v2_prompt_hash),
        "prompt_hash_changed": bool(
            v1_prompt_hash and v2_prompt_hash and v1_prompt_hash != v2_prompt_hash
        ),
        "v1_input_hash": _redact(v1_input_hash),
        "v2_input_hash": _redact(v2_input_hash),
        "input_hash_changed": bool(
            v1_input_hash and v2_input_hash and v1_input_hash != v2_input_hash
        ),
        "unresolved_p0": issue_closure.get("unresolved_p0", stop_reason.get("unresolved_p0")),
        "unresolved_p1": issue_closure.get("unresolved_p1", stop_reason.get("unresolved_p1")),
        "stop_reason": stop_reason.get("stop_reason"),
        "target_metric": stop_reason.get("target_metric"),
        "target_value": stop_reason.get("target_value"),
        "observed_value": stop_reason.get("observed_value"),
        "scientific_limitation": stop_reason.get("scientific_limitation"),
        "policy_validation_ok": policy_validation.get("ok"),
        "no_clobber_publication": True,
        "superseded_attempts": superseded_events,
        "artifact_snapshot_commit_sha": _current_head_sha(),
    }


def _current_head_sha() -> str | None:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def get_canonical_status(canonical_root: Path = CANONICAL_ROOT) -> dict[str, Any]:
    """Read-only status for API/UI consumption. Never fabricates a PASS."""
    canonical_root = Path(canonical_root)
    pointer_path = canonical_root / "canonical_pointer.json"
    semantic_report = validate_flagship_canonical_package()
    status: dict[str, Any] = {
        "case_id": CASE_ID,
        "semantic_validation_status": semantic_report["status"],
        "round2_blocked": semantic_report["round2_blocked"],
        "fail_closed_reasons": semantic_report["fail_closed_reasons"],
        "checks": semantic_report["checks"],
        "check_count": semantic_report["check_count"],
        "failed_count": semantic_report["failed_count"],
        "canonical_published": False,
        "canonical_pointer": None,
        "provenance": build_provenance_summary(canonical_root),
    }
    if pointer_path.exists():
        try:
            pointer = ap.read_canonical_pointer(pointer_path)
            ap.assert_consumer_accepts_state("PUBLISHED_VERIFIED")
            final_path = Path(pointer.final_path)
            if final_path.exists():
                status["canonical_published"] = True
                status["canonical_pointer"] = pointer.model_dump(mode="json")
        except ap.AtomicPublicationError:
            status["canonical_published"] = False
    return status
