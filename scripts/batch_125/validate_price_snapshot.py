"""Pure-offline validator for T07-WB5 operator price snapshot inputs."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.batch.errors import BatchRunnerError
from app.batch.price_snapshot_input import (
    FROZEN_PRICE_MODELS,
    inspect_price_snapshot_schema,
    load_price_snapshot_input,
)


DEFAULT_SCHEMA = Path(
    "docs/modules/T07/run_configs/T07-WB5-price-snapshot-input.schema.json"
)
DEFAULT_FROZEN_CONFIG = Path(
    "docs/modules/T07/run_configs/T07-WB5-20260803-v1.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a T07-WB5 price snapshot without network or provider",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--input", type=Path)
    parser.add_argument("--normalized-output", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--frozen-config", type=Path, default=DEFAULT_FROZEN_CONFIG)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    return parser


def _resolve(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _load_object(path: Path, error_code: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(error_code, "required JSON file is invalid") from exc
    if not isinstance(value, Mapping):
        raise BatchRunnerError(error_code, "required JSON root must be an object")
    return value


def _require_outside_repository(
    path: Path,
    repo_root: Path,
    error_code: str,
) -> Path:
    candidate = path.resolve(strict=False)
    root = repo_root.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError:
        return candidate
    raise BatchRunnerError(error_code, "price snapshot path must be outside repository")


def _safe_failure(exc: BatchRunnerError) -> dict[str, object]:
    return {
        "status": "PRICE_SNAPSHOT_INPUT_BLOCKED",
        "error_code": exc.error_code,
        "message": str(exc),
        "actual_price_snapshot_supplied": False,
        "actual_price_snapshot_validated": False,
        "provider_calls": 0,
        "provider_preflight_executed": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repo_root.resolve(strict=False)
    try:
        if args.self_check:
            if args.normalized_output is not None:
                raise BatchRunnerError(
                    "PRICE_SNAPSHOT_OUTPUT_PATH_INVALID",
                    "self-check does not produce a normalized snapshot",
                )
            schema = _load_object(
                _resolve(args.schema, root), "PRICE_SNAPSHOT_SPEC_INVALID"
            )
            frozen = _load_object(
                _resolve(args.frozen_config, root), "PRICE_SNAPSHOT_SPEC_INVALID"
            )
            print(
                json.dumps(
                    inspect_price_snapshot_schema(schema, frozen),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        if args.input is None:
            raise BatchRunnerError(
                "PRICE_SNAPSHOT_INPUT_INVALID", "--input is required"
            )
        input_path = _require_outside_repository(
            args.input,
            root,
            "PRICE_SNAPSHOT_INPUT_PATH_INVALID",
        )
        normalized = load_price_snapshot_input(input_path, allow_test_input=False)
        if args.normalized_output is not None:
            output_path = _require_outside_repository(
                args.normalized_output,
                root,
                "PRICE_SNAPSHOT_OUTPUT_PATH_INVALID",
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(
                    normalized,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "status": "PRICE_SNAPSHOT_INPUT_VALID",
                    "required_models": len(FROZEN_PRICE_MODELS),
                    "model_set_matches_frozen_config": True,
                    "actual_price_snapshot_supplied": True,
                    "actual_price_snapshot_validated": True,
                    "normalized_output_written": args.normalized_output is not None,
                    "provider_calls": 0,
                    "provider_preflight_executed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except BatchRunnerError as exc:
        print(
            json.dumps(_safe_failure(exc), ensure_ascii=False, sort_keys=True),
            file=sys.stdout,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
