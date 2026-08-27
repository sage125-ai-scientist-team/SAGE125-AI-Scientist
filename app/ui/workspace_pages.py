# -*- coding: utf-8 -*-
"""工作区各页：复用现有组件与 API，不编造数据、不触发隐式模型调用。"""

from __future__ import annotations

import datetime as _dt
import re as _re
from typing import Any, Callable

import streamlit as st

from app.ui import api_client, charts, components, errors, job_state, state
from app.ui.components import esc
from app.ui.i18n import domain_label, ui_text
from app.ui.landing import render_landing
from app.ui.workspace import (
    BOOT_HEALTH,
    BOOT_QUESTIONS,
    apply_pending_question,
    bootstrap,
    get_ui_question_index_cached,
    hide_sidebar,
    hypothesis_rows,
    list_runs,
    load_domain_chart,
    load_domain_distribution,
    load_question_selector_state,
    load_question_summary,
    persist_query_mode,
    persist_query_question,
    picker_is_expanded,
    questions_fingerprint,
    referenced_ids,
    render_empty,
    render_overview_skeleton,
    render_unselected_guide,
    render_workspace_header,
    research_status,
    selected_question,
    show_workspace_shell,
    store_question_selector_state,
)

_HOOKS: dict[str, Any] = {}


def bind_hooks(**hooks: Any) -> None:
    _HOOKS.update(hooks)


def _rt(name: str) -> Callable:
    fn = _HOOKS.get(name)
    if not fn:
        raise RuntimeError(f"workspace hook 未绑定：{name}")
    return fn


def _ctx() -> dict[str, Any]:
    show_workspace_shell()
    job_state.ensure_client_id()
    ctx = bootstrap()
    render_workspace_header(ctx)
    job_state.render_page_job_surface(ctx.get("qid"))
    return ctx


def _switches() -> dict:
    return components.render_pipeline_switches() if False else (
        st.session_state.get("_sage_switches")
        or {
            "use_local_rag": True,
            "use_deep_research": False,
            "use_open_literature": True,
            "reviewer_auto_revision": True,
        }
    )


_RUN_TS_RE = _re.compile(r"^(\d{8})-(\d{6})")


def _relative_time(run_id: str | None) -> str:
    """从 run_id 前缀（YYYYMMDD-HHMMSS）解析真实时间并转为相对时长；解析失败返回“—”。"""
    if not run_id:
        return "—"
    m = _RUN_TS_RE.match(str(run_id))
    if not m:
        return "—"
    try:
        ts = _dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return "—"
    delta = _dt.datetime.now() - ts
    seconds = delta.total_seconds()
    if seconds < 0:
        return "—"
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))} 分钟前"
    if seconds < 86400:
        return f"{int(seconds // 3600)} 小时前"
    return f"{int(seconds // 86400)} 天前"


def page_landing() -> None:
    hide_sidebar()
    ctx = {
        "questions": st.session_state.get(BOOT_QUESTIONS) or [],
        "health": st.session_state.get(BOOT_HEALTH) or {},
    }
    render_landing(
        ctx,
        workspace_page=_HOOKS["page_questions"],
        case_page=_HOOKS["page_execution"],
    )
    if BOOT_QUESTIONS not in st.session_state:
        bootstrap()


@st.fragment(run_every="2s")
def _render_model_progress(qid: str | None) -> None:
    """轮询当前题目的 Job，画出旧版模型调用进度卡。"""
    jobs = job_state.collect_visible_jobs(qid)
    if not jobs:
        return
    ranked = sorted(
        jobs,
        key=lambda item: (job_state.is_active(item), str(item.get("updated_at") or "")),
        reverse=True,
    )
    job = ranked[0]
    job_state.render_progress_card(job)
    job_state.apply_job_result_if_ready(job)


@st.fragment
def _render_status_kpis(ctx: dict[str, Any]) -> None:
    """研究状态 / 已用证据 / 运行次数。"""
    ctx = _live_ctx(ctx)
    qid = ctx.get("qid")
    label, _kind = research_status(ctx)
    result = ctx.get("result") or {}
    evidence_n = len(result.get("evidence_cards") or [])
    runs = [r for r in list_runs() if not qid or str(r.get("question_id")) == str(qid)]
    kpi_html = (
        '<div class="ws-kpi-row cols-3">'
        f'<div class="ws-kpi"><div class="ws-kpi-label">当前研究状态</div><div class="ws-kpi-value">{esc(label)}</div></div>'
        f'<div class="ws-kpi"><div class="ws-kpi-label">已用证据</div><div class="ws-kpi-value">{evidence_n if evidence_n else "—"}</div></div>'
        f'<div class="ws-kpi"><div class="ws-kpi-label">运行次数</div><div class="ws-kpi-value">{len(runs) if runs else "—"}</div></div>'
        "</div>"
    )
    st.markdown(kpi_html, unsafe_allow_html=True)


