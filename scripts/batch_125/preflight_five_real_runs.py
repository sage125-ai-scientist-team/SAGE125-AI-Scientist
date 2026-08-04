"""Offline-by-default preflight CLI for the frozen T07-WB5 run.

Only ``--execute-provider-preflight`` can cross the provider boundary. Codex
must not invoke that flag while producing WB5 engineering evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.core.config import get_settings

from app.batch.actual_call_audit import (
    ActualCallAudit,
    BudgetLedger,
    PriceSnapshot,
    compute_estimated_cost,
    sanitize_request_id,
)
from app.batch.errors import BatchRunnerError
from app.batch.five_run_preflight import (
    FrozenFiveRunConfig,
    load_frozen_run_config,
    run_five_run_preflight,
)


DEFAULT_CONFIG = Path(
    "docs/modules/T07/run_configs/T07-WB5-20260803-v1.json"
)


def _safe_provider_diagnostics(
    repo_root: Path,
    *,
    environment: Mapping[str, str] | None = None,
    settings_loader: Callable[[], Any] = get_settings,
) -> dict[str, object]:
    """Load repository configuration while returning no secret values."""

    settings = settings_loader()
    source = os.environ if environment is None else environment
    mock_enabled = str(source.get("MOCK_LLM", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return {
        "env_file_exists": (repo_root / ".env").is_file(),
        "provider_name": str(settings.llm_provider),
        "qwen_configured": bool(settings.qwen_configured),
        "deep_research_configured": bool(settings.deep_research_configured),
        "mock_mode_enabled": mock_enabled,
        "config_loader_invoked": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run T07-WB5 fail-closed preflight; offline unless explicitly enabled"
        ),
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--price-snapshot",
        type=Path,
        help="Operator-supplied frozen price JSON; required for a provider preflight",
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        help="Repository-external audit directory; required for provider preflight",
    )
    parser.add_argument("--execute-provider-preflight", action="store_true")
    return parser


def _load_price_snapshot(
    path: Path | None,
) -> tuple[Mapping[str, object] | None, PriceSnapshot | None]:
    if path is None:
        return None, None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise TypeError("price snapshot is not an object")
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise BatchRunnerError(
            "PRICE_SNAPSHOT_INVALID",
            "operator price snapshot is not valid UTF-8 JSON",
        ) from exc
    return raw, PriceSnapshot.from_mapping(raw)


def _outside_repo(run_root: Path, repo_root: Path) -> Path:
    resolved = run_root.resolve(strict=False)
    root = repo_root.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved
    raise BatchRunnerError(
        "PROVIDER_PREFLIGHT_RUN_ROOT_INVALID",
        "provider-preflight audit output must be outside the repository",
    )


def _budget_ledger(config: FrozenFiveRunConfig) -> BudgetLedger:
    try:
        per_question = config.budgets["per_question"]
        batch = config.budgets["batch"]
        if not isinstance(per_question, Mapping) or not isinstance(batch, Mapping):
            raise TypeError("budget scopes must be objects")
        return BudgetLedger(
            per_question_token_limit=int(per_question["token_limit"]),
            per_question_cost_limit_usd=Decimal(
                str(per_question["cost_limit_usd"])
            ),
            batch_token_limit=int(batch["token_limit"]),
            batch_cost_limit_usd=Decimal(str(batch["cost_limit_usd"])),
            max_output_tokens_per_call=int(
                config.budgets["max_output_tokens_per_call"]
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BatchRunnerError(
            "FROZEN_CONFIG_INVALID",
            "frozen budget configuration is invalid",
        ) from exc


def _execute_minimal_provider_preflight(
    config: FrozenFiveRunConfig,
    snapshot: PriceSnapshot,
    run_root: Path,
) -> ActualCallAudit:
    """Make one eight-token Bailian request after every offline gate passes."""

    if str(os.environ.get("MOCK_LLM", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise BatchRunnerError(
            "MOCK_LLM_ENABLED",
            "formal provider preflight refuses MOCK_LLM",
        )
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.qwen_configured or settings.llm_provider != "bailian":
        raise BatchRunnerError(
            "PROVIDER_CONFIGURATION_MISSING",
            "Bailian provider configuration boolean is false",
        )
    model = config.models.get("fast")
    if not model:
        raise BatchRunnerError(
            "FROZEN_CONFIG_INVALID",
            "frozen fast model is missing",
        )
    prompt = "Reply with exactly OK."
    maximum_output_tokens = 8
    planned_input_tokens = 64
    ledger = _budget_ledger(config)
    planned_cost = compute_estimated_cost(
        snapshot,
        model,
        planned_input_tokens,
        maximum_output_tokens,
    )
    ledger.require_capacity(
        "PROVIDER_PREFLIGHT",
        planned_input_tokens=planned_input_tokens,
        planned_output_tokens=maximum_output_tokens,
        estimated_cost_usd=planned_cost,
    )

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            max_retries=0,
            timeout=settings.qwen_probe_timeout_seconds,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=maximum_output_tokens,
            temperature=0,
            extra_body={"enable_thinking": False},
        )
    except Exception as exc:
        raise BatchRunnerError(
            "PROVIDER_PREFLIGHT_FAILED",
            f"Bailian preflight failed with {type(exc).__name__}",
        ) from None
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    if not all(
        type(value) is int
        for value in (input_tokens, output_tokens, total_tokens)
    ):
        raise BatchRunnerError(
            "PROVIDER_USAGE_MISSING",
            "provider preflight returned no complete token usage",
        )
    estimated_cost = compute_estimated_cost(
        snapshot,
        model,
        input_tokens,
        output_tokens,
    )
    audit = ActualCallAudit(
        provider="bailian",
        model=model,
        route_tier="fast",
        request_timestamp=datetime.now(timezone.utc),
        sanitized_request_id=sanitize_request_id(str(getattr(response, "id", ""))),
        static_prompt_version=config.prompt_version,
        static_prompt_hash=config.prompt_file.sha256,
        dynamic_prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        settled_cost_usd=None,
        retry_attempt=1,
        fallback=False,
        price_snapshot_version=snapshot.version,
    )
    ledger.record_call("PROVIDER_PREFLIGHT", audit)
    target = run_root / config.freeze_id / "provider_preflight"
    target.mkdir(parents=True, exist_ok=False)
    (target / "llm_call_audit.json").write_text(
        audit.to_json() + "\n",
        encoding="utf-8",
    )
    return audit


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve(strict=False)
    config_path = (
        args.config
        if args.config.is_absolute()
        else repo_root / args.config
    )
    try:
        raw_snapshot, snapshot = _load_price_snapshot(args.price_snapshot)
        provider_diagnostics = _safe_provider_diagnostics(repo_root)
        result = run_five_run_preflight(
            config_path,
            repo_root,
            injected_price_snapshot=raw_snapshot,
            provider_configured_override=bool(
                provider_diagnostics["qwen_configured"]
            ),
        )
        output = result.to_dict()
        output.update(provider_diagnostics)
        output["mode"] = "offline"
        if not args.execute_provider_preflight:
            print(json.dumps(output, ensure_ascii=False, sort_keys=True))
            return 0 if result.passed else 2
        if not result.passed:
            output["provider_preflight_executed"] = False
            print(json.dumps(output, ensure_ascii=False, sort_keys=True))
            return 2
        if snapshot is None or args.run_root is None:
            raise BatchRunnerError(
                "PROVIDER_PREFLIGHT_INPUT_MISSING",
                "--price-snapshot and --run-root are required for provider preflight",
            )
        run_root = _outside_repo(args.run_root, repo_root)
        audit = _execute_minimal_provider_preflight(
            load_frozen_run_config(config_path),
            snapshot,
            run_root,
        )
        print(
            json.dumps(
                {
                    "status": "PROVIDER_PREFLIGHT_PASSED",
                    "configured": True,
                    "provider": audit.provider,
                    "model": audit.model,
                    "request_timestamp": audit.request_timestamp.isoformat(),
                    "sanitized_request_id": audit.sanitized_request_id,
                    "input_tokens": audit.input_tokens,
                    "output_tokens": audit.output_tokens,
                    "total_tokens": audit.total_tokens,
                    "estimated_cost_usd": str(audit.estimated_cost_usd),
                    "fallback": audit.fallback,
                    "provider_preflight_executed": True,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except BatchRunnerError as exc:
        print(
            json.dumps(
                {
                    "status": "FIVE_REAL_RUNS_BLOCKED",
                    "error_code": exc.error_code,
                    "message": str(exc),
                    "provider_preflight_executed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
