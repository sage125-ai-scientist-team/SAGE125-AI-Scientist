"""
app.agents.schema_validator —— 输出校验智能体。

对最终 ResearchPlan 做结构与真实性校验，产出 ValidationResult，并给出保守的
validation_status。模型：settings.qwen_fast_model（默认 qwen3.6-flash）。

说明：真正的判定以 pipeline 中的 quality_gates 为准（更保守者优先）；本 Agent
的 LLM/mock 输出作为补充说明。
"""

from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.prompts import SCHEMA_VALIDATOR_PROMPT
from app.core.agent_schemas import ValidationResult
from app.core.config import Settings
from app.workflow import mock_outputs


class SchemaValidatorAgent(BaseAgent):
    """校验最终输出契约与反造假约束的智能体。"""

    # 阶段名与输出 schema。
    name = "schema_validator"
    output_schema = ValidationResult

    def __init__(self, settings: Optional[Settings] = None, chat_client=None) -> None:
        """初始化并绑定快速模型与专用 prompt。"""
        super().__init__(settings, chat_client)
        self.model_name = self.settings.qwen_fast_model
        self.system_prompt = SCHEMA_VALIDATOR_PROMPT

    def build_mock(self, input_data: dict, state) -> dict:
        """返回 mock ValidationResult。"""
        return mock_outputs.get_mock("validation", input_data.get("question_item", {}))
