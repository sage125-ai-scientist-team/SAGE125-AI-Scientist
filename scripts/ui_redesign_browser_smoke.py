# -*- coding: utf-8 -*-
"""本地浏览器验收：导航、控制台、截图。不调用新的付费模型。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ui" / "screenshots"
UI = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8610"
API = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8110"

PAGES = [
    ("01_landing_1920x1080.png", "/", (1920, 1080)),
    ("02_landing_1440x900.png", "/", (1440, 900)),
    ("03_workspace_overview_1920x1080.png", "/workspace", (1920, 1080)),
    ("04_workspace_question.png", "/workspace-questions", (1920, 1080)),
    ("05_workspace_evidence.png", "/workspace-evidence", (1600, 900)),
    ("06_workspace_hypotheses.png", "/workspace-hypotheses", (1600, 900)),
    ("07_workspace_plan.png", "/workspace-plan", (1600, 900)),
    ("08_workspace_execution.png", "/workspace-execution", (1600, 900)),
    ("09_workspace_history.png", "/workspace-history", (1600, 900)),
    ("10_workspace_versions.png", "/workspace-versions", (1600, 900)),
    ("11_workspace_export.png", "/workspace-results", (1600, 900)),
    ("12_workspace_mobile.png", "/workspace", (390, 844)),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    network_4xx = 0
    network_5xx = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        def on_response(resp):
            nonlocal network_4xx, network_5xx
            if 400 <= resp.status < 500:
                network_4xx += 1
            elif resp.status >= 500:
                network_5xx += 1

        page.on("response", on_response)
        page.goto(UI, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(1800)
        # 首页滚动与锚点
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(400)
        page.evaluate("window.scrollTo(0, 0)")
        enter = page.get_by_role("button", name="进入研究工作区")
        if enter.count():
            enter.first.click()
            page.wait_for_timeout(1500)
            page.goto(UI, wait_until="networkidle", timeout=60000)

        for name, path, (w, h) in PAGES:
            page.set_viewport_size({"width": w, "height": h})
            page.goto(UI.rstrip("/") + path, wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(1200)
            page.screenshot(path=str(OUT / name), full_page=True)
        page.goto(API.rstrip("/") + "/health", wait_until="networkidle", timeout=30000)
        health = page.inner_text("body")
        browser.close()

    report = {
        "ui": UI,
        "api": API,
        "console_errors": console_errors,
        "network_4xx": network_4xx,
        "network_5xx": network_5xx,
        "health_excerpt": health[:400],
        "screenshots": [p[0] for p in PAGES],
    }
    (OUT / "browser_smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
