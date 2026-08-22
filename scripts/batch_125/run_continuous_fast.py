"""Formal 125 continuous-fast supervisor: evidence producer + model consumer."""

from __future__ import annotations

import argparse
import json
import os
import random
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.evidence.oa_fulltext import FulltextFetchAudit  # noqa: E402
from app.evidence.remediation import build_seed_bundle  # noqa: E402
from app.formal125.actual_run import (  # noqa: E402
    install_captain_runtime_env,
    is_auth_failure,
    materialize_questions,
    package_question,
)
from app.formal125.authorization import require_actual_authorization  # noqa: E402
from app.formal125.continuous_fast import (  # noqa: E402
    AUTH_MAX_CALLS,
    AUTH_MAX_INPUT,
    AUTH_MAX_OUTPUT,
    EVIDENCE_DISCOVERY_CONCURRENCY,
    EVIDENCE_PREP_MAX_MINUTES_PER_QUESTION,
    LOCAL_CACHE_ROOTS,
    MANUAL_REVIEW_24,
    MAX_FULLTEXT_FETCH_ATTEMPTS_PER_QUESTION,
    METADATA_COMMIT_SHA,
    MODEL_QUESTION_CONCURRENCY_INITIAL,
    MODEL_QUESTION_CONCURRENCY_MAX,
    PROJECT_PROVIDER_CALLS_BEFORE,
    REUSED_CASE_IDS,
    SCIENTIFIC_PRODUCER_SHA,
    STAMP,
    STARTUP_SENTINEL_COUNT,
    add_retry,
    budget_from_measured_results,
    budget_state,
    catalog_item,
    claim_evidence_job,
    claim_model_job,
    copy_reused_question,
    ensure_relevance_template,
    hard_stop_triggered,
    init_queue,
    job_counts,
    load_catalog,
    mark_evidence_blocked,
    mark_evidence_ready,
    mark_model_done,
    official_question_ids,
    progress_payload,
    reclaim_stale_claims,
    record_event,
    remaining_case_ids,
    reuse_mode,
    scan_text_for_secrets,
    set_model_concurrency,
    trigger_hard_stop,
    utc_now,
    verify_locks,
    verify_set_identity,
    write_authorization_noclobber,
    write_blocked_package,
    write_review_packet,
    build_authorization_payload,
)
from app.formal125.evidence_rerun import _pipeline_with_frozen_bundle  # noqa: E402
from app.formal125.hashes import sha256_file  # noqa: E402
from app.formal125.actual_run import atomic_write_json, atomic_write_text  # noqa: E402


OUTPUT_ROOT = Path(rf"D:\SAGE125_Local_Runs\formal_125_fast_remaining_{STAMP}")
CANDIDATE_ROOT = Path(rf"D:\SAGE125_Local_Runs\formal_125_candidate_{STAMP}")
CACHE_ROOT = Path(rf"D:\SAGE125_Local_Evidence\formal_125_fast_{STAMP}")
PYTHON = Path(r"C:\Users\LYB\Desktop\学习\python\python.exe")

_RUNTIME_READY = threading.Event()
_SENTINEL_RELEASED = threading.Event()
_PDF_SEM = threading.Semaphore(2)
_HOST_SEM = threading.Semaphore(2)
_STOP = threading.Event()
_FETCH_TLS = threading.local()
_FETCH_WRAP_LOCK = threading.Lock()
_FETCH_WRAPPED = False
_DISPLAY = {"api": "http://127.0.0.1:8080", "ui": "http://127.0.0.1:8580"}
_ORCH_SHA = "pending"
_429_TIMES: list[float] = []
_SAFE_CALLS = 0
_CONC_LOCK = threading.Lock()
_REUSED_REPORTS: list[dict[str, Any]] = []


def git_head() -> str:
    import subprocess

    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def find_free_port(start: int) -> int:
    for port in range(start, start + 30):
        if port in {8020, 8030, 8040, 8050, 8060, 8070, 8520, 8530, 8540, 8550, 8560, 8570}:
            continue
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            continue
        finally:
            sock.close()
        return port
    raise RuntimeError("no free local port")


def install_wait_timeout_header() -> None:
    try:
        import openai

        original = openai.OpenAI

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            headers = dict(kwargs.get("default_headers") or {})
            headers["X-DashScope-Wait-Timeout"] = "60"
            kwargs["default_headers"] = headers
            return original(*args, **kwargs)

        openai.OpenAI = wrapped  # type: ignore[misc]
    except Exception:
        return


