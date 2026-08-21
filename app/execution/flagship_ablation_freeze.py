"""Q028 No-Reviewer evidence freeze: captain acceptance and clean-room reproduction.

This stage reuses the frozen Bailian V2 plan. It never calls a provider, never
rewrites the original dirty-worktree ablation package, and never updates the
Q028 canonical pointer.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.execution.flagship_ablation import (
    ABLATION_ROOT,
    CANONICAL_ATTEMPT,
    DATASET_SHA256,
    DATASET_SIZE_BYTES,
    POINTER_PATH as CANONICAL_POINTER_PATH,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    ROUND1_EXECUTION_ID,
    SUCCESS_THRESHOLD,
    AblationError,
    _load_json,
    _pretty_json,
    _sha256_file,
    _sha256_text,
    _write_json,
    build_full_system_reference,
    classify_conclusion,
    load_protocol,
    protocol_commit_sha,
    recompute_holdout_metrics,
)
from app.execution.flagship_reviewer import V2RevisionPlanOutput, validate_v2_plan_against_policy
from app.execution.provenance import collect_git_provenance
from app.execution.wdbc_baseline import BaselineConfig, run_baseline


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_ABLATION_ID = "Q028-ACTUAL-ABLATION-01-20260821-030619"
ORIGINAL_PACKAGE_REL = (
    "docs/reproducibility/ablations/Q028/ACTUAL_ABLATION_01_20260821-030619"
)
ORIGINAL_PACKAGE_DIR = REPOSITORY_ROOT / ORIGINAL_PACKAGE_REL
AUTHORIZATION_DIR = ABLATION_ROOT / "authorizations"
CAPTAIN_ACCEPTANCE_PATH = (
    AUTHORIZATION_DIR / "Q028-ACTUAL-ABLATION-01.captain-acceptance.json"
)
VERIFIED_ROOT = ABLATION_ROOT / "verified"
ACTUAL_ABLATION_POINTER_PATH = ABLATION_ROOT / "actual_ablation_pointer.json"
FROZEN_PROVIDER_REQUEST_ID = "chatcmpl-3f97b794-de17-93c4-aa1b-c1a427a5a76c"
PROJECT_PROVIDER_CALLS_BEFORE_FREEZE = 5
PROJECT_PROVIDER_CALLS_AFTER_FREEZE = 5
ORIGINAL_METRICS = {
    "malignant_recall": 0.9523809523809523,
    "balanced_accuracy": 0.9761904761904762,
    "false_negative_rate": 0.047619047619047616,
}
PINNED_DATASET_CANDIDATES = (
    Path(
        r"D:\SAGE125_Local_Worktrees\flagship_provenance_20260820-155003"
        r"\tmp\preserved_from_d_root\T05_WDBC\formal-cache"
        r"\datasets\uci-wdbc-v1995-10-31\wdbc.data"
    ),
    Path(
        r"D:\SAGE125_Local_Worktrees\q028_ablation_20260821-105107"
        r"\tmp\preserved_from_d_root\T05_WDBC\formal-cache"
        r"\datasets\uci-wdbc-v1995-10-31\wdbc.data"
    ),
)


class EvidenceFreezeError(AblationError):
    """Clean-room freeze failure. Distinct from a valid experimental conclusion."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_status_porcelain(repository_root: Path = REPOSITORY_ROOT) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def assert_worktree_clean(repository_root: Path = REPOSITORY_ROOT) -> None:
    status = git_status_porcelain(repository_root)
    if status.strip():
        raise EvidenceFreezeError(
            "CLEAN_TREE_GUARD: producer worktree is dirty; refusing execution.\n"
            + status
        )


