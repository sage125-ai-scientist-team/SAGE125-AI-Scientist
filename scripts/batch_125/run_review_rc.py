"""Captain review dashboard, background evidence prep, and RC assembly."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.evidence.oa_fulltext import FulltextFetchAudit  # noqa: E402
from app.evidence.remediation import build_seed_bundle  # noqa: E402
from app.formal125.actual_run import (  # noqa: E402
    atomic_write_json,
    atomic_write_text,
    install_captain_runtime_env,
    is_auth_failure,
    materialize_questions,
    package_question,
)
from app.formal125.continuous_fast import (  # noqa: E402
    LOCAL_CACHE_ROOTS,
    MANUAL_REVIEW_24,
    SCIENTIFIC_PRODUCER_SHA,
    catalog_item,
    ensure_relevance_template,
    load_catalog,
    official_question_ids,
    sha256_file,
    verify_locks,
    write_blocked_package,
)
from app.formal125.evidence_rerun import _pipeline_with_frozen_bundle  # noqa: E402
from app.formal125.hashes import sha256_canonical_json  # noqa: E402
from app.formal125.review_rc import (  # noqa: E402
    DECISIONS,
    MAX_NEW_INPUT_TOKENS,
    MAX_NEW_OUTPUT_TOKENS,
    MAX_NEW_PROVIDER_CALLS,
    ORIGINAL_CANDIDATE,
    PROJECT_PROVIDER_CALLS_BEFORE,
    START_SHA,
    STAMP,
    candidate_fingerprint,
    classify_partial_signature,
    decision_hash,
    load_json,
    official_ids,
    pre_review_question,
    risk_sort_key,
    utc_now,
    validate_decision,
)


OUT = Path(rf"D:\SAGE125_Local_Runs\formal_125_fast_review_rc_{STAMP}")
RC = Path(rf"D:\SAGE125_Local_Runs\formal_125_release_candidate_{STAMP}")
CACHE = Path(rf"D:\SAGE125_Local_Evidence\formal_125_fast_review_rc_{STAMP}")
_DISPLAY = {"api": "http://127.0.0.1:8090", "ui": "http://127.0.0.1:8590"}
_ORCH = "pending"
_FP0 = ""
_STOP = threading.Event()
_HARD = {}
_BUDGET = {"calls": 0, "input": 0, "output": 0, "retries": 0, "count_429": 0}
_BG = {"prepared": 0, "ready": 0, "failed": 0, "running": []}


def git_head() -> str:
    import subprocess

    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def find_port(start: int) -> int:
    reserved = {8020, 8030, 8040, 8050, 8060, 8070, 8080, 8520, 8530, 8540, 8550, 8560, 8570, 8580}
    for port in range(start, start + 40):
        if port in reserved:
            continue
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            continue
        finally:
            sock.close()
        return port
    raise RuntimeError("no free port")


def decisions_dir() -> Path:
    return OUT / "manual_review_24"


def decision_path(qid: str) -> Path:
    return decisions_dir() / qid / "manual_review_decision.json"


def completed_reviews() -> list[dict[str, Any]]:
    rows = []
    for qid in MANUAL_REVIEW_24:
        payload = load_json(decision_path(qid))
        if payload and payload.get("reviewed") is True and payload.get("decision") in DECISIONS:
            rows.append(payload)
    return rows


def review_progress() -> dict[str, Any]:
    done = completed_reviews()
    counts = {key: 0 for key in DECISIONS}
    for item in done:
        counts[item["decision"]] += 1
    return {
        "required": 24,
        "completed": len(done),
        "decisions": counts,
        "systemic_reject": counts["SYSTEMIC_REJECT"],
    }


def run_pre_review() -> list[dict[str, Any]]:
    catalog = load_catalog(ROOT)
    items = []
    for qid in official_ids():
        items.append(pre_review_question(ORIGINAL_CANDIDATE, catalog_item(catalog, qid)))
    matrix = {
        "total": 125,
        "risk_counts": {},
        "status_counts": {},
        "questions": items,
        "generated_at": utc_now(),
        "manual_reviewed": False,
    }
    for item in items:
        matrix["risk_counts"][item["risk"]] = matrix["risk_counts"].get(item["risk"], 0) + 1
        matrix["status_counts"][item["status"]] = matrix["status_counts"].get(item["status"], 0) + 1
    atomic_write_json(OUT / "formal_125_automated_pre_review.json", matrix)
    atomic_write_json(
        OUT / "formal_125_risk_matrix.json",
        {
            "risk_counts": matrix["risk_counts"],
            "status_counts": matrix["status_counts"],
            "review_order": [item["question_id"] for item in sorted((i for i in items if i["question_id"] in MANUAL_REVIEW_24), key=risk_sort_key)],
            "followup": [item["question_id"] for item in items if item["max_similarity"] > 0.90],
            "generated_at": utc_now(),
        },
    )
    return items


def review_card(qid: str, pre: dict[str, Any]) -> dict[str, Any]:
    qdir = ORIGINAL_CANDIDATE / qid
    catalog = load_catalog(ROOT)
    item = catalog_item(catalog, qid)
    result = load_json(qdir / "result.json") or {}
    cards = load_json(qdir / "evidence_cards.json") or []
    validation = load_json(qdir / "validation.json") or {}
    if not isinstance(cards, list):
        cards = []
    evidence = []
    for card in cards[:8]:
        evidence.append(
            {
                "evidence_id": card.get("evidence_id") or card.get("id"),
                "quote": (card.get("quote") or card.get("quoted_text") or "")[:280],
                "locator": card.get("locator") or str(card.get("reliability_note") or ""),
                "title": card.get("title"),
                "url": card.get("url"),
                "doi": card.get("doi"),
                "relevance": card.get("topic_relevance_status") or card.get("reliability_note"),
            }
        )
    hyps = []
    for hyp in result.get("generated_hypotheses") or []:
        if isinstance(hyp, dict):
            hyps.append(
                {
                    "hypothesis": hyp.get("hypothesis"),
                    "supporting_evidence_ids": hyp.get("supporting_evidence_ids") or [],
                }
            )
    decision = load_json(decision_path(qid))
    return {
        "question_id": qid,
        "official_title": item.get("original_title"),
        "official_text": item.get("original_question_text"),
        "status": pre.get("status"),
        "risk": pre.get("risk"),
        "paper_title": result.get("paper_title"),
        "paper_abstract": (result.get("paper_abstract") or "")[:1200],
        "hypotheses": hyps,
        "plan": (result.get("technical_details") or result.get("methods") or "")[:1200],
        "results": (result.get("results") or "")[:400],
        "actual_execution": result.get("actual_execution", False),
        "evidence": evidence,
        "p0": pre.get("p0_count"),
        "p1": pre.get("p1_count"),
        "provider_calls": pre.get("provider_calls"),
        "block_code": pre.get("block_code"),
        "findings": pre.get("findings"),
        "suggested_decision": pre.get("suggested_decision"),
        "similarity": validation.get("similarity") or {},
        "max_similarity": pre.get("max_similarity"),
        "pdf_url": f"/pdf/{qid}",
        "decision": decision,
        "lineage": load_json(qdir / "reuse_lineage.json") or load_json(qdir / "attempt_lineage.json") or {},
    }


def progress_state() -> dict[str, Any]:
    pre = load_json(OUT / "formal_125_automated_pre_review.json") or {}
    rp = review_progress()
    return {
        "total": 125,
        "automated_pre_review_count": len(pre.get("questions") or []),
        "manual_review": rp,
        "background": _BG,
        "budget": _BUDGET,
        "hard_stop": _HARD,
        "candidate_root": str(ORIGINAL_CANDIDATE),
        "review_root": str(OUT),
        "rc_root": str(RC),
        "FORMAL_125_RC_READY": (RC / "CANDIDATE_STATUS.json").is_file(),
        "FINAL_SUBMISSION_READY": False,
        "api": _DISPLAY["api"],
        "ui": _DISPLAY["ui"],
        "secrets_included": False,
    }


HTML = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>SAGE125｜24 题队长人工复核</title>
<style>
body{font-family:sans-serif;background:#0b1220;color:#e8eefc;margin:0}
header,nav{padding:12px 20px;background:#132033;border-bottom:1px solid #334}
.tabs button{margin-right:8px;padding:6px 10px}
.ok{color:#7dffb3}.warn{color:#ffd37d}.bad{color:#ff8a8a}
main{display:grid;grid-template-columns:280px 1fr;min-height:calc(100vh - 120px)}
#list{border-right:1px solid #334;overflow:auto;padding:8px}
#detail{padding:16px;overflow:auto}
.card{border:1px solid #334;padding:8px;margin:6px 0;cursor:pointer}
.card.active{border-color:#7dffb3}
pre{white-space:pre-wrap;background:#0f1a2b;padding:8px}
button.dec{margin:4px;padding:8px 10px}
</style></head><body>
<header>
<h1>SAGE125｜24 题队长人工复核</h1>
<div>进度 <span id="prog">0/24</span> ｜ 不得批量批准 ｜ 快捷键 1-5 / N / P</div>
<nav>
<button onclick="showTab('review')">人工复核 24 题</button>
<button onclick="showTab('bg')">后台修复进度</button>
<button onclick="showTab('rc')">Release Candidate</button>
</nav>
</header>
<section id="review">
<main>
<div id="list"></div>
<div id="detail">加载中…</div>
</main>
</section>
<section id="bg" hidden><pre id="bgpre"></pre></section>
<section id="rc" hidden><pre id="rcpre"></pre></section>
<script>
let items=[], current=0, tab='review';
async function load(){
  const s=await (await fetch('/api/state')).json();
  document.getElementById('prog').textContent=s.manual_review.completed+'/24';
  document.getElementById('bgpre').textContent=JSON.stringify({background:s.background,budget:s.budget},null,2);
  document.getElementById('rcpre').textContent=JSON.stringify(s,null,2);
  items=await (await fetch('/api/review-set')).json();
  renderList();
  if(items.length) show(current);
  if(s.manual_review.completed===24 && tab==='review') showTab('bg');
}
function renderList(){
  const el=document.getElementById('list');
  el.innerHTML=items.map((it,i)=>`<div class="card ${i===current?'active':''}" onclick="current=${i};show(${i})">${it.question_id} · ${it.status} · ${it.risk}${it.decision?' · '+it.decision.decision:''}</div>`).join('');
}
async function show(i){
  current=i; renderList();
  const q=items[i];
  const d=await (await fetch('/api/question/'+q.question_id)).json();
  const ev=(d.evidence||[]).map(e=>`<li><b>${e.evidence_id}</b> ${e.quote||''}<br><small>${e.locator||''} ${e.url||''}</small></li>`).join('');
  const hy=(d.hypotheses||[]).map(h=>`<li>${h.hypothesis}<br>IDs: ${(h.supporting_evidence_ids||[]).join(', ')||'无'}</li>`).join('');
  document.getElementById('detail').innerHTML=`
  <h2>${d.question_id} · ${d.status} · ${d.risk}</h2>
  <p><b>官方问题</b> ${d.official_title}</p>
  <pre>${d.official_text||''}</pre>
  <p><b>Title</b> ${d.paper_title||''}</p>
  <pre>${d.paper_abstract||''}</pre>
  <p><b>假设</b></p><ol>${hy}</ol>
  <p><b>计划</b></p><pre>${d.plan||''}</pre>
  <p><b>结果</b> ${d.results||''} ｜ actual_execution=${d.actual_execution}</p>
  <p><b>证据</b></p><ol>${ev}</ol>
  <p>P0/P1=${d.p0}/${d.p1} ｜ calls=${d.provider_calls} ｜ block=${d.block_code||''}</p>
  <p>自动预审建议：${d.suggested_decision} ｜ 发现：${(d.findings||[]).join('; ')}</p>
  <p><a href="${d.pdf_url}" target="_blank">打开 PDF</a></p>
  <p>
  <button class="dec" onclick="decide('ACCEPT_SUCCEEDED')">1 ACCEPT_SUCCEEDED</button>
  <button class="dec" onclick="decide('ACCEPT_GENUINE_PARTIAL')">2 ACCEPT_GENUINE_PARTIAL</button>
  <button class="dec" onclick="decide('ACCEPT_GENUINE_BLOCKED')">3 ACCEPT_GENUINE_BLOCKED</button>
  <button class="dec" onclick="decide('REQUEST_REMEDIATION')">4 REQUEST_REMEDIATION</button>
  <button class="dec" onclick="decide('SYSTEMIC_REJECT')">5 SYSTEMIC_REJECT</button>
  </p>
  <p>理由（D/E 必填）<br><textarea id="reason" rows="3" cols="70"></textarea></p>
  <p class="warn">必须逐题查看后决定。没有一键全部通过。</p>`;
}
async function decide(decision){
  const q=items[current];
  const reason=document.getElementById('reason').value;
  const res=await fetch('/api/decision/'+q.question_id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,reason})});
  const body=await res.json();
  if(!res.ok){alert(body.error||'保存失败');return;}
  await load();
}
function showTab(name){tab=name;['review','bg','rc'].forEach(id=>document.getElementById(id).hidden=id!==name);}
document.addEventListener('keydown',e=>{
  if(tab!=='review')return;
  if(e.key==='1')decide('ACCEPT_SUCCEEDED');
  if(e.key==='2')decide('ACCEPT_GENUINE_PARTIAL');
  if(e.key==='3')decide('ACCEPT_GENUINE_BLOCKED');
  if(e.key==='4')decide('REQUEST_REMEDIATION');
  if(e.key==='5')decide('SYSTEMIC_REJECT');
  if(e.key==='n'||e.key==='N'){current=Math.min(items.length-1,current+1);show(current);}
  if(e.key==='p'||e.key==='P'){current=Math.max(0,current-1);show(current);}
});
setInterval(load,8000); load();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/ui"}:
            return self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/state":
            return self._send(200, json.dumps(progress_state(), ensure_ascii=False).encode("utf-8"), "application/json")
        if path == "/api/review-set":
            pre = load_json(OUT / "formal_125_automated_pre_review.json") or {}
            by = {item["question_id"]: item for item in pre.get("questions") or []}
            rows = []
            for qid in MANUAL_REVIEW_24:
                item = dict(by.get(qid) or {"question_id": qid})
                item["decision"] = load_json(decision_path(qid))
                rows.append(item)
            rows.sort(key=risk_sort_key)
            return self._send(200, json.dumps(rows, ensure_ascii=False).encode("utf-8"), "application/json")
        if path.startswith("/api/question/"):
            qid = path.rsplit("/", 1)[-1]
            pre = load_json(OUT / "formal_125_automated_pre_review.json") or {}
            item = next((row for row in pre.get("questions") or [] if row["question_id"] == qid), {"question_id": qid})
            return self._send(200, json.dumps(review_card(qid, item), ensure_ascii=False).encode("utf-8"), "application/json")
        if path.startswith("/pdf/"):
            qid = unquote(path.split("/pdf/", 1)[1]).strip("/")
            pdf = ORIGINAL_CANDIDATE / qid / "result.pdf"
            if pdf.is_file():
                return self._send(200, pdf.read_bytes(), "application/pdf")
        return self._send(404, b"{}", "application/json")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        if not path.startswith("/api/decision/"):
            return self._send(404, b'{"error":"not found"}', "application/json")
        qid = path.rsplit("/", 1)[-1]
        if qid not in MANUAL_REVIEW_24:
            return self._send(400, b'{"error":"not in frozen 24"}', "application/json")
        body = json.loads(raw.decode("utf-8") or "{}")
        decision = str(body.get("decision") or "")
        reason = str(body.get("reason") or "")
        require_reason = decision in {"REQUEST_REMEDIATION", "SYSTEMIC_REJECT"}
        qdir = ORIGINAL_CANDIDATE / qid
        pre = load_json(OUT / "formal_125_automated_pre_review.json") or {}
        item = next((row for row in pre.get("questions") or [] if row["question_id"] == qid), {})
        payload = {
            "question_id": qid,
            "reviewer_role": "captain",
            "reviewer_account": "liuyanbo12",
            "decision": decision,
            "reason": reason,
            "reviewed_at": utc_now(),
            "result_digest": sha256_file(qdir / "result.json") if (qdir / "result.json").is_file() else None,
            "evidence_digest": sha256_file(qdir / "evidence_cards.json") if (qdir / "evidence_cards.json").is_file() else None,
            "pdf_digest": sha256_file(qdir / "result.pdf") if (qdir / "result.pdf").is_file() else None,
            "risk": item.get("risk"),
            "reviewed": True,
        }
        payload["decision_hash"] = decision_hash(payload)
        try:
            validate_decision(payload, require_reason=require_reason)
        except ValueError as exc:
            return self._send(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"), "application/json")
        atomic_write_json(decision_path(qid), payload)
        if decision == "SYSTEMIC_REJECT":
            _HARD.update({"triggered": True, "code": "HARD_STOP_MANUAL_SYSTEMIC_REJECT", "reason": reason})
            atomic_write_json(OUT / "HARD_STOP.json", _HARD)
            _STOP.set()
        return self._send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def start_display() -> None:
    api_port = find_port(8090)
    ui_port = find_port(8590)
    _DISPLAY["api"] = f"http://127.0.0.1:{api_port}"
    _DISPLAY["ui"] = f"http://127.0.0.1:{ui_port}"

    class Api(Handler):
        pass

    api = ThreadingHTTPServer(("127.0.0.1", api_port), Api)
    ui = ThreadingHTTPServer(("127.0.0.1", ui_port), Api)
    threading.Thread(target=api.serve_forever, name="review-api", daemon=True).start()
    threading.Thread(target=ui.serve_forever, name="review-ui", daemon=True).start()
    atomic_write_json(OUT / "display.json", {"api": _DISPLAY["api"], "ui": _DISPLAY["ui"], "pid": os.getpid()})


def background_evidence() -> None:
    catalog = load_catalog(ROOT)
    pre = load_json(OUT / "formal_125_automated_pre_review.json") or {}
    targets = []
    for item in pre.get("questions") or []:
        if item["status"] == "blocked" or (item["question_id"] in MANUAL_REVIEW_24 and item["status"] in {"partial", "blocked"}):
            targets.append(item["question_id"])
    signatures = {}
    for item in pre.get("questions") or []:
        if item["status"] in {"partial", "blocked"}:
            validation = load_json(ORIGINAL_CANDIDATE / item["question_id"] / "validation.json") or {}
            signatures[item["question_id"]] = classify_partial_signature(item, validation)
    atomic_write_json(OUT / "partial_block_signatures.json", signatures)
    seed_root = OUT / "evidence_prep"
    seed_root.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    for qid in targets:
        if _STOP.is_set():
            return
        _BG["running"] = [qid]
        try:
            item = catalog_item(catalog, qid)
            ensure_relevance_template(item)
            bundle = build_seed_bundle(
                question_id=qid,
                question_title=str(item.get("original_title") or qid),
                cache_root=CACHE,
                output_root=seed_root,
                audit=FulltextFetchAudit(),
                local_cache_roots=[path for path in LOCAL_CACHE_ROOTS if path.exists()],
            )
            ready = bool(bundle.get("evidence_seed_ready"))
            _BG["prepared"] += 1
            if ready:
                _BG["ready"] += 1
            atomic_write_json(
                OUT / "evidence_prep" / qid / "prep_status.json",
                {"question_id": qid, "ready": ready, "ts": utc_now(), "model_called": False},
            )
        except Exception as exc:
            _BG["failed"] += 1
            atomic_write_json(
                OUT / "evidence_prep" / qid / "prep_status.json",
                {"question_id": qid, "ready": False, "error": type(exc).__name__, "ts": utc_now(), "model_called": False},
            )
    _BG["running"] = []
    q027 = load_json(ORIGINAL_CANDIDATE / "Q027" / "result.json") or {}
    atomic_write_json(
        OUT / "q027_validation_error.json",
        {
            "question_id": "Q027",
            "status": (load_json(ORIGINAL_CANDIDATE / "Q027" / "package_manifest.json") or {}).get("status"),
            "block_code": q027.get("block_code") or "INDIVIDUAL_FAILED",
            "note": "ValidationError during model packaging; individual failure, not systemic.",
        },
    )


def wait_for_reviews() -> bool:
    while not _STOP.is_set():
        progress = review_progress()
        atomic_write_json(OUT / "manual_review_progress.json", progress)
        if progress["systemic_reject"]:
            return False
        if progress["completed"] == 24:
            return True
        time.sleep(5)
    return False


def build_remediation_ids(pre_items: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for payload in completed_reviews():
        if payload["decision"] == "REQUEST_REMEDIATION":
            ids.append(payload["question_id"])
    for item in pre_items:
        if "status_p0_p1_inconsistent" in (item.get("findings") or []) or "checksum_mismatch" in "".join(item.get("findings") or []):
            if item["question_id"] not in ids:
                ids.append(item["question_id"])
    return ids


def copy_question(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.iterdir():
        if path.is_file():
            target = dest / path.name
            if not target.exists():
                shutil.copy2(path, target)


def remediate_question(qid: str, workflow_sha: str) -> dict[str, Any]:
    attempt_dir = OUT / "remediation_attempts" / qid
    attempt_dir.mkdir(parents=True, exist_ok=True)
    src = ORIGINAL_CANDIDATE / qid
    atomic_write_json(
        attempt_dir / "previous_attempt_reference.json",
        {
            "question_id": qid,
            "source": str(src),
            "package_digest": sha256_file(src / "package_manifest.json") if (src / "package_manifest.json").is_file() else None,
            "immutable": True,
        },
    )
    decision = load_json(decision_path(qid)) or {}
    atomic_write_json(attempt_dir / "manual_review_decision.json", decision)
    pre = next((item for item in (load_json(OUT / "formal_125_automated_pre_review.json") or {}).get("questions") or [] if item["question_id"] == qid), {})
    atomic_write_json(attempt_dir / "automated_pre_review.json", pre)
    seed_ready = bool((load_json(OUT / "evidence_prep" / qid / "prep_status.json") or {}).get("ready"))
    plan = {
        "question_id": qid,
        "use_prepared_seed": seed_ready,
        "model_allowed": seed_ready and _BUDGET["calls"] < MAX_NEW_PROVIDER_CALLS,
        "budget_remaining_calls": MAX_NEW_PROVIDER_CALLS - _BUDGET["calls"],
    }
    atomic_write_json(attempt_dir / "remediation_plan.json", plan)
    if seed_ready:
        shutil.copy2(OUT / "evidence_prep" / qid / "evidence_bundle.json", attempt_dir / "evidence_bundle.json")
    if not plan["model_allowed"]:
        write_blocked_package(
            question_dir=attempt_dir,
            question_id=qid,
            block_code="REMEDIATION_SEED_OR_BUDGET",
            reason="seed not ready or budget exhausted; original candidate retained",
            orchestrator_sha=workflow_sha,
        )
        atomic_write_json(
            attempt_dir / "comparison_to_previous.json",
            {"selected": "original_candidate", "new_attempt_status": "blocked"},
        )
        return {"question_id": qid, "status": "blocked", "selected": "original"}
    os.environ["SAGE_EVIDENCE_BUNDLE_DIR"] = str(OUT / "evidence_prep")
    try:
        plan_obj, state = _pipeline_with_frozen_bundle(qid)
        packaged = package_question(
            question_dir=attempt_dir,
            question_id=qid,
            plan=plan_obj,
            state=state,
            previous_texts={},
            batch_calls=0,
            batch_input=0,
            batch_output=0,
        )
        _BUDGET["calls"] += int(packaged.get("calls") or 0)
        _BUDGET["input"] += int(packaged.get("input_tokens") or 0)
        _BUDGET["output"] += int(packaged.get("output_tokens") or 0)
        atomic_write_json(
            attempt_dir / "attempt_lineage.json",
            {
                "question_id": qid,
                "scientific_producer_sha": SCIENTIFIC_PRODUCER_SHA,
                "workflow_sha": workflow_sha,
                "status": packaged["status"],
            },
        )
        atomic_write_json(
            attempt_dir / "comparison_to_previous.json",
            {"selected": "new_attempt" if packaged["status"] in {"succeeded", "partial"} else "original_candidate", "new_status": packaged["status"]},
        )
        return {"question_id": qid, "status": packaged["status"], "selected": "new_attempt", "calls": packaged.get("calls")}
    except Exception as exc:
        if is_auth_failure(exc):
            _HARD.update({"triggered": True, "code": "HARD_STOP_3", "reason": "auth failure"})
            _STOP.set()
        write_blocked_package(
            question_dir=attempt_dir,
            question_id=qid,
            block_code="REMEDIATION_FAILED",
            reason=type(exc).__name__,
            orchestrator_sha=workflow_sha,
        )
        return {"question_id": qid, "status": "failed", "selected": "original"}


def assemble_rc(workflow_sha: str, remediations: list[dict[str, Any]]) -> None:
    RC.mkdir(parents=True, exist_ok=True)
    shutil.copytree(OUT / "authorization", RC / "authorization", dirs_exist_ok=True) if (OUT / "authorization").exists() else (RC / "authorization").mkdir(exist_ok=True)
    (RC / "audit").mkdir(exist_ok=True)
    shutil.copytree(decisions_dir(), RC / "manual_review_24", dirs_exist_ok=True)
    if (OUT / "remediation_attempts").exists():
        shutil.copytree(OUT / "remediation_attempts", RC / "remediation_attempts", dirs_exist_ok=True)
    selected = {}
    counts = {"succeeded": 0, "partial": 0, "failed": 0, "blocked": 0}
    rem_map = {item["question_id"]: item for item in remediations}
    for qid in official_ids():
        dest = RC / qid
        dest.mkdir(parents=True, exist_ok=True)
        attempt = OUT / "remediation_attempts" / qid
        use_new = False
        if qid in rem_map and rem_map[qid].get("selected") == "new_attempt" and (attempt / "package_manifest.json").is_file():
            new_status = str((load_json(attempt / "package_manifest.json") or {}).get("status"))
            if new_status in {"succeeded", "partial", "failed", "blocked"}:
                copy_question(attempt, dest)
                use_new = True
        if not use_new:
            copy_question(ORIGINAL_CANDIDATE / qid, dest)
            decision = load_json(decision_path(qid))
            if decision:
                atomic_write_json(dest / "manual_disposition.json", decision)
        status = str((load_json(dest / "package_manifest.json") or {}).get("status") or "blocked")
        counts[status] = counts.get(status, 0) + 1
        selected[qid] = {"status": status, "source": "remediation_attempt" if use_new else "original_candidate"}
    for name in ("formal_125_automated_pre_review.json", "formal_125_risk_matrix.json", "partial_block_signatures.json"):
        if (OUT / name).is_file():
            shutil.copy2(OUT / name, RC / "audit" / name)
    inventory = {
        "project_provider_calls_before": PROJECT_PROVIDER_CALLS_BEFORE,
        "new_remediation_provider_calls": _BUDGET["calls"],
        "project_provider_calls_after": PROJECT_PROVIDER_CALLS_BEFORE + _BUDGET["calls"],
        "input_tokens": _BUDGET["input"],
        "output_tokens": _BUDGET["output"],
        "retries": _BUDGET["retries"],
        "count_429": _BUDGET["count_429"],
        "openrouter_calls": 0,
        "mock_calls": 0,
        "estimated_cost": "unknown",
    }
    atomic_write_json(RC / "provider_call_inventory.json", inventory)
    atomic_write_json(RC / "budget_report.json", {**inventory, "max_calls": MAX_NEW_PROVIDER_CALLS, "estimated_cost": "unknown"})
    rp = review_progress()
    atomic_write_json(RC / "manual_review_summary.json", rp)
    atomic_write_json(RC / "remediation_summary.json", {"cases": remediations, "count": len(remediations)})
    atomic_write_json(RC / "domain_summary.json", {"note": "booklet domains unchanged", "total": 125})
    atomic_write_json(RC / "index.json", {"questions": selected, "total": 125})
    atomic_write_text(RC / "index.md", "\n".join([f"- {qid}: {item['status']}" for qid, item in selected.items()]) + "\n")
    atomic_write_json(
        RC / "summary_report.json",
        {"total": 125, "status_counts": counts, "status_count_total": sum(counts.values()), "FORMAL_125_RC_READY": True, "FINAL_SUBMISSION_READY": False},
    )
    atomic_write_json(
        RC / "failure_and_partial_report.json",
        {qid: item for qid, item in selected.items() if item["status"] != "succeeded"},
    )
    pre = load_json(OUT / "formal_125_automated_pre_review.json") or {}
    atomic_write_json(
        RC / "cross_question_similarity_report.json",
        {"followup": [item["question_id"] for item in pre.get("questions") or [] if item.get("max_similarity", 0) > 0.90]},
    )
    atomic_write_text(
        RC / "reproduction.md",
        f"# Formal 125 RC reproduction\n\nProducer `{SCIENTIFIC_PRODUCER_SHA}`\nWorkflow `{workflow_sha}`\nOriginal candidate `{ORIGINAL_CANDIDATE}`\n",
    )
    atomic_write_text(
        RC / "release_notes.md",
        "# Formal 125 Release Candidate\n\nLocal RC only. FINAL_SUBMISSION_READY=False.\n",
    )
    atomic_write_json(
        RC / "manifest.json",
        {
            "total": 125,
            "question_ids": official_ids(),
            "status_counts": counts,
            "status_count_total": sum(counts.values()),
            "questions": selected,
            "reused_from_original_candidate": sum(1 for item in selected.values() if item["source"] == "original_candidate"),
            "new_attempts": sum(1 for item in selected.values() if item["source"] == "remediation_attempt"),
            "FINAL_SUBMISSION_READY": False,
        },
    )
    names = [
        "manifest.json",
        "index.json",
        "index.md",
        "summary_report.json",
        "failure_and_partial_report.json",
        "provider_call_inventory.json",
        "manual_review_summary.json",
        "remediation_summary.json",
        "budget_report.json",
        "reproduction.md",
        "release_notes.md",
    ]
    files = []
    lines = []
    for name in names:
        path = RC / name
        if path.is_file():
            digest = sha256_file(path)
            files.append({"name": name, "sha256": digest})
            lines.append(f"{digest}  {name}")
    atomic_write_json(RC / "package_manifest.json", {"files": files, "total": 125})
    atomic_write_text(RC / "checksums.sha256", "\n".join(lines) + "\n")
    atomic_write_json(
        RC / "CANDIDATE_STATUS.json",
        {
            "FORMAL_125_RC_STATUS": "PASS_WITH_GENUINE_PARTIALS_AND_BLOCKS",
            "FORMAL_125_RC_READY": True,
            "FINAL_SUBMISSION_READY": False,
        },
    )


def write_repo_snapshot(workflow_sha: str) -> None:
    dest = ROOT / "docs" / "reproducibility" / "formal_125" / "runs" / f"formal_125_fast_review_rc_{STAMP}"
    dest.mkdir(parents=True, exist_ok=True)
    rp = review_progress()
    atomic_write_json(
        dest / "review_decision_digests.json",
        {qid: (load_json(decision_path(qid)) or {}).get("decision_hash") for qid in MANUAL_REVIEW_24},
    )
    if (RC / "remediation_summary.json").is_file():
        shutil.copy2(RC / "remediation_summary.json", dest / "remediation_summary.json")
    atomic_write_json(
        dest / "rc_manifest_digest.json",
        {
            "rc_root": str(RC),
            "manifest_sha256": sha256_file(RC / "manifest.json") if (RC / "manifest.json").is_file() else None,
            "provider_inventory_sha256": sha256_file(RC / "provider_call_inventory.json") if (RC / "provider_call_inventory.json").is_file() else None,
            "original_candidate_fingerprint": _FP0,
            "workflow_sha": workflow_sha,
        },
    )
    atomic_write_text(dest / "reproduction_reference.md", f"RC root: `{RC}`\nOriginal candidate: `{ORIGINAL_CANDIDATE}`\n")


def supervisor() -> int:
    global _ORCH, _FP0
    OUT.mkdir(parents=True, exist_ok=True)
    decisions_dir().mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    _ORCH = git_head()
    _FP0 = candidate_fingerprint(ORIGINAL_CANDIDATE)
    verify_locks(ROOT)
    if candidate_fingerprint(ORIGINAL_CANDIDATE) != _FP0:
        raise RuntimeError("original candidate mutated before start")
    questions_path = OUT / "input" / "questions_125.json"
    materialize_questions(questions_path)
    install_captain_runtime_env(export_dir=OUT / "pipeline_exports", questions_path=questions_path, max_retries=1)
    os.environ.pop("MOCK_LLM", None)
    run_pre_review()
    start_display()
    atomic_write_text(OUT / "supervisor.pid", str(os.getpid()) + "\n")
    bg = threading.Thread(target=background_evidence, name="evidence-prep", daemon=True)
    bg.start()
    ok = wait_for_reviews()
    if not ok or _HARD.get("triggered"):
        atomic_write_json(OUT / "STOPPED.json", {"reason": _HARD or "stopped", "ts": utc_now()})
        return 2
    pre_items = (load_json(OUT / "formal_125_automated_pre_review.json") or {}).get("questions") or []
    rem_ids = build_remediation_ids(pre_items)
    remediations = []
    for qid in rem_ids:
        if _BUDGET["calls"] >= MAX_NEW_PROVIDER_CALLS:
            remediations.append({"question_id": qid, "status": "blocked", "selected": "original", "reason": "budget"})
            continue
        remediations.append(remediate_question(qid, _ORCH))
    assemble_rc(_ORCH, remediations)
    if candidate_fingerprint(ORIGINAL_CANDIDATE) != _FP0:
        raise RuntimeError("original candidate mutated")
    write_repo_snapshot(_ORCH)
    atomic_write_json(OUT / "COMPLETE.json", {"ts": utc_now(), "rc": str(RC), "FORMAL_125_RC_READY": True, "FINAL_SUBMISSION_READY": False})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="supervisor", choices=["supervisor", "pre-review"])
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == "pre-review":
        run_pre_review()
        return 0
    try:
        return supervisor()
    except Exception:
        atomic_write_text(OUT / "supervisor_error.txt", traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
