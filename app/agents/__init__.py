"""
app.agents —— 多智能体子包。

每个智能体负责科学发现流水线中的一个职责，均继承 base.BaseAgent。
本模块导出各 Agent 类，便于 workflow.pipeline 统一编排。
"""

from app.agents.base import AgentOutputError, BaseAgent
from app.agents.deep_research_agent import DeepResearchAgent
from app.agents.evidence_extractor import EvidenceExtractorAgent
from app.agents.experiment_designer import ExperimentDesignerAgent
from app.agents.hypothesis_generator import HypothesisGeneratorAgent
from app.agents.query_planner import QueryPlannerAgent
from app.agents.question_parser import QuestionParserAgent
from app.agents.report_writer import ReportWriterAgent
from app.agents.schema_validator import SchemaValidatorAgent
from app.agents.scientific_reviewer import ScientificReviewerAgent
from app.agents.supervisor import SupervisorAgent

# 对外导出的符号集合。
__all__ = [
    "BaseAgent",
    "AgentOutputError",
    "SupervisorAgent",
    "QuestionParserAgent",
    "QueryPlannerAgent",
    "DeepResearchAgent",
    "EvidenceExtractorAgent",
    "HypothesisGeneratorAgent",
    "ExperimentDesignerAgent",
    "ScientificReviewerAgent",
    "ReportWriterAgent",
    "SchemaValidatorAgent",
]
