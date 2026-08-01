"""
模态识别骨架（PR-A）：按扩展名/清单提示识别，不冒充已完成视觉推理。
"""

from __future__ import annotations

from pathlib import Path

from app.contracts.multimodal import Modality

_EXTENSION_MAP: dict[str, Modality] = {
    ".csv": "timeseries",
    ".tsv": "timeseries",
    ".json": "table",
    ".pdf": "chart",
}


def detect_modality(source_path: str, hint: Modality | None = None) -> Modality:
    """
    识别输入模态。

    参数：
        source_path: 来源路径。
        hint: 可选显式提示；若提供则优先采用（仍须为受支持枚举）。

    返回：
        受支持的 Modality。

    异常：
        ValueError: 无法识别或不支持的扩展名。
    """
    if hint is not None:
        return hint
    suffix = Path(source_path).suffix.lower()
    if suffix not in _EXTENSION_MAP:
        raise ValueError(
            f"unsupported or unknown modality for extension {suffix!r} "
            f"(path={source_path!r}); provide an explicit hint"
        )
    return _EXTENSION_MAP[suffix]
