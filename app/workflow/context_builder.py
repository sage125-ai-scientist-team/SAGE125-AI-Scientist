"""
app.workflow.context_builder —— 各 Agent 输入上下文构造与上下文包保存。

用于“上下文工程”：为每个 Agent 组装精炼、可追溯的输入，并将整体上下文包
保存到 exports/{run_id}/context_pack.json，便于答辩展示与复现。

安全：context_pack 不含 API Key、不含用户上传文件全文；每条事实带 evidence_ids。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

# 模块级日志器。
logger = get_logger("workflow.context_builder")


def _card_id(card: Any) -> str | None:
    """从 EvidenceCard 对象或 dict 中取 id。"""
    return getattr(card, "id", None) if not isinstance(card, dict) else card.get("id")


def _card_dump(card: Any) -> dict:
    """将 EvidenceCard 对象或 dict 统一转为 dict。"""
    if isinstance(card, dict):
        return card
    return card.model_dump() if hasattr(card, "model_dump") else dict(card)


class ContextBuilder:
    """构造各 Agent 上下文并保存上下文包。"""

    def build_question_context(self, question_item: dict) -> dict:
        """
        构造问题上下文。

        参数：
            question_item: 选中问题 dict。

        返回：
            含问题、领域、booklet_excerpt 与 metadata 的上下文。
        """
        # 仅保留问题相关的可展示字段。
        return {
            "id": question_item.get("id"),
            "domain": question_item.get("domain"),
            "question": question_item.get("question"),
            "booklet_excerpt": question_item.get("booklet_excerpt"),
            "metadata": question_item.get("metadata", {}),
        }

    def build_evidence_pack(self, evidence_cards: list, max_cards: int = 12) -> list[dict]:
        """
        构造证据包（截断 quoted_text，控制体积）。

        参数：
            evidence_cards: EvidenceCard 列表（对象或 dict）。
            max_cards:      最大证据数。

        返回：
            精简后的证据 dict 列表。
        """
        pack: list[dict] = []
        for card in evidence_cards[:max_cards]:
            d = _card_dump(card)
            # 仅保留展示所需字段，截断原文，避免体积膨胀。
            pack.append(
                {
                    "id": d.get("id"),
                    "source_type": d.get("source_type"),
                    "title": d.get("title"),
                    "doi": d.get("doi"),
                    "url": d.get("url"),
                    "quoted_text": (d.get("quoted_text") or "")[:300],
                    "relevance_score": d.get("relevance_score"),
                    "reliability_note": d.get("reliability_note"),
                }
            )
        return pack

    def build_fact_context(self, evidence_extraction_result: dict | None) -> dict:
        """构造事实上下文（established_facts / knowledge_gaps）。"""
        # 无结果时返回空结构。
        r = evidence_extraction_result or {}
        return {
            "established_facts": r.get("established_facts", []),
            "knowledge_gaps": r.get("knowledge_gaps", []),
            "possible_datasets": r.get("possible_datasets", []),
        }

    def build_hypothesis_context(self, hypothesis_result: dict | None) -> dict:
        """构造假设上下文（候选假设与推荐索引）。"""
        r = hypothesis_result or {}
        return {
            "hypotheses": r.get("hypotheses", []),
            "recommended_hypothesis_index": r.get("recommended_hypothesis_index", 0),
        }

    def build_experiment_context(self, experiment_design_result: dict | None) -> dict:
        """构造实验设计摘要上下文。"""
        r = experiment_design_result or {}
        return {
            "datasets": r.get("datasets", {}),
            "experiments": r.get("experiments", {}),
            "results": r.get("results", ""),
            "execution_metadata": r.get("execution_metadata", {}),
        }

    def build_reviewer_context(self, review_result: dict | None) -> dict:
        """构造评审摘要上下文。"""
        r = review_result or {}
        return {
            "passed": r.get("passed"),
            "critical_issues": r.get("critical_issues", []),
            "required_revisions": r.get("required_revisions", []),
            "risk_level": r.get("risk_level"),
        }

    def build_context_pack(self, state) -> dict:
        """
        汇总整个运行的上下文包（用于答辩展示上下文工程）。

        参数：
            state: PipelineState。

        返回：
            context_pack dict（不含 API Key / 文件全文）。
        """
        # 选中问题（dict）。
        qi = state.selected_question.model_dump() if hasattr(state.selected_question, "model_dump") else state.selected_question
        evidence_ids = [_card_id(c) for c in state.retrieved_evidence if _card_id(c)]
        # 收集各阶段 prompt_hash。
        prompt_hashes = {ev.get("agent_name"): ev.get("prompt_hash") for ev in state.agent_trace}
        return {
            "run_id": state.run_id,
            "selected_question": self.build_question_context(qi),
            "parsed_question": state.parsed_question,
            "query_plan": state.query_plan,
            "evidence_pack": self.build_evidence_pack(state.retrieved_evidence),
            "evidence_ids": evidence_ids,
            "established_facts": (state.evidence_extraction or {}).get("established_facts", []),
            "knowledge_gaps": (state.evidence_extraction or {}).get("knowledge_gaps", []),
            "candidate_hypotheses": (state.hypothesis_generation or {}).get("hypotheses", []),
            "experiment_design_summary": self.build_experiment_context(state.experiment_design),
            "reviewer_summary": self.build_reviewer_context(state.review_result),
            "quality_gates": state.quality_gates,
            "user_feedback": (state.reviewer_feedback[-1] if state.reviewer_feedback else None),
            "prompt_hashes": prompt_hashes,
        }

    def save_context_pack(self, run_id: str, state, base_dir: str | Path = "exports") -> str:
        """
        构造并保存 context_pack.json 到 exports/{run_id}/。

        参数：
            run_id: 运行 ID。
            state:  PipelineState。

        返回：
            保存路径字符串。
        """
        pack = self.build_context_pack(state)
        # 写入 state 便于其它环节引用。
        state.context_pack = pack
        out_dir = Path(base_dir) / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "context_pack.json"
        path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("context_pack 已保存：%s", path)
        return str(path)
