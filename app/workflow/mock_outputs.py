"""
app.workflow.mock_outputs —— MOCK_LLM=true 下的稳定、领域相关演示输出。

作用：
    在不调用真实百炼 API 的前提下，为每个 Agent 提供结构完整、可被 Pydantic
    校验的确定性输出，用于测试与答辩演示。

关键修复（P0-1 选题-报告一致性）：
    - 所有 mock 输出必须**围绕用户实际选择的问题**生成，严禁固定输出 pandemic；
    - 通过 _detect_topic 依据问题文本/领域选择领域相关内容包；
    - 未命中特定内容包时，回退到**由问题文本驱动**的通用模板（绝不 pandemic）。

安全与诚实：
    - mock 证据统一标记 "mock_for_testing"，不伪装成真实论文（doi/url 均为 null）；
    - Results 严格 pending；validation_status 不得为 validated。
"""

from __future__ import annotations

from typing import Any

# 无真实实验时 Results 必须写的标准 pending 句子（全项目统一复用）。
PENDING_RESULTS = (
    "当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。"
)

# mock 证据的稳定 ID（供各 mock 输出引用，保证证据链一致）。
MOCK_EVIDENCE_IDS = ["EV-MOCK-0001", "EV-MOCK-0002", "EV-MOCK-0003"]


# ============================================================
# 领域相关内容包：每个 topic 提供围绕该主题的完整可验证研究计划素材。
# 严禁跨主题污染（例如 prime 问题绝不出现 pandemic / zoonotic 内容）。
# ============================================================

def _prime_pack(q: str, domain: str) -> dict:
    """质数 / 密码学主题内容包。"""
    return {
        "keywords": ["prime gap statistics", "integer factorization", "primality testing", "cryptographic key size"],
        "entities": ["Riemann zeta zeros", "Miller-Rabin", "Pollard Rho", "ECM"],
        "question_type": "theoretical_proof",
        "scientific_boundary": "可对素数分布的统计规律与因数分解复杂度做可验证的经验刻画，但无法在本计划内给出解析层面的存在性证明。",
        "what_not_to_claim": ["不得声称证明了素数分布的解析猜想", "不得把统计相关性表述为数学定理"],
        "title": "素数分布统计与因数分解复杂度的可验证研究计划（演示）",
        "problem_statement": "将“质数为何特别”转化为可检验问题：素数间隔统计量、局部分布特征与生成函数统计量能否改进素性测试启发式与大数分解的密码参数风险评估。",
        "rationale": "素数在因数分解困难性上的独特性质是现代密码学安全假设的基础；对其分布统计的经验刻画可指导密钥长度与素性测试的工程选择。",
        "hypothesis": "某些素数间隔与局部分布统计特征可作为特征，改进素性测试的伪素数风险控制与大数分解启发式的运行时预测。",
        "mechanism": "素数间隔与 Riemann zeta 零点分布相关；将这些统计特征引入分类/回归可捕捉分解难度的结构信号。",
        "falsifiable_prediction": "在合成大整数基准上，引入素数间隔统计特征的模型对分解耗时的预测显著优于仅用位长的基线。",
        "required_observations": ["合成整数分解耗时", "素数间隔分布", "素性测试假阳性率"],
        "risk_of_being_wrong": "若统计特征相对位长基线无增益，则假设被削弱。",
        "technical_details": (
            "构造合成大整数基准（受控位长与素因子结构）；统计特征包含 prime gap statistics、"
            "Riemann zeta zeros correlation 代理量；baseline 涵盖 Miller-Rabin / AKS / Pollard Rho / ECM；"
            "评估 factorization time、primality test false-positive control、distributional distance 与 runtime scaling；"
            "并做 cryptographic key-size risk analysis。"
        ),
        "datasets": {
            "source": "合成大整数与其素因子结构基准（可脚本化生成，待构造）",
            "target": "分解耗时 / 素性测试结果标签（按位长与结构分层，待构造）",
        },
        "methods": "特征工程（素数间隔统计）+ 回归/分类 + 密码参数风险分析 + 复杂度经验拟合。",
        "experiments": {
            "baselines": ["位长基线", "Miller-Rabin", "Pollard Rho", "ECM"],
            "metrics": ["factorization time", "primality test false-positive rate", "distributional distance", "runtime scaling"],
            "ablation": ["移除素数间隔特征", "移除 zeta 相关代理量", "仅用位长"],
            "validation_protocol": "按位长分层的留出验证 + 合成基准可复现脚本。",
        },
        "ev_titles": [
            "[MOCK] 素数间隔分布与 zeta 零点相关性综述片段",
            "[MOCK] 大整数因数分解算法（Pollard Rho / ECM）复杂度分析摘要",
            "[MOCK] 素性测试与密码密钥长度风险评估调研纪要",
        ],
        "ev_quotes": [
            "素数间隔的统计分布与 Riemann zeta 函数零点存在深刻联系。（mock 原文片段）",
            "亚指数级因数分解算法的运行时对素因子结构与位长高度敏感。（mock 摘要片段）",
            "密钥长度选择需结合当前分解算法的经验运行时与安全裕度。（mock 调研纪要）",
        ],
    }


