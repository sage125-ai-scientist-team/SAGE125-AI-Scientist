"""Tests for the generic RETAIN_SUSPECT_FINAL atomic publication state machine."""

from __future__ import annotations

import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

import pytest

from app.execution import atomic_publication as ap


def _ok_validator(manifest_hash: str = "deadbeef" * 8):
    def _validator(_staging: Path) -> ap.PrecommitValidationResult:
        return ap.PrecommitValidationResult(
            ok=True,
            checked_at="2026-01-01T00:00:00Z",
            manifest_hash=manifest_hash,
            checksum_inventory_hash="cafebabe" * 8,
        )

    return _validator


def _failing_validator(code: str = "MISSING_FILE"):
    def _validator(_staging: Path) -> ap.PrecommitValidationResult:
        return ap.PrecommitValidationResult(
            ok=False,
            checked_at="2026-01-01T00:00:00Z",
            failure_code=code,
            failure_message="required evidence file is missing",
        )

    return _validator


def _ok_verifier(manifest_hash: str = "deadbeef" * 8):
    def _verifier(_final: Path) -> ap.PostPublishVerificationResult:
        return ap.PostPublishVerificationResult(
            ok=True, verified_at="2026-01-01T00:01:00Z", manifest_hash=manifest_hash
        )

    return _verifier


def _failing_verifier(code: str = "CHECKSUM_MISMATCH"):
    def _verifier(_final: Path) -> ap.PostPublishVerificationResult:
        return ap.PostPublishVerificationResult(
            ok=False,
            verified_at="2026-01-01T00:01:00Z",
            failure_code=code,
            failure_message="checksum mismatch after rename",
        )

    return _verifier


def _make_dirs(tmp_path: Path) -> tuple[Path, Path]:
    parent = tmp_path / "publication-root"
    staging_root = parent / "staging"
    final_root = parent / "final"
    staging_root.mkdir(parents=True)
    final_root.mkdir(parents=True)
    return staging_root, final_root


def test_precommit_failure_blocks_rename_and_leaves_canonical_untouched(tmp_path: Path) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    pointer_path = tmp_path / "canonical" / "pointer.json"
    attempt = ap.new_attempt(
        run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
    )
    (Path(attempt.staging_path) / "placeholder.txt").write_text("x", encoding="utf-8")

    updated, result = ap.precommit_validate(attempt, _failing_validator())
    assert result.ok is False
    assert updated.state == "STAGING"
    assert updated.failure_code == "MISSING_FILE"
    assert not Path(attempt.final_path).exists()
    assert not pointer_path.exists()

    with pytest.raises(ap.AtomicPublicationError):
        ap.publish_atomic(updated)
    assert not Path(attempt.final_path).exists()


