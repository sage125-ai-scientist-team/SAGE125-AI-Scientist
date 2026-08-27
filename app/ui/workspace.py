# -*- coding: utf-8 -*-
"""研究工作区外壳：真实状态、顶栏、指标与切页守卫。"""

from __future__ import annotations

import re
from typing import Any

import streamlit as st

from app.ui import api_client, components, state
from app.ui.components import esc
from app.ui.ui_index import UI_INDEX_PATH, load_ui_question_index
from app.ui.ui_index import question_status_map as _question_status_map

_OFFICIAL_QID_RE = re.compile(r"^Q(\d{3})$", re.IGNORECASE)
QUERY_QUESTION_KEY = "question_id"
QUERY_QUESTION_LEGACY_KEY = "qid"

BOOT_QUESTIONS = "_sage_questions"
BOOT_HEALTH = "_sage_health"
BOOT_DIAG = "_sage_diag"
BOOT_API = "_sage_api_connected"
BOOT_RUNS_CACHE = "_sage_runs_cache"


def hide_sidebar() -> None:
    """首页隐藏侧栏由 style.css 的 `.stApp:has(.land-page)` 一次注入，
    不再每次 rerun 追加 ``<style>``，避免返回首页后 style 标签累积。"""
    return None


def show_workspace_shell() -> None:
    """工作区侧栏样式固定在 style.css，避免每次切页追加 style 标签。"""
    return None


def bootstrap(*, refresh_questions: bool = False, refresh_diag: bool = False) -> dict[str, Any]:
    """加载并缓存题目清单；健康状态每次刷新。切页不触发模型调用。"""
    health = api_client.get_health()
    st.session_state[BOOT_HEALTH] = health
    api_connected = api_client.api_available()
    st.session_state[BOOT_API] = api_connected

    if refresh_questions or BOOT_QUESTIONS not in st.session_state:
        q_resp = api_client.get_questions()
        questions = q_resp.get("questions", []) if q_resp.get("status") == "ok" else []
        st.session_state[BOOT_QUESTIONS] = questions
        st.session_state["_sage_q_resp"] = q_resp
    questions = list(st.session_state.get(BOOT_QUESTIONS) or [])

    if refresh_diag or BOOT_DIAG not in st.session_state:
        st.session_state[BOOT_DIAG] = api_client.get_diagnostics()
    diag = st.session_state.get(BOOT_DIAG) or {}

    apply_query_question(questions)
    apply_pending_question(questions)
    from app.ui.job_state import (
        JOB_TYPE_DEMO,
        JOB_TYPE_FULL,
        ensure_client_id,
        rehydrate_job_state,
    )

    client_id = ensure_client_id()
    qid = state.get(state.KEY_SELECTED_QID)
    if qid:
        rehydrate_job_state(client_id, str(qid), JOB_TYPE_FULL)
        from app.ui.job_state import get_pointer_job_id, persist_query_job

        if get_pointer_job_id(str(qid), JOB_TYPE_DEMO):
            rehydrate_job_state(client_id, str(qid), JOB_TYPE_DEMO)
        pointer = get_pointer_job_id(str(qid), JOB_TYPE_FULL) or get_pointer_job_id(
            str(qid), JOB_TYPE_DEMO
        )
        if pointer:
            persist_query_job(pointer)

    result = state.get_run_result()
    return {
        "health": health,
        "diag": diag,
        "api_connected": api_connected,
        "questions": questions,
        "result": result,
        "plan": result.get("plan") or {},
        "qid": state.get(state.KEY_SELECTED_QID),
        "qtext": official_question_text(state.get(state.KEY_SELECTED_QID), questions),
        "mode": state.current_mode(),
        "consistent": state.is_run_consistent(),
    }


def official_question_text(qid: str | None, questions: list[dict] | None = None) -> str:
    """按 question_id 实时查询官方标题，不使用 session 里的旧 label。"""
    official = official_question_id(qid)
    if not official:
        return ""
    try:
        from app.catalog.official import get_question

        item = get_question(official)
        if item is not None:
            return item.display_title()
    except Exception:
        pass
    for row in questions or []:
        if str(row.get("id") or row.get("question_id") or "").upper() == official:
            return str(row.get("title_en") or row.get("question") or "")
    return ""


def format_question_option(question_id: str, questions: list[dict] | None = None) -> str:
    if not question_id:
        return "选择科学问题"
    title = official_question_text(question_id, questions)
    return f"{question_id} · {title}" if title else str(question_id)


