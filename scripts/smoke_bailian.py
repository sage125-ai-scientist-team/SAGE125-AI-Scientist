#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/smoke_bailian.py — 真实百炼联调 smoke 测试（不纳入默认 pytest）。

运行示例（PowerShell；Key 通过本地 .env 配置，勿在命令行传 Key）：
    py -3 scripts/smoke_bailian.py --chat
    py -3 scripts/smoke_bailian.py --embedding
    py -3 scripts/smoke_bailian.py --rerank
    py -3 scripts/smoke_bailian.py --deepresearch
    py -3 scripts/smoke_bailian.py --all --skip-deepresearch
    py -3 scripts/smoke_bailian.py --dry-run     # 不需真实 Key，仅配置检查

安全：不打印/保存完整 API Key（仅掩码）；不保存敏感响应内容；DeepResearch 仅短 topic。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保项目根在 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings, mask_secret
from app.core.logging import get_logger, setup_logging

# 模块级日志器。
logger = get_logger("scripts.smoke_bailian")

# 输出目录。
OUT_DIR = Path(__file__).resolve().parents[1] / "exports" / "smoke_bailian"


def _config_check(settings) -> dict:
    """检查百炼配置是否齐备（不含占位符），返回检查结果。"""
    placeholder = "你的WorkspaceId"
    return {
        "dashscope_api_key": bool(settings.dashscope_api_key),
        "workspace_id": bool(settings.workspace_id),
        "base_url_ok": bool(settings.dashscope_base_url) and placeholder not in settings.dashscope_base_url,
        "deep_research_base_url_ok": bool(settings.dashscope_deep_research_base_url) and placeholder not in settings.dashscope_deep_research_base_url,
        "models_are_qwen": all(
            m.lower().startswith("qwen") or m in ("text-embedding-v4", "qwen3-rerank")
            for m in [settings.qwen_balanced_model, settings.qwen_deep_research_model,
                      settings.bailian_embedding_model, settings.bailian_rerank_model]
        ),
    }


def _smoke_chat(settings) -> dict:
    """Chat smoke：调用 qwen3.7-plus 返回可解析 JSON。"""
    from app.clients.qwen_chat_client import QwenChatClient

    try:
        client = QwenChatClient(settings)
        data = client.chat_json(
            [{"role": "user", "content": "Return a JSON object with keys status and model_family. Do not include secrets."}],
            model=settings.qwen_balanced_model,
        )
        ok = isinstance(data, dict)
        # 记录脱敏 request_id 与 usage，佐证真实调用。
        rid = getattr(client, "last_request_id", None)
        usage = getattr(client, "last_usage", {}) or {}
        return {
            "ok": ok,
            "detail": "chat_json 返回可解析 JSON" if ok else "返回非 dict",
            "request_id_masked": (str(rid)[:8] + "***") if rid else None,
            "usage": usage,
        }
    except Exception as exc:
        return {"ok": False, "detail": f"chat 失败：{exc}"}


def _smoke_embedding(settings) -> dict:
    """Embedding smoke：调用 text-embedding-v4，检查维度（不打印向量）。"""
    from app.clients.embedding_client import EmbeddingClient

    try:
        vecs = EmbeddingClient(settings).embed_texts(["zoonotic spillover", "land use change"])
        dims = {len(v) for v in vecs}
        ok = len(vecs) == 2 and len(dims) == 1 and next(iter(dims)) > 0
        return {"ok": ok, "detail": f"dimension={next(iter(dims)) if dims else 0}"}
    except Exception as exc:
        return {"ok": False, "detail": f"embedding 失败：{exc}"}


def _smoke_rerank(settings) -> dict:
    """Rerank smoke：调用 qwen3-rerank 对 3 条文档排序。"""
    from app.clients.rerank_client import RerankClient

    try:
        client = RerankClient(settings)
        docs = ["zoonotic spillover prediction models", "quantum computing basics", "pandemic surveillance systems"]
        ranked = client.rerank("zoonotic spillover pandemic prediction", docs, top_k=3)
        if client.last_used_fallback:
            return {"ok": False, "detail": "TODO_REQUIRES_BAILIAN_API_TEST：rerank 走了 fallback，未确认真实成功。"}
        return {"ok": bool(ranked), "detail": f"ranked_indices={[i for i, _ in ranked]}"}
    except Exception as exc:
        return {"ok": False, "detail": f"rerank 失败：{exc}"}


