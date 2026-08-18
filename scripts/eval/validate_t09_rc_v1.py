"""Offline fail-closed validator for a blocked-or-verified T09 RC v1 contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "schema_version", "status", "base_sha", "candidate_sha", "inputs",
    "packaging_status", "clean_room_status", "unresolved_gaps",
    "provider_calls", "actual_ablation_authorized", "mode",
}


def validate(path: Path) -> dict[str, object]:
    """Validate an RC v1 contract without accessing network or providers."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"passed": False, "errors": [f"contract:{type(error).__name__}"], "provider_calls": 0}
    errors = [f"missing:{key}" for key in REQUIRED - value.keys()] if isinstance(value, dict) else ["contract:shape"]
    if not isinstance(value, dict):
        return {"passed": False, "errors": errors, "provider_calls": 0}
    if value.get("status") not in {"BLOCKED", "PARTIAL"}:
        errors.append("status")
    if value.get("mode") == "actual" or value.get("provider_calls") != 0:
        errors.append("actual_or_provider")
    if value.get("actual_ablation_authorized") is not False:
        errors.append("ablation_authorization")
    if not isinstance(value.get("unresolved_gaps"), list) or not value["unresolved_gaps"]:
        errors.append("unresolved_gaps")
    if value.get("status") == "PARTIAL" and value.get("clean_room_status") == "PASS":
        errors.append("status_contradiction")
    return {"passed": not errors, "errors": sorted(errors), "provider_calls": 0}


def main() -> int:
    """Print structured result and return non-zero for invalid contracts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    report = validate(parser.parse_args().contract)
    print(json.dumps(report, sort_keys=True))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
