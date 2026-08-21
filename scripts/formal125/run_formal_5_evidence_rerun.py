"""CLI for attempt-2 formal five-question evidence rerun."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.formal125.evidence_rerun import run_attempt2, write_evidence_rerun_authorization  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Formal 5 evidence remediation attempt 2")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--write-authorization", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.write_authorization:
        result = write_evidence_rerun_authorization(repo_root=args.repo_root)
        print(json.dumps({"status": "AUTHORIZATION_WRITTEN", "authorization_hash_prefix": result["authorization_hash"][:12]}, ensure_ascii=False))
        return 0
    if not args.execute:
        print("REFUSING: attempt 2 requires --execute after captain authorization", file=sys.stderr)
        return 2
    summary = run_attempt2(repo_root=args.repo_root, execute=True)
    print(
        json.dumps(
            {
                "batch_status": summary.get("batch_status"),
                "status_counts": summary.get("status_counts"),
                "provider_calls": summary.get("provider_calls"),
                "project_provider_calls_after": summary.get("project_provider_calls_after"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
