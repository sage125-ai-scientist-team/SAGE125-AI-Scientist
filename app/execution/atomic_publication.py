"""Generic ``RETAIN_SUSPECT_FINAL`` atomic publication state machine.

This module implements the project-wide atomic publication policy used to
promote a validated staging package to a canonical, read-only final
directory::

    STAGING -> PRECOMMIT_VALIDATED -> ATOMIC_RENAMED
        -> PUBLISHED_PENDING_VERIFICATION
        -> PUBLISHED_VERIFIED | PUBLISHED_UNVERIFIED

Guarantees enforced here:

* staging and final share the same parent directory, so promotion is a
  single ``os.replace`` rename;
* the final destination must not already exist -- ``RETAIN_SUSPECT_FINAL``
  means a suspect/failed final is *retained* and never deleted, overwritten,
  or renamed a second time;
* exactly one staging -> final rename is ever performed per attempt;
* after the rename the final directory is made best-effort read-only and is
  never written to or deleted by this module again;
* post-publish verification is strictly read-only;
* on verification failure the final directory is retained as-is, the state
  becomes ``PUBLISHED_UNVERIFIED``, no PASS receipt is written, and the
  canonical pointer is not advanced;
* every attempt writes an append-only receipt record (PASS or FAIL);
* retries always mint a brand-new ``attempt_id``, staging path, and final
  path -- this module refuses to reuse or mutate a previous attempt.

This module is intentionally domain-agnostic: it never inspects the content
of the package being published. Domain-specific precommit/post-publish
checks (e.g. the Q028/WDBC canonical package validator) are supplied by the
caller as ``validator`` / ``verifier`` callables.
"""

from __future__ import annotations

import json
import os
import stat
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field


PublicationState = Literal[
    "STAGING",
    "PRECOMMIT_VALIDATED",
    "ATOMIC_RENAMED",
    "PUBLISHED_PENDING_VERIFICATION",
    "PUBLISHED_VERIFIED",
    "PUBLISHED_UNVERIFIED",
]

POLICY_VERSION = "RETAIN_SUSPECT_FINAL-v1"


class AtomicPublicationError(RuntimeError):
    """Raised whenever the publication state machine must fail closed."""


class PrecommitValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    checked_at: str
    manifest_hash: str | None = None
    checksum_inventory_hash: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PostPublishVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    verified_at: str
    manifest_hash: str | None = None
    checksum_inventory_hash: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PublicationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    run_id: str
    case_id: str
    source_git_sha: str | None = None
    staging_path: str
    final_path: str
    state: PublicationState
    created_at: str
    renamed_at: str | None = None
    verified_at: str | None = None
    manifest_hash: str | None = None
    checksum_inventory_hash: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    previous_canonical_attempt_id: str | None = None
    policy_version: str = POLICY_VERSION


class PublicationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    attempt_id: str
    run_id: str
    case_id: str
    outcome: Literal["PASS", "FAIL"]
    state: PublicationState
    written_at: str
    final_path: str
    manifest_hash: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    policy_version: str = POLICY_VERSION


class CanonicalPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    attempt_id: str
    run_id: str
    final_path: str
    manifest_hash: str
    updated_at: str
    policy_version: str = POLICY_VERSION


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, path)