def _pandemic_pack(q: str, domain: str) -> dict:
    """大流行预测 / 公共卫生主题内容包（仅当问题确与 pandemic 相关时使用）。"""
    return {
        "keywords": ["zoonotic spillover", "land use change", "climate anomaly", "early warning"],
        "entities": ["One Health", "host-vector distribution", "surveillance"],
        "question_type": "extreme_event_prediction",
        "scientific_boundary": "可对外溢风险进行概率性早期预警，但无法精确预测具体时间地点。",
        "what_not_to_claim": ["不得声称能精确预测下一次大流行的时间与地点", "不得把相关性表述为因果"],
        "title": "面向动物源外溢风险的前瞻性时空早期预警：一个可验证研究计划（演示）",
        "problem_statement": "将“能否预测下一次大流行”转化为对动物源外溢风险的前瞻性概率预警问题。",
        "rationale": "基于环境扰动改变宿主-媒介-人接触界面的机制，结合多源代理变量进行时空建模。",
        "hypothesis": "土地利用变化、宿主/媒介分布改变、气候异常与人类活动代理变量的耦合，可提高未来 3–9 个月外溢风险可预测性。",
        "mechanism": "环境扰动提升溢出概率，多源代理变量捕捉时空信号。",
        "falsifiable_prediction": "前瞻外推下多源模型 Top-K 召回显著优于气候单变量基线。",
        "required_observations": ["历史外溢事件", "环境协变量", "前瞻窗口标签"],
        "risk_of_being_wrong": "若环境代理变量在时间外推下无增益，则假设被削弱。",
        "technical_details": (
            "构造网格化时空数据集，整合历史外溢事件与环境协变量（土地利用、气候异常、宿主分布代理）；"
            "特征工程包含滞后窗口与空间邻接；模型涵盖 Logistic Regression / Random Forest / LightGBM / ST-GNN；"
            "使用 SHAP 做可解释性；采用时间外推与空间外推双重划分。"
        ),
        "datasets": {
            "source": "历史外溢事件与环境协变量（公开数据整合，待检索/待构造）",
            "target": "前瞻窗口（3–9 个月）外溢发生标签（按时间切分构造，待构造）",
        },
        "methods": "监督学习 + 时空图建模 + 类别不平衡处理 + 可解释性分析。",
        "experiments": {
            "baselines": ["Logistic Regression", "Random Forest", "LightGBM"],
            "metrics": ["AUROC", "AUPRC", "Top-K hotspot recall", "Brier Score", "lead-time gain"],
            "ablation": ["移除气候异常特征", "移除土地利用特征", "移除时空结构"],
            "validation_protocol": "时间外推 + 空间外推（留一区域）+ 前瞻窗口评估。",
        },
        "ev_titles": [
            "[MOCK] Local RAG excerpt on land-use change and spillover risk",
            "[MOCK] Spatiotemporal early-warning modeling of zoonotic spillover",
            "[MOCK] DeepResearch survey summary on pandemic prediction",
        ],
        "ev_quotes": [
            "土地利用变化与宿主/媒介分布改变被关联到动物源传染病外溢风险上升。（mock 原文片段）",
            "时空机器学习模型可用环境扰动代理变量预测外溢热点，但缺乏前瞻验证。（mock 摘要片段）",
            "调研纪要指出 One Health 框架与多源数据融合是当前主流方向，需下游核验。（mock 调研纪要）",
        ],
    }