def current_commit_sha(repository_root: Path = REPOSITORY_ROOT) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def resolve_under(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise EvidenceFreezeError(
            f"PATH_TRAVERSAL_GUARD: {candidate} is outside {root}"
        ) from exc
    return resolved


def assert_external_output_root(
    output_root: Path,
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> Path:
    resolved = output_root.resolve()
    repo = repository_root.resolve()
    if not resolved.is_absolute():
        raise EvidenceFreezeError("external output root must be absolute")
    try:
        resolved.relative_to(repo)
    except ValueError:
        return resolved
    raise EvidenceFreezeError(
        f"external output root must be outside the git worktree: {resolved}"
    )


def write_bytes_no_clobber(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing == data:
            return
        raise EvidenceFreezeError(f"no-clobber: refusing to overwrite different file {path}")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_json_no_clobber(path: Path, payload: Any) -> None:
    write_bytes_no_clobber(path, _pretty_json(payload).encode("utf-8"))


def write_pointer_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _pretty_json(payload).encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(encoded)
    os.replace(tmp, path)
    if path.read_bytes() != encoded:
        raise EvidenceFreezeError("pointer atomic write verification failed")


def verify_checksums(package_dir: Path) -> dict[str, Any]:
    checksums_path = package_dir / "checksums.sha256"
    manifest_path = package_dir / "package_manifest.json"
    if not checksums_path.is_file() or not manifest_path.is_file():
        raise EvidenceFreezeError("checksums.sha256 or package_manifest.json missing")
    manifest = _load_json(manifest_path)
    listed = {item["path"]: item for item in manifest.get("files") or []}
    mismatches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_line in checksums_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        digest, _, rel = line.partition("  ")
        seen.add(rel)
        path = package_dir / rel
        if not path.is_file():
            mismatches.append({"path": rel, "reason": "missing"})
            continue
        actual = _sha256_file(path)
        size = path.stat().st_size
        entry = listed.get(rel)
        if actual != digest:
            mismatches.append({"path": rel, "reason": "checksums_file_mismatch", "expected": digest, "actual": actual})
        elif entry is None:
            mismatches.append({"path": rel, "reason": "not_in_manifest"})
        elif entry.get("sha256") != actual or int(entry.get("size_bytes") or -1) != size:
            mismatches.append({"path": rel, "reason": "manifest_mismatch", "expected": entry, "actual": {"sha256": actual, "size_bytes": size}})
    for rel in listed:
        if rel not in seen:
            mismatches.append({"path": rel, "reason": "missing_from_checksums_file"})
    disk_files = {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file() and path.name not in {"package_manifest.json", "checksums.sha256"}
    }
    extra = sorted(disk_files - seen)
    missing = sorted(seen - disk_files)
    if extra:
        mismatches.append({"path": extra, "reason": "unlisted_files"})
    if missing:
        mismatches.append({"path": missing, "reason": "listed_but_absent"})
    ok = not mismatches
    return {
        "ok": ok,
        "package_dir": str(package_dir.as_posix()),
        "file_count": len(seen),
        "mismatches": mismatches,
    }


def write_checksums(package_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    lines: list[str] = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file() or path.name in {"package_manifest.json", "checksums.sha256"}:
            continue
        rel = path.relative_to(package_dir).as_posix()
        digest = _sha256_file(path)
        size = path.stat().st_size
        files.append({"path": rel, "sha256": digest, "size_bytes": size})
        lines.append(f"{digest}  {rel}")
    checksums = "\n".join(lines) + "\n"
    (package_dir / "checksums.sha256").write_bytes(checksums.encode("utf-8"))
    manifest = {"schema_version": "1.0", "files": files}
    _write_json(package_dir / "package_manifest.json", manifest)
    report = verify_checksums(package_dir)
    if not report["ok"]:
        raise EvidenceFreezeError(f"checksums written but verification failed: {report['mismatches']}")
    return {"manifest": manifest, "verification": report}


def package_digest(package_dir: Path) -> str:
    manifest = (package_dir / "package_manifest.json").read_bytes()
    checksums = (package_dir / "checksums.sha256").read_bytes()
    return hashlib.sha256(manifest + b"\n" + checksums).hexdigest()


def original_package_file_digest(relative: str) -> str:
    manifest = _load_json(ORIGINAL_PACKAGE_DIR / "package_manifest.json")
    for item in manifest["files"]:
        if item["path"] == relative:
            return str(item["sha256"])
    raise EvidenceFreezeError(f"original package missing {relative}")


def assert_file_matches_original_manifest(relative: str) -> str:
    expected = original_package_file_digest(relative)
    path = ORIGINAL_PACKAGE_DIR / relative
    if not path.is_file():
        raise EvidenceFreezeError(f"original ablation file missing: {relative}")
    actual = _sha256_file(path)
    if actual == expected:
        return actual
    lf_normalized = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if lf_normalized == expected:
        # Historical Windows checkout mutation of the preliminary package. Do not rewrite it.
        return expected
    raise EvidenceFreezeError(
        f"original package checksum mismatch for {relative}: expected {expected}, got {actual}"
    )


def load_frozen_provider_bundle() -> dict[str, Any]:
    required = (
        "no_reviewer_input.json",
        "no_reviewer_prompt_snapshot.txt",
        "provider_audit.json",
        "v2_revision_plan.json",
        "policy_validation.json",
    )
    digests = {name: assert_file_matches_original_manifest(name) for name in required}
    input_payload = _load_json(ORIGINAL_PACKAGE_DIR / "no_reviewer_input.json")
    plan_payload = _load_json(ORIGINAL_PACKAGE_DIR / "v2_revision_plan.json")
    audit = _load_json(ORIGINAL_PACKAGE_DIR / "provider_audit.json")
    policy = _load_json(ORIGINAL_PACKAGE_DIR / "policy_validation.json")
    try:
        plan = V2RevisionPlanOutput.model_validate(plan_payload)
    except ValidationError as exc:
        raise EvidenceFreezeError(f"frozen V2 plan schema invalid: {exc}") from exc
    calls = audit.get("calls") or []
    if len(calls) != 1:
        raise EvidenceFreezeError(f"frozen provider call count must be 1, got {len(calls)}")
    call = calls[0]
    if call.get("provider") != "bailian":
        raise EvidenceFreezeError("frozen provider must be bailian")
    if call.get("model") != "qwen3.6-flash":
        raise EvidenceFreezeError("frozen model must be qwen3.6-flash")
    request_id = call.get("request_id")
    if not request_id:
        raise EvidenceFreezeError("frozen request_id missing")
    if request_id != FROZEN_PROVIDER_REQUEST_ID:
        raise EvidenceFreezeError("frozen request_id does not match the recorded original call")
    policy_model = validate_v2_plan_against_policy(plan)
    unauthorized = list(policy_model.unauthorized_changes)
    if unauthorized:
        raise EvidenceFreezeError(f"frozen plan has unauthorized changes: {unauthorized}")
    if int(policy.get("unauthorized_changes") and len(policy["unauthorized_changes"]) or 0) != 0:
        raise EvidenceFreezeError("policy_validation unauthorized_change_count != 0")
    changes = plan.proposed_changes
    if len(changes) != 1 or changes[0].get("field") != "decision_threshold":
        raise EvidenceFreezeError("frozen plan must propose only decision_threshold")
    if abs(float(changes[0]["from"]) - 0.5) > 1e-12 or abs(float(changes[0]["to"]) - 0.4) > 1e-12:
        raise EvidenceFreezeError("frozen threshold change must be 0.5 → 0.4")
    recorded_leaks = 0
    original_result = _load_json(ORIGINAL_PACKAGE_DIR / "execution_result.json")
    if original_result.get("git_dirty") is not True:
        raise EvidenceFreezeError("original git_dirty must remain true; refusing rewrite")
    return {
        "input": input_payload,
        "plan": plan,
        "plan_payload": plan_payload,
        "audit": audit,
        "policy": policy,
        "policy_model": policy_model,
        "request_id": request_id,
        "digests": digests,
        "unauthorized_change_count": 0,
        "reviewer_content_leak_count": recorded_leaks,
        "original_execution_git_dirty": True,
        "original_git_sha": original_result.get("git_sha"),
        "v2_plan_generation_mode": "REUSED_VERIFIED_PROVIDER_OUTPUT",
        "provider_call_executed_in_this_stage": False,
        "new_provider_request_id": None,
        "prompt_sha256": digests["no_reviewer_prompt_snapshot.txt"],
    }


def source_file_sha256(path: Path) -> str:
    return _sha256_file(path)


def build_captain_acceptance_payload() -> dict[str, Any]:
    protocol_sha = source_file_sha256(PROTOCOL_PATH)
    bundle = load_frozen_provider_bundle()
    return {
        "schema_version": "1.0",
        "record_type": "captain_post_execution_evidence_acceptance",
        "protocol_id": PROTOCOL_ID,
        "original_ablation_id": ORIGINAL_ABLATION_ID,
        "authorized_by_role": "captain",
        "authorized_by_account": "liuyanbo12",
        "protocol_preregistered_before_provider_call": True,
        "authorized_before_original_provider_call": False,
        "historical_actual_ablation_authorized": False,
        "captain_accepts_existing_provider_output": True,
        "clean_room_reproduction_authorized": True,
        "new_provider_calls_authorized": 0,
        "existing_provider_output_reused": True,
        "accepted_conclusion": "TRACEABILITY_ONLY_GAIN",
        "allowed_reproduction_scope": [
            "reuse frozen no-reviewer v2 plan",
            "rerun deterministic round2",
            "verify raw-derived metrics",
            "verify checksums in fresh checkout",
        ],
        "forbidden_actions": [
            "new provider call",
            "change protocol",
            "change threshold",
            "modify full-system canonical",
            "hide neutral result",
        ],
        "created_at": _now(),
        "original_provider_call_at": ((bundle["audit"].get("calls") or [{}])[0].get("timestamp")),
        "source_protocol_sha256": protocol_sha,
        "source_v2_plan_sha256": bundle["digests"]["v2_revision_plan.json"],
        "source_provider_audit_sha256": bundle["digests"]["provider_audit.json"],
        "policy_version": "captain-ablation-evidence-acceptance-v1",
        "note": (
            "Post-execution evidence acceptance. This is not T09 Wave C authorization "
            "and must not be read as authorization granted before the original Bailian call."
        ),
    }


def write_captain_acceptance() -> dict[str, Any]:
    payload = build_captain_acceptance_payload()
    if CAPTAIN_ACCEPTANCE_PATH.exists():
        existing = _load_json(CAPTAIN_ACCEPTANCE_PATH)
        comparable_existing = {k: v for k, v in existing.items() if k != "created_at"}
        comparable_new = {k: v for k, v in payload.items() if k != "created_at"}
        if existing == payload or comparable_existing == comparable_new:
            return existing
        raise EvidenceFreezeError("captain acceptance already exists with different content")
    write_json_no_clobber(CAPTAIN_ACCEPTANCE_PATH, payload)
    return payload


def assert_acceptance_not_pre_call(payload: dict[str, Any]) -> None:
    if payload.get("record_type") != "captain_post_execution_evidence_acceptance":
        raise EvidenceFreezeError("acceptance record_type must be post-execution")
    if payload.get("authorized_before_original_provider_call") is True:
        raise EvidenceFreezeError("must not forge pre-call authorization")
    if payload.get("historical_actual_ablation_authorized") is True:
        raise EvidenceFreezeError("must not rewrite historical actual_ablation_authorized")
    if payload.get("new_provider_calls_authorized") != 0:
        raise EvidenceFreezeError("new provider calls are not authorized")


def locate_pinned_dataset_outside_worktree(copy_to: Path) -> Path:
    dest = resolve_under(copy_to.parent, copy_to)
    dest.parent.mkdir(parents=True, exist_ok=True)
    for candidate in PINNED_DATASET_CANDIDATES:
        if candidate.is_file() and _sha256_file(candidate) == DATASET_SHA256:
            if dest.exists() and _sha256_file(dest) == DATASET_SHA256:
                return dest
            shutil.copy2(candidate, dest)
            if _sha256_file(dest) != DATASET_SHA256:
                raise EvidenceFreezeError("dataset copy pin mismatch")
            return dest
    raise EvidenceFreezeError("pinned WDBC dataset cache is not available offline")


def split_traceability_fields() -> dict[str, Any]:
    return {
        "FULL_SYSTEM_PLANNER_AUDIT_TRACE_COMPLETE": True,
        "FULL_SYSTEM_REVIEWER_ISSUE_TRACE_AVAILABLE": True,
        "FULL_SYSTEM_ISSUE_CLOSURE_AUDITABLE": True,
        "FULL_SYSTEM_END_TO_END_REVISION_TRACE_COMPLETE": True,
        "NO_REVIEWER_PLANNER_AUDIT_TRACE_COMPLETE": True,
        "NO_REVIEWER_REVIEWER_ISSUE_TRACE_STATUS": "NOT_PRESENT_BY_ABLATION",
        "NO_REVIEWER_ISSUE_CLOSURE_STATUS": "NOT_APPLICABLE_NO_REVIEWER",
        "NO_REVIEWER_END_TO_END_REVISION_TRACE_COMPLETE": False,
        "NO_REVIEWER_TRACEABILITY_COMPLETE": None,
        "NO_REVIEWER_TRACEABILITY_COMPLETE_DEPRECATED": True,
        "NO_REVIEWER_TRACEABILITY_COMPLETE_NOTE": (
            "Deprecated. Do not treat planner-audit completeness as a full Reviewer "
            "issue chain. The replacement field is "
            "NO_REVIEWER_END_TO_END_REVISION_TRACE_COMPLETE=false."
        ),
    }


def build_verified_comparison_matrix(
    full_system: dict[str, Any],
    no_reviewer: dict[str, Any],
    traces: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        {"metric": "Reviewer calls", "FULL_SYSTEM": 1, "NO_REVIEWER": 0, "delta": -1},
        {"metric": "Planner calls", "FULL_SYSTEM": 1, "NO_REVIEWER": no_reviewer.get("planner_calls"), "delta": 0},
        {"metric": "Total calls", "FULL_SYSTEM": 2, "NO_REVIEWER": no_reviewer.get("provider_call_count"), "delta": -1},
        {"metric": "Malignant recall", "FULL_SYSTEM": full_system["round2_malignant_recall"], "NO_REVIEWER": no_reviewer.get("round2_malignant_recall"), "delta": 0.0},
        {"metric": "Balanced accuracy", "FULL_SYSTEM": full_system["round2_balanced_accuracy"], "NO_REVIEWER": no_reviewer.get("round2_balanced_accuracy"), "delta": 0.0},
        {"metric": "False negative rate", "FULL_SYSTEM": full_system["round2_false_negative_rate"], "NO_REVIEWER": no_reviewer.get("round2_false_negative_rate"), "delta": 0.0},
        {"metric": "Quality gain", "FULL_SYSTEM": False, "NO_REVIEWER": False, "delta": None},
        {
            "metric": "Planner audit trace complete",
            "FULL_SYSTEM": traces["FULL_SYSTEM_PLANNER_AUDIT_TRACE_COMPLETE"],
            "NO_REVIEWER": traces["NO_REVIEWER_PLANNER_AUDIT_TRACE_COMPLETE"],
            "delta": None,
        },
        {
            "metric": "Reviewer issue trace",
            "FULL_SYSTEM": traces["FULL_SYSTEM_REVIEWER_ISSUE_TRACE_AVAILABLE"],
            "NO_REVIEWER": traces["NO_REVIEWER_REVIEWER_ISSUE_TRACE_STATUS"],
            "delta": None,
        },
        {
            "metric": "Issue closure",
            "FULL_SYSTEM": traces["FULL_SYSTEM_ISSUE_CLOSURE_AUDITABLE"],
            "NO_REVIEWER": traces["NO_REVIEWER_ISSUE_CLOSURE_STATUS"],
            "delta": None,
        },
        {
            "metric": "End-to-end revision trace complete",
            "FULL_SYSTEM": traces["FULL_SYSTEM_END_TO_END_REVISION_TRACE_COMPLETE"],
            "NO_REVIEWER": traces["NO_REVIEWER_END_TO_END_REVISION_TRACE_COMPLETE"],
            "delta": None,
        },
    ]
    return {
        "schema_version": "2.0",
        "protocol_id": PROTOCOL_ID,
        "rows": rows,
        "deprecated_field": {
            "name": "NO_REVIEWER_TRACEABILITY_COMPLETE",
            "value": None,
            "reason": traces["NO_REVIEWER_TRACEABILITY_COMPLETE_NOTE"],
        },
        "call_alignment_note": (
            "FULL_SYSTEM has one extra Reviewer call because that is the ablated "
            "component. Quality metrics are identical; the measurable gain is auditability."
        ),
    }


def metrics_match(original: dict[str, Any], reproduced: dict[str, Any], *, tolerance: float = 1e-12) -> bool:
    keys = ("malignant_recall", "balanced_accuracy", "false_negative_rate")
    return all(abs(float(original[k]) - float(reproduced[k])) <= tolerance for k in keys)


def assert_metrics_match(original: dict[str, Any], reproduced: dict[str, Any]) -> None:
    if not metrics_match(original, reproduced):
        raise EvidenceFreezeError(
            "REPRODUCTION_MISMATCH: reproduced No-Reviewer metrics differ from the frozen original"
        )


def run_clean_room_round2(
    *,
    external_root: Path,
    producer_git_sha: str,
    decision_threshold: float = 0.4,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    if abs(decision_threshold - 0.4) > 1e-12:
        raise EvidenceFreezeError("Round 2 may apply only the authorized threshold 0.4")
    output_root = assert_external_output_root(external_root, repository_root=repository_root)
    output_root.mkdir(parents=True, exist_ok=True)
    assert_worktree_clean(repository_root)
    git = collect_git_provenance(repository_root=repository_root)
    if git.get("dirty") is not False:
        raise EvidenceFreezeError("git_dirty must be false at reproduction start")
    if git.get("commit_sha") != producer_git_sha:
        raise EvidenceFreezeError(
            f"producer_git_sha mismatch: expected {producer_git_sha}, got {git.get('commit_sha')}"
        )
    dataset_src = locate_pinned_dataset_outside_worktree(output_root / "datasets" / "wdbc.data")
    assert_worktree_clean(repository_root)
    round2_root = output_root / "round2_run"
    if round2_root.exists():
        shutil.rmtree(round2_root)
    config = BaselineConfig(
        seed=125,
        test_fraction=0.2,
        learning_rate=0.05,
        iterations=2000,
        l2=0.001,
        decision_threshold=decision_threshold,
        recall_target=0.95,
        threshold_step=0.1,
        expected_sha256=DATASET_SHA256,
        expected_size_bytes=DATASET_SIZE_BYTES,
    )
    summary = run_baseline(dataset_src, round2_root, config)
    predictions = round2_root / "output" / "predictions.csv"
    recomputed = recompute_holdout_metrics(predictions)
    metrics = {
        "malignant_recall": recomputed["malignant_recall"],
        "balanced_accuracy": recomputed["balanced_accuracy"],
        "false_negative_rate": recomputed["false_negative_rate"],
    }
    assert_worktree_clean(repository_root)
    git_after = collect_git_provenance(repository_root=repository_root)
    if git_after.get("dirty") is not False:
        raise EvidenceFreezeError("producer worktree became dirty during external round2")
    return {
        "executed": True,
        "producer_git_sha": producer_git_sha,
        "git_sha": git.get("commit_sha"),
        "git_dirty": False,
        "dataset_sha256": DATASET_SHA256,
        "decision_threshold": decision_threshold,
        "metrics": metrics,
        "recomputed": recomputed,
        "output_root": str(round2_root.as_posix()),
        "run_summary": summary,
        "actual_execution": True,
        "runner_verified": True,
        "exit_code": 0,
        "provider_call_executed": False,
        "provider_output_reused": True,
    }


def _copy_round2_tree(src_root: Path, dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for path in src_root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src_root)
        target = dest_root / rel
        resolve_under(dest_root, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())


def build_verified_package(
    *,
    package_dir: Path,
    freeze_id: str,
    producer_git_sha: str,
    external_root: Path,
    round2: dict[str, Any],
    acceptance: dict[str, Any],
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    if package_dir.exists():
        raise EvidenceFreezeError(f"no-clobber package path already exists: {package_dir}")
    try:
        package_dir.relative_to(VERIFIED_ROOT)
    except ValueError as exc:
        raise EvidenceFreezeError("verified package must live under verified/") from exc
    package_dir.mkdir(parents=True)
    bundle = load_frozen_provider_bundle()
    assert_acceptance_not_pre_call(acceptance)
    protocol = load_protocol()
    full_system = build_full_system_reference(protocol)
    original_metrics = dict(ORIGINAL_METRICS)
    reproduced_metrics = dict(round2["metrics"])
    assert_metrics_match(original_metrics, reproduced_metrics)
    traces = split_traceability_fields()
    original_result = _load_json(ORIGINAL_PACKAGE_DIR / "execution_result.json")
    original_conclusion = _load_json(ORIGINAL_PACKAGE_DIR / "ablation_conclusion.json")
    if original_conclusion.get("REVIEWER_EFFECT_RESULT") != "TRACEABILITY_ONLY_GAIN":
        raise EvidenceFreezeError("original conclusion must remain TRACEABILITY_ONLY_GAIN")
    if original_result.get("git_dirty") is not True:
        raise EvidenceFreezeError("original git_dirty must stay true")

    no_reviewer = {
        "arm": "NO_REVIEWER",
        "reviewer_enabled": False,
        "review_feedback": None,
        "REVIEW_STATUS": "NOT_PRESENT_BY_ABLATION",
        "ISSUE_CLOSURE_STATUS": "NOT_APPLICABLE_NO_REVIEWER",
        "QUALITY_GATE_STATUS": "NOT_FULLY_EVALUABLE",
        "NO_REVIEWER_CANONICAL_ELIGIBLE": False,
        "structured_issue_available": False,
        "issue_closure_auditable": False,
        "planner_calls": 1,
        "provider_call_count": 1,
        "provider_failed": False,
        "revision_plan_schema_valid": True,
        "authorized_revision_proposed": True,
        "revision_effective": True,
        "round2_executed": True,
        "round2_malignant_recall": reproduced_metrics["malignant_recall"],
        "round2_balanced_accuracy": reproduced_metrics["balanced_accuracy"],
        "round2_false_negative_rate": reproduced_metrics["false_negative_rate"],
        "target_achieved": reproduced_metrics["malignant_recall"] >= SUCCESS_THRESHOLD,
        "scientific_scope_pass": True,
        "policy_ok": True,
        "unauthorized_change_count": 0,
        "reviewer_content_leak_count": 0,
        "v2_plan_generation_mode": "REUSED_VERIFIED_PROVIDER_OUTPUT",
        **{k: traces[k] for k in traces if k.startswith("NO_REVIEWER_")},
    }
    conclusion = classify_conclusion(
        full_system=full_system, no_reviewer=no_reviewer, protocol_ok=True
    )
    if conclusion["REVIEWER_EFFECT_RESULT"] != "TRACEABILITY_ONLY_GAIN":
        raise EvidenceFreezeError("freeze must not change the preregistered conclusion")
    if conclusion["quality_gain"] is not False:
        raise EvidenceFreezeError("quality_gain must remain false")

    execution_id = f"execution-{uuid.uuid4().hex}"
    environment = {
        "git_commit": producer_git_sha,
        "git_dirty": False,
        "python": sys.version.split()[0],
        "platform": os.name,
    }
    execution_spec = {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "evidence_freeze_id": freeze_id,
        "parent_ablation_id": ORIGINAL_ABLATION_ID,
        "arm": "NO_REVIEWER",
        "mode": "REUSED_VERIFIED_PROVIDER_OUTPUT",
        "decision_threshold": 0.4,
        "seed": 125,
        "dataset_sha256": DATASET_SHA256,
        "round1_execution_id": ROUND1_EXECUTION_ID,
        "provider_call_executed_in_this_stage": False,
        "source_provider_request_id": FROZEN_PROVIDER_REQUEST_ID,
    }
    execution_result = {
        "schema_version": "1.0",
        "execution_id": execution_id,
        "parent_ablation_id": ORIGINAL_ABLATION_ID,
        "evidence_freeze_id": freeze_id,
        "producer_git_sha": producer_git_sha,
        "git_dirty": False,
        "provider_call_executed": False,
        "provider_call_executed_in_this_stage": False,
        "provider_output_reused": True,
        "v2_plan_generation_mode": "REUSED_VERIFIED_PROVIDER_OUTPUT",
        "provider_request_id": FROZEN_PROVIDER_REQUEST_ID,
        "source_provider_request_id": FROZEN_PROVIDER_REQUEST_ID,
        "new_provider_request_id": None,
        "actual_execution": True,
        "runner_verified": True,
        "exit_code": 0,
        "dataset_sha256": DATASET_SHA256,
        "decision_threshold": 0.4,
        "metrics": reproduced_metrics,
        "recomputed": round2["recomputed"],
        "environment_fingerprint": environment,
    }
    canonical_before = CANONICAL_POINTER_PATH.read_bytes()
    files = {
        "captain_acceptance_reference.json": {
            "path": str(CAPTAIN_ACCEPTANCE_PATH.relative_to(repository_root).as_posix()),
            "sha256": source_file_sha256(CAPTAIN_ACCEPTANCE_PATH),
            "record_type": acceptance["record_type"],
            "authorized_before_original_provider_call": False,
        },
        "original_ablation_reference.json": {
            "original_ablation_id": ORIGINAL_ABLATION_ID,
            "path": ORIGINAL_PACKAGE_REL,
            "ORIGINAL_EXECUTION_GIT_DIRTY": True,
            "ORIGINAL_EVIDENCE_STATUS": "PRELIMINARY_VALID_RESULT_WITH_DIRTY_WORKTREE",
            "SUPERSEDING_EVIDENCE_FREEZE_ID": freeze_id,
            "SUPERSEDED_REASON": "clean-room reproduction and byte-stable checksum freeze",
            "package_manifest_sha256": source_file_sha256(
                ORIGINAL_PACKAGE_DIR / "package_manifest.json"
            ),
        },
        "frozen_input_reference.json": {
            "no_reviewer_input_sha256": bundle["digests"]["no_reviewer_input.json"],
            "no_reviewer_prompt_sha256": bundle["digests"]["no_reviewer_prompt_snapshot.txt"],
            "copied": False,
            "note": "Frozen inputs are referenced by digest; the original package is not copied.",
        },
        "frozen_provider_output_reference.json": {
            "provider": "bailian",
            "model": "qwen3.6-flash",
            "request_id": FROZEN_PROVIDER_REQUEST_ID,
            "v2_revision_plan_sha256": bundle["digests"]["v2_revision_plan.json"],
            "provider_audit_sha256": bundle["digests"]["provider_audit.json"],
            "policy_validation_sha256": bundle["digests"]["policy_validation.json"],
            "v2_plan_generation_mode": "REUSED_VERIFIED_PROVIDER_OUTPUT",
            "new_request_id_created": False,
        },
        "reproduction_execution_spec.json": execution_spec,
        "reproduction_execution_result.json": execution_result,
        "raw_results.json": {
            "true_positive": round2["recomputed"]["true_positive"],
            "true_negative": round2["recomputed"]["true_negative"],
            "false_positive": round2["recomputed"]["false_positive"],
            "false_negative": round2["recomputed"]["false_negative"],
            "evidence_freeze_id": freeze_id,
        },
        "metrics.json": reproduced_metrics,
        "artifact_manifest.json": {
            "schema_version": "1.0",
            "evidence_freeze_id": freeze_id,
            "round2_output": "round2_run/output",
            "producer_git_sha": producer_git_sha,
        },
        "comparison_to_original.json": {
            "original_ablation_id": ORIGINAL_ABLATION_ID,
            "original_git_dirty": True,
            "reproduced_git_dirty": False,
            "metrics_match": True,
            "original_metrics": original_metrics,
            "reproduced_metrics": reproduced_metrics,
            "conclusion_unchanged": True,
        },
        "comparison_matrix.json": build_verified_comparison_matrix(full_system, no_reviewer, traces),
        "ablation_conclusion.json": {
            **conclusion,
            "protocol_id": PROTOCOL_ID,
            "original_ablation_id": ORIGINAL_ABLATION_ID,
            "evidence_freeze_id": freeze_id,
            "quality_gain": False,
            "traceability_gain": True,
            "REVIEWER_EFFECT_RESULT": "TRACEABILITY_ONLY_GAIN",
            "full_system": {
                "malignant_recall": full_system["round2_malignant_recall"],
                "target_achieved": True,
            },
            "no_reviewer": no_reviewer,
            **traces,
            "negative_result_disclosed": True,
            "caveats": [
                "Holdout quality metrics are identical between arms.",
                "FULL_SYSTEM includes one extra Scientific Reviewer call and a structured issue/closure chain.",
                "NO_REVIEWER has planner audit plus execution, not an end-to-end Reviewer revision trace.",
                "This arm is evaluation-only and is not canonical-eligible.",
            ],
        },
        "provenance_attestation.json": {
            "evidence_freeze_id": freeze_id,
            "producer_git_sha": producer_git_sha,
            "protocol_commit_sha": protocol_commit_sha(repository_root=repository_root),
            "original_ablation_artifact_sha": "b8faeb9a7d366c1858abcd7ff6fe04755d60432b",
            "canonical_attempt_id": CANONICAL_ATTEMPT,
            "canonical_pointer_updated": False,
            "environment": environment,
        },
        "provider_call_disclosure.json": {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
            "evidence_freeze_id": freeze_id,
            "original_provider_calls_this_arm": 1,
            "provider_calls_this_stage": 0,
            "project_provider_calls_before": PROJECT_PROVIDER_CALLS_BEFORE_FREEZE,
            "project_provider_calls_after": PROJECT_PROVIDER_CALLS_AFTER_FREEZE,
            "project_provider_calls_added": 0,
            "source_provider_request_id": FROZEN_PROVIDER_REQUEST_ID,
            "new_provider_request_id_created": False,
            "note": "The original Bailian call occurred in ACTUAL_ABLATION_01. This freeze stage reused that output.",
        },
        "verification_summary.json": {
            "evidence_freeze_id": freeze_id,
            "FORMAL_ABLATION_EVIDENCE_STATUS": "CAPTAIN_ACCEPTED_CLEAN_REPRODUCED",
            "CHECKSUM_FILE_WRITTEN": True,
            "CHECKSUM_VERIFIED_BEFORE_COMMIT": True,
            "CHECKSUM_STATUS_AT_PACKAGING": "VERIFIED_IN_PRODUCER_TREE",
            "ORIGINAL_EXECUTION_GIT_DIRTY": True,
            "REPRODUCTION_GIT_DIRTY": False,
            "BYTE_STABILITY_RULE": "docs/reproducibility/ablations/Q028/verified/** -text",
        },
    }
    for name, payload in files.items():
        _write_json(package_dir / name, payload)
    reproduction_md = (
        "# Q028 No-Reviewer Evidence Freeze\n\n"
        f"- evidence_freeze_id: `{freeze_id}`\n"
        f"- original_ablation_id: `{ORIGINAL_ABLATION_ID}`\n"
        "- conclusion: `TRACEABILITY_ONLY_GAIN` (unchanged)\n"
        "- provider_calls_this_stage: `0`\n"
        "- original_execution_git_dirty: `true` (historical, not rewritten)\n"
        "- reproduction_git_dirty: `false`\n"
        "- captain_acceptance: post-execution evidence acceptance, not pre-call authorization\n"
        "- No-Reviewer is not canonical-eligible\n"
        "- Q028 canonical pointer is not updated\n"
    )
    (package_dir / "reproduction.md").write_bytes(reproduction_md.encode("utf-8"))
    _copy_round2_tree(Path(round2["output_root"]), package_dir / "round2_run")
    checksum_report = write_checksums(package_dir)
    if CANONICAL_POINTER_PATH.read_bytes() != canonical_before:
        raise EvidenceFreezeError("canonical pointer mutated during freeze packaging")
    original_result_after = _load_json(ORIGINAL_PACKAGE_DIR / "execution_result.json")
    if original_result_after.get("git_dirty") is not True:
        raise EvidenceFreezeError("original git_dirty was rewritten")
    return {
        "package_dir": package_dir,
        "execution_id": execution_id,
        "checksum_report": checksum_report,
        "package_digest": package_digest(package_dir),
        "execution_result": execution_result,
        "conclusion": conclusion,
        "traces": traces,
        "metrics": reproduced_metrics,
    }


def write_actual_ablation_pointer(
    *,
    freeze_id: str,
    package_dir: Path,
    producer_git_sha: str,
    artifact_snapshot_git_sha: str | None,
    acceptance_sha256: str,
    package_digest_value: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "original_ablation_id": ORIGINAL_ABLATION_ID,
        "evidence_freeze_id": freeze_id,
        "path": str(package_dir.relative_to(REPOSITORY_ROOT).as_posix()),
        "package_digest": package_digest_value,
        "producer_git_sha": producer_git_sha,
        "artifact_snapshot_git_sha": artifact_snapshot_git_sha,
        "authorization_acceptance_digest": acceptance_sha256,
        "verification_status": "CAPTAIN_ACCEPTED_CLEAN_REPRODUCED",
        "checksum_status_at_pointer_write": "VERIFIED_IN_PRODUCER_TREE",
        "canonical_pointer_updated": False,
        "updated_at": _now(),
    }
    canonical_before = CANONICAL_POINTER_PATH.read_bytes()
    write_pointer_atomic(ACTUAL_ABLATION_POINTER_PATH, payload)
    if CANONICAL_POINTER_PATH.read_bytes() != canonical_before:
        raise EvidenceFreezeError("canonical pointer mutated while writing ablation pointer")
    return payload


def overlay_verified_status(base: dict[str, Any]) -> dict[str, Any]:
    payload = dict(base)
    traces = split_traceability_fields()
    payload.update(
        {
            "original_ablation_id": ORIGINAL_ABLATION_ID,
            "captain_acceptance_timing": "POST_EXECUTION_EVIDENCE_ACCEPTANCE",
            "provider_calls_this_stage": 0,
            "project_provider_call_total": PROJECT_PROVIDER_CALLS_AFTER_FREEZE,
            "reviewer_effect_result": "TRACEABILITY_ONLY_GAIN",
            "quality_gain": False,
            "full_system_end_to_end_revision_trace_complete": True,
            "no_reviewer_planner_audit_trace_complete": True,
            "no_reviewer_reviewer_issue_trace_status": "NOT_PRESENT_BY_ABLATION",
            "no_reviewer_issue_closure_status": "NOT_APPLICABLE_NO_REVIEWER",
            "no_reviewer_end_to_end_revision_trace_complete": False,
            "traceability_complete": None,
            "traceability_complete_deprecated": True,
            "traceability_complete_note": traces["NO_REVIEWER_TRACEABILITY_COMPLETE_NOTE"],
            "no_reviewer_canonical_eligible": False,
            "canonical_pointer_updated": False,
            **{k.lower(): v for k, v in traces.items() if k.startswith("NO_REVIEWER_") or k.startswith("FULL_SYSTEM_")},
        }
    )
    if CAPTAIN_ACCEPTANCE_PATH.exists():
        acceptance = _load_json(CAPTAIN_ACCEPTANCE_PATH)
        assert_acceptance_not_pre_call(acceptance)
        payload["captain_acceptance_status"] = acceptance["record_type"]
        payload["captain_acceptance_authorized_before_original_provider_call"] = False
        payload["captain_acceptance_sha256"] = source_file_sha256(CAPTAIN_ACCEPTANCE_PATH)
    else:
        payload["captain_acceptance_status"] = "missing"
    if ACTUAL_ABLATION_POINTER_PATH.exists():
        pointer = _load_json(ACTUAL_ABLATION_POINTER_PATH)
        package_dir = REPOSITORY_ROOT / pointer["path"]
        checksum_ok = False
        checksum_status = "pointer_present_package_missing"
        if package_dir.is_dir():
            report = verify_checksums(package_dir)
            checksum_ok = bool(report["ok"])
            git = collect_git_provenance(repository_root=REPOSITORY_ROOT)
            if checksum_ok and git.get("dirty") is False:
                checksum_status = "VERIFIED_AFTER_FRESH_CHECKOUT"
            elif checksum_ok:
                checksum_status = "VERIFIED_IN_PRODUCER_TREE"
            else:
                checksum_status = "CHECKSUM_MISMATCH"
            conclusion = _load_json(package_dir / "ablation_conclusion.json")
            result = _load_json(package_dir / "reproduction_execution_result.json")
            disclosure = _load_json(package_dir / "provider_call_disclosure.json")
            payload["verified_evidence_freeze_id"] = pointer.get("evidence_freeze_id")
            payload["artifact_path"] = pointer.get("path")
            payload["ablation_conclusion"] = conclusion
            payload["reproduction_execution_result"] = {
                "execution_id": result.get("execution_id"),
                "git_dirty": result.get("git_dirty"),
                "provider_output_reused": result.get("provider_output_reused"),
                "source_provider_request_id": result.get("source_provider_request_id"),
                "metrics": result.get("metrics"),
            }
            payload["provider_call_disclosure"] = disclosure
            payload["producer_git_sha"] = result.get("producer_git_sha") or pointer.get("producer_git_sha")
            payload["artifact_snapshot_git_sha"] = pointer.get("artifact_snapshot_git_sha")
            payload["execution_git_dirty"] = bool(result.get("git_dirty"))
            payload["provider_output_reused"] = True
            payload["formal_evidence_status"] = "CAPTAIN_ACCEPTED_CLEAN_REPRODUCED"
            payload["package_digest"] = pointer.get("package_digest")
        payload["checksum_status"] = checksum_status
        payload["checksum_ok"] = checksum_ok
        payload["actual_ablation_pointer"] = pointer
    else:
        payload["verified_evidence_freeze_id"] = None
        payload["checksum_status"] = "PENDING_VERIFIED_PACKAGE"
        payload["formal_evidence_status"] = "CAPTAIN_ACCEPTANCE_RECORDED_PACKAGE_PENDING"
        payload["execution_git_dirty"] = None
        payload["provider_output_reused"] = True
        payload["producer_git_sha"] = None
        payload["artifact_snapshot_git_sha"] = None
    return payload


def run_evidence_freeze(
    *,
    stamp: str,
    external_root: Path,
    producer_git_sha: str | None = None,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    assert_worktree_clean(repository_root)
    producer_git_sha = producer_git_sha or current_commit_sha(repository_root)
    acceptance = _load_json(CAPTAIN_ACCEPTANCE_PATH)
    assert_acceptance_not_pre_call(acceptance)
    freeze_id = f"Q028-ACTUAL-ABLATION-01-FREEZE-{stamp}"
    package_dir = VERIFIED_ROOT / freeze_id
    canonical_before = CANONICAL_POINTER_PATH.read_bytes()
    original_execution = (ORIGINAL_PACKAGE_DIR / "execution_result.json").read_bytes()
    round2 = run_clean_room_round2(
        external_root=external_root,
        producer_git_sha=producer_git_sha,
        repository_root=repository_root,
    )
    built = build_verified_package(
        package_dir=package_dir,
        freeze_id=freeze_id,
        producer_git_sha=producer_git_sha,
        external_root=external_root,
        round2=round2,
        acceptance=acceptance,
        repository_root=repository_root,
    )
    pointer = write_actual_ablation_pointer(
        freeze_id=freeze_id,
        package_dir=package_dir,
        producer_git_sha=producer_git_sha,
        artifact_snapshot_git_sha=None,
        acceptance_sha256=source_file_sha256(CAPTAIN_ACCEPTANCE_PATH),
        package_digest_value=built["package_digest"],
    )
    if CANONICAL_POINTER_PATH.read_bytes() != canonical_before:
        raise EvidenceFreezeError("canonical pointer changed")
    if (ORIGINAL_PACKAGE_DIR / "execution_result.json").read_bytes() != original_execution:
        raise EvidenceFreezeError("original ablation package was modified")
    receipt = {
        "evidence_freeze_id": freeze_id,
        "execution_id": built["execution_id"],
        "producer_git_sha": producer_git_sha,
        "package_dir": str(package_dir.as_posix()),
        "package_digest": built["package_digest"],
        "checksum_verified_before_commit": True,
        "pointer": pointer,
        "round2": {
            "git_dirty": round2["git_dirty"],
            "metrics": round2["metrics"],
            "output_root": round2["output_root"],
        },
    }
    _write_json(external_root / "execution_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    raise SystemExit("invoke run_evidence_freeze() from a driver after the producer commit")
