"""Cross-platform Wave C host probe with auditable raw evidence.

The short probe exercises the real T08 FastAPI application factory, SQLite
stores, in-process queue, authentication boundary, and API-only Streamlit
process.  It uses a deterministic slow synthetic runner so restart recovery can
be triggered without external model calls.  It is not a substitute for the
required 120-minute Docker run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ACTOR_A = "probe-actor-a"
ACTOR_B = "probe-actor-b"
TOKEN_A = "probe-actor-a-token"
TOKEN_B = "probe-actor-b-token"


def _utc_now() -> str:
    """Return a timezone-aware UTC timestamp for every evidence event."""
    return datetime.now(timezone.utc).isoformat()


def _json_request(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any]]:
    """Perform one bounded JSON request and preserve structured error bodies."""
    headers = {"Accept": "application/json"}
    if token:
        headers["X-API-Key"] = token
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def _wait_http(url: str, *, timeout_seconds: float) -> None:
    """Wait for one HTTP endpoint or raise with a bounded timeout."""
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - retained for final diagnosis
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"endpoint did not become ready: {url}") from last_error


def _process_sample(process: subprocess.Popen[Any]) -> dict[str, Any]:
    """Collect bounded RSS/CPU/descriptor metrics without third-party packages."""
    if process.poll() is not None:
        return {"pid": process.pid, "running": False}
    sample: dict[str, Any] = {"pid": process.pid, "running": True}
    try:
        output = subprocess.check_output(
            ["ps", "-o", "rss=,%cpu=", "-p", str(process.pid)],
            text=True,
            timeout=5,
        ).strip()
        rss, cpu = output.split()
        sample.update({"rss_kib": int(rss), "cpu_percent": float(cpu)})
    except (OSError, ValueError, subprocess.SubprocessError):
        sample.update({"rss_kib": None, "cpu_percent": None})
    if shutil.which("lsof"):
        try:
            output = subprocess.check_output(
                ["lsof", "-p", str(process.pid)],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            sample["open_file_rows"] = max(0, len(output.splitlines()) - 1)
        except (OSError, subprocess.SubprocessError):
            sample["open_file_rows"] = None
    else:
        sample["open_file_rows"] = None
    return sample


def _git_evidence() -> dict[str, Any]:
    """Bind evidence to the current commit and record dirty-worktree validity."""
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
    )
    return {
        "git_sha": sha,
        "worktree_clean": not bool(status.strip()),
        "dirty_path_count": len(status.splitlines()),
    }


def _safe_evidence_text(value: str) -> str:
    """Redact project and home absolute paths from committed evidence."""
    return (
        value.replace(str(ROOT), "<project>")
        .replace(str(Path.home()), "<home>")
    )


def _sanitize_log(path: Path) -> None:
    """Rewrite one text log with local absolute paths redacted."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    path.write_text(_safe_evidence_text(text), encoding="utf-8")


class _SlowProbeRunner:
    """Deterministic mock runner long enough to exercise restart recovery."""

    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds

    def run(self, job, progress_callback):
        """Emit progress, wait, and return fully explicit mock completion evidence."""
        from app.api.job_queue import CompletionEvidence, JobRunResult

        progress_callback({"stage": "probe_running", "status": "running"})
        time.sleep(self.delay_seconds)
        return JobRunResult(
            upstream_run_id=f"probe-run-{job.job_id}",
            completion_evidence=CompletionEvidence(
                required_artifacts_present=True,
                quality_gate_passed=True,
                blocking_issues_closed=True,
                truth_status_explicit=True,
                traceable_and_serializable=True,
            ),
        )


def _serve_api(args: argparse.Namespace) -> int:
    """Serve an isolated API instance backed by the probe's persistent state."""
    import uvicorn

    from app.api.auth import FixedWindowRateLimiter, HashedAPIKeyAuth
    from app.api.job_store import SQLiteJobStore
    from app.api.main import create_app

    state_root = Path(args.state_dir)
    export_root = state_root / "exports"
    os.environ["SAGE_TEST_EXPORT_DIR"] = str(export_root)
    os.environ["EXPORT_DIR"] = str(export_root)
    os.environ["DATA_DIR"] = str(state_root / "data")
    os.environ["PREVIEW_EPHEMERAL_STORAGE"] = "false"
    application = create_app(
        job_store=SQLiteJobStore(state_root / "jobs.sqlite3"),
        job_runner=_SlowProbeRunner(args.job_delay_seconds),
        worker_count=1,
        queue_capacity=20,
        auth_policy=HashedAPIKeyAuth(
            {ACTOR_A: TOKEN_A, ACTOR_B: TOKEN_B}
        ),
        rate_limiter=FixedWindowRateLimiter(
            limit=100_000,
            window_seconds=60,
        ),
        artifact_root=state_root / "artifacts",
    )
    uvicorn.run(
        application,
        host="127.0.0.1",
        port=args.api_port,
        log_level="info",
    )
    return 0


