# -*- coding: utf-8 -*-
"""CAPTAIN-LOCAL-SAGE125-INTERACTIVE-PARTICLES-RESTORE-10 验收。"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8610"
OUT = Path("docs/ui/particles_restore_10")
OUT.mkdir(parents=True, exist_ok=True)
BUILD_DIR = Path("frontend_components/sage125_landing/sage125_landing/frontend/build")

PROBE = r"""
() => {
  const walk = (root, acc) => {
    if (!root || !root.querySelectorAll) return;
    for (const el of root.querySelectorAll("*")) {
      acc.push(el);
      if (el.shadowRoot) walk(el.shadowRoot, acc);
    }
  };
  const nodes = [];
  walk(document, nodes);
  const canvases = nodes.filter((el) => el.tagName === "CANVAS");
  const hosts = nodes.filter((el) => el.id === "sage125-hero-particles");
  const hero = nodes.find((el) => (el.className || "").toString().includes("sage125-hero"));
  const canvas = canvases.find((el) => el.id === "sage125-hero-particles")
    || hosts.map((el) => el.querySelector("canvas")).find(Boolean)
    || canvases[0];
  const style = canvas ? getComputedStyle(canvas) : null;
  const heroBox = hero ? hero.getBoundingClientRect() : {};
  const canvasBox = canvas ? canvas.getBoundingClientRect() : {};
  const inHero = !!(canvas && hero && hero.contains(canvas));
  const snap = typeof window.__sage125ParticlesCapture === "function"
    ? window.__sage125ParticlesCapture()
    : (window.__sage125ParticlesSnapshot || null);
  const scripts = [...document.querySelectorAll("script[src]")].map((el) => el.src);
  const landingScripts = scripts.filter((src) => src.includes("sage125-landing") || src.includes("index-"));
  return {
    canvasCount: canvases.length,
    hostCount: hosts.length,
    hostTags: hosts.map((el) => el.tagName),
    canvasPresent: !!canvas,
    canvasParent: canvas && canvas.parentElement ? canvas.parentElement.id || canvas.parentElement.className : null,
    canvasInHero: inHero,
    canvasWidth: canvas ? canvas.width : 0,
    canvasHeight: canvas ? canvas.height : 0,
    canvasClientWidth: canvas ? canvas.clientWidth : 0,
    canvasClientHeight: canvas ? canvas.clientHeight : 0,
    canvasBox,
    canvasOpacity: style ? Number(style.opacity) : null,
    canvasDisplay: style ? style.display : null,
    canvasVisibility: style ? style.visibility : null,
    canvasZIndex: style ? style.zIndex : null,
    heroWidth: Math.round(heroBox.width || 0),
    heroHeight: Math.round(heroBox.height || 0),
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    status: window.__sage125ParticlesStatus || null,
    error: window.__sage125ParticlesError || null,
    initCount: window.__sage125ParticlesInitCount ?? 0,
    loadSlimCount: window.__sage125LoadSlimCount ?? 0,
    readyAt: window.__sage125ParticlesReadyAtMs ?? null,
    snapshot: snap,
    iframeCount: document.querySelectorAll("iframe").length,
    svgCount: document.querySelectorAll("svg").length,
    landingScripts,
    componentKey: !!document.querySelector(".st-key-sage125-landing-home-v2"),
    metricCards: document.querySelectorAll(".metric-card").length,
    abilityCards: document.querySelectorAll(".glass-card").length,
    heroCta: document.querySelectorAll("button.hero-cta").length,
    memoryMB: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null,
  };
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
            try:
                floc = frame.locator(sel)
                if floc.count() > 0:
                    floc.first.click(timeout=8000)
                    return True
            except Exception:
                continue
    return False


def wait_home(page, timeout=45000) -> None:
    page.locator("button.hero-cta-primary").first.wait_for(state="visible", timeout=timeout)
    page.locator(".sage125-hero, .hero-section").first.wait_for(state="visible", timeout=timeout)


def wait_workspace(page, timeout=30000) -> None:
    page.locator(".ws-topbar, .ws-guide-card, .ws-skel").first.wait_for(timeout=timeout)


def probe(page) -> dict:
    return page.evaluate(PROBE)


def current_bundle_sha() -> tuple[str, str]:
    files = sorted(BUILD_DIR.glob("index-*.js"))
    if not files:
        return "", ""
    path = files[-1]
    return path.name, hashlib.sha256(path.read_bytes()).hexdigest()


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((q / 100) * (len(ordered) - 1)))))
    return round(ordered[idx], 3)