def sanitize_question_selector_state(question_ids: list[str]) -> None:
    """丢掉非法 widget / 业务状态，必须在 selectbox 创建前调用。"""
    valid = {str(qid) for qid in question_ids if qid}
    stored = official_question_id(state.get(state.KEY_SELECTED_QID))
    if stored not in valid:
        st.session_state[state.KEY_SELECTED_QID] = None
        st.session_state[state.KEY_SELECTED_QTEXT] = None
    widget = st.session_state.get(components.SELECTOR_WIDGET_KEY)
    if widget not in valid and widget not in (None, ""):
        st.session_state.pop(components.SELECTOR_WIDGET_KEY, None)


def official_question_id(raw: Any) -> str | None:
    """仅接受官方目录 Q001—Q125。"""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    qid = str(raw or "").strip().upper()
    matched = _OFFICIAL_QID_RE.match(qid)
    if not matched:
        return None
    if not 1 <= int(matched.group(1)) <= 125:
        return None
    return qid


def apply_query_question(questions: list[dict]) -> None:
    """从 URL 恢复当前问题。已有合法 Session 时不得被 query 覆盖。"""
    current = official_question_id(state.get(state.KEY_SELECTED_QID))
    if current:
        return
    try:
        raw = st.query_params.get(QUERY_QUESTION_KEY) or st.query_params.get(QUERY_QUESTION_LEGACY_KEY)
    except Exception:
        raw = None
    qid = official_question_id(raw)
    if not qid:
        return
    item = next((q for q in questions if str(q.get("id", "")).upper() == qid), None)
    if item:
        state.select_question(str(item.get("id")), item.get("question", ""))


def persist_query_question(qid: str | None) -> None:
    """把当前问题写入 URL，便于刷新与分享。"""
    try:
        official = official_question_id(qid)
        if official:
            st.query_params[QUERY_QUESTION_KEY] = official
            st.query_params[QUERY_QUESTION_LEGACY_KEY] = official
        else:
            for key in (QUERY_QUESTION_KEY, QUERY_QUESTION_LEGACY_KEY):
                if key in st.query_params:
                    del st.query_params[key]
    except Exception:
        pass
    from app.ui.job_state import ensure_client_id

    ensure_client_id()


def apply_pending_question(questions: list[dict]) -> str | None:
    """消费 preset/历史排队的选题，并同步唯一选择器 widget。"""
    pending_qid = state.consume_question_selection()
    if pending_qid and any(str(q.get("id")) == pending_qid for q in questions):
        st.session_state[components.QUESTION_KEYWORD_WIDGET_KEY] = ""
        st.session_state[components.QUESTION_DOMAIN_WIDGET_KEY] = "全部"
        st.session_state[components.SELECTOR_WIDGET_KEY] = pending_qid
        pending_item = next(q for q in questions if str(q.get("id")) == pending_qid)
        state.select_question(pending_qid, pending_item.get("question", ""))
        persist_query_question(pending_qid)
        st.session_state[components.PICKER_EXPANDED_KEY] = False
        return pending_qid
    return None


def load_question_selector_state() -> None:
    st.session_state[components.SELECTOR_WIDGET_KEY] = st.session_state.get(state.KEY_SELECTED_QID)


def store_question_selector_state() -> None:
    selected = st.session_state.get(components.SELECTOR_WIDGET_KEY)
    if not selected:
        return
    questions = list(st.session_state.get(BOOT_QUESTIONS) or [])
    item = next((q for q in questions if str(q.get("id")) == str(selected)), None)
    text = str((item or {}).get("question") or state.get(state.KEY_SELECTED_QTEXT) or "")
    state.select_question(str(selected), text)
    persist_query_question(str(selected))
    st.session_state[components.PICKER_EXPANDED_KEY] = False


def picker_is_expanded() -> bool:
    qid = state.get(state.KEY_SELECTED_QID)
    if not qid:
        return True
    return bool(st.session_state.get(components.PICKER_EXPANDED_KEY))


def selected_question(questions: list[dict], qid: str | None) -> dict | None:
    if not qid:
        return None
    return next((q for q in questions if str(q.get("id")) == str(qid)), None)


