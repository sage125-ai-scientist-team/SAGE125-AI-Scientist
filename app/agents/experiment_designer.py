"""
app.agents.experiment_designer —— 实验设计智能体。

为推荐假设设计可验证研究计划（source/target 数据、baselines/metrics/ablation、
validation_protocol），未真实执行时 Results 严格 pending。
模型：settings.qwen_balanced_model（默认 qwen3.7-plus）。
"""

from __future__ import annotations

import json
from typing import Optional

from app.agents.base import BaseAgent
from app.agents.prompts import EXPERIMENT_DESIGNER_PROMPT
from app.core.agent_schemas import ExperimentDesignResult
from app.core.config import Settings
from app.workflow import mock_outputs
from app.workflow.mock_outputs import PENDING_RESULTS


class ExperimentDesignerAgent(BaseAgent):
    """为假设设计可复现验证实验的智能体。"""

    # 阶段名与输出 schema。
    name = "experiment_designer"
    output_schema = ExperimentDesignResult

    def __init__(self, settings: Optional[Settings] = None, chat_client=None) -> None:
        """初始化并绑定均衡模型与专用 prompt。"""
        super().__init__(settings, chat_client)
        self.model_name = self.settings.qwen_balanced_model
        self.system_prompt = EXPERIMENT_DESIGNER_PROMPT

    def build_messages(self, input_data: dict) -> list[dict]:
        """
        构造 LLM 消息：只传假设与证据上下文，不传 question_item，避免模型回显输入。

        参数：
            input_data: pipeline 组装的完整 Agent 输入。

        返回：
            OpenAI 风格消息列表。
        """
        payload = {
            "revision_iteration": input_data.get("revision_iteration", 1),
            "review_result": input_data.get("review_result") or {},
            "question_type": input_data.get("question_type", ""),
            "recommended_hypothesis": input_data.get("recommended_hypothesis") or {},
            "hypothesis_generation": input_data.get("hypothesis_generation") or {},
            "evidence_extraction": input_data.get("evidence_extraction") or {},
            "evidence_catalog": input_data.get("evidence_catalog") or [],
        }
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ]

    def build_mock(self, input_data: dict, state) -> dict:
        """返回 mock ExperimentDesignResult（Results 严格 pending）。"""
        return mock_outputs.get_mock("experiment_design", input_data.get("question_item", {}))

    def run(self, input_data: dict, state, step_index: int = 0) -> dict:
        """
        执行实验设计，并强制“未真实执行时 Results 为 pending”的不变量。

        参数/返回：见 BaseAgent.run。
        """
        # 先走标准模板得到结果。
        result = super().run(input_data, state, step_index)
        # 安全兜底：若未真实执行，强制 execution_metadata 与 pending results。
        meta = result.get("execution_metadata") or {}
        if not meta.get("actual_execution"):
            meta["actual_execution"] = False
            result["execution_metadata"] = meta
            # 若模型未写标准 pending 句子，则强制替换，杜绝伪造结果。
            if PENDING_RESULTS not in (result.get("results") or ""):
                result["results"] = PENDING_RESULTS
        return result
