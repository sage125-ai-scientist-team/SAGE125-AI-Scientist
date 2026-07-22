#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/check_real_qwen_invocation.py — 验证"是否真实调用了 Qwen"的最小真实链路。

用途：
    在配置了真实百炼 Key 的环境下，运行一次最小 real pipeline（可跳过 DeepResearch），
    输出脱敏的 LLM 调用审计摘要，确认 qwen_call_count > 0 且 mock_call_count == 0，
    并确认报告的 input_question / question_id 属于指定问题。

运行（PowerShell；Key 从本地 .env 读取，勿在命令行传 Key）：
    py -3 scripts/check_real_qwen_invocation.py --question-id Q001 --no-deepresearch

安全：不打印 API Key；默认不纳入 pytest（真实脚本）。无 Key 时清晰提示并 exit 1。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# 确保项目根在 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger("scripts.check_real_qwen_invocation")


def main() -> int:
    """真实 Qwen 调用验证主入口。"""
    parser = argparse.ArgumentParser(description="验证真实 Qwen 调用链路")
    parser.add_argument("--question-id", default="Q001", help="问题 ID（默认 Q001）")
    parser.add_argument("--no-deepresearch", action="store_true", help="跳过 DeepResearch（更快、更省）")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)

    # 前置检查：必须配置百炼；否则清晰提示并 exit 1（不静默降级 mock）。
    if not settings.qwen_configured:
        print("错误：未配置 DASHSCOPE_API_KEY / WORKSPACE_ID。")
        print("请先运行 py -3 scripts/setup_env.py，然后重试。真实脚本不会降级为 mock。")
        return 1

    # 强制真实模式：确保 MOCK_LLM 未开启。
    os.environ.pop("MOCK_LLM", None)

    from app.core.call_audit import summarize_calls
    from app.workflow.pipeline import run_pipeline_with_state

    print(f"开始真实最小 pipeline：question_id={args.question_id}，deepresearch={'off' if args.no_deepresearch else 'on'}")
    try:
        plan, state = run_pipeline_with_state(
            question_id=args.question_id,
            use_local_rag=True,
            use_deep_research=(not args.no_deepresearch),
            use_open_literature=False,  # 最小链路：减少外部依赖。
            reviewer_auto_revision=False,
            mock_mode=False,
        )
    except Exception as exc:
        print(f"真实运行失败（未静默降级）：{type(exc).__name__}: {exc}")
        return 1

    summary = summarize_calls(getattr(state, "llm_calls", []) or [])
    qwen_calls = summary.get("qwen_call_count", 0)
    mock_calls = summary.get("mock_call_count", 0)

    print("=" * 56)
    print("真实 Qwen 调用验证结果")
    print(f"  run_id           : {state.run_id}")
    print(f"  question_id      : {plan.question_id}")
    print(f"  input_question   : {plan.input_question}")
    print(f"  qwen_call_count  : {qwen_calls}")
    print(f"  mock_call_count  : {mock_calls}")
    print(f"  failed_call_count: {summary.get('failed_call_count', 0)}")
    print(f"  request_ids      : {summary.get('request_ids_masked', [])}")
    print(f"  usage_summary    : {summary.get('usage_summary', {})}")
    print(f"  audit_file       : exports/{state.run_id}/llm_call_audit.json")
    print("=" * 56)

    # 判定：真实调用 > 0，mock == 0，且报告属于该问题。
    ok = (
        qwen_calls > 0
        and mock_calls == 0
        and plan.question_id == args.question_id
    )
    if ok:
        print("RESULT: PASS（已确认真实调用 Qwen，且报告属于指定问题）")
        return 0
    print("RESULT: FAIL（未满足 qwen_call_count>0 且 mock_call_count==0 且 question_id 一致）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