def research_status(ctx: dict[str, Any]) -> tuple[str, str]:
    """由真实 session / plan 推导状态文案与语义色，禁止硬编码「研究中」。"""
    qid = ctx.get("qid")
    plan = ctx.get("plan") or {}
    result = ctx.get("result") or {}
    if not qid:
        return "未选题", "idle"
    rs = state.run_status()
    try:
        from app.ui.job_state import JOB_TYPE_DEMO, JOB_TYPE_FULL, get_pointer_job_id, is_active, ui_status
        from app.ui import api_client as jobs_api

        pointer_jobs = []
        for job_type in (JOB_TYPE_FULL, JOB_TYPE_DEMO):
            job_id = get_pointer_job_id(qid, job_type)
            if job_id:
                pointer_jobs.append(jobs_api.get_job(job_id))
        if any(is_active(job) for job in pointer_jobs):
            return "执行中", "running"
        kinds = {ui_status(job) for job in pointer_jobs if job}
        if "FAILED" in kinds:
            return "需要补充证据", "error"
        if "PARTIAL" in kinds:
            return "部分完成", "warning"
        if "SUCCEEDED" in kinds:
            return "已形成计划", "info"
    except Exception:
        pass
    if rs == "running":
        return "执行中", "running"
    if rs == "failed":
        return "需要补充证据", "error"
    if plan:
        vs = str(plan.get("validation_status") or "")
        mapped = {
            "validated": ("已完成", "success"),
            "ready_for_validation": ("等待评审", "info"),
            "needs_data": ("需要补充证据", "warning"),
            "draft": ("已形成计划", "info"),
        }
        if vs in mapped:
            return mapped[vs]
        return "已形成计划", "info"
    if rs == "partial_failed":
        return "部分完成", "warning"
    if result.get("run_id"):
        return "已形成计划", "info"
    return "尚未开始", "idle"


def flow_progress(ctx: dict[str, Any]) -> tuple[int | None, str]:
    """按真实产物估算流程进度；无法计算时返回 None。"""
    plan = ctx.get("plan") or {}
    result = ctx.get("result") or {}
    evidence = result.get("evidence_cards") or []
    hyps = plan.get("generated_hypotheses") or []
    if state.run_status() == "running":
        return None, "流水线执行中"
    if not ctx.get("qid"):
        return 0, "尚未选择科学问题"
    stages = [
        bool(ctx.get("qid")),
        bool(evidence),
        bool(hyps),
        bool(plan),
        bool(plan.get("reviewer_comments") or result.get("quality_gates")),
    ]
    done = sum(1 for item in stages if item)
    if done == 0:
        return 0, "尚未开始研究流程"
    return int(round(100 * done / len(stages))), f"已完成 {done}/{len(stages)} 个可观测阶段"


def list_runs(limit: int = 40, *, force: bool = False) -> list[dict]:
    if force or BOOT_RUNS_CACHE not in st.session_state:
        st.session_state[BOOT_RUNS_CACHE] = api_client.get_runs(limit=limit) or []
    return list(st.session_state.get(BOOT_RUNS_CACHE) or [])


def _ui_index_fingerprint() -> float:
    """轻量 UI 索引文件的 mtime；文件被重建后自动失效 st.cache_data 缓存。"""
    try:
        return UI_INDEX_PATH.stat().st_mtime
    except OSError:
        return 0.0


@st.cache_data(ttl=60, show_spinner=False)
def _load_ui_question_index_cached(_fingerprint: float) -> dict[str, dict]:
    return _question_status_map(load_ui_question_index())


def get_ui_question_index_cached() -> dict[str, dict]:
    """按 question_id 返回轻量 UI 索引（{question_id: {status,evidence_count,...}}）。

    首页 / 工作区概览 / 题目筛选应优先读这份索引，而不是每次都遍历 125 题目录
    或拉取全量 /runs；索引本身只在 `data/ui/ui_question_index.json` 的 mtime
    变化（即被 `build_ui_question_index()` 重建）时才重新解析。
    """
    return _load_ui_question_index_cached(_ui_index_fingerprint())


def load_question_index() -> dict[str, dict]:
    return get_ui_question_index_cached()


@st.cache_data(ttl=60, show_spinner=False)
def load_question_summary(question_id: str, digest: float) -> dict[str, Any]:
    """按题号读取轻量摘要，digest 变化才失效；不扫描全部 125 题报告目录。"""
    return dict(get_ui_question_index_cached().get(str(question_id)) or {})