def _start_api(
    args: argparse.Namespace,
    *,
    log_path: Path,
) -> tuple[subprocess.Popen[Any], Any]:
    """Start the probe API and return both process and owned log stream."""
    stream = log_path.open("ab")
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "serve-api",
        "--state-dir",
        args.state_dir,
        "--api-port",
        str(args.api_port),
        "--job-delay-seconds",
        str(args.job_delay_seconds),
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=stream,
        stderr=subprocess.STDOUT,
    )
    return process, stream


def _start_ui(
    args: argparse.Namespace,
    *,
    log_path: Path,
) -> tuple[subprocess.Popen[Any], Any]:
    """Start the API-only Streamlit process with no backend fallback."""
    stream = log_path.open("ab")
    environment = {
        **os.environ,
        "SAGE_UI_API_BASE_URL": f"http://127.0.0.1:{args.api_port}",
        "SAGE_UI_API_KEY": TOKEN_A,
        "SAGE_UI_TIMEOUT_SECONDS": "3",
    }
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "frontend/streamlit_app.py",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(args.ui_port),
        "--server.headless",
        "true",
        "--client.showErrorDetails",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=stream,
        stderr=subprocess.STDOUT,
    )
    return process, stream


def _stop_process(process: subprocess.Popen[Any] | None) -> None:
    """Stop one process without leaving a background server behind."""
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _run_probe(args: argparse.Namespace) -> int:
    """Execute the host short probe and write raw, machine-readable evidence."""
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir = Path(
        args.state_dir
        or tempfile.mkdtemp(prefix="sage125-wave-c-short-")
    ).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    args.state_dir = str(state_dir)
    api_url = f"http://127.0.0.1:{args.api_port}"
    ui_url = f"http://127.0.0.1:{args.ui_port}"
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    failures: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    job_ids: list[str] = []
    api: subprocess.Popen[Any] | None = None
    ui: subprocess.Popen[Any] | None = None
    streams: list[Any] = []

    def record(event: str, **details: Any) -> None:
        """Append one timestamped probe event."""
        events.append({"at": _utc_now(), "event": event, **details})

    def check(condition: bool, code: str, **details: Any) -> None:
        """Record a failed assertion while allowing evidence collection to continue."""
        if not condition:
            failures.append({"at": _utc_now(), "code": code, **details})

    try:
        api, api_stream = _start_api(
            args,
            log_path=output_dir / "api-initial.log",
        )
        streams.append(api_stream)
        _wait_http(f"{api_url}/health", timeout_seconds=30)
        record("api_started", pid=api.pid)

        ui, ui_stream = _start_ui(
            args,
            log_path=output_dir / "ui.log",
        )
        streams.append(ui_stream)
        _wait_http(f"{ui_url}/_stcore/health", timeout_seconds=30)
        record("ui_started", pid=ui.pid)

        def submit(index: int) -> tuple[int, dict[str, Any]]:
            return _json_request(
                f"{api_url}/api/v1/jobs",
                method="POST",
                token=TOKEN_A,
                correlation_id=f"wave-c-short-{index}",
                idempotency_key=f"wave-c-short-key-{index}",
                payload={
                    "question_id": f"Q00{index}",
                    "mode": "mock",
                    "options": {},
                },
            )

        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            submitted = list(
                pool.map(submit, range(1, args.concurrency + 1))
            )
        check(
            all(status == 202 for status, _ in submitted),
            "CONCURRENT_SUBMISSION_FAILED",
            statuses=[status for status, _ in submitted],
        )
        job_ids = [
            payload["job_id"]
            for status, payload in submitted
            if status == 202 and payload.get("job_id")
        ]
        check(
            len(set(job_ids)) == args.concurrency,
            "JOB_ID_ISOLATION_FAILED",
            job_ids=job_ids,
        )
        record("five_jobs_submitted", job_ids=job_ids)

        for job_id in job_ids:
            status, _payload = _json_request(
                f"{api_url}/api/v1/jobs/{job_id}",
                token=TOKEN_B,
            )
            check(
                status == 403,
                "CROSS_ACTOR_ISOLATION_FAILED",
                job_id=job_id,
                observed_status=status,
            )
        record("cross_actor_checks_completed", count=len(job_ids))

        time.sleep(1)
        if api.poll() is None:
            api.kill()
            api.wait(timeout=10)
        record("api_network_outage_started")
        try:
            urllib.request.urlopen(f"{api_url}/health", timeout=2)
            check(False, "API_OUTAGE_NOT_OBSERVED")
        except Exception:  # noqa: BLE001 - expected outage
            record("api_outage_observed")

        ui_status = urllib.request.urlopen(
            f"{ui_url}/_stcore/health",
            timeout=5,
        ).status
        check(ui_status == 200, "UI_DIED_DURING_API_OUTAGE")
        record("ui_survived_api_outage", status=ui_status)

        api, restart_stream = _start_api(
            args,
            log_path=output_dir / "api-restart.log",
        )
        streams.append(restart_stream)
        _wait_http(f"{api_url}/health", timeout_seconds=30)
        ui_root_status = urllib.request.urlopen(ui_url, timeout=10).status
        check(ui_root_status == 200, "UI_RECONNECT_FAILED")
        record(
            "api_restarted_and_ui_reconnected",
            api_pid=api.pid,
            ui_status=ui_root_status,
        )

        deadline = started_monotonic + args.duration_seconds
        while time.monotonic() < deadline:
            api_status, health = _json_request(f"{api_url}/health")
            check(api_status == 200, "API_HEALTH_FAILED", status=api_status)
            try:
                ui_health = urllib.request.urlopen(
                    f"{ui_url}/_stcore/health",
                    timeout=5,
                ).status
            except Exception:
                ui_health = 0
            check(ui_health == 200, "UI_HEALTH_FAILED", status=ui_health)
            statuses: dict[str, str] = {}
            for job_id in job_ids:
                status, payload = _json_request(
                    f"{api_url}/api/v1/jobs/{job_id}",
                    token=TOKEN_A,
                )
                check(
                    status == 200,
                    "JOB_STATUS_READ_FAILED",
                    job_id=job_id,
                    status=status,
                )
                if status == 200:
                    statuses[job_id] = str(payload.get("status"))
            samples.append(
                {
                    "at": _utc_now(),
                    "api_health_status": health.get("status"),
                    "api_dependencies": health.get("dependencies"),
                    "ui_health_status": ui_health,
                    "job_statuses": statuses,
                    "api_process": _process_sample(api),
                    "ui_process": _process_sample(ui),
                    "failure_count": len(failures),
                }
            )
            time.sleep(min(args.sample_interval_seconds, max(0.1, deadline - time.monotonic())))

        terminal: dict[str, str] = {}
        for job_id in job_ids:
            status, payload = _json_request(
                f"{api_url}/api/v1/jobs/{job_id}",
                token=TOKEN_A,
            )
            if status == 200:
                terminal[job_id] = str(payload.get("status"))
        check(
            len(terminal) == args.concurrency,
            "JOB_STATE_LOST_AFTER_RESTART",
            terminal=terminal,
        )
        check(
            all(value == "completed" for value in terminal.values()),
            "JOBS_NOT_COMPLETED",
            terminal=terminal,
        )

        from app.api.job_store import SQLiteJobStore

        reopened = SQLiteJobStore(state_dir / "jobs.sqlite3")
        reopened.initialize()
        recovery_events = [
            event
            for job_id in job_ids
            for event in reopened.list_events(job_id)
            if event.get("source") == "startup_recovery"
        ]
        check(
            bool(recovery_events),
            "QUEUE_RECOVERY_EVENT_MISSING",
        )
        record(
            "queue_recovery_verified",
            recovery_event_count=len(recovery_events),
            terminal=terminal,
        )
    except Exception as exc:  # noqa: BLE001 - evidence must survive probe failure
        failures.append(
            {
                "at": _utc_now(),
                "code": "PROBE_EXCEPTION",
                "error_type": type(exc).__name__,
                "message": _safe_evidence_text(str(exc)),
            }
        )
    finally:
        _stop_process(api)
        _stop_process(ui)
        for stream in streams:
            stream.close()
        for log_name in ("api-initial.log", "api-restart.log", "ui.log"):
            _sanitize_log(output_dir / log_name)

    ended_at = _utc_now()
    elapsed = time.monotonic() - started_monotonic
    git = _git_evidence()
    max_api_rss = max(
        (
            sample["api_process"].get("rss_kib") or 0
            for sample in samples
        ),
        default=0,
    )
    max_ui_rss = max(
        (
            sample["ui_process"].get("rss_kib") or 0
            for sample in samples
        ),
        default=0,
    )
    metrics = {
        "schema_version": "t08.wave_c_stability_probe.v1",
        "runtime": "host_synthetic_runner",
        "started_at": started_at,
        "ended_at": ended_at,
        "requested_duration_seconds": args.duration_seconds,
        "elapsed_seconds": round(elapsed, 3),
        "concurrency": args.concurrency,
        "sample_interval_seconds": args.sample_interval_seconds,
        "job_delay_seconds": args.job_delay_seconds,
        **git,
        "final_evidence_valid": (
            args.duration_seconds >= 7200
            and git["worktree_clean"]
            and False
        ),
        "failure_count": len(failures),
        "failures": failures,
        "events": events,
        "samples": samples,
        "job_ids": job_ids,
        "max_api_rss_kib": max_api_rss,
        "max_ui_rss_kib": max_ui_rss,
        "resource_leak_result": "UNVERIFIED_SHORT_HOST_RUN",
        "reproduction_command": (
            "python tests/api/wave_c_stability_probe.py run "
            f"--duration-seconds {args.duration_seconds} "
            f"--concurrency {args.concurrency} "
            f"--sample-interval-seconds {args.sample_interval_seconds} "
            f"--output-dir {_safe_evidence_text(str(output_dir))}"
        ),
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "reproduction.txt").write_text(
        metrics["reproduction_command"] + "\n",
        encoding="utf-8",
    )
    summary = [
        "# T08 Wave C host short probe",
        "",
        f"- Started: `{started_at}`",
        f"- Ended: `{ended_at}`",
        f"- Elapsed seconds: `{elapsed:.3f}`",
        f"- Git SHA: `{git['git_sha']}`",
        f"- Worktree clean: `{git['worktree_clean']}`",
        f"- Concurrency: `{args.concurrency}`",
        f"- Failure count: `{len(failures)}`",
        f"- Max API RSS KiB: `{max_api_rss}`",
        f"- Max UI RSS KiB: `{max_ui_rss}`",
        "- Formal 120-minute result: `WAIT_DOCKER_UNAVAILABLE`",
        "- Final evidence valid: `false`",
        "",
        "This short host run uses a deterministic synthetic runner. It exercises",
        "API/UI process boundaries and persistent T08 stores, but cannot replace",
        "the final 7200-second Docker test on a clean commit.",
    ]
    (output_dir / "summary.md").write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )
    return 0 if not failures else 1


def _parser() -> argparse.ArgumentParser:
    """Build the two-mode CLI used by the orchestrator and API child."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve-api")
    serve.add_argument("--state-dir", required=True)
    serve.add_argument("--api-port", type=int, required=True)
    serve.add_argument("--job-delay-seconds", type=float, default=5.0)

    run = subparsers.add_parser("run")
    run.add_argument("--duration-seconds", type=int, default=120)
    run.add_argument("--concurrency", type=int, default=5)
    run.add_argument("--sample-interval-seconds", type=float, default=5.0)
    run.add_argument("--job-delay-seconds", type=float, default=5.0)
    run.add_argument("--api-port", type=int, default=18000)
    run.add_argument("--ui-port", type=int, default=18501)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--state-dir", default="")
    return parser


def main() -> int:
    """Dispatch the host short probe or its isolated API child process."""
    args = _parser().parse_args()
    if args.command == "serve-api":
        return _serve_api(args)
    return _run_probe(args)


if __name__ == "__main__":
    raise SystemExit(main())
