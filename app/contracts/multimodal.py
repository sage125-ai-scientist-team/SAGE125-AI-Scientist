"""
app.contracts.multimodal —— T06 多模态产物数据契约（Wave A / PR-A）。

定义下游（T01 / T02 / T07 / T08）可消费的 MultimodalArtifact 及嵌套结构。
本模块仅冻结 Schema 与摘要视图；解析适配器在 app.multimodal 中实现。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# 当前支持的科学模态。
Modality = Literal["table", "chart", "timeseries"]

# 产物校验状态：needs_review 表示需人工核验，不得冒充已通过。
ValidationStatus = Literal[
    "passed",
    "needs_review",
    "failed",
    "pending",
]

# 夹具/来源类型（PR-A 合成样例使用 synthetic_fixture）。
ProvenanceSourceType = Literal[
    "synthetic_fixture",
    "real_fixture",
    "pdf",
    "csv",
    "user_upload",
]


class BoundingBox(BaseModel):
    """页面或图像上的轴对齐包围盒（PDF 用户空间坐标）。"""

    model_config = ConfigDict(extra="forbid")

    x0: float = Field(..., description="左边界")
    y0: float = Field(..., description="下/上边界（依坐标系）")
    x1: float = Field(..., description="右边界")
    y1: float = Field(..., description="上/下边界（依坐标系）")


class Provenance(BaseModel):
    """产物溯源：文件路径、来源类型、页码与可选 bbox。"""

    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(..., min_length=1, description="来源文件或夹具路径")
    source_type: ProvenanceSourceType = Field(..., description="来源类型")
    page: int = Field(..., ge=1, description="来源页码（从 1 起）")
    bbox: Optional[BoundingBox] = Field(default=None, description="可选包围盒")

    @field_validator("source_path")
    @classmethod
    def _reject_blank_source_path(cls, value: str) -> str:
        """空白来源路径视为缺失，必须拒绝。"""
        stripped = value.strip()
        if not stripped:
            raise ValueError("provenance.source_path must be a non-empty path")
        return stripped


class AxisSpec(BaseModel):
    """坐标轴描述（图表模态使用；table 样例可为 None）。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="轴名称（如 x / y）")
    label: str = Field(default="", description="轴标签文本")
    unit: Optional[str] = Field(default=None, description="轴单位")
    min_value: Optional[float] = Field(default=None, description="轴最小值")
    max_value: Optional[float] = Field(default=None, description="轴最大值")


class ColumnUnitBinding(BaseModel):
    """列名到单位的显式映射（禁止引用不存在的列）。"""

    model_config = ConfigDict(extra="forbid")

    column: str = Field(..., min_length=1, description="表格列名")
    unit: str = Field(..., min_length=1, description="该列单位")


class TableData(BaseModel):
    """表格结构化数据：表头 + 单元格行（单元格以字符串保留原文）。"""

    model_config = ConfigDict(extra="forbid")

    headers: list[str] = Field(..., min_length=1, description="表头")
    rows: list[list[str]] = Field(default_factory=list, description="数据行")

    @model_validator(mode="after")
    def _reject_row_width_mismatch(self) -> "TableData":
        """每行单元格数量必须等于 headers 数量；不一致时拒绝，不自动补齐或截断。"""
        expected = len(self.headers)
        for row_index, row in enumerate(self.rows):
            actual = len(row)
            if actual != expected:
                raise ValueError(
                    f"row {row_index} width mismatch: expected {expected} columns, "
                    f"got {actual}"
                )
        return self

    @model_validator(mode="after")
    def _reject_duplicate_headers(self) -> "TableData":
        """完全相同的重复表头会产生列歧义，必须拒绝。"""
        seen: set[str] = set()
        for index, header in enumerate(self.headers):
            if header in seen:
                raise ValueError(
                    f"duplicate header at index {index}: {header!r} "
                    "(exact duplicate column names are ambiguous)"
                )
            seen.add(header)
        return self


class MultimodalArtifact(BaseModel):
    """
    多模态提取产物的冻结契约。

    Wave A / PR-A：支持完整 table/chart/timeseries 样例构造与 JSON 序列化，
    并对非法结构主动拒绝。
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., min_length=1, description="产物唯一 ID")
    modality: Modality = Field(..., description="模态类型")
    provenance: Provenance = Field(..., description="来源与定位信息")
    units: list[str] = Field(default_factory=list, description="单位列表（顺序提示）")
    column_units: list[ColumnUnitBinding] = Field(
        default_factory=list,
        description="列→单位显式映射；引用不存在的列时拒绝",
    )
    axes: Optional[list[AxisSpec]] = Field(
        default=None, description="坐标轴列表；表格可为 None"
    )
    legend: list[str] = Field(default_factory=list, description="图例项")
    data: TableData = Field(..., description="结构化数据数组")
    confidence: float = Field(..., ge=0.0, le=1.0, description="提取置信度 0-1")
    validation_status: ValidationStatus = Field(..., description="校验状态")

    @model_validator(mode="after")
    def _reject_column_unit_unknown_columns(self) -> "MultimodalArtifact":
        """单位映射只能引用 data.headers 中存在的列名。"""
        header_set = set(self.data.headers)
        for binding in self.column_units:
            if binding.column not in header_set:
                raise ValueError(
                    f"column_units references unknown column {binding.column!r}; "
                    f"known headers={list(self.data.headers)}"
                )
        return self


class MultimodalSummary(BaseModel):
    """
    下游可消费的瘦身摘要（T01 / T02 / T07 / T08）。

    故意不包含完整 data 行，避免大对象进入 prompt。
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., description="产物 ID")
    modality: Modality = Field(..., description="模态")
    source_path: str = Field(..., description="来源路径")
    source_type: ProvenanceSourceType = Field(..., description="来源类型")
    page: int = Field(..., description="页码")
    units: list[str] = Field(default_factory=list, description="单位列表")
    column_units: list[ColumnUnitBinding] = Field(
        default_factory=list, description="列单位映射"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    validation_status: ValidationStatus = Field(..., description="校验状态")
    header_count: int = Field(..., ge=0, description="表头列数")
    row_count: int = Field(..., ge=0, description="数据行数")


def to_consumer_summary(artifact: MultimodalArtifact) -> MultimodalSummary:
    """将完整产物转为下游摘要，保留来源、单位、置信度与校验状态。"""
    return MultimodalSummary(
        artifact_id=artifact.artifact_id,
        modality=artifact.modality,
        source_path=artifact.provenance.source_path,
        source_type=artifact.provenance.source_type,
        page=artifact.provenance.page,
        units=list(artifact.units),
        column_units=list(artifact.column_units),
        confidence=artifact.confidence,
        validation_status=artifact.validation_status,
        header_count=len(artifact.data.headers),
        row_count=len(artifact.data.rows),
    )
