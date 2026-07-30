"""Bounded, offline provenance helpers for controlled local execution.

The helpers in this module inspect only an explicit dependency allowlist and
the local Git worktree.  They never enumerate all installed distributions,
contact package indexes, or invoke network-facing Git operations.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import platform as platform_module
import re
import shutil
import struct
import subprocess
import sys
import threading
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import BinaryIO, Final

from app.contracts.execution import EnvironmentFingerprint

DependencyVersionProvider = Callable[[tuple[str, ...]], Mapping[str, str]]
GitProvenanceProvider = Callable[[], Mapping[str, object]]

__all__ = [
    "DependencyProvenanceError",
    "DependencyVersionProvider",
    "GitProvenanceError",
    "GitProvenanceProvider",
    "ProvenanceError",
    "build_environment_fingerprint",
    "collect_dependency_versions",
    "collect_git_provenance",
]


_MAX_DEPENDENCIES: Final = 128
_MAX_DEPENDENCY_NAME_LENGTH: Final = 256
_MAX_VERSION_LENGTH: Final = 512
_GIT_TIMEOUT_SECONDS: Final = 3.0
_MAX_GIT_SHA_OUTPUT_BYTES: Final = 128
_MAX_GIT_PATH_STATUS_BYTES: Final = 4_096
_GIT_SHA_PATTERN: Final = re.compile(r"[0-9a-f]{40}\Z")
_DRIVE_PREFIX_PATTERN: Final = re.compile(r"[A-Za-z]:")


class ProvenanceError(RuntimeError):
    """Base class for controlled provenance collection failures."""


class DependencyProvenanceError(ProvenanceError):
    """Dependency evidence is missing, invalid, or could not be collected."""


class GitProvenanceError(ProvenanceError):
    """Injected Git evidence is missing, invalid, or could not be collected."""


def _normalize_dependency_names(names: Iterable[str]) -> tuple[str, ...]:
    if isinstance(names, (str, bytes)):
        raise DependencyProvenanceError(
            "dependency allowlist must be an iterable of names"
        )

    bounded: list[str] = []
    try:
        iterator = iter(names)
    except TypeError:
        raise DependencyProvenanceError(
            "dependency allowlist must be iterable"
        ) from None

    for _index in range(_MAX_DEPENDENCIES + 1):
        try:
            raw_name = next(iterator)
        except StopIteration:
            break
        except Exception:
            raise DependencyProvenanceError(
                "dependency allowlist iteration failed"
            ) from None
        if len(bounded) == _MAX_DEPENDENCIES:
            raise DependencyProvenanceError(
                "dependency allowlist exceeds the bounded collection limit"
            )
        if not isinstance(raw_name, str):
            raise DependencyProvenanceError(
                "dependency allowlist entries must be strings"
            )
        if (
            not raw_name
            or raw_name != raw_name.strip()
            or len(raw_name) > _MAX_DEPENDENCY_NAME_LENGTH
            or any(character in raw_name for character in ("\x00", "\r", "\n"))
            or "/" in raw_name
            or "\\" in raw_name
            or ":" in raw_name
        ):
            raise DependencyProvenanceError(
                "dependency allowlist contains an invalid name"
            )
        bounded.append(raw_name)

    if len(bounded) != len(set(bounded)):
        raise DependencyProvenanceError(
            "dependency allowlist entries must be unique"
        )
    return tuple(sorted(bounded))


def _validate_dependency_version(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > _MAX_VERSION_LENGTH
        or any(character in value for character in ("\x00", "\r", "\n"))
    ):
        raise DependencyProvenanceError(
            f"dependency version is missing or invalid for {name!r}"
        )

    normalized = value.replace("\\", "/")
    if (
        normalized.startswith("/")
        or _DRIVE_PREFIX_PATTERN.match(value) is not None
        or value.casefold().startswith("file:")
    ):
        raise DependencyProvenanceError(
            f"dependency version is unsafe for {name!r}"
        )
    return value


def _stdlib_dependency_versions(names: tuple[str, ...]) -> Mapping[str, str]:
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            raise DependencyProvenanceError(
                f"dependency version is unavailable for {name!r}"
            ) from None
        except Exception:
            raise DependencyProvenanceError(
                f"dependency version lookup failed for {name!r}"
            ) from None
    return versions


def collect_dependency_versions(
    names: Iterable[str],
    provider: DependencyVersionProvider | None = None,
) -> dict[str, str]:
    """Collect versions for only the sorted, bounded dependency allowlist.

    Provider output is accessed by allowlisted key instead of enumerated, so
    extra provider entries are ignored and cannot enter persisted evidence.
    """

    normalized_names = _normalize_dependency_names(names)
    if not normalized_names:
        return {}

    if provider is None:
        raw_versions = _stdlib_dependency_versions(normalized_names)
    else:
        try:
            raw_versions = provider(normalized_names)
        except ProvenanceError:
            raise
        except Exception:
            raise DependencyProvenanceError(
                "dependency version provider failed"
            ) from None

    if not isinstance(raw_versions, Mapping):
        raise DependencyProvenanceError(
            "dependency version provider must return a mapping"
        )

    collected: dict[str, str] = {}
    for name in normalized_names:
        try:
            value = raw_versions[name]
        except (KeyError, TypeError):
            raise DependencyProvenanceError(
                f"dependency version is unavailable for {name!r}"
            ) from None
        except ProvenanceError:
            raise
        except Exception:
            raise DependencyProvenanceError(
                f"dependency version lookup failed for {name!r}"
            ) from None
        collected[name] = _validate_dependency_version(name, value)
    return collected


def _unavailable_git_provenance() -> dict[str, object]:
    return {
        "commit_sha": None,
        "dirty": False,
        "available": False,
    }


def _run_local_git(
    executable: str,
    repository: Path,
    arguments: tuple[str, ...],
    *,
    capture_stdout: bool,
) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(
            [executable, "-C", str(repository), *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            shell=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _local_git_is_dirty(
    executable: str,
    repository: Path,
) -> bool | None:
    """Return dirty state while concurrently draining unretained status data."""

    process: subprocess.Popen[bytes] | None = None
    reader: threading.Thread | None = None
    dirty_seen = threading.Event()
    reader_failed = threading.Event()

    def drain_status(stream: BinaryIO) -> None:
        try:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                dirty_seen.set()
        except (OSError, ValueError):
            reader_failed.set()
        finally:
            try:
                stream.close()
            except OSError:
                reader_failed.set()

    try:
        process = subprocess.Popen(
            [
                executable,
                "-C",
                str(repository),
                "status",
                "--porcelain=v1",
                "--untracked-files=normal",
                "--ignore-submodules=all",
                "--no-renames",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
        if process.stdout is None:
            return None
        reader = threading.Thread(
            target=drain_status,
            args=(process.stdout,),
            name="git-status-drain",
            daemon=True,
        )
        reader.start()
        process.wait(timeout=_GIT_TIMEOUT_SECONDS)
        reader.join(timeout=_GIT_TIMEOUT_SECONDS)
        if (
            process.returncode != 0
            or reader.is_alive()
            or reader_failed.is_set()
        ):
            return None
        return dirty_seen.is_set()
    except (OSError, subprocess.SubprocessError):
        if process is not None and process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=_GIT_TIMEOUT_SECONDS)
            except (OSError, subprocess.SubprocessError):
                pass
        return None
    finally:
        if reader is not None and reader.is_alive():
            if process is not None and process.stdout is not None:
                try:
                    process.stdout.close()
                except OSError:
                    pass
            reader.join(timeout=_GIT_TIMEOUT_SECONDS)
        elif process is not None and process.stdout is not None:
            try:
                process.stdout.close()
            except OSError:
                pass


def _local_git_path_is_tracked_and_clean(
    executable: str,
    repository: Path,
    required_path: Path,
) -> bool:
    """Bind provenance to one clean, tracked entrypoint using Git status."""

    try:
        resolved_repository = repository.resolve(strict=True)
        resolved_path = required_path.resolve(strict=True)
        relative_path = resolved_path.relative_to(resolved_repository)
    except (OSError, ValueError):
        return False
    if not resolved_path.is_file():
        return False

    status = _run_local_git(
        executable,
        resolved_repository,
        (
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignored=matching",
            "--ignore-submodules=all",
            "--no-renames",
            "--",
            relative_path.as_posix(),
        ),
        capture_stdout=True,
    )
    return (
        status is not None
        and status.returncode == 0
        and len(status.stdout) <= _MAX_GIT_PATH_STATUS_BYTES
        and status.stdout == b""
    )


def _stdlib_git_provenance(
    repository_root: str | Path | None,
    required_tracked_path: str | Path | None = None,
) -> Mapping[str, object]:
    executable = shutil.which("git")
    if executable is None:
        return _unavailable_git_provenance()

    try:
        repository = (
            Path.cwd() if repository_root is None else Path(repository_root)
        )
    except (OSError, TypeError, ValueError):
        return _unavailable_git_provenance()
    if not repository.is_dir():
        return _unavailable_git_provenance()

    revision = _run_local_git(
        executable,
        repository,
        ("rev-parse", "--verify", "HEAD^{commit}"),
        capture_stdout=True,
    )
    if (
        revision is None
        or revision.returncode != 0
        or len(revision.stdout) > _MAX_GIT_SHA_OUTPUT_BYTES
    ):
        return _unavailable_git_provenance()
    try:
        commit_sha = revision.stdout.decode("ascii").strip()
    except UnicodeDecodeError:
        return _unavailable_git_provenance()
    if _GIT_SHA_PATTERN.fullmatch(commit_sha) is None:
        return _unavailable_git_provenance()

    dirty = _local_git_is_dirty(executable, repository)
    if dirty is None:
        return _unavailable_git_provenance()
    if (
        required_tracked_path is not None
        and not _local_git_path_is_tracked_and_clean(
            executable,
            repository,
            Path(required_tracked_path),
        )
    ):
        return _unavailable_git_provenance()
    return {
        "commit_sha": commit_sha,
        "dirty": dirty,
        "available": True,
    }


def _normalize_git_provenance(payload: object) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise GitProvenanceError(
            "Git provenance provider must return a mapping"
        )
    try:
        commit_sha = payload["commit_sha"]
        dirty = payload["dirty"]
        available = payload["available"]
    except (KeyError, TypeError):
        raise GitProvenanceError(
            "Git provenance provider returned incomplete evidence"
        ) from None
    except ProvenanceError:
        raise
    except Exception:
        raise GitProvenanceError(
            "Git provenance provider evidence could not be read"
        ) from None

    if type(available) is not bool or type(dirty) is not bool:
        raise GitProvenanceError(
            "Git availability and dirty state must be strict booleans"
        )
    if available:
        if (
            not isinstance(commit_sha, str)
            or _GIT_SHA_PATTERN.fullmatch(commit_sha) is None
        ):
            raise GitProvenanceError(
                "available Git provenance requires a canonical commit SHA"
            )
    elif commit_sha is not None or dirty:
        raise GitProvenanceError(
            "unavailable Git provenance cannot claim repository state"
        )

    return {
        "commit_sha": commit_sha,
        "dirty": dirty,
        "available": available,
    }


def collect_git_provenance(
    provider: GitProvenanceProvider | None = None,
    *,
    repository_root: str | Path | None = None,
    required_tracked_path: str | Path | None = None,
) -> dict[str, object]:
    """Collect and strictly normalize bounded local or injected Git evidence."""

    if provider is None:
        raw_provenance = _stdlib_git_provenance(
            repository_root,
            required_tracked_path,
        )
    else:
        try:
            raw_provenance = provider()
        except ProvenanceError:
            raise
        except Exception:
            raise GitProvenanceError("Git provenance provider failed") from None
    return _normalize_git_provenance(raw_provenance)


def build_environment_fingerprint(
    seed: int,
    dependency_names: Iterable[str] = (),
    *,
    dependency_version_provider: DependencyVersionProvider | None = None,
    git_provenance_provider: GitProvenanceProvider | None = None,
    repository_root: str | Path | None = None,
    required_tracked_path: str | Path | None = None,
) -> EnvironmentFingerprint:
    """Build a validated environment fingerprint without broad enumeration."""

    dependency_versions = collect_dependency_versions(
        dependency_names,
        provider=dependency_version_provider,
    )
    git_provenance = collect_git_provenance(
        git_provenance_provider,
        repository_root=repository_root,
        required_tracked_path=required_tracked_path,
    )

    architecture = platform_module.machine().strip()
    if not architecture:
        architecture = f"{struct.calcsize('P') * 8}-bit"
    release = platform_module.release().strip()
    platform_name = sys.platform if not release else f"{sys.platform}-{release}"

    return EnvironmentFingerprint(
        python_version=platform_module.python_version(),
        python_implementation=platform_module.python_implementation(),
        platform=platform_name,
        architecture=architecture,
        dependency_versions=dependency_versions,
        git_sha=git_provenance["commit_sha"],
        git_dirty=git_provenance["dirty"],
        git_available=git_provenance["available"],
        seed=seed,
    )