def install_fetch_budget(deadline: float) -> dict[str, int]:
    import app.evidence.oa_fulltext as oa
    import app.evidence.remediation as rem

    global _FETCH_WRAPPED
    state = {"n": 0, "deadline": deadline}
    _FETCH_TLS.budget = state
    with _FETCH_WRAP_LOCK:
        if _FETCH_WRAPPED:
            return state
        original = oa.fetch_arxiv_pdf

        def wrapped(**kwargs: Any) -> dict[str, Any]:
            budget = getattr(_FETCH_TLS, "budget", None)
            with _HOST_SEM:
                if budget is not None and (
                    time.time() > budget["deadline"] or budget["n"] >= MAX_FULLTEXT_FETCH_ATTEMPTS_PER_QUESTION
                ):
                    return {
                        "eligibility": "FETCH_FAILED",
                        "reason": "evidence_budget_exhausted",
                        "arxiv_id": kwargs.get("arxiv_id"),
                        "url": "",
                        "pages": [],
                    }
                if budget is not None:
                    budget["n"] += 1
                return original(**kwargs)

        oa.fetch_arxiv_pdf = wrapped
        rem.fetch_arxiv_pdf = wrapped
        _FETCH_WRAPPED = True
    return state


def refresh_manifest() -> None:
    questions: dict[str, Any] = {}
    counts = {"succeeded": 0, "partial": 0, "failed": 0, "blocked": 0, "pending": 0}
    for qid in official_question_ids():
        path = OUTPUT_ROOT / qid / "package_manifest.json"
        if not path.is_file():
            questions[qid] = {"status": "pending", "output_path": str(OUTPUT_ROOT / qid)}
            counts["pending"] += 1
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        status = str(manifest.get("status") or "pending")
        questions[qid] = {
            "status": status,
            "execution_mode": reuse_mode(qid) if qid in REUSED_CASE_IDS else manifest.get("execution_mode") or "NEW_ACTUAL",
            "provider_calls": 0 if qid in REUSED_CASE_IDS else manifest.get("provider_calls") or 0,
            "output_path": str(OUTPUT_ROOT / qid),
            "pdf_present": (OUTPUT_ROOT / qid / "result.pdf").is_file(),
        }
        counts[status] = counts.get(status, 0) + 1
    budget = budget_state(OUTPUT_ROOT) if (OUTPUT_ROOT / "runtime" / "queue.sqlite").exists() else {}
    payload = {
        "total": 125,
        "question_ids": official_question_ids(),
        "status_counts": {key: counts.get(key, 0) for key in ("succeeded", "partial", "failed", "blocked", "pending")},
        "status_count_total": sum(counts.get(key, 0) for key in ("succeeded", "partial", "failed", "blocked", "pending")),
        "reused_count": 15,
        "new_actual_count": 110,
        "succeeded_count": counts.get("succeeded", 0),
        "partial_count": counts.get("partial", 0),
        "failed_count": counts.get("failed", 0),
        "blocked_count": counts.get("blocked", 0),
        "questions": questions,
        "provider_calls": budget.get("calls") or 0,
        "input_tokens": budget.get("input_tokens") or 0,
        "output_tokens": budget.get("output_tokens") or 0,
        "estimated_cost": "unknown",
        "FINAL_SUBMISSION_READY": False,
        "updated_at": utc_now(),
    }
    atomic_write_json(OUTPUT_ROOT / "manifest.json", payload)
    atomic_write_json(OUTPUT_ROOT / "index.json", {"questions": questions, "total": 125})
    lines = ["# Formal 125 continuous-fast remaining", "", f"Updated: {payload['updated_at']}", ""]
    for qid, item in questions.items():
        lines.append(f"- {qid}: {item['status']}")
    atomic_write_text(OUTPUT_ROOT / "index.md", "\n".join(lines) + "\n")
    atomic_write_json(
        OUTPUT_ROOT / "provider_call_inventory.json",
        {
            "project_provider_calls_before": PROJECT_PROVIDER_CALLS_BEFORE,
            "formal_125_new_provider_calls": budget.get("calls") or 0,
            "project_provider_calls_after": PROJECT_PROVIDER_CALLS_BEFORE + int(budget.get("calls") or 0),
            "input_tokens": budget.get("input_tokens") or 0,
            "output_tokens": budget.get("output_tokens") or 0,
            "retries": budget.get("retries") or 0,
            "count_429": budget.get("count_429") or 0,
            "openrouter_calls": 0,
            "mock_calls": 0,
            "estimated_cost": "unknown",
            "updated_at": utc_now(),
        },
    )
    atomic_write_json(
        OUTPUT_ROOT / "budget_report.json",
        {
            **budget_from_measured_results(),
            "used_calls": budget.get("calls") or 0,
            "used_input_tokens": budget.get("input_tokens") or 0,
            "used_output_tokens": budget.get("output_tokens") or 0,
            "ratio": budget.get("ratio") or 0,
            "state": "ok",
            "estimated_cost": "unknown",
        },
    )
    atomic_write_json(
        OUTPUT_ROOT / "progress.json",
        progress_payload(
            output_root=OUTPUT_ROOT,
            reused_reports=_REUSED_REPORTS,
            api_url=_DISPLAY["api"],
            ui_url=_DISPLAY["ui"],
            heartbeat={"ts": utc_now(), "pid": os.getpid()},
        ),
    )


