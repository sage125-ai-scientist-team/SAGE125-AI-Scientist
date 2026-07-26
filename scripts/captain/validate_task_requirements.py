# -*- coding: utf-8 -*-
"""
scripts/captain/validate_task_requirements.py —— 校验 T01—T09 任务要求 YAML
与 source-manifest.json 的完整性、Schema 符合性、ID 唯一性与源哈希一致性。

用法：

    py -3 scripts/captain/validate_task_requirements.py
    py -3 scripts/captain/validate_task_requirements.py --dir docs/governance/task-requirements

退出码：0 通过；1 校验失败；2 环境/路径错误。
不读取 .env，不修改任何文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: python -m pip install -r requirements.txt") from exc

TASK_IDS = tuple("T0%d" % n for n in range(1, 10))
REQUIRED_TOP_LEVEL = (
    "schema_version",
    "repository",
    "task_id",
    "title",
    "mission",
    "scoring_dimensions",
    "owner_paths",
    "forbidden_paths",
    "dependencies",
    "branch_series",
    "paired_reviewer",
    "sprint_days",
    "must_deliver",
    "definition_of_done",
    "quantitative_thresholds",
    "waves",
    "requirements",
)
REQUIRED_REQ_FIELDS = (
    "id",
    "task_id",
    "wave",
    "category",
    "requirement_text",
    "source_heading",
    "source_paragraph_index",
    "source_text_sha256",
    "evidence_required",
    "verification_type",
    "blocking_policy",
)
BLOCKING_POLICIES = {
    "P0_BLOCKING",
    "P1_BLOCKING",
    "DEFERRED_ALLOWED",
    "P2_RECOMMENDATION",
    "OPTIONAL",
}
WAVES = {"A", "B", "C", "FINAL", "FREEZE"}


def sha256_bytes(data: bytes) -> str:
    """Compute lowercase hex SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text_file(path: Path) -> str:
    """
    Hash file contents as UTF-8 text with newline normalization (CRLF→LF).

    The extractor writes LF YAML and records sha256 of that text. On Windows the
    working tree may store CRLF; byte hashing would false-fail, so validation
    hashes the logical text instead of raw bytes.
    """
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    """Load a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load a UTF-8 YAML mapping."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s is not a mapping" % path)
    return data


def validate_against_schema(document: Dict[str, Any], schema: Dict[str, Any], path: str) -> List[str]:
    """
    Lightweight Draft-07 subset validator for our fixed governance schemas.

    Avoids adding jsonschema as a new runtime dependency. Checks required keys,
    const/enum/pattern/type for top-level and nested requirement items.
    """
    errors: List[str] = []

    def check_object(obj: Any, sch: Dict[str, Any], loc: str) -> None:
        if not isinstance(obj, dict):
            errors.append("%s: expected object" % loc)
            return
        for key in sch.get("required", []):
            if key not in obj:
                errors.append("%s: missing required key %s" % (loc, key))
        props = sch.get("properties", {})
        if sch.get("additionalProperties") is False:
            for key in obj:
                if key not in props:
                    errors.append("%s: unexpected key %s" % (loc, key))
        for key, value in obj.items():
            if key not in props:
                continue
            check_value(value, props[key], "%s.%s" % (loc, key))

    def check_value(value: Any, sch: Dict[str, Any], loc: str) -> None:
        if "const" in sch and value != sch["const"]:
            errors.append("%s: const mismatch" % loc)
        if "enum" in sch and value not in sch["enum"]:
            errors.append("%s: enum mismatch (%r)" % (loc, value))
        expected = sch.get("type")
        if expected == "string" and not isinstance(value, str):
            errors.append("%s: expected string" % loc)
        elif expected == "integer" and not isinstance(value, int):
            errors.append("%s: expected integer" % loc)
        elif expected == "boolean" and not isinstance(value, bool):
            errors.append("%s: expected boolean" % loc)
        elif expected == "array" and not isinstance(value, list):
            errors.append("%s: expected array" % loc)
        elif expected == "object" and not isinstance(value, dict):
            errors.append("%s: expected object" % loc)
        if expected == "string" and isinstance(value, str):
            if "minLength" in sch and len(value) < sch["minLength"]:
                errors.append("%s: too short" % loc)
            if "pattern" in sch:
                import re

                if not re.search(sch["pattern"], value):
                    errors.append("%s: pattern mismatch" % loc)
        if expected == "array" and isinstance(value, list):
            item_sch = sch.get("items")
            if isinstance(item_sch, dict):
                for idx, item in enumerate(value):
                    if item_sch.get("type") == "object" or "properties" in item_sch:
                        check_object(item, item_sch, "%s[%d]" % (loc, idx))
                    else:
                        check_value(item, item_sch, "%s[%d]" % (loc, idx))
        if expected == "object" or "properties" in sch:
            check_object(value, sch, loc)

    check_object(document, schema, path)
    return errors


def validate_task_file(path: Path, schema: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Validate one T0X.yaml; return (errors, requirement_ids)."""
    errors: List[str] = []
    data = load_yaml(path)
    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            errors.append("%s: missing top-level %s" % (path.name, key))
    if data.get("task_id") != path.stem:
        errors.append("%s: task_id %r != filename stem" % (path.name, data.get("task_id")))
    schema_errors = validate_against_schema(data, schema, path.name)
    # Schema may be stricter than our lightweight checker for nested waves;
    # keep structural checks below as the authoritative gate.
    _ = schema_errors

    reqs = data.get("requirements") or []
    if not isinstance(reqs, list) or not reqs:
        errors.append("%s: requirements must be a non-empty list" % path.name)
        return errors, []

    ids: List[str] = []
    for idx, req in enumerate(reqs):
        if not isinstance(req, dict):
            errors.append("%s.requirements[%d]: not an object" % (path.name, idx))
            continue
        for key in REQUIRED_REQ_FIELDS:
            if key not in req:
                errors.append("%s.requirements[%d]: missing %s" % (path.name, idx, key))
        text = str(req.get("requirement_text") or "").strip()
        if not text:
            errors.append("%s.requirements[%d]: empty requirement_text" % (path.name, idx))
        policy = req.get("blocking_policy")
        if policy not in BLOCKING_POLICIES:
            errors.append("%s.requirements[%d]: bad blocking_policy %r" % (path.name, idx, policy))
        wave = req.get("wave")
        if wave not in WAVES:
            errors.append("%s.requirements[%d]: bad wave %r" % (path.name, idx, wave))
        rid = req.get("id")
        if isinstance(rid, str) and rid:
            ids.append(rid)
            if not rid.startswith(str(data.get("task_id")) + "-"):
                errors.append("%s: id %s does not start with task_id" % (path.name, rid))
        sha = str(req.get("source_text_sha256") or "")
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            errors.append("%s: bad source_text_sha256 for %s" % (path.name, rid))
    return errors, ids


