"""
安全审计字段约定（PR-A）：禁止记录密钥与完整 prompt。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class VisionCallAuditStub(BaseModel):
    """
    Qwen 视觉调用审计字段骨架（PR-A 仅定义字段，不发起真实调用）。

    约束与 app.core.call_audit 一致：永不保存 API Key / 全文 prompt。
    """

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(..., description="调用 ID")
    model_alias: str = Field(default="vision", description="模型档位别名")
    status: Literal["success", "failed", "skipped", "not_implemented"] = Field(
        default="not_implemented", description="状态"
    )
    input_summary: str = Field(
        default="",
        max_length=200,
        description="输入摘要（短文本，非全文）",
    )
    key_masked: bool = Field(default=True, description="Key 是否已脱敏（恒 True）")
    error_type: Optional[str] = Field(default=None, description="错误类型（脱敏）")

    def ensure_safe(self) -> "VisionCallAuditStub":
        """断言审计记录满足安全约束。"""
        if self.key_masked is not True:
            raise ValueError("vision audit key_masked must be True")
        lowered = self.input_summary.lower()
        for needle in ("api_key", "sk-", "secret", "password", "token="):
            if needle in lowered:
                raise ValueError(
                    f"vision audit input_summary must not contain sensitive marker {needle!r}"
                )
        return self
