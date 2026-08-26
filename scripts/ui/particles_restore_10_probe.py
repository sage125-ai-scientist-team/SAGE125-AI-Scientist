# -*- coding: utf-8 -*-
"""Pre-change diagnosis of homepage tsParticles."""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8610"
OUT = Path("docs/ui/particles_restore_10")
OUT.mkdir(parents=True, exist_ok=True)

PROBE = r"""
() => {
  const logs = [];
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
  const particlesHosts = nodes.filter((el) => el.id === "sage125-hero-particles");
  const fallback = nodes.filter((el) => (el.className || "").toString().includes("particles-layer"));
  const grid = nodes.filter((el) => (el.className || "").toString().includes("ambient-light-layer"));
  const hero = nodes.find((el) => (el.className || "").toString().includes("hero-section"));
  const canvas = canvases.find((el) => el.id === "sage125-hero-particles") || canvases[0];
  const style = canvas ? getComputedStyle(canvas) : null;
  const parentStyle = canvas && canvas.parentElement ? getComputedStyle(canvas.parentElement) : null;
  const heroBox = hero ? hero.getBoundingClientRect() : null;
  const canvasBox = canvas ? canvas.getBoundingClientRect() : null;
  return {
    canvasCount: canvases.length,
    particlesHostCount: particlesHosts.length,
    particlesHostTags: particlesHosts.map((el) => el.tagName),
    canvasPresent: !!canvas,
    canvasWidthAttr: canvas ? canvas.width : null,
    canvasHeightAttr: canvas ? canvas.height : null,
    canvasClientWidth: canvas ? canvas.clientWidth : null,
    canvasClientHeight: canvas ? canvas.clientHeight : null,
    canvasBox,
    canvasOpacity: style ? style.opacity : null,
    canvasDisplay: style ? style.display : null,
    canvasVisibility: style ? style.visibility : null,
    canvasZIndex: style ? style.zIndex : null,
    parentOpacity: parentStyle ? parentStyle.opacity : null,
    parentDisplay: parentStyle ? parentStyle.display : null,
    heroBox,
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    initCount: window.__sage125ParticlesInitCount ?? null,
    readyAt: window.__sage125ParticlesReadyAtMs ?? null,
    fallbackLayerCount: fallback.length,
    gridLayerCount: grid.length,
    bodyHasParticlesText: document.body.innerText.includes("SAGE125"),
  };
}
"""


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, service_workers="block")
        page = context.new_page()
        console = []
        page.on("console", lambda msg: console.append({"type": msg.type, "text": msg.text}))
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.locator("button.hero-cta-primary").first.wait_for(timeout=45000)
        page.wait_for_timeout(3000)
        data = page.evaluate(PROBE)
        frames = []
        for frame in page.frames:
            try:
                extra = frame.evaluate(PROBE)
            except Exception:
                continue
            frames.append({"url": frame.url, **extra})
        page.screenshot(path=str(OUT / "01_before_no_particles.png"))
        report = {
            "main": data,
            "frames": frames,
            "console": console[:40],
            "url": page.url,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        (OUT / "_pre_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        browser.close()


if __name__ == "__main__":
    main()
