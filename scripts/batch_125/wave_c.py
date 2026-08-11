"""Provider-free T07 Wave C monitoring and package validation CLI."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.batch.errors import BatchRunnerError
from app.batch.wave_c_hardening import (
    inspect_wave_c_status,
    release_pause,
    request_pause,
    validate_wave_c_package,
    write_validation_receipts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or validate a T07 Wave C batch without Provider calls",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="read a batch status snapshot")
    status.add_argument("--batch-root", type=Path, required=True)

    pause = commands.add_parser("pause", help="request a safe stop before next job")
    pause.add_argument("--batch-root", type=Path, required=True)
    pause.add_argument("--requested-by", required=True)
    pause.add_argument("--reason", required=True)

    resume = commands.add_parser(
        "resume",
        help="archive an acknowledged pause marker before resuming",
    )
    resume.add_argument("--batch-root", type=Path, required=True)
    resume.add_argument("--released-by", required=True)
    resume.add_argument("--expected-pause-sha256", required=True)

    validate = commands.add_parser(
        "validate",
        help="fail-closed validation of a completed 125-question package",
    )
    validate.add_argument("--batch-root", type=Path, required=True)
    validate.add_argument("--expected-code-sha")
    validate.add_argument("--write-receipts", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            payload = inspect_wave_c_status(args.batch_root).to_dict()
            exit_code = 0
        elif args.command == "pause":
            path = request_pause(
                args.batch_root,
                requested_by=args.requested_by,
                reason=args.reason,
            )
            payload = {
                "status": "pause_requested",
                "path": str(path),
                "provider_calls": 0,
            }
            exit_code = 0
        elif args.command == "resume":
            path = release_pause(
                args.batch_root,
                released_by=args.released_by,
                expected_pause_sha256=args.expected_pause_sha256,
            )
            payload = {
                "status": "pause_released",
                "archive_path": str(path),
                "provider_calls": 0,
            }
            exit_code = 0
        else:
            validation = validate_wave_c_package(
                args.batch_root,
                expected_code_sha=args.expected_code_sha,
            )
            receipt_paths: tuple[Path, ...] = ()
            if args.write_receipts:
                receipt_paths = write_validation_receipts(
                    args.batch_root,
                    validation,
                )
            payload = validation.to_dict()
            payload["receipt_paths"] = [str(path) for path in receipt_paths]
            payload["provider_calls_executed_by_validation"] = 0
            exit_code = 0 if validation.passed else 2
    except BatchRunnerError as exc:
        payload = {
            "status": "blocked",
            "error_code": exc.error_code,
            "provider_calls": 0,
        }
        exit_code = 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
