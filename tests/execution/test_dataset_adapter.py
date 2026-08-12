"""Wave B red contracts for the pinned, offline-first dataset adapter.

SYNTHETIC_TEST_FIXTURE_ONLY
NOT_UCI_SOURCE_DATA
NOT_A_SCIENTIFIC_RESULT

The production module intentionally does not exist in this Wave B step.  Every
production-facing test resolves it at test runtime through ``require_symbol``
so collection remains healthy while the behavior matrix is red.  All HTTP
interactions use an injected ``httpx.MockTransport``; an autouse socket guard
turns any accidental real-network attempt into a test defect.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import inspect
import math
import os
import socket
import threading
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest


WDBC_DATASET_ID_VALUE = "uci-wdbc-diagnostic-17-1995-10-31"
WDBC_SOURCE_URL = (
    "https://archive.ics.uci.edu/ml/machine-learning-databases/"
    "breast-cancer-wisconsin/wdbc.data"
)
WDBC_CACHE_RELATIVE_DIR = "datasets/uci-wdbc-v1995-10-31"
WDBC_TARGET_FILENAME = "wdbc.data"
MAX_DOWNLOAD_BYTES = 1024 * 1024
WDBC_PIN_SHA256 = "d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a"
WDBC_PIN_SIZE_BYTES = 124103
DATASET_MODULE = "app.execution.datasets"

FROZEN_SYMBOLS = (
    "WDBC_DATASET_ID",
    "DatasetDefinition",
    "DatasetRegistry",
    "DatasetAdapter",
    "DatasetAdapterError",
    "DatasetValidationReport",
    "DatasetPinCandidate",
    "ResolvedDataset",
    "get_default_dataset_registry",
)


@dataclass(frozen=True)
class ContractCase:
    """A stable behavior ID and its externally observable expectation."""

    test_id: str
    summary: str
    expected_code: str | None = None
    expected_stage: str | None = None
    retryable: bool | None = None


def _family(
    name: str,
    summaries: tuple[str, ...],
    errors: Mapping[int, tuple[str, str | None, bool | None]] | None = None,
) -> tuple[ContractCase, ...]:
    error_map = errors or {}
    cases: list[ContractCase] = []
    for index, summary in enumerate(summaries, start=1):
        code, stage, retryable = error_map.get(index, (None, None, None))
        cases.append(
            ContractCase(
                test_id=f"T05-B-DATA-{name}-{index:03d}",
                summary=summary,
                expected_code=code,
                expected_stage=stage,
                retryable=retryable,
            )
        )
    return tuple(cases)


REG_CASES = _family(
    "REG",
    (
        "default registry contains only the frozen WDBC identifier",
        "WDBC provenance metadata is exact and complete",
        "WDBC source URL has the pinned HTTPS host and path shape",
        "target filename and cache-relative directory are safe",
        "WDBC schema dimensions and labels are frozen",
        "download ceiling is exactly one MiB",
        "archives are rejected",
        "default WDBC definition carries the independently verified hash and size pin",
        "dataset definitions are immutable",
        "duplicate dataset identifiers are rejected",
        "unknown dataset identifiers have a stable error",
        "module import has no filesystem, network, environment, or output effects",
    ),
    {11: ("dataset_unknown", "registry", False)},
)

URL_CASES = _family(
    "URL",
    (
        "plain HTTP is rejected while constructing a definition",
        "URL userinfo is rejected without disclosure",
        "secret-bearing query parameters are rejected without disclosure",
        "URL fragments are rejected",
        "a source host outside the allowlist is rejected",
        "an unregistered path on an allowed host is rejected",
        "fetch accepts no caller-controlled URL or pin override",
        "one validated same-host HTTPS redirect may succeed",
        "an explicitly allowed HTTPS redirect host may succeed",
        "redirects to unapproved hosts are rejected",
        "HTTPS-to-HTTP redirect downgrade is rejected",
        "redirect userinfo or secret query data is rejected and redacted",
        "redirect loops stop at the configured limit",
        "redirect chains longer than the configured limit stop",
        "HTTPX client disables automatic redirects and environment trust",
        "proxy environment variables cannot affect injected transport requests",
    ),
    {
        1: ("dataset_tls_required", "definition", False),
        2: ("dataset_url_forbidden", "definition", False),
        3: ("dataset_url_forbidden", "definition", False),
        4: ("dataset_url_forbidden", "definition", False),
        5: ("dataset_url_forbidden", "definition", False),
        6: ("dataset_url_forbidden", "definition", False),
        10: ("dataset_redirect_forbidden", "redirect", False),
        11: ("dataset_redirect_forbidden", "redirect", False),
        12: ("dataset_redirect_forbidden", "redirect", False),
        13: ("dataset_redirect_limit", "redirect", False),
        14: ("dataset_redirect_limit", "redirect", False),
    },
)

NET_CASES = _family(
    "NET",
    (
        "connect timeout is classified and retryable",
        "read timeout is classified and retryable",
        "write timeout is classified and retryable",
        "pool timeout is classified and retryable",
        "connect error is retryable",
        "remote protocol error is retryable",
        "HTTP 404 is not retryable",
        "HTTP 401 and 403 are not retryable",
        "HTTP 429 is retryable without an unbounded retry loop",
        "HTTP 5xx errors are retryable",
        "a deterministic total wall-clock timeout interrupts streaming",
        "None and negative public timeout values are rejected",
    ),
    {
        1: ("dataset_timeout", "connect", True),
        2: ("dataset_timeout", "read", True),
        3: ("dataset_timeout", "write", True),
        4: ("dataset_timeout", "pool", True),
        5: ("dataset_http_error", "connect", True),
        6: ("dataset_http_error", "read", True),
        7: ("dataset_http_error", "http", False),
        8: ("dataset_http_error", "http", False),
        9: ("dataset_http_error", "http", True),
        10: ("dataset_http_error", "http", True),
        11: ("dataset_timeout", "total", True),
    },
)

DL_CASES = _family(
    "DL",
    (
        "response bytes are consumed incrementally from SyncByteStream",
        "oversize Content-Length fails before reading the body",
        "chunked bytes stop as soon as the maximum is exceeded",
        "actual streamed size overrides an understated Content-Length",
        "Content-Length must equal the completed byte count",
        "the three declared content types are accepted with parameters",
        "HTML, JSON, images, and PDF content types are rejected",
        "missing content type has one exact pinned-source exception",
        "missing content type after redirect is rejected",
        "compressed Content-Encoding values are rejected",
        "archive magic is rejected even under text/plain",
        "ZIP, GZIP, 7z, XZ, BZIP2, and TAR magic are rejected",
        "NUL-dense binary content is rejected as invalid schema",
        "invalid UTF-8 is rejected as invalid schema",
    ),
    {
        2: ("dataset_size_invalid", "download", False),
        3: ("dataset_size_invalid", "download", False),
        4: ("dataset_size_invalid", "download", False),
        5: ("dataset_size_invalid", "download", False),
        7: ("dataset_content_type_invalid", "download", False),
        9: ("dataset_content_type_invalid", "download", False),
        10: ("dataset_archive_unexpected", "download", False),
        11: ("dataset_archive_unexpected", "download", False),
        12: ("dataset_archive_unexpected", "download", False),
        13: ("dataset_schema_invalid", "schema", False),
        14: ("dataset_schema_invalid", "schema", False),
    },
)

IO_CASES = _family(
    "IO",
    (
        "temporary downloads live beside the canonical cache file",
        "a unique caller-independent part filename is created safely",
        "only the part file exists while streaming",
        "atomic replacement occurs only after every validation gate",
        "checksum mismatch removes the part and creates no result",
        "schema mismatch removes the part and creates no result",
        "a write failure is classified and cleaned up",
        "flush, fsync, and close failures are classified",
        "atomic replace failure leaves no claimed success",
        "a failed download never overwrites an existing valid cache",
        "valid cache bytes and digest survive a failed recovery",
        "all failure paths remove orphan part files",
        "handles are closed so Windows rename and delete remain possible",
        "cache directory creation errors are safe and path-redacted",
    ),
    {
        5: ("dataset_checksum_mismatch", "checksum", False),
        6: ("dataset_schema_invalid", "schema", False),
        7: ("dataset_io_error", "io", False),
        8: ("dataset_io_error", "io", False),
        9: ("dataset_io_error", "io", False),
        14: ("dataset_io_error", "io", False),
    },
)

CACHE_CASES = _family(
    "CACHE",
    (
        "a pinned cache is revalidated and never causes network access",
        "offline mode returns a valid cache with offline evidence",
        "offline missing cache has a stable failure",
        "offline checksum corruption fails closed",
        "offline size corruption fails closed",
        "offline schema corruption fails closed",
        "online mode also fails closed on a corrupt cache",
        "corrupt cache is neither silently deleted nor overwritten",
        "cache entries are isolated by dataset version",
        "cache entries are isolated by dataset identifier",
        "a symlink cache file is rejected",
        "directories and other non-regular cache nodes are rejected",
        "resolved cache paths cannot escape cache_root",
        "unrelated cache_root files are preserved",
        "a leftover part file is never treated as a cache hit",
    ),
    {
        3: ("dataset_offline_missing", "cache", False),
        4: ("dataset_cache_corrupt", "cache", False),
        5: ("dataset_cache_corrupt", "cache", False),
        6: ("dataset_cache_corrupt", "cache", False),
        7: ("dataset_cache_corrupt", "cache", False),
        11: ("dataset_cache_corrupt", "cache", False),
        12: ("dataset_cache_corrupt", "cache", False),
        13: ("dataset_cache_corrupt", "cache", False),
    },
)

LOCK_CASES = _family(
    "LOCK",
    (
        "same dataset, version, and cache root permit one active fetch",
        "different versions do not share a lock",
        "different dataset identifiers do not share a lock",
        "lock files cannot be symlinks or junctions",
        "lock timeout has a stable retryable failure",
        "exceptions release the in-process lock",
        "successful downloads release the lock",
        "lock state and errors expose no user, path, token, or command data",
    ),
    {
        1: ("dataset_concurrent_fetch", "lock", True),
        4: ("dataset_concurrent_fetch", "lock", True),
        5: ("dataset_concurrent_fetch", "lock", True),
    },
)

SCHEMA_CASES = _family(
    "SCHEMA",
    (
        "a deterministic synthetic 569 by 32 fixture validates",
        "568 rows are rejected",
        "570 rows are rejected",
        "31 columns are rejected",
        "33 columns are rejected",
        "an unknown diagnosis label is rejected",
        "a blank diagnosis label is rejected",
        "duplicate identifiers are rejected",
        "a blank identifier is rejected",
        "a blank feature is rejected",
        "a nonnumeric feature is rejected",
        "NaN and infinity spellings are rejected",
        "boolean-shaped features are rejected",
        "an unexpected header is rejected",
        "an empty file is rejected",
        "blank rows, trailing fields, and NUL are rejected",
        "validation report records only aggregate schema evidence",
        "validation report stores no complete source rows",
    ),
    {
        index: ("dataset_schema_invalid", "schema", False)
        for index in range(2, 17)
    },
)

LICENSE_CASES = _family(
    "LICENSE",
    (
        "default WDBC definition retains complete license provenance",
        "missing license identifier is rejected",
        "missing license URL is rejected",
        "missing citation is rejected",
        "a non-HTTPS license URL is rejected",
        "resolved manifest retains the six required provenance fields",
        "manifest excludes host paths, secrets, usernames, and question text",
    ),
    {
        2: ("dataset_license_missing", "definition", False),
        3: ("dataset_license_missing", "definition", False),
        4: ("dataset_license_missing", "definition", False),
        5: ("dataset_tls_required", "definition", False),
    },
)

PIN_CASES = _family(
    "PIN",
    (
        "a test-only unpinned hash fails before any network request",
        "a test-only unpinned exact size fails before any network request",
        "fetch exposes no caller pin, URL, license, or version overrides",
        "candidate inspection validates only inside staging_root",
        "a candidate cannot become a formal manifest or resolved dataset",
        "candidate inspection never mutates the registry",
        "candidate public summary is useful, safe, and explicitly nonformal",
        "a test-only pinned definition can complete formal fetch",
        "an incorrect pinned checksum is rejected",
        "an incorrect pinned exact size is rejected",
    ),
    {
        1: ("dataset_unvalidated", "pin", False),
        2: ("dataset_unvalidated", "pin", False),
        9: ("dataset_checksum_mismatch", "checksum", False),
        10: ("dataset_size_invalid", "download", False),
    },
)

SEC_CASES = _family(
    "SEC",
    (
        "requests contain no Authorization header",
        "requests contain no Cookie header",
        "response cookies are not replayed across redirects",
        "credential-shaped parent environment values stay isolated",
        "adapter never reads a nearby .env file",
        "secret-bearing URL errors redact every public representation",
        "errors exclude the complete temporary path",
        "errors exclude the repository absolute path",
        "import and fetch write nothing to stdout or stderr",
        "offline mode constructs no network client",
        "unexpected archives are never extracted",
        "production download code uses no command interpreter or dynamic code",
    ),
)

INTEGRATION_CASES = _family(
    "INTEGRATION",
    (
        "resolved data converts to the current DatasetManifest type",
        "manifest provenance and integrity match the resolved dataset",
        "manifest contains no absolute cache path",
        "build_resolver returns a DatasetManifest-to-Path callable",
        "resolver revalidates identity, integrity, schema, type, and containment",
        "post-fetch cache tampering makes the resolver fail closed",
        "resolver performs no network access",
        "unknown, unpinned, and mismatched manifests are rejected",
        "resolver paths remain within the supplied cache_root",
    ),
)

ALL_CONTRACT_CASES = (
    REG_CASES
    + URL_CASES
    + NET_CASES
    + DL_CASES
    + IO_CASES
    + CACHE_CASES
    + LOCK_CASES
    + SCHEMA_CASES
    + LICENSE_CASES
    + PIN_CASES
    + SEC_CASES
    + INTEGRATION_CASES
)


class ChunkedSyncByteStream(httpx.SyncByteStream):
    """A deterministic stream that detects eager whole-body access."""

    def __init__(
        self,
        chunks: tuple[bytes, ...],
        *,
        before_chunk: Callable[[int], None] | None = None,
        failure_after: int | None = None,
    ) -> None:
        self._chunks = chunks
        self._before_chunk = before_chunk
        self._failure_after = failure_after
        self.iterated_chunks = 0
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        for index, chunk in enumerate(self._chunks):
            if self._before_chunk is not None:
                self._before_chunk(index)
            if self._failure_after is not None and index >= self._failure_after:
                raise OSError("synthetic stream failure")
            self.iterated_chunks += 1
            yield chunk

    def close(self) -> None:
        self.closed = True


class FakeClock:
    """A monotonic fake whose time advances only when a test requests it."""

    def __init__(self, initial: float = 100.0) -> None:
        self.value = initial

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail fast if adapter tests accidentally leave MockTransport."""

    def blocked(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("real network access is forbidden in dataset tests")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def _make_synthetic_wdbc_bytes(
    *,
    rows: int = 569,
    columns: int = 32,
    label: str | None = None,
    duplicate_id: bool = False,
    blank_id: bool = False,
    blank_feature: bool = False,
    feature_text: str | None = None,
    add_header: bool = False,
    add_blank_row: bool = False,
    add_nul: bool = False,
) -> bytes:
    """Generate deterministic schema-shaped bytes, never source records."""

    generated: list[list[str]] = []
    for row_index in range(rows):
        identifier = str(100_000 + row_index)
        if duplicate_id and row_index == rows - 1:
            identifier = "100000"
        if blank_id and row_index == 0:
            identifier = ""
        diagnosis = label if label is not None else ("M" if row_index % 2 else "B")
        features = [
            f"{((row_index + 1) * (feature_index + 1)) / 1000:.6f}"
            for feature_index in range(30)
        ]
        if blank_feature and row_index == 0:
            features[0] = ""
        if feature_text is not None and row_index == 0:
            features[0] = feature_text
        record = [identifier, diagnosis, *features]
        if columns < len(record):
            record = record[:columns]
        elif columns > len(record):
            record.extend("0.000000" for _ in range(columns - len(record)))
        generated.append(record)

    lines: list[str] = []
    if add_header:
        lines.append(",".join(["id", "diagnosis", *[f"f{i}" for i in range(30)]]))
    lines.extend(",".join(record) for record in generated)
    if add_blank_row:
        lines.insert(1, "")
    payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    if add_nul:
        payload += b"\x00"
    return payload


@pytest.fixture(scope="module")
def synthetic_wdbc_bytes() -> bytes:
    return _make_synthetic_wdbc_bytes()


def _split_chunks(payload: bytes, chunk_size: int = 4096) -> tuple[bytes, ...]:
    return tuple(
        payload[index : index + chunk_size]
        for index in range(0, len(payload), chunk_size)
    )


def _public_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return dict(value.model_dump(mode="python"))
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    raise TypeError(f"cannot inspect public fields for {type(value)!r}")


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _require_api(
    require_symbol: Callable[[str, str, str], Any],
    test_id: str,
) -> SimpleNamespace:
    symbols = {
        name: require_symbol(DATASET_MODULE, name, test_id)
        for name in FROZEN_SYMBOLS
    }
    symbols["DatasetManifest"] = require_symbol(
        "app.contracts.execution", "DatasetManifest", test_id
    )
    symbols["EntrypointRegistry"] = require_symbol(
        "app.execution", "EntrypointRegistry", test_id
    )
    symbols["LocalProcessRunner"] = require_symbol(
        "app.execution", "LocalProcessRunner", test_id
    )
    symbols["module"] = importlib.import_module(DATASET_MODULE)
    return SimpleNamespace(**symbols)


def _definition_payload(
    payload: bytes,
    *,
    pinned: bool = True,
    dataset_id: str = WDBC_DATASET_ID_VALUE,
    version: str = "1995-10-31",
    **overrides: Any,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "dataset_id": dataset_id,
        "official_name": "Breast Cancer Wisconsin (Diagnostic)",
        "publisher": "UCI Machine Learning Repository",
        "version": version,
        "source_url": WDBC_SOURCE_URL,
        "allowed_source_hosts": frozenset({"archive.ics.uci.edu"}),
        "allowed_redirect_hosts": frozenset({"archive.ics.uci.edu"}),
        "target_filename": WDBC_TARGET_FILENAME,
        "cache_relative_dir": WDBC_CACHE_RELATIVE_DIR,
        "license_id": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "citation": "Wolberg, Street, and Mangasarian; WDBC (1995).",
        "doi": "10.24432/C5DW2B",
        "expected_sha256": hashlib.sha256(payload).hexdigest() if pinned else None,
        "expected_size_bytes": len(payload) if pinned else None,
        "max_download_bytes": MAX_DOWNLOAD_BYTES,
        "expected_rows": 569,
        "expected_columns": 32,
        "feature_count": 30,
        "allowed_labels": frozenset({"M", "B"}),
        "allowed_content_types": frozenset(
            {"text/plain", "text/csv", "application/octet-stream"}
        ),
        "allow_missing_content_type_for_exact_url": True,
        "archive_policy": "reject",
    }
    values.update(overrides)
    return values


def _make_definition(
    api: SimpleNamespace,
    payload: bytes,
    *,
    pinned: bool = True,
    **overrides: Any,
) -> Any:
    return api.DatasetDefinition(
        **_definition_payload(payload, pinned=pinned, **overrides)
    )


def _make_registry(api: SimpleNamespace, *definitions: Any) -> Any:
    return api.DatasetRegistry(definitions)


def _make_adapter(
    api: SimpleNamespace,
    definition: Any,
    handler: Callable[[httpx.Request], httpx.Response],
    **overrides: Any,
) -> Any:
    return api.DatasetAdapter(
        _make_registry(api, definition),
        transport=httpx.MockTransport(handler),
        **overrides,
    )


def _success_response(
    request: httpx.Request,
    payload: bytes,
    *,
    content_type: str | None = "text/plain; charset=utf-8",
    headers: Mapping[str, str] | None = None,
    stream: httpx.SyncByteStream | None = None,
    status_code: int = 200,
) -> httpx.Response:
    response_headers = dict(headers or {})
    if content_type is not None:
        response_headers["Content-Type"] = content_type
    if stream is None:
        response_headers.setdefault("Content-Length", str(len(payload)))
        return httpx.Response(
            status_code,
            headers=response_headers,
            content=payload,
            request=request,
        )
    return httpx.Response(
        status_code,
        headers=response_headers,
        stream=stream,
        request=request,
    )


def _cache_path(cache_root: Path, definition: Any) -> Path:
    return (
        cache_root
        / str(definition.cache_relative_dir)
        / str(definition.target_filename)
    )


def _install_cache(cache_root: Path, definition: Any, payload: bytes) -> Path:
    target = _cache_path(cache_root, definition)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def _assert_error(
    api: SimpleNamespace,
    error: BaseException,
    case: ContractCase,
    *,
    forbidden: tuple[str, ...] = (),
) -> None:
    assert isinstance(error, api.DatasetAdapterError)
    assert _enum_value(getattr(error, "code")) == case.expected_code
    if case.expected_stage is not None:
        assert _enum_value(getattr(error, "stage")) == case.expected_stage
    if case.retryable is not None:
        assert getattr(error, "retryable") is case.retryable
    public_text = f"{error!s}\n{error!r}\n{_public_dump(error)!r}"
    for sensitive in forbidden:
        assert sensitive not in public_text


def _expect_adapter_error(
    api: SimpleNamespace,
    case: ContractCase,
    operation: Callable[[], Any],
    *,
    forbidden: tuple[str, ...] = (),
) -> BaseException:
    with pytest.raises(api.DatasetAdapterError) as captured:
        operation()
    _assert_error(api, captured.value, case, forbidden=forbidden)
    return captured.value


def _never_network(_request: httpx.Request) -> httpx.Response:
    raise AssertionError("MockTransport handler must not be called")


def _parts(cache_root: Path) -> list[Path]:
    return sorted(
        path
        for path in cache_root.rglob("*")
        if path.is_file() and ".part" in path.name
    )


def test_T05_B_DATA_HELPER_001_synthetic_fixture_is_deterministic_and_valid(
    synthetic_wdbc_bytes: bytes,
) -> None:
    """Helper self-check: generated bytes satisfy the frozen WDBC shape."""

    rows = list(csv.reader(synthetic_wdbc_bytes.decode("utf-8").splitlines()))
    assert len(rows) == 569
    assert {len(row) for row in rows} == {32}
    assert len({row[0] for row in rows}) == 569
    assert {row[1] for row in rows} == {"M", "B"}
    assert all(
        math.isfinite(float(feature))
        for row in rows
        for feature in row[2:]
    )
    assert len(synthetic_wdbc_bytes) < MAX_DOWNLOAD_BYTES
    assert len(hashlib.sha256(synthetic_wdbc_bytes).hexdigest()) == 64


def test_T05_B_DATA_HELPER_002_custom_stream_is_chunked_and_closeable() -> None:
    stream = ChunkedSyncByteStream((b"alpha", b"beta"))
    assert list(stream) == [b"alpha", b"beta"]
    assert stream.iterated_chunks == 2
    stream.close()
    assert stream.closed is True


def test_T05_B_DATA_HELPER_003_fake_clock_is_deterministic() -> None:
    clock = FakeClock()
    assert clock() == 100.0
    clock.advance(2.5)
    assert clock() == 102.5


def test_T05_B_DATA_HELPER_004_mock_transport_uses_no_socket() -> None:
    observed: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(str(request.url))
        return httpx.Response(204, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = client.get("https://example.test/synthetic")
    assert response.status_code == 204
    assert observed == ["https://example.test/synthetic"]


def _case_number(case: ContractCase) -> int:
    return int(case.test_id.rsplit("-", 1)[1])


def _default_definition(api: SimpleNamespace) -> Any:
    registry = api.get_default_dataset_registry()
    return registry.get(api.WDBC_DATASET_ID)


def _exercise_registry_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    number = _case_number(case)
    definition = _default_definition(api)
    registry = api.get_default_dataset_registry()

    if number == 1:
        assert api.WDBC_DATASET_ID == WDBC_DATASET_ID_VALUE
        assert tuple(registry.ids()) == (WDBC_DATASET_ID_VALUE,)
    elif number == 2:
        assert definition.official_name == "Breast Cancer Wisconsin (Diagnostic)"
        assert definition.version == "1995-10-31"
        assert definition.doi == "10.24432/C5DW2B"
        assert definition.license_id == "CC-BY-4.0"
        assert urlsplit(definition.license_url).scheme == "https"
        assert str(definition.citation).strip()
        assert str(definition.publisher).strip()
    elif number == 3:
        source = urlsplit(definition.source_url)
        assert source.scheme == "https"
        assert source.hostname == "archive.ics.uci.edu"
        assert source.path.endswith("/wdbc.data")
        assert source.username is None
        assert source.password is None
        assert source.query == ""
        assert source.fragment == ""
        assert source.port in {None, 443}
    elif number == 4:
        assert definition.target_filename == WDBC_TARGET_FILENAME
        assert definition.cache_relative_dir == WDBC_CACHE_RELATIVE_DIR
        cache_path = Path(definition.cache_relative_dir)
        assert not cache_path.is_absolute()
        assert ".." not in cache_path.parts
        text = definition.cache_relative_dir
        assert ":" not in text
        assert not text.startswith(("\\\\", "//"))
    elif number == 5:
        assert definition.expected_rows == 569
        assert definition.expected_columns == 32
        assert definition.feature_count == 30
        assert set(definition.allowed_labels) == {"M", "B"}
    elif number == 6:
        assert definition.max_download_bytes == MAX_DOWNLOAD_BYTES
    elif number == 7:
        assert _enum_value(definition.archive_policy) == "reject"
    elif number == 8:
        assert definition.expected_sha256 == WDBC_PIN_SHA256
        assert definition.expected_size_bytes == WDBC_PIN_SIZE_BYTES
        assert getattr(definition, "is_pinned", False) is True
    elif number == 9:
        original = definition.version
        with pytest.raises(Exception):
            definition.version = "caller-mutated"
        assert definition.version == original
    elif number == 10:
        duplicate = _make_definition(api, synthetic)
        with pytest.raises((ValueError, api.DatasetAdapterError)):
            api.DatasetRegistry((duplicate, duplicate))
    elif number == 11:
        _expect_adapter_error(
            api,
            case,
            lambda: registry.get("unknown-fixture-dataset"),
        )
    elif number == 12:
        before_cwd = Path.cwd()
        before_environment = dict(os.environ)
        before_entries = sorted(path.name for path in tmp_path.iterdir())
        capsys.readouterr()
        importlib.reload(api.module)
        captured = capsys.readouterr()
        assert Path.cwd() == before_cwd
        assert dict(os.environ) == before_environment
        assert sorted(path.name for path in tmp_path.iterdir()) == before_entries
        assert captured.out == ""
        assert captured.err == ""
    else:  # pragma: no cover - guarded by the frozen inventory
        raise AssertionError(f"unhandled registry case {case.test_id}")


@pytest.mark.parametrize("case", REG_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_registry_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Freeze the host-owned default registry and its import boundary."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_registry_case(api, case, synthetic_wdbc_bytes, tmp_path, capsys)


def _redirect_handler(
    payload: bytes,
    redirects: Mapping[str, str],
    *,
    observed: list[httpx.Request] | None = None,
    missing_content_type: bool = False,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if observed is not None:
            observed.append(request)
        current = str(request.url)
        if current in redirects:
            return httpx.Response(
                302,
                headers={"Location": redirects[current]},
                request=request,
            )
        return _success_response(
            request,
            payload,
            content_type=None if missing_content_type else "text/plain",
        )

    return handler


def _exercise_url_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    number = _case_number(case)
    forbidden = "fixture-only-secret"

    if number in {1, 2, 3, 4, 5, 6}:
        invalid_urls = {
            1: WDBC_SOURCE_URL.replace("https://", "http://", 1),
            2: WDBC_SOURCE_URL.replace(
                "https://", f"https://user:{forbidden}@", 1
            ),
            3: f"{WDBC_SOURCE_URL}?token={forbidden}",
            4: f"{WDBC_SOURCE_URL}#fragment",
            5: "https://unapproved.example.test/wdbc.data",
            6: "https://archive.ics.uci.edu/unregistered/wdbc.data",
        }
        _expect_adapter_error(
            api,
            case,
            lambda: _make_definition(
                api,
                synthetic,
                source_url=invalid_urls[number],
            ),
            forbidden=(forbidden,),
        )
        return

    definition = _make_definition(api, synthetic)
    if number == 7:
        parameters = inspect.signature(api.DatasetAdapter.fetch).parameters
        assert tuple(parameters) == ("self", "dataset_id", "cache_root", "offline")
        for forbidden_name in (
            "url",
            "source_url",
            "expected_sha256",
            "expected_size",
            "license",
            "version",
        ):
            assert forbidden_name not in parameters
        return

    if number in {8, 9}:
        destination = (
            "https://archive.ics.uci.edu/redirected/wdbc.data"
            if number == 8
            else "https://download.ics.uci.edu/wdbc.data"
        )
        allowed_redirects = (
            frozenset({"archive.ics.uci.edu"})
            if number == 8
            else frozenset({"archive.ics.uci.edu", "download.ics.uci.edu"})
        )
        definition = _make_definition(
            api,
            synthetic,
            allowed_redirect_hosts=allowed_redirects,
        )
        adapter = _make_adapter(
            api,
            definition,
            _redirect_handler(synthetic, {WDBC_SOURCE_URL: destination}),
        )
        result = adapter.fetch(
            definition.dataset_id,
            cache_root=tmp_path / f"url-{number}",
        )
        assert result.sha256 == hashlib.sha256(synthetic).hexdigest()
        return

    if number in {10, 11, 12, 13, 14}:
        secret_url = (
            "https://archive.ics.uci.edu/next/wdbc.data"
            f"?token={forbidden}"
        )
        if number == 10:
            redirects = {
                WDBC_SOURCE_URL: "https://unapproved.example.test/wdbc.data"
            }
        elif number == 11:
            redirects = {
                WDBC_SOURCE_URL: "http://archive.ics.uci.edu/wdbc.data"
            }
        elif number == 12:
            redirects = {WDBC_SOURCE_URL: secret_url}
        elif number == 13:
            loop_url = "https://archive.ics.uci.edu/loop/wdbc.data"
            redirects = {WDBC_SOURCE_URL: loop_url, loop_url: WDBC_SOURCE_URL}
        else:
            redirects = {
                WDBC_SOURCE_URL: "https://archive.ics.uci.edu/r1/wdbc.data",
                "https://archive.ics.uci.edu/r1/wdbc.data": (
                    "https://archive.ics.uci.edu/r2/wdbc.data"
                ),
                "https://archive.ics.uci.edu/r2/wdbc.data": (
                    "https://archive.ics.uci.edu/r3/wdbc.data"
                ),
            }
        adapter = _make_adapter(
            api,
            definition,
            _redirect_handler(synthetic, redirects),
            redirect_limit=2,
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=tmp_path / f"url-{number}",
            ),
            forbidden=(forbidden,),
        )
        return

    if number == 15:
        original_client = httpx.Client
        captured: dict[str, Any] = {}

        class SpyClient(original_client):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured.update(kwargs)
                super().__init__(*args, **kwargs)

        if hasattr(api.module, "httpx"):
            monkeypatch.setattr(api.module.httpx, "Client", SpyClient)
        if hasattr(api.module, "Client"):
            monkeypatch.setattr(api.module, "Client", SpyClient)
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        adapter.fetch(definition.dataset_id, cache_root=tmp_path / "client-spy")
        assert captured["follow_redirects"] is False
        assert captured["trust_env"] is False
        assert captured.get("verify", True) is True
        return

    if number == 16:
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
            monkeypatch.setenv(name, f"https://{forbidden}.example.test")
        observed: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            observed.append(request)
            return _success_response(request, synthetic)

        adapter = _make_adapter(api, definition, handler)
        result = adapter.fetch(
            definition.dataset_id,
            cache_root=tmp_path / "proxy-isolation",
        )
        assert result.sha256 == hashlib.sha256(synthetic).hexdigest()
        assert [str(request.url) for request in observed] == [WDBC_SOURCE_URL]
        return

    raise AssertionError(f"unhandled URL case {case.test_id}")


@pytest.mark.parametrize("case", URL_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_url_redirect_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Freeze source URL authority, manual redirects, and proxy isolation."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_url_case(api, case, synthetic_wdbc_bytes, tmp_path, monkeypatch)


def _http_exception_handler(
    kind: str,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        exceptions: dict[str, type[httpx.RequestError]] = {
            "connect-timeout": httpx.ConnectTimeout,
            "read-timeout": httpx.ReadTimeout,
            "write-timeout": httpx.WriteTimeout,
            "pool-timeout": httpx.PoolTimeout,
            "connect-error": httpx.ConnectError,
            "protocol-error": httpx.RemoteProtocolError,
        }
        raise exceptions[kind]("synthetic transport failure", request=request)

    return handler


def _exercise_network_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
) -> None:
    number = _case_number(case)
    definition = _make_definition(api, synthetic)

    if number <= 6:
        kinds = {
            1: "connect-timeout",
            2: "read-timeout",
            3: "write-timeout",
            4: "pool-timeout",
            5: "connect-error",
            6: "protocol-error",
        }
        adapter = _make_adapter(
            api,
            definition,
            _http_exception_handler(kinds[number]),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=tmp_path / f"net-{number}",
            ),
        )
        return

    if number in {7, 8, 9, 10}:
        statuses = {
            7: (404,),
            8: (401, 403),
            9: (429,),
            10: (500, 502, 503),
        }[number]
        for status in statuses:
            requests: list[httpx.Request] = []

            def handler(
                request: httpx.Request,
                response_status: int = status,
            ) -> httpx.Response:
                requests.append(request)
                return httpx.Response(response_status, request=request)

            adapter = _make_adapter(api, definition, handler)
            _expect_adapter_error(
                api,
                case,
                lambda: adapter.fetch(
                    definition.dataset_id,
                    cache_root=tmp_path / f"net-{number}-{status}",
                ),
            )
            assert len(requests) == 1
        return

    if number == 11:
        clock = FakeClock()

        def advance(_index: int) -> None:
            clock.advance(0.6)

        stream = ChunkedSyncByteStream(
            _split_chunks(synthetic, chunk_size=512),
            before_chunk=advance,
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return _success_response(
                request,
                synthetic,
                headers={"Content-Length": str(len(synthetic))},
                stream=stream,
            )

        cache_root = tmp_path / "total-timeout"
        adapter = _make_adapter(
            api,
            definition,
            handler,
            total_timeout_seconds=1.0,
            monotonic=clock,
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        assert not _cache_path(cache_root, definition).exists()
        assert _parts(cache_root) == []
        return

    if number == 12:
        registry = _make_registry(api, definition)
        for field in (
            "connect_timeout_seconds",
            "read_timeout_seconds",
            "total_timeout_seconds",
        ):
            for invalid in (None, -1.0):
                with pytest.raises((TypeError, ValueError)):
                    api.DatasetAdapter(
                        registry,
                        transport=httpx.MockTransport(_never_network),
                        **{field: invalid},
                    )
        return

    raise AssertionError(f"unhandled network case {case.test_id}")


@pytest.mark.parametrize("case", NET_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_timeout_http_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
) -> None:
    """Freeze HTTPX exception, status, and total-timeout classification."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_network_case(api, case, synthetic_wdbc_bytes, tmp_path)


ARCHIVE_MAGICS = (
    b"PK\x03\x04synthetic-zip",
    b"\x1f\x8b\x08synthetic-gzip",
    b"7z\xbc\xaf\x27\x1csynthetic-7z",
    b"\xfd7zXZ\x00synthetic-xz",
    b"BZh9synthetic-bzip2",
    (b"0" * 257) + b"ustar" + (b"0" * 16),
)


def _exercise_download_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
) -> None:
    number = _case_number(case)
    definition = _make_definition(api, synthetic)

    if number == 1:
        stream = ChunkedSyncByteStream(_split_chunks(synthetic, 1024))
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(
                request,
                synthetic,
                headers={"Content-Length": str(len(synthetic))},
                stream=stream,
            ),
        )
        result = adapter.fetch(definition.dataset_id, cache_root=tmp_path / "stream")
        assert result.size_bytes == len(synthetic)
        assert stream.iterated_chunks > 1
        assert stream.closed is True
        return

    if number == 2:
        stream = ChunkedSyncByteStream((synthetic,))
        definition = _make_definition(api, synthetic, max_download_bytes=100)
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(
                request,
                synthetic,
                headers={"Content-Length": "101"},
                stream=stream,
            ),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id, cache_root=tmp_path / "header-oversize"
            ),
        )
        assert stream.iterated_chunks == 0
        return

    if number in {3, 4}:
        body = b"a" * 120
        definition = _make_definition(
            api,
            body,
            max_download_bytes=100,
            expected_rows=1,
        )
        stream = ChunkedSyncByteStream((b"a" * 60, b"a" * 60))
        headers = {} if number == 3 else {"Content-Length": "10"}
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(
                request,
                body,
                headers=headers,
                stream=stream,
            ),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id, cache_root=tmp_path / f"actual-size-{number}"
            ),
        )
        assert stream.iterated_chunks <= 2
        return

    if number == 5:
        stream = ChunkedSyncByteStream(_split_chunks(synthetic))
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(
                request,
                synthetic,
                headers={"Content-Length": str(len(synthetic) + 1)},
                stream=stream,
            ),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id, cache_root=tmp_path / "length-mismatch"
            ),
        )
        return

    if number == 6:
        content_types = (
            "text/plain",
            "text/csv; charset=utf-8",
            "application/octet-stream",
        )
        for index, content_type in enumerate(content_types):
            adapter = _make_adapter(
                api,
                definition,
                lambda request, value=content_type: _success_response(
                    request, synthetic, content_type=value
                ),
            )
            result = adapter.fetch(
                definition.dataset_id,
                cache_root=tmp_path / f"content-type-{index}",
            )
            assert result.size_bytes == len(synthetic)
        return

    if number == 7:
        for index, content_type in enumerate(
            ("text/html", "application/json", "image/png", "application/pdf")
        ):
            adapter = _make_adapter(
                api,
                definition,
                lambda request, value=content_type: _success_response(
                    request, synthetic, content_type=value
                ),
            )
            _expect_adapter_error(
                api,
                case,
                lambda: adapter.fetch(
                    definition.dataset_id,
                    cache_root=tmp_path / f"bad-content-type-{index}",
                ),
            )
        return

    if number == 8:
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(
                request, synthetic, content_type=None
            ),
        )
        result = adapter.fetch(
            definition.dataset_id,
            cache_root=tmp_path / "missing-content-type-exact",
        )
        assert "content_type_missing_exact_source_exception" in set(result.warnings)
        return

    if number == 9:
        redirected = "https://archive.ics.uci.edu/other/wdbc.data"
        adapter = _make_adapter(
            api,
            definition,
            _redirect_handler(
                synthetic,
                {WDBC_SOURCE_URL: redirected},
                missing_content_type=True,
            ),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id, cache_root=tmp_path / "missing-after-redirect"
            ),
        )
        return

    if number == 10:
        for index, encoding in enumerate(("gzip", "deflate", "br", "zstd")):
            adapter = _make_adapter(
                api,
                definition,
                lambda request, value=encoding: _success_response(
                    request,
                    synthetic,
                    headers={"Content-Encoding": value},
                ),
            )
            _expect_adapter_error(
                api,
                case,
                lambda: adapter.fetch(
                    definition.dataset_id,
                    cache_root=tmp_path / f"encoding-{index}",
                ),
            )
        return

    if number in {11, 12}:
        magics = ARCHIVE_MAGICS[:1] if number == 11 else ARCHIVE_MAGICS
        for index, archive in enumerate(magics):
            archive_definition = _make_definition(api, archive)
            adapter = _make_adapter(
                api,
                archive_definition,
                lambda request, value=archive: _success_response(
                    request, value, content_type="text/plain"
                ),
            )
            _expect_adapter_error(
                api,
                case,
                lambda: adapter.fetch(
                    archive_definition.dataset_id,
                    cache_root=tmp_path / f"archive-{number}-{index}",
                ),
            )
        return

    if number in {13, 14}:
        invalid = (b"\x00" * 512) if number == 13 else b"\xff\xfe\xfd"
        invalid_definition = _make_definition(api, invalid)
        adapter = _make_adapter(
            api,
            invalid_definition,
            lambda request: _success_response(request, invalid),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                invalid_definition.dataset_id,
                cache_root=tmp_path / f"invalid-content-{number}",
            ),
        )
        return

    raise AssertionError(f"unhandled download case {case.test_id}")


@pytest.mark.parametrize("case", DL_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_streaming_header_archive_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
) -> None:
    """Freeze bounded streaming, content metadata, and archive rejection."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_download_case(api, case, synthetic_wdbc_bytes, tmp_path)


def _patch_module_os(
    api: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    replacement: Callable[..., Any],
) -> None:
    module_os = getattr(api.module, "os", None)
    if module_os is None:
        raise AssertionError("dataset module must use the standard os boundary")
    monkeypatch.setattr(module_os, name, replacement)


def _exercise_io_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    number = _case_number(case)
    definition = _make_definition(api, synthetic)
    cache_root = tmp_path / f"io-{number}"
    final_path = _cache_path(cache_root, definition)

    if number in {1, 2, 3}:
        observed_parts: list[tuple[Path, ...]] = []

        def observe(_index: int) -> None:
            parts = tuple(_parts(cache_root))
            observed_parts.append(parts)
            assert not final_path.exists()
            assert len(parts) == 1
            assert parts[0].parent == final_path.parent
            assert ".part" in parts[0].name
            assert parts[0].name.startswith(final_path.name)

        stream = ChunkedSyncByteStream(
            _split_chunks(synthetic, 1024), before_chunk=observe
        )
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(
                request,
                synthetic,
                headers={"Content-Length": str(len(synthetic))},
                stream=stream,
            ),
        )
        result = adapter.fetch(definition.dataset_id, cache_root=cache_root)
        assert observed_parts
        assert Path(result.cache_path) == final_path
        assert final_path.read_bytes() == synthetic
        assert _parts(cache_root) == []
        return

    if number == 4:
        replaced: list[tuple[Path, Path, int]] = []
        original_replace = os.replace
        stream = ChunkedSyncByteStream(_split_chunks(synthetic, 1024))

        def observed_replace(source: Any, destination: Any) -> None:
            replaced.append((Path(source), Path(destination), stream.iterated_chunks))
            original_replace(source, destination)

        _patch_module_os(api, monkeypatch, "replace", observed_replace)
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(
                request,
                synthetic,
                headers={"Content-Length": str(len(synthetic))},
                stream=stream,
            ),
        )
        adapter.fetch(definition.dataset_id, cache_root=cache_root)
        assert len(replaced) == 1
        assert replaced[0][0].parent == replaced[0][1].parent
        assert replaced[0][1] == final_path
        assert replaced[0][2] == len(_split_chunks(synthetic, 1024))
        return

    if number == 5:
        definition = _make_definition(
            api,
            synthetic,
            expected_sha256="0" * 64,
        )
        final_path = _cache_path(cache_root, definition)
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        assert not final_path.exists()
        assert _parts(cache_root) == []
        return

    if number == 6:
        invalid = _make_synthetic_wdbc_bytes(rows=568)
        definition = _make_definition(api, invalid)
        final_path = _cache_path(cache_root, definition)
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, invalid),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        assert not final_path.exists()
        assert _parts(cache_root) == []
        return

    if number == 7:
        original_open = Path.open

        def fail_part_open(path: Path, *args: Any, **kwargs: Any) -> Any:
            mode = str(args[0] if args else kwargs.get("mode", "r"))
            if ".part" in path.name and any(flag in mode for flag in "wax+"):
                raise OSError("synthetic write boundary failure")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", fail_part_open)
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        assert not final_path.exists()
        assert _parts(cache_root) == []
        return

    if number == 8:
        original_fsync = os.fsync

        def fail_fsync(_descriptor: int) -> None:
            raise OSError("synthetic durability failure")

        _patch_module_os(api, monkeypatch, "fsync", fail_fsync)
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        monkeypatch.setattr(os, "fsync", original_fsync)
        assert not final_path.exists()
        assert _parts(cache_root) == []
        return

    if number == 9:
        def fail_replace(_source: Any, _destination: Any) -> None:
            raise OSError("synthetic atomic replace failure")

        _patch_module_os(api, monkeypatch, "replace", fail_replace)
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        assert not final_path.exists()
        assert _parts(cache_root) == []
        return

    if number in {10, 11}:
        existing = _install_cache(cache_root, definition, synthetic)
        before = existing.read_bytes()
        before_digest = hashlib.sha256(before).hexdigest()
        adapter = _make_adapter(api, definition, _never_network)
        result = adapter.fetch(definition.dataset_id, cache_root=cache_root)
        after = existing.read_bytes()
        assert result.cache_hit is True
        assert after == before
        assert hashlib.sha256(after).hexdigest() == before_digest
        return

    if number == 12:
        definition = _make_definition(
            api,
            synthetic,
            expected_sha256="0" * 64,
        )
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        with pytest.raises(api.DatasetAdapterError):
            adapter.fetch(definition.dataset_id, cache_root=cache_root)
        assert _parts(cache_root) == []
        return

    if number == 13:
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        result = adapter.fetch(definition.dataset_id, cache_root=cache_root)
        installed = Path(result.cache_path)
        renamed = installed.with_name("renamed-fixture.data")
        installed.rename(renamed)
        renamed.unlink()
        assert not renamed.exists()
        return

    if number == 14:
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("fixture", encoding="utf-8")
        cache_root = blocker / "child"
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        error = _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
            forbidden=(str(tmp_path),),
        )
        assert str(tmp_path) not in repr(error)
        return

    raise AssertionError(f"unhandled I/O case {case.test_id}")


@pytest.mark.parametrize("case", IO_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_atomic_io_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Freeze same-directory parts, validation-before-replace, and cleanup."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_io_case(
        api,
        case,
        synthetic_wdbc_bytes,
        tmp_path,
        monkeypatch,
    )


def _fetch_valid_cache(
    api: SimpleNamespace,
    definition: Any,
    cache_root: Path,
    payload: bytes,
    *,
    offline: bool = False,
) -> Any:
    _install_cache(cache_root, definition, payload)
    adapter = _make_adapter(api, definition, _never_network)
    return adapter.fetch(
        definition.dataset_id,
        cache_root=cache_root,
        offline=offline,
    )


def _exercise_cache_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
) -> None:
    number = _case_number(case)
    definition = _make_definition(api, synthetic)
    cache_root = tmp_path / f"cache-{number}"
    target = _cache_path(cache_root, definition)

    if number in {1, 2}:
        result = _fetch_valid_cache(
            api,
            definition,
            cache_root,
            synthetic,
            offline=number == 2,
        )
        assert result.cache_hit is True
        assert result.offline is (number == 2)
        assert result.sha256 == hashlib.sha256(synthetic).hexdigest()
        assert result.size_bytes == len(synthetic)
        assert result.validation_report.schema_valid is True
        return

    if number == 3:
        adapter = _make_adapter(api, definition, _never_network)
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=cache_root,
                offline=True,
            ),
        )
        return

    if number in {4, 5, 6, 7, 8}:
        if number == 4:
            corrupt = synthetic[:-1] + b"x"
        elif number == 5:
            corrupt = synthetic + b"extra"
        else:
            corrupt = _make_synthetic_wdbc_bytes(rows=568)
        _install_cache(cache_root, definition, corrupt)
        before = target.read_bytes()
        adapter = _make_adapter(api, definition, _never_network)
        error_case = case
        if number == 8:
            error_case = CACHE_CASES[6]
        _expect_adapter_error(
            api,
            error_case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=cache_root,
                offline=number in {4, 5, 6},
            ),
        )
        assert target.exists()
        assert target.read_bytes() == before
        return

    if number == 9:
        older = _make_definition(
            api,
            synthetic,
            version="1995-10-30",
            cache_relative_dir="datasets/uci-wdbc-v1995-10-30",
        )
        newer = _make_definition(
            api,
            synthetic,
            version="1995-10-31",
            cache_relative_dir="datasets/uci-wdbc-v1995-10-31",
        )
        _fetch_valid_cache(api, older, cache_root, synthetic)
        _fetch_valid_cache(api, newer, cache_root, synthetic)
        assert _cache_path(cache_root, older) != _cache_path(cache_root, newer)
        assert _cache_path(cache_root, older).is_file()
        assert _cache_path(cache_root, newer).is_file()
        return

    if number == 10:
        second = _make_definition(
            api,
            synthetic,
            dataset_id="synthetic-secondary-dataset",
            cache_relative_dir="datasets/synthetic-secondary-v1",
        )
        _fetch_valid_cache(api, definition, cache_root, synthetic)
        _fetch_valid_cache(api, second, cache_root, synthetic)
        assert _cache_path(cache_root, definition) != _cache_path(cache_root, second)
        return

    if number == 11:
        target.parent.mkdir(parents=True)
        source = tmp_path / "outside-symlink-target"
        source.write_bytes(synthetic)
        try:
            target.symlink_to(source)
        except OSError as exc:
            pytest.skip(f"host cannot create a test symlink: {exc}")
        adapter = _make_adapter(api, definition, _never_network)
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        assert source.read_bytes() == synthetic
        return

    if number == 12:
        target.mkdir(parents=True)
        adapter = _make_adapter(api, definition, _never_network)
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        return

    if number == 13:
        with pytest.raises((ValueError, api.DatasetAdapterError)):
            _make_definition(
                api,
                synthetic,
                cache_relative_dir="../escape",
            )
        assert not (tmp_path / "escape").exists()
        return

    if number == 14:
        unrelated = cache_root / "keep-me.txt"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("preserve", encoding="utf-8")
        result = _fetch_valid_cache(api, definition, cache_root, synthetic)
        assert result.cache_hit is True
        assert unrelated.read_text(encoding="utf-8") == "preserve"
        return

    if number == 15:
        target.parent.mkdir(parents=True)
        part = target.with_name(f"{target.name}.part.fixture")
        part.write_bytes(synthetic)
        adapter = _make_adapter(api, definition, _never_network)
        missing_case = CACHE_CASES[2]
        _expect_adapter_error(
            api,
            missing_case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=cache_root,
                offline=True,
            ),
        )
        assert part.exists()
        assert not target.exists()
        return

    raise AssertionError(f"unhandled cache case {case.test_id}")


