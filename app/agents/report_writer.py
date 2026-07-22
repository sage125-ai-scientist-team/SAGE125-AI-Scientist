"""
app.agents.report_writer —— 报告撰写智能体。

整合各阶段产物，产出 ResearchPlan 的“草稿 dict”，其中以 reference_ids 引用
EvidenceCards（由 pipeline 解析为真实证据），references 不允许 LLM 手写新文献。
模型：settings.qwen_balanced_model（默认 qwen3.7-plus）。

说明：output_schema=None，本 Agent 返回原始 dict，最终 ResearchPlan 由 pipeline
组装并校验（因 references 需绑定真实 EvidenceCards）。
"""

from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.prompts import REPORT_WRITER_PROMPT
from app.core.config import Settings
from app.workflow import mock_outputs


class ReportWriterAgent(BaseAgent):
    """整合各阶段产物为 ResearchPlan 草稿（含 reference_ids）的智能体。"""

    # 阶段名；output_schema=None 表示由 pipeline 组装最终 ResearchPlan。
    name = "report_writer"
    output_schema = None

    def __init__(self, settings: Optional[Settings] = None, chat_client=None) -> None:
        """初始化并绑定均衡模型与专用 prompt。"""
        super().__init__(settings, chat_client)
        self.model_name = self.settings.qwen_balanced_model
        self.system_prompt = REPORT_WRITER_PROMPT

    def build_mock(self, input_data: dict, state) -> dict:
        """返回 mock ResearchPlan 草稿（reference_ids 引用现有证据）。"""
        # 复用现有证据 ID 作为 references 来源。
        evidence_ids: list[str] = []
        for e in state.retrieved_evidence:
            eid = getattr(e, "id", None) if not isinstance(e, dict) else e.get("id")
            if eid:
                evidence_ids.append(eid)
        return mock_outputs.get_mock("research_plan", input_data.get("question_item", {}), evidence_ids)
