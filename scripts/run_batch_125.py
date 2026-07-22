#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/run_batch_125.py — 125 问题批量输出（赛道 A 全量输出文档）。

运行示例（PowerShell）：
    $env:MOCK_LLM="true"; py -3 scripts/run_batch_125.py --mock; Remove-Item Env:\\MOCK_LLM
    $env:MOCK_LLM="true"; py -3 scripts/run_batch_125.py --mock --max-questions 5; Remove-Item Env:\\MOCK_LLM
    py -3 scripts/run_batch_125.py --real --max-questions 3 --no-deepresearch

安全/成本：真实模式默认不启用 DeepResearch（避免 125 次高成本）；单题失败不中断；
mock 输出标记 mock_for_testing；无真实实验 Results 保持 pending。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# 确保项目根在 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import get_logger, setup_logging
from app.core.config import get_settings
from app.workflow.artifacts import resolve_artifact_base

# 模块级日志器。
logger = get_logger("scripts.run_batch_125")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "questions_125.json"


def _row_from_plan(qitem: dict, plan: dict, run_id: str, status: str, report_path: str, errors, warnings) -> dict:
    """由计划构造一条 batch 记录。"""
    datasets = plan.get("datasets", {}) or {}
    experiments = plan.get("experiments", {}) or {}
    hyps = plan.get("generated_hypotheses", []) or []
    return {
        "question_id": qitem.get("id"),
        "domain": qitem.get("domain"),
        "question": qitem.get("question"),
        "status": status,
        "validation_status": plan.get("validation_status"),
        "paper_title": plan.get("paper_title"),
        "top_hypothesis": (hyps[0].get("hypothesis") if hyps else ""),
        "datasets_source_count": 1 if datasets.get("source") else 0,
        "datasets_target_count": 1 if datasets.get("target") else 0,
        "baseline_count": len(experiments.get("baselines", []) or []),
        "metric_count": len(experiments.get("metrics", []) or []),
        "reference_count": len(plan.get("references", []) or []),
        "results_pending": "待执行验证实验" in (plan.get("results", "") or ""),
        "run_id": run_id,
        "report_path": report_path,
        "errors": errors or [],
        "warnings": warnings or [],
    }


