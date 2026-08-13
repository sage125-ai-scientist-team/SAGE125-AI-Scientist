"""Tests for blocked-only Wave C final readiness governance."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.validate_t09_wave_c_final import validate


ROOT = Path("docs/reproducibility")


def test_blocked_contracts_are_valid_preparation() -> None:
    """Blocked contracts truthfully model missing final inputs."""
    assert validate(ROOT / "T09_12_DOMAIN_EVALUATION_CONTRACT.json", ROOT / "T09_RC_FINAL_CONTRACT.json")["passed"]


def test_ready_claim_without_attestation_fails(tmp_path: Path) -> None:
    """Ready cannot be claimed before external final-tip attestation."""
    final = json.loads((ROOT / "T09_RC_FINAL_CONTRACT.json").read_text(encoding="utf-8"))
    final["ready_candidate"] = True
    path = tmp_path / "final.json"
    path.write_text(json.dumps(final), encoding="utf-8")
    assert "premature_ready" in validate(ROOT / "T09_12_DOMAIN_EVALUATION_CONTRACT.json", path)["errors"]
