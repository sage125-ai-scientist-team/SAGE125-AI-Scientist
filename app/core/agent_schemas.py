"""
app.core.agent_schemas —— 多智能体中间输出的 Pydantic v2 数据契约。

设计意图：
    将各 Agent 的中间产物 schema 独立于 app.core.schemas，避免污染前两步已
    通过测试的主 schema（QuestionItem / EvidenceCard / ResearchPlan / PipelineState）。
    本模块只服务多智能体流程（app/agents + app/workflow）。

安全与反造假约束（贯穿所有 schema）：
    - established_facts 中每条 fact 必须绑定 evidence_ids；
    - 无 evidence 的内容只能进 knowledge_gaps / methodological_constraints；
    - 未真实执行实验时 execution_metadata.actual_execution 必须为 False，
      且 results 必须包含 pending 说明；
    - 追踪事件不保存完整 API Key、不保存用户上传文件全文。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# 问题类型可选集合（供 QuestionParser 分类，驱动 ExperimentDesigner 策略）。
# narrowed_falsifiable_subproblem 是 Q028 的正式类型：把“治愈所有癌症”
# 收窄为当前可执行、可证伪的 WDBC 子问题；必须与 mock 包和真实模型输出对齐。
QUESTION_TYPES: tuple[str, ...] = (
    "mechanism_discovery",
    "extreme_event_prediction",
    "material_or_drug_optimization",
    "theoretical_proof",
    "observation_plan",
    "engineering_optimization",
    "social_risk_or_policy",
    "ai_scientist_meta",
    "narrowed_falsifiable_subproblem",
    "general_scientific_unknown",
)
UNKNOWN_QUESTION_TYPE = "general_scientific_unknown"
QuestionType = Literal[
    "mechanism_discovery",
    "extreme_event_prediction",
    "material_or_drug_optimization",
    "theoretical_proof",
    "observation_plan",
    "engineering_optimization",
    "social_risk_or_policy",
    "ai_scientist_meta",
    "narrowed_falsifiable_subproblem",
    "general_scientific_unknown",
]

# 检索来源偏好可选集合。
SourcePreference = Literal["local_rag", "deep_research", "arxiv", "openalex", "crossref"]


class AgentTraceEvent(BaseModel):
    """单个 Agent 执行的可追踪事件（用于 agent_trace.json 与前端展示）。"""

    # 事件唯一 ID。
    event_id: str = Field(..., description="事件 ID")
    # 所属运行 ID。
    run_id: str = Field(..., description="运行 ID")
    # 在流水线中的步序。
    step_index: int = Field(..., description="步序索引")
    # Agent 名称。
    agent_name: str = Field(..., description="Agent 名称")
    # 使用的模型名（必须为千问；DeepResearch 为 qwen-deep-research）。
    model_name: str = Field(..., description="模型名")
    # 执行状态。
    status: Literal["pending", "running", "completed", "failed", "skipped"] = Field(
        ..., description="状态"
    )
    # 开始/结束时间（ISO 字符串，可空）。
    started_at: Optional[str] = Field(default=None, description="开始时间")
    ended_at: Optional[str] = Field(default=None, description="结束时间")
    # 耗时（毫秒，可空）。
    duration_ms: Optional[int] = Field(default=None, description="耗时毫秒")
    # 输入/输出摘要（<=600 字符，绝不含完整 Key 或文件全文）。
    input_summary: str = Field(default="", max_length=600, description="输入摘要")
    output_summary: str = Field(default="", max_length=600, description="输出摘要")
    # 关联证据 ID。
    evidence_ids: list[str] = Field(default_factory=list, description="关联证据 ID")
    # 警告/错误。
    warnings: list[str] = Field(default_factory=list, description="警告")
    errors: list[str] = Field(default_factory=list, description="错误")
    # prompt 指纹（便于可复现追踪）。
    prompt_hash: Optional[str] = Field(default=None, description="prompt 指纹")
    # 是否 mock 输出。
    mock: bool = Field(default=False, description="是否 mock")


class ParsedQuestionResult(BaseModel):
    """QuestionParser 的结构化输出。"""

    # 领域。
    domain: str = Field(..., description="领域")
    # 提炼后的核心问题。
    core_question: str = Field(..., description="核心问题")
    # 关键词与实体。
    keywords: list[str] = Field(default_factory=list, description="关键词")
    entities: list[str] = Field(default_factory=list, description="实体")
    # 问题类型（驱动实验设计策略）。
    question_type: QuestionType = Field(..., description="问题类型")

    @field_validator("question_type", mode="before")
    @classmethod
    def normalize_question_type(cls, value: object) -> object:
        """接受官方类型；未知标签回落到 general_scientific_unknown，避免流水线在第 1 阶段崩溃。"""
        raw = str(value or "").strip()
        if raw in QUESTION_TYPES:
            return raw
        return UNKNOWN_QUESTION_TYPE

    # 科学边界（当前科学能回答/不能回答的范围）。
    scientific_boundary: str = Field(..., description="科学边界")
    # 不应声称的内容（防止过度宣称）。
    what_not_to_claim: list[str] = Field(default_factory=list, description="不应声称的内容")
    # 疑似领域错配（来自抽取阶段的几何分配不确定性）。
    suspected_domain_mismatch: bool = Field(default=False, description="疑似领域错配")
    # 领域置信度。
    domain_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="领域置信度")


class QueryPlanItem(BaseModel):
    """单条检索查询计划。"""

    # 该查询的目的。
    purpose: str = Field(..., description="查询目的")
    # 查询本体（适合公开文献检索）。
    query: str = Field(..., description="查询文本")
    # 来源偏好。
    source_preference: SourcePreference = Field(..., description="来源偏好")
    # 期望获得的证据类型。
    expected_evidence: str = Field(..., description="期望证据")
    # 优先级。
    priority: Literal["high", "medium", "low"] = Field(default="medium", description="优先级")


class QueryPlanResult(BaseModel):
    """QueryPlanner 的结构化输出。"""

    # 查询列表。
    queries: list[QueryPlanItem] = Field(default_factory=list, description="查询列表")
    # 检索策略说明。
    search_rationale: str = Field(..., description="检索策略说明")
    # 所需证据类型。
    required_evidence_types: list[str] = Field(default_factory=list, description="所需证据类型")


class ExtractedFact(BaseModel):
    """从证据中抽取的一条事实（必须绑定 evidence_ids）。"""

    # 事实陈述。
    fact: str = Field(..., description="事实陈述")
    # 支撑证据 ID（established_facts 必须非空）。
    evidence_ids: list[str] = Field(default_factory=list, description="证据 ID")
    # 置信度。
    confidence: Literal["low", "medium", "high"] = Field(default="medium", description="置信度")
    # 事实类型。
    fact_type: Literal[
        "background", "mechanism", "dataset", "method", "limitation", "controversy"
    ] = Field(default="background", description="事实类型")
    # 附加说明/告诫（如适用范围）。
    caveat: Optional[str] = Field(default=None, description="告诫")


class KnowledgeGap(BaseModel):
    """一个知识空白（无充分证据的开放问题）。"""

    # 空白描述。
    gap: str = Field(..., description="知识空白")
    # 为何重要。
    why_it_matters: str = Field(..., description="重要性")
    # 相关证据 ID（可为空）。
    evidence_ids: list[str] = Field(default_factory=list, description="相关证据 ID")
    # 验证需求。
    validation_need: str = Field(..., description="验证需求")


class CandidateDataset(BaseModel):
    """候选数据集（区分 source / target）。"""

    # 名称。
    name: str = Field(..., description="数据集名称")
    # 类型：source=推演依据；target=验证需构造/采集；both=兼具。
    type: Literal["source", "target", "both"] = Field(..., description="数据集类型")
    # 用途。
    use: str = Field(..., description="用途")
    # 获取说明。
    access_note: str = Field(default="", description="获取说明")
    # 关联证据 ID。
    evidence_ids: list[str] = Field(default_factory=list, description="关联证据 ID")
    # 是否为公开候选。
    is_public_candidate: bool = Field(default=True, description="是否公开候选")
    # 是否已下载（默认 False，禁止伪造已下载）。
    is_already_downloaded: bool = Field(default=False, description="是否已下载")


class EvidenceExtractionResult(BaseModel):
    """EvidenceExtractor 的结构化输出。"""

    # 已确立事实（每条必须有 evidence_ids）。
    established_facts: list[ExtractedFact] = Field(default_factory=list, description="已确立事实")
    # 争议点。
    disputed_points: list[ExtractedFact] = Field(default_factory=list, description="争议点")
    # 知识空白。
    knowledge_gaps: list[KnowledgeGap] = Field(default_factory=list, description="知识空白")
    # 候选数据集。
    possible_datasets: list[CandidateDataset] = Field(default_factory=list, description="候选数据集")
    # 方法学约束。
    methodological_constraints: list[str] = Field(default_factory=list, description="方法学约束")
    # 证据覆盖说明（是否充分）。
    evidence_coverage_note: str = Field(..., description="证据覆盖说明")


class CandidateHypothesis(BaseModel):
    """候选科学假设（含评分与证据绑定）。"""

    # 假设陈述。
    hypothesis: str = Field(..., description="假设陈述")
    # 机制。
    mechanism: str = Field(..., description="机制")
    # 可证伪预测。
    falsifiable_prediction: str = Field(..., description="可证伪预测")
    # 所需观测。
    required_observations: list[str] = Field(default_factory=list, description="所需观测")
    # 被证伪风险。
    risk_of_being_wrong: str = Field(..., description="被证伪风险")
    # 支撑/反驳证据 ID。
    supporting_evidence_ids: list[str] = Field(default_factory=list, description="支撑证据 ID")
    contradicted_by_evidence_ids: list[str] = Field(
        default_factory=list, description="反驳证据 ID"
    )
    # 评分（0-1）。
    novelty_score: float = Field(default=0.0, ge=0.0, le=1.0, description="新颖性")
    falsifiability_score: float = Field(default=0.0, ge=0.0, le=1.0, description="可证伪性")
    feasibility_score: float = Field(default=0.0, ge=0.0, le=1.0, description="可行性")
    evidence_support_score: float = Field(default=0.0, ge=0.0, le=1.0, description="证据支撑度")
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0, description="综合分")


class HypothesisGenerationResult(BaseModel):
    """HypothesisGenerator 的结构化输出。"""

    # 候选假设（2-3 个）。
    hypotheses: list[CandidateHypothesis] = Field(default_factory=list, description="候选假设")
    # 推荐假设索引。
    recommended_hypothesis_index: int = Field(default=0, description="推荐索引")
    # 选择理由。
    selection_reason: str = Field(..., description="选择理由")
    # 被否决的方向。
    rejected_directions: list[str] = Field(default_factory=list, description="被否决方向")


class ExperimentDesignResult(BaseModel):
    """ExperimentDesigner 的结构化输出。"""

    # 技术细节。
    technical_details: str = Field(..., description="技术细节")
    # 数据集（必须含 source 与 target）。
    datasets: dict = Field(default_factory=dict, description="数据集")
    # 方法。
    methods: str = Field(..., description="方法")
    # 实验（必须含 baselines 与 metrics）。
    experiments: dict = Field(default_factory=dict, description="实验")
    # 结果（未执行时必须写 pending 说明）。
    results: str = Field(..., description="结果")
    # 可复现性检查清单。
    reproducibility_checklist: list[str] = Field(default_factory=list, description="可复现清单")
    # 执行元数据（含 actual_execution 标记）。
    execution_metadata: dict = Field(default_factory=dict, description="执行元数据")


class ReviewResult(BaseModel):
    """ScientificReviewer 的结构化输出。"""

    # 是否通过。
    passed: bool = Field(..., description="是否通过")
    # 评审意见。
    reviewer_comments: list[str] = Field(default_factory=list, description="评审意见")
    # 关键问题。
    critical_issues: list[str] = Field(default_factory=list, description="关键问题")
    # 必要修订。
    required_revisions: list[str] = Field(default_factory=list, description="必要修订")
    # 风险等级。
    risk_level: Literal["low", "medium", "high"] = Field(default="medium", description="风险等级")
    # 评分（0-1）。
    evidence_grounding_score: float = Field(default=0.0, ge=0.0, le=1.0, description="证据落地度")
    falsifiability_score: float = Field(default=0.0, ge=0.0, le=1.0, description="可证伪性")
    reproducibility_score: float = Field(default=0.0, ge=0.0, le=1.0, description="可复现性")
    reference_reliability_score: float = Field(default=0.0, ge=0.0, le=1.0, description="引用可靠性")


class ValidationResult(BaseModel):
    """SchemaValidator 的结构化输出。"""

    # 是否有效。
    valid: bool = Field(..., description="是否有效")
    # 错误与警告。
    errors: list[str] = Field(default_factory=list, description="错误")
    warnings: list[str] = Field(default_factory=list, description="警告")
    # 最终校验状态。
    validation_status: Literal["draft", "needs_data", "ready_for_validation", "validated"] = Field(
        default="draft", description="校验状态"
    )
    # 各质量门结果。
    quality_gate_results: dict = Field(default_factory=dict, description="质量门结果")
