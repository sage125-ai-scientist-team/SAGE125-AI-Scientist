#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/bootstrap_preview_data.py — Preview / 本地演示题库引导脚本。

用途：
    为 Render Preview 与本地无 booklet 场景准备 `data/processed/questions_125.json`，
    使 STEP 01–08 的 Mock 链路可以选题并运行，而不是 Questions=0 静默卡死。

优先级：
    1. 若已有合法 `questions_125.json`（默认 125 条）→ 复用，不覆盖；
    2. 若存在 `data/raw/sjtu-booklet.pdf` → 调用正式抽取脚本；
    3. 仅当显式 `--allow-seed` 或环境变量 `SAGE125_PREVIEW_SEED=1` →
       写入带 `preview_seed` 标记的演示题库（不得冒充正式 booklet 抽取结果）。

反造假：
    - 种子题库每条都带 `preview_seed=true` / `label_tier=preview_seed`；
    - 未知题目标题带 `[PREVIEW-SEED]` 前缀，摘录声明非 booklet 原文；
    - 已知 demo 题（质数 / pandemic / climate / creativity / quantum 等）使用仓库内
      已核对过的公开题面，便于侧栏 Demo Presets 命中。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 允许 `python scripts/bootstrap_preview_data.py` 直接导入 app / scripts 包。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import get_logger

logger = get_logger("scripts.bootstrap_preview_data")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = PROJECT_ROOT / "data" / "raw" / "sjtu-booklet.pdf"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
JSON_PATH = PROCESSED_DIR / "questions_125.json"
SEED_MARKER = "preview_seed"

# 与 extract_125_questions.EXPECTED_DOMAIN_COUNTS 保持一致，保证领域图可展示。
EXPECTED_DOMAIN_COUNTS = {
    "Mathematical Sciences": 3,
    "Chemistry": 9,
    "Medicine & Health": 10,
    "Biology": 23,
    "Astronomy": 23,
    "Physics": 18,
    "Engineering & Materials Science": 4,
    "Information Science": 4,
    "Neuroscience": 12,
    "Ecology": 8,
    "Energy Science": 3,
    "Artificial Intelligence": 8,
}

# Demo Presets / 回归测试依赖的已知题面（仓库内已出现，非模型编造结论）。
_KNOWN_DEMO_QUESTIONS: list[dict] = [
    {
        "id": "Q001",
        "domain": "Mathematical Sciences",
        "question": "What makes prime numbers so special?",
        "source_page": 7,
        "booklet_excerpt": (
            "Preview seed for Demo Preset「Prime Numbers」. "
            "Replace with booklet extract when sjtu-booklet.pdf is available."
        ),
    },
    {
        "id": "Q004",
        "domain": "Mathematical Sciences",
        "question": "Is the Riemann hypothesis true?",
        "source_page": 7,
        "booklet_excerpt": (
            "Riemann zeta function and the distribution of primes "
            "(canonical layout item reused for preview seed)."
        ),
    },
    {
        "id": "Q010",
        "domain": "Medicine & Health",
        "question": "Can we predict the next pandemic?",
        "source_page": 11,
        "booklet_excerpt": (
            "Preview seed for Demo Preset「Pandemic Prediction」. "
            "Not a formal booklet extraction artifact."
        ),
    },
    {
        "id": "Q018",
        "domain": "Medicine & Health",
        "question": "How will the next generation of vaccines be made?",
        "source_page": 12,
        "booklet_excerpt": (
            "Next-generation vaccine platforms accelerate vaccine development "
            "(canonical layout item reused for preview seed)."
        ),
    },
    {
        "id": "Q019",
        "domain": "Medicine & Health",
        "question": (
            "Is there a scientific basis to the Meridian System in traditional Chinese medicine?"
        ),
        "source_page": 12,
        "booklet_excerpt": (
            "Meridian / acupuncture discussion "
            "(canonical layout item reused for preview seed)."
        ),
    },
    {
        "id": "Q040",
        "domain": "Ecology",
        "question": "How will climate change reshape ecological systems?",
        "source_page": 30,
        "booklet_excerpt": (
            "Preview seed for Demo Preset「Climate Change」. "
            "Title is marked for UI routing only; not booklet-verified prose."
        ),
    },
    {
        "id": "Q121",
        "domain": "Artificial Intelligence",
        "question": "Will artificial intelligence replace humans?",
        "source_page": 41,
        "booklet_excerpt": (
            "AI uncertainty / equivocality "
            "(canonical layout item reused for preview seed)."
        ),
    },
    {
        "id": "Q122",
        "domain": "Artificial Intelligence",
        "question": "Could we integrate with computers to form a human–machine hybrid species?",
        "source_page": 42,
        "booklet_excerpt": (
            "Human–machine hybrids / exoskeletons "
            "(canonical layout item reused for preview seed)."
        ),
    },
    {
        "id": "Q123",
        "domain": "Artificial Intelligence",
        "question": "Can quantum artificial intelligence imitate the human brain?",
        "source_page": 42,
        "booklet_excerpt": (
            "Preview seed covering quantum + AI keywords for Demo Preset「Quantum Computing」."
        ),
    },
    {
        "id": "Q124",
        "domain": "Artificial Intelligence",
        "question": "Can artificial intelligence exhibit genuine creativity?",
        "source_page": 42,
        "booklet_excerpt": (
            "Preview seed for Demo Preset「AI Creativity」. "
            "Replace with booklet extract for formal evaluation."
        ),
    },
]


