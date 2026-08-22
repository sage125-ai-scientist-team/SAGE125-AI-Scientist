"""Read-only HTML UI for the frozen Formal 125 demo."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.formal125.frozen_demo import PUBLIC_RUN_DENIED, public_env


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAGE125 冻结 125 题演示</title>
<style>
:root { --bg:#0b1220; --card:#121b2f; --line:#2a3a5c; --text:#e8eefc; --muted:#9db0d0; --ok:#7dffb3; --warn:#ffd37d; --bad:#ff8d8d; }
body { margin:0; font-family:Segoe UI,sans-serif; background:var(--bg); color:var(--text); }
header, footer { padding:16px 24px; border-bottom:1px solid var(--line); }
footer { border-top:1px solid var(--line); border-bottom:0; color:var(--muted); }
main { padding:20px 24px 48px; }
h1,h2 { margin:0 0 12px; }
.banner { background:#3a2a10; border:1px solid #8a6a20; color:var(--warn); padding:10px 14px; border-radius:8px; margin:12px 0; }
.cards { display:flex; gap:12px; flex-wrap:wrap; margin:16px 0; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; min-width:140px; }
nav a { color:#9fd4ff; margin-right:14px; }
table { width:100%; border-collapse:collapse; background:var(--card); }
th,td { border:1px solid var(--line); padding:6px 8px; text-align:left; }
.succeeded { color:var(--ok); } .partial { color:var(--warn); } .blocked { color:var(--bad); }
button, .btn { background:#1d4ed8; color:white; border:0; padding:8px 12px; border-radius:6px; cursor:pointer; text-decoration:none; display:inline-block; }
button:disabled { background:#334; color:#889; cursor:not-allowed; }
pre { white-space:pre-wrap; background:#0a1020; padding:12px; border-radius:8px; overflow:auto; }
.grid { display:grid; grid-template-columns: 220px 1fr; gap:16px; }
@media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>SAGE125 正式 125 题冻结演示</h1>
  <div class="banner">演示环境仅展示已冻结结果，正式运行接口已关闭。公共页面不调用百炼，不产生模型费用。</div>
  <nav>
    <a href="#home">首页</a>
    <a href="#index">125 总览</a>
    <a href="#q001">Q001</a>
    <a href="#q095">Q095</a>
    <a href="#q012">Q012</a>
    <a href="#q028">Q028 旗舰</a>
    <a href="#ablation">消融</a>
    <a href="#api">API</a>
  </nav>
</header>
<main>
  <section id="home">
    <h2>项目目标</h2>
    <p>面向科学假设生成与研究计划设计：在冻结的 Formal 125 Release Candidate 上只读展示结果、证据、审查与旗舰闭环。</p>
    <div class="cards" id="stats"></div>
    <p class="muted">人工 24 题处置：队长基于当前正式状态和既有自动质量门进行状态映射式接受；不是逐题独立领域专家审查；未新增模型修复。</p>
    <button disabled>运行新任务</button>
    <span> 演示环境仅展示已冻结结果，正式运行接口已关闭。</span>
  </section>
  <section id="index">
    <h2>125 题总览</h2>
    <p><label>筛选 <select id="filter"><option value="">全部</option><option>succeeded</option><option>partial</option><option>blocked</option></select></label></p>
    <table id="qtable"></table>
  </section>
  <section id="detail">
    <h2>题目详情</h2>
    <div class="grid">
      <div>
        <p>打开 <input id="qid" value="Q001" size="6"> <button id="openq">打开</button></p>
        <div id="dl"></div>
      </div>
      <div id="qview">选择一道题。</div>
    </div>
  </section>
  <section id="flagship">
    <h2>Q028 旗舰与消融</h2>
    <pre id="flag"></pre>
    <pre id="abl"></pre>
  </section>
  <section id="api">
    <h2>API</h2>
    <p>只读 OpenAPI：<a id="docs" href="/proxy/docs" target="_blank">/docs</a></p>
  </section>
</main>
<footer>FORMAL_125_READ_ONLY=true · ALLOW_PUBLIC_ACTUAL_RUN=false · FINAL_SUBMISSION_READY=false</footer>
<script>
const API = "";
async function j(path){ const r = await fetch(API+path); if(!r.ok) throw new Error(path+' '+r.status); return r.json(); }
function esc(s){ return String(s??'').replace(/[&<>]/g, c=>({ '&':'&amp;','<':'&lt;','>':'&gt;' }[c])); }
async function boot(){
  const latest = await j('/proxy/formal-runs/latest');
  const counts = latest.status_counts||{};
  document.getElementById('stats').innerHTML = ['succeeded','partial','blocked'].map(k=>`<div class="card"><b class="${k}">${k}</b><div>${counts[k]??0}</div></div>`).join('') + `<div class="card"><b>total</b><div>${latest.total}</div></div>`;
  const qs = (await j('/proxy/formal-runs/latest/questions')).questions;
  const draw = ()=>{
    const f = document.getElementById('filter').value;
    const rows = qs.filter(x=>!f||x.status===f).map(x=>`<tr><td><a href="#q" data-q="${x.question_id}">${x.question_id}</a></td><td class="${x.status}">${x.status}</td><td>${esc(x.paper_title||'')}</td><td>${x.evidence_count}</td><td>${x.p0_count}/${x.p1_count}</td></tr>`).join('');
    document.getElementById('qtable').innerHTML = '<tr><th>题</th><th>状态</th><th>标题</th><th>证据</th><th>P0/P1</th></tr>'+rows;
  };
  document.getElementById('filter').onchange = draw; draw();
  async function show(qid){
    document.getElementById('qid').value = qid;
    const d = await j('/proxy/formal-runs/latest/questions/'+qid);
    document.getElementById('qview').innerHTML = `<h3>${d.question_id} <span class="${d.status}">${d.status}</span></h3><p>${esc(d.paper_title||'')}</p><p>${esc(d.abstract||'')}</p><h4>证据</h4>` + (d.evidence_cards||[]).map(c=>`<p><b>${esc(c.evidence_id)}</b> ${esc(c.quote||'')}<br><small>${esc(c.locator||'')} ${esc(c.doi||c.url||'')}</small></p>`).join('');
    document.getElementById('dl').innerHTML = `<a class="btn" href="/proxy/downloads/${qid}/result.pdf">PDF</a> <a class="btn" href="/proxy/downloads/${qid}/result.md">MD</a> <a class="btn" href="/proxy/downloads/${qid}/result.json">JSON</a>`;
  }
  document.getElementById('openq').onclick = ()=>show(document.getElementById('qid').value.trim());
  document.body.addEventListener('click', ev=>{ const a=ev.target.closest('a[data-q]'); if(a){ ev.preventDefault(); show(a.dataset.q);} });
  document.querySelector('a[href="#q001"]').onclick = e=>{ e.preventDefault(); show('Q001'); };
  document.querySelector('a[href="#q095"]').onclick = e=>{ e.preventDefault(); show('Q095'); };
  document.querySelector('a[href="#q012"]').onclick = e=>{ e.preventDefault(); show('Q012'); };
  try { document.getElementById('flag').textContent = JSON.stringify(await j('/proxy/formal-runs/latest/questions/Q028/flagship'), null, 2); } catch(e){ document.getElementById('flag').textContent = String(e); }
  try { document.getElementById('abl').textContent = JSON.stringify(await j('/proxy/formal-runs/latest/ablation'), null, 2); } catch(e){ document.getElementById('abl').textContent = String(e); }
  show('Q001');
}
boot().catch(err=>{ document.getElementById('stats').textContent = err; });
</script>
</body></html>
"""


