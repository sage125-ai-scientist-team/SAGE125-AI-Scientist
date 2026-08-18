"""Regression coverage for the offline T09 RC v1 contract."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.validate_t09_rc_v1 import validate


def contract(tmp_path: Path, **changes: object) -> Path:
    """Write an isolated RC contract with controlled validation mutations."""
    value = json.loads((Path("docs/reproducibility/T09_RC_V1_CONTRACT.json")).read_text(encoding="utf-8"))
    value.update(changes)
    path = tmp_path / "rc.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_blocked_offline_contract_is_valid_governance(tmp_path: Path) -> None:
    """A blocked RC v1 truthfully represents missing formal materials."""
    assert validate(contract(tmp_path))["passed"] is True


def test_actual_provider_and_missing_gaps_fail_closed(tmp_path: Path) -> None:
    """Actual claims, calls, and absent unresolved gaps cannot pass RC v1."""
    report = validate(contract(tmp_path, mode="actual", provider_calls=1, unresolved_gaps=[]))
    assert {"actual_or_provider", "unresolved_gaps"} <= set(report["errors"])
