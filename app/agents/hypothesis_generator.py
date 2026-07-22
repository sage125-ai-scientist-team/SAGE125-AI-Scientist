"""
app.agents.hypothesis_generator —— 假设生成智能体。

基于证据抽取结果生成 2-3 个可证伪的候选假设并推荐 1 个。
模型：settings.qwen_strong_model（默认 qwen3.7-max）。
"""

from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.prompts import HYPOTHESIS_GENERATOR_PROMPT
from app.core.agent_schemas import HypothesisGenerationResult
from app.core.config import Settings
from app.workflow import mock_outputs


class HypothesisGeneratorAgent(BaseAgent):
    """生成可证伪科学假设并评分的智能体。"""

    # 阶段名与输出 schema。
    name = "hypothesis_generator"
    output_schema = HypothesisGenerationResult

    def __init__(self, settings: Optional[Settings] = None, chat_client=None) -> None:
        """初始化并绑定强模型与专用 prompt。"""
        super().__init__(settings, chat_client)
        # 强模型：假设生成需要更强推理。
        self.model_name = self.settings.qwen_strong_model
        self.system_prompt = HYPOTHESIS_GENERATOR_PROMPT

    def build_mock(self, input_data: dict, state) -> dict:
        """返回 mock HypothesisGenerationResult（supporting evidence 绑定现有 ID）。"""
        # 复用现有证据 ID，保证支撑证据可追溯。
        evidence_ids: list[str] = []
        for e in state.retrieved_evidence:
            eid = getattr(e, "id", None) if not isinstance(e, dict) else e.get("id")
            if eid:
                evidence_ids.append(eid)
        return mock_outputs.get_mock(
            "hypothesis_generation", input_data.get("question_item", {}), evidence_ids
        )
