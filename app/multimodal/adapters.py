"""
适配器实现（Wave B / PR-B）：Table / Chart / Timeseries / Qwen（离线拒绝付费调用）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.contracts.multimodal import MultimodalArtifact, Modality
from app.multimodal.audit import run_vision_or_deny
from app.multimodal.chart_extract import extract_chart_artifact
from app.multimodal.errors import ExtractionError
from app.multimodal.table_extract import extract_table_artifact
from app.multimodal.timeseries_extract import extract_timeseries_artifact


class MultimodalAdapter(ABC):
    """多模态适配器抽象基类。"""

    modality: Modality

    @abstractmethod
    def process(self, source_path: str) -> MultimodalArtifact:
        """将输入处理为通过契约校验的 MultimodalArtifact。"""


class QwenVisionAdapter(MultimodalAdapter):
    """
    Qwen 视觉适配器。

    无付费授权时拒绝真实调用；可回退到本地 chart 包提取，并标记非 actual。
    """

    modality: Modality = "chart"
    last_audit = None

    def process(self, source_path: str) -> MultimodalArtifact:
        _payload, audit = run_vision_or_deny(source_path)
        self.last_audit = audit
        if audit.actual_external_call:
            raise ExtractionError("unexpected actual external vision call")
        # 离线：仅当输入是结构化 chart 包时提取；否则 fail-closed。
        try:
            artifact = extract_chart_artifact(source_path)
        except ExtractionError as exc:
            raise ExtractionError(
                f"QwenVisionAdapter denied paid call and offline chart "
                f"extract failed: {exc}"
            ) from exc
        # 视觉路径未 actual：若原 status 为 passed，降为 needs_review 以免冒充云端结果
        if artifact.validation_status == "passed":
            artifact = artifact.model_copy(
                update={"validation_status": "needs_review"}
            )
        return artifact


class TableAdapter(MultimodalAdapter):
    """表格适配器：页码/bbox/表头/单元格/合并单元/单位。"""

    modality: Modality = "table"

    def process(self, source_path: str) -> MultimodalArtifact:
        return extract_table_artifact(source_path)


class ChartAdapter(MultimodalAdapter):
    """图表适配器：轴/图例/系列值/置信度；缺图例或错误轴失败。"""

    modality: Modality = "chart"

    def process(self, source_path: str) -> MultimodalArtifact:
        return extract_chart_artifact(source_path)


class TimeseriesAdapter(MultimodalAdapter):
    """CSV/时序适配器：schema、时间索引、缺失/重复、受控单位转换。"""

    modality: Modality = "timeseries"
    last_cleaning_log = None

    def process(self, source_path: str) -> MultimodalArtifact:
        result = extract_timeseries_artifact(source_path)
        self.last_cleaning_log = result.cleaning_log
        return result.artifact


def get_adapter(modality: Modality) -> MultimodalAdapter:
    """按模态返回适配器；未知模态抛出 ValueError。"""
    mapping: dict[Modality, MultimodalAdapter] = {
        "table": TableAdapter(),
        "chart": ChartAdapter(),
        "timeseries": TimeseriesAdapter(),
    }
    if modality not in mapping:
        raise ValueError(f"unsupported modality for adapter: {modality!r}")
    return mapping[modality]