def _truthy_env(*names: str) -> bool:
    """
    判断任一环境变量是否为显式真值。

    参数：
        names: 环境变量名列表。

    返回：
        任一变量取值为 1/true/yes/on（大小写不敏感）时返回 True。
    """
    for name in names:
        if os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}:
            return True
    return False


def _preview_runtime() -> bool:
    """
    判断当前是否为托管 Preview 运行时。

    返回：
        当 `APP_ENV=preview` 或 `PREVIEW_EPHEMERAL_STORAGE` 为真时返回 True。
        用于 Render 已有服务未同步新 env 时仍能自动引导题库。
    """
    app_env = os.getenv("APP_ENV", "").strip().lower()
    return app_env == "preview" or _truthy_env("PREVIEW_EPHEMERAL_STORAGE")


def _seed_allowed(cli_allow: bool) -> bool:
    """
    判断当前是否允许写入 preview seed。

    参数：
        cli_allow: 命令行是否传入 `--allow-seed`。

    返回：
        True 表示允许生成/覆盖为种子题库；False 表示必须依赖正式抽取。
    """
    return cli_allow or _truthy_env("SAGE125_PREVIEW_SEED") or _preview_runtime()


def _existing_questions_ok(min_count: int = 1) -> bool:
    """
    检查已有 questions_125.json 是否可直接复用。

    参数：
        min_count: 最少题目数量；Preview 至少 1，正式环境期望 125。

    返回：
        True 表示文件存在且可解析为非空列表。
    """
    if not JSON_PATH.exists():
        return False
    try:
        items = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(items, list) and len(items) >= min_count


def _try_extract_from_booklet() -> bool:
    """
    尝试调用正式抽取脚本生成题库。

    返回：
        True 表示抽取成功且输出文件可用；False 表示 PDF 缺失或抽取失败。
    """
    if not PDF_PATH.exists():
        logger.warning("缺少 booklet PDF：%s", PDF_PATH)
        return False
    try:
        import scripts.extract_125_questions as extractor
    except Exception as exc:  # noqa: BLE001 — bootstrap 需吞并导入失败并回退
        logger.error("无法导入 extract_125_questions：%s", exc)
        return False
    code = int(extractor.main() or 0)
    ok = code == 0 and _existing_questions_ok(125)
    if ok:
        logger.info("已通过正式抽取生成 %s", JSON_PATH)
    else:
        logger.error("正式抽取未成功（exit=%s）", code)
    return ok


def _placeholder_question(qid: str, domain: str, ordinal: int) -> dict:
    """
    构造一条显式标记的 Preview 占位问题。

    参数：
        qid: 问题 ID，如 Q002。
        domain: 标准领域名。
        ordinal: 领域内序号，仅用于可读标题。

    返回：
        可被前端/pipeline 消费的问题 dict（含 preview_seed 标记）。
    """
    return {
        "id": qid,
        "domain": domain,
        "question": f"[PREVIEW-SEED] {domain} placeholder question {ordinal:02d}?",
        "source_page": 0,
        "booklet_excerpt": (
            "Synthetic preview placeholder. Not extracted from sjtu-booklet.pdf. "
            "Do not treat as booklet gold or formal evaluation evidence."
        ),
        "preview_seed": True,
        "label_tier": SEED_MARKER,
        "provisional": True,
    }


def _annotate_known(item: dict) -> dict:
    """
    为已知 demo 题补充 preview 标记字段。

    参数：
        item: 已知题面 dict。

    返回：
        带 preview_seed / label_tier / provisional 的新 dict。
    """
    out = dict(item)
    out["preview_seed"] = True
    out["label_tier"] = SEED_MARKER
    out["provisional"] = True
    return out


