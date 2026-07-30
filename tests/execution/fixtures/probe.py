"""Deterministic subprocess probe used by the T05 execution runner tests."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import struct
import sys
import time
from pathlib import Path, PurePosixPath, PureWindowsPath


_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _workspace_path(raw_path: str) -> Path:
    """Resolve a fixture path without permitting it to leave the probe cwd."""

    if (
        not raw_path
        or "\x00" in raw_path
        or "%" in raw_path
        or "\\" in raw_path
        or ":" in raw_path
    ):
        raise ValueError("probe path must be a non-empty, plain relative POSIX path")

    posix_path = PurePosixPath(raw_path)
    windows_path = PureWindowsPath(raw_path)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        raise ValueError("probe path must remain relative to the workspace")
    for part in posix_path.parts:
        normalized = part.rstrip(" .")
        basename = normalized.split(".", 1)[0].upper()
        if normalized != part or basename in _WINDOWS_RESERVED_NAMES:
            raise ValueError("probe path contains an unsafe Windows component")

    workspace = Path.cwd().resolve(strict=True)
    candidate = (workspace / Path(*posix_path.parts)).resolve(strict=False)
    if candidate != workspace and workspace not in candidate.parents:
        raise ValueError("probe path resolves outside the workspace")
    return candidate


def _positive_bounded(value: str, *, maximum: int) -> int:
    parsed = int(value)
    if parsed < 1 or parsed > maximum:
        raise argparse.ArgumentTypeError(f"value must be between 1 and {maximum}")
    return parsed


def _nonnegative_seconds(value: str) -> float:
    parsed = float(value)
    if parsed < 0.0 or parsed > 30.0:
        raise argparse.ArgumentTypeError("seconds must be between 0 and 30")
    return parsed


def _create_windows_junction(destination: Path, target: Path) -> None:
    """Create a test-only directory junction without invoking a shell."""

    if os.name != "nt":
        raise OSError("directory junctions are only available on Windows")
    target = target.resolve(strict=True)
    if not target.is_dir():
        raise OSError("junction target must be an existing directory")
    destination.mkdir()

    substitute = f"\\??\\{target}"
    display = str(target)
    substitute_bytes = substitute.encode("utf-16-le")
    display_bytes = display.encode("utf-16-le")
    path_buffer = substitute_bytes + b"\x00\x00" + display_bytes + b"\x00\x00"
    reparse_data_length = 8 + len(path_buffer)
    reparse_data = struct.pack(
        "<LHHHHHH",
        0xA0000003,
        reparse_data_length,
        0,
        0,
        len(substitute_bytes),
        len(substitute_bytes) + 2,
        len(display_bytes),
    ) + path_buffer

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.DeviceIoControl.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    kernel32.DeviceIoControl.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.CreateFileW(
        str(destination),
        0x40000000,
        0,
        None,
        3,
        0x00200000 | 0x02000000,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        destination.rmdir()
        raise OSError(error, "CreateFileW failed for junction probe")
    try:
        input_buffer = ctypes.create_string_buffer(reparse_data)
        returned = ctypes.c_uint32()
        succeeded = kernel32.DeviceIoControl(
            handle,
            0x000900A4,
            input_buffer,
            len(reparse_data),
            None,
            0,
            ctypes.byref(returned),
            None,
        )
        if not succeeded:
            error = ctypes.get_last_error()
            raise OSError(error, "FSCTL_SET_REPARSE_POINT failed")
    finally:
        kernel32.CloseHandle(handle)
    if not destination.is_junction():
        destination.rmdir()
        raise OSError("created reparse point is not a directory junction")


def _add_subcommands(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="operation", required=True)

    subparsers.add_parser("noop")

    fail = subparsers.add_parser("fail")
    fail.add_argument(
        "--code",
        "--exit-code",
        dest="exit_code",
        default=7,
        type=lambda value: _positive_bounded(value, maximum=125),
    )
    fail.add_argument("--message", default="deterministic probe failure")
    fail.add_argument("--stdout", default="")
    fail.add_argument("--stderr", default=None)

    sleep = subparsers.add_parser("sleep")
    sleep.add_argument("--seconds", required=True, type=_nonnegative_seconds)

    output = subparsers.add_parser("output")
    output.add_argument("--stdout", "--stdout-text", dest="stdout_text", default="")
    output.add_argument("--stderr", "--stderr-text", dest="stderr_text", default="")
    output.add_argument("--stdout-hex", default="")
    output.add_argument("--stderr-hex", default="")
    output.add_argument(
        "--repeat",
        default=1,
        type=lambda value: _positive_bounded(value, maximum=100_000),
    )

    artifact = subparsers.add_parser("artifact")
    artifact.add_argument("relative_path", nargs="?")
    artifact.add_argument("--path", dest="path_option")
    artifact.add_argument("--content", default="")
    artifact.add_argument("--metric-name")
    artifact.add_argument("--metric-value", type=float)
    artifact.add_argument("--metric-unit")
    artifact.add_argument("--metric-source")
    artifact.add_argument(
        "--repeat",
        default=1,
        type=lambda value: _positive_bounded(value, maximum=100_000),
    )
    artifact.add_argument(
        "--kind",
        choices=("file", "directory", "directory-symlink", "junction"),
        default="file",
    )

    environment = subparsers.add_parser("env")
    environment.add_argument("--name", action="append", default=[])

    argv = subparsers.add_parser("argv")
    argv.add_argument("--value", action="append", default=[])
    argv.add_argument("values", nargs=argparse.REMAINDER)

    mutate_copy = subparsers.add_parser("mutate-copy")
    mutate_copy.add_argument("relative_path", nargs="?")
    mutate_copy.add_argument("--path", dest="path_option")
    mutate_copy.add_argument("--content")
    mutate_copy.add_argument("--append-text")


def _run(args: argparse.Namespace) -> int:
    if args.operation == "noop":
        return 0

    if args.operation == "fail":
        sys.stdout.write(args.stdout)
        sys.stderr.write(args.stderr if args.stderr is not None else args.message)
        sys.stdout.flush()
        sys.stderr.flush()
        return args.exit_code

    if args.operation == "sleep":
        time.sleep(args.seconds)
        return 0

    if args.operation == "output":
        for _ in range(args.repeat):
            sys.stdout.write(args.stdout_text)
            sys.stderr.write(args.stderr_text)
        sys.stdout.flush()
        sys.stderr.flush()
        if args.stdout_hex:
            sys.stdout.buffer.write(bytes.fromhex(args.stdout_hex))
            sys.stdout.buffer.flush()
        if args.stderr_hex:
            sys.stderr.buffer.write(bytes.fromhex(args.stderr_hex))
            sys.stderr.buffer.flush()
        return 0

    if args.operation == "artifact":
        raw_path = args.path_option or args.relative_path
        if not raw_path:
            raise ValueError("artifact path is required")
        destination = _workspace_path(raw_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if args.kind == "file":
            metric_args = (args.metric_name, args.metric_value, args.metric_unit)
            if any(value is not None for value in metric_args):
                if any(value is None for value in metric_args):
                    raise ValueError("all metric fields are required together")
                metric_document = {
                    "metric": {
                        "name": args.metric_name,
                        "unit": args.metric_unit,
                        "value": args.metric_value,
                    }
                }
                if args.metric_source is not None:
                    metric_document["metric"]["source"] = args.metric_source
                content = (
                    json.dumps(
                        metric_document,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
            else:
                content = args.content.encode("utf-8")
            if len(content) * args.repeat > 1_048_576:
                raise ValueError("probe artifact exceeds the one-megabyte fixture cap")
            with destination.open("wb") as stream:
                for _ in range(args.repeat):
                    stream.write(content)
        elif args.kind == "directory":
            destination.mkdir()
        elif args.kind == "directory-symlink":
            destination.symlink_to(
                Path("..") / ".." / "outside-probe-target",
                target_is_directory=False,
            )
        else:
            _create_windows_junction(
                destination,
                Path.cwd().parent / "outside-probe-target",
            )
        return 0

    if args.operation == "env":
        invalid_names = [name for name in args.name if not _ENVIRONMENT_NAME.fullmatch(name)]
        if invalid_names:
            raise ValueError("invalid environment variable name")
        selected = {name: os.environ.get(name) for name in sorted(set(args.name))}
        sys.stdout.write(json.dumps(selected, sort_keys=True, separators=(",", ":")))
        sys.stdout.flush()
        return 0

    if args.operation == "argv":
        values = [*args.value, *args.values]
        sys.stdout.write(json.dumps(values, ensure_ascii=False, separators=(",", ":")))
        sys.stdout.flush()
        return 0

    if args.operation == "mutate-copy":
        raw_path = args.path_option or args.relative_path
        if not raw_path:
            raise ValueError("workspace copy path is required")
        destination = _workspace_path(raw_path)
        if not destination.is_file():
            raise ValueError("workspace copy must be an existing regular file")
        if args.append_text is not None:
            with destination.open("ab") as stream:
                stream.write(args.append_text.encode("utf-8"))
        else:
            content = args.content or "mutated workspace copy"
            destination.write_bytes(content.encode("utf-8"))
        return 0

    raise AssertionError(f"unhandled probe operation: {args.operation}")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    sys.stderr.reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser()
    _add_subcommands(parser)
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