@pytest.mark.parametrize("case", CACHE_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_cache_offline_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
) -> None:
    """Freeze revalidated cache hits, offline policy, and containment."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_cache_case(api, case, synthetic_wdbc_bytes, tmp_path)


def _exercise_lock_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
) -> None:
    number = _case_number(case)
    definition = _make_definition(api, synthetic)
    cache_root = tmp_path / f"lock-{number}"

    if number in {1, 5}:
        entered = threading.Event()
        release = threading.Event()

        def handler(request: httpx.Request) -> httpx.Response:
            entered.set()
            if not release.wait(timeout=5):
                raise AssertionError("test lock release signal timed out")
            return _success_response(request, synthetic)

        first_adapter = _make_adapter(
            api,
            definition,
            handler,
            lock_timeout_seconds=0.0,
        )
        second_adapter = _make_adapter(
            api,
            definition,
            _never_network,
            lock_timeout_seconds=0.0,
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(
                first_adapter.fetch,
                definition.dataset_id,
                cache_root=cache_root,
            )
            assert entered.wait(timeout=5)
            _expect_adapter_error(
                api,
                case,
                lambda: second_adapter.fetch(
                    definition.dataset_id,
                    cache_root=cache_root,
                ),
            )
            release.set()
            assert first.result(timeout=5).size_bytes == len(synthetic)
        assert len(list(cache_root.rglob(WDBC_TARGET_FILENAME))) == 1
        assert _parts(cache_root) == []
        return

    if number in {2, 3}:
        if number == 2:
            first_definition = _make_definition(
                api,
                synthetic,
                version="fixture-v1",
                cache_relative_dir="datasets/fixture-v1",
            )
            second_definition = _make_definition(
                api,
                synthetic,
                version="fixture-v2",
                cache_relative_dir="datasets/fixture-v2",
            )
        else:
            first_definition = _make_definition(
                api,
                synthetic,
                dataset_id="fixture-dataset-one",
                cache_relative_dir="datasets/fixture-one",
            )
            second_definition = _make_definition(
                api,
                synthetic,
                dataset_id="fixture-dataset-two",
                cache_relative_dir="datasets/fixture-two",
            )

        def adapter_for(item: Any) -> Any:
            return _make_adapter(
                api,
                item,
                lambda request: _success_response(request, synthetic),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    adapter_for(item).fetch,
                    item.dataset_id,
                    cache_root=cache_root,
                )
                for item in (first_definition, second_definition)
            ]
            results = [future.result(timeout=5) for future in futures]
        assert {result.size_bytes for result in results} == {len(synthetic)}
        return

    if number == 4:
        target = _cache_path(cache_root, definition)
        target.parent.mkdir(parents=True)
        outside = tmp_path / "outside-lock"
        outside.write_text("fixture", encoding="utf-8")
        candidate_names = (
            f"{target.name}.lock",
            f".{target.name}.lock",
            "dataset.lock",
        )
        created: Path | None = None
        for name in candidate_names:
            candidate = target.parent / name
            try:
                candidate.symlink_to(outside)
                created = candidate
                break
            except OSError:
                continue
        if created is None:
            pytest.skip("host cannot create a lock symlink probe")
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
        )
        assert outside.read_text(encoding="utf-8") == "fixture"
        return

    if number == 6:
        failing = _make_adapter(
            api,
            definition,
            _http_exception_handler("connect-error"),
        )
        with pytest.raises(api.DatasetAdapterError):
            failing.fetch(definition.dataset_id, cache_root=cache_root)
        succeeding = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        result = succeeding.fetch(definition.dataset_id, cache_root=cache_root)
        assert result.size_bytes == len(synthetic)
        return

    if number == 7:
        first = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        first.fetch(definition.dataset_id, cache_root=cache_root)
        second = _make_adapter(api, definition, _never_network)
        assert second.fetch(
            definition.dataset_id,
            cache_root=cache_root,
        ).cache_hit is True
        return

    if number == 8:
        private_marker = "fixture-only-private-marker"
        adapter = _make_adapter(
            api,
            definition,
            _http_exception_handler("connect-error"),
        )
        with pytest.raises(api.DatasetAdapterError) as captured:
            adapter.fetch(definition.dataset_id, cache_root=cache_root)
        public = f"{captured.value!s}\n{captured.value!r}"
        assert private_marker not in public
        assert str(tmp_path) not in public
        assert os.environ.get("USERNAME", "") not in public
        return

    raise AssertionError(f"unhandled lock case {case.test_id}")


@pytest.mark.parametrize("case", LOCK_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_lock_concurrency_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
) -> None:
    """Freeze lock scope, timeout, release, and safe diagnostics."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_lock_case(api, case, synthetic_wdbc_bytes, tmp_path)


