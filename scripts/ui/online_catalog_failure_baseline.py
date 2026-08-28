# -*- coding: utf-8 -*-
"""线上复现：搜索 / 领域 / 快速示例 / 选题器 / 切页延迟。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "ui"
SHOTS = OUT / "screenshots" / "before"
UI = "https://sage125-ui-preview.onrender.com"
WS = f"{UI}/workspace-questions"


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "ui": UI,
        "console": [],
        "network": [],
        "network_4xx": 0,
        "network_5xx": 0,
        "timings": {},
        "search": {},
        "domain_options": [],
        "status_options": [],
        "selector_options": [],
        "quick_examples": {},
        "preview_markers": 0,
        "blank_screen_ms": None,
        "errors": [],
    }

    def on_console(msg):
        item = {"type": msg.type, "text": msg.text}
        report["console"].append(item)

    def on_response(res):
        rec = {"url": res.url, "status": res.status}
        report["network"].append(rec)
        if 400 <= res.status < 500:
            report["network_4xx"] += 1
        if res.status >= 500:
            report["network_5xx"] += 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", on_console)
        page.on("response", on_response)
        try:
            t0 = time.perf_counter()
            page.goto(UI, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(2500)
            report["timings"]["home_ms"] = int((time.perf_counter() - t0) * 1000)
            page.screenshot(path=str(SHOTS / "00_home.png"), full_page=False)
            body = page.inner_text("body")
            report["preview_markers"] = body.count("PREVIEW-SEED") + body.lower().count("placeholder question")

            enter = page.get_by_text("进入研究工作区")
            t1 = time.perf_counter()
            if enter.count():
                enter.first.click()
            else:
                page.goto(WS, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(4000)
            report["timings"]["enter_workspace_ms"] = int((time.perf_counter() - t1) * 1000)
            page.screenshot(path=str(SHOTS / "01_workspace.png"), full_page=False)

            # Wait for picker widgets
            try:
                page.wait_for_selector("text=关键词搜索", timeout=45000)
            except Exception as exc:
                report["errors"].append(f"keyword_search_missing: {exc}")
                page.screenshot(path=str(SHOTS / "01b_no_search.png"), full_page=True)

            def _input_search(term: str) -> dict:
                box = page.get_by_label("关键词搜索")
                rec = {"term": term, "visible_change": False, "result_count_text": "", "body_has_term": False}
                if not box.count():
                    rec["error"] = "no_search_input"
                    return rec
                before = page.inner_text("body")
                t = time.perf_counter()
                box.first.click()
                box.first.fill(term)
                page.wait_for_timeout(1800)
                rec["ms"] = int((time.perf_counter() - t) * 1000)
                after = page.inner_text("body")
                rec["visible_change"] = after != before
                rec["body_has_term"] = term.lower() in after.lower()
                rec["has_match_count"] = "匹配" in after
                rec["has_empty_hint"] = "未找到匹配题目" in after
                page.screenshot(path=str(SHOTS / f"search_{term}.png"), full_page=False)
                return rec

            report["search"]["prime"] = _input_search("prime")
            report["search"]["gravity"] = _input_search("gravity")
            report["search"]["pandemic"] = _input_search("pandemic")
            # clear search
            box = page.get_by_label("关键词搜索")
            if box.count():
                box.first.fill("")
                page.wait_for_timeout(800)

            def _options(label: str) -> list[str]:
                loc = page.get_by_label(label)
                if not loc.count():
                    return []
                loc.first.click(force=True)
                page.wait_for_timeout(600)
                opts = [el.inner_text() for el in page.get_by_role("option").all()]
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                return opts

            report["domain_options"] = _options("领域筛选")
            page.screenshot(path=str(SHOTS / "02_domain_filter.png"), full_page=False)
            report["status_options"] = _options("状态筛选")
            page.screenshot(path=str(SHOTS / "03_status_filter.png"), full_page=False)
            report["selector_options"] = _options("选择一个科学问题")
            page.screenshot(path=str(SHOTS / "04_question_selector.png"), full_page=False)

            for label in ["素数", "疫情预测", "气候变化", "AI 创造力", "量子计算"]:
                t = time.perf_counter()
                btn = page.get_by_text(label, exact=True)
                ok = False
                qid_before = page.url
                body_before = page.inner_text("body")
                if btn.count():
                    btn.first.click()
                    page.wait_for_timeout(1500)
                    body_after = page.inner_text("body")
                    ok = body_after != body_before or page.url != qid_before
                report["quick_examples"][label] = {
                    "found": bool(btn.count()),
                    "changed": ok,
                    "ms": int((time.perf_counter() - t) * 1000),
                    "url": page.url,
                }
            page.screenshot(path=str(SHOTS / "05_quick_examples.png"), full_page=False)

            # navigation timings
            nav_ms = []
            for path in [
                f"{UI}/workspace-evidence",
                f"{UI}/workspace-hypotheses",
                f"{UI}/workspace-questions",
            ]:
                t = time.perf_counter()
                page.goto(path, wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(500)
                # detect blank-ish body
                text = (page.inner_text("body") or "").strip()
                elapsed = int((time.perf_counter() - t) * 1000)
                nav_ms.append({"path": path, "ms": elapsed, "chars": len(text)})
            report["timings"]["navigation"] = nav_ms
            page.screenshot(path=str(SHOTS / "06_after_nav.png"), full_page=False)
        except Exception as exc:
            report["errors"].append(repr(exc))
            page.screenshot(path=str(SHOTS / "99_error.png"), full_page=True)
        finally:
            browser.close()

    (OUT / "online_failure_network.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    console_lines = [f"[{i['type']}] {i['text']}" for i in report["console"] if i["type"] == "error"]
    (OUT / "online_failure_console.txt").write_text("\n".join(console_lines) or "(no console errors)\n", encoding="utf-8")
    print(json.dumps({
        "domain_option_count": len(report["domain_options"]),
        "status_option_count": len(report["status_options"]),
        "selector_option_count": len(report["selector_options"]),
        "search": {k: {kk: vv for kk, vv in v.items() if kk != "error"} for k, v in report["search"].items()},
        "quick": report["quick_examples"],
        "timings": report["timings"],
        "console_errors": len(console_lines),
        "network_4xx": report["network_4xx"],
        "network_5xx": report["network_5xx"],
        "errors": report["errors"],
        "domain_options": report["domain_options"][:20],
        "selector_sample": report["selector_options"][:8],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
