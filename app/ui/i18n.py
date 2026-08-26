"""
app.ui.i18n —— 前端界面中文显示层的集中映射。

设计原则：
    - 只做"显示"层的中英映射，绝不修改业务对象、后端枚举或内部稳定值；
    - 未知 key/value 一律安全回退为原始输入（英文原文或 key 本身），不返回空串；
    - 中文显示值只用于渲染，不得回写 API、不得作为查询/存储用的稳定值；
    - 不翻译：Q001—Q125 题目正文、外文文献标题、期刊名、作者、DOI、URL、
      run_id/question_id/evidence_id/execution_id、API 路径与 JSON 字段、
      Developer Diagnostics 中的底层技术值（模型代号等）。

用法：
    from app.ui.i18n import ui_text, domain_label, status_label, stage_label,
        preset_label, source_type_label
"""

from __future__ import annotations

# ============================================================
# 通用界面文案（含侧边栏）：英文原文 -> 简体中文。
# 只用于普通用户可见的控件标题、按钮、说明文字等界面壳层。
# ============================================================
UI_TEXT_ZH: dict[str, str] = {
    # 侧边栏。
    "mode_control": "运行模式",
    "mock_mode": "模拟演示",
    "real_mode": "真实运行",
    "system_status": "系统状态",
    "pipeline_switches": "高级能力设置",
    "demo_presets": "快速示例",
    "security_note_title": "安全说明",
    # 首次运行向导 / 问题选择。
    "first_run_wizard": "首次运行向导",
    "first_run_wizard_subtitle": "第一次打开？按向导确认系统就绪并一键演示。",
    "select_a_scientific_question": "选择科学问题",
    "select_a_scientific_question_subtitle": "从 125 个前沿科学问题中选择研究起点。",
    "questions_125": "125 题题库",
    "api_server": "API 服务",
    "latest_run": "最近运行",
    "keyword_search": "关键词搜索",
    "domain_filter": "领域筛选",
    "all_domains": "全部",
    "current_research_question": "当前研究问题",
    # 分区标题（STEP 0X）。
    "step_setup": "准备",
    "step_01": "步骤 01",
    "step_02": "步骤 02",
    "step_03": "步骤 03",
    "step_04": "步骤 04",
    "step_05": "步骤 05",
    "step_06": "步骤 06",
    "step_07": "步骤 07",
    "step_08": "步骤 08",
    "data_rag_workspace": "数据与文献检索工作区",
    "ai_scientist_run_console": "AI 科学家运行控制台",
    "agent_observatory": "智能体观测台",
    "evidence_wall": "文献证据墙",
    "researchplan_studio": "研究计划工作室",
    "human_feedback_bench": "人工反馈工作台",
    "researchplan_export_center": "研究计划导出中心",
    # 图表标题。
    "domain_coverage_chart": "125 个科学问题 · 领域分布",
    "knowledge_graph": "科研证据链",
    "agent_pipeline_timeline": "智能体流程耗时",
    "evidence_source_distribution": "证据来源分布",
    "relevance_score_distribution": "相关性分布",
    # 科研证据链五阶段。
    "flow_question": "科学问题",
    "flow_evidence": "文献证据",
    "flow_hypothesis": "科学假设",
    "flow_experiment": "实验方案",
    "flow_report": "研究报告",
    # 开发者诊断 / 门禁 / 执行 / 多模态。
    "developer_diagnostics": "开发者诊断",
    "validation_gates": "验证门",
    "execution": "实验执行",
    "multimodal": "多模态结果",
    "scores": "评分",
    "from_version": "起始版本",
    "to_version": "目标版本",
}


# ============================================================
# 12 个赛题领域：内部英文 key 保持不变，仅显示层映射为中文。
# ============================================================
DOMAIN_DISPLAY_ZH: dict[str, str] = {
    "Mathematical Sciences": "数学科学",
    "Chemistry": "化学",
    "Medicine & Health": "医学与健康",
    "Biology": "生物学",
    "Astronomy": "天文学",
    "Physics": "物理学",
    "Engineering & Materials Science": "工程与材料科学",
    "Information Science": "信息科学",
    "Neuroscience": "神经科学",
    "Ecology": "生态学",
    "Energy Science": "能源科学",
    "Artificial Intelligence": "人工智能",
}