def _inspect_candidate(
    api: SimpleNamespace,
    payload: bytes,
    staging_root: Path,
    *,
    definition_overrides: Mapping[str, Any] | None = None,
) -> Any:
    definition = _make_definition(
        api,
        payload,
        pinned=False,
        **dict(definition_overrides or {}),
    )
    adapter = _make_adapter(
        api,
        definition,
        lambda request: _success_response(request, payload),
    )
    return adapter.inspect_unpinned_candidate(
        definition.dataset_id,
        staging_root=staging_root,
    )


def _invalid_schema_payloads(number: int) -> tuple[bytes, ...]:
    if number == 2:
        return (_make_synthetic_wdbc_bytes(rows=568),)
    if number == 3:
        return (_make_synthetic_wdbc_bytes(rows=570),)
    if number == 4:
        return (_make_synthetic_wdbc_bytes(columns=31),)
    if number == 5:
        return (_make_synthetic_wdbc_bytes(columns=33),)
    if number == 6:
        return (_make_synthetic_wdbc_bytes(label="X"),)
    if number == 7:
        return (_make_synthetic_wdbc_bytes(label=""),)
    if number == 8:
        return (_make_synthetic_wdbc_bytes(duplicate_id=True),)
    if number == 9:
        return (_make_synthetic_wdbc_bytes(blank_id=True),)
    if number == 10:
        return (_make_synthetic_wdbc_bytes(blank_feature=True),)
    if number == 11:
        return (_make_synthetic_wdbc_bytes(feature_text="not-a-number"),)
    if number == 12:
        return tuple(
            _make_synthetic_wdbc_bytes(feature_text=value)
            for value in ("NaN", "nan", "Inf", "Infinity", "-Infinity")
        )
    if number == 13:
        return tuple(
            _make_synthetic_wdbc_bytes(feature_text=value)
            for value in ("true", "false", "True", "False")
        )
    if number == 14:
        return (_make_synthetic_wdbc_bytes(add_header=True),)
    if number == 15:
        return (b"",)
    if number == 16:
        return (
            _make_synthetic_wdbc_bytes(add_blank_row=True),
            _make_synthetic_wdbc_bytes(columns=33),
            _make_synthetic_wdbc_bytes(add_nul=True),
        )
    raise AssertionError(f"no invalid schema payload for case {number}")


