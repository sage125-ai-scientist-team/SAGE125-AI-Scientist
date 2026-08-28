# -*- coding: utf-8 -*-
"""本地热状态验收：搜索 / 领域 / 快速示例 / 125 选题器。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "ui" / "final_acceptance"
UI = "http://127.0.0.1:8617"
WS = f"{UI}/workspace-questions"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"timings": {}, "search": {}, "errors": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            t0 = time.perf_counter()
            page.goto(UI, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(1500)
            report["timings"]["home_ms"] = int((time.perf_counter() - t0) * 1000)
            t1 = time.perf_counter()
            page.goto(WS, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_selector("text=关键词搜索", timeout=60000)
            report["timings"]["workspace_ms"] = int((time.perf_counter() - t1) * 1000)

            def search(term: str, shot: str) -> int:
                box = page.get_by_label("关键词搜索")
                box.first.click()
                box.first.fill(term)
                page.keyboard.press("Enter")
                go = page.get_by_role("button", name="搜索")
                if go.count():
                    go.first.click()
                page.wait_for_timeout(1800)
                body = page.inner_text("body")
                page.screenshot(path=str(OUT / shot), full_page=False)
                if "未找到匹配题目" in body:
                    return 0
                if "匹配" in body or "选择" in body:
                    return body.count("Q0") + body.count("Q1")
                return 1 if term.lower() in body.lower() else 0

            report["search"]["prime"] = search("prime", "01_search_prime.png")
            report["search"]["gravity"] = search("gravity", "02_search_gravity.png")
            report["search"]["pandemic"] = search("pandemic", "03_search_pandemic.png")
            page.get_by_label("关键词搜索").first.fill("")
            page.wait_for_timeout(400)

            page.get_by_label("领域筛选").first.click()
            page.wait_for_timeout(400)
            report["domain_options"] = [el.inner_text() for el in page.get_by_role("option").all()]
            page.screenshot(path=str(OUT / "04_domain_filter.png"), full_page=False)
            page.keyboard.press("Escape")

            page.get_by_label("状态筛选").first.click()
            page.wait_for_timeout(400)
            report["status_options"] = [el.inner_text() for el in page.get_by_role("option").all()]
            page.screenshot(path=str(OUT / "05_status_filter.png"), full_page=False)
            page.keyboard.press("Escape")

            page.screenshot(path=str(OUT / "06_quick_example.png"), full_page=False)
            page.get_by_role("button", name="素数").first.click()
            page.wait_for_timeout(1500)
            report["quick_prime_url"] = page.url
            report["quick_prime_selected"] = "Q001" in page.inner_text("body")

            change = page.get_by_role("button", name="更换问题")
            if change.count():
                change.first.click()
                page.wait_for_timeout(800)
            page.get_by_label("选择一个科学问题").first.click()
            page.wait_for_timeout(500)
            page.keyboard.type("Q028")
            page.wait_for_timeout(400)
            report["selector_options"] = [el.inner_text() for el in page.get_by_role("option").all()]
            page.screenshot(path=str(OUT / "07_question_selector_125.png"), full_page=False)
            opt = page.get_by_role("option").filter(has_text="Q028")
            if opt.count():
                opt.first.click()
            else:
                page.keyboard.press("Enter")
            page.wait_for_timeout(1200)
            page.screenshot(path=str(OUT / "08_q028_selected.png"), full_page=False)
            report["q028"] = "Will it be possible to cure all cancers?" in page.inner_text("body")

            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(OUT / "09_after_refresh.png"), full_page=False)

            nav_ms = []
            for _ in range(15):
                for path in [f"{UI}/workspace-evidence", f"{UI}/workspace-questions"]:
                    t = time.perf_counter()
                    page.goto(path, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(200)
                    nav_ms.append(int((time.perf_counter() - t) * 1000))
            report["timings"]["nav_30_samples"] = nav_ms
            report["timings"]["nav_p95_ms"] = sorted(nav_ms)[int(len(nav_ms) * 0.95) - 1] if nav_ms else None
            page.screenshot(path=str(OUT / "10_after_30_cycles.png"), full_page=False)
            page.screenshot(path=str(OUT / "11_performance_summary.png"), full_page=False)
        except Exception as exc:
            report["errors"].append(repr(exc))
            page.screenshot(path=str(OUT / "99_error.png"), full_page=True)
        finally:
            browser.close()

    (OUT / "local_acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