def _smoke_deepresearch(settings) -> dict:
    """DeepResearch smoke：短 topic，stream=True，失败不影响其它。"""
    from app.clients.qwen_deep_research_client import QwenDeepResearchClient

    try:
        result = QwenDeepResearchClient(settings).run_deep_research("One Health 与人畜共患病监测的简要概述")
        ok = result.get("status") == "succeeded"
        return {"ok": ok, "detail": f"status={result.get('status')}, phases={result.get('phases', [])[:3]}"}
    except Exception as exc:
        return {"ok": False, "detail": f"deepresearch 失败：{exc}"}


def main() -> int:
    """smoke 主入口：解析参数 -> 配置检查 -> 按需 smoke -> 写脱敏报告。"""
    parser = argparse.ArgumentParser(description="百炼真实联调 smoke")
    parser.add_argument("--chat", action="store_true")
    parser.add_argument("--embedding", action="store_true")
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--deepresearch", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--skip-deepresearch", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="不调用真实 API，仅配置检查")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)
    cfg = _config_check(settings)

    # 决定要跑哪些 smoke。
    run_chat = args.chat or args.all
    run_embedding = args.embedding or args.all
    run_rerank = args.rerank or args.all
    run_deep = args.deepresearch or (args.all and not args.skip_deepresearch)

    report: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "config_check": cfg,
        "models": {
            "balanced": settings.qwen_balanced_model, "embedding": settings.bailian_embedding_model,
            "rerank": settings.bailian_rerank_model, "deep_research": settings.qwen_deep_research_model,
        },
        "dashscope_api_key_masked": mask_secret(settings.dashscope_api_key),
        "base_url_masked": (settings.dashscope_base_url.split(".")[0] + ".***" if settings.dashscope_base_url else "未配置"),
        "chat": {"ok": None, "detail": "skipped"},
        "embedding": {"ok": None, "detail": "skipped"},
        "rerank": {"ok": None, "detail": "skipped"},
        "deepresearch": {"ok": None, "detail": "skipped"},
        "warnings": [],
        "errors": [],
    }

    if args.dry_run:
        # dry-run：只做配置检查，不发起真实调用。
        report["warnings"].append("dry-run 模式：未调用真实 API。")
        if not cfg["dashscope_api_key"]:
            report["warnings"].append("未配置 DASHSCOPE_API_KEY，真实 smoke 将失败。")
    else:
        # 真实 smoke 前置：无 Key 直接提示。
        if not cfg["dashscope_api_key"] or not cfg["base_url_ok"]:
            report["errors"].append("百炼未正确配置（缺少 Key 或 base_url 含占位符），请先运行 python scripts/setup_env.py。")
        else:
            if run_chat:
                report["chat"] = _smoke_chat(settings)
            if run_embedding:
                report["embedding"] = _smoke_embedding(settings)
            if run_rerank:
                report["rerank"] = _smoke_rerank(settings)
            if run_deep:
                report["deepresearch"] = _smoke_deepresearch(settings)
            elif args.all and args.skip_deepresearch:
                report["deepresearch"]["detail"] = "skipped (--skip-deepresearch)"

    # 真实 smoke 中，任何用户明确请求的能力失败都必须计入 errors，
    # 未选择能力的 ok=None（以及 --skip-deepresearch）不算失败。
    requested = {
        "chat": run_chat,
        "embedding": run_embedding,
        "rerank": run_rerank,
        "deepresearch": run_deep,
    }
    failed: list[str] = []
    if not args.dry_run:
        if not any(requested.values()):
            report["errors"].append("未选择真实 smoke 能力；请指定 --chat、--embedding、--rerank、--deepresearch 或 --all。")
        elif not report["errors"]:
            failed = [name for name, selected in requested.items() if selected and report[name].get("ok") is not True]
            if failed:
                report["errors"].append("真实 smoke 失败：" + "、".join(failed))

    # 写报告（脱敏）。
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "smoke_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# 百炼 Smoke 报告\n",
        f"- 时间：{report['timestamp']}",
        f"- dry_run：{report['dry_run']}",
        f"- Key：{report['dashscope_api_key_masked']}",
        f"- chat：{report['chat']}",
        f"- embedding：{report['embedding']}",
        f"- rerank：{report['rerank']}",
        f"- deepresearch：{report['deepresearch']}",
    ]
    if report["warnings"]:
        md.append("- warnings：" + "; ".join(report["warnings"]))
    if report["errors"]:
        md.append("- errors：" + "; ".join(report["errors"]))
    (OUT_DIR / "smoke_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"smoke 报告已写入：{OUT_DIR}")
    print(f"chat={report['chat']['ok']} embedding={report['embedding']['ok']} rerank={report['rerank']['ok']} deepresearch={report['deepresearch']['ok']}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
