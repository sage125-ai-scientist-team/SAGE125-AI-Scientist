"""
适配器抽象骨架（PR-A）：定义处理接口，不实现真实 PDF/CSV/视觉提取。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from app.contracts.multimodal import MultimodalArtifact, Modality


class MultimodalAdapter(ABC):
    """多模态适配器抽象基类。"""

    modality: Modality

    @abstractmethod
    def process(self, source_path: str) -> MultimodalArtifact:
        """将输入处理为通过契约校验的 MultimodalArtifact。"""


class QwenVisionAdapter(MultimodalAdapter):
    """
    Qwen 视觉适配器抽象（PR-A 不调用云端）。

    真实调用与审计落地属于 PR-B。
    """

    modality: Modality = "chart"

    def process(self, source_path: str) -> MultimodalArtifact:
        raise NotImplementedError(
            "QwenVisionAdapter.process is not implemented in PR-A; "
            "Wave B will add audited vision calls without embedding secrets"
        )


class TableAdapter(MultimodalAdapter):
    """表格适配器骨架。"""

    modality: Modality = "table"

    def process(self, source_path: str) -> MultimodalArtifact:
        raise NotImplementedError(
            "TableAdapter.process is not implemented in PR-A (no PDF/table OCR yet)"
        )


class ChartAdapter(MultimodalAdapter):
    """图表适配器骨架。"""

    modality: Modality = "chart"

    def process(self, source_path: str) -> MultimodalArtifact:
        raise NotImplementedError(
            "ChartAdapter.process is not implemented in PR-A (no chart extraction yet)"
        )


class TimeseriesAdapter(MultimodalAdapter):
    """CSV/时序适配器骨架。"""

    modality: Modality = "timeseries"

    def process(self, source_path: str) -> MultimodalArtifact:
        raise NotImplementedError(
            "TimeseriesAdapter.process is not implemented in PR-A "
            "(no CSV cleaning algorithm yet)"
        )


def get_adapter(modality: Modality) -> MultimodalAdapter:
    """按模态返回对应骨架适配器；未知模态抛出 ValueError。"""
    mapping: dict[Modality, MultimodalAdapter] = {
        "table": TableAdapter(),
        "chart": ChartAdapter(),
        "timeseries": TimeseriesAdapter(),
    }
    if modality not in mapping:
        raise ValueError(f"unsupported modality for adapter: {modality!r}")
    return mapping[modality]
