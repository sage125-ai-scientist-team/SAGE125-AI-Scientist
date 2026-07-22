#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/run_demo.py — 多智能体 Pipeline 演示脚本。

Mock 演示（推荐，无需 Key）：
    PowerShell: $env:MOCK_LLM="true"; py -3 scripts/run_demo.py; Remove-Item Env:\\MOCK_LLM

真实模式：
    py -3 scripts/run_demo.py --real
    前置：配置 DASHSCOPE_API_KEY（python scripts/setup_env.py）+ 构建 RAG 索引。

功能：
    自动定位 “Can we predict the next pandemic?”，否则回退到首个 Medicine & Health
    问题，再回退到 Q001；运行 run_pipeline 并打印各产物路径与安全提醒。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 确保项目根在 sys.path 中。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

# 模块级日志器。
logger = get_logger("scripts.run_demo")

# 项目根与问题清单。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "questions_125.json"


def _select_question_id(items: list[dict]) -> str:
    """
    选择演示问题 ID：优先 pandemic，其次首个 Medicine & Health，最后 Q001。

    参数：
        items: 问题列表。

    返回：
        选中的 question_id。
    """
    # 1) pandemic 问题。
    for it in items:
        if "predict the next pandemic" in it.get("question", "").lower():
            return it["id"]
    # 2) 首个 Medicine & Health。
    for it in items:
        if it.get("domain") == "Medicine & Health":
            return it["id"]
    # 3) 回退 Q001 或首个。
    return items[0]["id"] if items else "Q001"


def main() -> int:
    """
    演示入口：解析参数 -> 选题 -> 运行 pipeline -> 打印产物与提醒。

    返回：
        进程退出码。
    """
    parser = argparse.ArgumentParser(description="SAGE125 多智能体 Pipeline 演示")
    parser.add_argument("--real", action="store_true", help="真实模式（需配置百炼 Key 与 RAG 索引）")
    parser.add_argument("--question-id", default=None, help="指定 question_id")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)

    # 判定模式：--real 时关闭 mock；否则依赖 MOCK_LLM。
    mock_mode = None
    if args.real:
        mock_mode = False
        # 真实模式前置检查。
        if not settings.qwen_configured:
            print("错误：真实模式需要 DASHSCOPE_API_KEY。请先运行 python scripts/setup_env.py。")
            return 2
        index_dir = PROJECT_ROOT / "data" / "index" / "zvec"
        if not (index_dir.exists() and any(index_dir.iterdir())):
            print("提示：未检测到 RAG 索引，请先运行 py -3 scripts/build_rag_index.py。")
    else:
        # 未显式 --real 时，若未设置 MOCK_LLM 则默认开启 mock，便于开箱演示。
        if os.getenv("MOCK_LLM", "").strip().lower() not in ("1", "true", "yes"):
            os.environ["MOCK_LLM"] = "true"
        mock_mode = True

    # 问题清单存在性检查。
    if not QUESTIONS_PATH.exists():
        print("错误：缺少 data/processed/questions_125.json，请先运行 py -3 scripts/extract_125_questions.py。")
        return 3

    items = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    qid = args.question_id or _select_question_id(items)

    # 延迟导入 pipeline（此时 MOCK_LLM 已就绪）。
    from app.workflow.pipeline import run_pipeline_with_state

    plan, state = run_pipeline_with_state(qid, mock_mode=mock_mode)

    # 打印结果与产物路径。
    run_dir = PROJECT_ROOT / "exports" / state.run_id
    print("=" * 60)
    print("SAGE125 多智能体 Pipeline 演示结果")
    print(f"  run_id            : {state.run_id}")
    print(f"  selected_question : [{qid}] {plan.input_question}")
    print(f"  domain            : {plan.domain}")
    print(f"  validation_status : {plan.validation_status}")
    print(f"  evidence_count    : {len(state.retrieved_evidence)}")
    print("-" * 60)
    print("  产物：")
    for name in ["report.json", "report.md", "evidence_cards.json", "agent_trace.json",
                 "context_pack.json", "quality_gates.json", "run_summary.txt"]:
        print(f"    - {run_dir / name}")
    print("=" * 60)
    if mock_mode:
        print("提醒：当前为 Mock 模式，结果不能作为真实科学结论；Results 为 pending。")
        print("正式评审请配置百炼 Key 并构建真实 RAG index 后使用 --real。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
