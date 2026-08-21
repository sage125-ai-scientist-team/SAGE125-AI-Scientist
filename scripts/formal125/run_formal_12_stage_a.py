"""CLI for Formal 12 stage A. Refuses provider execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.formal125.formal12 import (  # noqa: E402
    AUTHORIZATION_TEXT,
    STAMP,
    run_stage_a,
)

OUTPUT_ROOT = Path(rf"D:\SAGE125_Local_Runs\formal_12_domain_real_{STAMP}")
CACHE_ROOT = Path(rf"D:\SAGE125_Local_Evidence\formal_12_domain_{STAMP}")
BACKUP_PATH = Path(rf"D:\SAGE125_Local_Backups\formal_12_domain_real_{STAMP}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Formal 12 domain stage A")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--execute-stage-a", action="store_true")
    parser.add_argument("--execute", action="store_true", help="alias rejected: stage B is not this script")
    args = parser.parse_args(argv)
    if args.execute:
        print("REFUSING: stage B is not authorized from this script", file=sys.stderr)
        return 2
    if not args.execute_stage_a:
        print("REFUSING: stage A requires --execute-stage-a", file=sys.stderr)
        return 2
    summary = run_stage_a(
        repo_root=args.repo_root,
        output_root=OUTPUT_ROOT,
        cache_root=CACHE_ROOT,
        backup_path=BACKUP_PATH,
    )
    print(json.dumps({"FORMAL_12_STAGE_A_STATUS": summary["FORMAL_12_STAGE_A_STATUS"]}, ensure_ascii=False))
    print()
    print("[MANUAL_GATE_FORMAL_12_DOMAIN_CAPTAIN_AUTHORIZATION]")
    print(f"PROJECT_PROVIDER_CALLS_CURRENT={summary['PROJECT_PROVIDER_CALLS_CURRENT']}")
    print("FORMAL_12_CASE_IDS=")
    print(",".join(summary["FORMAL_12_CASE_IDS"]))
    print("Required authorization text:")
    print(AUTHORIZATION_TEXT)
    return 0 if summary["FORMAL_12_STAGE_A_STATUS"] == "GO" else 3


if __name__ == "__main__":
    raise SystemExit(main())