def _exercise_schema_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
) -> None:
    number = _case_number(case)
    if number == 1:
        candidate = _inspect_candidate(
            api,
            synthetic,
            tmp_path / "valid-candidate",
        )
        assert candidate.validation_report.schema_valid is True
        return

    if 2 <= number <= 16:
        for index, invalid in enumerate(_invalid_schema_payloads(number)):
            _expect_adapter_error(
                api,
                case,
                lambda value=invalid, suffix=index: _inspect_candidate(
                    api,
                    value,
                    tmp_path / f"invalid-{number}-{suffix}",
                ),
            )
        return

    candidate = _inspect_candidate(
        api,
        synthetic,
        tmp_path / f"report-{number}",
    )
    report = candidate.validation_report
    if number == 17:
        assert isinstance(report, api.DatasetValidationReport)
        assert report.row_count == 569
        assert report.column_count == 32
        assert report.feature_count == 30
        assert report.unique_id_count == 569
        assert set(report.labels) == {"M", "B"}
        assert report.finite_feature_values is True
        assert report.missing_value_count == 0
        assert report.duplicate_id_count == 0
        assert report.schema_valid is True
        assert tuple(report.errors) == ()
        return

    if number == 18:
        dumped = _public_dump(report)
        assert set(dumped).issuperset(
            {
                "row_count",
                "column_count",
                "feature_count",
                "unique_id_count",
                "labels",
                "finite_feature_values",
                "missing_value_count",
                "duplicate_id_count",
                "schema_valid",
                "errors",
                "warnings",
            }
        )
        first_row = synthetic.splitlines()[0].decode("utf-8")
        assert first_row not in repr(dumped)
        assert not any("row" in key and isinstance(value, list) for key, value in dumped.items())
        return

    raise AssertionError(f"unhandled schema case {case.test_id}")


