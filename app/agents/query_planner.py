"""
app.agents.query_planner —— 检索规划智能体。

基于解析结果生成 8-12 个多角度检索查询（覆盖 local_rag/deep_research/公开文献）。
模型：settings.qwen_balanced_model（默认 qwen3.7-plus）。
"""

from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.prompts import QUERY_PLANNER_PROMPT
from app.core.agent_schemas import QueryPlanResult
from app.core.config import Settings
from app.workflow import mock_outputs


class QueryPlannerAgent(BaseAgent):
    """将问题背景转化为多角度检索查询的智能体。"""

    # 阶段名与输出 schema。
    name = "query_planner"
    output_schema = QueryPlanResult

    def __init__(self, settings: Optional[Settings] = None, chat_client=None) -> None:
        """初始化并绑定均衡模型与专用 prompt。"""
        super().__init__(settings, chat_client)
        # 均衡模型：兼顾质量与成本。
        self.model_name = self.settings.qwen_balanced_model
        self.system_prompt = QUERY_PLANNER_PROMPT

    def build_mock(self, input_data: dict, state) -> dict:
        """返回 mock QueryPlanResult。"""
        return mock_outputs.get_mock("query_plan", input_data.get("question_item", {}))
