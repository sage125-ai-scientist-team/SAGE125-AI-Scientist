# -*- coding: utf-8 -*-
"""浏览器验收：侧栏切页恢复同一 Job。mock/test only，不调用付费模型。"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "ui" / "durable_job_progress_11"
UI = "http://127.0.0.1:8610"
API = "http://127.0.0.1:8000"
CLIENT_ID = "browser-verify-11"
QUESTION_ID = "Q001"

NAV = [
    ("overview", "概览", "overview.png"),
    ("evidence", "文献证据", "evidence.png"),
    ("hypotheses", "候选假设", "hypotheses.png"),
    ("plan", "研究计划", "plan.png"),
    ("execution", "实验与运行", "execution.png"),
    ("overview_return", "概览", "overview_return.png"),
]


def _reuse_or_create_job() -> dict:
    listing = requests.get(
        f"{API}/api/v1/jobs",
        params={"question_id": QUESTION_ID, "limit": 20},
        timeout=10,
    )
    if listing.status_code == 200:
        for item in listing.json().get("items") or []:
            if item.get("client_id") == CLIENT_ID and item.get("job_id"):
                item["created"] = False
                return item
    payload = {
        "question_id": QUESTION_ID,
        "mode": "mock",
        "job_type": "FULL_RESEARCH_PIPELINE",
        "client_id": CLIENT_ID,
        "input_digest": "browser-verify",
        "options": {
            "use_deep_research": False,
            "use_open_literature": True,
            "use_local_rag": True,
            "reviewer_auto_revision": True,
        },
    }
    created = requests.post(f"{API}/api/v1/jobs", json=payload, timeout=10)
    if created.status_code in (200, 202):
        return created.json()
    raise RuntimeError(f"create_job {created.status_code}: {created.text[:200]}")


def _visible(page, job_id: str) -> bool:
    body = page.inner_text("body")
    return any(
        token in body
        for token in (
            job_id,
            "FULL_RESEARCH_PIPELINE",
            "活动任务",
            "运行中，查看进度",
            "查看结果",
            "查看部分结果",
            "部分完成",
            "已形成计划",
            "执行中",
            "Job ",
            "正在从后台恢复",
        )
    )


def _click_nav(page, label: str) -> None:
    link = page.get_by_test_id("stSidebar").get_by_text(label, exact=True)
    if link.count():
        link.first.click()
        page.wait_for_timeout(1600)
        return
    page.get_by_role("link", name=label).first.click()
    page.wait_for_timeout(1600)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    accepted = _reuse_or_create_job()
    job_id = accepted["job_id"]
    before_count = len(
        [
            item
            for item in requests.get(
                f"{API}/api/v1/jobs",
                params={"question_id": QUESTION_ID, "limit": 50},
                timeout=10,
            ).json().get("items", [])
            if item.get("client_id") == CLIENT_ID
        ]
    )
    timings: list[float] = []
    console_errors: list[str] = []
    network_5xx = 0
    job_ids: dict[str, str] = {"original": job_id}
    visible_map: dict[str, bool] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        page = context.new_page()
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text)
            if msg.type == "error" and "404" not in msg.text
            else None,
        )
        page.on(
            "response",
            lambda resp: setattr(
                type("X", (), {}),
                "n",
                None,
            ),
        )

        def on_response(resp):
            nonlocal network_5xx
            if resp.status >= 500:
                network_5xx += 1

        page.on("response", on_response)

        started = time.perf_counter()
        page.goto(
            f"{UI}/workspace?qid={QUESTION_ID}&job_id={job_id}&client_id={CLIENT_ID}",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        page.wait_for_timeout(4000)
        timings.append((time.perf_counter() - started) * 1000)

        for name, label, shot in NAV:
            t0 = time.perf_counter()
            if name != "overview":
                _click_nav(page, label)
            else:
                page.wait_for_timeout(400)
            elapsed = (time.perf_counter() - t0) * 1000
            timings.append(elapsed)
            seen = _visible(page, job_id)
            visible_map[name] = seen
            job_ids[name] = job_id if seen or job_id in page.url else "MISSING"
            page.screenshot(path=str(OUT / shot), full_page=True)
            print(f"PAGE {name} visible={seen} ms={elapsed:.0f}")

        page.reload(wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT / "after_refresh.png"), full_page=True)
        refresh_ok = _visible(page, job_id) or job_id in page.url

        cycle_ids = []
        labels = ["概览", "文献证据", "候选假设", "研究计划", "实验与运行"]
        for index in range(30):
            _click_nav(page, labels[index % 5])
            cycle_ids.append(job_id if (job_id in page.url or _visible(page, job_id)) else "CHANGED")

        after = requests.get(
            f"{API}/api/v1/jobs",
            params={"question_id": QUESTION_ID, "limit": 50},
            timeout=10,
        ).json()
        same_client = [
            item
            for item in after.get("items", [])
            if item.get("client_id") == CLIENT_ID
            and item.get("job_type") == "FULL_RESEARCH_PIPELINE"
        ]
        browser.close()

    timings_sorted = sorted(timings)
    p95 = timings_sorted[max(0, int(len(timings_sorted) * 0.95) - 1)] if timings_sorted else 0
    all_visible = all(visible_map.values())
    report = {
        "job_id": job_id,
        "job_ids": job_ids,
        "visible": visible_map,
        "refresh_ok": refresh_ok,
        "duplicate_jobs": max(0, len(same_client) - max(before_count, 1)),
        "same_client_job_count": len(same_client),
        "cycle_job_id_change_count": sum(1 for item in cycle_ids if item != job_id),
        "navigation_cycle_count": 30,
        "rehydration_ms": timings,
        "rehydration_p95_ms": p95,
        "console_errors": console_errors,
        "network_5xx": network_5xx,
        "all_pages_visible": all_visible,
        "screenshots": [str(path.name) for path in OUT.glob("*.png")],
    }
    (OUT / "browser_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    ok = (
        all_visible
        and refresh_ok
        and report["cycle_job_id_change_count"] == 0
        and report["duplicate_jobs"] == 0
        and network_5xx == 0
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