@pytest.mark.parametrize("case", SCHEMA_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_wdbc_schema_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
) -> None:
    """Freeze strict row, column, identifier, label, and finite-value checks."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_schema_case(api, case, synthetic_wdbc_bytes, tmp_path)


def _resolved_fixture(
    api: SimpleNamespace,
    payload: bytes,
    cache_root: Path,
) -> tuple[Any, Any, Any]:
    definition = _make_definition(api, payload)
    adapter = _make_adapter(
        api,
        definition,
        lambda request: _success_response(request, payload),
    )
    resolved = adapter.fetch(definition.dataset_id, cache_root=cache_root)
    return definition, adapter, resolved


def _exercise_license_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
) -> None:
    number = _case_number(case)
    if number == 1:
        definition = _default_definition(api)
        assert definition.license_id == "CC-BY-4.0"
        assert urlsplit(definition.license_url).scheme == "https"
        assert definition.doi == "10.24432/C5DW2B"
        assert str(definition.citation).strip()
        assert str(definition.publisher).strip()
        assert definition.version == "1995-10-31"
        return

    if number in {2, 3, 4, 5}:
        overrides = {
            2: {"license_id": ""},
            3: {"license_url": ""},
            4: {"citation": ""},
            5: {"license_url": "http://example.test/license"},
        }[number]
        _expect_adapter_error(
            api,
            case,
            lambda: _make_definition(api, synthetic, **overrides),
        )
        return

    definition, _adapter, resolved = _resolved_fixture(
        api,
        synthetic,
        tmp_path / f"license-{number}",
    )
    manifest = resolved.to_dataset_manifest()
    if number == 6:
        assert manifest.dataset_id == definition.dataset_id
        assert manifest.source_uri == definition.source_url
        assert manifest.license == definition.license_id
        assert manifest.version == definition.version
        assert manifest.sha256 == definition.expected_sha256
        assert manifest.size_bytes == definition.expected_size_bytes
        return

    if number == 7:
        dumped = _public_dump(manifest)
        forbidden_fields = {
            "cache_path",
            "cookie",
            "token",
            "username",
            "question_text",
            "question_catalog",
        }
        assert forbidden_fields.isdisjoint({key.casefold() for key in dumped})
        assert str(tmp_path) not in repr(dumped)
        return

    raise AssertionError(f"unhandled license case {case.test_id}")


@pytest.mark.parametrize("case", LICENSE_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_license_provenance_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
) -> None:
    """Freeze provenance completeness and safe DatasetManifest conversion."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_license_case(api, case, synthetic_wdbc_bytes, tmp_path)