def _internal_api() -> str:
    raw = (os.environ.get("SAGE_INTERNAL_API_URL") or os.environ.get("API_BASE_URL") or "").strip()
    if not raw:
        raise FrozenUIConfigError("SAGE_INTERNAL_API_URL or API_BASE_URL is required")
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw.rstrip("/")
    return "http://" + raw.rstrip("/")


class FrozenUIConfigError(RuntimeError):
    pass


def create_demo_ui() -> FastAPI:
    application = FastAPI(title="SAGE125 Frozen Formal 125 UI", version="final-demo")

    @application.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "sage125-final-ui", **public_env()}

    @application.get("/", response_class=HTMLResponse)
    def home() -> str:
        return HTML

    @application.api_route("/proxy/{path:path}", methods=["GET", "HEAD"])
    async def proxy(path: str, request: Request) -> Response:
        base = _internal_api()
        url = urljoin(base + "/", path)
        if "127.0.0.1" in url or "localhost" in url:
            if os.getenv("ALLOW_LOCALHOST_API", "").strip() != "1":
                raise HTTPException(status_code=500, detail="localhost API is forbidden in hosted demo")
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            upstream = await client.get(url, params=request.query_params)
        headers = {}
        if "content-disposition" in upstream.headers:
            headers["content-disposition"] = upstream.headers["content-disposition"]
        media = upstream.headers.get("content-type", "application/octet-stream")
        return Response(content=upstream.content, status_code=upstream.status_code, media_type=media, headers=headers)

    @application.api_route("/{path:path}", methods=["POST", "PUT", "PATCH", "DELETE"])
    def deny_writes(path: str) -> JSONResponse:
        return JSONResponse(status_code=403, content={"ok": False, "message": PUBLIC_RUN_DENIED})

    return application
