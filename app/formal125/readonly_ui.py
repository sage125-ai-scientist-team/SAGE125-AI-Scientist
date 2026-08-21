"""Local read-only Formal 12 UI. Bind 8550; does not stop other local services."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.formal125.readonly_display import latest_domains, latest_formal_run, latest_questions

HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Formal 12 只读展示</title>
<style>
body { font-family: sans-serif; background:#0b1220; color:#e8eefc; margin:24px; }
table { border-collapse: collapse; width:100%; }
td,th { border:1px solid #334; padding:6px 8px; text-align:left; }
.ok { color:#7dffb3; } .warn { color:#ffd37d; }
</style></head><body>
<h1>SAGE125 Formal 12 只读展示</h1>
<pre id="meta"></pre>
<table id="q"></table>
<script>
const meta = %META%;
const questions = %QUESTIONS%;
document.getElementById('meta').textContent = JSON.stringify(meta, null, 2);
const rows = ['<tr><th>题</th><th>领域</th><th>模式</th><th>状态</th><th>证据</th><th>全文</th><th>调用</th><th>P0/P1</th><th>PDF</th></tr>'];
const domains = %DOMAINS%;
const domainMap = Object.fromEntries(domains.map(item => [item.question_id, item.t09_domain_id]));
for (const item of questions) {
  rows.push(`<tr><td>${item.question_id}</td><td>${domainMap[item.question_id]||''}</td><td>${item.execution_mode}</td><td>${item.status}</td><td>${item.evidence_count}</td><td>${item.fulltext_sources}</td><td>${item.provider_calls}</td><td>${item.p0}/${item.p1}</td><td>${item.pdf_present}</td></tr>`);
}
document.getElementById('q').innerHTML = rows.join('');
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        payload = HTML.replace("%META%", json.dumps(latest_formal_run(), ensure_ascii=False))
        payload = payload.replace("%QUESTIONS%", json.dumps(latest_questions()["questions"], ensure_ascii=False))
        payload = payload.replace("%DOMAINS%", json.dumps(latest_domains()["domains"], ensure_ascii=False))
        body = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def serve(host: str = "127.0.0.1", port: int = 8550) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()
