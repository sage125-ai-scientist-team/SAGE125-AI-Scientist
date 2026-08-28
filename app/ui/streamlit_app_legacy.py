"""
app.ui.streamlit_app —— 科研发现控制台（Science Exploration Console）。

专业 AI Scientist 工作台，页面区域：
System Hero / First Run Wizard / Select Scientific Question / Data & RAG Workspace /
AI Scientist Run Console / Agent Observatory / Evidence Wall / ResearchPlan Studio /
Human Feedback Bench / ResearchPlan Export Center / Developer Diagnostics。

核心保证：
    - 用户选择哪个问题，系统就只围绕该问题生成/展示 ResearchPlan（防串线）；
    - mock / real 模式严格区分；real 模式不 silent fallback 到 mock；
    - 运行进度展示友好的千问型号名称；内部请求信息仅在 Developer Diagnostics 展示；
    - 全程深色科学主题；所有 widget key 唯一。

启动：streamlit run app/ui/streamlit_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 确保项目根在 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from app.ui import api_client, charts, components, errors, state, validators
from app.ui.i18n import PRESET_KEYWORDS, preset_label, ui_text


def _find_qid_for_preset(questions: list[dict], preset_key: str) -> str | None:
    """按快速示例内部 key 对应的关键词匹配一个 question_id。"""
    keywords = PRESET_KEYWORDS.get(preset_key, [preset_key])
    for q in questions:
        text = q.get("question", "").lower()
        if all(k in text for k in keywords):
            return q.get("id")
    return None

# 回退入口独立启动时配置页面；被新入口导入时忽略重复配置。
try:
    st.set_page_config(page_title="SAGE125 AI Scientist", page_icon=":material/science:", layout="wide", initial_sidebar_state="expanded")
except Exception:
    pass


def _wizard_checks(diag: dict, api_connected: bool) -> list[dict]:
    """由诊断信息构造 First Run Wizard 检查项。"""
    q = diag.get("questions", {})
    rag = diag.get("rag_index", {})
    library = diag.get("library", {})

    def _st(cond_ok, cond_warn=False):
        return "ok" if cond_ok else ("warning" if cond_warn else "missing")

    return [
        {"label": "Questions 125", "status": "ok" if q.get("count") == 125 else _st(False, q.get("exists")),
         "detail": f"当前 {q.get('count', 0)} 个", "fix": "py -3 scripts/extract_125_questions.py"},
        {"label": "用户文献索引", "status": _st(library.get("status") in {"empty", "ready", "degraded"}, True),
         "detail": f"chunks={rag.get('chunk_count', 0)}；空库可运行，题源不会作证据", "fix": "在 STEP 02 上传真实参考资料"},
        {"label": "DASHSCOPE_API_KEY", "status": _st(diag.get("qwen", {}).get("configured"), True),
         "detail": "Mock 模式无需 Key；真实模式需配置", "fix": "py -3 scripts/setup_env.py"},
        {"label": "API Server", "status": _st(api_connected, True),
         "detail": "未连接时 Mock 可用 in-process 回退；真实模式请先启动 API", "fix": "uvicorn app.api.main:app --reload --port 8000"},
        {"label": "Mock Mode", "status": "ok", "detail": "可用（无需 Key，可直接演示）", "fix": ""},
        {"label": "Latest Run", "status": _st(bool(diag.get("latest_run")), True),
         "detail": (diag.get("latest_run") or {}).get("run_id", "暂无"), "fix": ""},
    ]


def _do_run(qid: str, mode: str, switches: dict, progress_callback=None) -> dict:
    """执行一次 pipeline 运行。"""
    return api_client.start_run(
        qid, "", switches, mode=mode, progress_callback=progress_callback
    )


def _execute_run(qid: str, run_mode: str, switches: dict) -> dict:
    """在 st.status 内执行运行并返回结果 dict。"""
    try:
        with st.status("AI Scientist 正在运行多智能体流水线…", expanded=True) as status_box:
            st.write("Supervisor → QuestionParser → QueryPlanner → RAG / DeepResearch / OpenLiterature")
            st.write("→ EvidenceExtractor → HypothesisGenerator → ExperimentDesigner → Reviewer → ReportWriter → Validator")
            if run_mode == "real":
                dr_note = "（已启用 DeepResearch，可能额外耗时数分钟）" if switches.get("use_deep_research") else "（DeepResearch 已关闭）"
                st.caption(f"真实模式将调用 Qwen/百炼，通常需 15–25 分钟，请勿关闭页面。{dr_note}")
            progress_slot = st.empty()
            latest_progress: dict = {}

            def _update_progress(payload: dict) -> None:
                # Reuse one placeholder so progress updates do not alter the page
                # structure or append an ever-growing list of cards.
                latest_progress.clear()
                latest_progress.update(payload or {})
                progress_slot.empty()
                with progress_slot.container():
                    components.render_run_progress(payload)

            _update_progress({
                "stage": "preparing",
                "status": "queued",
                "percent": 1,
                "message": "任务已提交，正在准备运行环境",
            })
            run_result = _do_run(qid, run_mode, switches, progress_callback=_update_progress)
            st_val = run_result.get("status", "failed")
            if st_val in ("completed", "partial_failed"):
                _update_progress({
                    "stage": "completed", "status": "completed", "percent": 100,
                    "message": "AI Scientist 运行完成，正在展示研究计划",
                })
                label = "运行完成" if st_val == "completed" else "运行完成（部分步骤失败，见警告）"
                if run_result.get("recovered_from_timeout"):
                    label += "（已从超时中恢复）"
                status_box.update(label=label, state="complete", expanded=True)
            else:
                err_text = "; ".join(str(x) for x in (run_result.get("errors") or []))
                # Preserve the last real stage/model on failure. If Reviewer or
                # ReportWriter fails, the card must not jump back to 1%/“准备中”.
                failed_progress = dict(latest_progress)
                if run_result.get("error_type") == "preflight_failed":
                    failed_progress.update({"stage": "preflight", "percent": 4})
                elif not failed_progress:
                    failed_progress.update({"stage": "preparing", "percent": 1})
                failed_progress.update({
                    "status": "failed",
                    "message": err_text or "本次运行未能完成，请查看下方修复建议",
                })
                _update_progress(failed_progress)
                status_box.update(label="运行失败", state="error", expanded=True)
        return run_result
    except Exception as exc:  # noqa: BLE001
        errors.unexpected_error("运行出错", exc)
        return {"status": "failed", "errors": [str(exc)], "error_type": type(exc).__name__}


def _handle_run_result(qid: str, run_mode: str, run_result: dict) -> None:
    """根据 RunResponse 更新 session；失败时不展示旧 report。"""
    st_val = run_result.get("status", "failed")
    if st_val in ("completed", "partial_failed") and run_result.get("plan"):
        plan = run_result.get("plan") or {}
        if str(plan.get("question_id", qid)) != str(qid):
            errors.report_mismatch(
                state.get(state.KEY_SELECTED_QTEXT) or qid,
                plan.get("input_question") or plan.get("question_id", ""),
                run_id=run_result.get("run_id"),
            )
            state.fail_run(run_result.get("run_id"))
            return
        state.set_run_result(run_result, question_id=qid)
        if run_result.get("recovered_from_timeout"):
            st.info(f"HTTP 超时后已从本地恢复运行：{run_result.get('run_id')}")
        llm_summary = run_result.get("llm_call_summary") or {}
        if run_mode == "real" and st_val == "completed" and llm_summary.get("qwen_call_count", 0) == 0:
            st.warning("真实模式未检测到 Qwen 调用，请检查 pipeline 配置。")
        if st_val == "partial_failed":
            st.warning("部分步骤失败（如 DeepResearch），请查看 warnings 与 Developer Diagnostics。")
    else:
        state.fail_run(run_result.get("run_id"))
        errs = run_result.get("errors") or [run_result.get("message", "未知错误")]
        errors.run_failed(
            "; ".join(str(e) for e in errs),
            run_id=run_result.get("run_id"),
            error_type=run_result.get("error_type"),
            mode=run_mode,
        )


def _activate_loaded_run(loaded: dict, questions: list[dict]) -> bool:
    """Atomically bind a loaded artifact, canonical question state and selector."""

    plan = loaded.get("plan") or {}
    qid = plan.get("question_id") or loaded.get("question_id")
    if not qid:
        return False
    item = next((q for q in questions if str(q.get("id")) == str(qid)), None)
    qtext = (item or {}).get("question") or plan.get("input_question") or ""
    state.select_question(str(qid), str(qtext))
    state.set_run_result(loaded, question_id=str(qid))
    state.set_value(state.KEY_OFFLINE, True)
    state.queue_question_selection(str(qid))
    return True


def main() -> None:
    """页面主入口。"""
    # 每次 rerun 都注入 CSS（防止交互后主背景变白），并重置 key 登记表。
    components.load_css()
    state.init_state()

    health = api_client.get_health()
    diag = api_client.get_diagnostics()
    api_connected = api_client.api_available()
    q_resp = api_client.get_questions()
    questions = q_resp.get("questions", []) if q_resp.get("status") == "ok" else []

    # 当前运行结果与 Qwen 调用摘要（用于 Hero/徽标）。
    result = state.get_run_result()
    llm_summary = result.get("llm_call_summary", {}) or {}
    qwen_calls = llm_summary.get("qwen_call_count")
    last_run_mode = "mock" if result.get("mock") else ("real" if result.get("mock") is False else None)

    mode = state.current_mode()

    # ---- 0) System Hero ----
    hero_status = {
        "qwen": health.get("qwen_config_loaded", False),
        "deep_research": health.get("deep_research_config_loaded", False),
        "rag_ready": health.get("rag_index_status") in {"ready", "empty"},
        "rag_status": health.get("rag_index_status"),
        "questions_ok": len(questions) == 125,
        "mode": mode,
        "qwen_calls": qwen_calls,
    }
    components.render_hero(hero_status, {"questions": len(questions), "agents": 10})
    components.render_mode_badges(mode, api_connected, last_run_mode, qwen_calls)
    if health.get("storage", {}).get("mode") == "ephemeral":
        st.warning("当前为临时预览环境；重新部署、休眠或重启后，任务历史与上传资料可能重置。")

    # ---- Sidebar：运行模式 → 系统状态 → 快速示例 → 高级能力设置 → 安全说明 ----
    with st.sidebar:
        mode = components.render_mode_control(mode)
        state.set_value(state.KEY_MODE, mode)
        from app.ui.workspace import persist_query_mode

        persist_query_mode(mode)
        mode = state.current_mode()

        components.render_system_status(health, llm_summary)

        preset_key = components.render_quick_presets(questions)
        if preset_key:
            if not questions:
                errors.questions_missing(
                    details=f"快速示例「{preset_label(preset_key)}」需要先加载问题清单。"
                )
            else:
                preset_qid = _find_qid_for_preset(questions, preset_key)
                if preset_qid:
                    state.queue_question_selection(preset_qid)
                else:
                    errors.question_not_selected(
                        details=(
                            f"快速示例「{preset_label(preset_key)}」未命中任何问题"
                            f"（关键词：{', '.join(PRESET_KEYWORDS.get(preset_key, [preset_key]))}）。"
                        )
                    )

        switches = components.render_pipeline_switches()
        components.render_security_note()

    # ---- 1) First Run Wizard ----
    components.section_title(ui_text("step_setup"), ui_text("first_run_wizard"), ui_text("first_run_wizard_subtitle"))
    wiz_action = components.render_first_run_wizard(_wizard_checks(diag, api_connected))

    # ---- 2) Select Scientific Question ----
    components.section_title(ui_text("step_01"), ui_text("select_a_scientific_question"), ui_text("select_a_scientific_question_subtitle"))
    # Preset/history selections are consumed before any selector widget exists.
    # Reset conflicting filters and synchronize the widget's stable QID value.
    pending_qid = state.consume_question_selection()
    if pending_qid and any(str(q.get("id")) == pending_qid for q in questions):
        st.session_state[components.QUESTION_KEYWORD_WIDGET_KEY] = ""
        st.session_state[components.QUESTION_DOMAIN_WIDGET_KEY] = "全部"
        st.session_state[components.QUESTION_CHOICE_WIDGET_KEY] = pending_qid
        pending_item = next(q for q in questions if str(q.get("id")) == pending_qid)
        state.select_question(pending_qid, pending_item.get("question", ""))
    if questions:
        charts.render_plotly_chart(
            charts.make_domain_coverage_chart(questions),
            key=components.make_widget_key("chart", "domain_cov"),
        )
    qid = components.render_question_selector(
        questions, selected_qid=state.get(state.KEY_SELECTED_QID)
    )
    selected_q = next((q for q in questions if q.get("id") == qid), None)
    # 写入唯一选题状态（切题会自动清空旧 run）。
    if qid:
        state.select_question(qid, (selected_q or {}).get("question", ""))

    # ---- 3) Data & RAG Workspace ----
    ephemeral_storage = health.get("storage", {}).get("mode") == "ephemeral"
    workspace_subtitle = (
        "当前预览使用临时存储；原文与索引在 API 实例存续期间可跨问题复用。"
        if ephemeral_storage
        else "原文与向量索引保存在项目数据目录；真实嵌入按当前配置调用百炼。"
    )
    components.section_title(
        ui_text("step_02"),
        ui_text("data_rag_workspace"),
        workspace_subtitle,
    )
    library_status = api_client.get_library_status()
    components.render_upload_panel(
        api_client.ingest_files,
        library_status=library_status,
        delete_fn=api_client.delete_library_document,
        validate_fn=api_client.validate_upload_batch,
        ephemeral_storage=ephemeral_storage,
    )

    # ---- 4) AI Scientist Run Console ----
    components.section_title(ui_text("step_03"), ui_text("ai_scientist_run_console"), "一键运行多智能体流水线生成《科学假设与研究计划》。")
    if mode == "real":
        pf_banner = api_client.run_preflight(switches.get("use_local_rag", True), switches.get("use_deep_research", True))
        if pf_banner.get("ok") and pf_banner.get("warnings"):
            st.caption("preflight 提示：" + "；".join(pf_banner.get("warnings", [])))
        elif not pf_banner.get("ok"):
            st.caption("preflight 未通过，真实模式运行将被阻止。请查看下方修复建议。")
    action = components.render_run_console(selected_q, switches, mode=mode)
    bc1, bc2 = st.columns(2)
    load_latest = bc1.button("加载历史运行", width="stretch", key="btn_load_latest")
    if bc2.button("清空当前结果", width="stretch", key="btn_clear_run"):
        state.clear_run()

    # ---- 处理动作 ----
    trigger_mock = (wiz_action == "mock") or (action == "mock")
    trigger_generate = action == "generate"
    trigger_latest = load_latest or (wiz_action == "latest")

    if trigger_generate or trigger_mock:
        if not questions:
            errors.questions_missing(
                details="触发了生成/Mock，但 questions_125.json 不可用。"
            )
        elif not qid:
            errors.question_not_selected(
                details="触发了生成/Mock，但 STEP 01 尚未选中 question_id。"
            )
        else:
            run_mode = "mock" if trigger_mock else mode
            # 真实模式：preflight 不通过则禁止启动（不 silent fallback mock）。
            if run_mode == "real":
                pf = api_client.run_preflight(
                    switches.get("use_local_rag", True),
                    switches.get("use_deep_research", True),
                    allow_wake=True,
                )
                if not pf.get("ok"):
                    err_text = "\n".join(pf.get("errors", []))
                    if any("DASHSCOPE" in e or "WORKSPACE" in e for e in pf.get("errors", [])):
                        errors.qwen_not_configured(details=err_text)
                    elif any("RAG" in e or "chunks" in e for e in pf.get("errors", [])):
                        errors.rag_missing(details=err_text)
                    else:
                        errors.render_user_error(
                            "无法启动真实模式",
                            "preflight 未通过：\n- " + "\n- ".join(pf.get("errors", [])),
                            fix_commands=pf.get("fix_commands"),
                        )
                else:
                    state.begin_run()
                    run_result = _execute_run(qid, run_mode, switches)
                    _handle_run_result(qid, run_mode, run_result)
            else:
                state.begin_run()
                run_result = _execute_run(qid, run_mode, switches)
                _handle_run_result(qid, run_mode, run_result)

    if trigger_latest:
        latest = (diag.get("latest_run") or {}).get("run_id")
        if not latest:
            errors.render_user_error(
                title="暂无历史运行",
                message="当前环境还没有可加载的 latest run。请先成功跑一次 Mock 演示。",
                fix_commands=[
                    "py -3 scripts/bootstrap_preview_data.py --allow-seed",
                    '$env:MOCK_LLM="true"; py -3 scripts/run_demo.py; Remove-Item Env:\\MOCK_LLM',
                ],
                severity="warning",
                key_ns="latest_missing",
            )
        else:
            loaded = api_client.get_run(latest)
            if loaded.get("status") == "missing" or not (loaded.get("plan") or loaded.get("question_id")):
                errors.missing_artifact("report.json", run_id=latest)
            elif _activate_loaded_run(loaded, questions):
                st.rerun()
            else:
                errors.render_user_error(
                    title="无法加载历史运行",
                    message=(
                        f"运行 {latest} 已找到，但未能绑定到当前问题清单。"
                        "请确认 questions_125.json 含对应 QID。"
                    ),
                    fix_commands=["py -3 scripts/bootstrap_preview_data.py --allow-seed"],
                    details=str({k: loaded.get(k) for k in ("run_id", "question_id", "status")}),
                    key_ns="latest_bind_failed",
                )

    # 读取当前运行结果。
    result = state.get_run_result()
    plan = result.get("plan")
    evidence_cards = result.get("evidence_cards", []) or []
    agent_trace = result.get("agent_trace", []) or []
    run_id = state.active_run_id()
    is_mock_run = bool(result.get("mock"))
    llm_summary = result.get("llm_call_summary", {}) or {}
    offline = bool(state.get(state.KEY_OFFLINE))

    # ---- Artifact Browser ----
    with st.expander("Artifact Browser · 历史运行", expanded=False):
        runs = api_client.get_runs(limit=10)
        chosen = components.render_run_browser(runs)
        if chosen:
            loaded = api_client.get_run(chosen)
            if _activate_loaded_run(loaded, questions):
                st.rerun()

    # ---- 选题-报告一致性校验（P0-1 阻断串线）----
    consistent = state.is_run_consistent()

    # ---- 5) Agent Observatory ----
    components.section_title(ui_text("step_04"), ui_text("agent_observatory"), "多智能体执行时间线、关系网络与追踪。")
    exp_result_state = st.session_state.get(components.make_widget_key("exp_run_result", qid)) if qid else None
    components.render_agent_pipeline(
        agent_trace, evidence_cards, plan or {},
        question=selected_q, is_mock=is_mock_run, experiment_result=exp_result_state,
    )

    # ---- 6) Evidence Wall ----
    components.section_title(ui_text("step_05"), ui_text("evidence_wall"), "可追溯证据墙：来源、原文引用、相关性与可靠性。")
    referenced_ids = {
        str(ref.get("id"))
        for ref in ((plan or {}).get("references", []) or [])
        if isinstance(ref, dict) and ref.get("id")
    }
    components.render_evidence_wall(evidence_cards, referenced_ids=referenced_ids)

    # ---- 7) ResearchPlan Studio ----
    components.section_title(ui_text("step_06"), ui_text("researchplan_studio"), "结构化《科学假设与研究计划》，适合截图。")
    if plan:
        binding_label = "历史报告对应问题" if offline else "当前报告对应问题"
        st.markdown(
            f'<div class="report-question-binding"><span>{binding_label}</span>'
            f'<b>[{components.esc(plan.get("question_id"))}] '
            f'{components.esc(plan.get("input_question") or "")}</b>'
            f'<small>Run ID：{components.esc(run_id or "-")}</small></div>',
            unsafe_allow_html=True,
        )
    if plan and not consistent:
        errors.report_mismatch(
            selected_question=state.get(state.KEY_SELECTED_QTEXT) or "(未知)",
            report_question=plan.get("input_question") or "(未知)",
            run_id=run_id,
        )
        st.info("请点击「启动 AI Scientist」为当前问题重新运行，或在 Artifact Browser 选择对应的历史运行。")
    elif state.run_status() == "failed":
        st.markdown(
            '<div class="user-error-card"><div class="ue-title">运行失败</div>'
            '<div class="ue-message">上次运行未成功，未生成可展示的报告。请修复问题后重试，或加载历史运行。</div></div>',
            unsafe_allow_html=True,
        )
    elif not plan:
        st.info("当前尚未为该问题生成 ResearchPlan。请选择问题并点击「生成 ResearchPlan」或「启动 AI Scientist（真实）」。")
    else:
        components.render_research_plan_tabs(
            plan, evidence_cards, agent_trace, run_id=run_id,
            file_reader=api_client.read_local_file, quality_gates=result.get("quality_gates"),
            is_mock=is_mock_run, llm_summary=llm_summary,
        )

    # ---- 8) Human Feedback Bench ----
    components.section_title(ui_text("step_07"), ui_text("human_feedback_bench"), "输入反馈触发一轮修订（不覆盖原始 run）。")
    components.render_feedback_panel(run_id if consistent else None, api_client.revise_run)

    # ---- 9) ResearchPlan Export Center ----
    components.section_title(ui_text("step_08"), ui_text("researchplan_export_center"), "导出当前运行的研究计划及其证据链、追踪与质量门。")
    components.render_researchplan_export_center(run_id if consistent else None, api_client.read_local_file)

    # ---- 10) Developer Diagnostics（默认折叠，唯一展示模型代号处）----
    llm_calls = api_client.get_llm_calls(run_id) if run_id else {}
    components.render_developer_diagnostics(health, result, llm_calls)

    components.render_footer()


if __name__ == "__main__":
    main()