def _climate_pack(q: str, domain: str) -> dict:
    """气候 / 生态主题内容包。"""
    return {
        "keywords": ["climate variability", "ecosystem response", "carbon flux", "remote sensing"],
        "entities": ["ENSO", "biosphere-atmosphere exchange", "land cover"],
        "question_type": "mechanism_discovery",
        "scientific_boundary": "可对生态-气候耦合的统计关系做可验证刻画，但难以在单一计划内确立全球因果链。",
        "what_not_to_claim": ["不得把区域相关性外推为全球因果", "不得声称已闭合碳收支不确定性"],
        "title": f"围绕“{q[:40]}”的气候-生态耦合可验证研究计划（演示）",
        "problem_statement": f"将问题“{q}”转化为对气候变量与生态响应之间可检验统计关系的建模问题。",
        "rationale": "气候异常通过温度、降水与扰动影响生态系统功能，可用遥感与站点数据进行时空建模。",
        "hypothesis": "引入气候异常与遥感植被指数的耦合特征，可提高对生态响应变量的可预测性。",
        "mechanism": "气候异常改变水热条件，驱动植被与碳通量变化，遥感代理变量捕捉该过程。",
        "falsifiable_prediction": "融合气候异常与遥感特征的模型在留出年份上显著优于仅气候基线。",
        "required_observations": ["气候再分析数据", "遥感植被指数", "站点通量观测"],
        "risk_of_being_wrong": "若遥感特征在时间外推下无增益，则假设被削弱。",
        "technical_details": (
            "整合气候再分析（temperature/precipitation anomaly）与 remote sensing 植被/碳通量代理；"
            "特征含滞后与空间邻接；baseline 涵盖线性模型与梯度提升；做时间外推评估与不确定性量化。"
        ),
        "datasets": {
            "source": "气候再分析与遥感协变量（公开数据整合，待检索）",
            "target": "生态响应/碳通量观测标签（按时间切分，待构造）",
        },
        "methods": "时空回归 + 遥感特征工程 + 不确定性量化。",
        "experiments": {
            "baselines": ["气候单变量基线", "Random Forest", "Gradient Boosting"],
            "metrics": ["R2", "RMSE", "MAE", "distributional distance"],
            "ablation": ["移除遥感特征", "移除气候异常特征", "移除时空结构"],
            "validation_protocol": "留出年份时间外推 + 区域留一。",
        },
        "ev_titles": [
            "[MOCK] 气候异常与生态系统响应的耦合机制综述片段",
            "[MOCK] 遥感植被指数用于碳通量估计的方法学摘要",
            "[MOCK] 气候-生态建模不确定性调研纪要",
        ],
        "ev_quotes": [
            "气候异常通过水热条件变化显著影响生态系统功能。（mock 原文片段）",
            "遥感植被指数可作为碳通量估计的有效代理变量。（mock 摘要片段）",
            "生态-气候耦合模型需系统量化时空外推下的不确定性。（mock 调研纪要）",
        ],
    }


