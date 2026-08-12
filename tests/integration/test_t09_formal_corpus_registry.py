"""Offline regression coverage for T09 formal corpus governance."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
from typing import Callable
from scripts.eval.validate_t09_formal_corpus import (
    REGISTRY,
    derive_positive_qrels,
    validate,
    validate_pairs,
)

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


def test_out_of_scope_t01_artifact_rejected(tmp_path: Path) -> None:
    """A registry must reject a package path outside approved T01 scope."""
    registry = altered_registry(
        tmp_path,
        lambda payload: payload.update(package_path="docs/modules/T01"),
    )
    assert "package_path" in validate(registry)


def test_unsupported_relation_not_positive_qrel() -> None:
    """Only supports-plus-allow can become a positive qrel."""
    assert derive_positive_qrels([{"relation": "contradicts", "expected_decision": "allow"}]) == []


def test_unjudged_is_not_negative() -> None:
    """Unjudged material produces neither a positive nor an inferred negative."""
    assert derive_positive_qrels([{"relation": "unjudged", "expected_decision": "allow"}]) == []


def test_missing_required_pair_field_fails() -> None:
    """A required pairing field cannot be silently omitted."""
    assert "pair_fields" in validate_pairs([{"claim_id": "c", "evidence_id": "e"}])


def test_duplicate_atomic_pair_id_fails() -> None:
    """Duplicate claim/evidence atomic keys are rejected."""
    pair = {"claim_id": "c", "evidence_id": "e"}
    assert "duplicate_pair" in validate_pairs([pair, pair])


def test_validator_is_offline_and_write_free(tmp_path: Path) -> None:
    """Invalid local input yields JSON failure without repository artifacts."""
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    before = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout
    result = subprocess.run(
        [sys.executable, "-B", "scripts/eval/validate_t09_formal_corpus.py", "--registry", str(invalid)],
        capture_output=True, text=True, check=False,
    )
    after = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout
    assert result.returncode != 0
    assert json.loads(result.stdout)["valid"] is False
    assert "Traceback" not in result.stderr
    assert after == before
