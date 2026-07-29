# -*- coding: utf-8 -*-
"""
scripts/captain/validate_content_review.py —— 校验 Agent 产出的 content-review.json。

合并前由 scripts/captain/review_latest_pr.ps1 -ContentReviewPath 调用，也可独立运行：

    py -3 scripts/captain/validate_content_review.py `
      --content-review <path> `
      --pr-number 2 `
      --task-id T09 `
      --wave A `
      --head-sha <40hex> `
      --source-spec docs/governance/task-requirements/T09.yaml

退出码：0 通过；1 内容门禁失败 / schema 失败；2 参数或文件错误。
不读取 .env；不修改仓库文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

STATUSES = {"PASS", "FAIL", "UNVERIFIED", "DEFERRED", "NOT_APPLICABLE"}
COMPLIANCE = {"PASS", "FAIL", "WAIT"}
WAVES = {"A", "B", "C", "FREEZE"}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[a-f0-9]{64}$")
REQ_ID = re.compile(r"^T0[1-9]-(A|B|C|MUST|DOD|METRIC|HANDOFF|FREEZE)-[0-9]{3}$")


def sha256_file(path: Path) -> str:
    """Lowercase hex SHA-256 of logical UTF-8 text (CRLF normalized to LF)."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON object from path."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("content-review root must be an object")
    return data


def validate_content_review(
    data: Dict[str, Any],
    *,
    expected_pr: Optional[int] = None,
    expected_task: Optional[str] = None,
    expected_wave: Optional[str] = None,
    expected_head_sha: Optional[str] = None,
    source_spec_path: Optional[Path] = None,
) -> List[str]:
    """
    Validate content-review.json semantics and optional identity bindings.

    Returns a list of human-readable error strings (empty means OK for schema/
    consistency). Callers that need CONTENT_COMPLIANCE=PASS for merge must also
    inspect data['content_compliance'] and blocking counts.
    """
    errors: List[str] = []
    required = [
        "schema_version",
        "repository",
        "pr_number",
        "reviewed_head_sha",
        "task_id",
        "wave",
        "source_spec_path",
        "source_spec_sha256",
        "requirements_total",
        "pass_count",
        "fail_count",
        "unverified_count",
        "deferred_count",
        "not_applicable_count",
        "p0_count",
        "p1_count",
        "p2_count",
        "current_wave_status",
        "final_dod_coverage",
        "content_compliance",
        "blocking_requirement_ids",
        "recommendation_ids",
        "requirements",
    ]
    for key in required:
        if key not in data:
            errors.append("missing key: %s" % key)

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("repository") != "sage125-ai-scientist-team/SAGE125-AI-Scientist":
        errors.append("repository mismatch")

    if expected_pr is not None and data.get("pr_number") != expected_pr:
        errors.append(
            "pr_number mismatch: expected=%s actual=%s" % (expected_pr, data.get("pr_number"))
        )
    if expected_task is not None and data.get("task_id") != expected_task:
        errors.append(
            "task_id mismatch: expected=%s actual=%s" % (expected_task, data.get("task_id"))
        )
    if expected_wave is not None and data.get("wave") != expected_wave:
        errors.append(
            "wave mismatch: expected=%s actual=%s" % (expected_wave, data.get("wave"))
        )
    head = str(data.get("reviewed_head_sha") or "")
    if not SHA40.match(head):
        errors.append("reviewed_head_sha must be 40 lowercase hex chars")
    if expected_head_sha and head != expected_head_sha.lower():
        errors.append(
            "reviewed_head_sha stale/mismatch: expected=%s actual=%s"
            % (expected_head_sha.lower(), head)
        )

    if data.get("wave") not in WAVES:
        errors.append("wave invalid: %r" % data.get("wave"))
    if data.get("content_compliance") not in COMPLIANCE:
        errors.append("content_compliance invalid: %r" % data.get("content_compliance"))
    if data.get("current_wave_status") not in {"PASS", "FAIL", "UNVERIFIED", "WAIT"}:
        errors.append("current_wave_status invalid: %r" % data.get("current_wave_status"))

    spec_sha = str(data.get("source_spec_sha256") or "")
    if not SHA64.match(spec_sha):
        errors.append("source_spec_sha256 invalid")
    if source_spec_path is not None:
        if not source_spec_path.is_file():
            errors.append("source spec missing: %s" % source_spec_path)
        else:
            disk = sha256_file(source_spec_path)
            if disk != spec_sha:
                errors.append(
                    "source_spec_sha256 stale: disk=%s review=%s" % (disk, spec_sha)
                )

    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        errors.append("requirements must be an array")
        return errors

    if data.get("requirements_total") != len(reqs):
        errors.append(
            "requirements_total=%s != len(requirements)=%s"
            % (data.get("requirements_total"), len(reqs))
        )

    counters = {
        "PASS": 0,
        "FAIL": 0,
        "UNVERIFIED": 0,
        "DEFERRED": 0,
        "NOT_APPLICABLE": 0,
    }
    for idx, item in enumerate(reqs):
        if not isinstance(item, dict):
            errors.append("requirements[%d] not an object" % idx)
            continue
        for key in (
            "requirement_id",
            "status",
            "severity",
            "requirement_text",
            "observed_implementation",
            "evidence_paths",
            "evidence_commands",
            "missing_evidence",
            "consequence",
            "required_fix",
            "verification_command",
            "blocking",
        ):
            if key not in item:
                errors.append("requirements[%d] missing %s" % (idx, key))
        rid = item.get("requirement_id")
        if not isinstance(rid, str) or not REQ_ID.match(rid):
            errors.append("requirements[%d] bad requirement_id %r" % (idx, rid))
        status = item.get("status")
        if status not in STATUSES:
            errors.append("requirements[%d] bad status %r" % (idx, status))
        else:
            counters[status] += 1
        if status == "PASS":
            evidence_paths = item.get("evidence_paths") or []
            evidence_commands = item.get("evidence_commands") or []
            if not evidence_paths and not evidence_commands:
                errors.append("%s PASS without evidence_paths/commands" % rid)
        if status == "FAIL":
            if not str(item.get("required_fix") or "").strip():
                errors.append("%s FAIL without required_fix" % rid)
        if status == "UNVERIFIED":
            missing = item.get("missing_evidence") or []
            if not missing:
                errors.append("%s UNVERIFIED without missing_evidence" % rid)
        if status == "DEFERRED":
            # Future-wave deferral must not claim current wave.
            if item.get("wave") == data.get("wave") and item.get("blocking") is True:
                errors.append("%s DEFERRED but blocking current wave" % rid)
        if not isinstance(item.get("blocking"), bool):
            errors.append("requirements[%d] blocking must be bool" % idx)

    for key, field in (
        ("PASS", "pass_count"),
        ("FAIL", "fail_count"),
        ("UNVERIFIED", "unverified_count"),
        ("DEFERRED", "deferred_count"),
        ("NOT_APPLICABLE", "not_applicable_count"),
    ):
        if data.get(field) != counters[key]:
            errors.append(
                "%s=%s != counted %s" % (field, data.get(field), counters[key])
            )

    dod = data.get("final_dod_coverage")
    if not isinstance(dod, dict):
        errors.append("final_dod_coverage must be object")
    else:
        for key in ("total", "pass", "outstanding", "verified_at_wave_c"):
            if key not in dod:
                errors.append("final_dod_coverage missing %s" % key)

    return errors