def moved_ratio(a: list[dict], b: list[dict], threshold: float = 1.5) -> tuple[float, float]:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0, 0.0
    moved = 0
    total = 0.0
    for i in range(n):
        dx = float(a[i]["x"]) - float(b[i]["x"])
        dy = float(a[i]["y"]) - float(b[i]["y"])
        dist = (dx * dx + dy * dy) ** 0.5
        total += dist
        if dist >= threshold:
            moved += 1
    return moved / n, total / n


def main() -> None:
    bundle_name, bundle_sha = current_bundle_sha()
    console_errors: list[str] = []
    network_5xx = 0
    cdn_count = 0
    loaded_bundle_sha = ""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, service_workers="block")
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        def on_response(resp):
            nonlocal network_5xx, cdn_count, loaded_bundle_sha
            if resp.status >= 500:
                network_5xx += 1
            url = resp.url
            if any(host in url for host in ("cdn.jsdelivr", "unpkg.com", "cdnjs", "esm.sh")):
                cdn_count += 1
            if "index-" in url and url.endswith(".js") and "sage125" in url:
                try:
                    loaded_bundle_sha = hashlib.sha256(resp.body()).hexdigest()
                except Exception:
                    pass

        page.on("response", on_response)

        t0 = time.perf_counter()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        wait_home(page)
        interactive_s = time.perf_counter() - t0
        page.wait_for_function("() => window.__sage125ParticlesStatus === 'ready'", timeout=8000)
        init_s = time.perf_counter() - t0

        page.screenshot(path=str(OUT / "02_after_t0.png"))
        snap0 = probe(page)
        pos0 = (snap0.get("snapshot") or {}).get("positions") or []
        links0 = (snap0.get("snapshot") or {}).get("linkCount") or 0
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT / "03_after_t2.png"))
        snap2 = probe(page)
        pos2 = (snap2.get("snapshot") or {}).get("positions") or []
        links2 = (snap2.get("snapshot") or {}).get("linkCount") or 0
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT / "04_after_t4.png"))
        snap4 = probe(page)

        moved_2s, avg_disp = moved_ratio(pos0, pos2)
        topology_changed = abs(int(links2) - int(links0)) > 0 or moved_2s >= 0.3

        hero = page.locator(".sage125-hero, .hero-section").first
        box = hero.bounding_box() or {"x": 200, "y": 120, "width": 1600, "height": 700}
        hover_before = (probe(page).get("snapshot") or {}).get("linkOpacityAvg") or 0
        hover_status = {}
        for name, fx, dest in (
            ("left", 0.18, OUT / "05_after_hover_left.png"),
            ("center", 0.50, OUT / "06_after_hover_center.png"),
            ("right", 0.82, OUT / "07_after_hover_right.png"),
        ):
            page.mouse.move(box["x"] + box["width"] * fx, box["y"] + box["height"] * 0.42)
            page.wait_for_timeout(400)
            after = probe(page)
            grab = (after.get("snapshot") or {}).get("grabBoosted") or 0
            opacity = (after.get("snapshot") or {}).get("linkOpacityAvg") or 0
            hover_status[name] = "PASS" if grab > 0 or opacity > hover_before else "FAIL"
            page.screenshot(path=str(dest))

        cta = page.locator("button.hero-cta-primary").first
        cta_box = cta.bounding_box()
        pointer_pass = bool(cta_box and cta.is_enabled())
        cta.focus()
        keyboard_pass = page.evaluate(
            """() => {
              const el = document.querySelector('button.hero-cta-primary');
              return !!el && document.activeElement === el && getComputedStyle(el).pointerEvents !== 'none';
            }"""
        )

        fps_samples: list[float] = []
        frame_times: list[float] = []
        page.evaluate(
            """() => new Promise((resolve) => {
              const times = [];
              let last = performance.now();
              const step = (now) => {
                times.push(now - last);
                last = now;
                if (times.length >= 90) {
                  window.__sage125FrameTimes = times;
                  resolve(true);
                  return;
                }
                requestAnimationFrame(step);
              };
              requestAnimationFrame(step);
            })"""
        )
        times = page.evaluate("() => window.__sage125FrameTimes || []")
        for dt in times:
            if dt > 0:
                frame_times.append(dt)
                fps_samples.append(1000.0 / dt)

        cycles = []
        visible_cycles = 0
        interactive_cycles = 0
        missing = 0
        paused_after = 0
        dup_canvas = 0
        abnormal = 0
        for i in range(1, 31):
            if not click_first(page, ["button.hero-cta-primary", "button:has-text('进入研究工作区')"]):
                raise RuntimeError("cannot enter workspace")
            wait_workspace(page)
            page.wait_for_timeout(150)
            if not click_first(page, ["[data-testid='stSidebarNavLink']:has-text('首页')", "a:has-text('首页')"]):
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            wait_home(page)
            try:
                page.wait_for_function("() => window.__sage125ParticlesStatus === 'ready'", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(250)
            snap = probe(page)
            shot = snap.get("snapshot") or {}
            canvas_ok = snap.get("canvasCount") == 1 and snap.get("canvasInHero")
            playing = snap.get("status") == "ready" and not shot.get("paused") and not shot.get("destroyed")
            nodes_ok = int(shot.get("count") or 0) > 0
            links_ok = int(shot.get("linkCount") or 0) > 0
            if canvas_ok and nodes_ok and links_ok:
                visible_cycles += 1
            else:
                missing += 1
            if canvas_ok and playing:
                interactive_cycles += 1
            if shot.get("paused") or snap.get("status") == "paused":
                paused_after += 1
            if int(snap.get("canvasCount") or 0) > 1:
                dup_canvas += 1
            cycles.append({"i": i, **snap, "playing": playing})
            if i == 1:
                page.screenshot(path=str(OUT / "08_after_return_home.png"))
            if i == 30:
                page.screenshot(path=str(OUT / "09_after_30_cycles.png"))

        mem0 = snap0.get("memoryMB")
        page.wait_for_timeout(200)
        # 15 分钟内存：首页保持粒子播放，每 30s 采样。
        mem_series = [mem0]
        t_mem = time.perf_counter()
        while time.perf_counter() - t_mem < 15 * 60:
            page.wait_for_timeout(30000)
            mem_series.append((probe(page).get("memoryMB")))
        mem_end = mem_series[-1]
        mem_growth = None
        if mem0 is not None and mem_end is not None:
            mem_growth = mem_end - mem0

        component_height = page.evaluate(
            """() => {
              const el = document.querySelector('.st-key-sage125-landing-home-v2');
              return el ? Math.round(el.getBoundingClientRect().height) : 0;
            }"""
        )

        last = probe(page)
        measurement = {
            "visible_node_count": (snap0.get("snapshot") or {}).get("count"),
            "visible_link_count": (snap0.get("snapshot") or {}).get("linkCount"),
            "average_node_displacement_2s": avg_disp,
            "moved_node_ratio_2s": moved_2s,
            "link_topology_change_count": abs(int(links2) - int(links0)),
            "hover_link_opacity_before": hover_before,
            "hover_link_opacity_after": (probe(page).get("snapshot") or {}).get("linkOpacityAvg"),
            "average_fps": sum(fps_samples) / len(fps_samples) if fps_samples else None,
            "p95_frame_time": pct(frame_times, 95),
            "memory_growth_15min": mem_growth,
            "memory_series_15min": mem_series,
        }
        (OUT / "particle_restore_measurement.json").write_text(
            json.dumps(measurement, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report = {
            "bundle_name": bundle_name,
            "bundle_sha": bundle_sha,
            "loaded_bundle_sha": loaded_bundle_sha,
            "interactive_s": interactive_s,
            "init_s": init_s,
            "snap0": snap0,
            "snap2": snap2,
            "snap4": snap4,
            "last": last,
            "hover_status": hover_status,
            "cta_pointer": pointer_pass,
            "cta_keyboard": bool(keyboard_pass),
            "cycles": cycles,
            "visible_cycles": visible_cycles,
            "interactive_cycles": interactive_cycles,
            "missing": missing,
            "paused_after": paused_after,
            "dup_canvas": dup_canvas,
            "abnormal": abnormal,
            "component_height": component_height,
            "console_errors": console_errors[:40],
            "network_5xx": network_5xx,
            "cdn_count": cdn_count,
            "measurement": measurement,
        }
        (OUT / "_verify_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(json.dumps({k: report[k] for k in report if k not in {"cycles", "snap0", "snap2", "snap4", "last"}}, ensure_ascii=False, indent=2, default=str))
        browser.close()


if __name__ == "__main__":
    main()