@st.fragment
def _render_dynamics_fragment() -> None:
    """「最新研究动态」时间线：独立 Fragment，不牵动页面其余区域。"""
    st.subheader("最新研究动态")
    recent = list_runs(limit=8)
    if not recent:
        render_empty("暂无研究动态", "生成研究计划或加载历史运行后，这里会列出可审计动态。")
        return
    items_html = []
    for item in recent[:6]:
        status = item.get("status") or item.get("validation_status") or "—"
        dot_cls = "error" if status in {"failed", "error"} else ("warning" if status in {"needs_data", "partial_failed"} else "")
        ev_n = item.get("evidence_count")
        items_html.append(
            f"""<li class="ws-timeline-item">
              <span class="ws-timeline-dot {dot_cls}"></span>
              <div class="ws-timeline-body">
                <div class="ws-timeline-title">{esc(item.get('question_id') or '—')} · {esc(str(status))} 运行完成</div>
                <div class="ws-timeline-meta">run_id {esc(item.get('run_id') or '—')} · 证据 {ev_n if ev_n is not None else '—'}</div>
              </div>
              <div class="ws-timeline-time">{esc(_relative_time(item.get('run_id')))}</div>
            </li>"""
        )
    st.markdown(f'<ul class="ws-timeline">{"".join(items_html)}</ul>', unsafe_allow_html=True)


def page_overview() -> None:
    """旧 /workspace 概览入口：重定向到合并后的科学问题页，不再渲染旧内容。"""
    st.session_state["question_picker_focus"] = False
    st.switch_page(_HOOKS["page_questions"])


def page_questions() -> None:
    """研究工作区默认页：选题区紧邻快速操作，领域图沉底。"""
    show_workspace_shell()
    skeleton_slot = st.empty()
    with skeleton_slot.container():
        render_overview_skeleton()
    ctx = bootstrap()
    skeleton_slot.empty()

    from app.ui.scroll_trigger import consume_picker_focus, render_scroll_trigger

    consume_picker_focus()
    render_question_action_hub(ctx)
    _render_research_plan_overview(ctx)
    _render_question_detail_expander(ctx)
    st.markdown('<div id="recent-activity"></div>', unsafe_allow_html=True)
    _render_dynamics_fragment()
    st.markdown('<div id="domain-distribution"></div>', unsafe_allow_html=True)
    _render_domain_catalog(ctx)
    render_scroll_trigger()


def _live_ctx(ctx: dict[str, Any]) -> dict[str, Any]:
    live = dict(ctx)
    live["qid"] = state.get(state.KEY_SELECTED_QID)
    live["qtext"] = state.get(state.KEY_SELECTED_QTEXT)
    result = state.get_run_result()
    live["result"] = result
    live["plan"] = result.get("plan") or {}
    return live


@st.fragment
def render_question_action_hub(ctx: dict[str, Any]) -> None:
    """选题 + 快速操作 + 只读上下文 + 紧凑 Job，同一次 Fragment 更新。"""
    apply_pending_question(ctx["questions"])
    load_question_selector_state()
    live = _live_ctx(ctx)
    st.markdown('<section id="workspace-header"></section>', unsafe_allow_html=True)
    render_workspace_header(live)
    st.markdown('<section id="global-job-status"></section>', unsafe_allow_html=True)
    st.markdown('<section id="question-picker"></section>', unsafe_allow_html=True)
    _render_picker_panel(live)
    st.markdown('<section id="quick-actions"></section>', unsafe_allow_html=True)
    _render_quick_actions(live)
    _render_model_progress(live.get("qid"))
    _render_status_kpis(_live_ctx(ctx))


