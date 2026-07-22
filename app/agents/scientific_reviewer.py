"""
app.agents.scientific_reviewer —— 科学评审智能体。

像严格评审专家一样挑错（可证伪性、证据落地、References 真实性、Results 是否造假、
是否可复现）。模型：settings.qwen_strong_model（默认 qwen3.7-max）。
"""

from __future__ import annotations

import json
import os
from typing import Optional

from app.agents.base import BaseAgent
from app.agents.prompts import SCIENTIFIC_REVIEWER_PROMPT
from app.core.agent_schemas import ReviewResult
from app.core.config import Settings
from app.workflow import mock_outputs


class ScientificReviewerAgent(BaseAgent):
    """多维度严格评审假设与实验设计的智能体。"""

    # 阶段名与输出 schema。
    name = "scientific_reviewer"
    output_schema = ReviewResult

    def __init__(self, settings: Optional[Settings] = None, chat_client=None) -> None:
        """初始化并绑定强模型与专用 prompt。"""
        super().__init__(settings, chat_client)
        # 强模型：评审需要严格推理。
        self.model_name = self.settings.qwen_strong_model
        self.system_prompt = SCIENTIFIC_REVIEWER_PROMPT

    def build_messages(self, input_data: dict) -> list[dict]:
        """
        构造 LLM 消息：传入假设、实验设计与证据，不传 question_item。

        参数：
            input_data: pipeline 组装的完整 Agent 输入。

        返回：
            OpenAI 风格消息列表。
        """
        payload = {
            "recommended_hypothesis": input_data.get("recommended_hypothesis") or {},
            "hypothesis_generation": input_data.get("hypothesis_generation") or {},
            "experiment_design": input_data.get("experiment_design") or {},
            "evidence_extraction": input_data.get("evidence_extraction") or {},
            "evidence_catalog": input_data.get("evidence_catalog") or [],
        }
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]

    def build_mock(self, input_data: dict, state) -> dict:
        """
        返回 mock ReviewResult。

        为便于测试“未通过 -> 自动修订 1 次 -> 通过”，当环境变量
        MOCK_REVIEW_FAIL=true 且尚未修订过（revision_history 为空）时返回 fail。
        """
        force_fail = os.getenv("MOCK_REVIEW_FAIL", "").strip().lower() in ("1", "true", "yes")
        # 仅在首轮返回 fail，第二轮（已修订）返回 pass，避免无限循环。
        if force_fail and not state.revision_history:
            return mock_outputs.get_mock("review_fail", input_data.get("question_item", {}))
        return mock_outputs.get_mock("review", input_data.get("question_item", {}))
