"""
app.agents.deep_research_agent —— 深度研究智能体。

调用 QwenDeepResearchClient（原生 dashscope SDK，stream=True，禁用 OpenAI-compatible），
将返回内容经 deep_research_to_evidence_cards 转为 EvidenceCard。

关键约束：
    - 不把 DeepResearch 输出直接作为最终 ResearchPlan；
    - 不把未核验引用标为 validated；
    - DeepResearch 失败**不**中断 pipeline（返回 status=failed）。
模型：settings.qwen_deep_research_model（默认 qwen-deep-research）。
"""

from __future__ import annotations

import os
from typing import Optional

from app.agents.base import BaseAgent, _now_iso
from app.clients.qwen_deep_research_client import QwenDeepResearchClient
from app.core.config import Settings
from app.core.logging import mask_text
from app.rag.evidence import deep_research_to_evidence_cards


class DeepResearchAgent(BaseAgent):
    """封装 Qwen Deep Research 调用的智能体（失败安全）。"""

    # 阶段名；不走标准 JSON 模板，故 output_schema=None。
    name = "deep_research"
    output_schema = None

    def __init__(
        self,
        settings: Optional[Settings] = None,
        dr_client: Optional[QwenDeepResearchClient] = None,
    ) -> None:
        """初始化并绑定深度研究模型。"""
        super().__init__(settings)
        # 深度研究专用模型（走 dashscope）。
        self.model_name = self.settings.qwen_deep_research_model
        self.system_prompt = "DeepResearch 调研资料来源（需下游核验）。"
        # 惰性/可注入的深度研究客户端。
        self._dr_client = dr_client

    def _force_fail(self) -> bool:
        """判断是否通过环境变量强制失败（用于测试失败路径）。"""
        return os.getenv("MOCK_DEEPRESEARCH_FAIL", "").strip().lower() in ("1", "true", "yes")

    def run(self, input_data: dict, state, step_index: int = 0) -> dict:
        """
        执行深度研究并返回结构化结果（永不抛出，失败返回 failed）。

        参数：
            input_data: 含 topic 与可选 context。
            state:      流水线状态。
            step_index: 步序索引。

        返回：
            {"status","content","evidence_cards","warnings","errors"}。
        """
        started = _now_iso()
        topic = input_data.get("topic", "")
        context = input_data.get("context", "")
        input_summary = self.safe_summarize_input({"topic": topic})
        warnings: list[str] = []
        errors: list[str] = []
        status_label = "completed"
        result = {"status": "failed", "content": "", "evidence_cards": [], "warnings": [], "errors": []}
        audit_request_id: str | None = None
        audit_usage: dict[str, int] = {}

        try:
            # 测试用：强制失败路径。
            if self._force_fail():
                warnings.append("deep_research_failed")
                result = {"status": "failed", "content": "", "evidence_cards": [], "warnings": warnings, "errors": ["forced_fail"]}
            elif self.is_mock():
                # mock：返回成功的调研纪要，但不产出证据卡（由 pipeline 注入 mock 证据）。
                result = {
                    "status": "succeeded",
                    "content": "[MOCK] DeepResearch 调研纪要：One Health 与多源数据融合是主流方向（需核验）。",
                    "evidence_cards": [],
                    "warnings": [],
                    "errors": [],
                }
            else:
                # 真实调用：dashscope stream=True。
                client = self._dr_client or QwenDeepResearchClient(self.settings)
                dr = client.run_deep_research(topic, context)
                # 客户端以响应字段为准；保留失败前已经收到的真实用量和 request_id。
                candidate_request_id = dr.get("request_id") or getattr(client, "last_request_id", None)
                if isinstance(candidate_request_id, str) and candidate_request_id.strip():
                    audit_request_id = candidate_request_id
                candidate_usage = dr.get("usage") or getattr(client, "last_usage", {})
                if isinstance(candidate_usage, dict):
                    audit_usage = candidate_usage
                if dr.get("status") == "succeeded":
                    # 将纪要与引用转为 EvidenceCard（标记需核验）。
                    cards = deep_research_to_evidence_cards(dr)
                    result = {
                        "status": "succeeded",
                        "content": dr.get("content", ""),
                        "evidence_cards": [c.model_dump() for c in cards],
                        "warnings": [],
                        "errors": [],
                    }
                else:
                    # 失败不终止 pipeline。
                    warnings.append("deep_research_failed")
                    result = {"status": "failed", "content": "", "evidence_cards": [], "warnings": warnings, "errors": [dr.get("error", "unknown")]}
        except Exception as exc:
            # 任何异常都不得中断 pipeline。
            status_label = "failed"
            warnings.append("deep_research_failed")
            errors.append(mask_text(str(exc)))
            result = {"status": "failed", "content": "", "evidence_cards": [], "warnings": warnings, "errors": errors}

        # 失败时状态标记为 skipped/failed（用于 trace 展示）。
        if result.get("status") != "succeeded":
            status_label = "failed"

        # 写入 DeepResearch 调用审计（脱敏；mock 与 real 均记录）。
        try:
            from app.core.call_audit import LLMCallRecord

            is_mock = self.is_mock()
            record = LLMCallRecord(
                run_id=state.run_id,
                agent_name=self.name,
                provider="mock" if is_mock else "dashscope_deepresearch",
                model_alias="deepresearch",
                model_name_internal=self.model_name,
                mock=is_mock,
                started_at=started,
                request_id=audit_request_id,
                input_tokens=audit_usage.get("input_tokens"),
                output_tokens=audit_usage.get("output_tokens"),
                total_tokens=audit_usage.get("total_tokens"),
                status="success" if result.get("status") == "succeeded" else "failed",
                error_type=None if result.get("status") == "succeeded" else "deep_research_failed",
            ).finalize()
            state.llm_calls.append(record.model_dump())
        except Exception:  # noqa: BLE001
            pass

        # 汇总 warning 到 state（供 pipeline 保守判定）。
        for w in warnings:
            if w not in state.warnings:
                state.warnings.append(w)

        # 登记 trace。
        self.create_trace_event(
            state=state,
            step_index=step_index,
            status=status_label,
            input_summary=input_summary,
            output_summary=self.safe_summarize_input({"status": result.get("status"), "cards": len(result.get("evidence_cards", []))}),
            evidence_ids=[c.get("id") for c in result.get("evidence_cards", []) if isinstance(c, dict) and c.get("id")],
            warnings=warnings,
            errors=errors,
            prompt_hash=self.hash_prompt(self.system_prompt, input_summary),
            started_at=started,
            ended_at=_now_iso(),
            mock=self.is_mock(),
        )
        return result

    def build_mock(self, input_data: dict, state) -> dict:
        """DeepResearchAgent 自定义 run，不使用标准 build_mock。"""
        # 保留以满足抽象约定；实际不被调用。
        return {"status": "succeeded", "content": "", "evidence_cards": []}