def _ai_pack(q: str, domain: str) -> dict:
    """人工智能 / 认知主题内容包。"""
    return {
        "keywords": ["generative models", "evaluation metrics", "novelty measurement", "human preference"],
        "entities": ["diffusion models", "LLM", "creativity metrics"],
        "question_type": "ai_scientist_meta",
        "scientific_boundary": "可对生成模型的新颖性/质量做可操作化度量，但“创造力”本身缺乏统一客观定义。",
        "what_not_to_claim": ["不得声称已客观定义创造力", "不得将偏好评分等同于真实创造力"],
        "title": f"围绕“{q[:40]}”的生成模型可验证评测研究计划（演示）",
        "problem_statement": f"将问题“{q}”转化为对生成模型新颖性与质量的可操作化度量与验证问题。",
        "rationale": "创造力难以直接定义，但可通过新颖性、质量与人类偏好的多维代理指标进行可验证评测。",
        "hypothesis": "结合分布新颖性与人类偏好的复合指标，比单一相似度更能区分高质量生成结果。",
        "mechanism": "复合指标同时刻画与训练分布的距离和人类可接受度，减少单一指标的偏置。",
        "falsifiable_prediction": "复合指标与人类评分的相关性显著高于单一相似度指标。",
        "required_observations": ["生成样本", "人类偏好标注", "分布统计"],
        "risk_of_being_wrong": "若复合指标与人类评分相关性不优于单一指标，则假设被削弱。",
        "technical_details": (
            "构造生成样本集与 human preference 标注；novelty measurement 采用分布距离与最近邻新颖性；"
            "baseline 含单一相似度与偏好模型；评估指标与人类评分相关性、区分度与稳定性。"
        ),
        "datasets": {
            "source": "生成模型样本与提示集（可脚本化生成，待构造）",
            "target": "人类偏好/质量标注（受控标注，待构造）",
        },
        "methods": "指标构造 + 相关性分析 + 消融与稳定性检验。",
        "experiments": {
            "baselines": ["单一相似度指标", "偏好模型打分", "随机基线"],
            "metrics": ["Spearman correlation", "ranking accuracy", "distributional distance", "stability"],
            "ablation": ["移除新颖性项", "移除偏好项", "移除分布项"],
            "validation_protocol": "多标注者一致性 + 留出提示集外推。",
        },
        "ev_titles": [
            "[MOCK] 生成模型新颖性度量方法综述片段",
            "[MOCK] 人类偏好评测与自动指标相关性研究摘要",
            "[MOCK] 生成式 AI 评测基准调研纪要",
        ],
        "ev_quotes": [
            "生成模型的新颖性可通过与训练分布的距离进行操作化度量。（mock 原文片段）",
            "自动指标与人类偏好的相关性是评测有效性的关键。（mock 摘要片段）",
            "现有生成式评测缺乏统一、可复现的创造力度量基准。（mock 调研纪要）",
        ],
    }