def _render_compact_job_status(qid: str | None) -> None:
    jobs = [job for job in job_state.collect_visible_jobs(qid) if job_state.is_active(job)]
    if not jobs:
        return
    job = jobs[0]
    current, total = job_state.stage_cursor(job.get("stage"))
    step = f"{current}/{total}" if current and total else job_state.friendly_stage_name(str(job.get("stage") or ""))
    st.markdown(
        f"""<div class="ws-job-bar compact" id="hub-job-status">
          <div class="ws-job-bar-count">当前任务 {esc(str(job.get('question_id') or '—'))}</div>
          <div>{esc(job_state.ui_status(job))} · {esc(step)} · Job {esc(str(job.get('job_id') or ''))}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _render_picker_panel(ctx: dict[str, Any]) -> None:
    qid = ctx.get("qid")
    selected = selected_question(ctx["questions"], qid)
    if qid and selected and not picker_is_expanded():
        domain = domain_label(selected.get("domain"))
        title = selected.get("question") or ctx.get("qtext") or ""
        bar, btn = st.columns([5.2, 1.1], vertical_alignment="center")
        with bar:
            st.markdown(
                f"""<div class="selected-question-bar">
                  <div class="selected-question-main">
                    <span class="selected-label">当前选题已就绪</span>
                    <strong>{esc(str(qid))} · {esc(str(title))}</strong>
                    <span class="domain">{esc(domain)}</span>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )
        with btn:
            if st.button("更换问题", key="change_question", width="stretch"):
                st.session_state[components.PICKER_EXPANDED_KEY] = True
                st.rerun(scope="fragment")
        return

    st.markdown(
        """<div class="question-picker-expanded">
          <div class="picker-kicker">步骤 01</div>
          <div class="picker-title">选择科学问题</div>
          <div class="picker-hint">从 125 个前沿科学问题中选择研究起点。</div>
        </div>""",
        unsafe_allow_html=True,
    )
    kw_col, domain_col, status_col = st.columns([2, 1, 1])
    with kw_col:
        keyword = st.text_input(
            "关键词搜索",
            placeholder="输入英文关键词，如 prime、gravity、pandemic",
            key=components.QUESTION_KEYWORD_WIDGET_KEY,
        )
    with domain_col:
        domain_keys = ["全部"] + sorted({q.get("domain", "Unknown") for q in (ctx["questions"] or [])})
        domain_sel = st.selectbox(
            "领域筛选",
            domain_keys,
            format_func=lambda d: ui_text("all_domains") if d == "全部" else domain_label(d),
            key=components.QUESTION_DOMAIN_WIDGET_KEY,
        )
    with status_col:
        status_filter = st.selectbox("状态筛选", ["全部", "已有运行", "尚无运行"], key="q_status_filter")

    more = st.columns([6, 1.2])
    with more[1]:
        if st.button("刷新索引", key="q_refresh_index", help="重建 125 题轻量索引"):
            from app.ui.workspace import refresh_ui_question_index

            refresh_ui_question_index()

    catalog = list(ctx["questions"] or [])
    if keyword and keyword.strip():
        kw = keyword.strip().lower()
        catalog = [q for q in catalog if kw in (q.get("question") or "").lower()]
    if domain_sel != "全部":
        catalog = [q for q in catalog if q.get("domain") == domain_sel]
    status_map = get_ui_question_index_cached()
    if status_filter != "全部" and catalog:
        catalog = [
            q for q in catalog
            if (status_map.get(str(q.get("id")), {}).get("status") != "not_started") == (status_filter == "已有运行")
        ]
    by_id = {str(q.get("id")): q for q in catalog if q.get("id")}
    if qid and qid not in by_id:
        original = selected_question(ctx["questions"], qid)
        if original:
            by_id[str(qid)] = original
    option_ids = [""] + list(by_id)
    from app.ui.workspace import format_question_option, sanitize_question_selector_state

    sanitize_question_selector_state([qid for qid in option_ids if qid])
    st.selectbox(
        "选择一个科学问题",
        option_ids,
        format_func=lambda item: format_question_option(item, ctx["questions"]),
        key=components.SELECTOR_WIDGET_KEY,
        on_change=store_question_selector_state,
    )
    preset_key = components.render_quick_presets(ctx["questions"], compact=True)
    if preset_key:
        from app.ui.i18n import PRESET_KEYWORDS

        keywords = PRESET_KEYWORDS.get(preset_key, [preset_key])
        hit = next(
            (q for q in (ctx["questions"] or []) if all(k in (q.get("question") or "").lower() for k in keywords)),
            None,
        )
        if hit:
            state.queue_question_selection(str(hit.get("id")))
            apply_pending_question(ctx["questions"])


