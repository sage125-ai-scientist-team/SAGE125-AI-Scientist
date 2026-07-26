# -*- coding: utf-8 -*-
"""
Governance regression tests for V3.0 task-content acceptance.

Covers the captain-required scenarios without merging real PRs or calling
gh pr review / gh pr merge. Does not read .env.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
REQ_DIR = ROOT / "docs" / "governance" / "task-requirements"
SCHEMA_CR = ROOT / "docs" / "governance" / "schemas" / "content-review.schema.json"
VALIDATE_TASKS = ROOT / "scripts" / "captain" / "validate_task_requirements.py"
VALIDATE_CR = ROOT / "scripts" / "captain" / "validate_content_review.py"


@pytest.fixture
def tmp_path():
    """
    Writable temp dir for this host.

    Some Windows environments deny creating pytest-of-<user> under %TEMP%.
    Keep artifacts under .pytest_tmp (untracked / local only).
    """
    import uuid

    base = ROOT / ".pytest_tmp" / "gov-tests" / uuid.uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sha256_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _base_review(**overrides):
    spec = REQ_DIR / "T09.yaml"
    data = {
        "schema_version": 1,
        "repository": "sage125-ai-scientist-team/SAGE125-AI-Scientist",
        "pr_number": 2,
        "reviewed_head_sha": "a" * 40,
        "task_id": "T09",
        "wave": "A",
        "source_spec_path": "docs/governance/task-requirements/T09.yaml",
        "source_spec_sha256": _sha256_file(spec),
        "requirements_total": 1,
        "pass_count": 0,
        "fail_count": 0,
        "unverified_count": 0,
        "deferred_count": 0,
        "not_applicable_count": 0,
        "p0_count": 0,
        "p1_count": 0,
        "p2_count": 0,
        "current_wave_status": "PASS",
        "final_dod_coverage": {
            "total": 3,
            "pass": 0,
            "outstanding": 3,
            "verified_at_wave_c": False,
        },
        "content_compliance": "PASS",
        "blocking_requirement_ids": [],
        "recommendation_ids": [],
        "requirements": [],
    }
    data.update(overrides)
    return data


def _req(
    rid: str,
    status: str,
    *,
    wave: str = "A",
    severity: str = "P1",
    blocking: bool = True,
    evidence_paths=None,
    evidence_commands=None,
    missing_evidence=None,
    required_fix: str = "",
):
    return {
        "requirement_id": rid,
        "status": status,
        "severity": severity,
        "wave": wave,
        "requirement_text": "synthetic requirement text",
        "observed_implementation": "synthetic observation",
        "evidence_paths": evidence_paths or [],
        "evidence_commands": evidence_commands or [],
        "missing_evidence": missing_evidence or [],
        "consequence": "synthetic consequence",
        "required_fix": required_fix,
        "verification_command": "py -3 -m pytest -q",
        "blocking": blocking,
    }


def _write_review(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "content-review.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run_validate(path: Path, *, merge_gate: bool = False, head: str = "a" * 40):
    cmd = [
        sys.executable,
        str(VALIDATE_CR),
        "--content-review",
        str(path),
        "--pr-number",
        "2",
        "--task-id",
        "T09",
        "--wave",
        "A",
        "--head-sha",
        head,
        "--source-spec",
        str(REQ_DIR / "T09.yaml"),
    ]
    if merge_gate:
        cmd.append("--require-merge-gate")
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")


def test_validate_task_requirements_pass():
    proc = subprocess.run(
        [sys.executable, str(VALIDATE_TASKS)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


def test_nine_task_yaml_exist_and_have_waves():
    for tid in [f"T0{i}" for i in range(1, 10)]:
        doc = yaml.safe_load((REQ_DIR / f"{tid}.yaml").read_text(encoding="utf-8"))
        assert doc["task_id"] == tid
        assert set(doc["waves"]) >= {"A", "B", "C"}
        assert doc["requirements"]
        assert all(r.get("requirement_text") for r in doc["requirements"])


def test_engineering_green_but_wave_deliverable_missing_is_fail(tmp_path):
    """Scenario 1: engineering green, current-wave must-deliver missing → FAIL."""
    data = _base_review(
        content_compliance="FAIL",
        current_wave_status="FAIL",
        fail_count=1,
        p1_count=1,
        blocking_requirement_ids=["T09-A-001"],
        requirements=[
            _req("T09-A-001", "FAIL", required_fix="Add CI skeleton jobs", blocking=True)
        ],
    )
    path = _write_review(tmp_path, data)
    proc = _run_validate(path, merge_gate=True)
    assert proc.returncode == 1
    assert "content_compliance" in proc.stdout.lower() or "FAIL" in proc.stdout


def test_pr_claim_without_evidence_is_unverified(tmp_path):
    """Scenario 2: claim without code/tests/evidence → UNVERIFIED, no merge."""
    data = _base_review(
        content_compliance="FAIL",
        current_wave_status="UNVERIFIED",
        unverified_count=1,
        p1_count=1,
        blocking_requirement_ids=["T09-A-002"],
        requirements=[
            _req(
                "T09-A-002",
                "UNVERIFIED",
                missing_evidence=["no workflow file", "no CI run link"],
                blocking=True,
            )
        ],
    )
    path = _write_review(tmp_path, data)
    proc = _run_validate(path, merge_gate=True)
    assert proc.returncode == 1


def test_wave_a_missing_wave_c_metric_is_deferred_not_blocking(tmp_path):
    """Scenario 3: Wave A PR missing Wave C metric → DEFERRED."""
    data = _base_review(
        content_compliance="PASS",
        current_wave_status="PASS",
        deferred_count=1,
        pass_count=0,
        requirements_total=1,
        requirements=[
            _req(
                "T09-C-001",
                "DEFERRED",
                wave="C",
                severity="P2",
                blocking=False,
            )
        ],
    )
    # recount
    data["deferred_count"] = 1
    path = _write_review(tmp_path, data)
    proc = _run_validate(path, merge_gate=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_wave_c_missing_final_dod_is_fail(tmp_path):
    """Scenario 4: Wave C without final DoD → FAIL."""
    data = _base_review(
        wave="C",
        content_compliance="FAIL",
        current_wave_status="FAIL",
        fail_count=1,
        p1_count=1,
        final_dod_coverage={
            "total": 3,
            "pass": 1,
            "outstanding": 2,
            "verified_at_wave_c": False,
        },
        blocking_requirement_ids=["T09-DOD-001"],
        requirements=[
            _req("T09-DOD-001", "FAIL", wave="C", required_fix="Complete final DoD")
        ],
    )
    path = _write_review(tmp_path, data)
    proc = subprocess.run(
        [
            sys.executable,
            str(VALIDATE_CR),
            "--content-review",
            str(path),
            "--pr-number",
            "2",
            "--task-id",
            "T09",
            "--wave",
            "C",
            "--head-sha",
            "a" * 40,
            "--source-spec",
            str(REQ_DIR / "T09.yaml"),
            "--require-merge-gate",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 1


def test_metric_screenshot_only_unverified(tmp_path):
    """Scenario 5: quantitative metric with only screenshot → UNVERIFIED."""
    item = _req(
        "T09-METRIC-001",
        "UNVERIFIED",
        wave="B",
        missing_evidence=["no script", "no raw results", "no checksum"],
        blocking=True,
    )
    item["evidence_paths"] = ["docs/screenshot.png"]
    data = _base_review(
        wave="B",
        content_compliance="FAIL",
        current_wave_status="UNVERIFIED",
        unverified_count=1,
        p1_count=1,
        requirements=[item],
        blocking_requirement_ids=["T09-METRIC-001"],
    )
    path = _write_review(tmp_path, data)
    proc = subprocess.run(
        [
            sys.executable,
            str(VALIDATE_CR),
            "--content-review",
            str(path),
            "--wave",
            "B",
            "--task-id",
            "T09",
            "--pr-number",
            "2",
            "--head-sha",
            "a" * 40,
            "--source-spec",
            str(REQ_DIR / "T09.yaml"),
            "--require-merge-gate",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 1


def test_metric_full_evidence_can_pass(tmp_path):
    """Scenario 6: metric with script/data/raw/command/commit can PASS."""
    data = _base_review(
        content_compliance="PASS",
        current_wave_status="PASS",
        pass_count=1,
        requirements=[
            _req(
                "T09-METRIC-001",
                "PASS",
                wave="A",
                blocking=False,
                severity="P2",
                evidence_paths=[
                    "scripts/eval/run_benchmark.py",
                    "docs/reproducibility/metrics_raw.json",
                    "docs/reproducibility/metrics.json",
                ],
                evidence_commands=["py -3 scripts/eval/run_benchmark.py --offline"],
            )
        ],
    )
    path = _write_review(tmp_path, data)
    assert _run_validate(path, merge_gate=True).returncode == 0


def test_assert_true_only_is_fail(tmp_path):
    """Scenario 7: trivial assert True tests → FAIL."""
    data = _base_review(
        content_compliance="FAIL",
        current_wave_status="FAIL",
        fail_count=1,
        p1_count=1,
        blocking_requirement_ids=["T09-A-003"],
        requirements=[
            _req(
                "T09-A-003",
                "FAIL",
                required_fix="Replace assert True with behavioral assertions",
            )
        ],
    )
    path = _write_review(tmp_path, data)
    assert _run_validate(path, merge_gate=True).returncode == 1


@pytest.mark.parametrize(
    ("rid", "note"),
    [
        ("T02-B-001", "Reviewer feedback saved but not fed into next round"),
        ("T03-B-001", "feedback saved but prompt lacks feedback_id"),
        ("T05-B-001", "planned marked as actual"),
        ("T07-B-001", "question body reused across ids"),
        ("T08-B-001", "API boots but loop incomplete"),
        ("T09-A-004", "six jobs green but eval contract missing"),
    ],
)
def test_task_specific_blocking_scenarios(tmp_path, rid, note):
    """Scenarios 8-13: task-specific content failures remain blocking."""
    severity = "P0" if "T05" in rid and "planned" in note else "P1"
    status = "FAIL"
    data = _base_review(
        task_id=rid[:3],
        wave="A" if "-A-" in rid else "B",
        content_compliance="FAIL",
        current_wave_status="FAIL",
        fail_count=1,
        p0_count=1 if severity == "P0" else 0,
        p1_count=0 if severity == "P0" else 1,
        source_spec_path=f"docs/governance/task-requirements/{rid[:3]}.yaml",
        source_spec_sha256=_sha256_file(REQ_DIR / f"{rid[:3]}.yaml"),
        blocking_requirement_ids=[rid],
        requirements=[
            _req(
                rid,
                status,
                wave="A" if "-A-" in rid else "B",
                severity=severity,
                required_fix=note,
            )
        ],
    )
    # For T05 planned→actual use P0
    if rid.startswith("T05"):
        data["requirements"][0]["severity"] = "P0"
        data["p0_count"] = 1
        data["p1_count"] = 0
    path = _write_review(tmp_path, data)
    proc = subprocess.run(
        [
            sys.executable,
            str(VALIDATE_CR),
            "--content-review",
            str(path),
            "--pr-number",
            "2",
            "--task-id",
            rid[:3],
            "--wave",
            data["wave"],
            "--head-sha",
            "a" * 40,
            "--source-spec",
            str(REQ_DIR / f"{rid[:3]}.yaml"),
            "--require-merge-gate",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 1, note


def test_p2_only_allows_merge(tmp_path):
    """Scenario 14: only P2 recommendations → CONTENT_COMPLIANCE=PASS."""
    data = _base_review(
        content_compliance="PASS",
        current_wave_status="PASS",
        p2_count=1,
        pass_count=1,
        recommendation_ids=["T09-A-005"],
        requirements=[
            _req(
                "T09-A-005",
                "PASS",
                severity="P2",
                blocking=False,
                evidence_paths=["docs/reproducibility/README.md"],
                evidence_commands=["gh pr checks 2"],
            )
        ],
    )
    path = _write_review(tmp_path, data)
    assert _run_validate(path, merge_gate=True).returncode == 0


def test_stale_head_sha_rejected(tmp_path):
    """Scenario 17: content-review head SHA expired → fail validation."""
    data = _base_review(reviewed_head_sha="b" * 40)
    data["requirements"] = [
        _req(
            "T09-A-001",
            "PASS",
            blocking=False,
            evidence_paths=["x"],
            evidence_commands=["y"],
        )
    ]
    data["pass_count"] = 1
    path = _write_review(tmp_path, data)
    proc = _run_validate(path, merge_gate=True, head="a" * 40)
    assert proc.returncode == 1
    assert "head" in proc.stdout.lower() or "mismatch" in proc.stdout.lower()


def test_stale_source_spec_sha_rejected(tmp_path):
    """Scenario 18: source spec SHA expired → fail validation."""
    data = _base_review(source_spec_sha256="c" * 64)
    data["requirements"] = [
        _req(
            "T09-A-001",
            "PASS",
            blocking=False,
            evidence_paths=["x"],
            evidence_commands=["y"],
        )
    ]
    data["pass_count"] = 1
    path = _write_review(tmp_path, data)
    proc = _run_validate(path, merge_gate=True)
    assert proc.returncode == 1
    assert "source_spec" in proc.stdout.lower() or "stale" in proc.stdout.lower()


def test_content_review_schema_file_exists():
    assert SCHEMA_CR.is_file()
    schema = json.loads(SCHEMA_CR.read_text(encoding="utf-8"))
    assert "content_compliance" in schema["required"]


def test_pass_without_evidence_rejected_by_validator(tmp_path):
    data = _base_review(
        pass_count=1,
        requirements=[_req("T09-A-001", "PASS", blocking=False)],
    )
    path = _write_review(tmp_path, data)
    proc = _run_validate(path)
    assert proc.returncode == 1
    assert "evidence" in proc.stdout.lower()
