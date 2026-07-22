"""
app.core.schemas —— 全局 Pydantic v2 数据模型与反造假校验。

定义系统在各智能体间流转的结构化契约：
    - QuestionItem        : 125 Questions 中的单个问题。
    - EvidenceCard        : 可溯源的证据卡片。
    - ScientificHypothesis: 可证伪的科学假设。
    - ResearchPlan        : 最终《科学假设与研究计划》聚合结构。
    - PipelineState       : 多智能体流水线的共享状态。

反造假约束（在 ResearchPlan 校验器中实现）：
    1. datasets 必须包含 source 与 target 两个 key；
    2. experiments 必须包含 baselines 与 metrics 两个 key；
    3. references 不能为空，除非 validation_status == "needs_data" 且
       results 中明确写“待检索/待验证”；
    4. DOI 若存在需通过基本格式检查；
    5. 未标注 actual_execution=True 时，results 中不得出现 AUROC=0.92 等
       看似真实的虚构量化指标。
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# 证据来源类型的可选集合。
SourceType = Literal[
    "booklet", "rag", "deep_research", "arxiv", "crossref", "openalex", "user_upload"
]

# 研究计划的校验状态可选集合。
ValidationStatus = Literal["draft", "needs_data", "ready_for_validation", "validated"]

# DOI 基本格式：以 10. 开头，后接 4-9 位登记号 + '/' + 后缀。
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")

# 疑似“虚构量化指标”的检测正则：指标名后跟一个小数或百分数。
# 例：AUROC=0.92、AUPRC: 0.81、accuracy = 95%、F1 0.88。
_FAKE_METRIC_PATTERN = re.compile(
    r"(auroc|auprc|auc|accuracy|acc|f1|precision|recall|dice|iou|bleu|rouge|mae|rmse|r2)"
    r"\s*[=:：]?\s*"
    r"(0?\.\d+|\d{1,3}\s*%|\d\.\d+)",
    re.IGNORECASE,
)

# results 中允许“无引用”时必须出现的占位说明关键字。
_PENDING_KEYWORDS = ("待检索", "待验证")


class QuestionItem(BaseModel):
    """125 Questions 中的单个科学问题及其溯源信息。"""

    # 问题稳定标识（如 "Q001"）。
    id: str = Field(..., description="问题唯一 ID")
    # 所属学科领域。
    domain: str = Field(..., description="学科领域")
    # 问题正文（须来自 booklet 原文，禁止改写题意）。
    question: str = Field(..., description="问题正文")
    # 问题在 booklet 中的来源页码（可空）。
    source_page: Optional[int] = Field(default=None, description="来源页码")
    # booklet 中的相关摘录（可空，用于溯源）。
    booklet_excerpt: Optional[str] = Field(default=None, description="booklet 摘录")
    # 向后兼容的扩展元数据（如 confidence / extraction_method / source_file）。
    # 说明：为保持提示词一的 schema 兼容，附加字段统一放入 metadata，而非改动原有字段。
    metadata: dict = Field(default_factory=dict, description="扩展元数据")


class EvidenceCard(BaseModel):
    """
    证据卡片：一条支撑/反驳假设的可溯源证据。

    DOI 若存在须通过基本格式检查；来源不可靠时应在 reliability_note 中标注。
    """

    # 证据唯一标识。
    id: str = Field(..., description="证据唯一 ID")
    # 证据来源类型（受 Literal 约束）。
    source_type: SourceType = Field(..., description="来源类型")
    # 文献/资料标题。
    title: str = Field(..., description="标题")
    # 作者列表（不得伪造，未知留空）。
    authors: list[str] = Field(default_factory=list, description="作者列表")
    # 发表年份（可空）。
    year: Optional[int] = Field(default=None, description="发表年份")
    # 来源 URL（不得伪造，可空）。
    url: Optional[str] = Field(default=None, description="来源 URL")
    # DOI（不得伪造，可空；存在时需通过格式检查）。
    doi: Optional[str] = Field(default=None, description="DOI")
    # 可核验的原文引用。
    quoted_text: str = Field(..., description="原文引用片段")
    # 对证据的摘要。
    summary: str = Field(..., description="证据摘要")
    # 相关性评分（0-1）。
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="相关性评分 0-1")
    # 可靠性说明（如 rerank_failed_fallback_used 等标记）。
    reliability_note: str = Field(default="", description="可靠性说明/标记")

    @field_validator("doi")
    @classmethod
    def _validate_doi_format(cls, value: Optional[str]) -> Optional[str]:
        """
        当 DOI 存在时执行基本格式校验（10.xxxx/xxx）。

        参数：
            value: DOI 字符串或 None。

        返回：
            合规的 DOI 或 None。

        异常：
            ValueError: DOI 非空但格式不合法时抛出。
        """
        # 空 DOI 直接放行（允许未知）。
        if value is None or value.strip() == "":
            return None
        # 非空则必须匹配基本 DOI 模式。
        if not _DOI_PATTERN.match(value.strip()):
            raise ValueError(f"DOI 格式非法：'{value}'（应形如 10.1000/xxxxx）。")
        return value.strip()


class ScientificHypothesis(BaseModel):
    """可证伪的科学假设，含机制、可证伪预测与被证伪风险。"""

    # 假设陈述（应可证伪）。
    hypothesis: str = Field(..., description="可证伪的假设陈述")
    # 机制解释。
    mechanism: str = Field(..., description="机制/原理解释")
    # 可证伪的预测（若假设错误则应观察到的反例）。
    falsifiable_prediction: str = Field(..., description="可证伪预测")
    # 验证所需的关键观测。
    required_observations: list[str] = Field(
        default_factory=list, description="验证所需观测"
    )
    # 该假设被证伪的风险评估。
    risk_of_being_wrong: str = Field(..., description="被证伪风险评估")
    # 保留候选阶段的证据绑定，避免 ReportWriter 聚合时丢失可追溯关系。
    supporting_evidence_ids: list[str] = Field(default_factory=list, description="支撑证据 ID")
    contradicted_by_evidence_ids: list[str] = Field(default_factory=list, description="反驳证据 ID")


class ResearchPlan(BaseModel):
    """
    《科学假设与研究计划》最终聚合结构，供 exporters 导出。

    通过 model_validator 施加多项反造假约束（见模块 docstring）。
    """

    # 关联的问题 ID（用于前端选题-报告一致性校验，防止串线）。
    question_id: str = Field(default="", description="关联问题 ID")
    # 用户选择的原始科学问题。
    input_question: str = Field(..., description="输入问题")
    # 所属领域。
    domain: str = Field(..., description="学科领域")
    # 问题陈述。
    problem_statement: str = Field(..., description="问题陈述")
    # 立论依据。
    rationale: str = Field(..., description="立论依据")
    # 生成的假设列表。
    generated_hypotheses: list[ScientificHypothesis] = Field(
        default_factory=list, description="生成的假设"
    )
    # 技术细节。
    technical_details: str = Field(default="", description="技术细节")
    # 数据集：必须包含 source 与 target 两个 key。
    datasets: dict = Field(default_factory=dict, description="数据集（须含 source/target）")
    # 论文标题。
    paper_title: str = Field(default="", description="论文标题")
    # 论文摘要。
    paper_abstract: str = Field(default="", description="论文摘要")
    # 方法。
    methods: str = Field(default="", description="方法")
    # 实验：必须包含 baselines 与 metrics 两个 key。
    experiments: dict = Field(
        default_factory=dict, description="实验（须含 baselines/metrics）"
    )
    # 结果（未真实执行时不得出现虚构指标数值）。
    results: str = Field(default="", description="结果")
    # 参考文献（可引用证据）。
    references: list[EvidenceCard] = Field(default_factory=list, description="参考文献")
    # 评审意见。
    reviewer_comments: list[str] = Field(default_factory=list, description="评审意见")
    # 修订历史。
    revision_history: list[str] = Field(default_factory=list, description="修订历史")
    # 可复现性检查清单。
    reproducibility_checklist: list[str] = Field(
        default_factory=list, description="可复现性检查清单"
    )
    # 校验状态。
    validation_status: ValidationStatus = Field(
        default="draft", description="校验状态"
    )
    # 是否已真实执行实验（仅当为 True 时 results 才允许包含量化指标）。
    actual_execution: bool = Field(
        default=False, description="是否已真实执行实验（控制指标数值是否合法）"
    )

    @model_validator(mode="after")
    def _validate_anti_fabrication(self) -> "ResearchPlan":
        """
        施加反造假与结构完整性约束。

        校验项：
            1. datasets 必须含 source 与 target；
            2. experiments 必须含 baselines 与 metrics；
            3. references 非空，除非 validation_status=="needs_data" 且 results
               含“待检索/待验证”；
            4. 未真实执行时，results 不得出现看似真实的量化指标。

        返回：
            通过校验的 ResearchPlan 实例（self）。

        异常：
            ValueError: 任一约束不满足时抛出。
        """
        # 约束 1：datasets 必须包含 source 与 target。
        missing_ds = [k for k in ("source", "target") if k not in self.datasets]
        if missing_ds:
            raise ValueError(f"datasets 缺少必需的 key：{missing_ds}（须含 source 与 target）。")

        # 约束 2：experiments 必须包含 baselines 与 metrics。
        missing_exp = [k for k in ("baselines", "metrics") if k not in self.experiments]
        if missing_exp:
            raise ValueError(
                f"experiments 缺少必需的 key：{missing_exp}（须含 baselines 与 metrics）。"
            )

        # 约束 3：references 非空规则。
        if not self.references:
            # 允许为空的唯一情形：needs_data 且 results 明确标注待检索/待验证。
            if self.validation_status != "needs_data":
                raise ValueError(
                    "references 不能为空（除非 validation_status='needs_data' 且 results 标注待检索/待验证）。"
                )
            if not any(k in self.results for k in _PENDING_KEYWORDS):
                raise ValueError(
                    "references 为空时，results 必须明确写“待检索/待验证”。"
                )

        # 约束 4：未真实执行时禁止虚构量化指标。
        if not self.actual_execution and self.results:
            match = _FAKE_METRIC_PATTERN.search(self.results)
            if match:
                raise ValueError(
                    f"results 中出现疑似虚构量化指标 '{match.group(0)}'，"
                    "但 actual_execution 未置为 True。禁止在无真实实验时写具体指标数值。"
                )
        return self


class PipelineState(BaseModel):
    """多智能体流水线的共享状态：承载各阶段的输入、中间产物与最终结果。"""

    # 本次运行的唯一标识。
    run_id: str = Field(..., description="运行 ID")
    # 用户选择的问题。
    selected_question: QuestionItem = Field(..., description="选中的问题")
    # 用户上传的文件路径列表。
    user_files: list[str] = Field(default_factory=list, description="用户上传文件路径")
    # 检索到的证据。
    retrieved_evidence: list[EvidenceCard] = Field(
        default_factory=list, description="检索到的证据"
    )
    # 抽取的事实。
    extracted_facts: list[str] = Field(default_factory=list, description="抽取的事实")
    # 识别到的知识空白。
    knowledge_gaps: list[str] = Field(default_factory=list, description="知识空白")
    # 生成的假设。
    hypotheses: list[ScientificHypothesis] = Field(
        default_factory=list, description="生成的假设"
    )
    # 草稿研究计划。
    draft_plan: Optional[ResearchPlan] = Field(default=None, description="草稿计划")
    # 评审反馈。
    reviewer_feedback: list[str] = Field(default_factory=list, description="评审反馈")
    # 最终研究计划。
    final_plan: Optional[ResearchPlan] = Field(default=None, description="最终计划")
    # 运行日志（人类可读）。
    logs: list[str] = Field(default_factory=list, description="运行日志")
    # 运行期错误信息。
    errors: list[str] = Field(default_factory=list, description="错误信息")

    # ---- 以下为多智能体流程新增的向后兼容可选字段（默认空，不影响前两步测试）----
    # 运行期警告（非致命，如 deep_research_failed / rag_missing）。
    warnings: list[str] = Field(default_factory=list, description="警告信息")
    # 解析后的问题（ParsedQuestionResult 的 dict 快照）。
    parsed_question: Optional[dict] = Field(default=None, description="解析后的问题")
    # 检索查询计划（QueryPlanResult 的 dict 快照）。
    query_plan: Optional[dict] = Field(default=None, description="检索查询计划")
    # 证据抽取结果（EvidenceExtractionResult 的 dict 快照）。
    evidence_extraction: Optional[dict] = Field(default=None, description="证据抽取结果")
    # 假设生成结果（HypothesisGenerationResult 的 dict 快照）。
    hypothesis_generation: Optional[dict] = Field(default=None, description="假设生成结果")
    # 实验设计结果（ExperimentDesignResult 的 dict 快照）。
    experiment_design: Optional[dict] = Field(default=None, description="实验设计结果")
    # 评审结果（ReviewResult 的 dict 快照）。
    review_result: Optional[dict] = Field(default=None, description="评审结果")
    # 校验结果（ValidationResult 的 dict 快照）。
    validation_result: Optional[dict] = Field(default=None, description="校验结果")
    # Agent 追踪事件列表（AgentTraceEvent 的 dict 快照）。
    agent_trace: list[dict] = Field(default_factory=list, description="Agent 追踪事件")
    # 质量门结果汇总。
    quality_gates: dict = Field(default_factory=dict, description="质量门结果")
    # 修订历史。
    revision_history: list[str] = Field(default_factory=list, description="修订历史")
    # 上下文包（context_pack 的 dict 快照）。
    context_pack: Optional[dict] = Field(default=None, description="上下文包")
    # 证据是否不足（影响 validation_status 上限）。
    evidence_insufficient: bool = Field(default=False, description="证据是否不足")
    # 领域错配警告（来自 QuestionParser）。
    domain_warning: Optional[str] = Field(default=None, description="领域错配警告")
    # 执行元数据（含 actual_execution）。
    execution_metadata: dict = Field(default_factory=dict, description="执行元数据")
    # 是否为 mock 运行。
    mock_mode: bool = Field(default=False, description="是否 mock 运行")
    # 运行模式（"mock" | "real"），供审计与前端徽标使用。
    run_mode: str = Field(default="mock", description="运行模式 mock/real")
    # LLM 调用审计记录（LLMCallRecord 的 dict 快照列表）。
    llm_calls: list[dict] = Field(default_factory=list, description="LLM 调用审计记录")
