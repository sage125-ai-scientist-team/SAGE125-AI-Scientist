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

``publish_atomic`` performs the staging -> final rename with a manual
existence check followed by ``os.replace``. That check-then-rename sequence
has a TOCTOU window: a concurrent publisher can create ``final_path`` after
the check but before the rename, and ``os.replace`` (POSIX ``rename(2)``)
will then silently clobber it. ``publish_atomic_no_clobber`` closes that gap:
it serializes concurrent publishers with an exclusive filesystem lock and
performs the rename with a true kernel-level no-replace primitive
(``os.rename`` on Windows, ``renameat2(RENAME_NOREPLACE)`` on Linux,
``renamex_np(RENAME_EXCL)`` on macOS) that fails atomically instead of
clobbering when the destination exists. On platforms without such a
primitive it fails closed rather than degrading to a clobbering
``os.replace()``. All Q028/WDBC flagship publications use
``publish_atomic_no_clobber``.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
import stat
import sys
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


class PublishLockHeldError(AtomicPublicationError):
    """Raised when a publish lock is already held by another attempt/process."""


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


def _renameat2_noreplace(src: Path, dst: Path) -> None:
    """Linux ``renameat2(2)`` with ``RENAME_NOREPLACE`` -- a true kernel-level
    no-clobber rename (no TOCTOU window between an existence check and the
    rename itself). Fails closed (raises) if the syscall or flag is
    unavailable; never falls back to a clobbering rename."""
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
    except OSError as exc:  # pragma: no cover - exercised only on non-glibc hosts
        raise AtomicPublicationError(
            f"NO_CLOBBER_UNSUPPORTED_PLATFORM: libc unavailable for renameat2: {exc}"
        ) from exc
    if not hasattr(libc, "renameat2"):  # pragma: no cover - old glibc
        raise AtomicPublicationError(
            "NO_CLOBBER_UNSUPPORTED_PLATFORM: libc.renameat2 is not exported on this host"
        )
    AT_FDCWD = -100
    RENAME_NOREPLACE = 1
    libc.renameat2.restype = ctypes.c_int
    libc.renameat2.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
    ]
    ctypes.set_errno(0)
    rc = libc.renameat2(
        AT_FDCWD, os.fsencode(str(src)), AT_FDCWD, os.fsencode(str(dst)), RENAME_NOREPLACE,
    )
    if rc == 0:
        return
    err = ctypes.get_errno()
    if err == errno.EEXIST:
        raise FileExistsError(errno.EEXIST, "Destination exists (RENAME_NOREPLACE)", str(dst))
    if err in (errno.EINVAL, errno.ENOSYS):  # pragma: no cover - old kernel/fs
        raise AtomicPublicationError(
            f"NO_CLOBBER_UNSUPPORTED_PLATFORM: kernel/filesystem rejects "
            f"renameat2(RENAME_NOREPLACE) (errno={err}); refusing to fall back to os.replace()"
        )
    raise OSError(err, os.strerror(err), str(dst))  # pragma: no cover - unexpected errno


def _renamex_np_excl(src: Path, dst: Path) -> None:  # pragma: no cover - macOS only
    """macOS ``renamex_np(2)`` with ``RENAME_EXCL`` -- true kernel no-clobber rename."""
    try:
        libc = ctypes.CDLL("libc.dylib", use_errno=True)
    except OSError as exc:
        raise AtomicPublicationError(
            f"NO_CLOBBER_UNSUPPORTED_PLATFORM: libc unavailable for renamex_np: {exc}"
        ) from exc
    if not hasattr(libc, "renamex_np"):
        raise AtomicPublicationError(
            "NO_CLOBBER_UNSUPPORTED_PLATFORM: libc.renamex_np is not exported on this host"
        )
    RENAME_EXCL = 0x0004
    libc.renamex_np.restype = ctypes.c_int
    libc.renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    ctypes.set_errno(0)
    rc = libc.renamex_np(os.fsencode(str(src)), os.fsencode(str(dst)), RENAME_EXCL)
    if rc == 0:
        return
    err = ctypes.get_errno()
    if err == errno.EEXIST:
        raise FileExistsError(errno.EEXIST, "Destination exists (RENAME_EXCL)", str(dst))
    if err in (errno.EINVAL, errno.ENOSYS, errno.ENOTSUP):
        raise AtomicPublicationError(
            f"NO_CLOBBER_UNSUPPORTED_PLATFORM: renamex_np(RENAME_EXCL) unsupported (errno={err})"
        )
    raise OSError(err, os.strerror(err), str(dst))


