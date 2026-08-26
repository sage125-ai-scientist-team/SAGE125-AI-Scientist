"""Tests for the generic RETAIN_SUSPECT_FINAL atomic publication state machine."""

from __future__ import annotations

import json
import os
import stat
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
