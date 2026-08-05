"""
T01 黄金集加载器 — Wave B（08/01 扩展）。

从 ``docs/modules/T01/evidence_gold_set.json`` 读取可机器校验的
provisional 事实—证据对；不把 Markdown 散文当作唯一真源。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 仓库内黄金集 JSON 默认路径（相对项目根可由调用方覆盖）。
DEFAULT_GOLD_SET_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "modules"
    / "T01"
    / "evidence_gold_set.json"
)


def load_evidence_gold_set(
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    加载黄金集 JSON，校验最小字段齐全。

    参数：
        path: JSON 路径；默认 ``docs/modules/T01/evidence_gold_set.json``。

    返回：
        pair 字典列表。

    异常：
        FileNotFoundError / ValueError: 文件缺失或字段不完整。
    """
    target = path or DEFAULT_GOLD_SET_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    pairs = raw.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("gold set must contain non-empty pairs list")

    required = {
        "claim_id",
        "claim",
        "evidence_id",
        "source_id",
        "source_type",
        "quote",
        "locator",
        "relation",
        "validation_status",
    }
    for index, pair in enumerate(pairs):
        missing = required - set(pair.keys())
        if missing:
            raise ValueError(
                f"gold pair[{index}] missing fields: {sorted(missing)}"
            )
        if not isinstance(pair.get("locator"), dict) or not pair["locator"]:
            raise ValueError(f"gold pair[{index}] locator must be non-empty dict")
        if not str(pair.get("quote", "")).strip():
            raise ValueError(f"gold pair[{index}] quote must be non-empty")
    return pairs


def gold_set_count(path: Path | None = None) -> int:
    """
    返回黄金集条目数。

    参数：
        path: 可选 JSON 路径。

    返回：
        整数条数。
    """
    return len(load_evidence_gold_set(path))
