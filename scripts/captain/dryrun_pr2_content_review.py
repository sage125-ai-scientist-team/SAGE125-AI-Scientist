# -*- coding: utf-8 -*-
"""
Read-only content-review DryRun helper for central PR #2 (T09 Wave A).

Writes content-review.json under %TEMP%\\sage125-pr-review\\... and prints the
resulting ENGINEERING/CONTENT compliance summary. Never calls gh pr review/merge
and never modifies the teammate branch.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "governance" / "task-requirements" / "T09.yaml"
REPO = "sage125-ai-scientist-team/SAGE125-AI-Scientist"


def sha256_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def gh_json(args: list[str]) -> dict:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit("gh failed: %s" % (proc.stderr or proc.stdout))
    return json.loads(proc.stdout)


def classify_wave_a(spec: dict, changed_files: list[str], is_draft: bool, checks_total: int) -> list[dict]:
    """Produce requirement judgments for T09 Wave A from observable PR facts only."""
    files = set(changed_files)
    has_workflow = any(p.startswith(".github/workflows/") for p in files)
    has_eval_docs = any("eval" in p.lower() or "reproducibility" in p.lower() for p in files)
    has_tests = any(p.startswith("tests/") for p in files)
    reqs = []
    for item in spec["requirements"]:
        if item.get("wave") != "A":
            # Future waves deferred for Wave A PR.
            if item.get("wave") in {"B", "C", "FINAL", "FREEZE"}:
                reqs.append(
                    {
                        "requirement_id": item["id"],
                        "status": "DEFERRED",
                        "severity": "P2",
                        "wave": item.get("wave"),
                        "requirement_text": item["requirement_text"],
                        "observed_implementation": "Deferred: not required for Wave A PR.",
                        "evidence_paths": [],
                        "evidence_commands": [],
                        "missing_evidence": [],
                        "consequence": "Tracked for later wave.",
                        "required_fix": "",
                        "verification_command": "n/a for Wave A",
                        "blocking": False,
                    }
                )
            continue

        text = item["requirement_text"]
        rid = item["id"]
        cat = item.get("category")
        status = "UNVERIFIED"
        missing = []
        evidence_paths = []
        required_fix = ""
        severity = "P1"
        blocking = item.get("blocking_policy") in {"P0_BLOCKING", "P1_BLOCKING"}

        if "lint/type/unit/integration/security/build" in text or (
            cat == "must_deliver" and "GitHub Actions" in text
        ):
            if has_workflow:
                status = "UNVERIFIED"
                missing = [
                    "cannot confirm all six stable job names from PR file list alone",
                    "need workflow YAML inspection + failing-path proof",
                ]
                evidence_paths = [p for p in files if p.startswith(".github/workflows/")]
            else:
                status = "FAIL"
                missing = ["no .github/workflows change in PR"]
                required_fix = "Add CI skeleton with lint/type/unit/integration/security/build jobs"
        elif "Draft" in text or cat == "daily_deliverable":
            if is_draft:
                status = "PASS"
                evidence_commands = ["gh pr view 2 --json isDraft"]
                evidence_paths = []
                missing = []
                # mark pass with command evidence
                reqs.append(
                    {
                        "requirement_id": rid,
                        "status": "PASS",
                        "severity": "P2",
                        "wave": "A",
                        "requirement_text": text,
                        "observed_implementation": "PR is Draft as required for early Wave A opening.",
                        "evidence_paths": [],
                        "evidence_commands": ["gh pr view 2 --json isDraft,url"],
                        "missing_evidence": [],
                        "consequence": "",
                        "required_fix": "",
                        "verification_command": "gh pr view 2 --json isDraft",
                        "blocking": False,
                    }
                )
                continue
            status = "UNVERIFIED"
            missing = ["Draft/Ready state not aligned with this deliverable wording"]
        elif cat in {"acceptance_evidence", "daily_work"}:
            status = "UNVERIFIED"
            missing = ["need linked CI run, fixture proof, or local command output"]
            if has_tests:
                evidence_paths = [p for p in files if p.startswith("tests/")]
        elif "评测" in text or "Evaluation" in text or "benchmark" in text.lower():
            if has_eval_docs:
                status = "UNVERIFIED"
                missing = ["evaluation contract text present? need explicit RFC/contract file proof"]
                evidence_paths = [p for p in files if "eval" in p.lower() or "reproduc" in p.lower()]
            else:
                status = "FAIL"
                required_fix = "Add evaluation/CI contract artifacts for Wave A"
                missing = ["no eval/reproducibility paths in PR"]
        else:
            status = "UNVERIFIED"
            missing = ["insufficient repository evidence in this DryRun"]

        if status == "FAIL" and item.get("blocking_policy") == "P0_BLOCKING":
            severity = "P0"
        reqs.append(
            {
                "requirement_id": rid,
                "status": status,
                "severity": severity if status in {"FAIL", "UNVERIFIED"} and blocking else "P2",
                "wave": "A",
                "requirement_text": text,
                "observed_implementation": (
                    "DryRun observation from PR #2 file list / draft flag / checks count=%s"
                    % checks_total
                ),
                "evidence_paths": evidence_paths,
                "evidence_commands": ["gh pr view 2 --json files,isDraft,statusCheckRollup"],
                "missing_evidence": missing,
                "consequence": "Wave A content gate not satisfied" if status != "PASS" else "",
                "required_fix": required_fix,
                "verification_command": "gh pr checks 2 --repo %s" % REPO,
                "blocking": bool(blocking and status in {"FAIL", "UNVERIFIED"}),
            }
        )
    return reqs


def main() -> int:
    machine = gh_json(
        [
            "pr",
            "view",
            "2",
            "--repo",
            REPO,
            "--json",
            "number,title,isDraft,headRefOid,headRefName,files,url",
        ]
    )
    title = machine["title"]
    head = machine["headRefOid"]
    branch = machine["headRefName"]
    is_draft = bool(machine["isDraft"])
    files = [f["path"] for f in machine.get("files") or []]

    # checks may fail for fork PRs; treat unavailable as zero
    checks_total = 0
    try:
        checks = subprocess.run(
            ["gh", "pr", "checks", "2", "--repo", REPO, "--json", "name,bucket,state"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if checks.returncode == 0 and checks.stdout.strip():
            checks_total = len(json.loads(checks.stdout))
    except Exception:
        checks_total = 0

    # Task/wave recognition (title/branch)
    task = "T09" if ("T09" in title or "t09" in branch.lower()) else "UNKNOWN"
    wave = "A" if ("[T09-A]" in title or "/a-" in branch.lower()) else "UNKNOWN"
    if task != "T09" or wave != "A":
        print("CONTENT_COMPLIANCE=WAIT (task/wave not identified as T09/A)")
        return 30

    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    requirements = classify_wave_a(spec, files, is_draft, checks_total)

    def count(status: str) -> int:
        return sum(1 for r in requirements if r["status"] == status)

    fail = count("FAIL")
    unverified = count("UNVERIFIED")
    deferred = count("DEFERRED")
    passed = count("PASS")
    na = count("NOT_APPLICABLE")
    p0 = sum(1 for r in requirements if r["severity"] == "P0" and r["status"] in {"FAIL", "UNVERIFIED"})
    p1 = sum(1 for r in requirements if r["severity"] == "P1" and r["status"] in {"FAIL", "UNVERIFIED"})
    p2 = sum(1 for r in requirements if r["severity"] == "P2")

    blocking_ids = [r["requirement_id"] for r in requirements if r.get("blocking")]
    current_fail_or_unverified = any(
        r["wave"] == "A" and r["status"] in {"FAIL", "UNVERIFIED"} and r.get("blocking")
        for r in requirements
    )
    if fail:
        content = "FAIL"
        current = "FAIL"
    elif current_fail_or_unverified:
        content = "FAIL"
        current = "UNVERIFIED"
    else:
        content = "PASS"
        current = "PASS"

    # Engineering: Draft + likely 0 checks => WAIT
    engineering = "WAIT" if is_draft or checks_total == 0 else "PASS"

    out_dir = Path(os.environ.get("TEMP") or os.environ["TMP"]) / "sage125-pr-review" / (
        "pr-2-%s" % head
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    # Ensure outside repo
    if str(ROOT).lower() in str(out_dir).lower():
        out_dir = Path.home() / "AppData" / "Local" / "Temp" / "sage125-pr-review" / ("pr-2-%s" % head)
        out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": 1,
        "repository": REPO,
        "pr_number": 2,
        "reviewed_head_sha": head,
        "task_id": "T09",
        "wave": "A",
        "source_spec_path": "docs/governance/task-requirements/T09.yaml",
        "source_spec_sha256": sha256_file(SPEC),
        "requirements_total": len(requirements),
        "pass_count": passed,
        "fail_count": fail,
        "unverified_count": unverified,
        "deferred_count": deferred,
        "not_applicable_count": na,
        "p0_count": p0,
        "p1_count": p1,
        "p2_count": p2,
        "current_wave_status": current,
        "final_dod_coverage": {
            "total": len(spec.get("definition_of_done") or []),
            "pass": 0,
            "outstanding": len(spec.get("definition_of_done") or []),
            "verified_at_wave_c": False,
        },
        "content_compliance": content,
        "blocking_requirement_ids": blocking_ids,
        "recommendation_ids": [],
        "reviewer": "dryrun-pr2-content-review",
        "reviewed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "requirements": requirements,
    }
    out_path = out_dir / "content-review.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("PR #2 DryRun content acceptance")
    print("title:", title)
    print("branch:", branch)
    print("head:", head)
    print("draft:", is_draft)
    print("changed_files:", len(files))
    print("checks_total:", checks_total)
    print("TASK=T09 WAVE=A")
    print("ENGINEERING_COMPLIANCE=%s" % engineering)
    print("CONTENT_COMPLIANCE=%s" % content)
    print("P0=%d P1=%d P2=%d" % (p0, p1, p2))
    print("fail=%d unverified=%d deferred=%d pass=%d" % (fail, unverified, deferred, passed))
    print("content-review:", out_path)
    print("side_effects: review_calls=0 merge_calls=0")
    return 0 if content in {"PASS", "FAIL", "WAIT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