def _candidate_summary(candidate: Any) -> Mapping[str, Any]:
    method = getattr(candidate, "public_summary", None)
    if not callable(method):
        raise AssertionError("DatasetPinCandidate must expose public_summary()")
    summary = method()
    if hasattr(summary, "model_dump"):
        return summary.model_dump(mode="python")
    if not isinstance(summary, Mapping):
        raise AssertionError("candidate public_summary() must return a mapping")
    return summary


def _exercise_pin_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
) -> None:
    number = _case_number(case)
    if number in {1, 2}:
        overrides: dict[str, Any] = {}
        if number == 1:
            overrides = {"expected_sha256": None}
        else:
            overrides = {"expected_size_bytes": None}
        definition = _make_definition(api, synthetic, **overrides)
        adapter = _make_adapter(api, definition, _never_network)
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=tmp_path / f"unpinned-{number}",
            ),
        )
        return

    if number == 3:
        parameters = inspect.signature(api.DatasetAdapter.fetch).parameters
        assert tuple(parameters) == ("self", "dataset_id", "cache_root", "offline")
        assert {
            "expected_sha256",
            "expected_size",
            "source_url",
            "license",
            "version",
        }.isdisjoint(parameters)
        return

    if number in {4, 5, 6, 7}:
        registry = api.get_default_dataset_registry()
        definition_before = registry.get(api.WDBC_DATASET_ID)
        before = _public_dump(definition_before)
        candidate = _inspect_candidate(
            api,
            synthetic,
            tmp_path / f"candidate-{number}",
        )
        if number == 4:
            candidate_path = Path(candidate.candidate_path)
            assert candidate_path.is_file()
            assert candidate_path.resolve().is_relative_to(
                (tmp_path / f"candidate-{number}").resolve()
            )
            assert candidate.computed_sha256 == hashlib.sha256(synthetic).hexdigest()
            assert candidate.size_bytes == len(synthetic)
            assert candidate.validation_report.schema_valid is True
            assert candidate.formal_use_allowed is False
            assert candidate.cache_installed is False
            assert not (tmp_path / WDBC_CACHE_RELATIVE_DIR).exists()
        elif number == 5:
            assert not hasattr(candidate, "to_dataset_manifest")
            assert not isinstance(candidate, api.ResolvedDataset)
        elif number == 6:
            after = _public_dump(registry.get(api.WDBC_DATASET_ID))
            assert after == before
            assert after["expected_sha256"] == WDBC_PIN_SHA256
            assert after["expected_size_bytes"] == WDBC_PIN_SIZE_BYTES
        else:
            summary = dict(_candidate_summary(candidate))
            assert summary["computed_sha256"] == hashlib.sha256(synthetic).hexdigest()
            assert summary["size_bytes"] == len(synthetic)
            assert summary["formal_use_allowed"] is False
            assert "candidate_path" not in summary
            assert str(tmp_path) not in repr(summary)
            assert "validated for formal run" not in repr(summary).casefold()
        return

    if number == 8:
        _definition, _adapter, resolved = _resolved_fixture(
            api,
            synthetic,
            tmp_path / "pinned-success",
        )
        assert isinstance(resolved, api.ResolvedDataset)
        assert resolved.sha256 == hashlib.sha256(synthetic).hexdigest()
        assert resolved.size_bytes == len(synthetic)
        return

    if number == 9:
        definition = _make_definition(
            api,
            synthetic,
            expected_sha256="0" * 64,
        )
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=tmp_path / "pin-bad-sha",
            ),
        )
        return

    if number == 10:
        definition = _make_definition(
            api,
            synthetic,
            expected_size_bytes=len(synthetic) + 1,
        )
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        _expect_adapter_error(
            api,
            case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=tmp_path / "pin-bad-size",
            ),
        )
        return

    raise AssertionError(f"unhandled pin case {case.test_id}")