def enforce_budget_or_stop() -> None:
    state = budget_state(OUTPUT_ROOT)
    if state["ratio"] >= 1.0:
        trigger_hard_stop(OUTPUT_ROOT, "HARD_STOP_5", "authorization budget exhausted")
        _STOP.set()
    elif state["ratio"] >= 0.9:
        set_model_concurrency(OUTPUT_ROOT, 1)


def note_429() -> None:
    global _SAFE_CALLS
    now = time.time()
    with _CONC_LOCK:
        _429_TIMES.append(now)
        recent = [item for item in _429_TIMES if now - item <= 300]
        _429_TIMES[:] = recent
        _SAFE_CALLS = 0
        add_retry(OUTPUT_ROOT, is_429=True)
        current = int(budget_state(OUTPUT_ROOT)["model_concurrency"])
        if len(recent) >= 2:
            set_model_concurrency(OUTPUT_ROOT, 1)
            time.sleep(120)
        else:
            set_model_concurrency(OUTPUT_ROOT, max(1, current - 1))
            time.sleep(random.uniform(45, 75))


def note_success_call() -> None:
    global _SAFE_CALLS
    with _CONC_LOCK:
        _SAFE_CALLS += 1
        current = int(budget_state(OUTPUT_ROOT)["model_concurrency"])
        if _SAFE_CALLS >= 20 and current < MODEL_QUESTION_CONCURRENCY_MAX and _SENTINEL_RELEASED.is_set():
            set_model_concurrency(OUTPUT_ROOT, current + 1)
            _SAFE_CALLS = 0


def evidence_worker(worker_id: str) -> None:
    catalog = load_catalog(ROOT)
    while not _STOP.is_set() and not hard_stop_triggered(OUTPUT_ROOT):
        question_id = claim_evidence_job(OUTPUT_ROOT, worker_id)
        if question_id is None:
            time.sleep(2)
            if job_counts(OUTPUT_ROOT)["evidence_pending"] == 0 and job_counts(OUTPUT_ROOT)["evidence_running"] == 0:
                return
            continue
        try:
            item = catalog_item(catalog, question_id)
            ensure_relevance_template(item)
            deadline = time.time() + EVIDENCE_PREP_MAX_MINUTES_PER_QUESTION * 60
            install_fetch_budget(deadline)
            seed_root = OUTPUT_ROOT / "evidence_seeds"
            seed_root.mkdir(parents=True, exist_ok=True)
            audit = FulltextFetchAudit()
            bundle = build_seed_bundle(
                question_id=question_id,
                question_title=str(item.get("original_title") or question_id),
                cache_root=CACHE_ROOT,
                output_root=seed_root,
                audit=audit,
                local_cache_roots=[path for path in LOCAL_CACHE_ROOTS if path.exists()],
            )
            ready = bool(bundle.get("evidence_seed_ready"))
            if scan_text_for_secrets(json.dumps(bundle, ensure_ascii=False)):
                trigger_hard_stop(OUTPUT_ROOT, "HARD_STOP_1", f"secret pattern in seed {question_id}")
                _STOP.set()
                return
            if ready:
                mark_evidence_ready(OUTPUT_ROOT, question_id)
                record_event(OUTPUT_ROOT, "evidence_ready", question_id, {"ready": True})
            else:
                write_blocked_package(
                    question_dir=OUTPUT_ROOT / question_id,
                    question_id=question_id,
                    block_code="EVIDENCE_SEED_NOT_READY",
                    reason=str((bundle.get("topic_gate") or {}).get("blocking_reasons") or "seed_not_ready"),
                    orchestrator_sha=_ORCH_SHA,
                    seed=bundle,
                )
                mark_evidence_blocked(OUTPUT_ROOT, question_id, "EVIDENCE_SEED_NOT_READY")
                record_event(OUTPUT_ROOT, "evidence_blocked", question_id, {"ready": False})
                refresh_manifest()
        except Exception as exc:
            write_blocked_package(
                question_dir=OUTPUT_ROOT / question_id,
                question_id=question_id,
                block_code="EVIDENCE_SEED_NOT_READY",
                reason=type(exc).__name__,
                orchestrator_sha=_ORCH_SHA,
            )
            mark_evidence_blocked(OUTPUT_ROOT, question_id, "EVIDENCE_SEED_NOT_READY")
            record_event(OUTPUT_ROOT, "evidence_error", question_id, {"error": type(exc).__name__})
            refresh_manifest()