def _no_replace_rename(src: Path, dst: Path) -> None:
    """Perform a single atomic rename that is guaranteed to fail (rather than
    silently clobber) if ``dst`` already exists, with no TOCTOU window.

    Platform semantics:
      * Windows (``os.name == "nt"``): the Win32 ``MoveFileW`` call underlying
        Python's ``os.rename`` (as opposed to ``os.replace``) does *not* pass
        ``MOVEFILE_REPLACE_EXISTING`` and therefore already raises
        ``FileExistsError`` if the destination exists -- this gives native,
        race-free no-clobber semantics.
      * Linux: ``renameat2(2)`` with ``RENAME_NOREPLACE`` (atomic, kernel-level).
      * macOS: ``renamex_np(2)`` with ``RENAME_EXCL`` (atomic, kernel-level).
      * Any other platform: fail closed. This function must never fall back
        to a clobbering ``os.replace()``.
    """
    if os.name == "nt":
        os.rename(src, dst)
        return
    if sys.platform.startswith("linux"):
        _renameat2_noreplace(src, dst)
        return
    if sys.platform == "darwin":  # pragma: no cover - macOS only
        _renamex_np_excl(src, dst)
        return
    raise AtomicPublicationError(  # pragma: no cover - exotic platform
        f"NO_CLOBBER_UNSUPPORTED_PLATFORM: no strict no-replace rename primitive is "
        f"implemented for platform {sys.platform!r}; refusing to fall back to a "
        f"clobbering os.replace()"
    )


