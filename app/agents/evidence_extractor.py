"""
app.agents.evidence_extractor —— 证据抽取智能体。

从合并后的 EvidenceCards 中抽取 established_facts / disputed_points /
knowledge_gaps / possible_datasets / methodological_constraints，
每条事实必须绑定 evidence_ids。模型：settings.qwen_balanced_model。
"""

from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.prompts import EVIDENCE_EXTRACTOR_PROMPT
from app.core.agent_schemas import EvidenceExtractionResult
from app.core.config import Settings
from app.workflow import mock_outputs


class EvidenceExtractorAgent(BaseAgent):
    """抽取并核验证据、区分 source/target 数据集的智能体。"""

    # 阶段名与输出 schema。
    name = "evidence_extractor"
    output_schema = EvidenceExtractionResult

    def __init__(self, settings: Optional[Settings] = None, chat_client=None) -> None:
        """初始化并绑定均衡模型与专用 prompt。"""
        super().__init__(settings, chat_client)
        self.model_name = self.settings.qwen_balanced_model
        self.system_prompt = EVIDENCE_EXTRACTOR_PROMPT

    def build_mock(self, input_data: dict, state) -> dict:
        """返回 mock EvidenceExtractionResult（事实绑定现有证据 ID）。"""
        # 兼容 EvidenceCard 对象与 dict，收集现有证据 ID，保证事实可追溯。
        evidence_ids: list[str] = []
        for e in state.retrieved_evidence:
            eid = getattr(e, "id", None) if not isinstance(e, dict) else e.get("id")
            if eid:
                evidence_ids.append(eid)
        return mock_outputs.get_mock(
            "evidence_extraction", input_data.get("question_item", {}), evidence_ids
        )
