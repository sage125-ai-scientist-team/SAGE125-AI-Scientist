"""
app.multimodal —— T06 多模态处理包（Wave A / PR-A 最小骨架）。

PR-A 仅提供模态识别、处理队列与适配器抽象；真实 PDF/CSV 提取留待 PR-B。
"""

from app.multimodal.detect import detect_modality
from app.multimodal.queue import MultimodalQueue, QueueRejection
from app.multimodal.summary import build_consumer_summary

__all__ = [
    "detect_modality",
    "MultimodalQueue",
    "QueueRejection",
    "build_consumer_summary",
]