def _generic_pack(q: str, domain: str) -> dict:
    """
    通用回退内容包：完全由问题文本驱动，绝不引入其它主题（尤其禁止 pandemic）。
    """
    short = (q or "该科学问题").strip()
    return {
        "keywords": ["mechanism", "measurement", "dataset", "validation"],
        "entities": ["baseline model", "public dataset", "evaluation protocol"],
        "question_type": "general_scientific_unknown",
        "scientific_boundary": f"可将“{short}”转化为可检验的经验假设与验证计划，但不在本计划内给出终极结论。",
        "what_not_to_claim": ["不得把相关性表述为因果", "不得在无真实实验时给出量化结论"],
        "title": f"围绕“{short[:44]}”的可验证科学假设与研究计划（演示）",
        "problem_statement": f"将科学问题“{short}”拆解为可操作化的变量、可检验的假设与可复现的验证实验。",
        "rationale": f"针对“{short}”，通过文献证据梳理机制线索，构造可测量的代理变量并设计可证伪的验证方案。",
        "hypothesis": f"针对“{short}”，存在一组可测量的代理变量，其组合可显著改善对目标结果的可预测性/可解释性。",
        "mechanism": "候选机制通过可观测代理变量与目标结果相联系，可用统计/机器学习模型进行检验。",
        "falsifiable_prediction": "引入候选特征的模型在留出集上显著优于朴素基线；若无增益则假设被削弱。",
        "required_observations": ["相关公开数据", "目标结果标签", "候选特征观测"],
        "risk_of_being_wrong": "候选代理变量可能与目标结果无稳定关联，需以留出验证证伪。",
        "technical_details": (
            f"围绕“{short}”构造数据集与 measurement 方案；特征工程基于领域先验；"
            "baseline 涵盖线性模型与梯度提升；采用留出/时间或分组外推做 validation；量化不确定性并做消融。"
        ),
        "datasets": {
            "source": "与问题相关的公开数据整合（待检索/待构造）",
            "target": "目标结果标签（按合理协议切分，待构造）",
        },
        "methods": "特征工程 + 监督学习 + 消融与外推验证 + 不确定性量化。",
        "experiments": {
            "baselines": ["朴素基线", "Logistic/Linear Regression", "Gradient Boosting"],
            "metrics": ["accuracy/R2", "AUROC/RMSE", "distributional distance", "calibration"],
            "ablation": ["移除候选特征组 A", "移除候选特征组 B", "仅用基线特征"],
            "validation_protocol": "留出验证 + 分组/时间外推 + 可复现脚本。",
        },
        "ev_titles": [
            f"[MOCK] 关于“{short[:36]}”的机制背景综述片段",
            f"[MOCK] “{short[:30]}”相关方法学与建模摘要",
            f"[MOCK] “{short[:30]}”研究现状调研纪要",
        ],
        "ev_quotes": [
            f"围绕“{short}”，已有研究给出若干机制线索，但缺乏统一的可验证基准。（mock 原文片段）",
            "相关方法学表明可用代理变量与统计模型对目标结果进行建模。（mock 摘要片段）",
            "现状调研指出该问题仍需可复现的数据集与外推验证协议。（mock 调研纪要）",
        ],
    }


# 主题关键词 -> 内容包构造器。顺序影响匹配优先级。
_TOPIC_MATCHERS: list[tuple[tuple[str, ...], Any]] = [
    (("prime", "质数", "素数", "factor", "cryptograph"), _prime_pack),
    (("pandemic", "spillover", "zoonotic", "outbreak", "epidemic", "大流行"), _pandemic_pack),
    (("climate", "ecolog", "carbon", "warming", "气候", "生态"), _climate_pack),
    (("ai", "artificial intelligence", "creativity", "creative", "generative", "machine learning", "人工智能", "创造"), _ai_pack),
]


def _select_pack(question_item: dict) -> dict:
    """
    依据问题文本与领域，选择领域相关内容包（未命中则通用回退）。

    参数：
        question_item: 选中问题 dict。

    返回：
        内容包 dict（含标题/假设/技术细节/实验/证据素材等字段）。
    """
    q = (question_item.get("question") or "").strip()
    domain = (question_item.get("domain") or "").strip()
    haystack = f"{q} {domain}".lower()
    for keywords, builder in _TOPIC_MATCHERS:
        if any(k in haystack for k in keywords):
            return builder(q, domain)
    return _generic_pack(q, domain)


def build_mock_evidence_cards(question_item: dict) -> list[dict]:
    """
    构造 3 张领域相关 mock EvidenceCard（标记 mock_for_testing，不伪造 DOI/URL）。

    参数：
        question_item: 选中问题的 dict（决定主题）。

    返回：
        EvidenceCard 兼容的 dict 列表。
    """
    pack = _select_pack(question_item)
    titles = pack["ev_titles"]
    quotes = pack["ev_quotes"]
    source_types = ["rag", "arxiv", "deep_research"]
    notes = [
        "mock_for_testing; source=local_rag",
        "mock_for_testing; source=arxiv_preprint",
        "mock_for_testing; DeepResearch summary; requires downstream verification.",
    ]
    scores = [0.82, 0.76, 0.6]
    cards = []
    for i in range(3):
        cards.append({
            "id": MOCK_EVIDENCE_IDS[i],
            "source_type": source_types[i],
            "title": titles[i],
            "authors": [],
            "year": None,
            "url": None,
            "doi": None,
            "quoted_text": quotes[i],
            "summary": quotes[i][:60],
            "relevance_score": scores[i],
            "reliability_note": notes[i],
        })
    return cards


