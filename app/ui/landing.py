# -*- coding: utf-8 -*-
"""科学产品首页：单一 Custom Component + 统计 Fragment。"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
from sage125_landing import sage125_landing

from app.ui.components import esc
from app.ui.ui_summary import UI_SUMMARY_PATH, SCHEMA_VERSION, load_or_build_ui_summary
from app.ui.results_root import resolve_results_root
from app.ui.workspace import landing_metrics_raw


def _brand_mark() -> str:
    return """
<svg class="land-mark" viewBox="0 0 32 32" role="img" aria-label="SAGE125 标志">
  <defs>
    <linearGradient id="sageMarkGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#4D7FFF"/>
      <stop offset="100%" stop-color="#27C5D7"/>
    </linearGradient>
  </defs>
  <polygon points="16,2 28,9 28,23 16,30 4,23 4,9"
           fill="rgba(19,38,62,0.9)" stroke="url(#sageMarkGrad)" stroke-width="1.4"/>
  <line x1="16" y1="10" x2="10" y2="16" stroke="rgba(169,201,235,0.65)" stroke-width="1"/>
  <line x1="16" y1="10" x2="22" y2="16" stroke="rgba(169,201,235,0.65)" stroke-width="1"/>
  <line x1="10" y1="16" x2="16" y2="22" stroke="rgba(169,201,235,0.65)" stroke-width="1"/>
  <line x1="22" y1="16" x2="16" y2="22" stroke="rgba(169,201,235,0.65)" stroke-width="1"/>
  <circle cx="16" cy="10" r="2.3" fill="#4D7FFF"/>
  <circle cx="10" cy="16" r="1.8" fill="#27C5D7"/>
  <circle cx="22" cy="16" r="1.8" fill="#27C5D7"/>
  <circle cx="16" cy="22" r="2.1" fill="#4D7FFF"/>
</svg>"""


def _summary_fingerprint() -> tuple[str, float, str]:
    resolved = resolve_results_root()
    try:
        mtime = UI_SUMMARY_PATH.stat().st_mtime
    except OSError:
        mtime = 0.0
    root = str(resolved.results_root or "")
    return root, mtime, SCHEMA_VERSION


@st.cache_data(show_spinner=False)
def _cached_ui_summary(root: str, mtime: float, schema: str) -> dict[str, Any]:
    del root, schema
    if mtime <= 0 or not UI_SUMMARY_PATH.exists():
        return {"status": "loading", "error": None}
    try:
        payload = json.loads(UI_SUMMARY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "loading", "error": None}
    return payload if isinstance(payload, dict) else {"status": "loading", "error": None}


def _go_workspace() -> None:
    st.session_state["_sage_nav_target"] = "workspace"


def _go_q028() -> None:
    st.session_state["_sage_focus_q028"] = True
    st.session_state["_sage_nav_target"] = "q028"


@st.fragment
def _stats_refresh_fragment() -> None:
    """只刷新统计读取，不包裹 Hero / tsParticles / Bento。"""
    if not UI_SUMMARY_PATH.exists():
        load_or_build_ui_summary(force=True)
        _cached_ui_summary.clear()
        st.rerun()
    if st.button("刷新统计", key="land_refresh_stats"):
        load_or_build_ui_summary(force=True)
        _cached_ui_summary.clear()
        st.rerun(scope="fragment")


def render_landing(ctx: dict[str, Any], *, workspace_page, case_page) -> None:
    from app.ui import api_client

    api_client.wake_hosted_api(wait=False)
    st.markdown(
        f"""
<div class="land-page">
  <header class="land-nav" role="banner">
    <div class="land-brand">
      {_brand_mark()}
      <div>
        <div class="land-brand-name">SAGE125</div>
        <div class="land-brand-sub">AI Scientist</div>
      </div>
    </div>
    <nav class="land-nav-links" aria-label="首页导航">
      <a href="#land-home">首页</a>
      <a href="#land-capabilities">系统能力</a>
      <a href="#land-case">代表案例</a>
      <a href="#land-transparency">技术透明性</a>
      <a class="land-nav-cta" href="#land-home">进入研究工作区</a>
    </nav>
  </header>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div id="land-home"></div>', unsafe_allow_html=True)

    try:
        summary = _cached_ui_summary(*_summary_fingerprint())
        metrics = landing_metrics_raw(ctx, summary)
        stats_status = "calculated" if summary.get("status") == "calculated" else (
            "error" if summary.get("status") == "source_invalid" else "loading"
        )
    except Exception:
        metrics = landing_metrics_raw(ctx, {"status": "source_invalid", "error": "数据异常"})
        stats_status = "error"
        summary = {}

    sage125_landing(
        q028_available=bool(metrics.get("q028_available")),
        question_count=metrics.get("question_count"),
        evidence_count=metrics.get("evidence_count"),
        plan_count=metrics.get("plan_count"),
        coverage=metrics.get("coverage"),
        coverage_status=metrics.get("coverage_status"),
        stats_status=stats_status,
        on_enter_workspace=_go_workspace,
        on_view_q028=_go_q028,
        key="sage125-landing-home-v2",
    )

    if stats_status == "error" and (summary.get("missing_question_ids") or metrics.get("missing_question_ids")):
        missing = summary.get("missing_question_ids") or metrics.get("missing_question_ids") or []
        st.error("数据源未通过完整性校验。缺失题号：" + ", ".join(str(item) for item in missing[:24]))

    st.markdown('<div id="land-capabilities"></div>', unsafe_allow_html=True)
    _stats_refresh_fragment()

    nav_target = st.session_state.pop("_sage_nav_target", None)
    if nav_target == "workspace":
        st.switch_page(workspace_page)
    elif nav_target == "q028":
        st.switch_page(case_page)

    steps = [
        "从官方 125 题中选定研究对象",
        "检索并核验可定位的文献证据",
        "标明尚未被证据覆盖的问题",
        "形成可证伪的机制陈述",
        "对照证据、评审与质量门",
        "给出变量、步骤与判定条件",
        "保留版本与停止原因",
    ]
    step_titles = ["科学问题", "文献探索", "知识缺口", "候选假设", "假设核验", "研究计划", "反馈修订"]
    flow_html = "".join(
        f'<li class="land-step"><strong>{esc(title)}</strong><span>{esc(body)}</span></li>'
        for title, body in zip(step_titles, steps, strict=True)
    )
    st.markdown(
        f"""
<section class="land-section" id="land-loop">
  <h2>科研闭环</h2>
  <ol class="land-flow">{flow_html}</ol>
</section>
<section class="land-section" id="land-case">
  <h2>代表案例 Q028</h2>
  <p>该案例沿官方问题组织真实证据、Round 1、Reviewer、RevisionContext、Round 2、受控执行、消融与科学边界。它是受控科研工作流演示，不构成临床验证，也不能外推至所有癌症。</p>
</section>
        """,
        unsafe_allow_html=True,
    )
    if st.button("查看 Q028 完整案例", key="land_q028_full"):
        st.session_state["_sage_focus_q028"] = True
        st.switch_page(case_page)

    st.markdown(
        """
<section class="land-section" id="land-transparency">
  <h2>技术透明性</h2>
  <p>模型提供方、本次调用、文献索引与 Provider Audit 属于系统状态，不作为首页卖点。请在研究工作区的设置页查看。</p>
</section>
<footer class="land-footer">SAGE125 AI Scientist · 将科学问题转化为可验证研究计划 · 本系统不是百科问答工具</footer>
        """,
        unsafe_allow_html=True,
    )
