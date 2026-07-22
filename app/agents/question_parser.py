"""
app.agents.question_parser —— 问题解析智能体。

将 125 Questions 中的问题解析为结构化背景（领域/关键词/实体/问题类型/科学边界），
并标记疑似领域错配。模型：settings.qwen_fast_model（默认 qwen3.6-flash）。
"""

from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.prompts import QUESTION_PARSER_PROMPT
from app.core.agent_schemas import ParsedQuestionResult
from app.core.config import Settings
from app.workflow import mock_outputs


class QuestionParserAgent(BaseAgent):
    """解析科学问题为结构化背景的智能体。"""

    # 阶段名与输出 schema。
    name = "question_parser"
    output_schema = ParsedQuestionResult

    def __init__(self, settings: Optional[Settings] = None, chat_client=None) -> None:
        """初始化并绑定快速模型与专用 prompt。"""
        super().__init__(settings, chat_client)
        # 使用快速模型（成本低，任务简单）。
        self.model_name = self.settings.qwen_fast_model
        self.system_prompt = QUESTION_PARSER_PROMPT

    def build_mock(self, input_data: dict, state) -> dict:
        """返回 mock ParsedQuestionResult。"""
        # 以选中问题为上下文生成确定性解析。
        return mock_outputs.get_mock("parsed_question", input_data.get("question_item", {}))