def parsed_question(question_item: dict) -> dict:
    """返回 ParsedQuestionResult 的 mock（领域相关）。"""
    pack = _select_pack(question_item)
    q = question_item.get("question", "")
    domain = question_item.get("domain", "Unknown")
    return {
        "domain": domain,
        "core_question": q or "如何将该科学问题转化为可验证假设？",
        "keywords": pack["keywords"],
        "entities": pack["entities"],
        "question_type": pack["question_type"],
        "scientific_boundary": pack["scientific_boundary"],
        "what_not_to_claim": pack["what_not_to_claim"],
        "suspected_domain_mismatch": bool(question_item.get("metadata", {}).get("confidence", 1.0) < 0.7),
        "domain_confidence": float(question_item.get("metadata", {}).get("confidence", 0.9)),
    }


def query_plan(question_item: dict) -> dict:
    """返回 QueryPlanResult 的 mock（查询围绕所选问题的关键词）。"""
    pack = _select_pack(question_item)
    kws = pack["keywords"]
    # 用主题关键词构造覆盖多来源的查询。
    queries = [
        {"purpose": "机制背景", "query": f"{kws[0]} mechanism", "source_preference": "local_rag", "expected_evidence": "机制证据", "priority": "high"},
        {"purpose": "方法学", "query": f"{kws[1]} method", "source_preference": "local_rag", "expected_evidence": "方法证据", "priority": "high"},
        {"purpose": "度量与评估", "query": f"{kws[2]} evaluation", "source_preference": "arxiv", "expected_evidence": "方法学论文", "priority": "medium"},
        {"purpose": "前沿调研", "query": f"{kws[0]} {kws[3]} survey", "source_preference": "deep_research", "expected_evidence": "综述性调研", "priority": "high"},
        {"purpose": "文献元数据", "query": f"{kws[1]} {kws[2]}", "source_preference": "openalex", "expected_evidence": "相关工作", "priority": "low"},
        {"purpose": "DOI 核验", "query": f"{kws[3]} benchmark", "source_preference": "crossref", "expected_evidence": "可核验文献", "priority": "low"},
    ]
    return {
        "queries": queries,
        "search_rationale": "围绕所选问题的机制、方法、度量与前沿多维证据，兼顾本地 RAG 与公开文献。",
        "required_evidence_types": ["mechanism", "method", "dataset", "limitation"],
    }


def evidence_extraction(question_item: dict, evidence_ids: list[str]) -> dict:
    """返回 EvidenceExtractionResult 的 mock（事实均绑定 evidence_id，领域相关）。"""
    pack = _select_pack(question_item)
    ids = evidence_ids or MOCK_EVIDENCE_IDS
    # 保证至少有 3 个 id 可用。
    while len(ids) < 3:
        ids = ids + [ids[-1]]
    return {
        "established_facts": [
            {"fact": pack["ev_quotes"][0].replace("（mock 原文片段）", "").strip(), "evidence_ids": [ids[0]], "confidence": "medium", "fact_type": "mechanism", "caveat": "关联非因果。"},
            {"fact": pack["ev_quotes"][1].replace("（mock 摘要片段）", "").strip(), "evidence_ids": [ids[1]], "confidence": "medium", "fact_type": "method", "caveat": "需进一步验证。"},
            {"fact": pack["ev_quotes"][2].replace("（mock 调研纪要）", "").strip(), "evidence_ids": [ids[2]], "confidence": "low", "fact_type": "background", "caveat": "来自调研纪要，需核验。"},
        ],
        "disputed_points": [],
        "knowledge_gaps": [
            {"gap": "缺乏统一的可复现验证基准。", "why_it_matters": "决定研究计划可否实战落地。", "evidence_ids": [ids[1]], "validation_need": "构建外推验证集。"},
        ],
        "possible_datasets": [
            {"name": pack["datasets"]["source"], "type": "source", "use": "假设推演依据", "access_note": "公开数据整合（待检索）", "evidence_ids": [ids[0]], "is_public_candidate": True, "is_already_downloaded": False},
            {"name": pack["datasets"]["target"], "type": "target", "use": "验证实验目标变量", "access_note": "按协议构造（待构造）", "evidence_ids": [ids[1]], "is_public_candidate": True, "is_already_downloaded": False},
        ],
        "methodological_constraints": ["标签稀疏与不平衡", "外推下的数据泄漏风险"],
        "evidence_coverage_note": "证据覆盖机制/方法/背景，但外推验证证据不足；总体为 mock 演示数据。",
    }


