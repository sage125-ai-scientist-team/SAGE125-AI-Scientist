"""Evidence-freeze guards for Q028 No-Reviewer clean-room reproduction."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from app.execution import flagship_ablation as fa
from app.execution import flagship_ablation_freeze as freeze


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init")
    _git(root, "config", "user.email", "freeze-test@example.invalid")
    _git(root, "config", "user.name", "freeze-test")
    (root / "tracked.py").write_text("print(1)\n", encoding="utf-8")
    _git(root, "add", "tracked.py")
    _git(root, "commit", "-m", "init")
    return root


def test_01_clean_tree_guard_rejects_dirty_tracked_code(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    freeze.assert_worktree_clean(repo)
    (repo / "tracked.py").write_text("print(2)\n", encoding="utf-8")
    with pytest.raises(freeze.EvidenceFreezeError, match="CLEAN_TREE_GUARD"):
        freeze.assert_worktree_clean(repo)


def test_02_external_output_does_not_dirty_producer(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    external = tmp_path / "run"
    freeze.assert_external_output_root(external, repository_root=repo)
    (external / "out.json").parent.mkdir(parents=True, exist_ok=True)
    (external / "out.json").write_text("{}\n", encoding="utf-8")
    freeze.assert_worktree_clean(repo)
    with pytest.raises(freeze.EvidenceFreezeError, match="outside the git worktree"):
        freeze.assert_external_output_root(repo / "inside", repository_root=repo)


def test_03_frozen_provider_output_is_reusable_hashed_input() -> None:
    bundle = freeze.load_frozen_provider_bundle()
    assert bundle["request_id"] == freeze.FROZEN_PROVIDER_REQUEST_ID
    assert bundle["v2_plan_generation_mode"] == "REUSED_VERIFIED_PROVIDER_OUTPUT"
    assert bundle["digests"]["v2_revision_plan.json"]
    assert bundle["plan"].proposed_changes[0]["to"] == 0.4


def test_04_reuse_does_not_increment_provider_call_count() -> None:
    bundle = freeze.load_frozen_provider_bundle()
    assert bundle["provider_call_executed_in_this_stage"] is False
    assert len(bundle["audit"]["calls"]) == 1
    disclosure_original = json.loads(
        (freeze.ORIGINAL_PACKAGE_DIR / "provider_call_disclosure.json").read_text(encoding="utf-8")
    )
    assert disclosure_original["project_provider_calls_after"] == 5


def test_05_reuse_cannot_mint_new_request_id() -> None:
    bundle = freeze.load_frozen_provider_bundle()
    assert bundle["new_provider_request_id"] is None
    assert bundle["request_id"] == "chatcmpl-3f97b794-de17-93c4-aa1b-c1a427a5a76c"


def test_06_original_git_dirty_is_not_rewritten() -> None:
    original = json.loads(
        (freeze.ORIGINAL_PACKAGE_DIR / "execution_result.json").read_text(encoding="utf-8")
    )
    assert original["git_dirty"] is True
    bundle = freeze.load_frozen_provider_bundle()
    assert bundle["original_execution_git_dirty"] is True
    reread = json.loads(
        (freeze.ORIGINAL_PACKAGE_DIR / "execution_result.json").read_text(encoding="utf-8")
    )
    assert reread["git_dirty"] is True


def test_07_captain_acceptance_is_not_pre_call_authorization() -> None:
    payload = freeze.build_captain_acceptance_payload()
    freeze.assert_acceptance_not_pre_call(payload)
    assert payload["authorized_before_original_provider_call"] is False
    assert payload["historical_actual_ablation_authorized"] is False
    assert payload["record_type"] == "captain_post_execution_evidence_acceptance"
    assert payload["new_provider_calls_authorized"] == 0
    if freeze.CAPTAIN_ACCEPTANCE_PATH.exists():
        existing = json.loads(freeze.CAPTAIN_ACCEPTANCE_PATH.read_text(encoding="utf-8"))
        freeze.assert_acceptance_not_pre_call(existing)


def test_08_original_metrics_match_frozen_constants() -> None:
    original = json.loads((freeze.ORIGINAL_PACKAGE_DIR / "metrics.json").read_text(encoding="utf-8"))
    freeze.assert_metrics_match(freeze.ORIGINAL_METRICS, original)
    predictions = freeze.ORIGINAL_PACKAGE_DIR / "round2_run" / "output" / "predictions.csv"
    recomputed = fa.recompute_holdout_metrics(predictions)
    freeze.assert_metrics_match(original, recomputed)


def test_09_metric_mismatch_fail_closed() -> None:
    with pytest.raises(freeze.EvidenceFreezeError, match="REPRODUCTION_MISMATCH"):
        freeze.assert_metrics_match(
            freeze.ORIGINAL_METRICS,
            {**freeze.ORIGINAL_METRICS, "malignant_recall": 0.5},
        )


def test_10_checksums_are_verified_not_only_written(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "metrics.json").write_bytes(b'{"ok":true}\n')
    freeze.write_checksums(package)
    report = freeze.verify_checksums(package)
    assert report["ok"] is True
    (package / "metrics.json").write_bytes(b'{"ok":false}\n')
    failed = freeze.verify_checksums(package)
    assert failed["ok"] is False
    assert failed["mismatches"]


def test_11_and_12_verified_path_is_crlf_protected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "freeze-test@example.invalid")
    _git(repo, "config", "user.name", "freeze-test")
    _git(repo, "config", "core.autocrlf", "true")
    gitattributes = (
        "* text=auto\n"
        "*.json text eol=lf\n"
        "*.svg text eol=lf\n"
        "docs/reproducibility/ablations/Q028/verified/** -text\n"
    )
    (repo / ".gitattributes").write_text(gitattributes, encoding="utf-8")
    verified = repo / "docs" / "reproducibility" / "ablations" / "Q028" / "verified" / "demo"
    verified.mkdir(parents=True)
    payload = b'<svg>\nline\n</svg>\n'
    (verified / "summary.svg").write_bytes(payload)
    (verified / "note.md").write_bytes(b"# freeze\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "verified bytes")
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    checkout = tmp_path / "fresh"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(checkout), sha],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(repo),
    )
    fresh_svg = checkout / "docs/reproducibility/ablations/Q028/verified/demo/summary.svg"
    assert fresh_svg.read_bytes() == payload
    other_json = repo / "docs" / "reproducibility" / "ablations" / "Q028" / "outside.json"
    attr = _git(
        repo,
        "check-attr",
        "text",
        "--",
        "docs/reproducibility/ablations/Q028/verified/demo/summary.svg",
    ).stdout
    assert "text: unset" in attr
    outside_attr = subprocess.run(
        ["git", "check-attr", "text", "--", "docs/reproducibility/ablations/Q028/ACTUAL_ABLATION_01_PROTOCOL.json"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(freeze.REPOSITORY_ROOT),
    ).stdout
    assert "text: unset" not in outside_attr
    assert other_json.exists() is False


def test_13_gitattributes_rule_is_scoped_to_verified_dir() -> None:
    repo = freeze.REPOSITORY_ROOT
    verified_attr = subprocess.run(
        [
            "git",
            "check-attr",
            "text",
            "--",
            "docs/reproducibility/ablations/Q028/verified/placeholder.json",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(repo),
    ).stdout
    protocol_attr = subprocess.run(
        [
            "git",
            "check-attr",
            "text",
            "--",
            "docs/reproducibility/ablations/Q028/ACTUAL_ABLATION_01_PROTOCOL.json",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(repo),
    ).stdout
    assert "text: unset" in verified_attr
    assert "text: set" in protocol_attr or "text: unspecified" not in protocol_attr


def test_14_planner_and_reviewer_traces_are_split() -> None:
    traces = freeze.split_traceability_fields()
    assert traces["NO_REVIEWER_PLANNER_AUDIT_TRACE_COMPLETE"] is True
    assert traces["NO_REVIEWER_REVIEWER_ISSUE_TRACE_STATUS"] == "NOT_PRESENT_BY_ABLATION"
    assert traces["NO_REVIEWER_ISSUE_CLOSURE_STATUS"] == "NOT_APPLICABLE_NO_REVIEWER"
    assert traces["NO_REVIEWER_END_TO_END_REVISION_TRACE_COMPLETE"] is False
    assert traces["FULL_SYSTEM_END_TO_END_REVISION_TRACE_COMPLETE"] is True
    assert traces["NO_REVIEWER_TRACEABILITY_COMPLETE"] is None


def test_15_no_reviewer_is_not_canonical_eligible() -> None:
    status = fa.get_actual_ablation_status()
    assert status["no_reviewer_canonical_eligible"] is False


def test_16_ablation_pointer_does_not_modify_canonical_pointer(tmp_path: Path) -> None:
    before = fa.POINTER_PATH.read_bytes()
    original_pointer = freeze.ACTUAL_ABLATION_POINTER_PATH
    try:
        freeze.ACTUAL_ABLATION_POINTER_PATH = tmp_path / "actual_ablation_pointer.json"
        payload = freeze.write_actual_ablation_pointer(
            freeze_id="demo",
            package_dir=freeze.VERIFIED_ROOT / "demo-do-not-create",
            producer_git_sha="abc",
            artifact_snapshot_git_sha=None,
            acceptance_sha256="00" * 32,
            package_digest_value="11" * 32,
        )
        assert payload["canonical_pointer_updated"] is False
        assert freeze.ACTUAL_ABLATION_POINTER_PATH.exists()
        assert fa.POINTER_PATH.read_bytes() == before
    finally:
        freeze.ACTUAL_ABLATION_POINTER_PATH = original_pointer
    assert fa.POINTER_PATH.read_bytes() == before


def test_17_original_ablation_package_is_unmodified() -> None:
    execution = freeze.ORIGINAL_PACKAGE_DIR / "execution_result.json"
    payload = json.loads(execution.read_text(encoding="utf-8"))
    assert payload["git_dirty"] is True
    assert payload["git_sha"] == "015a0a62a0646c83c93a7aaa31596b1da44e6734"


def test_18_project_provider_call_total_stays_five() -> None:
    status = fa.get_actual_ablation_status()
    assert status["project_provider_call_total"] == 5
    assert status["provider_calls_this_stage"] == 0


def test_19_api_status_has_no_secrets() -> None:
    status = fa.get_actual_ablation_status()
    text = json.dumps(status, ensure_ascii=False)
    for banned in ("Authorization", "Bearer ", "DASHSCOPE_API_KEY", "sk-", "api_key", "workspace_id"):
        assert banned not in text
    assert status.get("captain_acceptance_timing") == "POST_EXECUTION_EVIDENCE_ACCEPTANCE"
    assert status.get("reviewer_effect_result") == "TRACEABILITY_ONLY_GAIN"
    assert status.get("quality_gain") is False


def test_20_no_clobber_and_path_traversal(tmp_path: Path) -> None:
    target = tmp_path / "file.json"
    freeze.write_bytes_no_clobber(target, b"abc")
    freeze.write_bytes_no_clobber(target, b"abc")
    with pytest.raises(freeze.EvidenceFreezeError, match="no-clobber"):
        freeze.write_bytes_no_clobber(target, b"abcd")
    with pytest.raises(freeze.EvidenceFreezeError, match="PATH_TRAVERSAL_GUARD"):
        freeze.resolve_under(tmp_path / "pkg", tmp_path / "other" / "x.json")


def test_21_traceability_fields_present_on_status() -> None:
    status = fa.get_actual_ablation_status()
    assert status["full_system_end_to_end_revision_trace_complete"] is True
    assert status["no_reviewer_planner_audit_trace_complete"] is True
    assert status["no_reviewer_reviewer_issue_trace_status"] == "NOT_PRESENT_BY_ABLATION"
    assert status["no_reviewer_issue_closure_status"] == "NOT_APPLICABLE_NO_REVIEWER"
    assert status["no_reviewer_end_to_end_revision_trace_complete"] is False
    assert status["traceability_complete"] is None


def test_22_verified_package_contract_when_present() -> None:
    if not freeze.ACTUAL_ABLATION_POINTER_PATH.exists():
        pytest.fail("verified actual_ablation_pointer.json is required after freeze packaging")
    pointer = json.loads(freeze.ACTUAL_ABLATION_POINTER_PATH.read_text(encoding="utf-8"))
    package = freeze.REPOSITORY_ROOT / pointer["path"]
    assert package.is_dir()
    report = freeze.verify_checksums(package)
    assert report["ok"] is True
    result = json.loads((package / "reproduction_execution_result.json").read_text(encoding="utf-8"))
    assert result["git_dirty"] is False
    assert result["provider_output_reused"] is True
    assert result["provider_request_id"] == freeze.FROZEN_PROVIDER_REQUEST_ID
    assert result["new_provider_request_id"] is None
    assert result["producer_git_sha"] != pointer.get("artifact_snapshot_git_sha") or pointer.get("artifact_snapshot_git_sha") is None
    conclusion = json.loads((package / "ablation_conclusion.json").read_text(encoding="utf-8"))
    assert conclusion["REVIEWER_EFFECT_RESULT"] == "TRACEABILITY_ONLY_GAIN"
    assert conclusion["quality_gain"] is False
    assert conclusion["NO_REVIEWER_END_TO_END_REVISION_TRACE_COMPLETE"] is False
    original = json.loads((freeze.ORIGINAL_PACKAGE_DIR / "execution_result.json").read_text(encoding="utf-8"))
    assert original["git_dirty"] is True
    freeze.assert_metrics_match(freeze.ORIGINAL_METRICS, result["metrics"])
    canonical = json.loads(fa.POINTER_PATH.read_text(encoding="utf-8"))
    assert "pub-a7d6c7e7dd6c42a488c7f39079d6a434" in json.dumps(canonical)
    disclosure = json.loads((package / "provider_call_disclosure.json").read_text(encoding="utf-8"))
    assert disclosure["provider_calls_this_stage"] == 0
    assert disclosure["project_provider_calls_after"] == 5
    assert "AUTHORIZED_BEFORE_ORIGINAL_RUN" not in json.dumps(conclusion)
    status = fa.get_actual_ablation_status()
    assert status["formal_evidence_status"] == "CAPTAIN_ACCEPTED_CLEAN_REPRODUCED"
    assert hashlib.sha256(freeze.CAPTAIN_ACCEPTANCE_PATH.read_bytes()).hexdigest() == status["captain_acceptance_sha256"]
