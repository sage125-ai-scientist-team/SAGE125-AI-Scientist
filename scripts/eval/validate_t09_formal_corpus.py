"""Fail-closed, offline validator for the T09 formal corpus registry."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/reproducibility/T09_FORMAL_CORPUS_REGISTRY.json"
APPROVED_PACKAGE_PATH = "docs/modules/T01/eval_gold/v1"

def digest(path: Path) -> str:
    """Return the raw-byte SHA-256 of one admitted file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate(registry_path: Path = REGISTRY) -> list[str]:
    """Validate registry scope, byte identities, pairs and qrel eligibility."""
    r = json.loads(registry_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    required = {"schema_version", "status", "audit_head", "package_path", "pair_count",
                "t09_admission_file_inventory", "excluded_paths"}
    errors += [f"missing:{x}" for x in required - r.keys()]
    if r.get("status") != "APPROVED_FOR_T09_FORMAL_EVALUATION":
        errors.append("status")
    if r.get("pair_count") != 8:
        errors.append("pair_count")
    if r.get("package_path") != APPROVED_PACKAGE_PATH:
        return errors + ["package_path"]
    base = ROOT / APPROVED_PACKAGE_PATH
    if "docs/modules/T01/evidence_gold_set.json" not in r["excluded_paths"]:
        errors.append("fixture_not_excluded")
    for rel, expected in r.get("t09_admission_file_inventory", {}).items():
        p = base / rel
        if not p.is_file() or digest(p) != expected:
            errors.append(f"hash:{rel}")
    pairs = json.loads((base / "pairs.json").read_text(encoding="utf-8")).get("pairs", [])
    keys = set()
    for pair in pairs:
        needed = {"claim_id", "evidence_id", "linked_question_id", "source_id", "relation",
                  "expected_decision", "quote", "locator", "content_hash", "source_file_sha256"}
        if needed - pair.keys():
            errors.append("pair_fields")
        key = (pair.get("claim_id"), pair.get("evidence_id"))
        if key in keys:
            errors.append("duplicate_pair")
        keys.add(key)
        if pair.get("fixture") or pair.get("synthetic") or pair.get("provisional"):
            errors.append("invalid_material")
    if len(pairs) != 8:
        errors.append("pair_file_count")
    return errors

def main() -> int:
    """Print a JSON summary and return non-zero on any drift."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    args = parser.parse_args()
    errors = validate(args.registry)
    print(json.dumps({"valid": not errors, "errors": errors, "provider_calls": 0}))
    return int(bool(errors))
if __name__ == "__main__":
    raise SystemExit(main())