def hypothesis_generation(question_item: dict, evidence_ids: list[str]) -> dict:
    """返回 HypothesisGenerationResult 的 mock（含 2 个候选与推荐，领域相关）。"""
    pack = _select_pack(question_item)
    ids = evidence_ids or MOCK_EVIDENCE_IDS
    while len(ids) < 2:
        ids = ids + [ids[-1]]
    return {
        "hypotheses": [
            {
                "hypothesis": pack["hypothesis"],
                "mechanism": pack["mechanism"],
                "falsifiable_prediction": pack["falsifiable_prediction"],
                "required_observations": pack["required_observations"],
                "risk_of_being_wrong": pack["risk_of_being_wrong"],
                "supporting_evidence_ids": [ids[0], ids[1]],
                "contradicted_by_evidence_ids": [],
                "novelty_score": 0.6, "falsifiability_score": 0.8, "feasibility_score": 0.7,
                "evidence_support_score": 0.6, "overall_score": 0.68,
            },
            {
                "hypothesis": f"仅使用最简基线特征即可达到与完整方案相当的效果（针对：{(question_item.get('question') or '')[:40]}）。",
                "mechanism": "基线特征可能已包含多数可预测信号。",
                "falsifiable_prediction": "若完整方案相较基线无显著提升，则该假设成立。",
                "required_observations": pack["required_observations"][:2],
                "risk_of_being_wrong": "完整方案通常带来增益，该假设先验风险较高。",
                "supporting_evidence_ids": [ids[1]],
                "contradicted_by_evidence_ids": [ids[0]],
                "novelty_score": 0.3, "falsifiability_score": 0.8, "feasibility_score": 0.8,
                "evidence_support_score": 0.4, "overall_score": 0.52,
            },
        ],
        "recommended_hypothesis_index": 0,
        "selection_reason": "假设 0 机制链条清晰、可证伪且可用公开数据验证，综合分更高。",
        "rejected_directions": ["在无真实实验时直接给出量化结论。"],
    }


def experiment_design(question_item: dict) -> dict:
    """返回 ExperimentDesignResult 的 mock（Results 严格 pending，领域相关）。"""
    pack = _select_pack(question_item)
    return {
        "technical_details": pack["technical_details"],
        "datasets": pack["datasets"],
        "methods": pack["methods"],
        "experiments": pack["experiments"],
        "results": PENDING_RESULTS,
        "reproducibility_checklist": [
            "固定随机种子", "公开数据获取脚本", "特征构造脚本", "训练/评估配置文件", "指标计算脚本",
        ],
        "execution_metadata": {"actual_execution": False, "note": "mock 演示，未运行真实实验。"},
    }


def review(question_item: dict) -> dict:
    """返回 ReviewResult 的 mock（通过，但保守）。"""
    return {
        "passed": True,
        "reviewer_comments": [
            "假设可证伪且机制链条清晰。",
            "数据集区分 source/target，实验含多基线与多指标。",
            "Results 正确保持 pending，未出现伪造指标。",
        ],
        "critical_issues": [],
        "required_revisions": ["建议补充外推的显著性检验方案。"],
        "risk_level": "medium",
        "evidence_grounding_score": 0.7,
        "falsifiability_score": 0.8,
        "reproducibility_score": 0.75,
        "reference_reliability_score": 0.6,
    }


