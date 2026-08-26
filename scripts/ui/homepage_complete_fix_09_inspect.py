# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://127.0.0.1:8610", wait_until="domcontentloaded", timeout=60000)
    page.locator("button.hero-cta-primary").first.wait_for(timeout=45000)
    page.locator(".metric-card").first.wait_for(timeout=45000)
    page.wait_for_timeout(800)
    info = page.locator("#sage125-hero-particles").evaluate_all(
        "els => els.map(e => ({tag:e.tagName, id:e.id, w:Math.round(e.getBoundingClientRect().width), h:Math.round(e.getBoundingClientRect().height)}))"
    )
    print("PARTICLES", info)
    btns = page.locator("button.hero-cta").evaluate_all(
        "els => els.map(e => ({cls:e.className, r:getComputedStyle(e).borderRadius, w:Math.round(e.getBoundingClientRect().width), h:Math.round(e.getBoundingClientRect().height), parent:e.parentElement && e.parentElement.className}))"
    )
    print("BTNS", btns)
    page.locator(".metric-grid").first.screenshot(path="docs/ui/homepage_complete_fix_09/03_metrics_after.png")
    page.locator(".metric-grid").first.screenshot(path="docs/ui/homepage_complete_fix_09/04_glass_metrics.png")
    page.locator(".hero-actions").first.screenshot(path="docs/ui/homepage_complete_fix_09/06_rectangular_cta.png")
    page.screenshot(path="docs/ui/homepage_complete_fix_09/07_home_first_load.png")
    page.locator("text=系统能力").first.scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    page.screenshot(path="docs/ui/homepage_complete_fix_09/05_glass_bento.png")
    browser.close()
    print("OK")
