# -*- coding: utf-8 -*-
"""浏览器验收：概览并入科学问题、只读顶栏、唯一选题器。不调用付费模型。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "ui" / "overview_question_hub_12"
UI = "http://127.0.0.1:8610"


def _click_nav(page, label: str) -> None:
    sidebar = page.get_by_test_id("stSidebar")
    link = sidebar.get_by_text(label, exact=True)
    if link.count():
        link.first.click()
        page.wait_for_timeout(1400)
        return
    page.locator(f'[data-testid="stSidebarNavLink"]:has-text("{label}")').first.click()
    page.wait_for_timeout(1400)


def _pick_question(page, qid: str) -> bool:
    box = page.get_by_label("选择一个科学问题")
    if not box.count():
        boxes = page.locator('[data-testid="stSelectbox"]')
        target = None
        for i in range(boxes.count()):
            text = boxes.nth(i).inner_text()
            if "选择一个科学问题" in text or "Q" in text:
                target = boxes.nth(i)
                break
        if target is None:
            return False
        target.click()
    else:
        box.first.click()
    page.wait_for_timeout(400)
    opt = page.get_by_role("option").filter(has_text=qid)
    if opt.count():
        opt.first.click()
        page.wait_for_timeout(1400)
        return True
    page.keyboard.type(qid)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1400)
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "console_errors": [],
        "network_5xx": 0,
        "sidebar_overview": False,
        "sidebar_question": False,
        "top_selectbox_in_header": False,
        "readonly_context": False,
        "unselected_ok": False,
        "q039_ok": False,
        "q028_ok": False,
        "cross_page_qid": False,
        "legacy_redirect": False,
        "duplicate_qid": False,
        "timings": {},
        "nav_text": "",
    }

    def on_console(msg):
        if msg.type == "error" and "404" not in (msg.text or "") and "static" not in (msg.text or ""):
            report["console_errors"].append(msg.text)

    def on_response(res):
        if res.status >= 500 and ":8610" in res.url:
            report["network_5xx"] += 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", on_console)
        page.on("response", on_response)
        try:
            t0 = time.perf_counter()
            page.goto(f"{UI}/workspace-questions", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(2800)
            report["timings"]["warm_load_ms"] = int((time.perf_counter() - t0) * 1000)
            page.screenshot(path=str(OUT / "merged_page_top.png"), full_page=False)

            nav = page.get_by_test_id("stSidebar")
            report["nav_text"] = nav.inner_text() if nav.count() else page.inner_text("body")[:2000]
            report["sidebar_overview"] = "\n概览\n" in f"\n{report['nav_text']}\n" or report["nav_text"].strip().startswith("概览")
            # 侧栏正式分组不应再出现独立概览项；兼容组已 CSS 隐藏
            report["sidebar_overview"] = "概览" in report["nav_text"] and "科学问题" in report["nav_text"] and report["nav_text"].find("概览") < report["nav_text"].find("科学问题")
            visible_nav = page.locator('[data-testid="stSidebarNavLink"]:visible').all_inner_texts()
            report["visible_nav"] = visible_nav
            report["sidebar_overview"] = any(item.strip() == "概览" for item in visible_nav)
            report["sidebar_question"] = any("科学问题" in item for item in visible_nav)

            body = page.inner_text("body")
            report["unselected_ok"] = "尚未选择科学问题" in body
            header = page.locator(".st-key-ws_topbar")
            report["top_selectbox_in_header"] = header.locator('[data-testid="stSelectbox"]').count() > 0 if header.count() else False
            report["readonly_context"] = page.locator(".question-context-readonly").count() > 0

            pick_btn = page.get_by_role("button", name="选择科学问题")
            if pick_btn.count():
                t1 = time.perf_counter()
                pick_btn.first.click()
                page.wait_for_timeout(900)
                report["timings"]["picker_scroll_ms"] = int((time.perf_counter() - t1) * 1000)
            page.screenshot(path=str(OUT / "question_picker.png"), full_page=False)

            t2 = time.perf_counter()
            report["q039_picked"] = _pick_question(page, "Q039")
            report["timings"]["context_update_ms"] = int((time.perf_counter() - t2) * 1000)
            page.wait_for_timeout(400)
            ctx_value = page.locator(".context-value").inner_text() if page.locator(".context-value").count() else ""
            report["top_context_value"] = ctx_value
            report["q039_ok"] = "Q039" in ctx_value or "Q039" in page.inner_text("body")
            report["duplicate_qid"] = page.locator(".ws-qid").count() > 0
            page.screenshot(path=str(OUT / "q039_selected.png"), full_page=False)

            for label in ("文献证据", "候选假设", "研究计划", "科学问题"):
                _click_nav(page, label)
            ctx_value = page.locator(".context-value").inner_text() if page.locator(".context-value").count() else page.inner_text("body")
            report["cross_page_qid"] = "Q039" in ctx_value

            report["q028_picked"] = _pick_question(page, "Q028")
            page.wait_for_timeout(400)
            ctx_value = page.locator(".context-value").inner_text() if page.locator(".context-value").count() else ""
            report["q028_context"] = ctx_value
            report["q028_ok"] = "Q028" in ctx_value or "Q028" in page.inner_text("body")
            page.screenshot(path=str(OUT / "q028_selected.png"), full_page=False)

            page.goto(f"{UI}/workspace", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(2200)
            report["legacy_url"] = page.url
            report["legacy_redirect"] = "workspace-questions" in page.url or page.locator("#research-overview").count() > 0
            page.screenshot(path=str(OUT / "legacy_route.png"), full_page=False)
        except Exception as exc:
            report["error"] = str(exc)
            page.screenshot(path=str(OUT / "error.png"), full_page=True)
            raise
        finally:
            (OUT / "browser_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            browser.close()

    failed = []
    if report["sidebar_overview"]:
        failed.append("sidebar_overview")
    if not report["sidebar_question"]:
        failed.append("sidebar_question")
    if report["top_selectbox_in_header"]:
        failed.append("top_selectbox")
    if not report.get("readonly_context"):
        failed.append("readonly_context")
    if not report["q039_ok"]:
        failed.append("q039")
    if not report["cross_page_qid"]:
        failed.append("cross_page")
    if not report["q028_ok"]:
        failed.append("q028")
    if not report["legacy_redirect"]:
        failed.append("legacy_redirect")
    if report["network_5xx"]:
        failed.append("network_5xx")
    print(json.dumps({"failed": failed, **{k: report[k] for k in report if k != "nav_text"}}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
