"""
app.workflow.state —— 工作流状态。

流水线共享状态的权威定义位于 app.core.schemas.PipelineState。
本模块从 schemas 重新导出 PipelineState，作为 workflow 包内的稳定引用点。
"""

from __future__ import annotations

from app.core.schemas import PipelineState

# 对外导出的符号：workflow 内部统一引用 PipelineState。
__all__ = ["PipelineState"]