def _render_quick_actions(ctx: dict[str, Any]) -> None:
    st.subheader("快速操作")
    selected_q = selected_question(ctx["questions"], ctx.get("qid"))
    from app.ui.icons import lucide

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.markdown(
            f'<div class="ws-action-card primary"><div class="ws-action-icon">{lucide("clipboard-list", 18)}</div>'
            '<div class="ws-action-title">生成研究计划</div>'
            '<div class="ws-action-desc">基于当前问题生成完整研究计划</div></div>',
            unsafe_allow_html=True,
        )
        gen_action = job_state.render_job_action_button(
            "开始生成",
            job_type=job_state.JOB_TYPE_FULL,
            question_id=ctx.get("qid"),
            key="ov_gen",
        )
    with a2:
        st.markdown(
            f'<div class="ws-action-card"><div class="ws-action-icon">{lucide("library", 18)}</div>'
            '<div class="ws-action-title">开始文献调研</div>'
            '<div class="ws-action-desc">深入探索相关文献和知识背景</div></div>',
            unsafe_allow_html=True,
        )
        ev_action = job_state.render_job_action_button(
            "开始调研",
            job_type=job_state.JOB_TYPE_FULL,
            question_id=ctx.get("qid"),
            key="ov_ev",
            primary=False,
        )
    with a3:
        st.markdown(
            f'<div class="ws-action-card"><div class="ws-action-icon">{lucide("play", 18)}</div>'
            '<div class="ws-action-title">运行受控演示</div>'
            '<div class="ws-action-desc">执行模拟数据结果分析</div></div>',
            unsafe_allow_html=True,
        )
        mock_action = job_state.render_job_action_button(
            "开始运行",
            job_type=job_state.JOB_TYPE_DEMO,
            question_id=ctx.get("qid"),
            key="ov_mock",
            primary=False,
        )
    with a4:
        st.markdown(
            f'<div class="ws-action-card"><div class="ws-action-icon">{lucide("history", 18)}</div>'
            '<div class="ws-action-title">查看历史运行</div>'
            '<div class="ws-action-desc">查看和加载历史运行结果</div></div>',
            unsafe_allow_html=True,
        )
        go_history = st.button("查看历史", width="stretch", key="ov_hist")

    with st.expander("更多操作"):
        m1, m2 = st.columns(2)
        go_feedback = m1.button("提交人工反馈", width="stretch", key="ov_fb")
        go_export = m2.button("导出当前结果", width="stretch", key="ov_ex")
        st.caption("清空当前草稿不会删除历史审计或正式运行产物。")
        if st.checkbox("我确认只清空本会话草稿", key="ov_clear_ack"):
            if st.button("清空当前草稿", type="primary", key="ov_clear"):
                state.clear_run()

    if go_history:
        st.switch_page(_HOOKS["page_history"])
    if ev_action != "none":
        if ev_action == "submit" and ctx.get("qid"):
            job_state.submit_or_reuse_job(
                question_id=str(ctx.get("qid")),
                job_type=job_state.JOB_TYPE_FULL,
                mode=ctx["mode"],
                switches=_switches(),
            )
        st.switch_page(_HOOKS["page_evidence"])
    if go_feedback:
        st.switch_page(_HOOKS["page_versions"])
    if go_export:
        st.switch_page(_HOOKS["page_results"])

    _rt("process_run_triggers")(
        trigger_generate=gen_action == "submit",
        trigger_mock=mock_action == "submit",
        questions=ctx["questions"],
        qid=ctx.get("qid"),
        selected_q=selected_q,
        switches=_switches(),
        mode=ctx["mode"],
        trigger_latest=False,
        diag=ctx["diag"],
    )


def _render_research_plan_overview(ctx: dict[str, Any]) -> None:
    live = _live_ctx(ctx)
    st.markdown('<section id="research-plan-overview"></section>', unsafe_allow_html=True)
    plan_col, _ = st.columns([1, 0.001])
    with plan_col:
        head1, head2 = st.columns([4, 1])
        head1.subheader("当前研究计划概览")
        plan = live.get("plan") or {}
        if plan and head2.button("查看完整计划 →", key="ov_full_plan", width="stretch"):
            st.switch_page(_HOOKS["page_plan"])
    hyps = hypothesis_rows(live.get("plan") or {})
    if not hyps:
        render_empty("尚未形成候选假设", "请先完成文献证据整理，或开始研究流程。")
        return
    for row in hyps[:6]:
        ev_n = len(row.get("support") or [])
        reviewer = (live.get("plan") or {}).get("reviewer_comments")
        validation = (live.get("plan") or {}).get("validation_status") or "draft"
        version = (live.get("plan") or {}).get("version") or (live.get("result") or {}).get("version") or "v1"
        st.markdown(
            f"""<div class="ws-hypo">
              <div class="ws-hypo-id">{esc(row["id"])}</div>
              <div class="ws-hypo-text">{esc(row["statement"])}</div>
              <div class="ws-hypo-meta">证据 {ev_n if ev_n else "—"} · Reviewer {"已返回" if reviewer else "未返回"} ·
                Validation {esc(str(validation))} · 版本 {esc(str(version))}</div>
            </div>""",
            unsafe_allow_html=True,
        )


