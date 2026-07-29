"""Create a provider-free T07 dry-run manifest and checkpoints."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.batch import BatchRunner, BatchRunnerError
from app.contracts.batch import ResultKind, SourceKind


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a T07 dry-run manifest without calling a model provider"
        )
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--source-kind",
        choices=[kind.value for kind in SourceKind],
        required=True,
    )
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = BatchRunner(args.run_root).dry_run(
            args.source,
            batch_id=args.batch_id,
            source_kind=SourceKind(args.source_kind),
        )
    except BatchRunnerError as exc:
        print(
            json.dumps(
                {"error_code": exc.error_code, "message": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    summary = {
        "actual_results": sum(
            job.result_kind is ResultKind.ACTUAL for job in manifest.jobs
        ),
        "batch_id": manifest.batch_id,
        "dry_run": manifest.dry_run,
        "jobs": len(manifest.jobs),
        "manifest_path": (
            args.run_root / manifest.batch_id / "manifest.json"
        ).as_posix(),
        "provider_calls": 0,
        "source_kind": manifest.source_kind.value,
        "tokens_used": sum(job.budget.tokens_used for job in manifest.jobs),
        "unique_cache_namespaces": len(
            {job.cache_namespace for job in manifest.jobs}
        ),
        "unique_context_ids": len(
            {job.context_id for job in manifest.jobs}
        ),
        "unique_workspaces": len({job.workspace for job in manifest.jobs}),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
