"""Offline regression coverage for T09 formal corpus governance."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Callable
from scripts.eval.validate_t09_formal_corpus import REGISTRY, validate

def altered_registry(
    tmp_path: Path, mutate: Callable[[dict[str, object]], None]
) -> Path:
    """Write an isolated registry copy with one deliberate invalid mutation."""
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    mutate(payload)
    target = tmp_path / "registry.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target

def test_valid_current_approved_package_passes() -> None:
    """Current pinned T01 package passes without provider access."""
    assert validate() == []

def test_registry_audit_head_is_pinned() -> None:
    """Registry remains bound to the reviewed Wave C baseline."""
    assert json.loads(REGISTRY.read_text(encoding="utf-8"))["audit_head"] == "20592a0eeb9924d021e3ec75ec28d27e2f971e9f"

def test_actual_ablation_remains_disabled() -> None:
    """Admission does not authorize actual ablation."""
    assert json.loads(REGISTRY.read_text(encoding="utf-8"))["actual_ablation_authorized"] is False

def test_pair_count_must_equal_eight(tmp_path: Path) -> None:
    """Any changed registry denominator fails closed."""
    assert "pair_count" in validate(altered_registry(tmp_path, lambda x: x.update(pair_count=7)))

def test_sha256_drift_fails(tmp_path: Path) -> None:
    """A raw-byte identity mismatch is rejected."""
    assert any(x.startswith("hash:pairs.json") for x in validate(altered_registry(tmp_path, lambda x: x["t09_admission_file_inventory"].update({"pairs.json": "0"*64}))))

def test_excluded_evidence_gold_set_is_required(tmp_path: Path) -> None:
    """The explicitly excluded upstream artifact cannot be admitted."""
    assert "fixture_not_excluded" in validate(altered_registry(tmp_path, lambda x: x.update(excluded_paths=[])))

def test_t06_not_in_retrieval_qrels() -> None:
    """T06 role is explicitly excluded from retrieval relevance denominators."""
    assert json.loads(REGISTRY.read_text(encoding="utf-8"))["t06_role"]["relevance_gold"] is False