def _render_question_detail_expander(ctx: dict[str, Any]) -> None:
    qid = state.get(state.KEY_SELECTED_QID)
    selected = selected_question(ctx["questions"], qid)
    if not selected:
        return
    with st.expander("查看题目详情", expanded=False):
        summary = load_question_summary(str(qid or ""), _ui_index_mtime())
        components._render_question_detail_card(selected, summary)


def _render_domain_catalog(ctx: dict[str, Any]) -> None:
    questions = ctx.get("questions") or []
    if not questions:
        return
    fingerprint = questions_fingerprint(questions)
    load_domain_distribution(fingerprint)
    event = charts.render_plotly_chart(
        load_domain_chart(fingerprint),
        key=components.make_widget_key("chart", "domain_cov"),
        on_select="rerun",
    )
    selected_label = None
    selection = getattr(event, "selection", None)
    points = getattr(selection, "points", None) if selection is not None else None
    if points:
        first = points[0]
        selected_label = first.get("y") if isinstance(first, dict) else getattr(first, "y", None)
    if selected_label:
        domain_key = next(
            (
                str(q.get("domain") or "Unknown")
                for q in questions
                if domain_label(q.get("domain")) == selected_label or q.get("domain") == selected_label
            ),
            None,
        )
        if domain_key and st.session_state.get(components.QUESTION_DOMAIN_WIDGET_KEY) != domain_key:
            st.session_state[components.QUESTION_DOMAIN_WIDGET_KEY] = domain_key


def _ui_index_mtime() -> float:
    from app.ui.workspace import _ui_index_fingerprint

    return _ui_index_fingerprint()


def page_evidence() -> None:
    ctx = _ctx()
    if not ctx.get("qid"):
        render_unselected_guide(_HOOKS["page_questions"])
        return
    result = ctx.get("result") or {}
    plan = ctx.get("plan") or {}
    cards = result.get("evidence_cards") or []
    if not cards:
        render_empty("当前没有可用证据", "请先生成研究计划、运行受控演示，或加载历史运行。")
        return
    if plan and not ctx.get("consistent"):
        errors.report_mismatch(
            selected_question=state.get(state.KEY_SELECTED_QTEXT) or "(未知)",
            report_question=plan.get("input_question") or "(未知)",
            run_id=state.active_run_id(),
        )
        return
    _render_evidence_fragment(cards, plan)


@st.fragment
def _render_evidence_fragment(cards: list[dict], plan: dict) -> None:
    """Evidence 列表 + 文献详情选择器：独立 Fragment，切换所选文献不重跑工作区。"""
    components.render_evidence_wall(cards, referenced_ids=referenced_ids(plan))
    picked = st.selectbox(
        "打开文献详情",
        ["无"] + [str(c.get("id") or i) for i, c in enumerate(cards)],
        key="ev_detail_pick",
    )
    if picked != "无":
        card = next((c for c in cards if str(c.get("id")) == picked), None)
        if card:
            with st.expander("文献详情", expanded=True):
                st.markdown(f"**标题（原文）** {card.get('title') or '—'}")
                st.markdown(f"**原文片段** {card.get('quoted_text') or '—'}")
                st.markdown(f"**定位** {card.get('locator') or card.get('location') or '—'}")
                st.markdown(f"**来源类型** {card.get('source_type') or '—'}")
                st.markdown(f"**内容哈希** {card.get('content_hash') or card.get('hash') or '—'}")
                st.json({k: card.get(k) for k in ("doi", "url", "source_type", "relevance_score") if k in card})


def page_hypotheses() -> None:
    ctx = _ctx()
    if not ctx.get("qid"):
        render_unselected_guide(_HOOKS["page_questions"])
        return
    plan = ctx.get("plan") or {}
    if not plan:
        render_empty("尚未生成候选假设", "请先完成文献证据整理，或开始研究流程。")
        return
    if not ctx.get("consistent"):
        errors.report_mismatch(
            selected_question=state.get(state.KEY_SELECTED_QTEXT) or "(未知)",
            report_question=plan.get("input_question") or "(未知)",
            run_id=state.active_run_id(),
        )
        return
    rows = hypothesis_rows(plan)
    if not rows:
        render_empty("尚未生成候选假设", "当前研究计划中没有 generated_hypotheses。")
        return
    _render_hypotheses_fragment(rows, plan)


