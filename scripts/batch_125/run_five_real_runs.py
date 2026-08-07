"""CLI for the frozen WB5 formal execution contract.

Without ``--execute`` this command performs validation and writes only an
external dry-run manifest.  Execute mode initializes the audited single-call
provider runtime before handing control to the fail-closed batch runner.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from app.batch.errors import BatchRunnerError
from app.batch.formal_five_runs import FormalRunRequest, run_formal_five_runs
from app.batch.formal_provider_runtime import build_formal_provider_executor
from app.core.config import get_settings


DEFAULT_CONFIG = Path(
    "docs/modules/T07/run_configs/T07-WB5-20260807-v2.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fail-closed T07-WB5 frozen formal entrypoint",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--provider-preflight-audit", type=Path, required=True)
    parser.add_argument("--question-id", action="append", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser


def _mock_enabled() -> bool:
    return os.environ.get("MOCK_LLM", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = get_settings()
        request = FormalRunRequest(
            repo_root=args.repo_root,
            config_path=args.config,
            run_root=args.run_root,
            authorization_reference=args.authorization_reference,
            provider_preflight_audit=args.provider_preflight_audit,
            question_ids=tuple(args.question_id),
            execute=args.execute,
            resume=args.resume,
            provider_configured=bool(
                settings.qwen_configured
                and settings.deep_research_configured
                and settings.llm_provider == "bailian"
            ),
            mock_environment=_mock_enabled(),
        )
        executor = (
            build_formal_provider_executor(settings) if args.execute else None
        )
        receipt = run_formal_five_runs(request, executor=executor)
    except BatchRunnerError as exc:
        print(
            json.dumps(
                {
                    "status": "FIVE_REAL_RUNS_BLOCKED",
                    "error_code": exc.error_code,
                    "provider_calls": 0,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            receipt.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if receipt.status in {"dry_run", "completed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