@pytest.mark.parametrize("case", PIN_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_pinned_unpinned_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
) -> None:
    """Freeze formal-use pin gates and the separate candidate workflow."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_pin_case(api, case, synthetic_wdbc_bytes, tmp_path)


def _exercise_security_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    number = _case_number(case)
    definition = _make_definition(api, synthetic)
    cache_root = tmp_path / f"security-{number}"
    observed: list[httpx.Request] = []

    if number in {1, 2}:
        def handler(request: httpx.Request) -> httpx.Response:
            observed.append(request)
            return _success_response(request, synthetic)

        adapter = _make_adapter(api, definition, handler)
        adapter.fetch(definition.dataset_id, cache_root=cache_root)
        assert len(observed) == 1
        lowered = {name.casefold() for name in observed[0].headers}
        forbidden_header = "authorization" if number == 1 else "cookie"
        assert forbidden_header not in lowered
        return

    if number == 3:
        redirected = "https://archive.ics.uci.edu/redirect/wdbc.data"

        def handler(request: httpx.Request) -> httpx.Response:
            observed.append(request)
            if str(request.url) == WDBC_SOURCE_URL:
                return httpx.Response(
                    302,
                    headers={
                        "Location": redirected,
                        "Set-Cookie": "fixture_cookie=fixture-only",
                    },
                    request=request,
                )
            return _success_response(request, synthetic)

        adapter = _make_adapter(api, definition, handler)
        adapter.fetch(definition.dataset_id, cache_root=cache_root)
        assert len(observed) == 2
        assert "cookie" not in {name.casefold() for name in observed[1].headers}
        return

    if number == 4:
        fake_values = {
            name: f"fixture-only-{name.casefold()}-value"
            for name in (
                "UCI_TOKEN",
                "API_KEY",
                "TOKEN",
                "SECRET",
                "PASSWORD",
                "GH_TOKEN",
                "GITHUB_TOKEN",
            )
        }
        for name, value in fake_values.items():
            monkeypatch.setenv(name, value)

        def handler(request: httpx.Request) -> httpx.Response:
            observed.append(request)
            return _success_response(request, synthetic)

        adapter = _make_adapter(api, definition, handler)
        result = adapter.fetch(definition.dataset_id, cache_root=cache_root)
        public = f"{observed[0].url!s}\n{dict(observed[0].headers)!r}\n{result!r}"
        assert all(value not in public for value in fake_values.values())
        return

    if number == 5:
        marker = "fixture-only-dotenv-marker"
        (tmp_path / ".env").write_text(
            f"UCI_TOKEN={marker}\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        def handler(request: httpx.Request) -> httpx.Response:
            observed.append(request)
            return _success_response(request, synthetic)

        adapter = _make_adapter(api, definition, handler)
        result = adapter.fetch(definition.dataset_id, cache_root=cache_root)
        assert marker not in repr(result)
        assert marker not in repr(observed[0].headers)
        return

    if number == 6:
        marker = "fixture-only-url-secret"
        redirected = f"{WDBC_SOURCE_URL}?token={marker}"
        adapter = _make_adapter(
            api,
            definition,
            _redirect_handler(synthetic, {WDBC_SOURCE_URL: redirected}),
        )
        synthetic_case = ContractCase(
            case.test_id,
            case.summary,
            "dataset_redirect_forbidden",
            "redirect",
            False,
        )
        _expect_adapter_error(
            api,
            synthetic_case,
            lambda: adapter.fetch(definition.dataset_id, cache_root=cache_root),
            forbidden=(marker,),
        )
        return

    if number in {7, 8}:
        blocker = tmp_path / "blocker"
        blocker.write_text("fixture", encoding="utf-8")
        invalid_root = blocker / "child"
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        with pytest.raises(api.DatasetAdapterError) as captured:
            adapter.fetch(definition.dataset_id, cache_root=invalid_root)
        public = f"{captured.value!s}\n{captured.value!r}"
        assert str(tmp_path) not in public
        assert str(Path.cwd().resolve()) not in public
        return

    if number == 9:
        capsys.readouterr()
        adapter = _make_adapter(
            api,
            definition,
            lambda request: _success_response(request, synthetic),
        )
        adapter.fetch(definition.dataset_id, cache_root=cache_root)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
        return

    if number == 10:
        original_client = httpx.Client

        class ForbiddenClient(original_client):
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                raise AssertionError("offline mode constructed an HTTP client")

        if hasattr(api.module, "httpx"):
            monkeypatch.setattr(api.module.httpx, "Client", ForbiddenClient)
        if hasattr(api.module, "Client"):
            monkeypatch.setattr(api.module, "Client", ForbiddenClient)
        adapter = api.DatasetAdapter(_make_registry(api, definition))
        offline_case = ContractCase(
            case.test_id,
            case.summary,
            "dataset_offline_missing",
            "cache",
            False,
        )
        _expect_adapter_error(
            api,
            offline_case,
            lambda: adapter.fetch(
                definition.dataset_id,
                cache_root=cache_root,
                offline=True,
            ),
        )
        return

    if number == 11:
        archive = ARCHIVE_MAGICS[0]
        archive_definition = _make_definition(api, archive)
        before = set(tmp_path.rglob("*"))
        adapter = _make_adapter(
            api,
            archive_definition,
            lambda request: _success_response(request, archive),
        )
        archive_case = ContractCase(
            case.test_id,
            case.summary,
            "dataset_archive_unexpected",
            "download",
            False,
        )
        _expect_adapter_error(
            api,
            archive_case,
            lambda: adapter.fetch(
                archive_definition.dataset_id,
                cache_root=cache_root,
            ),
        )
        after = set(tmp_path.rglob("*"))
        created_files = {path for path in after - before if path.is_file()}
        assert created_files == set()
        return

    if number == 12:
        source = inspect.getsource(api.module)
        forbidden_snippets = (
            "shell" + "=" + "True",
            "os" + "." + "system",
            "sub" + "process",
            "ev" + "al(",
            "ex" + "ec(",
        )
        assert all(snippet not in source for snippet in forbidden_snippets)
        return

    raise AssertionError(f"unhandled security case {case.test_id}")


@pytest.mark.parametrize("case", SEC_CASES, ids=lambda case: case.test_id)
def test_T05_B_DATA_http_secret_environment_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Freeze request secrecy, environment isolation, and safe diagnostics."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_security_case(
        api,
        case,
        synthetic_wdbc_bytes,
        tmp_path,
        monkeypatch,
        capsys,
    )


def _manifest_copy(api: SimpleNamespace, manifest: Any, **updates: Any) -> Any:
    dumped = _public_dump(manifest)
    dumped.update(updates)
    if hasattr(api.DatasetManifest, "model_validate"):
        return api.DatasetManifest.model_validate(dumped)
    return api.DatasetManifest(**dumped)


def _exercise_integration_case(
    api: SimpleNamespace,
    case: ContractCase,
    synthetic: bytes,
    tmp_path: Path,
) -> None:
    number = _case_number(case)
    cache_root = tmp_path / f"integration-{number}"
    definition, adapter, resolved = _resolved_fixture(api, synthetic, cache_root)
    manifest = resolved.to_dataset_manifest()

    if number == 1:
        assert isinstance(manifest, api.DatasetManifest)
        return

    if number == 2:
        assert manifest.dataset_id == resolved.dataset_id
        assert manifest.source_uri == resolved.source_url
        assert manifest.license == definition.license_id
        assert manifest.version == resolved.version
        assert manifest.sha256 == resolved.sha256
        assert manifest.size_bytes == resolved.size_bytes
        return

    if number == 3:
        dumped = _public_dump(manifest)
        assert "cache_path" not in dumped
        assert str(cache_root.resolve()) not in repr(dumped)
        return

    resolver = adapter.build_resolver(cache_root)
    if number == 4:
        assert callable(resolver)
        signature = inspect.signature(resolver)
        assert len(signature.parameters) == 1
        resolved_path = resolver(manifest)
        assert isinstance(resolved_path, Path)
        return

    if number == 5:
        resolved_path = resolver(manifest)
        assert resolved_path.is_file()
        assert not resolved_path.is_symlink()
        assert resolved_path.resolve().is_relative_to(cache_root.resolve())
        assert hashlib.sha256(resolved_path.read_bytes()).hexdigest() == manifest.sha256
        assert resolved_path.stat().st_size == manifest.size_bytes
        return

    if number == 6:
        cache_path = Path(resolved.cache_path)
        cache_path.write_bytes(synthetic + b"tampered")
        with pytest.raises(api.DatasetAdapterError):
            resolver(manifest)
        return

    if number == 7:
        requests_before = list(cache_root.rglob("*"))
        assert resolver(manifest) == Path(resolved.cache_path)
        requests_after = list(cache_root.rglob("*"))
        assert requests_after == requests_before
        return

    if number == 8:
        variants = (
            _manifest_copy(api, manifest, dataset_id="unknown-fixture-dataset"),
            _manifest_copy(api, manifest, version="mismatched-version"),
            _manifest_copy(api, manifest, sha256="0" * 64),
            _manifest_copy(api, manifest, size_bytes=manifest.size_bytes + 1),
        )
        for invalid in variants:
            with pytest.raises(api.DatasetAdapterError):
                resolver(invalid)
        return

    if number == 9:
        path = resolver(manifest)
        assert path.resolve().is_relative_to(cache_root.resolve())
        assert ".." not in path.relative_to(cache_root).parts
        return

    raise AssertionError(f"unhandled integration case {case.test_id}")


@pytest.mark.parametrize(
    "case",
    INTEGRATION_CASES,
    ids=lambda case: case.test_id,
)
def test_T05_B_DATA_runner_resolver_integration_contract(
    require_symbol: Callable[[str, str, str], Any],
    case: ContractCase,
    synthetic_wdbc_bytes: bytes,
    tmp_path: Path,
) -> None:
    """Freeze DatasetManifest conversion and resolver fail-closed behavior."""

    api = _require_api(require_symbol, case.test_id)
    _exercise_integration_case(api, case, synthetic_wdbc_bytes, tmp_path)


def test_T05_B_DATA_HELPER_005_inventory_is_complete_and_unique() -> None:
    """Self-check the 147 frozen behavior IDs without production imports."""

    expected_counts = {
        "REG": 12,
        "URL": 16,
        "NET": 12,
        "DL": 14,
        "IO": 14,
        "CACHE": 15,
        "LOCK": 8,
        "SCHEMA": 18,
        "LICENSE": 7,
        "PIN": 10,
        "SEC": 12,
        "INTEGRATION": 9,
    }
    identifiers = [case.test_id for case in ALL_CONTRACT_CASES]
    assert len(identifiers) == 147
    assert len(set(identifiers)) == len(identifiers)
    for family, expected in expected_counts.items():
        prefix = f"T05-B-DATA-{family}-"
        assert sum(identifier.startswith(prefix) for identifier in identifiers) == expected