@st.fragment
def _render_hypotheses_fragment(rows: list[dict], plan: dict) -> None:
    """候选假设列表：独立 Fragment，展开/折叠某一假设不重跑工作区。"""
    reviewer = "已记录" if plan.get("reviewer_comments") else "尚未评审"
    version = plan.get("version") or plan.get("plan_version") or "当前会话"
    for row in rows:
        with st.expander(f"{row['id']} · {(row['statement'] or '（无核心陈述）')[:80]}", expanded=False):
            st.markdown(f"**核心陈述** {row['statement'] or '—'}")
            st.caption(f"Reviewer：{reviewer} · 版本：{version} · 不得显示未提供的置信度")
            st.markdown(f"**可检验预测** {row['prediction'] or '—'}")
            st.markdown(f"**形成依据 / 机制** {row['mechanism'] or '—'}")
            st.markdown(f"**所需观测** {'；'.join(row['observations']) if row['observations'] else '—'}")
            st.markdown(f"**不确定性 / 否定条件** {row['risk'] or '—'}")
            st.markdown(f"**适用边界** {row['boundary'] or '—'}")
            if row["support"]:
                st.markdown("**支持证据**")
                st.write(row["support"])
            if row["against"]:
                st.markdown("**反对证据**")
                st.write(row["against"])
            if row["alternatives"]:
                st.markdown("**替代解释**")
                st.write(row["alternatives"])


def page_plan() -> None:
    ctx = _ctx()
    if not ctx.get("qid"):
        render_unselected_guide(_HOOKS["page_questions"])
        return
    result = ctx.get("result") or {}
    plan = ctx.get("plan") or {}
    selected_q = selected_question(ctx["questions"], ctx.get("qid"))
    components.section_title(ui_text("step_06"), ui_text("researchplan_studio"), "结构化研究目标、变量、步骤、判定与边界。")
    plan_action = job_state.render_job_action_button(
        "生成研究计划",
        job_type=job_state.JOB_TYPE_FULL,
        question_id=ctx.get("qid"),
        key="plan_gen",
    )
    _rt("process_run_triggers")(
        trigger_generate=plan_action == "submit",
        trigger_mock=False,
        questions=ctx["questions"],
        qid=ctx.get("qid"),
        selected_q=selected_q,
        switches=_switches(),
        mode=ctx["mode"],
        trigger_latest=False,
        diag=ctx["diag"],
    )
    ctx = bootstrap()
    result = ctx.get("result") or {}
    plan = ctx.get("plan") or {}
    _render_plan_block(ctx, result, plan)


def _render_plan_block(ctx: dict, result: dict, plan: dict) -> None:
    run_id = state.active_run_id()
    if plan and not ctx.get("consistent"):
        errors.report_mismatch(
            selected_question=state.get(state.KEY_SELECTED_QTEXT) or "(未知)",
            report_question=plan.get("input_question") or "(未知)",
            run_id=run_id,
        )
        return
    if state.run_status() == "failed":
        render_empty("运行失败", "上次运行未成功，未生成可展示的报告。请修复后重试，或加载历史运行。")
        return
    if not plan:
        render_empty("尚未生成研究计划", "请选择问题并生成研究计划，或加载历史运行。")
        return
    components.render_research_plan_tabs(
        plan,
        result.get("evidence_cards") or [],
        result.get("agent_trace") or [],
        run_id=run_id,
        file_reader=api_client.read_local_file,
        quality_gates=result.get("quality_gates"),
        is_mock=bool(result.get("mock")),
        llm_summary=result.get("llm_call_summary") or {},
    )


