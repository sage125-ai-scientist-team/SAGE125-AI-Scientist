# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import json

PROBE = r"""
() => {
  const byId = document.getElementById("sage125-hero-particles");
  const walk = (root, acc) => {
    if (!root || !root.querySelectorAll) return;
    for (const el of root.querySelectorAll("*")) {
      acc.push(el);
      if (el.shadowRoot) walk(el.shadowRoot, acc);
    }
  };
  const nodes = [];
  walk(document, nodes);
  const canvas = nodes.find((el) => el.tagName === "CANVAS" && el.id === "sage125-hero-particles")
    || nodes.find((el) => el.tagName === "CANVAS");
  const chain = [];
  let n = canvas;
  while (n) {
    const cs = n.nodeType === 1 ? getComputedStyle(n) : null;
    chain.push({
      tag: n.tagName || n.nodeName,
      id: n.id || "",
      cls: (n.className || "").toString().slice(0, 80),
      z: cs ? cs.zIndex : null,
      op: cs ? cs.opacity : null,
      bg: cs ? cs.backgroundColor : null,
      pos: cs ? cs.position : null,
    });
    n = n.parentElement;
  }
  const sample = { offscreen: true };
  const engine = window.tsParticles || null;
  let containers = [];
  try {
    if (engine && engine.dom) {
      containers = engine.dom().map((c) => ({
        id: c.id,
        paused: c.paused,
        destroyed: c.destroyed,
        started: c.started,
        w: c.canvas?.size?.width,
        h: c.canvas?.size?.height,
        count: c.particles?.count,
      }));
    }
  } catch (e) {
    containers = [{ error: String(e) }];
  }
  return {
    getElementByIdTag: byId ? byId.tagName : null,
    getElementByIdInDocument: !!byId,
    canvasInShadow: !!(canvas && canvas.getRootNode && canvas.getRootNode() !== document),
    rootNode: canvas && canvas.getRootNode ? canvas.getRootNode().toString() : null,
    parentChain: chain,
    opaqueSamples: opaque,
    totalSamples: total,
    midPixel: sample,
    containers,
    initCount: window.__sage125ParticlesInitCount ?? null,
  };
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://127.0.0.1:8610", wait_until="domcontentloaded", timeout=60000)
    page.locator("button.hero-cta-primary").first.wait_for(timeout=45000)
    page.wait_for_timeout(4000)
    print(json.dumps(page.evaluate(PROBE), ensure_ascii=False, indent=2))
    browser.close()