def review_fail(question_item: dict) -> dict:
    """返回一个未通过的 ReviewResult 的 mock（用于测试自动修订）。"""
    return {
        "passed": False,
        "reviewer_comments": ["假设的可证伪预测不够具体。"],
        "critical_issues": ["缺少明确的证伪判据。"],
        "required_revisions": ["为推荐假设补充明确的证伪阈值与观测。"],
        "risk_level": "high",
        "evidence_grounding_score": 0.5,
        "falsifiability_score": 0.4,
        "reproducibility_score": 0.6,
        "reference_reliability_score": 0.5,
    }


def research_plan(question_item: dict, evidence_ids: list[str]) -> dict:
    """返回 ReportWriter 的 mock（references 用 reference_ids 引用 mock 证据，领域相关）。"""
    pack = _select_pack(question_item)
    ids = evidence_ids or MOCK_EVIDENCE_IDS
    exp = experiment_design(question_item)
    q = question_item.get("question", "")
    return {
        "question_id": question_item.get("id", ""),
        "input_question": q,
        "domain": question_item.get("domain", "Unknown"),
        "problem_statement": pack["problem_statement"],
        "rationale": pack["rationale"],
        "generated_hypotheses": [
            {
                "hypothesis": pack["hypothesis"],
                "mechanism": pack["mechanism"],
                "falsifiable_prediction": pack["falsifiable_prediction"],
                "required_observations": pack["required_observations"],
                "risk_of_being_wrong": pack["risk_of_being_wrong"],
            }
        ],
        "technical_details": exp["technical_details"],
        "datasets": exp["datasets"],
        "paper_title": pack["title"],
        "paper_abstract": (
            f"背景：本报告针对科学问题“{q}”，将其转化为可验证的科学假设与研究计划。"
            "方法：整合证据构造数据集，设计可证伪假设与多基线实验并做外推评估。"
            "结果：待执行验证实验（pending），本报告不含真实实验数值。"
        ),
        "methods": exp["methods"],
        "experiments": exp["experiments"],
        "results": exp["results"],
        "reference_ids": ids,
        "reviewer_comments": review(question_item)["reviewer_comments"],
        "revision_history": [],
        "reproducibility_checklist": exp["reproducibility_checklist"],
        "validation_status": "ready_for_validation",
    }


def validation(question_item: dict) -> dict:
    """返回 ValidationResult 的 mock（保守状态）。"""
    return {
        "valid": True,
        "errors": [],
        "warnings": ["mock 运行，结果不可作为真实科学结论。"],
        "validation_status": "ready_for_validation",
        "quality_gate_results": {},
    }


# mock_key -> 构造函数 的分派表（BaseAgent 在 mock 模式据此取输出）。
_DISPATCH: dict[str, Any] = {
    "parsed_question": parsed_question,
    "query_plan": query_plan,
    "evidence_extraction": evidence_extraction,
    "hypothesis_generation": hypothesis_generation,
    "experiment_design": experiment_design,
    "review": review,
    "review_fail": review_fail,
    "research_plan": research_plan,
    "validation": validation,
}


def get_mock(mock_key: str, question_item: dict, evidence_ids: list[str] | None = None) -> dict:
    """
    按 mock_key 返回对应 Agent 的 mock 输出（始终围绕 question_item 主题）。

    参数：
        mock_key:      mock 分派键（如 "parsed_question"）。
        question_item: 选中问题 dict（决定主题，杜绝跨题污染）。
        evidence_ids:  可用证据 ID（供事实/引用绑定）。

    返回：
        结构完整、可被对应 Pydantic schema 校验的 dict。

    异常：
        KeyError: 未知 mock_key。
    """
    fn = _DISPATCH.get(mock_key)
    if fn is None:
        raise KeyError(f"未知 mock_key：{mock_key}")
    # 依据函数签名决定是否传 evidence_ids。
    if mock_key in ("evidence_extraction", "hypothesis_generation", "research_plan"):
        return fn(question_item, evidence_ids or MOCK_EVIDENCE_IDS)
    return fn(question_item)
