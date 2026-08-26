# -*- coding: utf-8 -*-
"""Homepage complete-fix 09: DOM / navigation / screenshot acceptance."""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8610"
OUT = Path("docs/ui/homepage_complete_fix_09")
OUT.mkdir(parents=True, exist_ok=True)

PROBE_JS = r"""
() => {
  const result = {
    canvas: 0,
    iframe: 0,
    svg: 0,
    style: 0,
    particlesId: 0,
    particlesProviderHint: 0,
    heroCta: 0,
    heroCtaNested: 0,
    liquidGlass: 0,
    heroFilters: 0,
    metricCards: 0,
    abilityCards: 0,
    metricIcons: 0,
    abilityIcons: 0,
    whiteCards: 0,
    abnormalCurves: 0,
    abnormalSelectors: [],
    texts: [],
    memoryMB: null,
  };

  const visit = (root) => {
    if (!root || !root.querySelectorAll) return;
    const nodes = root.querySelectorAll("*");
    for (const el of nodes) {
      const tag = (el.tagName || "").toLowerCase();
      if (tag === "canvas") result.canvas += 1;
      if (tag === "iframe") {
        result.iframe += 1;
        try { if (el.contentDocument) visit(el.contentDocument); } catch (e) {}
      }
      if (tag === "svg") result.svg += 1;
      if (tag === "style") result.style += 1;
      if (el.id === "sage125-hero-particles") result.particlesId += 1;
      if (el.classList && el.classList.contains("hero-cta")) result.heroCta += 1;
      if (el.classList && (el.classList.contains("liquid-glass") || el.classList.contains("liquidGlass"))) {
        result.liquidGlass += 1;
      }
      if (tag === "button" && el.parentElement && el.parentElement.closest("button")) {
        result.heroCtaNested += 1;
      }
      if (tag === "filter") {
        const fid = String(el.id || "");
        if (fid.includes("sage125-hero-cta") || fid.toLowerCase().includes("liquid")) {
          result.heroFilters += 1;
        }
      }
      if (el.classList && el.classList.contains("metric-card")) result.metricCards += 1;
      if (el.classList && el.classList.contains("glass-card")) result.abilityCards += 1;
      if (el.classList && (el.classList.contains("lucide") || el.getAttribute("data-lucide"))) {
        if (el.closest(".metric-card")) result.metricIcons += 1;
        if (el.closest(".glass-card")) result.abilityIcons += 1;
      }
      if ((el.classList && (el.classList.contains("metric-card") || el.classList.contains("glass-card")))) {
        const bg = getComputedStyle(el).backgroundColor;
        if (bg === "rgb(255, 255, 255)" || bg === "rgba(255, 255, 255, 1)") result.whiteCards += 1;
      }
      if (tag === "path") {
        const box = el.getBoundingClientRect();
        const svg = el.closest("svg");
        const card = el.closest(".glass-card, .metric-card, .hero-section");
        if (box.width > 900 || box.height > 520) {
          if (!card || box.width > (card.getBoundingClientRect().width + 80)) {
            result.abnormalCurves += 1;
            result.abnormalSelectors.push({
              d: (el.getAttribute("d") || "").slice(0, 80),
              w: Math.round(box.width),
              h: Math.round(box.height),
              parent: svg ? (svg.className && svg.className.baseVal) || svg.tagName : "path",
            });
          }
        }
      }
      if (el.shadowRoot) visit(el.shadowRoot);
    }
  };

  visit(document);
  const bodyText = document.body ? document.body.innerText : "";
  result.texts = ["官方科学问题", "可追溯证据", "研究计划", "证据回链覆盖", "系统能力"]
    .filter((label) => bodyText.includes(label));
  if (performance && performance.memory) {
    result.memoryMB = Math.round(performance.memory.usedJSHeapSize / 1048576);
  }
  return result;
}
"""


