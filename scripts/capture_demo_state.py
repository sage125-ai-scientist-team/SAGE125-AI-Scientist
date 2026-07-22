#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/capture_demo_state.py — 导出前端演示所需的状态文件（非浏览器截图）。

运行示例：
    py -3 scripts/capture_demo_state.py --run-id <run_id>

输出到 exports/demo_state/：hero_status / selected_question / agent_timeline /
evidence_wall_sample / research_plan_preview / export_center_manifest / screenshot_guide.md。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保项目根在 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import get_logger, setup_logging

# 模块级日志器。
logger = get_logger("scripts.capture_demo_state")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "exports" / "demo_state"


def _latest_run() -> str | None:
    """选择最新含 report.json 的 run 目录名。"""
    exports = PROJECT_ROOT / "exports"
    if not exports.exists():
        return None
    runs = [d for d in exports.iterdir() if d.is_dir() and (d / "report.json").exists()]
    if not runs:
        return None
    return max(runs, key=lambda x: x.stat().st_mtime).name


def main() -> int:
    """捕获演示状态主入口。"""
    parser = argparse.ArgumentParser(description="导出前端演示状态")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    setup_logging("INFO")
    run_id = args.run_id or _latest_run()
    if not run_id:
        print("错误：未找到任何运行产物，请先运行 py -3 scripts/run_demo.py。")
        return 2

    run_dir = PROJECT_ROOT / "exports" / run_id
    if not run_dir.exists():
        print(f"错误：运行不存在：{run_id}")
        return 2

    def _rj(name: str):
        p = run_dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    plan = _rj("report.json") or {}
    evidence = _rj("evidence_cards.json") or []
    trace = _rj("agent_trace.json") or []

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # hero_status。
    from app.core.config import get_settings

    s = get_settings()
    (OUT_DIR / "hero_status.json").write_text(json.dumps({
        "qwen_configured": s.qwen_configured, "deep_research_configured": s.deep_research_configured,
        "run_id": run_id, "validation_status": plan.get("validation_status"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # selected_question。
    (OUT_DIR / "selected_question.json").write_text(json.dumps({
        "input_question": plan.get("input_question"), "domain": plan.get("domain"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # agent_timeline。
    (OUT_DIR / "agent_timeline.json").write_text(json.dumps(
        [{"agent_name": e.get("agent_name"), "model_name": e.get("model_name"),
          "status": e.get("status"), "duration_ms": e.get("duration_ms")} for e in trace],
        ensure_ascii=False, indent=2), encoding="utf-8")

    # evidence_wall_sample（前 6 条）。
    (OUT_DIR / "evidence_wall_sample.json").write_text(json.dumps(evidence[:6], ensure_ascii=False, indent=2), encoding="utf-8")

    # research_plan_preview。
    (OUT_DIR / "research_plan_preview.json").write_text(json.dumps({
        "paper_title": plan.get("paper_title"), "validation_status": plan.get("validation_status"),
        "hypotheses": [h.get("hypothesis") for h in plan.get("generated_hypotheses", [])],
        "results": plan.get("results"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # export_center_manifest。
    files = [f.name for f in run_dir.iterdir() if f.is_file()]
    (OUT_DIR / "export_center_manifest.json").write_text(json.dumps({"run_id": run_id, "files": files}, ensure_ascii=False, indent=2), encoding="utf-8")

    # screenshot_guide.md。
    (OUT_DIR / "screenshot_guide.md").write_text(
        "# 截图指南\n\n"
        "1. Hero + Sidebar（体现 Qwen/Bailian 与多智能体定位）\n"
        "2. Step 01 · 125 Questions 选题大卡片\n"
        "3. Step 04 · Agent Timeline + 关系图\n"
        "4. Step 05 · Evidence Wall 证据墙\n"
        "5. Step 06 · ResearchPlan（Executive Summary / Research Plan Tab）\n"
        "6. Step 07 · Human-in-the-loop Feedback\n"
        "7. Step 08 · Export Center + 赛题提交映射表\n",
        encoding="utf-8",
    )

    print(f"演示状态已导出：{OUT_DIR}（run_id={run_id}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