def test_rename_success_and_verification_success_publishes_and_updates_canonical(
    tmp_path: Path,
) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    receipts_dir = tmp_path / "receipts"
    pointer_path = tmp_path / "canonical" / "pointer.json"
    attempt = ap.new_attempt(
        run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
    )
    (Path(attempt.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")

    attempt, precommit = ap.precommit_validate(attempt, _ok_validator())
    assert precommit.ok is True
    assert attempt.state == "PRECOMMIT_VALIDATED"

    attempt = ap.publish_atomic(attempt)
    assert attempt.state == "PUBLISHED_PENDING_VERIFICATION"
    assert Path(attempt.final_path).exists()
    assert not Path(attempt.staging_path).exists()

    attempt, verification = ap.post_publish_verify(attempt, _ok_verifier())
    assert verification.ok is True
    assert attempt.state == "PUBLISHED_VERIFIED"

    receipt = ap.write_receipt(attempt, receipts_dir)
    assert receipt.outcome == "PASS"

    pointer = ap.update_canonical_pointer(attempt, pointer_path)
    assert pointer.attempt_id == attempt.attempt_id
    resolved = ap.load_canonical_package(pointer_path)
    assert resolved == Path(attempt.final_path)

    journal = receipts_dir / "Q028.receipts.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["outcome"] == "PASS"


def test_rename_success_verification_failure_retains_final_and_blocks_canonical(
    tmp_path: Path,
) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    receipts_dir = tmp_path / "receipts"
    pointer_path = tmp_path / "canonical" / "pointer.json"
    attempt = ap.new_attempt(
        run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
    )
    (Path(attempt.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")

    attempt, _ = ap.precommit_validate(attempt, _ok_validator())
    attempt = ap.publish_atomic(attempt)
    final_path = Path(attempt.final_path)
    assert final_path.exists()

    attempt, verification = ap.post_publish_verify(attempt, _failing_verifier())
    assert verification.ok is False
    assert attempt.state == "PUBLISHED_UNVERIFIED"

    # Final must be retained -- never deleted.
    assert final_path.exists()
    assert (final_path / "evidence.json").exists()

    # No PASS receipt; a FAIL receipt is written instead (append-only journal).
    receipt = ap.write_receipt(attempt, receipts_dir)
    assert receipt.outcome == "FAIL"
    journal = receipts_dir / "Q028.receipts.jsonl"
    assert json.loads(journal.read_text(encoding="utf-8").splitlines()[0])["outcome"] == "FAIL"

    # Canonical pointer must not be created/updated.
    assert not pointer_path.exists()
    with pytest.raises(ap.AtomicPublicationError):
        ap.update_canonical_pointer(attempt, pointer_path)

    # No second rename is permitted for this attempt.
    with pytest.raises(ap.AtomicPublicationError):
        ap.publish_atomic(attempt)


def test_existing_final_directory_blocks_publish_without_overwrite(tmp_path: Path) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    attempt = ap.new_attempt(
        run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
    )
    (Path(attempt.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")
    attempt, _ = ap.precommit_validate(attempt, _ok_validator())

    # Simulate a final directory that already exists at the same path (e.g. a
    # duplicated attempt id, or a defensive re-run).
    Path(attempt.final_path).mkdir(parents=True)
    (Path(attempt.final_path) / "sentinel.txt").write_text("do-not-touch", encoding="utf-8")

    with pytest.raises(ap.AtomicPublicationError):
        ap.publish_atomic(attempt)

    # The pre-existing final content must be completely untouched.
    assert (Path(attempt.final_path) / "sentinel.txt").read_text(encoding="utf-8") == "do-not-touch"
    assert Path(attempt.staging_path).exists()  # staging was never consumed


def test_retry_uses_new_attempt_and_never_touches_previous_suspect_final(tmp_path: Path) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    receipts_dir = tmp_path / "receipts"

    first = ap.new_attempt(
        run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
    )
    (Path(first.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")
    first, _ = ap.precommit_validate(first, _ok_validator())
    first = ap.publish_atomic(first)
    first, _ = ap.post_publish_verify(first, _failing_verifier())
    ap.write_receipt(first, receipts_dir)
    suspect_final = Path(first.final_path)
    assert suspect_final.exists()

    second = ap.new_attempt(
        run_id="run-1",
        case_id="Q028",
        staging_root=staging_root,
        final_root=final_root,
        previous_canonical_attempt_id=first.attempt_id,
    )
    assert second.attempt_id != first.attempt_id
    assert second.final_path != first.final_path
    assert second.staging_path != first.staging_path

    (Path(second.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")
    second, _ = ap.precommit_validate(second, _ok_validator())
    second = ap.publish_atomic(second)
    second, _ = ap.post_publish_verify(second, _ok_verifier())
    assert second.state == "PUBLISHED_VERIFIED"

    # The old suspect final must be completely unaffected by the retry.
    assert suspect_final.exists()
    assert (suspect_final / "evidence.json").exists()
    assert Path(second.final_path).exists()
    assert Path(second.final_path) != suspect_final


def test_canonical_consumer_rejects_unverified_state() -> None:
    with pytest.raises(ap.AtomicPublicationError):
        ap.assert_consumer_accepts_state("PUBLISHED_UNVERIFIED")
    with pytest.raises(ap.AtomicPublicationError):
        ap.assert_consumer_accepts_state("PUBLISHED_PENDING_VERIFICATION")
    ap.assert_consumer_accepts_state("PUBLISHED_VERIFIED")  # must not raise


def test_concurrent_or_duplicate_submission_of_same_attempt_cannot_double_publish(
    tmp_path: Path,
) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    attempt = ap.new_attempt(
        run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
    )
    (Path(attempt.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")
    validated, _ = ap.precommit_validate(attempt, _ok_validator())

    published_once = ap.publish_atomic(validated)
    assert published_once.state == "PUBLISHED_PENDING_VERIFICATION"

    # Re-submitting the same (stale) validated attempt object must not
    # produce a second canonical directory or silently succeed.
    with pytest.raises(ap.AtomicPublicationError):
        ap.publish_atomic(validated)

    finals = [p for p in Path(final_root).iterdir() if p.is_dir()]
    assert len(finals) == 1


def test_receipts_are_append_only_and_never_overwrite_history(tmp_path: Path) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    receipts_dir = tmp_path / "receipts"

    for _ in range(3):
        attempt = ap.new_attempt(
            run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
        )
        (Path(attempt.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")
        attempt, _ = ap.precommit_validate(attempt, _ok_validator())
        attempt = ap.publish_atomic(attempt)
        attempt, _ = ap.post_publish_verify(attempt, _failing_verifier())
        ap.write_receipt(attempt, receipts_dir)

    journal = receipts_dir / "Q028.receipts.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    receipt_ids = {json.loads(line)["receipt_id"] for line in lines}
    assert len(receipt_ids) == 3  # all distinct, none overwritten


def test_final_directory_is_best_effort_read_only_after_rename(tmp_path: Path) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    attempt = ap.new_attempt(
        run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
    )
    target_file = Path(attempt.staging_path) / "evidence.json"
    target_file.write_text("{}", encoding="utf-8")
    attempt, _ = ap.precommit_validate(attempt, _ok_validator())
    attempt = ap.publish_atomic(attempt)

    final_file = Path(attempt.final_path) / "evidence.json"
    mode = final_file.stat().st_mode
    assert not (mode & stat.S_IWRITE) or os.name == "nt" and not (mode & stat.S_IWRITE)


def test_staging_and_final_must_share_parent_directory(tmp_path: Path) -> None:
    staging_root = tmp_path / "a" / "staging"
    final_root = tmp_path / "b" / "final"
    staging_root.mkdir(parents=True)
    final_root.mkdir(parents=True)
    with pytest.raises(ap.AtomicPublicationError):
        ap.new_attempt(
            run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
        )


# ---------------------------------------------------------------------------
# GAP-03: NO_CLOBBER hardened publication (publish_atomic_no_clobber).
# ---------------------------------------------------------------------------


def _validated_attempt(tmp_path: Path, *, case_id: str = "Q028") -> ap.PublicationAttempt:
    staging_root, final_root = _make_dirs(tmp_path)
    attempt = ap.new_attempt(
        run_id="run-1", case_id=case_id, staging_root=staging_root, final_root=final_root
    )
    (Path(attempt.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")
    attempt, precommit = ap.precommit_validate(attempt, _ok_validator())
    assert precommit.ok is True
    return attempt


def test_no_clobber_1_destination_already_exists_before_precheck(tmp_path: Path) -> None:
    attempt = _validated_attempt(tmp_path)
    Path(attempt.final_path).mkdir(parents=True)
    (Path(attempt.final_path) / "sentinel.txt").write_text("do-not-touch", encoding="utf-8")

    with pytest.raises(ap.AtomicPublicationError, match="NO_CLOBBER_VIOLATION"):
        ap.publish_atomic_no_clobber(attempt)

    assert (Path(attempt.final_path) / "sentinel.txt").read_text(encoding="utf-8") == "do-not-touch"
    assert Path(attempt.staging_path).exists()
    # Lock must be released after a failed attempt, not leaked.
    lock_path = Path(attempt.final_path).parent / f".{attempt.case_id}.publish.lock"
    assert not lock_path.exists()


def test_no_clobber_2_destination_created_after_precheck_toctou(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    attempt = _validated_attempt(tmp_path)
    final_path = Path(attempt.final_path)
    real_exists = Path.exists
    call_state = {"checked": False}

    def _fake_exists(self: Path) -> bool:  # noqa: ANN001 - matches Path.exists signature
        if self == final_path and not call_state["checked"]:
            call_state["checked"] = True
            # Report "does not exist" for the precheck, then create it right
            # before the rename to simulate a concurrent publisher winning
            # the race in the TOCTOU window.
            final_path.mkdir(parents=True)
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _fake_exists)

    with pytest.raises(ap.AtomicPublicationError, match="NO_CLOBBER_VIOLATION"):
        ap.publish_atomic_no_clobber(attempt)

    # The "concurrent" final directory must be untouched by our failed rename.
    assert final_path.exists()
    assert Path(attempt.staging_path).exists()


def test_no_clobber_3_two_concurrent_publishers_only_one_succeeds(tmp_path: Path) -> None:
    staging_root, final_root = _make_dirs(tmp_path)
    shared_final = final_root / "Q028.shared-attempt"

    def _attempt_targeting_shared_final(idx: int) -> ap.PublicationAttempt:
        attempt = ap.new_attempt(
            run_id="run-1", case_id="Q028", staging_root=staging_root, final_root=final_root
        )
        (Path(attempt.staging_path) / "evidence.json").write_text(str(idx), encoding="utf-8")
        attempt, _ = ap.precommit_validate(attempt, _ok_validator())
        # Force both attempts to target the *same* final path to simulate a
        # true collision (independent of the random attempt_id suffix).
        return attempt.model_copy(update={"final_path": str(shared_final)})

    attempt_a = _attempt_targeting_shared_final(1)
    attempt_b = _attempt_targeting_shared_final(2)

    results: dict[str, object] = {}

    def _publish(name: str, attempt: ap.PublicationAttempt) -> None:
        try:
            results[name] = ap.publish_atomic_no_clobber(attempt)
        except ap.AtomicPublicationError as exc:
            results[name] = exc

    barrier = threading.Barrier(2)

    def _run(name: str, attempt: ap.PublicationAttempt) -> None:
        barrier.wait()
        _publish(name, attempt)

    t1 = threading.Thread(target=_run, args=("a", attempt_a))
    t2 = threading.Thread(target=_run, args=("b", attempt_b))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    outcomes = list(results.values())
    successes = [o for o in outcomes if isinstance(o, ap.PublicationAttempt)]
    failures = [o for o in outcomes if isinstance(o, ap.AtomicPublicationError)]
    assert len(successes) == 1, "exactly one concurrent publisher must win"
    assert len(failures) == 1, "the loser must fail closed, not silently no-op"
    assert shared_final.exists()
    # Exactly one final directory was created for the shared destination.
    assert successes[0].final_path == str(shared_final)


def test_no_clobber_4_stale_lock_has_explicit_recovery_not_automatic(tmp_path: Path) -> None:
    attempt = _validated_attempt(tmp_path)
    lock_path = Path(attempt.final_path).parent / f".{attempt.case_id}.publish.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stale_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 10_000))
    lock_path.write_text(
        json.dumps({"attempt_id": "pub-stale", "pid": 999_999_999, "timestamp": stale_timestamp, "source_git_sha": None}),
        encoding="utf-8",
    )

    # Publishing must fail closed while the (stale) lock file is present --
    # no automatic steal.
    with pytest.raises(ap.PublishLockHeldError):
        ap.publish_atomic_no_clobber(attempt)
    assert lock_path.exists()

    # A live-looking lock (current process pid, fresh timestamp) must never
    # be reported as stale, so it can never be silently broken.
    live_lock = lock_path.parent / ".LIVE.publish.lock"
    live_lock.write_text(
        json.dumps({"attempt_id": "pub-live", "pid": os.getpid(), "timestamp": ap._now(), "source_git_sha": None}),
        encoding="utf-8",
    )
    assert ap.is_lock_stale(live_lock, max_age_seconds=0) is False
    with pytest.raises(ap.PublishLockHeldError):
        ap.force_break_stale_lock(live_lock, max_age_seconds=0)

    # Only an explicit, proven-stale break succeeds.
    ap.force_break_stale_lock(lock_path, max_age_seconds=1)
    assert not lock_path.exists()
    published = ap.publish_atomic_no_clobber(attempt)
    assert published.state == "PUBLISHED_PENDING_VERIFICATION"


def test_no_clobber_5_post_verify_failure_then_retry_with_new_attempt(tmp_path: Path) -> None:
    attempt = _validated_attempt(tmp_path)
    attempt = ap.publish_atomic_no_clobber(attempt)
    attempt, verification = ap.post_publish_verify(attempt, _failing_verifier())
    assert attempt.state == "PUBLISHED_UNVERIFIED"
    suspect_final = Path(attempt.final_path)
    assert suspect_final.exists()

    # NO_CLOBBER_6: retry must mint a brand-new attempt (new ids/paths); the
    # old attempt object itself is never reused for the retry rename.
    staging_root = Path(attempt.staging_path).parent
    final_root = Path(attempt.final_path).parent
    retry = ap.new_attempt(
        run_id=attempt.run_id, case_id=attempt.case_id, staging_root=staging_root, final_root=final_root,
        previous_canonical_attempt_id=attempt.attempt_id,
    )
    assert retry.attempt_id != attempt.attempt_id
    assert retry.final_path != attempt.final_path
    (Path(retry.staging_path) / "evidence.json").write_text("{}", encoding="utf-8")
    retry, _ = ap.precommit_validate(retry, _ok_validator())
    retry = ap.publish_atomic_no_clobber(retry)
    retry, verification2 = ap.post_publish_verify(retry, _ok_verifier())
    assert retry.state == "PUBLISHED_VERIFIED"

    # The old suspect final must remain completely untouched.
    assert suspect_final.exists()
    assert Path(retry.final_path) != suspect_final


def test_no_clobber_7_unsupported_platform_fails_closed_never_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Exercise the platform-dispatch primitive directly: constructing new
    # Path objects after monkeypatching os.name/sys.platform is unsafe
    # (pathlib picks WindowsPath/PosixPath based on os.name at construction
    # time), so pre-build the concrete paths first.
    src = tmp_path / "src-dir"
    src.mkdir()
    (src / "evidence.json").write_text("{}", encoding="utf-8")
    dst = tmp_path / "dst-dir"

    monkeypatch.setattr(ap.os, "name", "exotic-os", raising=False)
    monkeypatch.setattr(ap.sys, "platform", "exotic-platform", raising=False)

    with pytest.raises(ap.AtomicPublicationError, match="NO_CLOBBER_UNSUPPORTED_PLATFORM"):
        ap._no_replace_rename(src, dst)

    # Must not have performed any rename (clobbering fallback) at all.
    assert src.exists()
    assert not dst.exists()


def test_no_clobber_8_canonical_pointer_race_never_corrupts_pointer_file(tmp_path: Path) -> None:
    pointer_path = tmp_path / "canonical" / "pointer.json"
    attempts = []
    for i in range(2):
        a = _validated_attempt(tmp_path / f"slot-{i}", case_id=f"Q028-{i}")
        a = ap.publish_atomic_no_clobber(a)
        a, _ = ap.post_publish_verify(a, _ok_verifier(manifest_hash=f"hash-{i}" * 8))
        # Force both onto the same case_id/pointer file to simulate a race
        # over a single canonical pointer.
        a = a.model_copy(update={"case_id": "Q028"})
        attempts.append(a)

    def _update(a: ap.PublicationAttempt) -> None:
        ap.update_canonical_pointer(a, pointer_path)

    t1 = threading.Thread(target=_update, args=(attempts[0],))
    t2 = threading.Thread(target=_update, args=(attempts[1],))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    # The pointer file must always be one fully-written, valid JSON document
    # (never truncated/corrupted by the race) that names one of the two
    # attempts as canonical.
    pointer = ap.read_canonical_pointer(pointer_path)
    assert pointer.attempt_id in {attempts[0].attempt_id, attempts[1].attempt_id}


def test_no_clobber_lock_content_records_required_fields(tmp_path: Path) -> None:
    lock_path = tmp_path / "case.publish.lock"
    ap.acquire_publish_lock(lock_path, attempt_id="pub-abc123", source_git_sha="deadbeef" * 5)
    info = ap.read_publish_lock(lock_path)
    assert info["attempt_id"] == "pub-abc123"
    assert info["source_git_sha"] == "deadbeef" * 5
    assert isinstance(info["pid"], int)
    assert "timestamp" in info
    with pytest.raises(ap.PublishLockHeldError):
        ap.acquire_publish_lock(lock_path, attempt_id="pub-other", source_git_sha=None)
    ap.release_publish_lock(lock_path)
    assert not lock_path.exists()