def main() -> int:
    """批处理主入口。"""
    parser = argparse.ArgumentParser(description="125 问题批量输出")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-deepresearch", action="store_true")
    parser.add_argument("--no-open-literature", action="store_true")
    parser.add_argument("--rate-limit-seconds", type=float, default=0.0)
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "exports" / "batch_125"))
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--cost-guard", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    setup_logging("INFO")

    # 模式判定：--mock 强制 mock；否则看 MOCK_LLM/--real。
    mock = args.mock or (not args.real and os.getenv("MOCK_LLM", "").strip().lower() in ("1", "true", "yes"))
    if mock:
        os.environ["MOCK_LLM"] = "true"

    # DeepResearch 开关：真实模式默认关闭（成本保护，避免 125 次高成本调用）；
    # mock 模式为廉价占位，默认开启，除非显式 --no-deepresearch。
    if args.real:
        use_deep = False
    else:
        use_deep = not args.no_deepresearch
    use_open = not args.no_open_literature

    if not QUESTIONS_PATH.exists():
        print("错误：缺少 data/processed/questions_125.json，请先运行 py -3 scripts/extract_125_questions.py。")
        return 2
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    if len(questions) != 125:
        print(f"警告：问题数量为 {len(questions)}（不是 125），仍继续。")

    # 选择子集。
    if args.question_id:
        selected = [q for q in questions if q.get("id") in set(args.question_id)]
    else:
        selected = questions[args.start_index:]
        if args.max_questions is not None:
            selected = selected[: args.max_questions]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(f"[dry-run] 将处理 {len(selected)} 个问题，mock={mock}，use_deep={use_deep}，use_open={use_open}")
        print(f"[dry-run] 输出目录：{out_dir}")
        return 0

    from app.workflow.pipeline import run_pipeline_with_state

    rows: list[dict] = []
    completed = failed = 0
    for q in selected:
        qid = q.get("id")
        qdir = out_dir / qid
        # --resume：跳过已完成。
        if args.resume and (qdir / "report.json").exists():
            logger.info("resume 跳过 %s", qid)
            try:
                plan = json.loads((qdir / "report.json").read_text(encoding="utf-8"))
                rows.append(_row_from_plan(q, plan, plan.get("run_id", ""), "completed", str((qdir / "report.json").as_posix()), [], []))
                completed += 1
            except Exception:
                pass
            continue
        try:
            plan_obj, state = run_pipeline_with_state(
                question_id=qid, use_local_rag=True, use_deep_research=use_deep,
                use_open_literature=use_open, reviewer_auto_revision=True, mock_mode=mock,
            )
            plan = plan_obj.model_dump()
            # 复制该题产物到 batch 目录。
            qdir.mkdir(parents=True, exist_ok=True)
            src = resolve_artifact_base(get_settings().export_dir) / state.run_id
            for name in ["report.json", "report.md", "evidence_cards.json", "agent_trace.json"]:
                sp = src / name
                if sp.exists():
                    (qdir / name).write_bytes(sp.read_bytes())
            rows.append(_row_from_plan(q, plan, state.run_id, "completed", str((qdir / "report.json").as_posix()), state.errors, state.warnings))
            completed += 1
        except Exception as exc:
            failed += 1
            rows.append({
                "question_id": qid, "domain": q.get("domain"), "question": q.get("question"),
                "status": "failed", "validation_status": None, "paper_title": None, "top_hypothesis": None,
                "datasets_source_count": 0, "datasets_target_count": 0, "baseline_count": 0, "metric_count": 0,
                "reference_count": 0, "results_pending": True, "run_id": "", "report_path": "",
                "errors": [str(exc)], "warnings": [],
            })
            logger.warning("问题 %s 失败：%s", qid, exc)
            if args.fail_fast:
                break
        # 速率限制。
        if args.rate_limit_seconds > 0:
            time.sleep(args.rate_limit_seconds)

    # 写 jsonl / csv。
    with (out_dir / "batch_outputs_125.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    csv_cols = ["question_id", "domain", "status", "validation_status", "paper_title", "reference_count", "results_pending", "run_id"]
    with (out_dir / "batch_outputs_125.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # 汇总。
    domain_counts = dict(Counter(r["domain"] for r in rows))
    status_counts = dict(Counter(r.get("validation_status") for r in rows))
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total": len(rows), "completed": completed, "failed": failed, "mock": mock,
        "domain_counts": domain_counts, "status_counts": status_counts, "rows": rows,
    }
    (out_dir / "batch_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # batch_summary.md。
    md = [f"# Batch 125 Summary\n", f"- 时间：{summary['created_at']}",
          f"- 总数：{summary['total']} · 完成：{completed} · 失败：{failed} · mock：{mock}\n",
          "## 各领域数量\n"]
    for d, c in domain_counts.items():
        md.append(f"- {d}: {c}")
    md.append("\n## Validation Status 分布\n")
    for s, c in status_counts.items():
        md.append(f"- {s}: {c}")
    md.append("\n## 每题摘要（摘要与路径）\n")
    md.append("| ID | Domain | Status | Validation | Refs | Pending |")
    md.append("|---|---|---|---|---|---|")
    for r in rows:
        md.append(f"| {r['question_id']} | {r['domain']} | {r['status']} | {r.get('validation_status')} | {r['reference_count']} | {r['results_pending']} |")
    (out_dir / "batch_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # batch_summary.html + pdf（失败不影响）。
    try:
        from app.exporters.html_exporter import export_batch_summary_html

        export_batch_summary_html(summary, out_dir / "batch_summary.html")
        from app.exporters.pdf_exporter import export_html_to_pdf

        export_html_to_pdf(out_dir / "batch_summary.html", out_dir / "batch_summary.pdf")
    except Exception as exc:
        logger.warning("batch summary html/pdf 生成失败（忽略）：%s", exc)

    print(f"批处理完成：total={len(rows)} completed={completed} failed={failed}")
    print(f"输出目录：{out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
