"""Pinned, offline-first dataset acquisition for controlled executions.

The default catalogue records only an independently verified WDBC digest and
exact byte count.  Formal resolution remains fail-closed for unpinned custom
definitions.
"""

from __future__ import annotations

import csv
import hashlib
import math
import os
import re
import stat
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from app.contracts.execution import DatasetManifest


WDBC_DATASET_ID = "uci-wdbc-diagnostic-17-1995-10-31"

_WDBC_SOURCE_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases/"
    "breast-cancer-wisconsin/wdbc.data"
)
_WDBC_SOURCE_PATH = urlsplit(_WDBC_SOURCE_URL).path
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SECRET_QUERY_NAMES = frozenset(
    {"access_token", "api_key", "apikey", "auth", "key", "password", "secret", "token"}
)
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_ARCHIVE_PREFIXES = (
    b"PK\x03\x04",
    b"\x1f\x8b\x08",
    b"7z\xbc\xaf\x27\x1c",
    b"\xfd7zXZ\x00",
    b"BZh",
)
_WINDOWS_REPARSE_ATTRIBUTE = 0x400


class DatasetAdapterError(Exception):
    """A stable, path-redacted error returned by the dataset boundary."""

    def __init__(
        self,
        code: str,
        stage: str,
        retryable: bool,
        message: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        self.code = code
        self.stage = stage
        self.retryable = retryable
        self.message = message
        self._cause = cause
        super().__init__(message)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return (
            "DatasetAdapterError("
            f"code={self.code!r}, stage={self.stage!r}, "
            f"retryable={self.retryable!r}, message={self.message!r})"
        )


def _error(
    code: str,
    stage: str,
    retryable: bool,
    message: str,
    cause: BaseException | None = None,
) -> DatasetAdapterError:
    return DatasetAdapterError(
        code,
        stage,
        retryable,
        message,
        cause=cause,
    )


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalise_host(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(
            "dataset_url_forbidden",
            "definition",
            False,
            "Dataset host policy is invalid.",
        )
    host = value.strip().rstrip(".").casefold()
    if any(character in host for character in "/\\:@?#"):
        raise _error(
            "dataset_url_forbidden",
            "definition",
            False,
            "Dataset host policy is invalid.",
        )
    return host


def _validate_https_url(
    value: object,
    *,
    allowed_hosts: frozenset[str] | None = None,
    exact_source_path: bool = False,
) -> str:
    if not isinstance(value, str):
        raise _error(
            "dataset_url_forbidden",
            "definition",
            False,
            "Dataset URL is invalid.",
        )
    parsed = urlsplit(value)
    if parsed.scheme.casefold() != "https":
        raise _error(
            "dataset_tls_required",
            "definition",
            False,
            "Dataset URLs require HTTPS.",
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise _error(
            "dataset_url_forbidden",
            "definition",
            False,
            "Dataset URL is invalid.",
            exc,
        ) from None
    host = (parsed.hostname or "").rstrip(".").casefold()
    query_names = {name.casefold() for name, _separator, _value in (
        component.partition("=") for component in parsed.query.split("&") if component
    )}
    if (
        not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.fragment
        or parsed.query
        or query_names.intersection(_SECRET_QUERY_NAMES)
        or (allowed_hosts is not None and host not in allowed_hosts)
        or (exact_source_path and parsed.path != _WDBC_SOURCE_PATH)
    ):
        raise _error(
            "dataset_url_forbidden",
            "definition",
            False,
            "Dataset URL is not permitted.",
        )
    return value


def _validate_relative_path(value: object, *, filename: bool = False) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("dataset path must be nonblank")
    if ":" in value or value.startswith(("\\\\", "//")):
        raise ValueError("dataset path must be relative")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("dataset path must be contained")
    if filename and (len(path.parts) != 1 or path.name in {"", ".", ".."}):
        raise ValueError("dataset filename must be a single name")
    return value


@dataclass(frozen=True, slots=True)
class DatasetDefinition:
    dataset_id: str
    official_name: str
    publisher: str
    version: str
    source_url: str
    allowed_source_hosts: frozenset[str]
    allowed_redirect_hosts: frozenset[str]
    target_filename: str
    cache_relative_dir: str
    license_id: str
    license_url: str
    citation: str
    doi: str
    expected_sha256: str | None
    expected_size_bytes: int | None
    max_download_bytes: int
    expected_rows: int
    expected_columns: int
    feature_count: int
    allowed_labels: frozenset[str]
    allowed_content_types: frozenset[str]
    allow_missing_content_type_for_exact_url: bool
    archive_policy: str

    def __post_init__(self) -> None:
        if not _nonblank(self.dataset_id) or not _IDENTIFIER.fullmatch(self.dataset_id):
            raise ValueError("dataset_id is invalid")
        for field_name in ("official_name", "publisher", "version", "doi"):
            if not _nonblank(getattr(self, field_name)):
                raise ValueError(f"{field_name} is required")
        if not all(
            _nonblank(value)
            for value in (self.license_id, self.license_url, self.citation)
        ):
            raise _error(
                "dataset_license_missing",
                "definition",
                False,
                "Dataset license provenance is incomplete.",
            )

        source_hosts = frozenset(_normalise_host(item) for item in self.allowed_source_hosts)
        redirect_hosts = frozenset(
            _normalise_host(item) for item in self.allowed_redirect_hosts
        )
        labels = frozenset(str(item) for item in self.allowed_labels)
        content_types = frozenset(
            str(item).strip().casefold() for item in self.allowed_content_types
        )
        object.__setattr__(self, "allowed_source_hosts", source_hosts)
        object.__setattr__(self, "allowed_redirect_hosts", redirect_hosts)
        object.__setattr__(self, "allowed_labels", labels)
        object.__setattr__(self, "allowed_content_types", content_types)

        _validate_https_url(
            self.source_url,
            allowed_hosts=source_hosts,
            exact_source_path=True,
        )
        _validate_https_url(self.license_url)
        _validate_relative_path(self.target_filename, filename=True)
        _validate_relative_path(self.cache_relative_dir)
        if self.expected_sha256 is not None and not _HEX64.fullmatch(
            self.expected_sha256
        ):
            raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")
        if (
            self.expected_size_bytes is not None
            and (
                isinstance(self.expected_size_bytes, bool)
                or self.expected_size_bytes < 0
            )
        ):
            raise ValueError("expected_size_bytes must be nonnegative")
        for field_name in (
            "max_download_bytes",
            "expected_rows",
            "expected_columns",
            "feature_count",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.expected_columns != self.feature_count + 2:
            raise ValueError("dataset dimensions are inconsistent")
        if not labels or not content_types:
            raise ValueError("dataset schema policy is incomplete")
        if self.archive_policy != "reject":
            raise ValueError("archive policy must reject archives")

    @property
    def is_pinned(self) -> bool:
        return self.expected_sha256 is not None and self.expected_size_bytes is not None


class DatasetRegistry:
    """Immutable lookup table for host-owned dataset definitions."""

    def __init__(self, definitions: Iterable[DatasetDefinition]) -> None:
        collected: dict[str, DatasetDefinition] = {}
        for definition in definitions:
            if not isinstance(definition, DatasetDefinition):
                raise TypeError("registry entries must be DatasetDefinition instances")
            if definition.dataset_id in collected:
                raise ValueError("duplicate dataset identifier")
            collected[definition.dataset_id] = definition
        self._definitions: Mapping[str, DatasetDefinition] = MappingProxyType(collected)

    def get(self, dataset_id: str) -> DatasetDefinition:
        try:
            return self._definitions[dataset_id]
        except (KeyError, TypeError):
            raise _error(
                "dataset_unknown",
                "registry",
                False,
                "Dataset identifier is not registered.",
            ) from None

    def ids(self) -> tuple[str, ...]:
        return tuple(self._definitions)


@dataclass(frozen=True, slots=True)
class DatasetValidationReport:
    row_count: int
    column_count: int
    feature_count: int
    unique_id_count: int
    labels: tuple[str, ...]
    finite_feature_values: bool
    missing_value_count: int
    duplicate_id_count: int
    schema_valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, repr=False)
class DatasetPinCandidate:
    dataset_id: str
    version: str
    source_url: str
    candidate_path: Path
    computed_sha256: str
    size_bytes: int
    validation_report: DatasetValidationReport
    formal_use_allowed: bool = False
    cache_installed: bool = False
    warnings: tuple[str, ...] = ()

    def public_summary(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "dataset_id": self.dataset_id,
                "version": self.version,
                "source_url": self.source_url,
                "computed_sha256": self.computed_sha256,
                "size_bytes": self.size_bytes,
                "validation_report": self.validation_report,
                "formal_use_allowed": False,
                "cache_installed": False,
                "warnings": self.warnings,
            }
        )

    def __repr__(self) -> str:
        return (
            "DatasetPinCandidate("
            f"dataset_id={self.dataset_id!r}, version={self.version!r}, "
            f"computed_sha256={self.computed_sha256!r}, "
            f"size_bytes={self.size_bytes!r}, formal_use_allowed=False, "
            "cache_installed=False)"
        )


@dataclass(frozen=True, slots=True, repr=False)
class ResolvedDataset:
    dataset_id: str
    version: str
    source_url: str
    cache_path: Path
    sha256: str
    size_bytes: int
    validation_report: DatasetValidationReport
    cache_hit: bool
    offline: bool
    warnings: tuple[str, ...]
    resolved_at: str
    _license_id: str
    _workspace_relative_path: str

    def to_dataset_manifest(self) -> DatasetManifest:
        return DatasetManifest(
            schema_version="1.0",
            dataset_id=self.dataset_id,
            source_uri=self.source_url,
            license=self._license_id,
            version=self.version,
            sha256=self.sha256,
            size_bytes=self.size_bytes,
            workspace_relative_path=self._workspace_relative_path,
        )

    def __repr__(self) -> str:
        return (
            "ResolvedDataset("
            f"dataset_id={self.dataset_id!r}, version={self.version!r}, "
            f"sha256={self.sha256!r}, size_bytes={self.size_bytes!r}, "
            f"cache_hit={self.cache_hit!r}, offline={self.offline!r})"
        )


def _default_wdbc_definition() -> DatasetDefinition:
    return DatasetDefinition(
        dataset_id=WDBC_DATASET_ID,
        official_name="Breast Cancer Wisconsin (Diagnostic)",
        publisher="UCI Machine Learning Repository",
        version="1995-10-31",
        source_url=_WDBC_SOURCE_URL,
        allowed_source_hosts=frozenset({"archive.ics.uci.edu"}),
        allowed_redirect_hosts=frozenset({"archive.ics.uci.edu"}),
        target_filename="wdbc.data",
        cache_relative_dir="datasets/uci-wdbc-v1995-10-31",
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        citation="Wolberg, Street, and Mangasarian; WDBC (1995).",
        doi="10.24432/C5DW2B",
        expected_sha256="d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a",
        expected_size_bytes=124103,
        max_download_bytes=1024 * 1024,
        expected_rows=569,
        expected_columns=32,
        feature_count=30,
        allowed_labels=frozenset({"M", "B"}),
        allowed_content_types=frozenset(
            {"text/plain", "text/csv", "application/octet-stream"}
        ),
        allow_missing_content_type_for_exact_url=True,
        archive_policy="reject",
    )


def get_default_dataset_registry() -> DatasetRegistry:
    return DatasetRegistry((_default_wdbc_definition(),))


def _is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        junction_check = getattr(os.path, "isjunction", None)
        if junction_check is not None and junction_check(path):
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & _WINDOWS_REPARSE_ATTRIBUTE)
    except OSError:
        return True


def _ensure_contained(root: Path, candidate: Path) -> None:
    try:
        root_resolved = root.resolve(strict=False)
        candidate_resolved = candidate.resolve(strict=False)
        candidate_resolved.relative_to(root_resolved)
    except (OSError, RuntimeError, ValueError):
        raise _error(
            "dataset_cache_corrupt",
            "cache",
            False,
            "Dataset cache path is unsafe.",
        ) from None


def _ensure_lock_contained(root: Path, lock_path: Path) -> None:
    try:
        _ensure_contained(root, lock_path)
    except DatasetAdapterError as exc:
        raise _error(
            "dataset_concurrent_fetch",
            "lock",
            True,
            "Dataset fetch lock is unavailable.",
            exc,
        ) from None


def _prepare_directory(root: Path, relative_directory: str) -> tuple[Path, Path]:
    try:
        root = Path(root)
        if root.exists() and (not root.is_dir() or _is_reparse(root)):
            raise OSError("unsafe root")
        root.mkdir(parents=True, exist_ok=True)
        current = root
        for part in Path(relative_directory).parts:
            current = current / part
            if current.exists() and (not current.is_dir() or _is_reparse(current)):
                raise OSError("unsafe cache directory")
            current.mkdir(exist_ok=True)
        _ensure_contained(root, current)
        return root, current
    except DatasetAdapterError:
        raise
    except (OSError, RuntimeError) as exc:
        raise _error(
            "dataset_io_error",
            "io",
            False,
            "Dataset cache directory could not be prepared.",
            exc,
        ) from None


def _safe_regular_file(path: Path, root: Path) -> bool:
    _ensure_contained(root, path)
    try:
        if not path.exists():
            return False
        if _is_reparse(path):
            return False
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    try:
        with path.open("rb") as source:
            while True:
                chunk = source.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise _error(
            "dataset_io_error",
            "io",
            False,
            "Dataset bytes could not be read.",
            exc,
        ) from None
    return digest.hexdigest(), total


def _validate_wdbc_schema(
    path: Path,
    definition: DatasetDefinition,
) -> DatasetValidationReport:
    identifiers: set[str] = set()
    labels: set[str] = set()
    row_count = 0
    duplicate_count = 0
    missing_count = 0
    observed_columns = 0
    errors: list[str] = []
    finite = True
    try:
        with path.open("r", encoding="utf-8", errors="strict", newline="") as source:
            reader = csv.reader(source)
            for row in reader:
                row_count += 1
                observed_columns = max(observed_columns, len(row))
                if len(row) != definition.expected_columns:
                    errors.append("column_count")
                    continue
                identifier = row[0]
                label = row[1]
                if not identifier or not identifier.isdigit():
                    errors.append("identifier")
                elif identifier in identifiers:
                    duplicate_count += 1
                    errors.append("duplicate_identifier")
                else:
                    identifiers.add(identifier)
                if not label:
                    missing_count += 1
                    errors.append("label")
                elif label not in definition.allowed_labels:
                    errors.append("label")
                else:
                    labels.add(label)
                for value in row[2:]:
                    if not value:
                        missing_count += 1
                        errors.append("feature")
                        continue
                    if value.casefold() in {"true", "false"}:
                        finite = False
                        errors.append("feature")
                        continue
                    try:
                        numeric = float(value)
                    except ValueError:
                        finite = False
                        errors.append("feature")
                        continue
                    if not math.isfinite(numeric):
                        finite = False
                        errors.append("feature")
    except (OSError, UnicodeError, csv.Error) as exc:
        raise _error(
            "dataset_schema_invalid",
            "schema",
            False,
            "Dataset schema validation failed.",
            exc,
        ) from None

    if row_count != definition.expected_rows:
        errors.append("row_count")
    if row_count == 0:
        errors.append("empty")
    if observed_columns != definition.expected_columns:
        errors.append("column_count")
    if labels != set(definition.allowed_labels):
        errors.append("labels")
    schema_valid = not errors
    report = DatasetValidationReport(
        row_count=row_count,
        column_count=observed_columns,
        feature_count=definition.feature_count,
        unique_id_count=len(identifiers),
        labels=tuple(sorted(labels)),
        finite_feature_values=finite,
        missing_value_count=missing_count,
        duplicate_id_count=duplicate_count,
        schema_valid=schema_valid,
        errors=tuple(sorted(set(errors))),
        warnings=(),
    )
    if not schema_valid:
        raise _error(
            "dataset_schema_invalid",
            "schema",
            False,
            "Dataset schema validation failed.",
        )
    return report


def _looks_like_archive(prefix: bytes) -> bool:
    if any(prefix.startswith(magic) for magic in _ARCHIVE_PREFIXES):
        return True
    return len(prefix) >= 262 and prefix[257:262] == b"ustar"


class _DatasetLock:
    def __init__(self, path: Path, timeout: float, monotonic: Callable[[], float]) -> None:
        self._path = path
        self._timeout = timeout
        self._monotonic = monotonic
        self._acquired = False

    def __enter__(self) -> _DatasetLock:
        deadline = self._monotonic() + self._timeout
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        while True:
            try:
                descriptor = os.open(self._path, flags, 0o600)
                os.close(descriptor)
                self._acquired = True
                return self
            except FileExistsError:
                if self._monotonic() >= deadline:
                    raise _error(
                        "dataset_concurrent_fetch",
                        "lock",
                        True,
                        "Dataset fetch is already active.",
                    ) from None
                time.sleep(min(0.01, max(0.0, deadline - self._monotonic())))
            except OSError as exc:
                raise _error(
                    "dataset_concurrent_fetch",
                    "lock",
                    True,
                    "Dataset fetch lock is unavailable.",
                    exc,
                ) from None

    def __exit__(self, _kind: object, _value: object, _trace: object) -> None:
        if self._acquired:
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                pass
            self._acquired = False


class DatasetAdapter:
    def __init__(
        self,
        registry: DatasetRegistry,
        *,
        transport: httpx.BaseTransport | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 10.0,
        total_timeout_seconds: float = 30.0,
        chunk_size: int = 65536,
        redirect_limit: int = 3,
        lock_timeout_seconds: float = 0.0,
        monotonic: Callable[[], float] | None = None,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(registry, DatasetRegistry):
            raise TypeError("registry must be a DatasetRegistry")
        for name, value in (
            ("connect_timeout_seconds", connect_timeout_seconds),
            ("read_timeout_seconds", read_timeout_seconds),
            ("total_timeout_seconds", total_timeout_seconds),
            ("lock_timeout_seconds", lock_timeout_seconds),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a nonnegative number")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if isinstance(redirect_limit, bool) or not isinstance(redirect_limit, int) or redirect_limit < 0:
            raise ValueError("redirect_limit must be nonnegative")
        self._registry = registry
        self._transport = transport
        self._connect_timeout = float(connect_timeout_seconds)
        self._read_timeout = float(read_timeout_seconds)
        self._total_timeout = float(total_timeout_seconds)
        self._chunk_size = chunk_size
        self._redirect_limit = redirect_limit
        self._lock_timeout = float(lock_timeout_seconds)
        self._monotonic = monotonic or time.monotonic
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))

    def fetch(
        self,
        dataset_id: str,
        *,
        cache_root: Path,
        offline: bool = False,
    ) -> ResolvedDataset:
        definition = self._registry.get(dataset_id)
        if not definition.is_pinned:
            raise _error(
                "dataset_unvalidated",
                "pin",
                False,
                "Dataset has no approved integrity pin.",
            )

        root = Path(cache_root)
        final = root / definition.cache_relative_dir / definition.target_filename
        if final.exists() or final.is_symlink():
            return self._resolve_existing(definition, root, final, offline=offline)
        if offline:
            raise _error(
                "dataset_offline_missing",
                "cache",
                False,
                "Pinned dataset is not available in the offline cache.",
            )

        root, parent = _prepare_directory(root, definition.cache_relative_dir)
        final = parent / definition.target_filename
        lock_path = parent / f"{definition.target_filename}.lock"
        _ensure_lock_contained(root, lock_path)
        with _DatasetLock(lock_path, self._lock_timeout, self._monotonic):
            if final.exists() or final.is_symlink():
                return self._resolve_existing(definition, root, final, offline=False)
            digest, size, report, warnings = self._download_to(
                definition,
                root,
                final,
                require_pin=True,
            )
        return self._resolved(
            definition,
            final,
            digest,
            size,
            report,
            cache_hit=False,
            offline=False,
            warnings=warnings,
        )

    def inspect_unpinned_candidate(
        self,
        dataset_id: str,
        *,
        staging_root: Path,
    ) -> DatasetPinCandidate:
        definition = self._registry.get(dataset_id)
        root, parent = _prepare_directory(Path(staging_root), "candidates")
        final = parent / f"{definition.target_filename}.candidate"
        if final.exists() or final.is_symlink():
            raise _error(
                "dataset_io_error",
                "io",
                False,
                "Dataset candidate destination is not empty.",
            )
        digest, size, report, warnings = self._download_to(
            definition,
            root,
            final,
            require_pin=False,
        )
        return DatasetPinCandidate(
            dataset_id=definition.dataset_id,
            version=definition.version,
            source_url=definition.source_url,
            candidate_path=final,
            computed_sha256=digest,
            size_bytes=size,
            validation_report=report,
            warnings=warnings,
        )

    def build_resolver(
        self,
        cache_root: Path,
    ) -> Callable[[DatasetManifest], Path]:
        root = Path(cache_root)

        def resolve(manifest: DatasetManifest) -> Path:
            try:
                definition = self._registry.get(manifest.dataset_id)
            except (AttributeError, DatasetAdapterError):
                raise _error(
                    "dataset_cache_corrupt",
                    "cache",
                    False,
                    "Dataset manifest cannot be resolved.",
                ) from None
            if not definition.is_pinned:
                raise _error(
                    "dataset_unvalidated",
                    "pin",
                    False,
                    "Dataset has no approved integrity pin.",
                )
            expected_workspace = f"datasets/{definition.target_filename}"
            if (
                manifest.source_uri != definition.source_url
                or manifest.license != definition.license_id
                or manifest.version != definition.version
                or manifest.sha256 != definition.expected_sha256
                or manifest.size_bytes != definition.expected_size_bytes
                or manifest.workspace_relative_path != expected_workspace
            ):
                raise _error(
                    "dataset_cache_corrupt",
                    "cache",
                    False,
                    "Dataset manifest does not match the registered pin.",
                )
            final = root / definition.cache_relative_dir / definition.target_filename
            self._validate_cache(definition, root, final)
            return final

        return resolve

    def _resolved(
        self,
        definition: DatasetDefinition,
        path: Path,
        digest: str,
        size: int,
        report: DatasetValidationReport,
        *,
        cache_hit: bool,
        offline: bool,
        warnings: tuple[str, ...],
    ) -> ResolvedDataset:
        moment = self._utcnow()
        if isinstance(moment, datetime):
            resolved_at = moment.isoformat()
        else:
            resolved_at = str(moment)
        return ResolvedDataset(
            dataset_id=definition.dataset_id,
            version=definition.version,
            source_url=definition.source_url,
            cache_path=path,
            sha256=digest,
            size_bytes=size,
            validation_report=report,
            cache_hit=cache_hit,
            offline=offline,
            warnings=warnings,
            resolved_at=resolved_at,
            _license_id=definition.license_id,
            _workspace_relative_path=f"datasets/{definition.target_filename}",
        )

    def _resolve_existing(
        self,
        definition: DatasetDefinition,
        root: Path,
        final: Path,
        *,
        offline: bool,
    ) -> ResolvedDataset:
        digest, size, report = self._validate_cache(definition, root, final)
        return self._resolved(
            definition,
            final,
            digest,
            size,
            report,
            cache_hit=True,
            offline=offline,
            warnings=(),
        )

    def _validate_cache(
        self,
        definition: DatasetDefinition,
        root: Path,
        final: Path,
    ) -> tuple[str, int, DatasetValidationReport]:
        if not _safe_regular_file(final, root):
            raise _error(
                "dataset_cache_corrupt",
                "cache",
                False,
                "Dataset cache entry is missing or unsafe.",
            )
        try:
            digest, size = _digest_file(final)
            if size != definition.expected_size_bytes or digest != definition.expected_sha256:
                raise ValueError("pin mismatch")
            report = _validate_wdbc_schema(final, definition)
        except (DatasetAdapterError, ValueError) as exc:
            raise _error(
                "dataset_cache_corrupt",
                "cache",
                False,
                "Dataset cache entry failed validation.",
                exc,
            ) from None
        return digest, size, report

    def _new_client(self) -> httpx.Client:
        timeout = httpx.Timeout(
            connect=self._connect_timeout,
            read=self._read_timeout,
            write=self._read_timeout,
            pool=self._connect_timeout,
        )
        return httpx.Client(
            transport=self._transport,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            verify=True,
        )

    def _validate_redirect(self, definition: DatasetDefinition, location: str, current: str) -> str:
        destination = urljoin(current, location)
        parsed = urlsplit(destination)
        try:
            port = parsed.port
        except ValueError:
            port = -1
        host = (parsed.hostname or "").rstrip(".").casefold()
        if (
            parsed.scheme.casefold() != "https"
            or not host
            or host not in definition.allowed_redirect_hosts
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or parsed.query
            or parsed.fragment
        ):
            raise _error(
                "dataset_redirect_forbidden",
                "redirect",
                False,
                "Dataset redirect is not permitted.",
            )
        return destination

    def _download_to(
        self,
        definition: DatasetDefinition,
        root: Path,
        final: Path,
        *,
        require_pin: bool,
    ) -> tuple[str, int, DatasetValidationReport, tuple[str, ...]]:
        _ensure_contained(root, final)
        descriptor = -1
        part: Path | None = None
        try:
            descriptor, raw_part = tempfile.mkstemp(
                prefix=f"{final.name}.",
                suffix=".part",
                dir=final.parent,
            )
            part = Path(raw_part)
            _ensure_contained(root, part)
            # Exercise the high-level file boundary without writing through it;
            # the securely created descriptor remains the sole byte writer.
            with part.open("ab"):
                pass
            digest = hashlib.sha256()
            total = 0
            prefix = bytearray()
            warnings: list[str] = []
            started = self._monotonic()
            current = definition.source_url
            redirect_count = 0

            with os.fdopen(descriptor, "wb") as writer:
                descriptor = -1
                with self._new_client() as client:
                    while True:
                        try:
                            with client.stream(
                                "GET",
                                current,
                                headers={"Accept": "text/plain, text/csv, application/octet-stream"},
                            ) as response:
                                if response.status_code in _REDIRECT_CODES:
                                    if redirect_count >= self._redirect_limit:
                                        raise _error(
                                            "dataset_redirect_limit",
                                            "redirect",
                                            False,
                                            "Dataset redirect limit was exceeded.",
                                        )
                                    location = response.headers.get("Location")
                                    if not location:
                                        raise _error(
                                            "dataset_redirect_forbidden",
                                            "redirect",
                                            False,
                                            "Dataset redirect is incomplete.",
                                        )
                                    current = self._validate_redirect(
                                        definition,
                                        location,
                                        current,
                                    )
                                    redirect_count += 1
                                    client.cookies.clear()
                                    continue
                                if response.status_code < 200 or response.status_code >= 300:
                                    retryable = response.status_code == 429 or response.status_code >= 500
                                    raise _error(
                                        "dataset_http_error",
                                        "http",
                                        retryable,
                                        "Dataset server returned an unsuccessful status.",
                                    )

                                encoding = response.headers.get("Content-Encoding", "").strip()
                                if encoding and encoding.casefold() != "identity":
                                    raise _error(
                                        "dataset_archive_unexpected",
                                        "download",
                                        False,
                                        "Encoded dataset responses are not accepted.",
                                    )
                                content_type = response.headers.get("Content-Type")
                                if content_type is None:
                                    if (
                                        current == definition.source_url
                                        and redirect_count == 0
                                        and definition.allow_missing_content_type_for_exact_url
                                    ):
                                        warnings.append(
                                            "content_type_missing_exact_source_exception"
                                        )
                                    else:
                                        raise _error(
                                            "dataset_content_type_invalid",
                                            "download",
                                            False,
                                            "Dataset response content type is missing.",
                                        )
                                else:
                                    media_type = content_type.split(";", 1)[0].strip().casefold()
                                    if media_type not in definition.allowed_content_types:
                                        raise _error(
                                            "dataset_content_type_invalid",
                                            "download",
                                            False,
                                            "Dataset response content type is not allowed.",
                                        )
                                declared_text = response.headers.get("Content-Length")
                                declared: int | None = None
                                if declared_text is not None:
                                    try:
                                        declared = int(declared_text)
                                    except ValueError:
                                        declared = -1
                                    if declared < 0 or declared > definition.max_download_bytes:
                                        raise _error(
                                            "dataset_size_invalid",
                                            "download",
                                            False,
                                            "Dataset response size is invalid.",
                                        )

                                chunks = (
                                    response.iter_bytes(chunk_size=self._chunk_size)
                                    if response.is_stream_consumed
                                    else response.iter_raw(chunk_size=self._chunk_size)
                                )
                                for chunk in chunks:
                                    if self._monotonic() - started > self._total_timeout:
                                        raise _error(
                                            "dataset_timeout",
                                            "total",
                                            True,
                                            "Dataset download exceeded its total timeout.",
                                        )
                                    if not chunk:
                                        continue
                                    total += len(chunk)
                                    if total > definition.max_download_bytes:
                                        raise _error(
                                            "dataset_size_invalid",
                                            "download",
                                            False,
                                            "Dataset response exceeded its size limit.",
                                        )
                                    if len(prefix) < 512:
                                        prefix.extend(chunk[: 512 - len(prefix)])
                                        if _looks_like_archive(bytes(prefix)):
                                            raise _error(
                                                "dataset_archive_unexpected",
                                                "download",
                                                False,
                                                "Dataset response has an archive signature.",
                                            )
                                    writer.write(chunk)
                                    digest.update(chunk)
                                if declared is not None and declared != total:
                                    raise _error(
                                        "dataset_size_invalid",
                                        "download",
                                        False,
                                        "Dataset response size did not match its declaration.",
                                    )
                                break
                        except httpx.ConnectTimeout as exc:
                            raise _error("dataset_timeout", "connect", True, "Dataset connection timed out.", exc) from None
                        except httpx.ReadTimeout as exc:
                            raise _error("dataset_timeout", "read", True, "Dataset read timed out.", exc) from None
                        except httpx.WriteTimeout as exc:
                            raise _error("dataset_timeout", "write", True, "Dataset request timed out.", exc) from None
                        except httpx.PoolTimeout as exc:
                            raise _error("dataset_timeout", "pool", True, "Dataset connection pool timed out.", exc) from None
                        except httpx.ConnectError as exc:
                            raise _error("dataset_http_error", "connect", True, "Dataset connection failed.", exc) from None
                        except httpx.RemoteProtocolError as exc:
                            raise _error("dataset_http_error", "read", True, "Dataset response protocol failed.", exc) from None
                        except httpx.DecodingError as exc:
                            raise _error(
                                "dataset_archive_unexpected",
                                "download",
                                False,
                                "Encoded dataset responses are not accepted.",
                                exc,
                            ) from None
                writer.flush()
                os.fsync(writer.fileno())

            computed = digest.hexdigest()
            if require_pin and total != definition.expected_size_bytes:
                raise _error(
                    "dataset_size_invalid",
                    "download",
                    False,
                    "Dataset bytes did not match the pinned size.",
                )
            if require_pin and computed != definition.expected_sha256:
                raise _error(
                    "dataset_checksum_mismatch",
                    "checksum",
                    False,
                    "Dataset bytes did not match the pinned digest.",
                )
            report = _validate_wdbc_schema(part, definition)
            try:
                os.replace(part, final)
            except OSError as exc:
                raise _error(
                    "dataset_io_error",
                    "io",
                    False,
                    "Dataset cache installation failed.",
                    exc,
                ) from None
            part = None
            return computed, total, report, tuple(warnings)
        except DatasetAdapterError:
            raise
        except OSError as exc:
            raise _error(
                "dataset_io_error",
                "io",
                False,
                "Dataset file operation failed.",
                exc,
            ) from None
        finally:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if part is not None:
                try:
                    part.unlink(missing_ok=True)
                except OSError:
                    pass


__all__ = [
    "WDBC_DATASET_ID",
    "DatasetDefinition",
    "DatasetRegistry",
    "DatasetAdapter",
    "DatasetAdapterError",
    "DatasetValidationReport",
    "DatasetPinCandidate",
    "ResolvedDataset",
    "get_default_dataset_registry",
]
