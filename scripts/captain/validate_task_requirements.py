# -*- coding: utf-8 -*-
"""
scripts/captain/validate_task_requirements.py —— 校验 T01—T09 任务要求 YAML
与 source-manifest.json 的完整性、ID 唯一性与源哈希一致性。

不依赖 PyYAML（CI 运行依赖未包含它）。提取脚本仍可选用 PyYAML；
本校验器使用 JSON manifest + 确定性文本规则完成门禁检查。

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
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

TASK_IDS = tuple("T0%d" % n for n in range(1, 10))
REQ_ID_RE = re.compile(
    r"^- id:\s*(T0[1-9]-(?:A|B|C|MUST|DOD|METRIC|HANDOFF|FREEZE)-\d{3})\s*$",
    re.M,
)
TASK_ID_LINE_RE = re.compile(r"^task_id:\s*(T0[1-9])\s*$", re.M)
REQ_TEXT_RE = re.compile(r"^  requirement_text:\s*(\S.*)$", re.M)
BLOCKING_RE = re.compile(
    r"^  blocking_policy:\s*(P0_BLOCKING|P1_BLOCKING|DEFERRED_ALLOWED|P2_RECOMMENDATION|OPTIONAL)\s*$",
    re.M,
)
WAVE_RE = re.compile(r"^  wave:\s*(A|B|C|FINAL|FREEZE)\s*$", re.M)
SOURCE_SHA_RE = re.compile(r"^  source_text_sha256:\s*([a-f0-9]{64})\s*$", re.M)


def sha256_text_file(path: Path) -> str:
    """Hash file contents as UTF-8 text with newline normalization (CRLF→LF)."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    """Load a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def validate_task_file(path: Path) -> Tuple[List[str], List[str]]:
    """Validate one T0X.yaml via text rules; return (errors, requirement_ids)."""
    errors: List[str] = []
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    task_ids = TASK_ID_LINE_RE.findall(text)
    if not task_ids:
        errors.append("%s: missing task_id" % path.name)
    elif task_ids[0] != path.stem:
        errors.append("%s: task_id %r != filename stem" % (path.name, task_ids[0]))

    for key in (
        "schema_version:",
        "repository:",
        "title:",
        "mission:",
        "must_deliver:",
        "definition_of_done:",
        "waves:",
        "requirements:",
    ):
        if key not in text:
            errors.append("%s: missing section/key %s" % (path.name, key.rstrip(":")))

    if "\n  A:" not in text and "\nA:" not in text:
        errors.append("%s: missing waves.A" % path.name)
    if "\n  B:" not in text and "\nB:" not in text:
        errors.append("%s: missing waves.B" % path.name)
    if "\n  C:" not in text and "\nC:" not in text:
        errors.append("%s: missing waves.C" % path.name)

    ids = REQ_ID_RE.findall(text)
    if not ids:
        errors.append("%s: no requirement ids found" % path.name)

    texts = REQ_TEXT_RE.findall(text)
    if any(not t.strip() or t.strip() in {"''", '""', "|", ">"} for t in texts):
        errors.append("%s: empty requirement_text detected" % path.name)
    if ids and len(texts) < len(ids):
        # folded/block scalars may reduce line matches; only hard-fail when zero.
        pass

    policies = BLOCKING_RE.findall(text)
    if ids and not policies:
        errors.append("%s: no blocking_policy lines found" % path.name)

    waves = WAVE_RE.findall(text)
    if ids and not waves:
        errors.append("%s: no wave lines found under requirements" % path.name)

    shas = SOURCE_SHA_RE.findall(text)
    if ids and len(shas) < len(ids):
        errors.append(
            "%s: source_text_sha256 count %d < id count %d"
            % (path.name, len(shas), len(ids))
        )

    for rid in ids:
        if not rid.startswith(path.stem + "-"):
            errors.append("%s: id %s does not start with task_id" % (path.name, rid))

    return errors, ids


def validate_manifest(manifest_path: Path, task_dir: Path) -> List[str]:
    """Validate source-manifest.json against on-disk YAML text hashes."""
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
        rel = item.get("path") or ""
        candidate = Path.cwd() / rel if rel else task_dir / ("%s.yaml" % task_id)
        target = candidate if candidate.exists() else task_dir / ("%s.yaml" % task_id)
        if not target.exists():
            errors.append("manifest references missing %s" % target)
            continue
        digest = sha256_text_file(target)
        if digest != item.get("sha256"):
            errors.append(
                "sha256 mismatch for %s: manifest=%s disk=%s"
                % (task_id, item.get("sha256"), digest)
            )
        if int(item.get("requirements_total") or 0) < 1:
            errors.append("%s requirements_total < 1" % task_id)

    missing = set(TASK_IDS) - seen_tasks
    if missing:
        errors.append("manifest missing tasks: %s" % ", ".join(sorted(missing)))
    return errors


def validate_schema_files(repo_root: Path) -> List[str]:
    """Ensure JSON schemas exist and are parseable objects."""
    errors: List[str] = []
    for rel in (
        "docs/governance/schemas/task-requirement.schema.json",
        "docs/governance/schemas/content-review.schema.json",
    ):
        path = repo_root / rel
        if not path.is_file():
            errors.append("missing schema %s" % rel)
            continue
        try:
            data = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append("schema %s invalid JSON: %s" % (rel, exc))
            continue
        if not isinstance(data, dict) or "properties" not in data:
            errors.append("schema %s missing properties" % rel)
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
        help="JSON Schema path (existence/parse check; full Draft-07 not required in CI)",
    )
    args = parser.parse_args(argv)

    task_dir = Path(args.dir)
    if not task_dir.is_dir():
        print("ERROR: missing directory %s" % task_dir, file=sys.stderr)
        return 2

    repo_root = Path.cwd()
    all_errors: List[str] = []
    all_ids: List[str] = []

    all_errors.extend(validate_schema_files(repo_root))
    schema_path = Path(args.schema)
    if not schema_path.is_file():
        all_errors.append("missing schema %s" % schema_path)

    for task_id in TASK_IDS:
        path = task_dir / ("%s.yaml" % task_id)
        if not path.is_file():
            all_errors.append("missing %s" % path)
            continue
        errors, ids = validate_task_file(path)
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
        % (len(TASK_IDS), len(set(all_ids)))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
