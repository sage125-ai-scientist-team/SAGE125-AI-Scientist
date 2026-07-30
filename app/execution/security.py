"""Security helpers for the controlled local execution runner.

The helpers in this module provide narrow, auditable controls around paths,
file copying, output retention, environment construction, redaction, and
workspace cleanup.  They are defence-in-depth for a local process runner, not
an operating-system sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import BinaryIO
from urllib.parse import quote, unquote

__all__ = [
    "BoundedPipeBuffer",
    "FileDigest",
    "PipeCapture",
    "SecurityViolation",
    "StagedFile",
    "build_minimal_environment",
    "copy_verified_file",
    "create_unique_workspace",
    "drain_pipe",
    "ensure_regular_file",
    "ensure_secure_directory",
    "ensure_secure_root",
    "file_sha256",
    "is_reserved_environment_name",
    "is_secret_environment_name",
    "read_verified_bytes",
    "redact_text",
    "safe_cleanup_workspace",
    "secure_relative_path",
]


_HASH_CHUNK_SIZE = 64 * 1024
_PIPE_CHUNK_SIZE = 64 * 1024
_DEFAULT_MAX_COPY_BYTES = 1024 * 1024 * 1024
_MAX_REDACTION_DECODE_ROUNDS = 8
_REDACTED = "[REDACTED]"
_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_WORKSPACE_PREFIX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")
_DRIVE_PREFIX = re.compile(r"[A-Za-z]:")
_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
    *(
        f"com{index}"
        for index in (
            "\N{SUPERSCRIPT ONE}",
            "\N{SUPERSCRIPT TWO}",
            "\N{SUPERSCRIPT THREE}",
        )
    ),
    *(
        f"lpt{index}"
        for index in (
            "\N{SUPERSCRIPT ONE}",
            "\N{SUPERSCRIPT TWO}",
            "\N{SUPERSCRIPT THREE}",
        )
    ),
}
_EXPLICIT_SECRET_ENVIRONMENT_NAMES = {
    "API_KEY",
    "AUTHORIZATION",
    "CREDENTIAL",
    "DASHSCOPE_API_KEY",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "OPENAI_API_KEY",
    "PASSWORD",
    "PRIVATE_KEY",
    "SECRET",
    "TOKEN",
}
_SECRET_ENVIRONMENT_COMPONENTS = {
    "CREDENTIAL",
    "PASSWORD",
    "SECRET",
    "TOKEN",
}
_RESERVED_ENVIRONMENT_NAMES = {
    "BASH_ENV",
    "CDPATH",
    "COMSPEC",
    "CONDA_PREFIX",
    "ENV",
    "GIT_SSH",
    "GIT_SSH_COMMAND",
    "HOME",
    "IFS",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "PROMPT",
    "PSMODULEPATH",
    "SHELLOPTS",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "VIRTUAL_ENV",
    "WINDIR",
    "__COMPAT_LAYER",
}
_RESERVED_ENVIRONMENT_PREFIXES = (
    "DYLD_",
    "LD_",
    "PYTHON",
)
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [^-]*(?:PRIVATE|SECRET) KEY-----.*?"
    r"-----END [^-]*(?:PRIVATE|SECRET) KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_BEARER_TOKEN = re.compile(
    r"(?i)\bBearer[ \t]+[A-Za-z0-9._~+/=-]+",
)
_OPENAI_STYLE_KEY = re.compile(
    r"(?i)\bsk-[A-Za-z0-9][A-Za-z0-9._-]{5,}\b",
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:access[_-]?token|api[_-]?key|authorization|credential|"
    r"password|private[_-]?key|secret|token)\b[ \t]*(?:=|:)[ \t]*)"
    r"(?:Bearer[ \t]+)?([^&;,\s\"']+)",
)
_STANDALONE_SECRET = re.compile(
    r"(?i)\b(?:fake[-_])?(?:access[-_]?token|api[-_]?key|credential|"
    r"password|private[-_]?key|secret|token)[-_]"
    r"[A-Za-z0-9][A-Za-z0-9._-]*\b",
)


class SecurityViolation(ValueError):
    """A runner-safe failure with a stable code and stage.

    ``message`` must be suitable for persistence.  Helper functions never put
    a host absolute path or the text of an underlying ``OSError`` in it.
    """

    __slots__ = ("code", "stage")

    def __init__(self, code: str, stage: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage


@dataclass(frozen=True, slots=True)
class FileDigest:
    """Streaming integrity evidence for one regular file."""

    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class StagedFile:
    """A verified workspace copy and its post-copy digest."""

    path: Path
    digest: FileDigest

    @property
    def sha256(self) -> str:
        return self.digest.sha256

    @property
    def size_bytes(self) -> int:
        return self.digest.size_bytes


@dataclass(frozen=True, slots=True)
class PipeCapture:
    """An immutable snapshot of one drained process pipe."""

    data: bytes
    total_bytes: int
    truncated: bool
    finished: bool
    error: str | None

    @property
    def text(self) -> str:
        return self.data.decode("utf-8", errors="replace")


def _violation(code: str, stage: str, message: str) -> SecurityViolation:
    return SecurityViolation(code=code, stage=stage, message=message)


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _absolute_lexical(path: str | os.PathLike[str]) -> Path:
    """Make a path absolute and collapse dot segments without following links."""

    return Path(os.path.abspath(os.fspath(path)))


def _is_junction(path: Path) -> bool:
    predicate = getattr(path, "is_junction", None)
    if predicate is None:
        return False
    try:
        return bool(predicate())
    except OSError:
        return True


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    attributes = getattr(file_stat, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _is_indirection(path: Path, file_stat: os.stat_result | None = None) -> bool:
    try:
        details = file_stat if file_stat is not None else path.lstat()
    except OSError:
        return True
    return path.is_symlink() or _is_junction(path) or _is_reparse_point(details)


def _decoded_forms(value: str) -> tuple[str, ...]:
    forms = [value]
    current = value
    for _ in range(len(value) + 1):
        decoded = unquote(current)
        if decoded == current:
            return tuple(forms)
        forms.append(decoded)
        current = decoded
    raise ValueError("encoding does not reach a stable representation")


def _validate_relative_form(value: str) -> None:
    if not value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("path contains a forbidden control character")
    if value.startswith(("/", "\\")) or _DRIVE_PREFIX.match(value):
        raise ValueError("path is rooted")

    windows_path = PureWindowsPath(value)
    if windows_path.drive or windows_path.root or windows_path.is_absolute():
        raise ValueError("path has Windows root semantics")

    normalized = value.replace("\\", "/")
    segments = normalized.split("/")
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError("path has an unsafe segment")
    for segment in segments:
        if ":" in segment:
            raise ValueError("path has alternate-stream semantics")
        if segment.endswith((" ", ".")):
            raise ValueError("path has unsafe trailing characters")
        base_name = segment.split(".", 1)[0].casefold()
        if base_name in _WINDOWS_RESERVED_NAMES:
            raise ValueError("path names a Windows device")


def _relative_parts(value: str | os.PathLike[str]) -> tuple[str, ...]:
    try:
        text = os.fspath(value)
    except TypeError as exc:
        raise ValueError("path must be text") from exc
    if not isinstance(text, str) or not text:
        raise ValueError("path must be non-empty text")
    for form in _decoded_forms(text):
        _validate_relative_form(form)
    return tuple(text.replace("\\", "/").split("/"))


def _assert_path_entry_safe(
    path: Path,
    *,
    stage: str,
    symlink_code: str = "symlink_escape",
) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise _violation(
            "path_invalid",
            stage,
            "controlled path metadata is unavailable",
        ) from None
    if _is_indirection(path, details):
        raise _violation(
            symlink_code,
            stage,
            "symbolic links and filesystem reparse points are forbidden",
        )
    return details


def _assert_existing_components_safe(
    root: Path,
    candidate: Path,
    *,
    stage: str,
) -> None:
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        raise _violation(
            "path_escape",
            stage,
            "controlled path is outside the managed root",
        ) from None

    _assert_path_entry_safe(root, stage=stage)
    current = root
    for part in relative.parts:
        current = current / part
        if not _lexists(current):
            break
        _assert_path_entry_safe(current, stage=stage)


def _assert_absolute_components_safe(path: Path, *, stage: str) -> None:
    absolute = _absolute_lexical(path)
    anchor = Path(absolute.anchor)
    current = anchor
    for part in absolute.parts[1:]:
        current = current / part
        if not _lexists(current):
            break
        _assert_path_entry_safe(current, stage=stage)


def ensure_secure_root(
    root: str | os.PathLike[str],
    *,
    create: bool = False,
    stage: str = "workspace",
) -> Path:
    """Return a resolved, non-link directory suitable as a security root."""

    root_path = _absolute_lexical(root)
    if root_path == Path(root_path.anchor):
        raise _violation(
            "path_escape",
            stage,
            "a filesystem root cannot be used as the managed root",
        )

    if not _lexists(root_path):
        if not create:
            raise _violation(
                "path_invalid",
                stage,
                "managed root does not exist",
            )
        missing: list[str] = []
        existing = root_path
        while not _lexists(existing):
            if existing.parent == existing:
                raise _violation(
                    "path_invalid",
                    stage,
                    "managed root has no existing parent",
                )
            missing.append(existing.name)
            existing = existing.parent
        _assert_absolute_components_safe(existing, stage=stage)
        try:
            for name in reversed(missing):
                existing = existing / name
                existing.mkdir()
                _assert_path_entry_safe(existing, stage=stage)
        except OSError:
            raise _violation(
                "path_invalid",
                stage,
                "managed root could not be created",
            ) from None

    _assert_absolute_components_safe(root_path, stage=stage)
    details = _assert_path_entry_safe(root_path, stage=stage)
    if not stat.S_ISDIR(details.st_mode):
        raise _violation(
            "path_invalid",
            stage,
            "managed root must be a directory",
        )
    try:
        resolved = root_path.resolve(strict=True)
    except OSError:
        raise _violation(
            "path_invalid",
            stage,
            "managed root could not be resolved",
        ) from None
    return resolved


def secure_relative_path(
    root: str | os.PathLike[str],
    relative: str | os.PathLike[str],
    *,
    must_exist: bool = False,
    require_file: bool = False,
    require_directory: bool = False,
    stage: str = "path",
    missing_code: str = "path_invalid",
    invalid_code: str = "path_invalid",
) -> Path:
    """Resolve a relative path below ``root`` without following indirection."""

    if require_file and require_directory:
        raise ValueError("a path cannot require both file and directory semantics")
    try:
        parts = _relative_parts(relative)
    except (TypeError, ValueError):
        raise _violation(
            "path_escape",
            stage,
            "path must be a safe relative path",
        ) from None

    root_path = ensure_secure_root(root, create=False, stage=stage)
    candidate = root_path.joinpath(*parts)
    _assert_existing_components_safe(root_path, candidate, stage=stage)
    try:
        resolved = candidate.resolve(strict=must_exist)
        resolved.relative_to(root_path)
    except (OSError, ValueError):
        code = missing_code if must_exist and not _lexists(candidate) else "path_escape"
        raise _violation(
            code,
            stage,
            "controlled path is unavailable or outside the managed root",
        ) from None

    if must_exist and not _lexists(candidate):
        raise _violation(
            missing_code,
            stage,
            "required controlled path does not exist",
        )
    if _lexists(candidate):
        details = _assert_path_entry_safe(candidate, stage=stage)
        if require_file and not stat.S_ISREG(details.st_mode):
            raise _violation(
                invalid_code,
                stage,
                "controlled path is not a regular file",
            )
        if require_directory and not stat.S_ISDIR(details.st_mode):
            raise _violation(
                invalid_code,
                stage,
                "controlled path is not a directory",
            )
    return resolved


def ensure_secure_directory(
    root: str | os.PathLike[str],
    relative: str | os.PathLike[str],
    *,
    stage: str = "workspace",
) -> Path:
    """Create a directory tree below ``root`` without accepting links."""

    try:
        parts = _relative_parts(relative)
    except (TypeError, ValueError):
        raise _violation(
            "path_escape",
            stage,
            "directory must use a safe relative path",
        ) from None
    root_path = ensure_secure_root(root, create=False, stage=stage)
    current = root_path
    for part in parts:
        current = current / part
        if _lexists(current):
            details = _assert_path_entry_safe(current, stage=stage)
            if not stat.S_ISDIR(details.st_mode):
                raise _violation(
                    "path_invalid",
                    stage,
                    "directory component is not a directory",
                )
            continue
        try:
            current.mkdir()
        except OSError:
            raise _violation(
                "path_invalid",
                stage,
                "controlled directory could not be created",
            ) from None
        details = _assert_path_entry_safe(current, stage=stage)
        if not stat.S_ISDIR(details.st_mode):
            raise _violation(
                "path_invalid",
                stage,
                "created path is not a directory",
            )
    return secure_relative_path(
        root_path,
        relative,
        must_exist=True,
        require_directory=True,
        stage=stage,
    )


def create_unique_workspace(
    managed_root: str | os.PathLike[str],
    *,
    prefix: str = "run-",
) -> Path:
    """Create and verify one unpredictable workspace under ``managed_root``."""

    normalized_prefix = prefix[:-1] if prefix.endswith("-") else prefix
    if not normalized_prefix or _WORKSPACE_PREFIX.fullmatch(normalized_prefix) is None:
        raise ValueError("workspace prefix must be a short safe identifier")
    root = ensure_secure_root(managed_root, create=True, stage="workspace")
    try:
        created = Path(tempfile.mkdtemp(prefix=prefix, dir=root))
    except OSError:
        raise _violation(
            "path_invalid",
            "workspace",
            "unique workspace could not be created",
        ) from None
    return secure_relative_path(
        root,
        created.name,
        must_exist=True,
        require_directory=True,
        stage="workspace",
    )


def ensure_regular_file(
    path: str | os.PathLike[str],
    *,
    containment_root: str | os.PathLike[str] | None = None,
    stage: str = "file",
    invalid_code: str = "path_invalid",
) -> Path:
    """Validate an existing path as a non-link regular file."""

    candidate = _absolute_lexical(path)
    if containment_root is not None:
        root = ensure_secure_root(containment_root, create=False, stage=stage)
        try:
            candidate.relative_to(root)
        except ValueError:
            raise _violation(
                "path_escape",
                stage,
                "regular file is outside the managed root",
            ) from None
        _assert_existing_components_safe(root, candidate, stage=stage)
    else:
        _assert_absolute_components_safe(candidate, stage=stage)

    if not _lexists(candidate):
        raise _violation(
            invalid_code,
            stage,
            "required regular file does not exist",
        )
    details = _assert_path_entry_safe(candidate, stage=stage)
    if not stat.S_ISREG(details.st_mode):
        raise _violation(
            invalid_code,
            stage,
            "controlled file is not a regular file",
        )
    try:
        resolved = candidate.resolve(strict=True)
        if containment_root is not None:
            resolved.relative_to(root)
    except (OSError, ValueError):
        raise _violation(
            "path_escape",
            stage,
            "regular file resolves outside the managed root",
        ) from None
    return resolved


def _open_regular_readonly(
    path: Path,
    *,
    stage: str,
    invalid_code: str,
) -> tuple[BinaryIO, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise _violation(
            invalid_code,
            stage,
            "controlled file could not be opened safely",
        ) from None
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise _violation(
                invalid_code,
                stage,
                "controlled file is not a regular file",
            )
        stream = os.fdopen(descriptor, "rb", closefd=True)
    except BaseException:
        os.close(descriptor)
        raise
    return stream, details


def file_sha256(
    path: str | os.PathLike[str],
    *,
    max_bytes: int | None = None,
    containment_root: str | os.PathLike[str] | None = None,
    stage: str = "hash",
    invalid_code: str = "artifact_invalid",
) -> FileDigest:
    """Hash one regular file with fixed-size streaming reads."""

    if max_bytes is not None and (
        type(max_bytes) is not int or max_bytes < 0
    ):
        raise ValueError("max_bytes must be a nonnegative integer or None")
    regular = ensure_regular_file(
        path,
        containment_root=containment_root,
        stage=stage,
        invalid_code=invalid_code,
    )
    digest = hashlib.sha256()
    total = 0
    stream: BinaryIO | None = None
    try:
        stream, before = _open_regular_readonly(
            regular,
            stage=stage,
            invalid_code=invalid_code,
        )
        if max_bytes is not None and before.st_size > max_bytes:
            raise _violation(
                invalid_code,
                stage,
                "controlled file exceeds its byte limit",
            )
        opened_stream = stream
        with opened_stream:
            stream = None
            while True:
                chunk = opened_stream.read(_HASH_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if max_bytes is not None and total > max_bytes:
                    raise _violation(
                        invalid_code,
                        stage,
                        "controlled file exceeds its byte limit",
                    )
                digest.update(chunk)
    except SecurityViolation:
        raise
    except OSError:
        raise _violation(
            invalid_code,
            stage,
            "controlled file could not be read",
        ) from None
    finally:
        if stream is not None:
            stream.close()

    try:
        after = regular.stat()
    except OSError:
        raise _violation(
            invalid_code,
            stage,
            "controlled file changed during verification",
        ) from None
    if (
        after.st_size != total
        or before.st_size != after.st_size
        or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
    ):
        raise _violation(
            invalid_code,
            stage,
            "controlled file changed during verification",
        )
    return FileDigest(sha256=digest.hexdigest(), size_bytes=total)


def read_verified_bytes(
    path: str | os.PathLike[str],
    *,
    expected_sha256: str,
    expected_size: int,
    max_bytes: int,
    containment_root: str | os.PathLike[str] | None = None,
    stage: str = "file",
    invalid_code: str = "artifact_invalid",
) -> bytes:
    """Read bounded bytes while binding that exact read to integrity evidence."""

    if (
        not isinstance(expected_sha256, str)
        or _SHA256.fullmatch(expected_sha256) is None
        or type(expected_size) is not int
        or expected_size < 0
        or type(max_bytes) is not int
        or max_bytes < 0
    ):
        raise _violation(
            invalid_code,
            stage,
            "expected file integrity evidence is invalid",
        )
    if expected_size > max_bytes:
        raise _violation(
            invalid_code,
            stage,
            "controlled file exceeds its byte limit",
        )

    regular = ensure_regular_file(
        path,
        containment_root=containment_root,
        stage=stage,
        invalid_code=invalid_code,
    )
    stream: BinaryIO | None = None
    digest = hashlib.sha256()
    retained = bytearray()
    total = 0
    try:
        stream, before = _open_regular_readonly(
            regular,
            stage=stage,
            invalid_code=invalid_code,
        )
        if before.st_size != expected_size or before.st_size > max_bytes:
            raise _violation(
                invalid_code,
                stage,
                "controlled file no longer matches its integrity evidence",
            )
        opened_stream = stream
        with opened_stream:
            stream = None
            while True:
                chunk = opened_stream.read(_HASH_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise _violation(
                        invalid_code,
                        stage,
                        "controlled file exceeds its byte limit",
                    )
                retained.extend(chunk)
                digest.update(chunk)
            after = os.fstat(opened_stream.fileno())
    except SecurityViolation:
        raise
    except OSError:
        raise _violation(
            invalid_code,
            stage,
            "controlled file could not be read safely",
        ) from None
    finally:
        if stream is not None:
            stream.close()

    if (
        total != expected_size
        or digest.hexdigest() != expected_sha256
        or before.st_size != after.st_size
        or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
    ):
        raise _violation(
            invalid_code,
            stage,
            "controlled file no longer matches its integrity evidence",
        )
    return bytes(retained)


def _unlink_partial_destination(destination: Path) -> None:
    try:
        if _lexists(destination):
            destination.unlink()
    except OSError:
        pass


def copy_verified_file(
    source: str | os.PathLike[str],
    destination_root: str | os.PathLike[str],
    relative_path: str | os.PathLike[str],
    *,
    expected_sha256: str,
    expected_size: int,
    max_bytes: int | None = _DEFAULT_MAX_COPY_BYTES,
    stage: str = "dataset",
) -> StagedFile:
    """Copy a verified source into a workspace and verify both ends again."""

    if not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None:
        raise _violation(
            "dataset_invalid",
            stage,
            "dataset checksum evidence is invalid",
        )
    if type(expected_size) is not int or expected_size < 0:
        raise _violation(
            "dataset_invalid",
            stage,
            "dataset size evidence is invalid",
        )
    if max_bytes is not None and (
        type(max_bytes) is not int or max_bytes < 0
    ):
        raise ValueError("max_bytes must be a nonnegative integer or None")
    if max_bytes is not None and expected_size > max_bytes:
        raise _violation(
            "dataset_invalid",
            stage,
            "dataset exceeds the staging byte limit",
        )

    source_path = ensure_regular_file(
        source,
        stage=stage,
        invalid_code="dataset_invalid",
    )
    source_before = file_sha256(
        source_path,
        max_bytes=max_bytes,
        stage=stage,
        invalid_code="dataset_invalid",
    )
    if (
        source_before.sha256 != expected_sha256
        or source_before.size_bytes != expected_size
    ):
        raise _violation(
            "dataset_invalid",
            stage,
            "dataset source does not match its manifest",
        )

    root = ensure_secure_root(destination_root, create=False, stage=stage)
    try:
        relative_parts = _relative_parts(relative_path)
    except (TypeError, ValueError):
        raise _violation(
            "path_escape",
            stage,
            "dataset destination must be a safe relative path",
        ) from None
    relative_parent = "/".join(relative_parts[:-1])
    if relative_parent:
        ensure_secure_directory(root, relative_parent, stage=stage)
    destination = secure_relative_path(root, relative_path, stage=stage)
    if _lexists(destination):
        raise _violation(
            "path_invalid",
            stage,
            "dataset destination already exists",
        )

    source_stream: BinaryIO | None = None
    destination_stream: BinaryIO | None = None
    copied_hash = hashlib.sha256()
    copied_size = 0
    destination_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        source_stream, _source_details = _open_regular_readonly(
            source_path,
            stage=stage,
            invalid_code="dataset_invalid",
        )
        descriptor = os.open(destination, destination_flags, 0o600)
        destination_stream = os.fdopen(descriptor, "wb", closefd=True)
        while True:
            chunk = source_stream.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            copied_size += len(chunk)
            if max_bytes is not None and copied_size > max_bytes:
                raise _violation(
                    "dataset_invalid",
                    stage,
                    "dataset exceeds the staging byte limit",
                )
            destination_stream.write(chunk)
            copied_hash.update(chunk)
        destination_stream.flush()
        os.fsync(destination_stream.fileno())
    except SecurityViolation:
        _unlink_partial_destination(destination)
        raise
    except OSError:
        _unlink_partial_destination(destination)
        raise _violation(
            "dataset_invalid",
            stage,
            "dataset could not be copied safely",
        ) from None
    finally:
        if source_stream is not None:
            source_stream.close()
        if destination_stream is not None:
            destination_stream.close()

    copied = FileDigest(
        sha256=copied_hash.hexdigest(),
        size_bytes=copied_size,
    )
    if copied.sha256 != expected_sha256 or copied.size_bytes != expected_size:
        _unlink_partial_destination(destination)
        raise _violation(
            "dataset_invalid",
            stage,
            "workspace dataset copy failed integrity validation",
        )

    destination_digest = file_sha256(
        destination,
        max_bytes=max_bytes,
        containment_root=root,
        stage=stage,
        invalid_code="dataset_invalid",
    )
    source_after = file_sha256(
        source_path,
        max_bytes=max_bytes,
        stage=stage,
        invalid_code="dataset_invalid",
    )
    if (
        destination_digest != copied
        or source_after != source_before
        or source_after.sha256 != expected_sha256
        or source_after.size_bytes != expected_size
    ):
        _unlink_partial_destination(destination)
        raise _violation(
            "dataset_invalid",
            stage,
            "dataset changed during staging",
        )
    return StagedFile(path=destination, digest=destination_digest)


class BoundedPipeBuffer:
    """Thread-safe retained-byte cap for a continuously drained pipe."""

    __slots__ = (
        "_data",
        "_error",
        "_finished",
        "_finished_event",
        "_limit",
        "_lock",
        "_total_bytes",
        "_truncated",
    )

    def __init__(self, limit: int) -> None:
        if type(limit) is not int or limit < 0:
            raise ValueError("pipe buffer limit must be a nonnegative integer")
        self._limit = limit
        self._data = bytearray()
        self._total_bytes = 0
        self._truncated = False
        self._finished = False
        self._error: str | None = None
        self._lock = threading.Lock()
        self._finished_event = threading.Event()

    @property
    def limit(self) -> int:
        return self._limit

    def feed(self, chunk: bytes | bytearray | memoryview) -> None:
        payload = bytes(chunk)
        if not payload:
            return
        with self._lock:
            if self._finished:
                raise RuntimeError("cannot feed a finished pipe buffer")
            self._total_bytes += len(payload)
            remaining = self._limit - len(self._data)
            if remaining > 0:
                self._data.extend(payload[:remaining])
            if len(payload) > max(remaining, 0):
                self._truncated = True

    def finish(self, error: BaseException | str | None = None) -> None:
        with self._lock:
            if self._finished:
                return
            if error is not None:
                self._error = (
                    error
                    if isinstance(error, str)
                    else error.__class__.__name__
                )
            self._finished = True
            self._finished_event.set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._finished_event.wait(timeout)

    def snapshot(self) -> PipeCapture:
        with self._lock:
            return PipeCapture(
                data=bytes(self._data),
                total_bytes=self._total_bytes,
                truncated=self._truncated,
                finished=self._finished,
                error=self._error,
            )


def drain_pipe(
    stream: BinaryIO,
    buffer: BoundedPipeBuffer,
    *,
    chunk_size: int = _PIPE_CHUNK_SIZE,
) -> None:
    """Drain ``stream`` to EOF while retaining at most ``buffer.limit`` bytes."""

    if type(chunk_size) is not int or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer")
    error: BaseException | None = None
    try:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            buffer.feed(chunk)
    except Exception as exc:
        error = exc
    finally:
        try:
            stream.close()
        except OSError as exc:
            error = error or exc
        buffer.finish(error)


def _replace_literal(
    text: str,
    value: str,
    *,
    case_insensitive: bool,
) -> str:
    if not value:
        return text
    if case_insensitive:
        return re.sub(re.escape(value), _REDACTED, text, flags=re.IGNORECASE)
    return text.replace(value, _REDACTED)


def redact_text(
    text: str,
    *,
    secrets: Iterable[str] = (),
    sensitive_paths: Iterable[str | os.PathLike[str]] = (),
) -> str:
    """Deterministically remove credentials and selected host paths."""

    if not isinstance(text, str):
        raise TypeError("redaction input must be text")
    redacted = text

    explicit_secrets = sorted(
        {
            value
            for value in secrets
            if isinstance(value, str) and len(value) >= 4
        },
        key=len,
        reverse=True,
    )
    for secret in explicit_secrets:
        redacted = _replace_literal(
            redacted,
            secret,
            case_insensitive=False,
        )

    path_forms: set[str] = set()
    sensitive_literals: set[str] = set()
    for raw_path in sensitive_paths:
        try:
            path = _absolute_lexical(raw_path)
        except (TypeError, ValueError, OSError):
            continue
        literal_forms = {str(path), path.as_posix()}
        try:
            literal_forms.add(path.as_uri())
        except ValueError:
            pass
        sensitive_literals.update(literal_forms)
        for literal in literal_forms:
            path_forms.add(literal)
            path_forms.add(literal.replace("\\", "\\\\"))
            path_forms.add(literal.replace("/", "\\/"))
            path_forms.add(json.dumps(literal, ensure_ascii=True)[1:-1])
            for safe_characters in ("", "/"):
                encoded = literal
                for _ in range(2):
                    encoded = quote(encoded, safe=safe_characters)
                    path_forms.add(encoded)
    for path_form in sorted(path_forms, key=len, reverse=True):
        redacted = _replace_literal(
            redacted,
            path_form,
            case_insensitive=os.name == "nt",
        )

    redacted = _PRIVATE_KEY_BLOCK.sub(_REDACTED, redacted)
    redacted = _BEARER_TOKEN.sub(f"Bearer {_REDACTED}", redacted)
    redacted = _OPENAI_STYLE_KEY.sub(_REDACTED, redacted)
    redacted = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{_REDACTED}",
        redacted,
    )
    redacted = _STANDALONE_SECRET.sub(_REDACTED, redacted)

    decoded_probe = redacted
    for _ in range(_MAX_REDACTION_DECODE_ROUNDS):
        decoded = unquote(decoded_probe)
        if decoded == decoded_probe:
            break
        decoded_probe = decoded
        comparable_probe = (
            decoded_probe.casefold() if os.name == "nt" else decoded_probe
        )
        if any(
            (
                literal.casefold() if os.name == "nt" else literal
            ) in comparable_probe
            for literal in sensitive_literals
        ):
            return _REDACTED
        if any(secret in decoded_probe for secret in explicit_secrets):
            return _REDACTED
        if (
            _PRIVATE_KEY_BLOCK.search(decoded_probe)
            or _BEARER_TOKEN.search(decoded_probe)
            or _OPENAI_STYLE_KEY.search(decoded_probe)
            or _SECRET_ASSIGNMENT.search(decoded_probe)
            or _STANDALONE_SECRET.search(decoded_probe)
        ):
            return _REDACTED
    else:
        return _REDACTED
    return redacted


def is_secret_environment_name(name: str) -> bool:
    """Return whether an environment key is credential-bearing by policy."""

    if not isinstance(name, str):
        return True
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    if normalized in _EXPLICIT_SECRET_ENVIRONMENT_NAMES:
        return True
    components = set(normalized.split("_"))
    if components & _SECRET_ENVIRONMENT_COMPONENTS:
        return True
    return normalized.endswith("_API_KEY") or normalized.endswith("_PRIVATE_KEY")


def is_reserved_environment_name(name: str) -> bool:
    """Reject variables that can replace runner or interpreter controls."""

    if not isinstance(name, str):
        return True
    normalized = name.upper()
    return (
        normalized in _RESERVED_ENVIRONMENT_NAMES
        or normalized.startswith(_RESERVED_ENVIRONMENT_PREFIXES)
    )


def build_minimal_environment(
    workspace: str | os.PathLike[str],
    allowed_names: Iterable[str],
    requested_variables: Mapping[str, str],
    *,
    parent_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build a small child environment without inheriting caller credentials."""

    workspace_path = ensure_secure_root(
        workspace,
        create=False,
        stage="environment",
    )
    temporary = ensure_secure_directory(
        workspace_path,
        "tmp",
        stage="environment",
    )
    source_environment = os.environ if parent_environment is None else parent_environment
    casefold_names = os.name == "nt"

    allowed_lookup: dict[str, str] = {}
    for raw_name in allowed_names:
        if not isinstance(raw_name, str) or _ENVIRONMENT_NAME.fullmatch(raw_name) is None:
            raise _violation(
                "policy_rejected",
                "environment",
                "environment allowlist contains an invalid name",
            )
        if is_secret_environment_name(raw_name):
            raise _violation(
                "policy_rejected",
                "environment",
                "credential-bearing environment names are forbidden",
            )
        if is_reserved_environment_name(raw_name):
            raise _violation(
                "policy_rejected",
                "environment",
                "runner-controlled environment names are forbidden",
            )
        lookup = raw_name.casefold() if casefold_names else raw_name
        if lookup in allowed_lookup:
            raise _violation(
                "policy_rejected",
                "environment",
                "environment allowlist contains duplicate names",
            )
        allowed_lookup[lookup] = raw_name

    result = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
        "TEMP": str(temporary),
        "TMP": str(temporary),
    }
    if os.name == "nt":
        parent_lookup = {
            key.casefold(): value
            for key, value in source_environment.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        for platform_name in ("SYSTEMROOT", "WINDIR"):
            platform_value = parent_lookup.get(platform_name.casefold())
            if platform_value:
                result[platform_name] = platform_value

    if not isinstance(requested_variables, Mapping):
        raise _violation(
            "policy_rejected",
            "environment",
            "requested environment must be a mapping",
        )
    for raw_name, raw_value in requested_variables.items():
        if (
            not isinstance(raw_name, str)
            or _ENVIRONMENT_NAME.fullmatch(raw_name) is None
            or not isinstance(raw_value, str)
            or "\x00" in raw_value
            or is_reserved_environment_name(raw_name)
        ):
            raise _violation(
                "policy_rejected",
                "environment",
                "requested environment contains an invalid entry",
            )
        lookup = raw_name.casefold() if casefold_names else raw_name
        if lookup not in allowed_lookup or is_secret_environment_name(raw_name):
            raise _violation(
                "policy_rejected",
                "environment",
                "requested environment variable is not allowed",
            )
        result[allowed_lookup[lookup]] = raw_value
    return dict(sorted(result.items()))


def _remove_entry_no_follow(path: Path) -> None:
    details = path.lstat()
    if _is_indirection(path, details):
        if _is_junction(path) or stat.S_ISDIR(details.st_mode):
            os.rmdir(path)
        else:
            path.unlink()
        return
    if stat.S_ISDIR(details.st_mode):
        if os.path.ismount(path):
            raise OSError("refusing to cross a mounted directory")
        with os.scandir(path) as entries:
            children = [Path(entry.path) for entry in entries]
        for child in children:
            _remove_entry_no_follow(child)
        path.rmdir()
        return
    path.unlink()


def safe_cleanup_workspace(
    managed_root: str | os.PathLike[str],
    workspace: str | os.PathLike[str],
) -> None:
    """Remove only one managed workspace without following links or junctions."""

    root = ensure_secure_root(managed_root, create=False, stage="cleanup")
    workspace_path = _absolute_lexical(workspace)
    try:
        relative = workspace_path.relative_to(root)
    except ValueError:
        raise _violation(
            "cleanup_failed",
            "cleanup",
            "cleanup target is outside the managed root",
        ) from None
    if not relative.parts or workspace_path == root:
        raise _violation(
            "cleanup_failed",
            "cleanup",
            "managed root itself cannot be cleaned as a workspace",
        )

    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if not _lexists(current):
            return
        _assert_path_entry_safe(
            current,
            stage="cleanup",
            symlink_code="cleanup_failed",
        )
    if not _lexists(workspace_path):
        return
    try:
        _remove_entry_no_follow(workspace_path)
    except OSError:
        raise _violation(
            "cleanup_failed",
            "cleanup",
            "workspace cleanup failed",
        ) from None
