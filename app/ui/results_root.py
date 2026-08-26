# -*- coding: utf-8 -*-
"""统一权威结果根目录解析。

首页、工作区、轻量索引与统计汇总必须读取同一 ``SAGE125_RESULTS_ROOT``。
解析顺序（不得用目录 mtime 猜测“最新”）：

1. 环境变量 / Settings.sage125_results_root；
2. ``data/ui/results_root_pointer.json`` 中显式声明的 path（由人工或发布流程写入）；
3. 否则判定为未配置，调用方必须展示“数据源未通过完整性校验”。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, get_settings
from app.ui.api_client import QUESTIONS_PATH

POINTER_PATH = PROJECT_ROOT / "data" / "ui" / "results_root_pointer.json"
EXPECTED_QUESTION_IDS = [f"Q{i:03d}" for i in range(1, 126)]


@dataclass(frozen=True)
class ResultsRootResolution:
    results_root: Path | None
    catalog_path: Path
    manifest_path: Path | None
    pointer_path: Path
    source: str
    intact: bool
    missing_question_ids: list[str] = field(default_factory=list)
    extra_question_ids: list[str] = field(default_factory=list)
    duplicate_question_ids: list[str] = field(default_factory=list)
    catalog_ids: list[str] = field(default_factory=list)
    error: str | None = None

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "results_root": str(self.results_root) if self.results_root else None,
            "catalog_path": str(self.catalog_path),
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "pointer_path": str(self.pointer_path),
            "source": self.source,
            "intact": self.intact,
            "missing_question_ids": list(self.missing_question_ids),
            "error": self.error,
        }


def _load_catalog_ids(catalog_path: Path) -> list[str]:
    if not catalog_path.exists():
        return []
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload if isinstance(payload, list) else payload.get("questions") or []
    ids: list[str] = []
    for item in items:
        if isinstance(item, dict):
            qid = str(item.get("id") or item.get("question_id") or "").strip().upper()
        else:
            qid = str(item).strip().upper()
        if qid:
            ids.append(qid)
    return ids


def _configured_root() -> tuple[Path | None, str]:
    settings = get_settings()
    env_value = (os.environ.get("SAGE125_RESULTS_ROOT") or settings.sage125_results_root or "").strip()
    if env_value:
        return Path(env_value), "SAGE125_RESULTS_ROOT"
    if POINTER_PATH.exists():
        try:
            pointer = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pointer = {}
        raw = str(pointer.get("path") or "").strip()
        if raw:
            return Path(raw), "results_root_pointer"
    return None, "unconfigured"


def resolve_results_root() -> ResultsRootResolution:
    catalog_path = QUESTIONS_PATH
    catalog_ids = _load_catalog_ids(catalog_path)
    seen: set[str] = set()
    duplicates: list[str] = []
    for qid in catalog_ids:
        if qid in seen and qid not in duplicates:
            duplicates.append(qid)
        seen.add(qid)
    catalog_missing = [qid for qid in EXPECTED_QUESTION_IDS if qid not in seen]
    catalog_extra = sorted(qid for qid in seen if qid not in set(EXPECTED_QUESTION_IDS))

    root, source = _configured_root()
    if root is None:
        return ResultsRootResolution(
            results_root=None,
            catalog_path=catalog_path,
            manifest_path=None,
            pointer_path=POINTER_PATH,
            source=source,
            intact=False,
            missing_question_ids=catalog_missing or EXPECTED_QUESTION_IDS[:],
            extra_question_ids=catalog_extra,
            duplicate_question_ids=duplicates,
            catalog_ids=catalog_ids,
            error="SAGE125_RESULTS_ROOT 未配置",
        )

    if not root.exists() or not root.is_dir():
        return ResultsRootResolution(
            results_root=root,
            catalog_path=catalog_path,
            manifest_path=root / "manifest.json" if root else None,
            pointer_path=POINTER_PATH,
            source=source,
            intact=False,
            missing_question_ids=EXPECTED_QUESTION_IDS[:],
            extra_question_ids=catalog_extra,
            duplicate_question_ids=duplicates,
            catalog_ids=catalog_ids,
            error="结果根目录不存在",
        )

    present = sorted(
        path.name.upper()
        for path in root.iterdir()
        if path.is_dir() and path.name.upper().startswith("Q") and len(path.name) == 4
    )
    present_set = set(present)
    missing = [qid for qid in EXPECTED_QUESTION_IDS if qid not in present_set]
    extra = [qid for qid in present if qid not in set(EXPECTED_QUESTION_IDS)]
    catalog_ok = (
        len(catalog_ids) == 125
        and not catalog_missing
        and not duplicates
        and set(catalog_ids) == set(EXPECTED_QUESTION_IDS)
    )
    intact = catalog_ok and not missing and not extra
    manifest = root / "manifest.json"
    if not manifest.exists():
        pkg = root / "package_manifest.json"
        if pkg.exists():
            manifest = pkg
    return ResultsRootResolution(
        results_root=root,
        catalog_path=catalog_path,
        manifest_path=manifest if manifest.exists() else None,
        pointer_path=POINTER_PATH,
        source=source,
        intact=intact,
        missing_question_ids=missing or catalog_missing,
        extra_question_ids=extra or catalog_extra,
        duplicate_question_ids=duplicates,
        catalog_ids=catalog_ids,
        error=None if intact else "数据源未通过完整性校验",
    )
