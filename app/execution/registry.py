"""Trusted entrypoint registration for the controlled local runner.

Only host code may associate an opaque entrypoint ID with a Python script.
Execution requests select that ID; they never select an executable or script
path themselves.
"""

from __future__ import annotations

import os
import re
import stat
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from app.contracts.execution import EntrypointClass

from .security import is_reserved_environment_name

__all__ = ["EntrypointRegistry"]


_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_SECRET_ENVIRONMENT_COMPONENTS = frozenset(
    {
        "authorization",
        "bearer",
        "credential",
        "password",
        "secret",
        "token",
    }
)
_SECRET_ENVIRONMENT_PAIRS = frozenset(
    {
        ("access", "key"),
        ("access", "token"),
        ("api", "key"),
        ("auth", "token"),
        ("client", "secret"),
        ("private", "key"),
    }
)
_PYTHON_ARGUMENTS = ("-X", "utf8")


@dataclass(frozen=True, slots=True)
class _EntrypointRegistration:
    """Immutable command material produced only by the trusted registry."""

    entrypoint_id: str
    executable: Path
    script_path: Path
    entrypoint_class: EntrypointClass
    allowed_environment: tuple[str, ...]
    interpreter_arguments: tuple[str, ...] = _PYTHON_ARGUMENTS


def _validate_entrypoint_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("entrypoint ID must be a string")
    if "\x00" in value or not value.strip():
        raise ValueError("entrypoint ID must be non-empty")
    if value != value.strip() or len(value) > 256:
        raise ValueError("entrypoint ID is not allowed")
    return value


def _is_secret_environment_name(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    components = tuple(part for part in normalized.split("_") if part)
    if any(part in _SECRET_ENVIRONMENT_COMPONENTS for part in components):
        return True
    return any(
        pair in _SECRET_ENVIRONMENT_PAIRS
        for pair in zip(components, components[1:], strict=False)
    )


def _normalize_allowed_environment(value: Iterable[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError("allowed environment must be a collection of names")
    try:
        names = tuple(value)
    except TypeError as exc:
        raise ValueError(
            "allowed environment must be a collection of names"
        ) from exc

    normalized: dict[str, str] = {}
    for raw_name in names:
        if not isinstance(raw_name, str):
            raise ValueError("allowed environment names must be strings")
        if (
            not raw_name
            or raw_name != raw_name.strip()
            or len(raw_name) > 256
            or _ENVIRONMENT_NAME.fullmatch(raw_name) is None
        ):
            raise ValueError("allowed environment name is invalid")
        if _is_secret_environment_name(raw_name):
            raise ValueError("secret-bearing environment names are not allowed")
        if is_reserved_environment_name(raw_name):
            raise ValueError("runner-controlled environment names are not allowed")
        normalized.setdefault(raw_name.casefold(), raw_name)
    return tuple(sorted(normalized.values(), key=lambda item: (item.casefold(), item)))


def _is_reparse_component(path: Path, path_stat: os.stat_result) -> bool:
    if stat.S_ISLNK(path_stat.st_mode):
        return True

    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None:
        try:
            if is_junction():
                return True
        except OSError:
            return True

    file_attributes = getattr(path_stat, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_attribute and file_attributes & reparse_attribute)


def _assert_no_reparse_components(path: Path) -> os.stat_result:
    target_stat: os.stat_result | None = None
    for component in reversed((path, *path.parents)):
        try:
            component_stat = component.lstat()
        except OSError:
            raise ValueError("Python entrypoint script does not exist") from None
        if _is_reparse_component(component, component_stat):
            raise ValueError(
                "Python entrypoint script cannot use a symlink or junction"
            )
        if component == path:
            target_stat = component_stat

    if target_stat is None:
        raise ValueError("Python entrypoint script cannot be inspected")
    return target_stat


def _trusted_python_executable() -> Path:
    if not sys.executable or "\x00" in sys.executable:
        raise RuntimeError("trusted Python executable is unavailable")
    try:
        executable = Path(sys.executable).resolve(strict=True)
        executable_stat = executable.stat()
    except OSError:
        raise RuntimeError("trusted Python executable is unavailable") from None
    if not executable.is_absolute() or not stat.S_ISREG(executable_stat.st_mode):
        raise RuntimeError("trusted Python executable is unavailable")
    return executable


def _validate_python_script(script_path: os.PathLike[str] | str) -> Path:
    try:
        raw_path = os.fspath(script_path)
    except TypeError as exc:
        raise ValueError("Python entrypoint script path is invalid") from exc
    if not isinstance(raw_path, str) or "\x00" in raw_path or not raw_path:
        raise ValueError("Python entrypoint script path is invalid")

    candidate = Path(raw_path)
    if candidate.suffix.casefold() != ".py":
        raise ValueError("Python entrypoint scripts must use the .py suffix")
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    target_stat = _assert_no_reparse_components(candidate)
    if not stat.S_ISREG(target_stat.st_mode):
        raise ValueError("Python entrypoint script must be a regular file")
    try:
        resolved = candidate.resolve(strict=True)
        resolved_stat = resolved.stat()
    except OSError:
        raise ValueError("Python entrypoint script cannot be inspected") from None
    if not resolved.is_absolute() or not stat.S_ISREG(resolved_stat.st_mode):
        raise ValueError("Python entrypoint script must be a regular file")
    return resolved


class EntrypointRegistry:
    """Explicit, instance-local allowlist of trusted Python entrypoints."""

    def __init__(self) -> None:
        self._registrations: dict[str, _EntrypointRegistration] = {}
        self._lock = RLock()

    def register_python(
        self,
        entrypoint_id: str,
        script_path: os.PathLike[str] | str,
        *,
        entrypoint_class: EntrypointClass = "test",
        allowed_environment: Iterable[str] = (),
    ) -> None:
        """Register a trusted regular Python file under an opaque ID."""

        normalized_id = _validate_entrypoint_id(entrypoint_id)
        if (
            not isinstance(entrypoint_class, str)
            or entrypoint_class not in {"scientific", "test"}
        ):
            raise ValueError("entrypoint class is not allowed")

        with self._lock:
            if normalized_id in self._registrations:
                raise ValueError("entrypoint ID is already registered")

        registration = _EntrypointRegistration(
            entrypoint_id=normalized_id,
            executable=_trusted_python_executable(),
            script_path=_validate_python_script(script_path),
            entrypoint_class=entrypoint_class,
            allowed_environment=_normalize_allowed_environment(
                allowed_environment
            ),
        )
        with self._lock:
            if normalized_id in self._registrations:
                raise ValueError("entrypoint ID is already registered")
            self._registrations[normalized_id] = registration

    def resolve(self, entrypoint_id: str) -> _EntrypointRegistration:
        """Resolve a registered ID without exposing mutable registry state."""

        normalized_id = _validate_entrypoint_id(entrypoint_id)
        with self._lock:
            try:
                return self._registrations[normalized_id]
            except KeyError:
                raise KeyError("entrypoint is not registered") from None
