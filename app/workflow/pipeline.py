"""
app.workflow.pipeline —— 多智能体核心编排器（自研、轻量、可解释）。

按如下顺序驱动状态机（借鉴“节点/边/质量门”思想，但不依赖 LangGraph）：
    Supervisor -> QuestionParser -> QueryPlanner -> LocalRAG -> DeepResearch
    -> OpenLiterature -> EvidenceExtractor -> HypothesisGenerator
    -> ExperimentDesigner -> ScientificReviewer(最多 1 次自动修订)
    -> ReportWriter -> SchemaValidator + QualityGates -> Artifacts。

关键不变量：
    - 非关键步骤失败（RAG/DeepResearch/OpenAlex）只记 warning，不终止；
    - References 全部来自 EvidenceCards；无真实实验时 Results 为 pending；
    - validation_status 取“质量门 / 校验器”中更保守者，且无真实实验绝不 validated。
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

from app.agents import (
    DeepResearchAgent,
    EvidenceExtractorAgent,
    ExperimentDesignerAgent,
    HypothesisGeneratorAgent,
    QueryPlannerAgent,
    QuestionParserAgent,
    ReportWriterAgent,
    ScientificReviewerAgent,
    SchemaValidatorAgent,
    SupervisorAgent,
)
from app.agents.base import AgentOutputError
from app.core.config import get_settings
from app.core.execution_mode import execution_mode, is_mock_mode
from app.core.logging import get_logger, mask_text
from app.core.run_progress import ProgressCallback, emit_progress, progress_reporting
from app.core.schemas import EvidenceCard, PipelineState, QuestionItem, ResearchPlan, ScientificHypothesis
from app.workflow.artifacts import ArtifactManager, generate_run_id, resolve_artifact_base
from app.workflow.context_builder import ContextBuilder
from app.workflow.mock_outputs import PENDING_RESULTS, build_mock_evidence_cards
from app.workflow.quality_gates import run_all_quality_gates

# 模块级日志器。
logger = get_logger("workflow.pipeline")

# The public wrapper uses this context-local handle to persist partial state if
# any early Agent/client failure escapes before the normal artifact phase.
_ACTIVE_STATE: ContextVar[PipelineState | None] = ContextVar("sage125_active_state", default=None)

# 项目根与问题清单路径。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "questions_125.json"

# 校验状态的保守排序（数值越小越保守）。
_STATUS_RANK = {"needs_data": 0, "draft": 1, "ready_for_validation": 2, "validated": 3}


def _is_mock(mock_mode: Optional[bool]) -> bool:
    """判断是否 mock 模式：显式参数优先，否则看 MOCK_LLM 环境变量。"""
    return is_mock_mode(mock_mode)


def load_question(question_id: str) -> dict:
    """
    从 questions_125.json 加载指定 question_id 的问题。

    参数：
        question_id: 问题 ID（如 "Q001"）。

    返回：
        QuestionItem 兼容 dict。

    异常：
        FileNotFoundError: questions_125.json 缺失。
        ValueError:        question_id 不存在。
    """
    # 问题清单必须已由 extract_125_questions.py 生成。
    if not QUESTIONS_PATH.exists():
        raise FileNotFoundError(
            "缺少 data/processed/questions_125.json，请先运行 python scripts/extract_125_questions.py。"
        )
    items = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    for it in items:
        if it.get("id") == question_id:
            return it
    # 未找到给出清晰错误。
    raise ValueError(f"question_id 不存在：{question_id}")


def _conservative_status(a: str, b: str) -> str:
    """返回两个校验状态中更保守者。"""
    # 取排序较小者（更保守）。
    return a if _STATUS_RANK.get(a, 0) <= _STATUS_RANK.get(b, 0) else b


def _to_evidence_objs(cards: list) -> list[EvidenceCard]:
    """将 dict/对象混合的证据列表统一为 EvidenceCard 对象。"""
    out: list[EvidenceCard] = []
    for c in cards:
        if isinstance(c, EvidenceCard):
            out.append(c)
        elif isinstance(c, dict):
            try:
                out.append(EvidenceCard(**c))
            except Exception:
                continue
    return out


def _gather_real_evidence(state, qplan: dict, exec_plan: dict, settings) -> list[EvidenceCard]:
    """
    真实模式下从 LocalRAG / OpenLiterature 收集证据（失败仅告警，不终止）。

    参数：
        state:     流水线状态。
        qplan:     QueryPlanResult dict。
        exec_plan: Supervisor 的执行计划。
        settings:  配置。

    返回：
        EvidenceCard 列表。
    """
    evidence: list[EvidenceCard] = []
    queries = qplan.get("queries", [])

    # 1) Local RAG。
    if exec_plan.get("use_local_rag"):
        try:
            from app.clients.embedding_client import EmbeddingClient
            from app.clients.rerank_client import RerankClient
            from app.rag.library_manager import USER_LIBRARY_ZVEC_DIR
            from app.rag.retriever import LocalRAGRetriever
            from app.rag.zvec_store import get_vector_store

            # 题源 sjtu-booklet.pdf 与用户文献使用完全独立的索引目录。
            retriever = LocalRAGRetriever(
                EmbeddingClient(settings),
                RerankClient(settings),
                get_vector_store(index_dir=str(USER_LIBRARY_ZVEC_DIR)),
            )
            for q in [x for x in queries if x.get("source_preference") == "local_rag"]:
                evidence += retriever.retrieve(
                    q.get("query", ""),
                    filters={"source_role": "user_literature"},
                    source_scope="user_upload",
                )
        except Exception as exc:
            state.warnings.append("rag_failed")
            logger.warning("Local RAG 失败（继续）：%s", exc)

    # 3) Open literature（arXiv/OpenAlex/Crossref）。
    if exec_plan.get("use_open_literature"):
        try:
            from app.rag.open_literature_retriever import OpenLiteratureRetriever

            # Preserve source_preference. Previously only query strings were
            # passed, causing every query to hit all three providers and mixing
            # unrelated keyword collisions into the evidence wall.
            lit_queries = [
                x for x in queries
                if x.get("source_preference") in ("arxiv", "openalex", "crossref")
            ]
            if lit_queries:
                evidence += OpenLiteratureRetriever(settings).search(lit_queries, max_results_per_query=3)
        except Exception as exc:
            state.warnings.append("open_literature_failed")
            logger.warning("OpenLiterature 失败（继续）：%s", exc)

    return evidence


def _evidence_catalog(evidence_pool: list[EvidenceCard], limit: int = 30) -> list[dict]:
    """
    将 EvidenceCard 序列化为 Agent 可消费的轻量目录（不含长 quoted_text）。

    参数：
        evidence_pool: 已检索证据池。
        limit:         最多条目数，避免 prompt 过长。

    返回：
        含 id/title/source_type/doi/url 等字段的 dict 列表。
    """
    catalog: list[dict] = []
    for card in evidence_pool[:limit]:
        catalog.append(
            {
                "id": card.id,
                "title": card.title,
                "source_type": card.source_type,
                "doi": card.doi,
                "url": card.url,
                "year": card.year,
                "relevance_score": card.relevance_score,
            }
        )
    return catalog


def _recommended_hypothesis(hyp_result: dict | None) -> dict:
    """从 HypothesisGenerationResult 提取推荐假设 dict。"""
    hyp_result = hyp_result or {}
    hyps = hyp_result.get("hypotheses") or []
    idx = hyp_result.get("recommended_hypothesis_index", 0)
    if hyps and 0 <= idx < len(hyps):
        return hyps[idx]
    return hyps[0] if hyps else {}


def _experiment_designer_input(state: PipelineState, qdict: dict) -> dict:
    """
    构造 ExperimentDesigner 完整输入（真实模式必须含假设与证据，不能只传 question_item）。

    参数：
        state:  流水线状态。
        qdict:  问题 dict。

    返回：
        Agent 输入 dict。
    """
    parsed = state.parsed_question or {}
    return {
        "question_item": qdict,
        "question_type": parsed.get("question_type", ""),
        "recommended_hypothesis": _recommended_hypothesis(state.hypothesis_generation),
        "hypothesis_generation": state.hypothesis_generation,
        "evidence_extraction": state.evidence_extraction,
        "evidence_catalog": _evidence_catalog(state.retrieved_evidence),
    }


def _reviewer_input(state: PipelineState, qdict: dict) -> dict:
    """
    构造 ScientificReviewer 完整输入。

    参数：
        state:  流水线状态。
        qdict:  问题 dict。

    返回：
        Agent 输入 dict。
    """
    return {
        "question_item": qdict,
        "recommended_hypothesis": _recommended_hypothesis(state.hypothesis_generation),
        "hypothesis_generation": state.hypothesis_generation,
        "experiment_design": state.experiment_design,
        "evidence_extraction": state.evidence_extraction,
        "evidence_catalog": _evidence_catalog(state.retrieved_evidence),
    }


def _resolve_references(ref_ids: list[str], evidence_pool: list[EvidenceCard]) -> list[EvidenceCard]:
    """
    由 ReportWriter 的 reference_ids 解析 references；无效时从证据池回填。

    参数：
        ref_ids:        ReportWriter 输出的证据 ID 列表。
        evidence_pool:  流水线已收集的真实 EvidenceCard 池。

    返回：
        用于 ResearchPlan.references 的证据列表（均来自 evidence_pool，不伪造）。
    """
    id_map = {c.id: c for c in evidence_pool}
    references = [id_map[r] for r in ref_ids if r in id_map]
    if not references and evidence_pool:
        references = list(evidence_pool)[:20]
    return references


def _build_research_plan(
    draft: dict,
    evidence_pool: list[EvidenceCard],
    exec_meta: dict,
    status: str,
    revision_history: list[str],
    hypothesis_result: dict | None = None,
) -> ResearchPlan:
    """
    由 ReportWriter 草稿与证据池组装最终 ResearchPlan（references 绑定真实证据）。

    参数：
        draft:            ReportWriter 输出的草稿 dict（含 reference_ids）。
        evidence_pool:    证据池（EvidenceCard 列表）。
        exec_meta:        实验执行元数据（含 actual_execution）。
        status:           目标 validation_status。
        revision_history: 修订历史。

    返回：
        构造好的 ResearchPlan。
    """
    # references 仅来自证据池；ReportWriter 通过 reference_ids 引用。
    ref_ids = draft.get("reference_ids", []) or []
    references = _resolve_references(ref_ids, evidence_pool)

    # 假设草稿 -> ScientificHypothesis。
    hyps: list[ScientificHypothesis] = []
    source_hypotheses = (hypothesis_result or {}).get("hypotheses") or draft.get("generated_hypotheses", []) or []
    for h in source_hypotheses:
        try:
            hyps.append(
                ScientificHypothesis(
                    hypothesis=h.get("hypothesis", ""),
                    mechanism=h.get("mechanism", ""),
                    falsifiable_prediction=h.get("falsifiable_prediction", ""),
                    required_observations=h.get("required_observations", []),
                    risk_of_being_wrong=h.get("risk_of_being_wrong", ""),
                    supporting_evidence_ids=h.get("supporting_evidence_ids", []),
                    contradicted_by_evidence_ids=h.get("contradicted_by_evidence_ids", []),
                )
            )
        except Exception:
            continue

    actual_execution = bool(exec_meta.get("actual_execution"))
    results = draft.get("results", "") or ""
    # 无引用时降级为 needs_data，并写入占位说明以满足 ResearchPlan 校验。
    if not references:
        status = "needs_data"
        if not any(kw in results for kw in ("待检索", "待验证")):
            results = "references 待检索/待验证。" + PENDING_RESULTS

    return ResearchPlan(
        input_question=draft.get("input_question", ""),
        domain=draft.get("domain", "Unknown"),
        problem_statement=draft.get("problem_statement", ""),
        rationale=draft.get("rationale", ""),
        generated_hypotheses=hyps,
        technical_details=draft.get("technical_details", ""),
        datasets=draft.get("datasets", {}),
        paper_title=draft.get("paper_title", ""),
        paper_abstract=draft.get("paper_abstract", ""),
        methods=draft.get("methods", ""),
        experiments=draft.get("experiments", {}),
        results=results,
        references=references,
        reviewer_comments=draft.get("reviewer_comments", []),
        revision_history=revision_history,
        reproducibility_checklist=draft.get("reproducibility_checklist", []),
        validation_status=status,
        actual_execution=actual_execution,
    )


def _run_pipeline_with_state_impl(
    question_id: str,
    user_files: Optional[list[str]] = None,
    user_feedback: Optional[str] = None,
    use_local_rag: bool = True,
    use_deep_research: bool = True,
    use_open_literature: bool = True,
    reviewer_auto_revision: bool = True,
    mock_mode: Optional[bool] = None,
) -> tuple[ResearchPlan, PipelineState]:
    """
    运行完整多智能体流水线，返回 (ResearchPlan, PipelineState)。

    参数：见 run_pipeline。

    返回：
        (最终 ResearchPlan, 完整 PipelineState)。
    """
    settings = get_settings()
    mock = _is_mock(mock_mode)
    export_base = resolve_artifact_base(settings.export_dir)
    emit_progress("initializing", status="running", message="正在初始化 AI Scientist 运行环境")

    # 先加载问题（关键错误尽早抛出，避免创建无效导出目录）。
    qdict = load_question(question_id)
    qitem = QuestionItem(**qdict)

    run_id = generate_run_id()
    # 预创建导出目录。
    artifact_manager = ArtifactManager(run_id, base_dir=export_base)
    state = PipelineState(
        run_id=run_id, selected_question=qitem, user_files=user_files or [],
        mock_mode=mock, run_mode=("mock" if mock else "real"),
    )
    _ACTIVE_STATE.set(state)
    artifact_manager.save_started(state)
    if user_feedback:
        # 用户反馈只作为偏好记录，不进入事实。
        state.reviewer_feedback.append(user_feedback)

    step = 0

    # 1) Supervisor：生成执行计划。
    emit_progress("supervisor", status="running", message="正在规划多智能体执行路径")
    supervisor = SupervisorAgent(settings)
    strategy = supervisor.run(
        {"switches": {
            "use_local_rag": use_local_rag, "use_deep_research": use_deep_research,
            "use_open_literature": use_open_literature, "reviewer_auto_revision": reviewer_auto_revision,
            "mock_mode": mock,
        }},
        state, step,
    )
    step += 1
    exec_plan = strategy["execution_plan"]

    # 2) QuestionParser。
    parsed = QuestionParserAgent(settings).run({"question_item": qdict, "user_feedback": user_feedback}, state, step)
    step += 1
    state.parsed_question = parsed
    if parsed.get("suspected_domain_mismatch"):
        state.domain_warning = f"suspected_domain_mismatch (confidence={parsed.get('domain_confidence')})"
        if "suspected_domain_mismatch" not in state.warnings:
            state.warnings.append("suspected_domain_mismatch")

    # 3) QueryPlanner。
    qplan = QueryPlannerAgent(settings).run({"question_item": qdict, "parsed_question": parsed}, state, step)
    step += 1
    state.query_plan = qplan

    # 4-6) 证据收集：Local RAG / DeepResearch / OpenLiterature。
    emit_progress("retrieval", status="running", message="正在检索本地资料与开放文献")
    evidence: list[EvidenceCard] = []
    if mock:
        # mock：以稳定 mock 证据代表 RAG/文献结果（明确标记 mock_for_testing）。
        evidence = _to_evidence_objs(build_mock_evidence_cards(qdict))
    else:
        evidence = _gather_real_evidence(state, qplan, exec_plan, settings)

    # 5) DeepResearchAgent（永不中断；失败记 warning）。
    if exec_plan.get("use_deep_research"):
        emit_progress(
            "deep_research", status="connecting", message="正在连接千问 DeepResearch",
            model_alias="deepresearch", model_name_internal=settings.qwen_deep_research_model,
        )
        dr_result = DeepResearchAgent(settings).run(
            {"topic": parsed.get("core_question", qdict.get("question", "")), "context": parsed.get("scientific_boundary", "")},
            state, step,
        )
        step += 1
        # 合并深度研究产出的证据（需下游核验）。
        evidence += _to_evidence_objs(dr_result.get("evidence_cards", []))

    # 证据去重并写入状态。
    try:
        from app.rag.evidence import evidence_deduplicate

        evidence = evidence_deduplicate(evidence)
    except Exception:
        pass
    state.retrieved_evidence = evidence
    if not evidence:
        state.evidence_insufficient = True
        if "evidence_empty" not in state.warnings:
            state.warnings.append("evidence_empty")

    # 8) EvidenceExtractor。
    try:
        extraction = EvidenceExtractorAgent(settings).run(
            {"question_item": qdict, "evidence_catalog": _evidence_catalog(evidence)},
            state,
            step,
        )
        state.evidence_extraction = extraction
        state.extracted_facts = [f.get("fact", "") for f in extraction.get("established_facts", [])]
        state.knowledge_gaps = [g.get("gap", "") for g in extraction.get("knowledge_gaps", [])]
        if not extraction.get("established_facts"):
            state.evidence_insufficient = True
    except AgentOutputError:
        state.evidence_insufficient = True
    step += 1

    # 9) HypothesisGenerator。
    hyp_result = HypothesisGeneratorAgent(settings).run(
        {
            "question_item": qdict,
            "evidence_catalog": _evidence_catalog(state.retrieved_evidence),
            "evidence_extraction": state.evidence_extraction,
        },
        state,
        step,
    )
    step += 1
    state.hypothesis_generation = hyp_result
    # 记录候选假设到 state.hypotheses（ScientificHypothesis）。
    state.hypotheses = []
    for h in hyp_result.get("hypotheses", []):
        try:
            state.hypotheses.append(
                ScientificHypothesis(
                    hypothesis=h.get("hypothesis", ""), mechanism=h.get("mechanism", ""),
                    falsifiable_prediction=h.get("falsifiable_prediction", ""),
                    required_observations=h.get("required_observations", []),
                    risk_of_being_wrong=h.get("risk_of_being_wrong", ""),
                )
            )
        except Exception:
            continue

    # 10) ExperimentDesigner（必须传入假设+证据，否则真实 Qwen 易回显 question_item 导致校验失败）。
    exp_result = ExperimentDesignerAgent(settings).run(_experiment_designer_input(state, qdict), state, step)
    step += 1
    state.experiment_design = exp_result
    state.execution_metadata = exp_result.get("execution_metadata", {})

    # 11) ScientificReviewer（最多 1 次自动修订）。
    review = ScientificReviewerAgent(settings).run(_reviewer_input(state, qdict), state, step)
    step += 1
    state.review_result = review
    if (not review.get("passed")) and reviewer_auto_revision and not state.revision_history:
        # 记录一次自动修订，重跑假设与实验，再评审一次（严格上限 1 次）。
        state.revision_history.append("auto_revision_1: 依据评审意见重做假设与实验设计。")
        hyp_result = HypothesisGeneratorAgent(settings).run(
            {
                "question_item": qdict,
                "evidence_catalog": _evidence_catalog(state.retrieved_evidence),
                "evidence_extraction": state.evidence_extraction,
            },
            state,
            step,
        )
        step += 1
        state.hypothesis_generation = hyp_result
        exp_result = ExperimentDesignerAgent(settings).run(_experiment_designer_input(state, qdict), state, step)
        step += 1
        state.experiment_design = exp_result
        state.execution_metadata = exp_result.get("execution_metadata", {})
        review = ScientificReviewerAgent(settings).run(_reviewer_input(state, qdict), state, step)
        step += 1
        state.review_result = review

    # 12) ReportWriter：生成草稿（含 reference_ids）。
    draft = ReportWriterAgent(settings).run(
        {
            "question_item": qdict,
            "parsed_question": state.parsed_question,
            "evidence_catalog": _evidence_catalog(state.retrieved_evidence),
            "evidence_extraction": state.evidence_extraction,
            "hypothesis_generation": state.hypothesis_generation,
            "experiment_design": state.experiment_design,
            "review_result": state.review_result,
        },
        state,
        step,
    )
    step += 1
    # 用最新实验设计覆盖草稿的实验/结果字段，保证 pending 不变量。
    draft["experiments"] = exp_result.get("experiments", draft.get("experiments", {}))
    draft["datasets"] = exp_result.get("datasets", draft.get("datasets", {}))
    draft["results"] = exp_result.get("results", draft.get("results", ""))
    draft["technical_details"] = exp_result.get("technical_details", draft.get("technical_details", ""))
    draft["reproducibility_checklist"] = exp_result.get("reproducibility_checklist", draft.get("reproducibility_checklist", []))
    draft["reviewer_comments"] = review.get("reviewer_comments", [])

    # 计算初步 validation_status。
    exec_meta = exp_result.get("execution_metadata", {})
    if not state.retrieved_evidence:
        tentative = "needs_data"
    elif state.evidence_insufficient:
        tentative = "draft"
    else:
        tentative = "ready_for_validation"

    # 构建 ResearchPlan。
    plan = _build_research_plan(
        draft,
        state.retrieved_evidence,
        exec_meta,
        tentative,
        state.revision_history,
        hypothesis_result=state.hypothesis_generation,
    )

    # 13) 质量门。
    gates = run_all_quality_gates(
        plan,
        state.retrieved_evidence,
        state.agent_trace,
        hypothesis_generation=state.hypothesis_generation,
        evidence_extraction=state.evidence_extraction,
    )
    state.quality_gates = gates
    final_status = tentative
    # 质量门未过则下调 ready_for_validation -> draft。
    if not gates["passed"] and final_status == "ready_for_validation":
        final_status = "draft"

    # SchemaValidatorAgent（补充判定；取更保守者）。
    validation = SchemaValidatorAgent(settings).run({"question_item": qdict}, state, step)
    step += 1
    state.validation_result = validation
    final_status = _conservative_status(final_status, validation.get("validation_status", "draft"))
    # 无真实实验绝不 validated。
    if not exec_meta.get("actual_execution") and final_status == "validated":
        final_status = "ready_for_validation"
    # 应用最终状态（不触发 pydantic 重新校验；仅赋值）。
    plan.validation_status = final_status  # type: ignore[assignment]
    # 绑定 question_id（选题-报告一致性权威来源为选中问题）。
    plan.question_id = qitem.id  # type: ignore[assignment]
    plan.input_question = qitem.question  # type: ignore[assignment]
    state.final_plan = plan

    # 14) 保存上下文包与全部 artifacts。
    emit_progress("artifacts", status="running", message="正在保存报告、证据链与运行审计")
    ContextBuilder().save_context_pack(run_id, state, base_dir=export_base)
    ArtifactManager(run_id, base_dir=export_base).save_all(state, plan, gates)

    logger.info("pipeline 完成：run_id=%s，status=%s，evidence=%d", run_id, final_status, len(state.retrieved_evidence))
    emit_progress("completed", status="completed", percent=100, message="AI Scientist 运行完成")
    return plan, state


def run_pipeline_with_state(
    question_id: str,
    user_files: Optional[list[str]] = None,
    user_feedback: Optional[str] = None,
    use_local_rag: bool = True,
    use_deep_research: bool = True,
    use_open_literature: bool = True,
    reviewer_auto_revision: bool = True,
    mock_mode: Optional[bool] = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[ResearchPlan, PipelineState]:
    """Run the pipeline in an isolated mode/progress context and persist failures."""
    resolved_mock = _is_mock(mock_mode)
    active_token = _ACTIVE_STATE.set(None)
    try:
        with execution_mode(resolved_mock), progress_reporting(progress_callback):
            try:
                return _run_pipeline_with_state_impl(
                    question_id=question_id,
                    user_files=user_files,
                    user_feedback=user_feedback,
                    use_local_rag=use_local_rag,
                    use_deep_research=use_deep_research,
                    use_open_literature=use_open_literature,
                    reviewer_auto_revision=reviewer_auto_revision,
                    mock_mode=resolved_mock,
                )
            except Exception as exc:
                state = _ACTIVE_STATE.get()
                if state is not None:
                    masked = mask_text(str(exc))
                    if masked and all(masked not in item for item in state.errors):
                        state.errors.append(masked)
                    try:
                        ArtifactManager(
                            state.run_id,
                            base_dir=resolve_artifact_base(get_settings().export_dir),
                        ).save_failure(state, exc)
                    except Exception as artifact_exc:
                        logger.warning("失败状态落盘失败：%s", artifact_exc)
                    try:
                        setattr(exc, "run_id", state.run_id)
                    except Exception:
                        pass
                emit_progress("failed", status="failed", message=f"运行失败：{mask_text(str(exc))[:180]}")
                raise
    finally:
        _ACTIVE_STATE.reset(active_token)


def run_pipeline(
    question_id: str,
    user_files: Optional[list[str]] = None,
    user_feedback: Optional[str] = None,
    use_local_rag: bool = True,
    use_deep_research: bool = True,
    use_open_literature: bool = True,
    reviewer_auto_revision: bool = True,
    mock_mode: Optional[bool] = None,
) -> ResearchPlan:
    """
    运行完整多智能体流水线并返回最终 ResearchPlan。

    参数：
        question_id:            问题 ID（如 "Q001"）。
        user_files:             可选用户上传文件路径（仅本地索引）。
        user_feedback:          可选用户反馈（仅作偏好）。
        use_local_rag:          是否启用本地 RAG。
        use_deep_research:      是否启用深度研究。
        use_open_literature:    是否启用公开文献检索。
        reviewer_auto_revision: 评审未过时是否自动修订（最多 1 次）。
        mock_mode:              是否 mock；None 时看 MOCK_LLM。

    返回：
        最终 ResearchPlan。
    """
    plan, _state = run_pipeline_with_state(
        question_id, user_files, user_feedback, use_local_rag, use_deep_research,
        use_open_literature, reviewer_auto_revision, mock_mode,
    )
    return plan


# 拒绝的非法反馈关键词（编造结果/去引用/强行 validated）。
_ILLEGAL_FEEDBACK = ("编造", "伪造", "去掉引用", "删除引用", "去除引用", "标记为 validated", "设为 validated", "标为 validated")


def revise_with_feedback(
    run_id: str,
    feedback: str,
    reviewer_auto_revision: bool = True,
) -> ResearchPlan:
    """
    基于用户反馈对既有运行进行修订，生成新版本（不覆盖原始 run）。

    参数：
        run_id:                 原始运行 ID。
        feedback:               用户反馈（仅作偏好，不作事实）。
        reviewer_auto_revision: 是否允许评审自动修订。

    返回：
        修订后的 ResearchPlan。

    异常：
        ValueError:        非法反馈（要求造假/去引用/强行 validated）被拒绝，或运行不存在。
        FileNotFoundError: 原始 artifacts 缺失。
    """
    # 拒绝违反科学诚信的反馈。
    if any(bad in feedback for bad in _ILLEGAL_FEEDBACK):
        raise ValueError("拒绝该反馈：不得编造结果、删除引用或在无真实实验时标记 validated。")

    run_dir = resolve_artifact_base(get_settings().export_dir) / run_id
    ctx_path = run_dir / "context_pack.json"
    ev_path = run_dir / "evidence_cards.json"
    report_path = run_dir / "report.json"
    if not report_path.exists() or not ctx_path.exists():
        raise FileNotFoundError(f"原始运行产物缺失：{run_dir}")

    # 读取上下文包与证据。
    ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
    old_report = json.loads(report_path.read_text(encoding="utf-8"))
    evidence = _to_evidence_objs(json.loads(ev_path.read_text(encoding="utf-8"))) if ev_path.exists() else []

    # 从上下文包恢复选中问题。
    sq = ctx.get("selected_question", {})
    qdict = {
        "id": sq.get("id", "Q000"),
        "domain": sq.get("domain", "Unknown"),
        "question": sq.get("question", old_report.get("input_question", "")),
        "source_page": None,
        "booklet_excerpt": sq.get("booklet_excerpt"),
        "metadata": sq.get("metadata", {}),
    }
    qitem = QuestionItem(**qdict)

    settings = get_settings()
    # 新建状态，沿用原 run_id 下的 revisions 子目录。
    state = PipelineState(run_id=run_id, selected_question=qitem, mock_mode=_is_mock(None))
    state.retrieved_evidence = evidence
    # 反馈进入修订历史（before 摘要），不进入事实。
    before_summary = f"before: status={old_report.get('validation_status')}, hypotheses={len(old_report.get('generated_hypotheses', []))}"
    state.revision_history = list(old_report.get("revision_history", []))
    state.reviewer_feedback.append(feedback)

    step = 0
    # 依据反馈决定重跑范围（简化：统一重做假设->实验->评审->报告，保证一致性）。
    hyp_result = HypothesisGeneratorAgent(settings).run(
        {
            "question_item": qdict,
            "evidence_catalog": _evidence_catalog(state.retrieved_evidence),
            "evidence_extraction": state.evidence_extraction,
        },
        state,
        step,
    )
    step += 1
    state.hypothesis_generation = hyp_result
    exp_result = ExperimentDesignerAgent(settings).run(_experiment_designer_input(state, qdict), state, step)
    step += 1
    state.experiment_design = exp_result
    review = ScientificReviewerAgent(settings).run(_reviewer_input(state, qdict), state, step)
    state.review_result = review
    draft = ReportWriterAgent(settings).run({"question_item": qdict}, state, step); step += 1
    draft["experiments"] = exp_result.get("experiments", {})
    draft["datasets"] = exp_result.get("datasets", {})
    draft["results"] = exp_result.get("results", "")
    draft["reproducibility_checklist"] = exp_result.get("reproducibility_checklist", [])

    exec_meta = exp_result.get("execution_metadata", {})
    tentative = "ready_for_validation" if state.retrieved_evidence else "needs_data"
    # 追加 before/after 摘要到修订历史。
    revision_note = f"{before_summary}; feedback='{feedback[:80]}'"
    state.revision_history.append(revision_note)
    plan = _build_research_plan(
        draft,
        state.retrieved_evidence,
        exec_meta,
        tentative,
        state.revision_history,
        hypothesis_result=state.hypothesis_generation,
    )

    gates = run_all_quality_gates(
        plan,
        state.retrieved_evidence,
        state.agent_trace,
        hypothesis_generation=state.hypothesis_generation,
        evidence_extraction=state.evidence_extraction,
    )
    final_status = tentative if gates["passed"] else "draft"
    if not exec_meta.get("actual_execution") and final_status == "validated":
        final_status = "ready_for_validation"
    plan.validation_status = final_status  # type: ignore[assignment]
    state.final_plan = plan

    # 保存到 revisions/{revision_id}/，不覆盖原始 run。
    revision_id = generate_run_id()
    revision_dir = run_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True, exist_ok=True)
    (revision_dir / "report.json").write_text(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (revision_dir / "agent_trace.json").write_text(json.dumps(state.agent_trace, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("修订完成：run_id=%s，revision_id=%s，status=%s", run_id, revision_id, final_status)
    return plan