def model_worker(worker_id: str) -> None:
    _RUNTIME_READY.wait()
    while not _STOP.is_set() and not hard_stop_triggered(OUTPUT_ROOT):
        if not _SENTINEL_RELEASED.is_set() and worker_id not in {"model-1", "model-2", "model-3"}:
            time.sleep(1)
            continue
        target = int(budget_state(OUTPUT_ROOT)["model_concurrency"])
        ordinal = int(worker_id.split("-")[-1])
        if ordinal > target:
            time.sleep(2)
            continue
        question_id = claim_model_job(OUTPUT_ROOT, worker_id)
        if question_id is None:
            counts = job_counts(OUTPUT_ROOT)
            if counts["evidence_pending"] == 0 and counts["evidence_running"] == 0 and counts["model_queued"] == 0 and counts["model_running"] == 0:
                return
            time.sleep(2)
            continue
        enforce_budget_or_stop()
        if hard_stop_triggered(OUTPUT_ROOT):
            return
        os.environ["SAGE_EVIDENCE_BUNDLE_DIR"] = str(OUTPUT_ROOT / "evidence_seeds")
        question_dir = OUTPUT_ROOT / question_id
        question_dir.mkdir(parents=True, exist_ok=True)
        try:
            plan, state = _pipeline_with_frozen_bundle(question_id)
            with _PDF_SEM:
                packaged = package_question(
                    question_dir=question_dir,
                    question_id=question_id,
                    plan=plan,
                    state=state,
                    previous_texts={},
                    batch_calls=0,
                    batch_input=0,
                    batch_output=0,
                )
            if scan_text_for_secrets((question_dir / "result.md").read_text(encoding="utf-8", errors="ignore")):
                trigger_hard_stop(OUTPUT_ROOT, "HARD_STOP_1", f"secret pattern in {question_id}")
                _STOP.set()
                return
            lineage = {
                "question_id": question_id,
                "execution_mode": "NEW_ACTUAL",
                "scientific_producer_sha": SCIENTIFIC_PRODUCER_SHA,
                "orchestrator_sha": _ORCH_SHA,
                "actual_execution": False,
                "packaged_at": utc_now(),
            }
            atomic_write_json(question_dir / "attempt_lineage.json", lineage)
            mark_model_done(
                OUTPUT_ROOT,
                question_id,
                packaged["status"],
                packaged["calls"],
                packaged["input_tokens"],
                packaged["output_tokens"],
                _ORCH_SHA,
            )
            note_success_call()
            record_event(OUTPUT_ROOT, "model_done", question_id, {"status": packaged["status"], "calls": packaged["calls"]})
        except Exception as exc:
            if is_auth_failure(exc):
                trigger_hard_stop(OUTPUT_ROOT, "HARD_STOP_3", "provider authentication failure")
                _STOP.set()
                return
            text = str(exc)
            if "429" in text or "RateLimit" in type(exc).__name__:
                note_429()
            write_blocked_package(
                question_dir=question_dir,
                question_id=question_id,
                block_code="INDIVIDUAL_FAILED",
                reason=type(exc).__name__,
                orchestrator_sha=_ORCH_SHA,
            )
            mark_model_done(
                OUTPUT_ROOT,
                question_id,
                "failed",
                0,
                0,
                0,
                _ORCH_SHA,
                error_signature=type(exc).__name__,
            )
            record_event(OUTPUT_ROOT, "model_error", question_id, {"error": type(exc).__name__})
        refresh_manifest()
        maybe_checkpoint()