def page_execution() -> None:
    ctx = _ctx()
    if st.session_state.pop("_sage_focus_q028", None):
        q028 = next((q for q in ctx["questions"] if str(q.get("id")).upper() == "Q028"), None)
        if q028:
            state.select_question("Q028", q028.get("question", ""))
            ctx = bootstrap()
    selected_q = selected_question(ctx["questions"], ctx.get("qid"))
    st.info("「运行受控演示」使用模拟流水线，不是真实实验。Q028 的受控执行入口单独标注。")
    if ctx["mode"] == "real":
        pf_banner = api_client.run_preflight(True, True)
        if pf_banner.get("ok") and pf_banner.get("warnings"):
            st.caption("preflight 提示：" + "；".join(pf_banner.get("warnings", [])))
        elif not pf_banner.get("ok"):
            st.caption("preflight 未通过，真实模式运行将被阻止。")
    action = components.render_run_console(selected_q, _switches(), mode=ctx["mode"])
    _rt("process_run_triggers")(
        trigger_generate=action == "generate",
        trigger_mock=action == "mock",
        questions=ctx["questions"],
        qid=ctx.get("qid"),
        selected_q=selected_q,
        switches=_switches(),
        mode=ctx["mode"],
        trigger_latest=False,
        diag=ctx["diag"],
    )
    ctx = bootstrap()
    result = ctx.get("result") or {}
    plan = ctx.get("plan") or {}
    components.render_agent_pipeline(
        result.get("agent_trace") or [],
        result.get("evidence_cards") or [],
        plan,
        question=selected_q,
        is_mock=bool(result.get("mock")),
        experiment_result=st.session_state.get(components.make_widget_key("exp_run_result", ctx.get("qid"))) if ctx.get("qid") else None,
    )
    if str(ctx.get("qid") or "").upper() == "Q028":
        st.caption("Q028 为受控科研工作流演示，不构成临床验证，也不能外推至所有癌症。")


def page_versions() -> None:
    ctx = _ctx()
    result = ctx.get("result") or {}
    plan = ctx.get("plan") or {}
    run_id = state.active_run_id() if ctx.get("consistent") else None
    if not plan:
        render_empty("尚无版本可审计", "生成研究计划后可查看 Reviewer、修订与反馈。")
        components.render_feedback_panel(run_id, api_client.revise_run)
        return
    st.subheader("评审与质量门")
    comments = plan.get("reviewer_comments") or []
    if comments:
        for item in comments:
            st.markdown(f"- {item}")
    else:
        st.caption("尚无 Reviewer 意见。")
    if result.get("quality_gates"):
        with st.expander("Quality Gates", expanded=False):
            st.json(result.get("quality_gates"))
    revision = result.get("revision_history") or plan.get("revision_history") or []
    st.subheader("修订轨迹")
    if revision:
        for item in revision:
            st.markdown(f"- {item}")
    else:
        st.caption("尚无 RevisionContext / 修订历史。")
    components.render_feedback_panel(run_id, api_client.revise_run)
    llm_calls = api_client.get_llm_calls(run_id) if run_id else {}
    if llm_calls:
        with st.expander("调用审计摘要", expanded=False):
            st.json(llm_calls.get("summary") or {})


def page_history() -> None:
    ctx = _ctx()
    components.section_title("历史", "历史运行", "加载不会自动重跑模型。")
    trigger_latest = st.button("加载最近一次运行", key="hist_latest")
    _rt("process_run_triggers")(
        trigger_generate=False,
        trigger_mock=False,
        questions=ctx["questions"],
        qid=ctx.get("qid"),
        selected_q=selected_question(ctx["questions"], ctx.get("qid")),
        switches=_switches(),
        mode=ctx["mode"],
        trigger_latest=trigger_latest,
        diag=ctx["diag"],
    )
    # 只在整页刷新时强制拉取一次最新运行列表；筛选控件的交互只重跑下方 Fragment，
    # 不会对每次筛选都重新请求 /runs。
    runs = list_runs(limit=40, force=True)
    _render_history_fragment(runs, ctx["questions"])


@st.fragment
def _render_history_fragment(runs: list[dict], questions: list[dict]) -> None:
    """历史运行表：搜索 / 状态过滤只重跑本 Fragment；选中某次运行时触发整页刷新
    （加载运行会改变整个工作区上下文，属于预期的 app 级 rerun）。"""
    q_filter = st.text_input("搜索 Run ID / 问题编号", key="hist_q")
    status_sel = st.multiselect(
        "状态过滤",
        sorted({str(r.get("status") or r.get("validation_status") or "unknown") for r in runs}) or ["unknown"],
        key="hist_status",
    )
    filtered = []
    for item in runs:
        blob = f"{item.get('run_id')} {item.get('question_id')} {item.get('question')}"
        if q_filter.strip() and q_filter.strip().lower() not in blob.lower():
            continue
        stt = str(item.get("status") or item.get("validation_status") or "unknown")
        if status_sel and stt not in status_sel:
            continue
        filtered.append(item)
    chosen = components.render_run_browser(filtered)
    if chosen:
        loaded = api_client.get_run(chosen)
        if _rt("activate_loaded_run")(loaded, questions):
            st.rerun()


def page_results() -> None:
    ctx = _ctx()
    run_id = state.active_run_id() if ctx.get("consistent") else None
    components.section_title(ui_text("step_08"), ui_text("researchplan_export_center"), "导出当前运行的研究计划及其证据链、追踪与质量门。")
    _render_downloads_fragment(run_id)


