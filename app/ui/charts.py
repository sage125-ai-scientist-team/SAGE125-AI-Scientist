"""
app.ui.charts —— 所有 Plotly 图表构造函数。

统一使用项目主题色与透明/浅色背景，适配暗色控制台。所有函数返回
plotly.graph_objects.Figure，供 Streamlit st.plotly_chart 渲染。

诚实性：readiness 雷达为“基于字段完整性的规则预览”，非实验验证结果，
图表标题会显式标注。
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from app.ui import theme
from app.ui.i18n import domain_label, source_type_label

# 统一的透明背景布局参数。
_TRANSPARENT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#CBD5E1", family="system-ui"),
    margin=dict(l=30, r=20, t=48, b=30),
)

# 统一 Plotly 工具栏配置：隐藏相机/缩放/平移/自动缩放/重置/全屏/Plotly logo，
# 仅用于用户可见图表；不依赖 CSS 隐藏作为主实现，CSS 只作为额外防御。
PLOTLY_CONFIG: dict[str, Any] = {
    "displayModeBar": False,
    "displaylogo": False,
    "scrollZoom": False,
    "responsive": True,
}


def render_plotly_chart(
    figure: go.Figure,
    *,
    key: str,
    width: str = "stretch",
    on_select: str | None = None,
    selection_mode: str = "points",
):
    """
    统一的 Plotly 图表渲染入口：确保每一个用户可见图表都禁用工具栏。

    参数：
        figure: 待渲染的 Plotly Figure。
        key:    Streamlit 组件唯一 key（经 make_widget_key 生成）。
        width:  沿用 Streamlit 1.58 的 width 语义（"stretch"/"content"/int）。

    说明：
        theme=None 保留图表自身显式设置的配色（避免 Streamlit 默认主题覆盖
        本项目统一的蓝青配色体系）；config=PLOTLY_CONFIG 关闭工具栏与 logo，
        但保留 hover、响应式宽度与图表内容/数值。
    """
    kwargs: dict[str, Any] = {
        "width": width,
        "theme": None,
        "key": key,
    }
    if on_select is not None:
        kwargs["on_select"] = on_select
        kwargs["selection_mode"] = selection_mode
    return st.plotly_chart(figure, config=PLOTLY_CONFIG, **kwargs)


def _empty_fig(title: str) -> go.Figure:
    """构造一个带提示的空图（无数据时使用）。"""
    fig = go.Figure()
    fig.update_layout(title=title, **_TRANSPARENT_LAYOUT)
    # 居中提示无数据。
    fig.add_annotation(text="暂无数据", showarrow=False, font=dict(color="#94A3B8"))
    return fig


def make_agent_timeline(agent_trace: list[dict]) -> go.Figure:
    """
    构造 Agent 运行时间线（水平条，按步序，颜色映射状态）。

    参数：
        agent_trace: AgentTraceEvent dict 列表。

    返回：
        Plotly 图。
    """
    if not agent_trace:
        return _empty_fig("智能体流程耗时")
    names = [ev.get("agent_name", "?") for ev in agent_trace]
    durations = [max(1, ev.get("duration_ms") or 1) for ev in agent_trace]
    colors = [theme.AGENT_STATUS_COLORS.get(ev.get("status", "pending"), "#94A3B8") for ev in agent_trace]
    status_zh = {"completed": "已完成", "failed": "失败", "skipped": "跳过", "running": "运行中", "pending": "等待"}
    statuses = [status_zh.get(ev.get("status", ""), ev.get("status", "")) for ev in agent_trace]

    fig = go.Figure(
        go.Bar(
            x=durations,
            y=[f"{i:02d} · {n}" for i, n in enumerate(names)],
            orientation="h",
            marker=dict(color=colors),
            text=statuses,
            textposition="auto",
            hovertemplate="%{y}<br>状态=%{text}<br>%{x} ms<extra></extra>",
        )
    )
    fig.update_layout(
        title="智能体流程耗时（状态/耗时）",
        xaxis_title="耗时 (ms)",
        yaxis=dict(autorange="reversed"),
        height=380,
        **_TRANSPARENT_LAYOUT,
    )
    return fig


def make_evidence_distribution(evidence_cards: list[dict]) -> go.Figure:
    """
    构造证据来源分布（按 source_type 计数的条形图）。

    参数：
        evidence_cards: EvidenceCard dict 列表。

    返回：
        Plotly 图。
    """
    if not evidence_cards:
        return _empty_fig("证据来源分布")
    counts = Counter(c.get("source_type", "unknown") for c in evidence_cards)
    labels = list(counts.keys())
    display_labels = [source_type_label(k) for k in labels]
    values = [counts[k] for k in labels]
    colors = [theme.SOURCE_COLORS.get(k, "#64748B") for k in labels]
    fig = go.Figure(
        go.Bar(
            x=display_labels,
            y=values,
            marker=dict(color=colors),
            text=values,
            textposition="auto",
            hovertemplate="%{x}<br>数量=%{y}<extra></extra>",
        )
    )
    fig.update_layout(title="证据来源分布", height=320, **_TRANSPARENT_LAYOUT)
    return fig


def make_relevance_histogram(evidence_cards: list[dict]) -> go.Figure:
    """
    构造相关性分数分布直方图。

    参数：
        evidence_cards: EvidenceCard dict 列表。

    返回：
        Plotly 图。
    """
    if not evidence_cards:
        return _empty_fig("相关性分布")
    scores = [float(c.get("relevance_score", 0) or 0) for c in evidence_cards]
    fig = go.Figure(
        go.Histogram(
            x=scores, nbinsx=10, marker=dict(color=theme.SCIENCE_CYAN),
            hovertemplate="相关性=%{x}<br>数量=%{y}<extra></extra>",
        )
    )
    fig.update_layout(title="相关性分布", xaxis_title="相关性", yaxis_title="数量", height=320, **_TRANSPARENT_LAYOUT)
    return fig


def _rule_based_readiness(plan: dict) -> dict[str, float]:
    """
    基于字段完整性给出规则分（0-1），不伪造精确实验分数。

    参数：
        plan: ResearchPlan dict。

    返回：
        六维规则分映射。
    """
    datasets = plan.get("datasets", {}) or {}
    experiments = plan.get("experiments", {}) or {}
    refs = plan.get("references", []) or []
    hyps = plan.get("generated_hypotheses", []) or []
    # 证据完整性：以引用数量衡量（封顶 1.0）。
    evidence = min(1.0, len(refs) / 5.0)
    # 可证伪性：假设是否含 falsifiable_prediction。
    fals = 1.0 if any(h.get("falsifiable_prediction") for h in hyps) else 0.3
    # 数据可得性：source/target 是否齐备。
    ds = (0.5 if datasets.get("source") else 0) + (0.5 if datasets.get("target") else 0)
    # 实验设计：baselines/metrics 是否齐备。
    ex = (0.5 if experiments.get("baselines") else 0) + (0.5 if experiments.get("metrics") else 0)
    # 引用可靠性：有真实 doi/url 的引用占比（mock/无来源不加满分）。
    reliable = sum(1 for r in refs if r.get("doi") or r.get("url"))
    ref_rel = min(1.0, reliable / max(1, len(refs))) if refs else 0.2
    # 可复现性：checklist 是否非空。
    repro = min(1.0, len(plan.get("reproducibility_checklist", []) or []) / 4.0)
    return {
        "Evidence Completeness": round(evidence, 2),
        "Hypothesis Falsifiability": round(fals, 2),
        "Dataset Availability": round(ds, 2),
        "Experiment Design": round(ex, 2),
        "Reference Reliability": round(ref_rel, 2),
        "Reproducibility": round(repro, 2),
    }


def make_readiness_radar(plan: dict) -> go.Figure:
    """
    构造 readiness 雷达图（规则预览，非实验验证）。

    参数：
        plan: ResearchPlan dict。

    返回：
        Plotly 图。
    """
    scores = _rule_based_readiness(plan or {})
    dims = list(scores.keys())
    vals = [scores[d] for d in dims]
    # 闭合雷达。
    fig = go.Figure(
        go.Scatterpolar(
            r=vals + [vals[0]],
            theta=dims + [dims[0]],
            fill="toself",
            line=dict(color=theme.PRIMARY_BLUE),
            fillcolor="rgba(37,99,235,0.25)",
        )
    )
    fig.update_layout(
        title="就绪度规则预览（非实验验证结果）",
        polar=dict(radialaxis=dict(range=[0, 1], color="#94A3B8"), bgcolor="rgba(0,0,0,0)"),
        height=380,
        **_TRANSPARENT_LAYOUT,
    )
    return fig


def make_experiment_metrics_bar(metrics: dict[str, float]) -> go.Figure:
    """
    构造真实实验指标条形图（0-1 比例），用于替代纯文字数字列表。

    参数：
        metrics: 指标名 -> 数值（均为真实观测值，非编造）。

    返回：
        Plotly 图。
    """
    if not metrics:
        return _empty_fig("Experiment Metrics")
    label_zh = {
        "balanced_accuracy": "平衡准确率 balanced_accuracy",
        "malignant_recall": "恶性召回率 malignant_recall",
    }
    names = list(metrics.keys())
    labels = [label_zh.get(n, n) for n in names]
    values = [float(metrics[n]) for n in names]
    colors = [theme.SCIENCE_CYAN, theme.GOLD, theme.PRIMARY_BLUE, theme.SUCCESS][: len(values)]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=colors),
            text=[f"{v:.1%}" for v in values],
            textposition="auto",
        )
    )
    fig.update_layout(
        title="真实实验指标（留出测试集观测值）",
        xaxis=dict(range=[0, 1], tickformat=".0%"),
        height=220,
        **_TRANSPARENT_LAYOUT,
    )
    return fig


def make_confusion_matrix_heatmap(confusion: dict[str, int]) -> go.Figure:
    """
    构造 2x2 混淆矩阵热力图（真实预测计数，非编造）。

    参数：
        confusion: 含 true_positive/true_negative/false_positive/false_negative 的字典。

    返回：
        Plotly 图。
    """
    if not confusion:
        return _empty_fig("Confusion Matrix")
    tn = int(confusion.get("true_negative", 0))
    fp = int(confusion.get("false_positive", 0))
    fn = int(confusion.get("false_negative", 0))
    tp = int(confusion.get("true_positive", 0))
    # 行 = 实际标签（良性/恶性），列 = 预测标签（良性/恶性）。
    z = [[tn, fp], [fn, tp]]
    text = [[str(tn), str(fp)], [str(fn), str(tp)]]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=["预测：良性 (B)", "预测：恶性 (M)"],
            y=["实际：良性 (B)", "实际：恶性 (M)"],
            text=text,
            texttemplate="%{text}",
            textfont=dict(size=16, color="#0B1628"),
            colorscale=[[0, "rgba(37,99,235,0.15)"], [1, theme.SCIENCE_CYAN]],
            showscale=False,
        )
    )
    fig.update_layout(title="混淆矩阵（真实预测计数）", height=300, **_TRANSPARENT_LAYOUT)
    fig.update_yaxes(autorange="reversed")
    return fig


# 统一蓝青配色体系（不使用高饱和彩虹色）；数量越高颜色越深。
_DOMAIN_CHART_PALETTE = ["#38BDF8", "#22D3EE", "#3B82F6", "#2563EB", "#1D4ED8"]


def make_domain_coverage_chart(questions: list[dict]) -> go.Figure:
    """
    构造 125 个科学问题的领域分布条形图（中文显示标签，蓝青配色，横向条形）。

    内部领域 key 保持英文不变（不改变实际计数与业务口径），仅在图表标签、
    hover 文案中通过 i18n.domain_label 映射为中文。

    参数：
        questions: 问题 dict 列表。

    返回：
        Plotly 图。
    """
    if not questions:
        return _empty_fig("125 个科学问题 · 领域分布")
    counts = Counter(q.get("domain", "Unknown") for q in questions)
    # 数量从高到低排序；同数量按领域中文名排序，保持稳定顺序。
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], domain_label(kv[0])))
    domain_keys = [k for k, _ in ordered]
    values = [v for _, v in ordered]
    labels_zh = [domain_label(k) for k in domain_keys]
    max_v = max(values) if values else 1
    colors = []
    for v in values:
        # 数量越高，配色越深（索引越大）；单一数量时使用居中色。
        ratio = (v / max_v) if max_v else 0
        idx = min(len(_DOMAIN_CHART_PALETTE) - 1, int(round(ratio * (len(_DOMAIN_CHART_PALETTE) - 1))))
        colors.append(_DOMAIN_CHART_PALETTE[idx])
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels_zh,
            orientation="h",
            marker=dict(color=colors),
            text=values,
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}：%{x} 题<extra></extra>",
        )
    )
    fig.update_layout(
        title="125 个科学问题 · 领域分布",
        height=max(360, 34 * len(labels_zh) + 90),
        margin=dict(l=170, r=36, t=48, b=24),
        yaxis=dict(autorange="reversed", showgrid=False, zeroline=False, ticksuffix="  "),
        xaxis=dict(showgrid=True, gridcolor="rgba(148,163,184,0.12)", zeroline=False),
        showlegend=False,
        **{k: v for k, v in _TRANSPARENT_LAYOUT.items() if k != "margin"},
    )
    return fig


def make_knowledge_graph(evidence_cards: list[dict], hypotheses: list[dict], plan: dict) -> go.Figure:
    """
    构造简化知识网络：Question -> Evidence -> Hypothesis -> Experiment -> Reference。

    兼容保留函数：主界面已改用 app.ui.components.render_research_flow 的结构化
    科研证据链（固定 5 阶段布局），不再在普通用户主页面调用本函数生成的随机
    力导向图。仅保留给需要旧版力导向图的调用方或历史测试使用。

    参数：
        evidence_cards: 证据 dict 列表。
        hypotheses:     候选假设 dict 列表。
        plan:           ResearchPlan dict。

    返回：
        Plotly 网络图。
    """
    try:
        import networkx as nx
    except ImportError:
        return _empty_fig("Knowledge Graph")

    g = nx.DiGraph()
    # 中心节点：Question。
    g.add_node("Question", kind="question")
    # 证据节点（最多 8 个，避免过密）。
    for c in (evidence_cards or [])[:8]:
        cid = c.get("id", "EV")
        g.add_node(cid, kind="evidence")
        g.add_edge("Question", cid)
    # 假设节点。
    for i, _h in enumerate((hypotheses or [])[:3]):
        hid = f"H{i+1}"
        g.add_node(hid, kind="hypothesis")
        # 假设连接到其支撑证据。
        for eid in (_h.get("supporting_evidence_ids") or [])[:4]:
            if eid in g:
                g.add_edge(eid, hid)
    # 实验与报告节点。
    g.add_node("Experiment", kind="experiment")
    g.add_node("Report", kind="report")
    for i in range(min(3, len(hypotheses or []))):
        g.add_edge(f"H{i+1}", "Experiment")
    g.add_edge("Experiment", "Report")

    # 布局。
    pos = nx.spring_layout(g, seed=42, k=0.9)
    kind_color = {
        "question": theme.GOLD, "evidence": theme.SCIENCE_CYAN, "hypothesis": theme.PRIMARY_BLUE,
        "experiment": "#8B5CF6", "report": theme.SUCCESS,
    }
    # 边。
    edge_x, edge_y = [], []
    for u, v in g.edges():
        edge_x += [pos[u][0], pos[v][0], None]
        edge_y += [pos[u][1], pos[v][1], None]
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(color="rgba(148,163,184,0.5)", width=1), hoverinfo="none")
    # 点。
    node_x = [pos[n][0] for n in g.nodes()]
    node_y = [pos[n][1] for n in g.nodes()]
    node_color = [kind_color.get(g.nodes[n]["kind"], "#64748B") for n in g.nodes()]
    node_text = list(g.nodes())
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text", text=node_text, textposition="top center",
        textfont=dict(size=9, color="#CBD5E1"),
        marker=dict(size=16, color=node_color, line=dict(color="#0B1628", width=1)),
        hoverinfo="text",
    )
    fig = go.Figure([edge_trace, node_trace])
    fig.update_layout(
        title="Knowledge Graph · Question → Evidence → Hypothesis → Experiment → Report",
        showlegend=False, height=420,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        **_TRANSPARENT_LAYOUT,
    )
    return fig