def evaluate_merge_gate(data: Dict[str, Any]) -> List[str]:
    """
    Extra merge-gate checks beyond schema/consistency.

    Merge is allowed only when content_compliance=PASS, fail_count=0,
    p0_count=0, p1_count=0, and no blocking UNVERIFIED on current wave.
    """
    errors: List[str] = []
    if data.get("content_compliance") != "PASS":
        errors.append("content_compliance is %s (need PASS)" % data.get("content_compliance"))
    if int(data.get("fail_count") or 0) != 0:
        errors.append("fail_count must be 0")
    if int(data.get("p0_count") or 0) != 0:
        errors.append("p0_count must be 0")
    if int(data.get("p1_count") or 0) != 0:
        errors.append("p1_count must be 0")
    if data.get("current_wave_status") not in {"PASS"}:
        # WAIT/FAIL/UNVERIFIED block merge
        errors.append(
            "current_wave_status is %s (need PASS)" % data.get("current_wave_status")
        )
    blocking_unverified = [
        item
        for item in (data.get("requirements") or [])
        if item.get("status") == "UNVERIFIED"
        and item.get("blocking") is True
        and item.get("wave") == data.get("wave")
    ]
    if blocking_unverified:
        errors.append(
            "blocking unverified on current wave: %s"
            % ", ".join(i.get("requirement_id", "?") for i in blocking_unverified[:10])
        )
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry."""
    parser = argparse.ArgumentParser(description="Validate a SAGE125 content-review.json")
    parser.add_argument("--content-review", required=True, help="Path to content-review.json")
    parser.add_argument("--pr-number", type=int, default=None)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--wave", default=None)
    parser.add_argument("--head-sha", default=None)
    parser.add_argument("--source-spec", default=None, help="Path to current T0X.yaml")
    parser.add_argument(
        "--require-merge-gate",
        action="store_true",
        help="Also require CONTENT_COMPLIANCE=PASS and zero P0/P1/FAIL/blocking-UNVERIFIED",
    )
    args = parser.parse_args(argv)

    path = Path(args.content_review)
    if not path.is_file():
        print("ERROR: missing content-review file: %s" % path, file=sys.stderr)
        return 2

    try:
        data = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("ERROR: cannot parse content-review: %s" % exc, file=sys.stderr)
        return 2

    source_spec = Path(args.source_spec) if args.source_spec else None
    errors = validate_content_review(
        data,
        expected_pr=args.pr_number,
        expected_task=args.task_id,
        expected_wave=args.wave,
        expected_head_sha=args.head_sha,
        source_spec_path=source_spec,
    )
    if args.require_merge_gate:
        errors.extend(evaluate_merge_gate(data))

    if errors:
        print("FAIL: %d issue(s)" % len(errors))
        for err in errors:
            print(" - %s" % err)
        return 1

    print(
        "PASS: content-review ok pr=%s task=%s wave=%s compliance=%s"
        % (
            data.get("pr_number"),
            data.get("task_id"),
            data.get("wave"),
            data.get("content_compliance"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
