"""T06 Wave B：适配器安全失败异常。"""

from __future__ import annotations


class ExtractionError(ValueError):
    """结构化提取失败；不得静默编造数值或单位。"""


class LowConfidenceDecision(RuntimeError):
    """低置信度需人工确认（非静默成功）。"""