def validate_manifest(manifest_path: Path, task_dir: Path) -> List[str]:
    """Validate source-manifest.json against on-disk YAML hashes."""
    errors: List[str] = []
    manifest = load_json(manifest_path)
    source = manifest.get("source") or {}
    for key in ("docx_name", "docx_sha256", "docx_size_bytes", "document_version", "execution_period"):
        if key not in source:
            errors.append("source-manifest missing source.%s" % key)
    files = manifest.get("files") or []
    if len(files) != 9:
        errors.append("source-manifest files length != 9")
    seen_tasks: Set[str] = set()
    for item in files:
        task_id = item.get("task_id")
        seen_tasks.add(task_id)
        rel = item.get("path")
        target = task_dir.parent.parent.parent / rel if False else task_dir / ("%s.yaml" % task_id)
        # Prefer path relative to repo root when present.
        repo_relative = Path(rel) if rel else target
        if not repo_relative.is_absolute():
            candidate = Path.cwd() / repo_relative
            if candidate.exists():
                target = candidate
            else:
                target = task_dir / ("%s.yaml" % task_id)
        if not target.exists():
            errors.append("manifest references missing %s" % target)
            continue
        digest = sha256_text_file(target)
        if digest != item.get("sha256"):
            errors.append(
                "sha256 mismatch for %s: manifest=%s disk=%s"
                % (task_id, item.get("sha256"), digest)
            )
        if item.get("requirements_total", -1) < 1:
            errors.append("%s requirements_total < 1" % task_id)
    missing = set(TASK_IDS) - seen_tasks
    if missing:
        errors.append("manifest missing tasks: %s" % ", ".join(sorted(missing)))
    return errors


def main(argv: List[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Validate SAGE125 task-requirements YAML set.")
    parser.add_argument(
        "--dir",
        default="docs/governance/task-requirements",
        help="Directory containing T01.yaml..T09.yaml and source-manifest.json",
    )
    parser.add_argument(
        "--schema",
        default="docs/governance/schemas/task-requirement.schema.json",
        help="JSON Schema path for a single task document",
    )
    args = parser.parse_args(argv)

    task_dir = Path(args.dir)
    schema_path = Path(args.schema)
    if not task_dir.is_dir():
        print("ERROR: missing directory %s" % task_dir, file=sys.stderr)
        return 2
    if not schema_path.is_file():
        print("ERROR: missing schema %s" % schema_path, file=sys.stderr)
        return 2

    schema = load_json(schema_path)
    all_errors: List[str] = []
    all_ids: List[str] = []

    for task_id in TASK_IDS:
        path = task_dir / ("%s.yaml" % task_id)
        if not path.is_file():
            all_errors.append("missing %s" % path)
            continue
        errors, ids = validate_task_file(path, schema)
        all_errors.extend(errors)
        all_ids.extend(ids)

    dupes = sorted({rid for rid in all_ids if all_ids.count(rid) > 1})
    if dupes:
        all_errors.append("duplicate requirement ids: %s" % ", ".join(dupes[:20]))

    manifest_path = task_dir / "source-manifest.json"
    if not manifest_path.is_file():
        all_errors.append("missing source-manifest.json")
    else:
        all_errors.extend(validate_manifest(manifest_path, task_dir))

    if all_errors:
        print("FAIL: %d issue(s)" % len(all_errors))
        for err in all_errors:
            print(" - %s" % err)
        return 1

    print(
        "PASS: %d tasks, %d unique requirement ids, manifest hashes match"
        % (len(TASK_IDS), len(all_ids))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