@st.cache_data(show_spinner=False)
def load_domain_distribution(fingerprint: tuple[tuple[str, str], ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _qid, domain in fingerprint:
        key = str(domain or "Unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


@st.cache_data(show_spinner=False)
def load_domain_chart(fingerprint: tuple[tuple[str, str], ...]):
    from app.ui import charts as _charts

    synthetic = [{"id": qid, "domain": domain} for qid, domain in fingerprint]
    return _charts.make_domain_coverage_chart(synthetic)


def questions_fingerprint(questions: list[dict]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(item.get("id") or ""), str(item.get("domain") or "Unknown"))
        for item in questions
    )


def refresh_ui_question_index() -> dict[str, dict]:
    """用户主动刷新：强制重建轻量 UI 索引（对应第十四节「用户主动刷新」）。"""
    from app.ui.ui_index import build_ui_question_index

    build_ui_question_index()
    _load_ui_question_index_cached.clear()
    return get_ui_question_index_cached()


def landing_metrics_raw(ctx: dict[str, Any], summary: dict[str, Any] | None = None) -> dict[str, Any]:
    """首页统计只读 ``ui_summary``，不再用当前会话证据或最近 50 次运行冒充全库。"""
    from app.ui.ui_summary import load_or_build_ui_summary

    questions = ctx.get("questions") or []
    health = ctx.get("health") or {}
    payload = summary if isinstance(summary, dict) else load_or_build_ui_summary()
    status = str(payload.get("status") or "error")
    q028 = any(str(q.get("id", "")).upper() == "Q028" for q in questions) or (
        (payload.get("official_question_count") or 0) == 125
    )
    return {
        "question_count": payload.get("official_question_count"),
        "evidence_count": payload.get("traceable_evidence_count"),
        "plan_count": payload.get("research_plan_count"),
        "coverage": payload.get("evidence_link_coverage"),
        "coverage_status": payload.get("evidence_link_coverage_status"),
        "stats_status": status,
        "stats_error": payload.get("error"),
        "missing_question_ids": payload.get("missing_question_ids") or [],
        "q028_available": q028,
        "service_status": health.get("status"),
        "traceable_evidence_question_count": payload.get("traceable_evidence_question_count"),
        "invalid_evidence_card_count": payload.get("invalid_evidence_card_count"),
        "total_supporting_evidence_links": payload.get("total_supporting_evidence_links"),
        "resolved_supporting_evidence_links": payload.get("resolved_supporting_evidence_links"),
        "unresolved_supporting_evidence_links": payload.get("unresolved_supporting_evidence_links"),
    }


def landing_metrics(ctx: dict[str, Any]) -> list[tuple[str, str]]:
    """首页真实统计（字符串展示版）。状态机：加载中 / 已计算 / 未计算 / 数据异常。"""
    raw = landing_metrics_raw(ctx)
    status = raw.get("stats_status")
    if status == "source_invalid":
        mark = "数据异常"
        return [
            ("官方科学问题", mark),
            ("可追溯证据", mark),
            ("研究计划", mark),
            ("证据回链覆盖", mark),
        ]

    def _num(value: Any) -> str:
        return str(value) if value is not None else "数据异常"

    coverage_status = raw.get("coverage_status")
    if coverage_status == "unavailable":
        coverage_text = "未计算"
    elif coverage_status == "calculated" and raw.get("coverage") is not None:
        coverage_text = f"{raw['coverage']:.1f}%"
    else:
        coverage_text = "数据异常"
    return [
        ("官方科学问题", _num(raw.get("question_count"))),
        ("可追溯证据", _num(raw.get("evidence_count"))),
        ("研究计划", _num(raw.get("plan_count"))),
        ("证据回链覆盖", coverage_text),
    ]


def render_workspace_header(ctx: dict[str, Any]) -> None:
    """工作区顶栏：只读当前问题上下文 + 状态 + 系统菜单。禁止下拉选题。"""
    qid = ctx.get("qid") or None
    if qid:
        label, kind = research_status(ctx)
        title = official_question_text(qid, ctx.get("questions") or [])
        context_value = f"{qid} · {title}" if title else str(qid)
    else:
        label, kind = "未开始", "idle"
        context_value = "尚未选择科学问题"

    with st.container(key="ws_topbar"):
        head_col, ctrl_col = st.columns([1.5, 2.0], vertical_alignment="center")
        with head_col:
            st.markdown(
                '<div class="ws-topbar"><div class="ws-kicker">研究工作区</div>'
                "<h1>探索、验证并推进科学发现</h1></div>",
                unsafe_allow_html=True,
            )
        with ctrl_col:
            ctx_col, sys_col = st.columns([3.2, 0.55], vertical_alignment="center")
            with ctx_col:
                st.markdown(
                    f"""<div class="workspace-context">
                      <div class="question-context-readonly">
                        <span class="context-label">当前问题</span>
                        <span class="context-value">{esc(context_value)}</span>
                      </div>
                      <span class="question-status ws-status ws-status-{esc(kind)}">{esc(label)}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
            with sys_col:
                with st.popover("系统", use_container_width=False):
                    health = ctx.get("health") or {}
                    st.caption(f"API：{'已连接' if ctx.get('api_connected') else '未连接'}")
                    st.caption(f"健康状态：{health.get('status') or '—'}")
                    st.caption("此菜单仅显示系统状态。当前部署未提供账户体系。")
                    docs = f"{api_client.api_base().rstrip('/')}/docs"
                    st.markdown(f"[OpenAPI 文档]({docs})")
    from app.ui.job_state import render_global_job_status_bar

    render_global_job_status_bar(qid)


def render_unselected_guide(go_questions: Any | None = None, *, already_on_hub: bool = False) -> None:
    """未选题时的紧凑引导卡。按钮只滚动到唯一选择器，不打开第二套页面。"""
    st.markdown(
        """<div class="ws-guide-card">
          <div>
            <div class="ws-guide-title">尚未选择科学问题</div>
            <div class="ws-guide-hint">从 125 道官方问题中选择一题，开始整理证据并形成研究计划。</div>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )
    if st.button("选择科学问题", key="ws_guide_pick"):
        from app.ui.scroll_trigger import request_question_picker, request_scroll

        if already_on_hub:
            request_scroll("question-picker")
        else:
            request_question_picker(switch_page=go_questions)


def render_overview_skeleton() -> None:
    """工作区概览首屏 Skeleton（第十五节）。

    在 `bootstrap()` 真实数据（健康检查/题库/最近运行）到达前立即渲染：
    顶部栏、四张状态卡、研究计划区块、四个快速操作卡、最新动态占位行。
    纯 CSS，无需等待任何网络请求，配合 Streamlit 的增量渲染（脚本执行到这里
    就会被发送到浏览器），可在真实数据就位前先给出可感知的加载反馈，
    避免大面积深蓝空白页。
    """
    st.markdown(
        """
<div class="ws-skel ws-skel-topbar"></div>
<div class="ws-skel-kpi-row">
  <div class="ws-skel ws-skel-kpi"></div>
  <div class="ws-skel ws-skel-kpi"></div>
  <div class="ws-skel ws-skel-kpi"></div>
  <div class="ws-skel ws-skel-kpi"></div>
</div>
<div class="ws-skel ws-skel-block"></div>
<div class="ws-skel-actions-row">
  <div class="ws-skel ws-skel-action"></div>
  <div class="ws-skel ws-skel-action"></div>
  <div class="ws-skel ws-skel-action"></div>
  <div class="ws-skel ws-skel-action"></div>
</div>
<div class="ws-skel ws-skel-block"></div>
""",
        unsafe_allow_html=True,
    )


def render_empty(title: str, hint: str) -> None:
    """无 Emoji 的空状态。"""
    st.markdown(
        f"""<div class="glass-card sage-empty">
            <div class="sage-empty-title">{esc(title)}</div>
            <div class="sage-empty-hint">{esc(hint)}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def hypothesis_rows(plan: dict) -> list[dict]:
    rows = []
    for i, item in enumerate(plan.get("generated_hypotheses") or []):
        if not isinstance(item, dict):
            continue
        rows.append({
            "id": item.get("id") or f"H{i+1}",
            "statement": item.get("hypothesis") or item.get("statement") or "",
            "mechanism": item.get("mechanism") or "",
            "prediction": item.get("falsifiable_prediction") or item.get("prediction") or "",
            "observations": item.get("required_observations") or [],
            "risk": item.get("risk_of_being_wrong") or item.get("uncertainty") or "",
            "support": item.get("supporting_evidence") or item.get("support_evidence") or [],
            "against": item.get("opposing_evidence") or item.get("against_evidence") or [],
            "alternatives": item.get("alternative_explanations") or [],
            "boundary": item.get("scope") or item.get("applicability") or "",
            "raw": item,
        })
    return rows


def referenced_ids(plan: dict) -> set[str]:
    return {
        str(ref.get("id"))
        for ref in (plan.get("references") or [])
        if isinstance(ref, dict) and ref.get("id")
    }