def maybe_checkpoint() -> None:
    counts = job_counts(OUTPUT_ROOT)
    completed = counts["completed"]
    if completed and completed % 5 == 0:
        atomic_write_json(
            OUTPUT_ROOT / "runtime" / f"checkpoint_{completed:03d}.json",
            {"completed": completed, "counts": counts, "ts": utc_now()},
        )
    if completed and completed % 10 == 0:
        wave = completed // 10
        atomic_write_json(
            OUTPUT_ROOT / "runtime" / f"wave_{wave:02d}_receipt.json",
            {"wave": wave, "completed": completed, "counts": counts, "ts": utc_now()},
        )


def sentinel_watch() -> None:
    seen: dict[str, str] = {}
    while not _STOP.is_set() and not _SENTINEL_RELEASED.is_set():
        conn_path = OUTPUT_ROOT / "runtime" / "queue.sqlite"
        if not conn_path.exists():
            time.sleep(2)
            continue
        from app.formal125.continuous_fast import connect_queue

        conn = connect_queue(OUTPUT_ROOT)
        rows = conn.execute(
            """
            SELECT question_id, domain_id, status, error_signature
            FROM jobs
            WHERE status IN ('failed', 'blocked', 'succeeded', 'partial')
            ORDER BY completed_at
            LIMIT 12
            """
        ).fetchall()
        conn.close()
        domains = []
        signatures: dict[str, set[str]] = {}
        for row in rows:
            domains.append(row["domain_id"])
            sig = row["error_signature"]
            if sig:
                signatures.setdefault(sig, set()).add(row["domain_id"])
                if len(signatures[sig]) >= 2:
                    trigger_hard_stop(
                        OUTPUT_ROOT,
                        "HARD_STOP_4",
                        f"systemic signature {sig} across domains {sorted(signatures[sig])}",
                    )
                    _STOP.set()
                    return
            seen[row["question_id"]] = row["status"]
        ready_domains = {row["domain_id"] for row in rows if row["status"] in {"succeeded", "partial", "failed", "blocked"}}
        if len(ready_domains) >= STARTUP_SENTINEL_COUNT or len(seen) >= STARTUP_SENTINEL_COUNT:
            _SENTINEL_RELEASED.set()
            record_event(OUTPUT_ROOT, "sentinel_released", None, {"count": len(seen)})
            return
        if job_counts(OUTPUT_ROOT)["evidence_pending"] == 0 and job_counts(OUTPUT_ROOT)["model_queued"] == 0:
            _SENTINEL_RELEASED.set()
            return
        time.sleep(5)
    _SENTINEL_RELEASED.set()


