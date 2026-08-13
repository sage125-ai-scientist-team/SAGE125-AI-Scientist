"""Offline fail-closed validation for T09 Wave C final-readiness contracts."""
from __future__ import annotations

import json
from pathlib import Path


def validate(domain_contract: Path, rc_final: Path) -> dict[str, object]:
    """Reject any actual/ready claim without all final governance evidence."""
    try:
        domains = json.loads(domain_contract.read_text(encoding="utf-8"))
        final = json.loads(rc_final.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"passed": False, "errors": [type(error).__name__], "provider_calls": 0}
    errors: list[str] = []
    required = domains.get("required_domains", [])
    if len(required) != 12 or len(set(required)) != 12:
        errors.append("domain_count_or_duplicate")
    if domains.get("provider_calls") != 0 or domains.get("actual_evaluation_authorized") is not False:
        errors.append("actual_or_provider")
    if final.get("ready_candidate") is not False or final.get("verified_at_wave_c") is not False:
        errors.append("premature_ready")
    if final.get("ready_candidate") is True and final.get("final_tip_binding", {}).get("status") != "ATTESTED":
        errors.append("final_tip_unattested")
    if final.get("status") != "BLOCKED" or domains.get("status") != "BLOCKED":
        errors.append("status")
    return {"passed": not errors, "errors": errors, "provider_calls": 0}