def _lock_path_for(case_id: str, lock_dir: Path) -> Path:
    return Path(lock_dir) / f".{case_id}.publish.lock"


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness check; a failure to determine liveness is treated
    as "alive" so staleness detection stays conservative (fail closed)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            STILL_ACTIVE = 259
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def read_publish_lock(lock_path: Path) -> dict[str, Any]:
    """Read and return the contents of a publish lock file (diagnostic use)."""
    path = Path(lock_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AtomicPublicationError(f"cannot read publish lock at {path}: {exc}") from exc


def acquire_publish_lock(lock_path: Path, *, attempt_id: str, source_git_sha: str | None) -> None:
    """Acquire an exclusive publish lock via ``O_CREAT | O_EXCL`` (atomic
    create-if-absent). Raises :class:`PublishLockHeldError` if another
    attempt/process already holds the lock."""
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            info = read_publish_lock(lock_path)
        except AtomicPublicationError:
            info = {"note": "lock file exists but is unreadable/corrupt"}
        raise PublishLockHeldError(f"PUBLISH_LOCK_HELD: another publish attempt holds the lock: {info}") from None
    try:
        payload = {
            "attempt_id": attempt_id,
            "pid": os.getpid(),
            "timestamp": _now(),
            "source_git_sha": source_git_sha,
        }
        os.write(fd, json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    finally:
        os.close(fd)


def release_publish_lock(lock_path: Path) -> None:
    """Release a publish lock. Safe to call even if the lock does not exist.

    A handful of short retries absorb transient Windows file-lock contention
    (e.g. an AV/indexer briefly holding a freshly-created small file) without
    ever leaving the lock permanently unreleased due to a spurious sharing
    violation.
    """
    lock_path = Path(lock_path)
    last_exc: OSError | None = None
    for attempt_no in range(5):
        try:
            lock_path.unlink()
            return
        except FileNotFoundError:
            return
        except PermissionError as exc:  # pragma: no cover - platform-dependent flake
            last_exc = exc
            time.sleep(0.02 * (attempt_no + 1))
    if last_exc is not None:  # pragma: no cover - platform-dependent flake
        raise last_exc


def is_lock_stale(lock_path: Path, *, max_age_seconds: float = 900.0) -> bool:
    """A lock is only ever considered stale when *both* it is older than
    ``max_age_seconds`` *and* the recorded owning PID is no longer alive.
    This is intentionally conservative: an old-but-still-running publisher's
    lock is never reported stale, so callers cannot accidentally steal an
    active lock."""
    info = read_publish_lock(lock_path)
    try:
        recorded = time.strptime(info["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        age_seconds = time.mktime(time.gmtime()) - time.mktime(recorded)
    except (KeyError, ValueError):
        age_seconds = float("inf")
    pid = info.get("pid")
    return age_seconds > max_age_seconds and not _pid_alive(pid)


def force_break_stale_lock(lock_path: Path, *, max_age_seconds: float = 900.0) -> None:
    """Explicit, caller-intentional stale-lock recovery.

    This function *never* runs automatically as part of ``publish_atomic_no_clobber``.
    A caller must call it deliberately, and it still refuses to remove a lock
    that is not provably stale (age + dead PID) -- so an unknown, possibly
    still-active lock can never be silently stolen.
    """
    lock_path = Path(lock_path)
    if not lock_path.exists():
        return
    if not is_lock_stale(lock_path, max_age_seconds=max_age_seconds):
        raise PublishLockHeldError(
            "refusing to break publish lock: it is not proven stale "
            "(recorded owner may still be an active process)"
        )
    release_publish_lock(lock_path)


def publish_atomic_no_clobber(attempt: PublicationAttempt, *, lock_dir: Path | None = None) -> PublicationAttempt:
    """Hardened, no-clobber replacement for :func:`publish_atomic`.

    Differences from ``publish_atomic``:
      * an exclusive, filesystem-level publish lock (``O_CREAT|O_EXCL``)
        serializes concurrent publishers for the same ``case_id`` so that at
        most one rename attempt is ever in flight at a time;
      * the staging -> final promotion uses :func:`_no_replace_rename`, a
        true no-clobber rename primitive with no existence-check-then-rename
        TOCTOU window, instead of ``os.replace`` (which silently clobbers);
      * on any failure prior to a successful rename the lock is released and
        the final directory (if any pre-existing suspect final) is left
        completely untouched -- ``RETAIN_SUSPECT_FINAL`` still holds;
      * after a successful rename the attempt is marked
        ``PUBLISHED_PENDING_VERIFICATION`` exactly as ``publish_atomic`` does.
    """
    if attempt.state != "PRECOMMIT_VALIDATED":
        raise AtomicPublicationError(
            f"atomic rename requires PRECOMMIT_VALIDATED state, got {attempt.state}"
        )
    staging_path = Path(attempt.staging_path)
    final_path = Path(attempt.final_path)
    lock_root = Path(lock_dir) if lock_dir is not None else final_path.parent
    lock_path = _lock_path_for(attempt.case_id, lock_root)

    acquire_publish_lock(lock_path, attempt_id=attempt.attempt_id, source_git_sha=attempt.source_git_sha)
    try:
        if final_path.exists() or final_path.is_symlink():
            raise AtomicPublicationError(
                "NO_CLOBBER_VIOLATION: final destination already exists; RETAIN_SUSPECT_FINAL "
                "forbids overwriting a previous publication -- retry with a new attempt"
            )
        if not staging_path.exists():
            raise AtomicPublicationError(
                "staging directory is missing; this attempt may have already been published"
            )
        try:
            _no_replace_rename(staging_path, final_path)
        except FileExistsError as exc:
            raise AtomicPublicationError(
                "NO_CLOBBER_VIOLATION: final destination was created by a concurrent publisher "
                "between the precheck and the rename (TOCTOU) -- retry with a new attempt"
            ) from exc
    except Exception:
        release_publish_lock(lock_path)
        raise
    _make_read_only(final_path)
    renamed_at = _now()
    release_publish_lock(lock_path)
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
