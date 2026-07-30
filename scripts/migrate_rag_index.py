"""Migrate the legacy RAG index into the active ``IndexConfig`` layout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.contracts.rag import IndexConfig  # noqa: E402
from app.rag.index_migration import (  # noqa: E402
    IndexMigrationError,
    migrate_index,
    rollback_index_migration,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default=str(PROJECT_ROOT / "data"))
    parser.add_argument("--apply", action="store_true", help="execute instead of dry-run")
    parser.add_argument("--rollback", action="store_true", help="restore the legacy layout")
    parser.add_argument("--expected-checksum", help="require this legacy index SHA-256")
    args = parser.parse_args()
    if args.apply and args.rollback:
        parser.error("--apply and --rollback are mutually exclusive")

    config = IndexConfig.resolve({"data_root": args.data_root})
    try:
        if args.rollback:
            result = rollback_index_migration(config)
        else:
            result = migrate_index(
                config,
                dry_run=not args.apply,
                expected_checksum=args.expected_checksum,
            )
        payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except IndexMigrationError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
