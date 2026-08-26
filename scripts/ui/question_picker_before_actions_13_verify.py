# -*- coding: utf-8 -*-
"""浏览器验收：选题区在快速操作上方，首屏可见，不自动滚顶。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "ui" / "question_picker_before_actions_13"
UI = "http://127.0.0.1:8610"
VIEWPORTS = [(1920, 1080), (1600, 900), (1440, 900), (1366, 768)]


def _open_hub(page) -> None:
    page.goto(f"{UI}/workspace-questions", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(700)
    if page.locator('[data-testid="stDialog"]').count():
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    page.wait_for_selector("#question-picker, .question-context-readonly", timeout=30000)


def _visible(page, selector: str) -> bool:
    loc = page.locator(selector)
    if not loc.count():
        return False
    box = loc.first.bounding_box()
    if not box:
        return False
    vh = page.viewport_size["height"]
    return box["y"] < vh and (box["y"] + min(box["height"], 40)) > 0


def _pick(page, qid: str) -> bool:
    box = page.get_by_label("选择一个科学问题")
    if not box.count():
        return False
    box.first.click(force=True)
    page.wait_for_timeout(200)
    box.first.fill(qid)
    page.wait_for_timeout(250)
    opt = page.get_by_role("option").filter(has_text=qid)
    if opt.count():
        opt.first.click()
    else:
        page.keyboard.press("Enter")
    page.wait_for_timeout(800)
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "console_errors": [],
        "network_5xx": 0,
        "viewports": {},
        "unselected_disabled": False,
        "history_enabled": False,
        "q039_compact": False,
        "q039_actions_enabled": False,
        "no_auto_scroll": True,
        "q028_changed": False,
        "top_readonly": False,
        "timings": {},
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
            _open_hub(page)
            report["timings"]["hub_load_ms"] = int((time.perf_counter() - t0) * 1000)
            page.screenshot(path=str(OUT / "unselected.png"), full_page=False)
            report["top_readonly"] = page.locator(".st-key-ws_topbar [data-testid='stSelectbox']").count() == 0
            report["picker_before_actions"] = (
                page.locator("#question-picker").count() and page.locator("#quick-actions").count()
            )
            gen = page.get_by_role("button", name="开始生成")
            hist = page.get_by_role("button", name="查看历史")
            report["unselected_disabled"] = gen.count() > 0 and bool(gen.first.is_disabled())
            report["history_enabled"] = hist.count() > 0 and hist.first.is_enabled()

            scroll_before = page.evaluate("() => window.scrollY")
            t1 = time.perf_counter()
            report["q039_picked"] = _pick(page, "Q039")
            report["timings"]["select_to_action_ms"] = int((time.perf_counter() - t1) * 1000)
            scroll_after = page.evaluate("() => window.scrollY")
            report["no_auto_scroll"] = abs(scroll_after - scroll_before) < 80
            report["q039_compact"] = page.locator(".selected-question-bar").count() > 0
            report["q039_actions_enabled"] = page.get_by_role("button", name="开始生成").first.is_enabled()
            report["top_q039"] = "Q039" in (page.locator(".context-value").inner_text() if page.locator(".context-value").count() else "")
            page.screenshot(path=str(OUT / "q039_selected.png"), full_page=False)
            page.screenshot(path=str(OUT / "quick_actions.png"), full_page=False)

            if page.get_by_role("button", name="更换问题").count():
                page.get_by_role("button", name="更换问题").first.click()
                page.wait_for_timeout(500)
                report["expanded_after_change"] = page.get_by_label("选择一个科学问题").count() > 0
                _pick(page, "Q028")
                report["q028_changed"] = "Q028" in page.inner_text("body")
                page.screenshot(path=str(OUT / "q028_changed.png"), full_page=False)

            for w, h in VIEWPORTS:
                page.set_viewport_size({"width": w, "height": h})
                _open_hub(page)
                same = _visible(page, "#question-picker") and _visible(page, "#quick-actions")
                actions_title = page.get_by_text("快速操作", exact=True)
                same = same and actions_title.count() > 0
                report["viewports"][f"{w}x{h}"] = {
                    "picker": _visible(page, "#question-picker"),
                    "actions": _visible(page, "#quick-actions"),
                    "same_viewport": same,
                }
                page.screenshot(path=str(OUT / f"viewport_{w}x{h}.png"), full_page=False)
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
    if not report.get("unselected_disabled"):
        failed.append("unselected_disabled")
    if not report.get("history_enabled"):
        failed.append("history_enabled")
    if not report.get("q039_compact"):
        failed.append("q039_compact")
    if not report.get("q039_actions_enabled"):
        failed.append("q039_actions_enabled")
    if not report.get("no_auto_scroll"):
        failed.append("auto_scroll")
    if not report.get("top_readonly"):
        failed.append("top_readonly")
    if report["network_5xx"]:
        failed.append("network_5xx")
    for key, item in report.get("viewports", {}).items():
        if not item.get("same_viewport"):
            failed.append(f"viewport_{key}")
    print(json.dumps({"failed": failed, **report}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