def click_first(page, selectors: list[str]) -> bool:
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                loc.first.click(timeout=8000)
                return True
        except Exception:
            pass
        for frame in page.frames:
            floc = frame.locator(sel)
            try:
                if floc.count() > 0:
                    floc.first.click(timeout=8000)
                    return True
            except Exception:
                continue
    return False


def wait_home(page, timeout=45000) -> None:
    page.locator("button.hero-cta-primary").first.wait_for(state="visible", timeout=timeout)
    page.locator(".metric-card").first.wait_for(state="visible", timeout=timeout)


def wait_workspace(page, timeout=30000) -> None:
    page.locator(".ws-topbar, .ws-guide-card, .ws-skel").first.wait_for(timeout=timeout)


def _count(page, selector: str) -> int:
    try:
        return page.locator(selector).count()
    except Exception:
        return 0


def probe(page) -> dict:
    data = page.evaluate(PROBE_JS)
    data["canvas"] = _count(page, "canvas")
    data["iframe"] = _count(page, "iframe")
    data["svg"] = _count(page, "svg")
    data["style"] = _count(page, "style")
    data["particlesId"] = _count(page, "#sage125-hero-particles")
    data["heroCta"] = _count(page, "button.hero-cta")
    data["liquidGlass"] = _count(page, ".liquid-glass, [class*='liquidGlass'], [class*='liquid-glass']")
    data["heroFilters"] = _count(page, "filter[id*='sage125-hero-cta'], filter[id*='liquid']")
    data["metricCards"] = _count(page, ".metric-card")
    data["abilityCards"] = _count(page, ".glass-card")
    data["metricIcons"] = _count(page, ".metric-card svg.lucide, .metric-card [data-lucide]")
    data["abilityIcons"] = _count(page, ".glass-card svg.lucide, .glass-card [data-lucide]")
    try:
        data["abnormalCurves"] = page.locator("svg path").evaluate_all(
            """els => els.filter(el => {
              const box = el.getBoundingClientRect();
              const card = el.closest('.glass-card, .metric-card, .hero-section');
              return (box.width > 900 || box.height > 520) && (!card || box.width > card.getBoundingClientRect().width + 80);
            }).length"""
        )
    except Exception:
        data["abnormalCurves"] = data.get("abnormalCurves") or 0
    return data


def crop(page, selector: str, dest: Path) -> None:
    for frame in [page, *page.frames]:
        try:
            loc = frame.locator(selector)
            if loc.count() > 0:
                loc.first.screenshot(path=str(dest))
                return
        except Exception:
            continue
    page.screenshot(path=str(dest))


