"""CLI for the captain-authorized formal five-question actual run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.formal125.actual_run import (  # noqa: E402
    run_formal_five_actual,
    write_captain_authorization,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Formal five-question actual run")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--authorization-path", type=Path, default=None)
    parser.add_argument("--write-authorization", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = args.output_root
    if args.write_authorization:
        result = write_captain_authorization(
            repo_root=args.repo_root,
            output_root=output_root,
        )
        print(json.dumps({"status": "AUTHORIZATION_WRITTEN", "authorization_hash_prefix": result["authorization_hash"][:12]}, ensure_ascii=False))
        return 0
    authorization_path = args.authorization_path or (output_root / "authorization" / "authorization.json")
    summary = run_formal_five_actual(
        repo_root=args.repo_root,
        output_root=output_root,
        authorization_path=authorization_path,
        execute=args.execute,
        resume=args.resume,
    )
    print(
        json.dumps(
            {
                "batch_status": summary["batch_status"],
                "status_counts": summary["status_counts"],
                "provider_calls": summary["provider_calls"],
                "estimated_cost": summary["estimated_cost"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if summary["batch_status"] in {"PASS", "PASS_WITH_PARTIAL_QUESTIONS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
