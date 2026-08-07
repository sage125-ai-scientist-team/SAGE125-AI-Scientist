"""
app.multimodal —— T06 多模态处理包（Wave B / PR-B）。
"""

from app.multimodal.adapters import (
    ChartAdapter,
    MultimodalAdapter,
    QwenVisionAdapter,
    TableAdapter,
    TimeseriesAdapter,
    get_adapter,
)
from app.multimodal.detect import detect_modality
from app.multimodal.queue import MultimodalQueue, QueueRejection
from app.multimodal.summary import build_consumer_summary

__all__ = [
    "detect_modality",
    "MultimodalQueue",
    "QueueRejection",
    "build_consumer_summary",
    "MultimodalAdapter",
    "TableAdapter",
    "ChartAdapter",
    "TimeseriesAdapter",
    "QwenVisionAdapter",
    "get_adapter",
]