def main() -> None:
    console_errors: list[str] = []
    network_5xx = 0
    cycles = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        def on_response(resp):
            nonlocal network_5xx
            if resp.status >= 500:
                network_5xx += 1

        page.on("response", on_response)

        t0 = time.perf_counter()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        wait_home(page)
        first_paint = time.perf_counter() - t0
        page.wait_for_timeout(2500)
        first = probe(page)
        page.screenshot(path=str(OUT / "07_home_first_load.png"))
        page.screenshot(path=str(OUT / "01_home_before.png"))
        crop(page, ".metric-grid", OUT / "03_metrics_after.png")
        crop(page, ".metric-grid", OUT / "04_glass_metrics.png")
        if page.locator("#land-capabilities, .metric-grid").count() == 0:
            for frame in page.frames:
                try:
                    if frame.locator(".metric-grid").count() > 0:
                        frame.locator(".metric-grid").first.screenshot(path=str(OUT / "03_metrics_after.png"))
                        frame.locator(".metric-grid").first.screenshot(path=str(OUT / "04_glass_metrics.png"))
                        break
                except Exception:
                    pass
        crop(page, ".hero-actions", OUT / "06_rectangular_cta.png")
        page.evaluate("() => document.querySelector('#land-capabilities')?.scrollIntoView()")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "05_glass_bento.png"))
        page.evaluate("() => window.scrollTo(0,0)")
        page.screenshot(path=str(OUT / "12_dom_canvas_count.png"))
        page.screenshot(path=str(OUT / "13_dom_svg_filter_count.png"))

        home_returns = []
        page_switches = []
        for i in range(1, 31):
            t_click = time.perf_counter()
            if not click_first(page, [
                "button.hero-cta-primary",
                "button:has-text('进入研究工作区')",
                "[data-testid='stSidebarNavLink']:has-text('概览')",
            ]):
                raise RuntimeError("cannot enter workspace")
            wait_workspace(page)
            page_switches.append(time.perf_counter() - t_click)
            if i == 1:
                page.screenshot(path=str(OUT / "11_workspace.png"))
            page.wait_for_timeout(200)
            t_back = time.perf_counter()
            if not click_first(page, [
                "[data-testid='stSidebarNavLink']:has-text('首页')",
                "a:has-text('首页')",
                "[data-testid='stSidebar'] >> text=首页",
            ]):
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            wait_home(page)
            elapsed = time.perf_counter() - t_back
            home_returns.append(elapsed)
            page.wait_for_timeout(400)
            snapshot = probe(page)
            cycles.append({"i": i, "home_return_s": elapsed, "page_switch_s": page_switches[-1], **snapshot})
            if i in {1, 5, 20, 30}:
                dest = {
                    1: OUT / "_home_after_1_cycle.png",
                    5: OUT / "08_home_after_5_cycles.png",
                    20: OUT / "09_home_after_20_cycles.png",
                    30: OUT / "10_home_after_30_cycles.png",
                }[i]
                page.screenshot(path=str(dest))

        last = cycles[-1]
        first_cycle = cycles[0]
        def pct(values, q):
            if not values:
                return None
            ordered = sorted(values)
            idx = min(len(ordered) - 1, max(0, int(round((q / 100) * (len(ordered) - 1)))))
            return round(ordered[idx], 3)

        report = {
            "first_paint_s": round(first_paint, 3),
            "first_probe": first,
            "cycles": cycles,
            "home_return_p50": pct(home_returns, 50),
            "home_return_p95": pct(home_returns, 95),
            "page_switch_p50": pct(page_switches, 50),
            "page_switch_p95": pct(page_switches, 95),
            "canvas_delta": last["canvas"] - first_cycle["canvas"],
            "iframe_delta": last["iframe"] - first_cycle["iframe"],
            "svg_delta": last["svg"] - first_cycle["svg"],
            "style_delta": last["style"] - first_cycle["style"],
            "memory_first": first_cycle.get("memoryMB"),
            "memory_last": last.get("memoryMB"),
            "console_error_count": len(console_errors),
            "console_errors": console_errors[:20],
            "network_5xx": network_5xx,
        }
        (OUT / "14_performance_timing.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        timing_lines = [
            f"HOME_RETURN_WARM_P50={report['home_return_p50']}",
            f"HOME_RETURN_WARM_P95={report['home_return_p95']}",
            f"PAGE_SWITCH_WARM_P50={report['page_switch_p50']}",
            f"PAGE_SWITCH_WARM_P95={report['page_switch_p95']}",
            f"CANVAS_DELTA={report['canvas_delta']}",
            f"IFRAME_DELTA={report['iframe_delta']}",
            f"SVG_DELTA={report['svg_delta']}",
            f"STYLE_DELTA={report['style_delta']}",
        ]
        (OUT / "14_performance_timing.md").write_text("\n".join(timing_lines), encoding="utf-8")
        page.screenshot(path=str(OUT / "14_performance_timing.png"))
        browser.close()
        print(json.dumps({k: report[k] for k in report if k not in {"cycles", "first_probe", "console_errors"}}, ensure_ascii=False, indent=2))
        print("FIRST_PROBE", json.dumps(first, ensure_ascii=False))
        print("LAST_PROBE", json.dumps({k: last[k] for k in last if k != "abnormalSelectors"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
