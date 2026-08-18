"""Fixture-explicit server for truthful Wave C browser rehearsal.

This server exists only to exercise the browser and release-package workflow.
Every owner payload comes from `tests/api/fixtures` and remains `planned`,
fixture, or unavailable.  It must never be presented as production E2E proof.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FIXTURES = Path(__file__).with_name("fixtures")
DEMO_TOKEN = "browser-rehearsal-key"


class _DemoRunner:
    """Return an explicit planned fixture run without external calls."""

    def run(self, job, progress_callback):
        """Bind the browser job to the fixture owner identity."""
        from app.api.job_queue import CompletionEvidence, JobRunResult

        progress_callback({"stage": "fixture_projection", "status": "running"})
        return JobRunResult(
            upstream_run_id="run-owner-1",
            completion_evidence=CompletionEvidence(
                required_artifacts_present=True,
                quality_gate_passed=True,
                blocking_issues_closed=True,
                truth_status_explicit=True,
                traceable_and_serializable=True,
            ),
        )


def _load(name: str):
    """Load one committed contract fixture as JSON."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def build_app(state_root: Path):
    """Compose fixture ports while preserving production fail-closed feedback status."""
    from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
    from app.api.job_store import SQLiteJobStore
    from app.api.main import create_app
    from app.api.upstream import FixtureOwnerContractAdapter
    from app.export.canonical import CanonicalReport, StaticCanonicalReportSource

    state_root.mkdir(parents=True, exist_ok=True)
    os.environ["SAGE_TEST_EXPORT_DIR"] = str(state_root / "exports")
    questions = _load("question_items.json")
    evidence = _load("evidence_bundle.json")
    versions = _load("plan_versions.json")
    version_diff = _load("version_diff.json")
    report = CanonicalReport.model_validate(_load("canonical_report.json"))
    upstream = FixtureOwnerContractAdapter.from_payloads(
        questions=questions,
        evidence_by_identity={("run-owner-1", "Q001"): evidence},
        versions_by_identity={("run-owner-1", "Q001"): versions},
        diffs_by_identity={
            (
                "run-owner-1",
                "Q001",
                "run-owner-1:v1",
                "run-owner-1:v2",
            ): version_diff
        },
    )
    return create_app(
        job_store=SQLiteJobStore(state_root / "jobs.sqlite3"),
        job_runner=_DemoRunner(),
        upstream_read_port=upstream,
        auth_policy=HashedAPIKeyAuth(
            {"browser-rehearsal": DEMO_TOKEN}
        ),
        rate_limiter=FixedWindowRateLimiter(
            limit=10_000,
            window_seconds=60,
        ),
        canonical_report_source=StaticCanonicalReportSource(
            {"run-owner-1": report}
        ),
        artifact_root=state_root / "artifacts",
    )


def main() -> int:
    """Run the local fixture-explicit FastAPI server."""
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18010)
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    uvicorn.run(
        build_app(Path(args.state_dir)),
        host="127.0.0.1",
        port=args.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