def build_preview_seed_questions(total: int = 125) -> list[dict]:
    """
    构建 125 条 Preview 种子题库（领域分布对齐正式抽取期望）。

    参数：
        total: 目标题量，默认 125。

    返回：
        按 Q001..Q{total} 排序的问题列表。

    说明：
        - 先放入已知 demo / canonical 题面；
        - 再按 EXPECTED_DOMAIN_COUNTS 填充占位题；
        - 若计数仍不足，用 Artificial Intelligence 占位补齐。
    """
    by_id: dict[str, dict] = {}
    for known in _KNOWN_DEMO_QUESTIONS:
        by_id[str(known["id"])] = _annotate_known(known)

    domain_counts = {domain: 0 for domain in EXPECTED_DOMAIN_COUNTS}
    for item in by_id.values():
        domain = item.get("domain")
        if domain in domain_counts:
            domain_counts[domain] += 1

    next_num = 1

    def _alloc_id() -> str:
        """分配下一个尚未占用的 Q 编号。"""
        nonlocal next_num
        while f"Q{next_num:03d}" in by_id:
            next_num += 1
        qid = f"Q{next_num:03d}"
        next_num += 1
        return qid

    for domain, need in EXPECTED_DOMAIN_COUNTS.items():
        ordinal = 1
        while domain_counts[domain] < need and len(by_id) < total:
            qid = _alloc_id()
            by_id[qid] = _placeholder_question(qid, domain, ordinal)
            domain_counts[domain] += 1
            ordinal += 1

    while len(by_id) < total:
        qid = _alloc_id()
        by_id[qid] = _placeholder_question(qid, "Artificial Intelligence", len(by_id) + 1)

    ordered = [by_id[f"Q{i:03d}"] for i in range(1, total + 1) if f"Q{i:03d}" in by_id]
    # 若编号不连续，按数字序兜底，保证前端下拉稳定。
    if len(ordered) != total:
        ordered = [by_id[k] for k in sorted(by_id.keys(), key=lambda x: int(x[1:]))]
    return ordered[:total]


def write_preview_seed(force: bool = False) -> Path:
    """
    将 Preview 种子题库写入 `data/processed/questions_125.json`。

    参数：
        force: True 时即使已有题库也覆盖为 seed（仅 Preview 排障使用）。

    返回：
        写入后的 JSON 路径。
    """
    if _existing_questions_ok(125) and not force:
        logger.info("已存在题库，跳过 seed 写入：%s", JSON_PATH)
        return JSON_PATH
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    items = build_preview_seed_questions(125)
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    JSON_PATH.write_text(payload + "\n", encoding="utf-8")
    logger.info("已写入 preview seed：%s（count=%s）", JSON_PATH, len(items))
    return JSON_PATH


def bootstrap(*, allow_seed: bool = False, force_seed: bool = False) -> int:
    """
    执行 Preview 数据引导主流程。

    参数：
        allow_seed: 是否允许在无 PDF 时写入 preview seed。
        force_seed: 是否强制覆盖为 seed。

    返回：
        进程退出码：0 成功；2 无法准备题库。
    """
    if force_seed:
        if not _seed_allowed(allow_seed):
            print("错误：--force-seed 需要同时提供 --allow-seed 或 SAGE125_PREVIEW_SEED=1")
            return 2
        write_preview_seed(force=True)
        return 0

    if _existing_questions_ok(125):
        print(f"OK: 复用已有题库 {JSON_PATH}")
        return 0

    if PDF_PATH.exists() and _try_extract_from_booklet():
        print(f"OK: 已从 booklet 抽取 {JSON_PATH}")
        return 0

    if _seed_allowed(allow_seed):
        write_preview_seed(force=False)
        print(
            f"OK: 已写入 preview seed {JSON_PATH} "
            f"（SAGE125_PREVIEW_SEED / --allow-seed；非正式 booklet 抽取）"
        )
        return 0

    print(
        "错误：无法准备 questions_125.json。\n"
        "可选修复：\n"
        "  1) 放置 data/raw/sjtu-booklet.pdf 后运行 py -3 scripts/extract_125_questions.py\n"
        "  2) Preview：py -3 scripts/bootstrap_preview_data.py --allow-seed\n"
        "  3) 或设置环境变量 SAGE125_PREVIEW_SEED=1 后重跑本脚本"
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    """
    CLI 入口：解析参数并执行 bootstrap。

    参数：
        argv: 可选参数列表；默认读取 sys.argv[1:]。

    返回：
        进程退出码。
    """
    parser = argparse.ArgumentParser(description="Bootstrap preview questions_125.json")
    parser.add_argument(
        "--allow-seed",
        action="store_true",
        help="无 booklet 时允许写入带 preview_seed 标记的演示题库",
    )
    parser.add_argument(
        "--force-seed",
        action="store_true",
        help="强制覆盖为 preview seed（需同时 --allow-seed 或环境变量）",
    )
    args = parser.parse_args(argv)
    return bootstrap(allow_seed=args.allow_seed, force_seed=args.force_seed)


if __name__ == "__main__":
    raise SystemExit(main())
