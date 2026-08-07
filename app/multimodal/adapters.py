"""适配器：表格/图表/时序 + 真实视觉路径（Qwen VL schema → MultimodalArtifact）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.contracts.multimodal import MultimodalArtifact, Modality
from app.multimodal.chart_extract import (
    extract_chart_artifact,
    extract_chart_from_packet,
    extract_chart_from_preprocessed_pdf_directives,
)
from app.multimodal.errors import ExtractionError
from app.multimodal.qwen_vision import run_qwen_vision
from app.multimodal.table_extract import extract_table_artifact
from app.multimodal.timeseries_extract import extract_timeseries_artifact


class MultimodalAdapter(ABC):
    modality: Modality

    @abstractmethod
    def process(self, source_path: str) -> MultimodalArtifact:
        raise NotImplementedError


class QwenVisionAdapter(MultimodalAdapter):
    """
    真实视觉路径入口。

    - 成功解析的 VL JSON → MultimodalArtifact（不得丢弃再回退文本指令 parser）
    - 无授权/失败时：栅格图 fail-closed；PDF 仅允许降级的 preprocessed 文本指令路径
    """

    modality: Modality = "chart"
    last_audit = None
    last_call_meta = None

    def process(
        self,
        source_path: str,
        *,
        allow_actual: bool = False,
        page: int = 1,
        mock_response_json: str | None = None,
        simulate_error: str | None = None,
    ) -> MultimodalArtifact:
        meta, audit = run_qwen_vision(
            source_path,
            page=page,
            allow_actual=allow_actual,
            mock_response_json=mock_response_json,
            simulate_error=simulate_error,
        )
        self.last_audit = audit
        self.last_call_meta = meta

        if meta.get("artifact") is not None:
            # Never discard a successfully schema-validated vision artifact.
            return MultimodalArtifact.model_validate(meta["artifact"])

        if audit.status == "success":
            raise ExtractionError("vision reported success but artifact missing")

        suffix = Path(source_path).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ExtractionError(
                "raster chart requires successful vision parse; "
                "no silent fallback to text-directive parser"
            )
        if suffix == ".pdf":
            # Explicit demotion: embedded LEGEND/AXIS/SERIES only.
            return extract_chart_from_preprocessed_pdf_directives(
                source_path, page=page
            )
        if suffix == ".json":
            art = extract_chart_from_packet(source_path)
            if art.validation_status == "passed":
                return art.model_copy(update={"validation_status": "needs_review"})
            return art
        raise ExtractionError(
            f"vision path did not yield artifact and no offline fallback for {suffix!r}"
        )


class TableAdapter(MultimodalAdapter):
    modality: Modality = "table"

    def process(self, source_path: str, **kwargs) -> MultimodalArtifact:
        return extract_table_artifact(source_path, **kwargs)


class ChartAdapter(MultimodalAdapter):
    modality: Modality = "chart"

    def process(self, source_path: str, **kwargs) -> MultimodalArtifact:
        return extract_chart_artifact(source_path, **kwargs)


class TimeseriesAdapter(MultimodalAdapter):
    modality: Modality = "timeseries"
    last_cleaning_log = None

    def process(self, source_path: str) -> MultimodalArtifact:
        result = extract_timeseries_artifact(source_path)
        self.last_cleaning_log = result.cleaning_log
        return result.artifact


def get_adapter(modality: Modality) -> MultimodalAdapter:
    mapping: dict[Modality, MultimodalAdapter] = {
        "table": TableAdapter(),
        "chart": ChartAdapter(),
        "timeseries": TimeseriesAdapter(),
    }
    if modality not in mapping:
        raise ValueError(f"unsupported modality for adapter: {modality!r}")
    return mapping[modality]