# ============================================================
# 运行 / 校验 / 执行状态显示映射（内部稳定值保持不变）。
# ============================================================
STATUS_DISPLAY_ZH: dict[str, str] = {
    "draft": "草稿",
    "needs_data": "需补充数据",
    "ready_for_validation": "待验证",
    "validated": "已验证",
    "pending": "等待",
    "running": "运行中",
    "completed": "已完成",
    "succeeded": "已实际执行",
    "failed": "执行失败",
    "skipped": "跳过",
    "planned": "计划中",
    "mock": "模拟演示",
    "actual": "已实际执行",
    "timed_out": "执行超时",
    "cancelled": "已取消",
    "rejected": "已拒绝",
    "not_available": "暂不可用",
}


# ============================================================
# 智能体流水线 / 运行阶段显示映射。
# ============================================================
STAGE_DISPLAY_ZH: dict[str, str] = {
    "preparing": "准备中",
    "preflight": "启动前检查",
    "queued": "已提交队列",
    "connecting": "连接中",
    "waiting": "等待中",
    "running": "运行中",
    "completed": "已完成",
    "failed": "失败",
    "supervisor": "监督调度",
    "question_parser": "问题解析",
    "query_planner": "检索规划",
    "deep_research": "深度调研",
    "evidence_extractor": "证据抽取",
    "hypothesis_generator": "假设生成",
    "experiment_designer": "实验设计",
    "scientific_reviewer": "审稿校验",
    "report_writer": "报告生成",
    "schema_validator": "结构校验",
}


# ============================================================
# 快速示例（原 Demo Presets）显示映射。内部稳定值为英文 key；
# 选择后仍通过既有关键词匹配逻辑定位到对应题目，不改变题库数据。
# ============================================================
PRESET_DISPLAY_ZH: dict[str, str] = {
    "prime": "素数",
    "pandemic": "疫情预测",
    "climate": "气候变化",
    "creativity": "AI 创造力",
    "quantum": "量子计算",
}

#: 快速示例内部 key -> 问题关键词（用于复用既有的关键词匹配逻辑）。
PRESET_KEYWORDS: dict[str, list[str]] = {
    "prime": ["prime"],
    "pandemic": ["pandemic"],
    "climate": ["climate"],
    "creativity": ["creativity"],
    "quantum": ["quantum"],
}


# ============================================================
# 证据来源类型显示映射。
# ============================================================
SOURCE_TYPE_DISPLAY_ZH: dict[str, str] = {
    "booklet": "题库原文",
    "rag": "本地文献检索",
    "deep_research": "深度调研",
    "arxiv": "arXiv",
    "crossref": "Crossref",
    "openalex": "OpenAlex",
    "user_upload": "用户上传",
    "unknown": "未知来源",
}


def ui_text(key: str) -> str:
    """
    返回界面壳层文案的中文显示值。

    参数：
        key: UI_TEXT_ZH 的键。

    返回：
        中文文案；key 未登记时原样返回 key 本身（不返回空串，不静默丢失文案）。
    """
    return UI_TEXT_ZH.get(key, key)


def domain_label(domain: str | None) -> str:
    """
    返回领域的中文显示名；内部领域 key（英文）保持不变，只用于显示。

    参数：
        domain: 内部领域英文 key（如 "Biology"）。

    返回：
        中文领域名；未登记的领域原样返回英文原值，不返回空串。
    """
    value = str(domain or "")
    return DOMAIN_DISPLAY_ZH.get(value, value)


def status_label(status: str | None) -> str:
    """返回状态的中文显示值；未知状态原样返回，不返回空串。"""
    value = str(status or "")
    return STATUS_DISPLAY_ZH.get(value, value)


def stage_label(stage: str | None) -> str:
    """返回流水线阶段/Agent 名的中文显示值；未知值原样返回，不返回空串。"""
    value = str(stage or "")
    return STAGE_DISPLAY_ZH.get(value, value)


def preset_label(preset_key: str | None) -> str:
    """返回快速示例的中文显示值；未知 key 原样返回，不返回空串。"""
    value = str(preset_key or "")
    return PRESET_DISPLAY_ZH.get(value, value)


def source_type_label(source_type: str | None) -> str:
    """返回证据来源类型的中文显示值；未知类型原样返回，不返回空串。"""
    value = str(source_type or "")
    return SOURCE_TYPE_DISPLAY_ZH.get(value, value)
