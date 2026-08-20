"""Tests for the Q028/WDBC canonical package atomic publication pipeline.

These tests redirect the publication destination (``canonical_root``) to a
temporary directory so that running the test suite never mutates the real,
already-published canonical evidence under
``docs/modules/T05/canonical``. They still read the *real* Round 1/Round 2
evidence already committed in this workspace (validated independently by
``test_flagship_canonical.py``), so a skip is used if that evidence is not
present (e.g. a fresh checkout before Round 2 has been formally executed).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.execution import atomic_publication as ap
from app.execution import flagship_canonical as fc
from app.execution import flagship_publish as fp


pytestmark = pytest.mark.skipif(
    not (fc.ROUND2_PACKAGE / "execution_result.json").exists(),
    reason="formal Round 2 has not been executed in this workspace yet",
)


def test_publish_succeeds_against_real_committed_evidence(tmp_path: Path) -> None:
    result = fp.publish_flagship_canonical_package(
        source_git_sha="deadbeefcafebabe0000000000000000000000",
        canonical_root=tmp_path,
    )
    assert result["published"] is True
    assert result["state"] == "PUBLISHED_VERIFIED"
    assert result["manifest_hash"]

    final_path = Path(result["final_path"])
    assert final_path.exists()
    for name in (
        "canonical_manifest.json",
        "checksums.sha256",
        "package_manifest.json",
        "regression_matrix.json",
        "reproduction.md",
        "semantic_validation.json",
    ):
        assert (final_path / name).is_file()

    semantic = json.loads((final_path / "semantic_validation.json").read_text(encoding="utf-8"))
    assert semantic["status"] == "PASS"

    pointer_path = tmp_path / "canonical_pointer.json"
    pointer = ap.read_canonical_pointer(pointer_path)
    assert pointer.attempt_id == result["attempt_id"]
    assert Path(pointer.final_path) == final_path


def test_get_canonical_status_reports_published_after_publish(tmp_path: Path) -> None:
    status_before = fp.get_canonical_status(canonical_root=tmp_path)
    assert status_before["canonical_published"] is False

    fp.publish_flagship_canonical_package(canonical_root=tmp_path)

    status_after = fp.get_canonical_status(canonical_root=tmp_path)
    assert status_after["canonical_published"] is True
    assert status_after["canonical_pointer"]["case_id"] == "Q028"


def test_repeated_publish_creates_new_attempts_and_preserves_prior_finals(tmp_path: Path) -> None:
    first = fp.publish_flagship_canonical_package(canonical_root=tmp_path)
    second = fp.publish_flagship_canonical_package(canonical_root=tmp_path)

    assert first["attempt_id"] != second["attempt_id"]
    assert first["final_path"] != second["final_path"]
    assert Path(first["final_path"]).exists()
    assert Path(second["final_path"]).exists()

    pointer = ap.read_canonical_pointer(tmp_path / "canonical_pointer.json")
    assert pointer.attempt_id == second["attempt_id"]

    journal = tmp_path / "receipts" / "Q028.receipts.jsonl"
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_publish_refuses_when_semantic_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing_report = {
        "schema_version": "1.0",
        "case_id": "Q028",
        "checks": [{"category": "round2", "requirement_id": "CANON-E-001", "status": "FAIL", "detail": "missing"}],
        "fail_closed_reasons": ["CANON-E-001: missing"],
        "status": "FAIL",
        "round2_blocked": True,
        "check_count": 1,
        "failed_count": 1,
    }
    monkeypatch.setattr(fp, "validate_flagship_canonical_package", lambda: failing_report)

    result = fp.publish_flagship_canonical_package(canonical_root=tmp_path)
    assert result["published"] is False
    assert result["state"] == "STAGING"
    assert result["failure_code"] == "SEMANTIC_VALIDATION_FAILED"

    # No final directory and no canonical pointer must ever be produced.
    assert not (tmp_path / "canonical_pointer.json").exists()
    finals = [p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("Q028.") and not p.name.startswith(".")]
    assert finals == []


def test_post_publish_verification_failure_is_caught_and_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        fp,
        "_post_publish_verifier",
        lambda _final: ap.PostPublishVerificationResult(
            ok=False,
            verified_at="2026-01-01T00:00:00Z",
            failure_code="INJECTED_TEST_FAILURE",
            failure_message="forced failure for test coverage",
        ),
    )
    result = fp.publish_flagship_canonical_package(canonical_root=tmp_path)
    assert result["published"] is False
    assert result["state"] == "PUBLISHED_UNVERIFIED"
    assert result["failure_code"] == "INJECTED_TEST_FAILURE"

    # The suspect final must be retained (RETAIN_SUSPECT_FINAL), not deleted.
    assert Path(result["final_path"]).exists()
    # No canonical pointer may be created from an unverified publication.
    assert not (tmp_path / "canonical_pointer.json").exists()

    journal = tmp_path / "receipts" / "Q028.receipts.jsonl"
    receipts = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert receipts[-1]["outcome"] == "FAIL"
