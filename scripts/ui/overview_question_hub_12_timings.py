# -*- coding: utf-8 -*-
"""热加载与滚动/选题延迟的诚实测量（不含固定 sleep）。"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

UI = "http://127.0.0.1:8610"
OUT = Path(__file__).resolve().parents[2] / "docs" / "ui" / "overview_question_hub_12"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{UI}/workspace-questions", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_selector(".question-context-readonly", timeout=30000)

        warm = []
        for _ in range(5):
            t0 = time.perf_counter()
            page.goto(f"{UI}/workspace-questions", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_selector(".question-context-readonly", timeout=30000)
            warm.append((time.perf_counter() - t0) * 1000)

        page.wait_for_timeout(800)
        scroll_ms = None
        btn = page.get_by_role("button", name="选择科学问题")
        if btn.count():
            t0 = time.perf_counter()
            btn.first.click()
            page.wait_for_function(
                "() => { const el = document.getElementById('question-picker'); if (!el) return false; const r = el.getBoundingClientRect(); return r.top < window.innerHeight && r.bottom > 0; }",
                timeout=15000,
            )
            scroll_ms = (time.perf_counter() - t0) * 1000

        ctx_ms = None
        boxes = page.locator('[data-testid="stSelectbox"]')
        target = None
        for i in range(boxes.count()):
            if "选择一个科学问题" in boxes.nth(i).inner_text() or "选择科学问题" in boxes.nth(i).inner_text():
                target = boxes.nth(i)
        if target is not None:
            target.click()
            page.wait_for_timeout(250)
            opt = page.get_by_role("option").filter(has_text="Q039")
            t0 = time.perf_counter()
            if opt.count():
                opt.first.click()
                try:
                    page.wait_for_function(
                        "() => { const el = document.querySelector('.context-value'); return !!(el && el.textContent && el.textContent.indexOf('Q039') >= 0); }",
                        timeout=15000,
                    )
                    ctx_ms = (time.perf_counter() - t0) * 1000
                except Exception:
                    ctx_ms = (time.perf_counter() - t0) * 1000
                    page.screenshot(path=str(OUT / "q039_timeout.png"), full_page=False)
            page.screenshot(path=str(OUT / "q039_header.png"), full_page=False)

        payload = {
            "warm_ms": [round(x, 1) for x in warm],
            "warm_p50": round(statistics.median(warm), 1),
            "warm_p95": round(sorted(warm)[int(round((len(warm) - 1) * 0.95))], 1),
            "picker_scroll_ms": None if scroll_ms is None else round(scroll_ms, 1),
            "context_update_ms": None if ctx_ms is None else round(ctx_ms, 1),
        }
        (OUT / "timings.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
