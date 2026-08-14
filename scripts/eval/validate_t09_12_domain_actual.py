"""Offline validator for T09 12-domain runner preflight and execution ledgers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_PROTOCOL_KEYS = {
    "schema_version",
    "task_id",
    "required_domains",
    "scoring",
    "execution_policy",
    "artifact_policy",
}


def _load(path: Path) -> dict[str, Any]:
    """Load one JSON object and return an empty object on malformed input."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def validate(protocol_path: Path, ledger_path: Path | None = None) -> dict[str, object]:
    """Fail closed when protocol or optional ledger violates T09 execution governance."""
    protocol = _load(protocol_path)
    errors = [f"missing:{key}" for key in sorted(REQUIRED_PROTOCOL_KEYS - protocol.keys())]
    domains = protocol.get("required_domains")
    if protocol.get("schema_version") != "1.2" or protocol.get("task_id") != "T09":
        errors.append("protocol_identity")
    if not isinstance(domains, list) or len(domains) != 12 or len(set(domains)) != 12:
        errors.append("required_domains")
    policy = protocol.get("execution_policy", {})
    if not isinstance(policy, dict) or policy.get("default_mode") != "preflight-only":
        errors.append("default_mode")
    if not isinstance(policy, dict) or policy.get("execute_flag") != "--execute":
        errors.append("execute_gate")
    if not isinstance(policy, dict) or policy.get("max_attempt_cap") != 24:
        errors.append("max_attempt_cap")
    if not isinstance(policy, dict) or policy.get("max_retries_per_entry") != 1:
        errors.append("retry_policy")
    authorization = protocol.get("actual_execution_authorization")
    if (
        not isinstance(authorization, dict)
        or not isinstance(authorization.get("authorized"), bool)
        or authorization.get("provider") != "bailian"
        or authorization.get("model") != "qwen3.6-flash"
        or authorization.get("region") != "cn-beijing"
        or authorization.get("endpoint_rule")
        != "https://{workspace_id}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    ):
        errors.append("actual_execution_authorization")
    scoring = protocol.get("scoring", {})
    metric = scoring.get("METRIC-005") if isinstance(scoring, dict) else None
    if not isinstance(metric, dict) or metric.get("minimum") != 12:
        errors.append("metric_005_protocol")
    if ledger_path is not None:
        ledger = _load(ledger_path)
        if ledger.get("schema_version") != "1.2":
            errors.append("ledger_schema")
        if ledger.get("mode") not in {"preflight-only", "execute"}:
            errors.append("ledger_mode")
        if ledger.get("mode") == "preflight-only" and ledger.get("provider_calls", 0) != 0:
            errors.append("preflight_provider_calls")
        if not isinstance(ledger.get("attempt_cap"), int) or ledger["attempt_cap"] < 1:
            errors.append("attempt_cap")
        if ledger.get("global_attempt_cap") != 24:
            errors.append("global_attempt_cap")
        if not isinstance(ledger.get("manifest_sha256"), str) or len(ledger["manifest_sha256"]) != 64:
            errors.append("manifest_sha256")
        if ledger.get("manifest_hash_algorithm") != "sha256-canonical-json-v1":
            errors.append("manifest_hash_algorithm")
        source_binding = ledger.get("question_source_binding")
        if (
            not isinstance(source_binding, dict)
            or source_binding.get("source_path") != "data/processed/questions_125.json"
            or not isinstance(source_binding.get("resolved_path"), str)
            or not isinstance(source_binding.get("sha256"), str)
            or len(source_binding["sha256"]) != 64
            or not isinstance(source_binding.get("question_bindings_sha256"), str)
            or len(source_binding["question_bindings_sha256"]) != 64
        ):
            errors.append("question_source_binding")
        if not isinstance(ledger.get("environment"), dict):
            errors.append("environment")
        entries = ledger.get("entries", [])
        if not isinstance(entries, list):
            errors.append("ledger_entries")
        elif any(len(item.get("attempts", [])) > 2 for item in entries if isinstance(item, dict)):
            errors.append("attempt_cap_exceeded")
        elif ledger.get("global_attempt_count") != sum(
            len(item.get("attempts", []))
            for item in entries
            if isinstance(item, dict) and isinstance(item.get("attempts", []), list)
        ):
            errors.append("global_attempt_count")
        elif isinstance(ledger.get("global_attempt_count"), int) and ledger["global_attempt_count"] > 24:
            errors.append("global_attempt_cap_exceeded")
        elif any(
            attempt.get("status") == "completed"
            and (
                not isinstance(attempt.get("artifact"), dict)
                or not isinstance(attempt["artifact"].get("sha256"), str)
                or attempt["artifact"].get("secret_scan", {}).get("passed") is not True
            )
            for item in entries
            if isinstance(item, dict)
            for attempt in item.get("attempts", [])
            if isinstance(attempt, dict)
        ):
            errors.append("artifact_integrity")
        coverage = ledger.get("metric_coverage")
        if ledger.get("mode") == "execute" and (
            not isinstance(coverage, dict)
            or coverage.get("requirement_id") != "T09-METRIC-005"
            or coverage.get("evaluated_domain_count") != 12
            or coverage.get("passed") is not True
        ):
            errors.append("metric_005_coverage")
        if ledger.get("mode") == "execute":
            for item in entries:
                if not isinstance(item, dict):
                    errors.append("ledger_entries")
                    continue
                for attempt in item.get("attempts", []):
                    if not isinstance(attempt, dict):
                        errors.append("ledger_entries")
                        continue
                    if attempt.get("status") == "completed":
                        audit = attempt.get("audit_identity")
                        if (
                            not isinstance(audit, dict)
                            or audit.get("provider") != "bailian_qwen"
                            or audit.get("model") != "qwen3.6-flash"
                            or audit.get("cost_usd") is not None
                            or audit.get("cost_accounting") != "token_only_unpriced"
                            or not all(
                                isinstance(audit.get(field), int) and audit[field] >= 0
                                for field in ("call_count", "input_tokens", "output_tokens", "total_tokens")
                            )
                            or audit.get("total_tokens")
                            != audit.get("input_tokens", 0) + audit.get("output_tokens", 0)
                            or attempt.get("token_count") != audit.get("total_tokens")
                            or attempt.get("cost_usd") is not None
                        ):
                            errors.append("call_audit_identity_or_usage")
    return {"passed": not errors, "errors": sorted(set(errors)), "provider_calls": 0}


def main() -> int:
    """Validate a protocol and optional runner ledger from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    report = validate(parser.parse_args().protocol, parser.parse_args().ledger)
    print(json.dumps(report, sort_keys=True))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