def _append_json_line(path: Path, payload: dict[str, Any]) -> None:
    """Append-only receipt journal: never truncates or rewrites prior lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def new_attempt(
    *,
    run_id: str,
    case_id: str,
    staging_root: Path,
    final_root: Path,
    source_git_sha: str | None = None,
    previous_canonical_attempt_id: str | None = None,
) -> PublicationAttempt:
    """Create a fresh attempt with brand-new, per-attempt staging/final paths.

    ``staging_root`` and ``final_root`` must share the same parent directory
    (and therefore the same filesystem) so the eventual promotion is a single
    atomic rename.
    """
    staging_root = Path(staging_root)
    final_root = Path(final_root)
    if staging_root.parent != final_root.parent:
        raise AtomicPublicationError(
            "staging and final must share the same parent directory for an atomic rename"
        )
    attempt_id = f"pub-{uuid.uuid4().hex}"
    staging_path = staging_root / f".{case_id}.{attempt_id}.staging"
    final_path = final_root / f"{case_id}.{attempt_id}"
    if staging_path.exists() or staging_path.is_symlink():
        raise AtomicPublicationError("staging destination already exists or is unsafe")
    if final_path.exists() or final_path.is_symlink():
        raise AtomicPublicationError("final destination already exists or is unsafe")
    staging_path.mkdir(parents=True)
    return PublicationAttempt(
        attempt_id=attempt_id,
        run_id=run_id,
        case_id=case_id,
        source_git_sha=source_git_sha,
        staging_path=str(staging_path),
        final_path=str(final_path),
        state="STAGING",
        created_at=_now(),
        previous_canonical_attempt_id=previous_canonical_attempt_id,
    )


def precommit_validate(
    attempt: PublicationAttempt,
    validator: Callable[[Path], PrecommitValidationResult],
) -> tuple[PublicationAttempt, PrecommitValidationResult]:
    """Run all staging-side checks. Never renames; never mutates on failure
    beyond recording the failure reason on the returned attempt copy."""
    if attempt.state != "STAGING":
        raise AtomicPublicationError(
            f"precommit validation requires STAGING state, got {attempt.state}"
        )
    result = validator(Path(attempt.staging_path))
    if not result.ok:
        updated = attempt.model_copy(
            update={
                "failure_code": result.failure_code or "PRECOMMIT_VALIDATION_FAILED",
                "failure_message": result.failure_message,
            }
        )
        return updated, result
    updated = attempt.model_copy(
        update={
            "state": "PRECOMMIT_VALIDATED",
            "manifest_hash": result.manifest_hash,
            "checksum_inventory_hash": result.checksum_inventory_hash,
        }
    )
    return updated, result


def _make_read_only(root: Path) -> None:
    """Best-effort recursive read-only marking (Windows/POSIX-compatible).

    This is advisory hardening, not a security boundary: an administrator or
    the file owner can still reverse it. It exists so that accidental writes
    after publication fail fast instead of silently mutating canonical
    evidence.
    """
    for path in sorted(root.rglob("*"), reverse=True):
        try:
            if path.is_file():
                os.chmod(path, stat.S_IREAD)
            elif path.is_dir():
                os.chmod(path, stat.S_IREAD | stat.S_IEXEC)
        except OSError:
            continue
    try:
        os.chmod(root, stat.S_IREAD | stat.S_IEXEC)
    except OSError:
        pass


def publish_atomic(attempt: PublicationAttempt) -> PublicationAttempt:
    """Perform the single, one-shot staging -> final rename.

    Refuses to run for an attempt that is not ``PRECOMMIT_VALIDATED`` and
    refuses to overwrite an existing final directory: a prior suspect final
    is never deleted or replaced ("RETAIN_SUSPECT_FINAL"). Callers must
    start a brand-new attempt (``new_attempt``) to retry.
    """
    if attempt.state != "PRECOMMIT_VALIDATED":
        raise AtomicPublicationError(
            f"atomic rename requires PRECOMMIT_VALIDATED state, got {attempt.state}"
        )
    staging_path = Path(attempt.staging_path)
    final_path = Path(attempt.final_path)
    if final_path.exists() or final_path.is_symlink():
        raise AtomicPublicationError(
            "final destination already exists; RETAIN_SUSPECT_FINAL forbids "
            "overwriting a previous publication -- retry with a new attempt"
        )
    if not staging_path.exists():
        raise AtomicPublicationError(
            "staging directory is missing; this attempt may have already been published"
        )
    os.replace(staging_path, final_path)
    _make_read_only(final_path)
    renamed_at = _now()
    return attempt.model_copy(
        update={
            "state": "PUBLISHED_PENDING_VERIFICATION",
            "renamed_at": renamed_at,
        }
    )


def post_publish_verify(
    attempt: PublicationAttempt,
    verifier: Callable[[Path], PostPublishVerificationResult],
) -> tuple[PublicationAttempt, PostPublishVerificationResult]:
    """Read-only verification of the final directory. Never mutates it."""
    if attempt.state != "PUBLISHED_PENDING_VERIFICATION":
        raise AtomicPublicationError(
            "post-publish verification requires PUBLISHED_PENDING_VERIFICATION "
            f"state, got {attempt.state}"
        )
    result = verifier(Path(attempt.final_path))
    verified_at = _now()
    if result.ok:
        updated = attempt.model_copy(
            update={
                "state": "PUBLISHED_VERIFIED",
                "verified_at": verified_at,
                "manifest_hash": result.manifest_hash or attempt.manifest_hash,
                "checksum_inventory_hash": (
                    result.checksum_inventory_hash or attempt.checksum_inventory_hash
                ),
            }
        )
    else:
        updated = attempt.model_copy(
            update={
                "state": "PUBLISHED_UNVERIFIED",
                "verified_at": verified_at,
                "failure_code": result.failure_code or "POST_PUBLISH_VERIFICATION_FAILED",
                "failure_message": result.failure_message,
            }
        )
    return updated, result


def write_receipt(attempt: PublicationAttempt, receipts_dir: Path) -> PublicationReceipt:
    """Append-only receipt journal.

    A ``PASS`` receipt is only ever written for ``PUBLISHED_VERIFIED``
    attempts; every other terminal or failure state produces a ``FAIL``
    receipt. Receipts for one case accumulate in a single append-only JSONL
    journal that is never truncated or rewritten.
    """
    outcome: Literal["PASS", "FAIL"] = (
        "PASS" if attempt.state == "PUBLISHED_VERIFIED" else "FAIL"
    )
    if outcome == "PASS" and attempt.manifest_hash is None:
        raise AtomicPublicationError("cannot write a PASS receipt without a manifest_hash")
    receipt = PublicationReceipt(
        receipt_id=f"receipt-{uuid.uuid4().hex}",
        attempt_id=attempt.attempt_id,
        run_id=attempt.run_id,
        case_id=attempt.case_id,
        outcome=outcome,
        state=attempt.state,
        written_at=_now(),
        final_path=attempt.final_path,
        manifest_hash=attempt.manifest_hash,
        failure_code=attempt.failure_code,
        failure_message=attempt.failure_message,
    )
    receipts_dir = Path(receipts_dir)
    journal = receipts_dir / f"{attempt.case_id}.receipts.jsonl"
    _append_json_line(journal, receipt.model_dump(mode="json"))
    return receipt


def update_canonical_pointer(attempt: PublicationAttempt, pointer_path: Path) -> CanonicalPointer:
    """Advance the canonical pointer. Only ever valid for ``PUBLISHED_VERIFIED``."""
    if attempt.state != "PUBLISHED_VERIFIED":
        raise AtomicPublicationError(
            "canonical pointer may only be updated for a PUBLISHED_VERIFIED attempt"
        )
    if attempt.manifest_hash is None:
        raise AtomicPublicationError("cannot update canonical pointer without a manifest_hash")
    pointer = CanonicalPointer(
        case_id=attempt.case_id,
        attempt_id=attempt.attempt_id,
        run_id=attempt.run_id,
        final_path=attempt.final_path,
        manifest_hash=attempt.manifest_hash,
        updated_at=_now(),
    )
    _write_json_atomic(Path(pointer_path), pointer.model_dump(mode="json"))
    return pointer


def read_canonical_pointer(pointer_path: Path) -> CanonicalPointer:
    path = Path(pointer_path)
    if not path.exists():
        raise AtomicPublicationError("no canonical publication exists yet")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CanonicalPointer.model_validate(payload)


def load_canonical_package(pointer_path: Path) -> Path:
    """The canonical consumer entrypoint.

    Resolves the pointer and refuses anything other than an intact,
    filesystem-present final directory. Callers that need the *state*
    guarantee (as opposed to just "a directory exists") should keep and
    check the ``PublicationAttempt``/receipt directly -- existence of the
    final directory alone must never be treated as proof of a successful
    publication.
    """
    pointer = read_canonical_pointer(pointer_path)
    final_path = Path(pointer.final_path)
    if not final_path.exists() or not final_path.is_dir():
        raise AtomicPublicationError("canonical pointer target is missing")
    return final_path


def assert_consumer_accepts_state(state: PublicationState) -> None:
    """Canonical consumers must categorically refuse ``PUBLISHED_UNVERIFIED``
    (and any non-terminal state)."""
    if state != "PUBLISHED_VERIFIED":
        raise AtomicPublicationError(
            f"canonical consumers must reject non-verified publication state: {state}"
        )
