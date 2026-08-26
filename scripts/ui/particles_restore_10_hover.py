# -*- coding: utf-8 -*-
"""Hover grab + switch-overhead recheck after mouse-position diagnostic fix."""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8610"
OUT = Path("docs/ui/particles_restore_10")


def click_first(page, selectors: list[str]) -> bool:
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                loc.first.click(timeout=8000)
                return True
        except Exception:
            pass
    return False


def wait_home(page) -> None:
    page.locator("button.hero-cta-primary").first.wait_for(state="visible", timeout=45000)


def wait_workspace(page) -> None:
    page.locator(".ws-topbar, .ws-guide-card, .ws-skel").first.wait_for(timeout=30000)


def capture(page) -> dict:
    return page.evaluate(
        """() => window.__sage125ParticlesCapture ? window.__sage125ParticlesCapture() : null"""
    )


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, service_workers="block")
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        wait_home(page)
        page.wait_for_function("() => window.__sage125ParticlesStatus === 'ready'", timeout=8000)
        page.wait_for_timeout(800)

        hero = page.locator(".sage125-hero").first
        box = hero.bounding_box() or {"x": 64, "y": 112, "width": 1792, "height": 700}
        before = capture(page)
        hover = {}
        for name, fx, dest in (
            ("left", 0.18, OUT / "05_after_hover_left.png"),
            ("center", 0.50, OUT / "06_after_hover_center.png"),
            ("right", 0.82, OUT / "07_after_hover_right.png"),
        ):
            x = box["x"] + box["width"] * fx
            y = box["y"] + box["height"] * 0.42
            page.mouse.move(x, y, steps=12)
            page.evaluate(
                """([x, y]) => {
                  document.dispatchEvent(new PointerEvent('pointermove', {
                    clientX: x, clientY: y, bubbles: true, cancelable: true, view: window
                  }));
                }""",
                [x, y],
            )
            page.wait_for_timeout(500)
            after = capture(page)
            hover[name] = {
                "grabBoosted": (after or {}).get("grabBoosted"),
                "mouse": (after or {}).get("mouse"),
                "detectsOn": (after or {}).get("detectsOn"),
                "hoverEnabled": (after or {}).get("hoverEnabled"),
                "linkOpacityAvg": (after or {}).get("linkOpacityAvg"),
            }
            page.screenshot(path=str(dest))

        switches = []
        for _ in range(5):
            t0 = time.perf_counter()
            if not click_first(page, ["button.hero-cta-primary"]):
                raise RuntimeError("cannot enter workspace")
            wait_workspace(page)
            switches.append(time.perf_counter() - t0)
            t1 = time.perf_counter()
            if not click_first(page, ["[data-testid='stSidebarNavLink']:has-text('首页')"]):
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            wait_home(page)
            page.wait_for_function("() => window.__sage125ParticlesStatus === 'ready'", timeout=8000)
            switches.append(time.perf_counter() - t1)

        report = {
            "before": before,
            "hover": hover,
            "page_switch_samples_s": switches,
            "page_switch_p95_s": sorted(switches)[min(len(switches) - 1, int(round(0.95 * (len(switches) - 1))))],
        }
        (OUT / "_hover_recheck.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        browser.close()


if __name__ == "__main__":
    main()
