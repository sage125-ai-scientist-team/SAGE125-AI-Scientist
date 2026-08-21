"""Build the formal 125 preflight lock files and evidence package."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.formal125.hashes import write_json  # noqa: E402
from app.formal125.preflight import build_preflight_package  # noqa: E402


STAMP = "20260821-142429"
COMMITS = [
    ("c2d155d483c5ca9f32d734e9d3d98eb0837e1f07", "B", "FLAGSHIP_EVIDENCE_REQUIRED", True, "keep", "Q028 canonical implementation snapshot"),
    ("f29fbf4a40ac3f0b17df4d8a8cd03de8672f1c87", "B", "FORMAL_125_RUNTIME_REQUIRED", True, "keep", "reviewer loop and publication provenance"),
    ("1ae89e0d886e5fd770a64489785f605b7e67fcfd", "C", "FLAGSHIP_EVIDENCE_REQUIRED", True, "keep", "verified Q028 canonical artifacts"),
    ("79b1a42c161cd8f2e40847d97d9bc71c367d5a8c", "E", "DISPLAY_OPTIONAL", True, "keep", "canonical-status API/UI details"),
    ("a7bdd52b82e6135687df54b8d214a64805cb211a", "C", "FLAGSHIP_EVIDENCE_REQUIRED", True, "keep", "versioned multi-commit provenance attestation"),
    ("c3d0dfd55486e05db346c36185a33f74a26bc936", "D", "ABLATION_EVIDENCE_REQUIRED", True, "keep", "Q028 no-reviewer protocol"),
    ("015a0a62a0646c83c93a7aaa31596b1da44e6734", "D", "ABLATION_EVIDENCE_REQUIRED", True, "keep", "no-reviewer arm implementation"),
    ("b8faeb9a7d366c1858abcd7ff6fe04755d60432b", "D", "ABLATION_EVIDENCE_REQUIRED", True, "keep", "actual comparison artifacts"),
    ("e8dc0425fedb6117607bc1c42001f0b83823cb56", "B", "FORMAL_125_RUNTIME_REQUIRED", True, "keep", "evidence freeze guards"),
    ("b0e962cda5c7d2773566d908899fc0a5243a6759", "D", "ABLATION_EVIDENCE_REQUIRED", True, "keep", "verified no-reviewer freeze package"),
    ("b1e7e2e37a4e5d5d1a1e2cd85d55518382363efc", "D", "ABLATION_EVIDENCE_REQUIRED", True, "keep", "verified artifact sha pointer"),
    ("c26c70a", "E", "DISPLAY_OPTIONAL", True, "keep", "checksum status scoped to verified package"),
    ("e33a04ba1f756b3a5380f3b218cdf7578e1448c5", "E", "DISPLAY_OPTIONAL", True, "keep", "API overlay for verified comparison matrix"),
]


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def build_commit_matrix() -> dict:
    rows = []
    central = _git("rev-parse", "upstream/integration/2026-08-10")
    for sha, _letter, classification, required, action, reason in COMMITS:
        full = _git("rev-parse", sha)
        subject = _git("log", "-1", "--format=%s", full)
        names = _git("diff-tree", "--no-commit-id", "--name-only", "-r", full).splitlines()
        patch = subprocess.check_output(
            f'git show --format= {full} | git patch-id --stable',
            cwd=ROOT,
            shell=True,
            text=True,
        ).strip()
        patch_id = patch.split()[0] if patch else ""
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", full, central],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        already = ancestor.returncode == 0
        rows.append(
            {
                "commit_sha": full,
                "subject": subject,
                "paths": names,
                "patch_id": patch_id,
                "classification": classification,
                "already_in_central": already,
                "conflicts": [],
                "required_for_formal_125": required,
                "integration_action": "merged_via_no_ff_from_freeze_lineage" if not already else "skip_equivalent",
                "reason": reason,
            }
        )
    return {
        "central_integration_sha": central,
        "integration_commit_message": "local(formal125): integrate validated project capabilities",
        "commits": rows,
    }


def main() -> int:
    matrix = build_commit_matrix()
    write_json(ROOT / "docs" / "reproducibility" / "formal_125" / "LOCAL_VALIDATED_COMMIT_MATRIX.json", matrix)
    result = build_preflight_package(
        stamp=STAMP,
        run_root=Path(r"D:\SAGE125_Local_Runs") / f"formal_125_preflight_{STAMP}",
        commit_matrix=matrix,
        test_report={"status": "PENDING_FULL_PYTEST", "specialized": "PENDING"},
        clean_checkout_report={"status": "PENDING_FRESH_VERIFY"},
    )
    print(json.dumps({"package_dir": result["package_dir"], "checksum": result["checksum"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
