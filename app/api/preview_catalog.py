"""T08 runtime question catalog for writable ``DATA_DIR``.

Render preview mounts a read-only repository tree. ``scripts.bootstrap_preview_data``
still writes ``<repo>/data/processed/questions_125.json`` by default, so
``GET /health`` reports ``questions_count=0`` even after a successful-looking
start. This module is the T08-owned resolver and writer: it prefers
``DATA_DIR/processed/questions_125.json`` and exports ``SAGE_QUESTIONS_PATH``.

It does not own booklet extraction, T07 isolation, or formal gold labels.
Preview rows stay marked ``preview_seed`` and must not be shown as booklet
extracts or T09 evaluation input.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger("api.preview_catalog")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_NAME = "questions_125.json"


def preview_seed_allowed() -> bool:
    """
    判断当前进程是否允许写入 preview seed。

    返回：
        任一预览开关为真时返回 True：``SAGE125_PREVIEW_SEED``、
        ``APP_ENV=preview``、``PREVIEW_EPHEMERAL_STORAGE``。
    """
    seed = os.getenv("SAGE125_PREVIEW_SEED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    app_env = os.getenv("APP_ENV", "").strip().lower() == "preview"
    ephemeral = os.getenv("PREVIEW_EPHEMERAL_STORAGE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return seed or app_env or ephemeral


def configured_data_dir() -> Path:
    """
    解析可写数据根。显式 ``DATA_DIR`` 优先于 settings 默认值。

    返回：
        绝对 ``Path``。相对路径相对仓库根展开。
    """
    explicit = os.getenv("DATA_DIR", "").strip()
    raw = explicit or str(getattr(get_settings(), "data_dir", "data"))
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def writable_catalog_path() -> Path:
    """
    返回 T08 应写入的题库路径：``DATA_DIR/processed/questions_125.json``。

    返回：
        尚未保证父目录存在的绝对路径。
    """
    return configured_data_dir() / "processed" / CATALOG_NAME


def repository_catalog_path() -> Path:
    """
    返回仓库内只读回退路径。

    返回：
        ``<repo>/data/processed/questions_125.json``。
    """
    return PROJECT_ROOT / "data" / "processed" / CATALOG_NAME


def resolve_runtime_questions_path() -> Path:
    """
    解析运行时题库路径，不创建文件。

    优先级：

    1. 已设置的 ``SAGE_QUESTIONS_PATH``；
    2. 已存在的 ``DATA_DIR`` 题库；
    3. 已存在的仓库题库（仅当未显式设置 ``DATA_DIR``）；
    4. 可写 ``DATA_DIR`` 目标（即使尚不存在）。

    返回：
        应读取或写入的绝对路径。
    """
    override = os.getenv("SAGE_QUESTIONS_PATH", "").strip()
    if override:
        return Path(override)
    writable = writable_catalog_path()
    if writable.exists():
        return writable
    repository = repository_catalog_path()
    if repository.exists() and not os.getenv("DATA_DIR", "").strip():
        return repository
    return writable


def catalog_is_usable(path: Path, *, expected: int = 125) -> bool:
    """
    检查路径是否包含可解析且数量正确的题库。

    参数：
        path: 候选 JSON 路径。
        expected: 期望条数，默认 125。

    返回：
        文件存在、可解析、长度为 ``expected`` 时为 True。
    """
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return False
    return isinstance(payload, list) and len(payload) == expected


def _export_questions_path(path: Path) -> None:
    """
    把运行时路径写入 ``SAGE_QUESTIONS_PATH``，供 pipeline 与后续请求复用。

    参数：
        path: 已确认或即将写入的题库路径。
    """
    os.environ["SAGE_QUESTIONS_PATH"] = str(path)


def _load_preview_seed_items() -> list[dict[str, Any]]:
    """
    复用已有 preview seed 生成器；失败时不编造题面。

    返回：
        带 ``preview_seed`` 标记的 125 条 dict。

    异常：
        RuntimeError: 生成器不可用或产物不合格。
    """
    try:
        from scripts.bootstrap_preview_data import build_preview_seed_questions
    except Exception as exc:  # noqa: BLE001 — 启动路径必须失败关闭
        raise RuntimeError("preview seed generator is unavailable") from exc
    items = build_preview_seed_questions(125)
    if not isinstance(items, list) or len(items) != 125:
        raise RuntimeError("preview seed generator returned an invalid catalog")
    if not all(item.get("preview_seed") is True for item in items):
        raise RuntimeError("preview seed generator omitted preview_seed marks")
    return items


def write_preview_catalog(path: Path) -> Path:
    """
    把带标记的 preview seed 写入可写 ``DATA_DIR`` 路径。

    参数：
        path: 目标 JSON 路径。

    返回：
        写入后的路径。

    异常：
        RuntimeError: 生成失败或写入失败。
    """
    items = _load_preview_seed_items()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("wrote preview_seed catalog count=%s", len(items))
    return path


def ensure_preview_catalog() -> Path | None:
    """
    在 API 启动时准备运行时题库。

    行为：

    - 已有合法题库：导出 ``SAGE_QUESTIONS_PATH`` 并返回该路径；
    - 预览开关打开且题库缺失：写入 ``DATA_DIR``，不写仓库树；
    - 非预览且缺失：返回 None，``/health`` 保持 ``questions_count=0``。

    返回：
        可用题库路径；无法准备时为 None。
    """
    current = resolve_runtime_questions_path()
    if catalog_is_usable(current):
        _export_questions_path(current)
        return current
    if not preview_seed_allowed():
        return None
    target = writable_catalog_path()
    try:
        write_preview_catalog(target)
    except Exception as exc:  # noqa: BLE001 — 启动不得因 seed 失败而崩溃
        logger.warning("preview catalog write failed: %s", type(exc).__name__)
        return None
    _export_questions_path(target)
    return target