class ProgressHandler(BaseHTTPRequestHandler):
    mode = "api"

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/pdf/"):
            qid = unquote(self.path.split("/pdf/", 1)[1]).strip("/")
            pdf = OUTPUT_ROOT / qid / "result.pdf"
            if pdf.is_file():
                body = pdf.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        progress = progress_payload(
            output_root=OUTPUT_ROOT,
            reused_reports=_REUSED_REPORTS,
            api_url=_DISPLAY["api"],
            ui_url=_DISPLAY["ui"],
            heartbeat={"ts": utc_now(), "pid": os.getpid()},
        )
        if self.mode == "api" and (self.path in {"/", "/progress", "/api/progress"}):
            body = json.dumps(progress, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Formal 125 连续高速进度</title>
<meta http-equiv="refresh" content="15">
<style>body{{font-family:sans-serif;background:#0b1220;color:#e8eefc;margin:24px}}
.ok{{color:#7dffb3}}.warn{{color:#ffd37d}}</style></head><body>
<h1>SAGE125 Formal 125 连续高速只读进度</h1>
<pre>{json.dumps(progress, ensure_ascii=False, indent=2)}</pre>
<p>FINAL_SUBMISSION_READY=False</p>
</body></html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def start_display() -> None:
    api_port = find_free_port(8080)
    ui_port = find_free_port(8580)
    _DISPLAY["api"] = f"http://127.0.0.1:{api_port}"
    _DISPLAY["ui"] = f"http://127.0.0.1:{ui_port}"

    class ApiHandler(ProgressHandler):
        mode = "api"

    class UiHandler(ProgressHandler):
        mode = "ui"

    api = ThreadingHTTPServer(("127.0.0.1", api_port), ApiHandler)
    ui = ThreadingHTTPServer(("127.0.0.1", ui_port), UiHandler)
    threading.Thread(target=api.serve_forever, name="formal125-api", daemon=True).start()
    threading.Thread(target=ui.serve_forever, name="formal125-ui", daemon=True).start()
    atomic_write_json(
        OUTPUT_ROOT / "runtime" / "display.json",
        {"api": _DISPLAY["api"], "ui": _DISPLAY["ui"], "pid": os.getpid()},
    )


def assemble_candidate() -> None:
    CANDIDATE_ROOT.mkdir(parents=True, exist_ok=True)
    import shutil

    for qid in official_question_ids():
        src = OUTPUT_ROOT / qid
        dest = CANDIDATE_ROOT / qid
        dest.mkdir(parents=True, exist_ok=True)
        for name in (
            "result.md",
            "result.json",
            "result.pdf",
            "evidence_cards.json",
            "agent_trace.json",
            "validation.json",
            "provider_audit.json",
            "package_manifest.json",
            "checksums.sha256",
            "reuse_lineage.json",
            "attempt_lineage.json",
        ):
            path = src / name
            if path.is_file():
                target = dest / name
                if not target.exists():
                    shutil.copy2(path, target)
    if (OUTPUT_ROOT / "manifest.json").is_file():
        shutil.copy2(OUTPUT_ROOT / "manifest.json", CANDIDATE_ROOT / "manifest.json")
        shutil.copy2(OUTPUT_ROOT / "index.json", CANDIDATE_ROOT / "index.json")
        shutil.copy2(OUTPUT_ROOT / "index.md", CANDIDATE_ROOT / "index.md")
        shutil.copy2(OUTPUT_ROOT / "provider_call_inventory.json", CANDIDATE_ROOT / "provider_call_inventory.json")
        shutil.copy2(OUTPUT_ROOT / "budget_report.json", CANDIDATE_ROOT / "budget_report.json")
    review_root = CANDIDATE_ROOT / "manual_review_24"
    for qid in MANUAL_REVIEW_24:
        write_review_packet(CANDIDATE_ROOT / qid, review_root / qid)
    atomic_write_json(
        CANDIDATE_ROOT / "manual_review_24" / "summary.json",
        {
            "MANUAL_REVIEW_REQUIRED_COUNT": 24,
            "MANUAL_REVIEW_COMPLETED_COUNT": 0,
            "reviewed": False,
            "FINAL_SUBMISSION_READY": False,
        },
    )
    atomic_write_json(
        CANDIDATE_ROOT / "CANDIDATE_STATUS.json",
        {
            "FORMAL_125_CANDIDATE_STATUS": "PASS_WITH_GENUINE_PARTIALS_AND_BLOCKS",
            "FINAL_SUBMISSION_READY": False,
            "assembled_at": utc_now(),
        },
    )


def init_workspace() -> None:
    global _ORCH_SHA, _REUSED_REPORTS
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "runtime").mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "authorization").mkdir(parents=True, exist_ok=True)
    _ORCH_SHA = git_head()
    verify_set_identity()
    locks = verify_locks(ROOT)
    catalog = load_catalog(ROOT)
    remaining = remaining_case_ids()
    auth = build_authorization_payload(remaining=remaining, output_root=OUTPUT_ROOT, locks=locks)
    write_authorization_noclobber(OUTPUT_ROOT / "authorization" / "authorization.json", auth)
    require_actual_authorization(OUTPUT_ROOT / "authorization" / "authorization.json")
    reports = []
    for qid in REUSED_CASE_IDS:
        reports.append(copy_reused_question(qid, OUTPUT_ROOT))
    _REUSED_REPORTS = reports
    init_queue(OUTPUT_ROOT, remaining, catalog)
    reclaim_stale_claims(OUTPUT_ROOT)
    questions_path = OUTPUT_ROOT / "input" / "questions_125.json"
    materialize_questions(questions_path)
    os.environ["SAGE_EVIDENCE_BUNDLE_DIR"] = str(OUTPUT_ROOT / "evidence_seeds")
    os.environ["SAGE_FORMAL_125_OUTPUT_ROOT"] = str(OUTPUT_ROOT)
    install_captain_runtime_env(
        export_dir=OUTPUT_ROOT / "pipeline_exports",
        questions_path=questions_path,
        max_retries=1,
    )
    os.environ["LLM_MAX_RETRIES"] = "1"
    install_wait_timeout_header()
    _RUNTIME_READY.set()
    refresh_manifest()
    atomic_write_json(
        OUTPUT_ROOT / "runtime" / "init.json",
        {
            "STAMP": STAMP,
            "SCIENTIFIC_PRODUCER_SHA": SCIENTIFIC_PRODUCER_SHA,
            "ORCHESTRATOR_SHA": _ORCH_SHA,
            "METADATA_COMMIT_SHA": METADATA_COMMIT_SHA,
            "locks": locks,
            "set_identity": verify_set_identity(),
            "budget": budget_from_measured_results(),
            "reused": reports,
        },
    )


def supervisor_loop() -> int:
    global _ORCH_SHA
    init_workspace()
    start_display()
    refresh_manifest()
    atomic_write_text(
        OUTPUT_ROOT / "runtime" / "supervisor.pid",
        str(os.getpid()) + "\n",
    )
    workers: list[threading.Thread] = []
    for index in range(1, EVIDENCE_DISCOVERY_CONCURRENCY + 1):
        thread = threading.Thread(target=evidence_worker, args=(f"evidence-{index}",), name=f"evidence-{index}", daemon=True)
        thread.start()
        workers.append(thread)
    for index in range(1, MODEL_QUESTION_CONCURRENCY_MAX + 1):
        thread = threading.Thread(target=model_worker, args=(f"model-{index}",), name=f"model-{index}", daemon=True)
        thread.start()
        workers.append(thread)
    threading.Thread(target=sentinel_watch, name="sentinel", daemon=True).start()
    last_progress = 0.0
    last_heartbeat = 0.0
    while not _STOP.is_set() and not hard_stop_triggered(OUTPUT_ROOT):
        now = time.time()
        if now - last_heartbeat >= 60:
            atomic_write_json(
                OUTPUT_ROOT / "runtime" / "heartbeat.json",
                {
                    "ts": utc_now(),
                    "pid": os.getpid(),
                    "command": "formal125-fast-supervisor",
                    "alive_workers": [thread.name for thread in workers if thread.is_alive()],
                    "secrets_included": False,
                },
            )
            last_heartbeat = now
        if now - last_progress >= 300:
            refresh_manifest()
            last_progress = now
        counts = job_counts(OUTPUT_ROOT)
        if counts["evidence_pending"] == 0 and counts["evidence_running"] == 0 and counts["model_queued"] == 0 and counts["model_running"] == 0:
            break
        for thread in list(workers):
            if not thread.is_alive() and not _STOP.is_set():
                name = thread.name
                target = evidence_worker if name.startswith("evidence-") else model_worker
                replacement = threading.Thread(target=target, args=(name,), name=name, daemon=True)
                replacement.start()
                workers.append(replacement)
        time.sleep(5)
    refresh_manifest()
    assemble_candidate()
    atomic_write_json(
        OUTPUT_ROOT / "COMPLETE.json",
        {
            "completed_at": utc_now(),
            "HARD_STOP_TRIGGERED": hard_stop_triggered(OUTPUT_ROOT),
            "candidate_root": str(CANDIDATE_ROOT),
            "FINAL_SUBMISSION_READY": False,
        },
    )
    return 0 if not hard_stop_triggered(OUTPUT_ROOT) else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="supervisor", choices=["supervisor", "init", "assemble"])
    args = parser.parse_args(argv)
    if args.mode == "init":
        init_workspace()
        return 0
    if args.mode == "assemble":
        assemble_candidate()
        return 0
    try:
        return supervisor_loop()
    except Exception:
        atomic_write_text(OUTPUT_ROOT / "runtime" / "supervisor_error.txt", traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