@st.fragment
def _render_downloads_fragment(run_id: str | None) -> None:
    """下载区：独立 Fragment，切换导出格式/触发下载不重跑工作区。"""
    components.render_researchplan_export_center(run_id, api_client.read_local_file)


def page_knowledge() -> None:
    ctx = _ctx()
    health = ctx.get("health") or {}
    ephemeral_storage = health.get("storage", {}).get("mode") == "ephemeral"
    workspace_subtitle = (
        "当前预览使用临时存储；原文与索引在 API 实例存续期间可跨问题复用。"
        if ephemeral_storage
        else "原文与向量索引保存在项目数据目录；真实嵌入按当前配置调用百炼。"
    )
    components.section_title(ui_text("step_02"), ui_text("data_rag_workspace"), workspace_subtitle)
    library_status = api_client.get_library_status()
    components.render_upload_panel(
        api_client.ingest_files,
        library_status=library_status,
        delete_fn=api_client.delete_library_document,
        validate_fn=api_client.validate_upload_batch,
        ephemeral_storage=ephemeral_storage,
    )


@st.fragment
def _render_provider_status_fragment(health: dict, llm_summary: dict | None) -> None:
    """Provider 状态：独立 Fragment，含手动刷新按钮，只重跑本区域。"""
    if st.button("刷新 Provider 状态", key="settings_refresh_provider"):
        api_client._fetch_health_cached.clear()
        api_client._fetch_diagnostics_cached.clear()
        st.rerun(scope="fragment")
    components.render_system_status(health, llm_summary)
    components.render_security_note()


@st.fragment
def _render_health_check_fragment(ctx: dict[str, Any]) -> None:
    """健康检查 + 技术透明性：独立 Fragment，含手动刷新按钮，只重跑本区域。"""
    health = ctx.get("health") or {}
    if (health.get("storage", {}) or {}).get("mode") == "ephemeral":
        st.warning("当前为临时预览环境；重新部署、休眠或重启后，任务历史与上传资料可能重置。")
    st.subheader("技术透明性")
    col_status, col_refresh = st.columns([5, 1])
    with col_status:
        st.caption(f"健康检查：{health.get('status')} · 文献索引：{health.get('rag_index_status')}")
    with col_refresh:
        if st.button("刷新", key="settings_refresh_health"):
            api_client._fetch_health_cached.clear()
            st.rerun(scope="fragment")
    st.markdown(f"[OpenAPI /docs]({api_client.api_base().rstrip('/')}/docs)")
    llm_calls = api_client.get_llm_calls(state.active_run_id()) if state.active_run_id() else {}
    components.render_developer_diagnostics(health, ctx.get("result") or {}, llm_calls)


def page_settings() -> None:
    ctx = _ctx()
    st.subheader("运行模式与能力")
    mode = components.render_mode_control(ctx["mode"])
    state.set_value(state.KEY_MODE, mode)
    persist_query_mode(mode)
    switches = components.render_pipeline_switches()
    st.session_state["_sage_switches"] = switches
    _render_provider_status_fragment(ctx["health"], (ctx.get("result") or {}).get("llm_call_summary"))
    st.subheader("首次运行向导")
    wiz = components.render_first_run_wizard(_rt("wizard_checks")(ctx["diag"], ctx["api_connected"]))
    if wiz == "refresh":
        bootstrap(refresh_questions=True, refresh_diag=True)
        st.rerun()
    _rt("process_run_triggers")(
        trigger_generate=False,
        trigger_mock=wiz == "mock",
        questions=ctx["questions"],
        qid=ctx.get("qid"),
        selected_q=selected_question(ctx["questions"], ctx.get("qid")),
        switches=switches,
        mode=state.current_mode(),
        trigger_latest=wiz == "latest",
        diag=ctx["diag"],
    )
    _render_health_check_fragment(ctx)

    with st.expander("高级选项"):
        st.caption(
            "旧版控制台（回退）为调试兼容入口，保留原单页控制台的全部功能，"
            "普通使用请优先使用左侧工作区导航。"
        )
        if st.button("打开旧版控制台（回退）", key="settings_open_legacy"):
            st.switch_page(_HOOKS["page_legacy"])
        st.caption("直达链接：/legacy")

    components.render_footer()


def page_legacy() -> None:
    show_workspace_shell()
    st.caption("完整控制台回退页。默认请使用左侧工作区导航。")
    _rt("render_legacy_workspace")()
