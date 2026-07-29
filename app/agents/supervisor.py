"""
app.agents.supervisor —— 调度策略智能体。

Supervisor 不生成科学内容，仅根据资源可用性与开关决定启用/跳过哪些 Agent，
并给出风险标记。模型：settings.qwen_balanced_model（默认 qwen3.7-plus，仅用于 trace 标识）。
"""

from __future__ import annotations

from typing import Optional

from app.agents.base import BaseAgent, _now_iso
from app.agents.prompts import SUPERVISOR_PROMPT
from app.contracts.rag import IndexConfig
from app.core.config import Settings


class SupervisorAgent(BaseAgent):
    """编排策略生成器：决定各 Agent 的启用/跳过与风险标记。"""

    # 阶段名；纯策略逻辑，不走 JSON LLM 模板。
    name = "supervisor"
    output_schema = None

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """初始化并绑定均衡模型（仅用于 trace 标识）。"""
        super().__init__(settings)
        self.model_name = self.settings.qwen_balanced_model
        self.system_prompt = SUPERVISOR_PROMPT
        self.index_config = IndexConfig.resolve({"data_root": self.settings.data_dir})

    def run(self, input_data: dict, state, step_index: int = 0) -> dict:
        """
        生成 execution_plan / enabled_agents / skipped_agents / risk_flags。

        参数：
            input_data: 含 switches（use_local_rag/use_deep_research/use_open_literature/
                        reviewer_auto_revision/mock_mode）。
            state:      流水线状态。
            step_index: 步序索引。

        返回：
            调度策略 dict。
        """
        started = _now_iso()
        switches = input_data.get("switches", {})
        risk_flags: list[str] = []
        skipped: list[str] = []
        enabled: list[str] = ["question_parser", "query_planner", "evidence_extractor",
                              "hypothesis_generator", "experiment_designer",
                              "scientific_reviewer", "report_writer", "schema_validator"]

        mock_mode = bool(switches.get("mock_mode"))

        # 1) RAG index 状态：缺失仍继续，但标记 warning 并关闭 local_rag。
        use_local_rag = bool(switches.get("use_local_rag", True))
        index_dir = self.index_config.vector_index_dir
        rag_available = index_dir.exists() and any(index_dir.iterdir()) if index_dir.exists() else False
        if use_local_rag and not rag_available and not mock_mode:
            risk_flags.append("rag_missing_warning")
            use_local_rag = False

        # 2) DeepResearch：未配置则跳过（不终止）。
        use_deep_research = bool(switches.get("use_deep_research", True))
        if use_deep_research and not self.settings.deep_research_configured and not mock_mode:
            skipped.append("deep_research")
            risk_flags.append("deep_research_not_configured")
            use_deep_research = False

        # 3) OpenAlex：缺 Key 只影响 OpenAlex，不跳过 arxiv/crossref。
        use_open_literature = bool(switches.get("use_open_literature", True))
        if use_open_literature and not self.settings.openalex_configured:
            risk_flags.append("openalex_key_missing")

        # 组装执行计划。
        plan = {
            "execution_plan": {
                "use_local_rag": use_local_rag,
                "use_deep_research": use_deep_research,
                "use_open_literature": use_open_literature,
                "reviewer_auto_revision": bool(switches.get("reviewer_auto_revision", True)),
                "mock_mode": mock_mode,
            },
            "enabled_agents": enabled,
            "skipped_agents": skipped,
            "risk_flags": risk_flags,
        }

        # 记录 trace（策略事件）。
        input_summary = self.safe_summarize_input(switches)
        self.create_trace_event(
            state=state,
            step_index=step_index,
            status="completed",
            input_summary=input_summary,
            output_summary=self.safe_summarize_input(plan),
            evidence_ids=[],
            warnings=risk_flags,
            errors=[],
            prompt_hash=self.hash_prompt(self.system_prompt, input_summary),
            started_at=started,
            ended_at=_now_iso(),
            mock=mock_mode,
        )
        return plan
