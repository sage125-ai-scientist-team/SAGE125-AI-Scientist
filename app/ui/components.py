"""
app.ui.components —— 科研发现控制台的受控 UI 组件（专业 AI Scientist 工作台）。

设计原则：
    - 每个组件职责单一；组件内部不直接调用模型，只调用 api_client；
    - 所有进入 unsafe_allow_html 的动态文本先经 html.escape 转义，杜绝注入；
    - 普通用户主界面**不展示具体模型代号**（qwen3.x 等）；模型别名/内部模型名
      仅出现在默认折叠的 Developer Diagnostics 面板；
    - 所有交互 widget 的 key 统一经 key_factory.make_widget_key 生成，杜绝
      StreamlitDuplicateElementKey；
    - 全程深色科学主题，卡片深底亮字，高对比可读。
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Optional

import streamlit as st

from app.core.evidence_links import canonical_evidence_link, evidence_verification_note
from app.ui import charts, progress as progress_ui, theme
from app.ui.key_factory import make_widget_key

# style.css 路径。
_CSS_PATH = Path(__file__).parent / "style.css"

# Stable question widget keys are also used by streamlit_app to synchronize a
# preset/history selection *before* the widgets are instantiated.
QUESTION_KEYWORD_WIDGET_KEY = make_widget_key("qsel", "keyword")
QUESTION_DOMAIN_WIDGET_KEY = make_widget_key("qsel", "domain")
QUESTION_CHOICE_WIDGET_KEY = make_widget_key("qsel", "choice")

# 标准 pending 说明（与 mock_outputs.PENDING_RESULTS 一致，用于前端提示）。
PENDING_TEXT = "当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。"

# Agent 名称中英文映射（普通用户看到"系统完成了什么"，而非模型名）。
AGENT_DISPLAY: dict[str, tuple[str, str]] = {
    "supervisor": ("监督调度", "Supervisor"),
    "question_parser": ("问题解析", "Question Parser"),
    "query_planner": ("检索规划", "Query Planner"),
    "deep_research": ("深度调研", "Deep Research"),
    "evidence_extractor": ("证据抽取", "Evidence Extractor"),
    "hypothesis_generator": ("假设生成", "Hypothesis Generator"),
    "experiment_designer": ("实验设计", "Experiment Designer"),
    "scientific_reviewer": ("审稿校验", "Scientific Reviewer"),
    "report_writer": ("报告生成", "Report Writer"),
    "schema_validator": ("结构校验", "Schema Validator"),
}


def esc(value: Any) -> str:
    """
    将任意值转义为 HTML 安全字符串。

    参数：
        value: 任意值。

    返回：
        转义后的字符串（None 转为空串）。
    """
    return html.escape("" if value is None else str(value))


def load_css() -> None:
    """
    读取 style.css 并注入页面。

    重要：每次 rerun 都重新注入（不做幂等短路），否则交互后样式丢失导致主背景
    变白、文字不可读。同时重置 widget key 登记表。
    """
    if _CSS_PATH.exists():
        css = _CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    # 每次 rerun 重置 key 登记表，供重复检测使用。
    st.session_state["_used_widget_keys"] = set()


def section_title(overline: str, title: str, subtitle: str = "") -> None:
    """渲染分步标题（overline + 主标题 + 副说明）。"""
    st.markdown(
        f"""<div class="section-title">
            <div class="overline">{esc(overline)}</div>
            <div class="title">{esc(title)}</div>
            <div class="subtitle">{esc(subtitle)}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _status_chip(label: str, ok: bool, ok_text: str = "已配置", bad_text: str = "未配置") -> str:
    """构造一个系统状态 chip 的 HTML 片段。"""
    cls = "status-ok" if ok else "status-bad"
    val = ok_text if ok else bad_text
    return f'<div class="status-chip"><span>{esc(label)}</span><span class="{cls}">{esc(val)}</span></div>'


def render_hero(status: dict, metrics: dict) -> None:
    """
    渲染 Hero（科研发现控制台顶部）。

    只展示"系统完成了什么"与运行状态，**不展示任何具体模型代号**。

    参数：
        status:  {qwen, deep_research, rag_ready, questions_ok, mode, qwen_calls,
                  last_run_mode} 等状态。
        metrics: {questions, agents} KPI 值。
    """
    qwen_calls = status.get("qwen_calls")
    qwen_call_text = "未调用" if not qwen_calls else f"已调用 {qwen_calls} 次"
    chips = (
        _status_chip("Qwen / 百炼", status.get("qwen", False))
        + _status_chip("Qwen 调用", bool(qwen_calls), qwen_call_text, "未调用")
        + _status_chip("DeepResearch", status.get("deep_research", False), "已启用", "未启用")
        + _status_chip(
            "RAG Index",
            status.get("rag_ready", False),
            "Empty" if status.get("rag_status") == "empty" else "Ready",
            "Unavailable",
        )
        + _status_chip("Questions", status.get("questions_ok", False), f"{metrics.get('questions', 0)}", "Warning")
    )
    kpis = [
        (metrics.get("questions", 0), "Questions"),
        (metrics.get("agents", 10), "Agents"),
        ("RAG + DeepResearch", "Evidence Engine"),
        ("MD / JSON / HTML / PDF", "Export Formats"),
    ]
    kpi_html = "".join(
        f'<div class="kpi-card"><div class="kpi-value">{esc(v)}</div><div class="kpi-label">{esc(l)}</div></div>'
        for v, l in kpis
    )
    st.markdown(
        f"""<div class="science-hero">
            <div style="display:flex; justify-content:space-between; gap:24px; flex-wrap:wrap;">
              <div style="flex:1 1 520px; min-width:320px;">
                <h1>🔬 {esc(theme.APP_TITLE)}</h1>
                <div class="hero-sub">{esc(theme.APP_SUBTITLE)}</div>
                <div class="hero-zh">从 125 个前沿科学问题中选择一个，系统自动完成文献检索、证据抽取、假设生成、实验设计与审稿校验，输出可验证《科学假设与研究计划》。</div>
                <div class="hero-badges">
                  <span class="hero-badge">125 Questions</span>
                  <span class="hero-badge">Qwen / 阿里云百炼</span>
                  <span class="hero-badge">Multi-Agent Pipeline</span>
                  <span class="hero-badge">Evidence Cards</span>
                  <span class="hero-badge">Human-in-the-loop</span>
                </div>
              </div>
              <div style="flex:0 1 300px; min-width:260px;">{chips}</div>
            </div>
            <div class="kpi-row">{kpi_html}</div>
          </div>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="safe-warning">本系统不是百科问答工具，而是将科学问题转化为可验证科研假设和研究计划的 AI Scientist 原型。</div>',
        unsafe_allow_html=True,
    )


def render_mode_badges(mode: str, api_connected: bool, last_run_mode: Optional[str], qwen_calls: Optional[int]) -> None:
    """
    渲染运行模式 / API / 上次运行 / Qwen 调用徽标行（不含模型名）。

    参数：
        mode:          当前模式 "mock" | "real"。
        api_connected: API 是否连接。
        last_run_mode: 上次运行模式（mock/real/None）。
        qwen_calls:    上次运行的真实 Qwen 调用次数。
    """
    mode_cls = "mock" if mode == "mock" else "real"
    mode_txt = "运行模式：模拟 Mock" if mode == "mock" else "运行模式：真实 Real"
    api_cls = "info" if api_connected else "warn"
    api_txt = "API 状态：已连接" if api_connected else "API 状态：进程内回退（模拟模式不请求百炼）"
    last_txt = "上次运行：暂无" if not last_run_mode else f"上次运行：{'模拟' if last_run_mode == 'mock' else '真实'}"
    call_cls = "real" if qwen_calls else "info"
    call_txt = f"Qwen 调用：{'已调用 ' + str(qwen_calls) + ' 次' if qwen_calls else '未调用'}"
    st.markdown(
        f"""<div class="mode-badge-row">
            <span class="mode-badge {mode_cls}">{esc(mode_txt)}</span>
            <span class="mode-badge {api_cls}">{esc(api_txt)}</span>
            <span class="mode-badge info">{esc(last_txt)}</span>
            <span class="mode-badge {call_cls}">{esc(call_txt)}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def render_system_status(health: dict, llm_summary: dict | None = None) -> None:
    """
    渲染侧边栏系统状态（配置 vs 本次运行分离）。

    参数：
        health:      /health 返回的 dict。
        llm_summary: 当前运行的 llm_call_summary（可选）。
    """
    st.markdown("### 🧭 System Status")
    st.markdown(_status_chip("百炼 Qwen 配置", health.get("qwen_config_loaded", False)), unsafe_allow_html=True)
    dr_cfg = health.get("deep_research_config_loaded", False)
    st.markdown(_status_chip("DeepResearch 配置", dr_cfg, "已配置", "未配置"), unsafe_allow_html=True)
    if llm_summary:
        dr_run = "已调用" if llm_summary.get("deep_research_invoked") else "未调用"
        st.caption(f"DeepResearch 本次运行：{dr_run}")
    st.markdown(_status_chip("OpenAlex（可选）", health.get("openalex_config_loaded", False)), unsafe_allow_html=True)
    rag_status = str(health.get("rag_index_status") or "unavailable")
    st.markdown(
        _status_chip(
            "用户文献索引",
            rag_status in {"ready", "empty"},
            "Ready" if rag_status == "ready" else "Empty",
            "Unavailable",
        ),
        unsafe_allow_html=True,
    )
    st.caption("具体模型代号见页面底部 Developer Diagnostics（默认折叠）。")


def render_pipeline_switches() -> dict:
    """渲染侧边栏 Pipeline 能力开关（不含 mock 开关，模式由顶部 Mode Control 决定）。"""
    st.markdown("### ⚙️ Pipeline Switches")
    return {
        "use_local_rag": st.checkbox("启用 Local RAG", value=True, key=make_widget_key("sw", "local_rag")),
        "use_deep_research": st.checkbox(
            "启用 DeepResearch（较慢，可能耗时数分钟）",
            value=False,
            key=make_widget_key("sw", "deep_research"),
        ),
        "use_open_literature": st.checkbox("启用 Open Literature APIs", value=True, key=make_widget_key("sw", "open_lit")),
        "reviewer_auto_revision": st.checkbox("启用 Reviewer Auto-Revision", value=True, key=make_widget_key("sw", "auto_rev")),
    }


def render_security_note() -> None:
    """渲染侧边栏安全提示（不在前端输入/显示/上传 Key）。"""
    st.markdown(
        '<div class="safe-warning">API Key 只允许配置在本地 .env 文件中。前端不会读取、显示或上传你的 Key。</div>',
        unsafe_allow_html=True,
    )


def render_question_selector(
    questions: list[dict], selected_qid: Optional[str] = None
) -> Optional[str]:
    """
    渲染 Step 01：科学问题选择（搜索 + 领域过滤 + 大卡片）。

    不设 pandemic 默认；用户选择即为唯一选题来源。

    参数：
        questions: 问题 dict 列表。

    返回：
        选中的 question_id（无问题时返回 None）。
    """
    if not questions:
        st.warning("尚未加载到问题清单，请先运行 python scripts/extract_125_questions.py。")
        return None

    if len(questions) != 125:
        st.markdown(
            f'<div class="user-error-card"><div class="ue-title">⚠️ 问题数量异常</div>'
            f'<div class="ue-message">当前问题数量为 {len(questions)}（不是 125），请检查 extract_125_questions.py 输出。</div></div>',
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input("🔍 关键词搜索", value="", placeholder="如 prime / gravity / pandemic",
                                key=QUESTION_KEYWORD_WIDGET_KEY)
    with col2:
        domains = ["全部"] + sorted({q.get("domain", "Unknown") for q in questions})
        domain_sel = st.selectbox("领域过滤", domains, key=QUESTION_DOMAIN_WIDGET_KEY)

    filtered = questions
    if keyword.strip():
        kw = keyword.strip().lower()
        filtered = [q for q in filtered if kw in q.get("question", "").lower()]
    if domain_sel != "全部":
        filtered = [q for q in filtered if q.get("domain") == domain_sel]
    if not filtered:
        st.info("没有匹配的问题，请调整搜索或领域。")
        filtered = questions

    # Widget value is the stable QID itself—not an index into a filtered list.
    # This prevents Q024 from silently becoming Q001 after filters/presets/history
    # reorder the options.
    by_id = {str(q.get("id")): q for q in filtered if q.get("id")}
    option_ids = list(by_id)
    preferred = str(selected_qid) if selected_qid and str(selected_qid) in by_id else option_ids[0]
    existing = st.session_state.get(QUESTION_CHOICE_WIDGET_KEY)
    if existing is not None and str(existing) not in by_id:
        # The prior QID is outside the new filter. Removing it before widget
        # creation lets Streamlit safely use the preferred/default option.
        del st.session_state[QUESTION_CHOICE_WIDGET_KEY]
    qid = st.selectbox(
        "选择一个科学问题",
        option_ids,
        format_func=lambda item: f"{item} · {by_id[item].get('question', '')[:70]}",
        index=option_ids.index(preferred),
        key=QUESTION_CHOICE_WIDGET_KEY,
    )
    selected = by_id[str(qid)]

    dcolor = theme.domain_color(selected.get("domain", ""))
    excerpt = (selected.get("booklet_excerpt") or "")[:420]
    st.markdown(
        f"""<div class="glass-card">
            <span class="status-pill" style="background:{dcolor}">{esc(selected.get('domain'))}</span>
            <span style="color:#93A4BE;margin-left:8px">{esc(selected.get('id'))} · p{esc(selected.get('source_page'))}</span>
            <div class="question-card-title">{esc(selected.get('question'))}</div>
            <div style="color:#B6C4DA;font-size:0.86rem;line-height:1.6">{esc(excerpt)}</div>
            <div style="margin-top:10px;font-size:0.82rem;color:#67E8F9;font-weight:600">
              本系统将为该问题生成可验证研究计划，而不是直接回答问题。
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    return qid


def _format_bytes(value: Any) -> str:
    """将字节数格式化为紧凑的用量文案。"""
    try:
        size = max(int(value or 0), 0)
    except (TypeError, ValueError):
        size = 0
    units = ("B", "KB", "MB", "GB")
    amount = float(size)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{size} B"


def _library_error_messages(payload: Any) -> list[str]:
    """把索引错误交给统一分类器；分类器异常时也绝不回显原始错误。"""
    try:
        from app.ui.api_client import format_library_errors

        return format_library_errors(payload)
    except Exception:  # noqa: BLE001 - UI 降级必须保持脱敏
        return [
            "文献索引失败，原文件未丢失。请运行 "
            "`py -3 scripts/smoke_bailian.py --embedding` 后重试。"
        ]


def render_upload_panel(
    ingest_fn,
    *,
    library_status: Optional[dict] = None,
    delete_fn=None,
    validate_fn=None,
    ephemeral_storage: bool = False,
) -> None:
    """
    渲染 Step 02：上传、配额、持久化策略与可确认删除的本地文献库。

    参数均保留可选默认，使旧调用方与组件单测不需同步改造。
    """
    status = library_status or {}
    documents = status.get("documents") or []
    usage = status.get("usage") or {}
    quota = status.get("quota") or {}
    service_status = str(status.get("status") or "unknown").lower()

    notice = st.session_state.pop("_library_notice", None)
    if notice:
        if isinstance(notice, dict) and notice.get("level") == "warning":
            st.warning(str(notice.get("message") or "文献库操作部分完成。"))
        else:
            message = notice.get("message") if isinstance(notice, dict) else notice
            st.success(str(message))

    storage_copy = (
        "上传成功后的原文与索引<strong style=\"color:#F8FAFC\">仅保存在当前临时 API 实例</strong>，"
        "可在实例存续期间跨问题复用；重新部署、休眠或重启后可能重置。"
        if ephemeral_storage
        else "上传成功后的原文与索引<strong style=\"color:#F8FAFC\">保存在项目数据目录</strong>，会跨问题复用。"
    )

    # 将存储策略、跨问题复用、题源隔离和显式删除集中说明，
    # 不改变原有深色 glass-card 视觉语言。
    st.markdown(
        f"""<div class="glass-card">
            <div style="font-weight:700;color:#F8FAFC">🗂️ 本地文献库治理</div>
            <div style="color:#B6C4DA;font-size:0.84rem;line-height:1.75;margin-top:7px">
              {storage_copy}
              题源 <code>sjtu-booklet.pdf</code> <strong style="color:#A7F3D0">不参与用户文献检索</strong>。
              文献只会在下方<strong style="color:#FCA5A5">显式确认删除</strong>后移除。
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded = st.file_uploader("上传资料（PDF/TXT/MD/CSV）", type=["pdf", "txt", "md", "csv"],
                                    accept_multiple_files=True, key=make_widget_key("upload", "files"))
        if st.button("📥 加入本地 RAG 索引", width="stretch", key=make_widget_key("upload", "btn")):
            if not uploaded:
                st.info("请先选择文件。")
            else:
                # 先只看 UploadedFile.size，超限时不调用 getvalue() 复制整批内容。
                selected_sizes = [int(getattr(f, "size", 0) or 0) for f in uploaded]
                max_batch_files = int(quota.get("max_files_per_upload") or 10)
                max_batch_bytes = int(quota.get("max_batch_bytes") or 100 * 1024 * 1024)
                max_file_bytes = int(quota.get("max_file_bytes") or 25 * 1024 * 1024)
                selection_errors: list[str] = []
                if len(uploaded) > max_batch_files:
                    selection_errors.append(f"单次最多上传 {max_batch_files} 个文件。")
                if sum(selected_sizes) > max_batch_bytes:
                    selection_errors.append(
                        f"本批文件超过 {_format_bytes(max_batch_bytes)} 上限。"
                    )
                for uploaded_file, size in zip(uploaded, selected_sizes):
                    if size > max_file_bytes:
                        selection_errors.append(
                            f"{uploaded_file.name}: 超过 {_format_bytes(max_file_bytes)} 单文件上限。"
                        )
                files = [] if selection_errors else [(f.name, f.getvalue()) for f in uploaded]
                if selection_errors:
                    check = {"ok": False, "errors": selection_errors}
                elif validate_fn:
                    check = validate_fn(files, status)
                else:
                    # 旧调用方的最小保护；主应用会传入 api_client.validate_upload_batch。
                    check = {"ok": True, "errors": []}
                if not check.get("ok"):
                    for message in check.get("errors") or ["上传前检查未通过。"]:
                        st.error(str(message))
                else:
                    with st.spinner("正在连接 API、保存文件并构建索引（冷启动可能需要约一分钟）…"):
                        result = ingest_fn(files)
                    result_status = str(result.get("status", "")).lower()
                    if result_status in {"ok", "success", "completed"}:
                        duplicate_count = len(result.get("duplicates") or [])
                        message = (
                            f"已新增持久化 {len(result.get('files', []))} 个文件，"
                            f"内容重复复用 {duplicate_count} 个，"
                            f"新增 {result.get('chunks_added', 0)} chunks。"
                        )
                        st.session_state["_library_notice"] = message
                        st.rerun()
                    elif result_status == "partial":
                        mapped_messages = _library_error_messages(result)
                        st.session_state["_library_notice"] = {
                            "level": "warning",
                            "message": (
                                f"文献库部分更新：已保存 {len(result.get('files', []))} 个，"
                                f"新增 {result.get('chunks_added', 0)} chunks；"
                                f"需注意：{'；'.join(mapped_messages)}"
                            ),
                        }
                        st.rerun()
                    else:
                        mapped_messages = _library_error_messages(result)
                        st.warning("；".join(mapped_messages))
    with col2:
        st.markdown(
            """<div class="glass-card">
                <div style="font-weight:700;color:#F8FAFC">RAG 证据链流程</div>
                <div class="rag-flow">
                  <span class="node">Document</span><span class="arrow">→</span>
                  <span class="node">Chunk</span><span class="arrow">→</span>
                  <span class="node">Embedding</span><span class="arrow">→</span>
                  <span class="node">zvec</span><span class="arrow">→</span>
                  <span class="node">Rerank</span><span class="arrow">→</span>
                  <span class="node">EvidenceCard</span>
                </div>
                <div style="margin-top:8px;font-size:0.78rem;color:#93A4BE">
                  原文不会发送到 arXiv / OpenAlex / Crossref；嵌入会按当前的本地/百炼配置执行。
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("#### 📊 文献库配额与清单")
    used_documents = int(usage.get("document_count") or len(documents) or 0)
    used_bytes = int(usage.get("total_bytes") or 0)
    max_documents = quota.get("max_documents")
    max_total_bytes = quota.get("max_total_bytes")
    q1, q2, q3 = st.columns(3)
    q1.metric("已保存文献", used_documents, f"上限 {max_documents}" if max_documents is not None else "未设硬上限")
    q2.metric("已用容量", _format_bytes(used_bytes), f"上限 {_format_bytes(max_total_bytes)}" if max_total_bytes is not None else "未设硬上限")
    q3.metric("检索范围", "用户文献", "排除 sjtu-booklet")
    if max_total_bytes is not None and int(max_total_bytes) > 0:
        ratio = min(max(used_bytes / int(max_total_bytes), 0.0), 1.0)
        st.progress(ratio, text=f"存储用量 {_format_bytes(used_bytes)} / {_format_bytes(max_total_bytes)}")

    if service_status in {"unavailable", "error", "failed"}:
        if status.get("message"):
            st.warning("；".join(_library_error_messages({"message": status.get("message")})))
        else:
            st.warning("本地文献库状态暂不可用；请检查 LibraryManager 或本地 API。")

    if not documents:
        st.caption("暂无用户文献。上传后会在此显示，并在后续所有问题中复用。")
        return

    for document in documents:
        document_id = str(document.get("document_id") or document.get("id") or "")
        name = str(document.get("name") or document.get("filename") or "未命名文献")
        size_text = _format_bytes(document.get("size_bytes"))
        chunks = int(document.get("chunk_count") or document.get("chunks") or 0)
        document_status = str(document.get("status") or "unknown")
        with st.expander(
            f"📄 {name} · {size_text} · {chunks} chunks · {document_status}",
            expanded=False,
        ):
            created_at = document.get("created_at") or document.get("uploaded_at") or "未记录"
            st.caption(f"document_id: {document_id or '旧版记录未分配'} · 保存时间: {created_at}")
            if document.get("error"):
                mapped_messages = _library_error_messages({"errors": [document.get("error")]})
                st.warning(f"索引状态：{'；'.join(mapped_messages)}")
            if not document_id or delete_fn is None:
                st.info("该记录暂不支持前端删除，请升级本地文献库服务。")
                continue
            confirm_key = make_widget_key("library", "confirm_delete", document_id)
            delete_key = make_widget_key("library", "delete", document_id)
            confirmed = st.checkbox(
                f"我确认永久删除「{name}」的原文、chunks 和向量索引",
                value=False,
                key=confirm_key,
            )
            if st.button("🗑️ 显式确认删除", key=delete_key, disabled=not confirmed):
                with st.spinner(f"正在删除 {name}…"):
                    result = delete_fn(document_id)
                if str(result.get("status", "")).lower() in {"ok", "success", "deleted", "completed"}:
                    st.session_state["_library_notice"] = f"已删除「{name}」及其索引数据。"
                    st.rerun()
                else:
                    mapped_messages = _library_error_messages(result)
                    st.error(f"删除失败，文献仍保留。{'；'.join(mapped_messages)}")


def render_run_console(selected_question: Optional[dict], switches: dict, mode: str = "mock") -> Optional[str]:
    """
    渲染 Step 03：运行控制台。

    参数：
        selected_question: 选中问题 dict（可能为 None）。
        switches:          能力开关。
        mode:              当前模式 mock/real。

    返回：
        用户触发的动作："generate" / "mock" / None。
    """
    enabled = []
    if switches.get("use_local_rag"):
        enabled.append("Local RAG")
    if switches.get("use_deep_research"):
        enabled.append("DeepResearch")
    if switches.get("use_open_literature"):
        enabled.append("Open Literature")
    if switches.get("reviewer_auto_revision"):
        enabled.append("Reviewer Revision")
    qtext = selected_question.get("question") if selected_question else "（未选择）"
    mode_txt = "真实 Real（调用 Qwen/百炼）" if mode == "real" else "模拟 Mock（不调用真实模型）"
    st.markdown(
        f"""<div class="glass-card">
            <div style="font-weight:700;color:#F8FAFC">AI Scientist Run Console</div>
            <div style="color:#B6C4DA;margin:6px 0">当前问题：<b style="color:#F8FAFC">{esc(qtext)}</b></div>
            <div style="font-size:0.82rem;color:#67E8F9">运行模式：{esc(mode_txt)}</div>
            <div style="font-size:0.82rem;color:#93A4BE">已启用能力：{esc(' · '.join(enabled) or '无')}</div>
            <div style="font-size:0.8rem;color:#93A4BE;margin-top:6px">
              系统将自动完成问题解析、检索规划、证据抽取、假设生成、实验设计、审稿校验与报告生成。
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns([1, 1])
    action = None
    with col1:
        primary_label = "🚀 启动 AI Scientist（真实）" if mode == "real" else "🚀 生成 ResearchPlan"
        if st.button(primary_label, type="primary", width="stretch", key=make_widget_key("run", "generate")):
            action = "generate"
    with col2:
        if st.button("🧪 运行模拟演示", width="stretch", key=make_widget_key("run", "mock")):
            action = "mock"
    if mode == "real":
        st.caption("真实模式将调用 Qwen/百炼 API，不会静默降级为模拟。")
    return action


def render_run_progress(
    payload: dict[str, Any] | None,
    *,
    diagnostics: bool = False,
    title: str = "AI Scientist 正在运行",
) -> progress_ui.RunProgress:
    """渲染紧凑、可轮询刷新的 AI Scientist 运行进度卡。

    ``payload`` 支持 ``stage/status/percent/message/model_alias/model_display/``
    ``model_name_internal``。普通进度卡只使用经过脱敏的用户文案和友好模型
    显示名；只有调用方明确传入 ``diagnostics=True`` 时，内部模型名才会放在
    默认折叠的开发者诊断区。

    返回归一化后的 :class:`app.ui.progress.RunProgress`，便于调用方记录状态或
    测试，不会改变现有页面布局和 session state。
    """

    snapshot = progress_ui.normalize_progress(payload)
    state_icon = {
        "queued": "○",
        "connecting": "◌",
        "waiting": "◌",
        "running": "●",
        "completed": "✓",
        "failed": "!",
    }[snapshot.status]
    is_live = snapshot.status in {"queued", "connecting", "waiting", "running"}
    live_class = " is-live" if is_live else ""

    supplied = payload or {}
    has_model = bool(
        supplied.get("model_alias")
        or supplied.get("model_display")
        or supplied.get("model_name_internal")
    )
    model_chip = (
        f'<span class="run-progress-model">{esc(snapshot.model_display)}</span>'
        if has_model
        else ""
    )
    diagnostic_html = ""
    if diagnostics:
        internal_name = snapshot.model_name_internal or "-"
        diagnostic_html = (
            '<details class="run-progress-diagnostics">'
            '<summary>开发者诊断（默认折叠）</summary>'
            f'<div><span>stage</span><code>{esc(snapshot.stage)}</code></div>'
            f'<div><span>model_alias</span><code>{esc(snapshot.model_alias)}</code></div>'
            f'<div><span>model_name_internal</span><code>{esc(internal_name)}</code></div>'
            '</details>'
        )

    # Keep the HTML in one uninterrupted block. Indented multiline closing tags
    # can be interpreted as Markdown code by Streamlit during rapid placeholder
    # updates, which would expose a literal ``</div>`` below the progress card.
    progress_html = (
        f'<div class="run-progress-card state-{esc(snapshot.status)}{live_class}">'
        '<div class="run-progress-head">'
        '<div class="run-progress-heading">'
        f'<span class="run-progress-signal" aria-hidden="true">{state_icon}</span>'
        '<div>'
        f'<div class="run-progress-title">{esc(title)}</div>'
        f'<div class="run-progress-status">{esc(snapshot.status_label)}</div>'
        '</div></div>'
        f'<div class="run-progress-percent">{snapshot.percent}<span>%</span></div>'
        '</div>'
        f'<div class="run-progress-track" role="progressbar" aria-label="{esc(snapshot.stage_label)}" '
        f'aria-valuemin="0" aria-valuemax="100" aria-valuenow="{snapshot.percent}">'
        f'<div class="run-progress-fill" style="width:{snapshot.percent}%"></div>'
        '</div>'
        '<div class="run-progress-body">'
        f'<div class="run-progress-message">{esc(snapshot.message)}</div>'
        f'{model_chip}'
        '</div>'
        '<div class="run-progress-foot">'
        f'<span class="run-progress-stage">当前阶段 · {esc(snapshot.stage_label)}</span>'
        f'<span>第 {snapshot.step_index} / {snapshot.step_count} 阶段</span>'
        '</div>'
        f'{diagnostic_html}'
        '</div>'
    )
    st.markdown(progress_html, unsafe_allow_html=True)
    return snapshot


def _agent_chip(status: str) -> str:
    """构造 Agent 状态 chip HTML。"""
    color = theme.AGENT_STATUS_COLORS.get(status, "#94A3B8")
    label = {"completed": "已完成", "failed": "失败", "skipped": "跳过", "running": "运行中", "pending": "等待"}.get(status, status)
    return f'<span class="agent-chip" style="background:{color}">{esc(label)}</span>'


def render_agent_pipeline(agent_trace: list[dict], evidence_cards: list[dict], plan: dict) -> None:
    """
    渲染 Step 04：多智能体工作流可视化（不展示模型代号）。

    参数：
        agent_trace:    AgentTraceEvent dict 列表。
        evidence_cards: 证据 dict 列表。
        plan:           ResearchPlan dict。
    """
    if not agent_trace:
        st.info("运行后展示 Agent 工作流。")
        return
    st.plotly_chart(charts.make_agent_timeline(agent_trace), width="stretch",
                    key=make_widget_key("chart", "agent_timeline"))
    hyps = (plan or {}).get("generated_hypotheses", []) if plan else []
    st.plotly_chart(charts.make_knowledge_graph(evidence_cards, hyps, plan or {}), width="stretch",
                    key=make_widget_key("chart", "knowledge_graph"))

    for ev in agent_trace:
        name = ev.get("agent_name", "")
        cn, en = AGENT_DISPLAY.get(name, (name, ""))
        status_html = _agent_chip(ev.get("status", "pending"))
        dur = f'{ev.get("duration_ms")} ms' if ev.get("duration_ms") is not None else ""
        warn = ("⚠ " + esc(", ".join(ev["warnings"]))) if ev.get("warnings") else ""
        out_summary = esc((ev.get("output_summary") or "")[:120])
        st.markdown(
            f"""<div class="agent-row">
                <div style="flex:2">
                  <span class="a-name">{esc(cn)}</span> <span class="a-name-en">{esc(en)}</span>
                  <div class="a-summary">{out_summary}</div>
                </div>
                <div style="flex:1;text-align:center">{status_html}</div>
                <div style="flex:1;text-align:right;color:#93A4BE;font-size:0.76rem">{esc(dur)}<br>{warn}</div>
            </div>""",
            unsafe_allow_html=True,
        )


def render_qwen_invocation_summary(llm_summary: dict, is_mock: bool) -> None:
    """
    渲染 Qwen 真实调用摘要（证明是否真实调用，不泄露 Key/模型名）。

    参数:
        llm_summary: summarize_calls 的输出。
        is_mock:     当前运行是否 mock。
    """
    if not llm_summary:
        return
    qwen_n = llm_summary.get("qwen_call_count", 0)
    mock_n = llm_summary.get("mock_call_count", 0)
    failed_n = llm_summary.get("failed_call_count", 0)
    dr = llm_summary.get("deep_research_invoked")
    usage = llm_summary.get("usage_summary", {}) or {}
    dr_txt = "已调用" if dr else ("未调用" if not is_mock else "模拟跳过")
    if failed_n and not dr:
        dr_txt = "失败/跳过"
    call_label = "模拟演示，未请求百炼" if is_mock else (
        f"真实百炼已调用 {qwen_n} 次" if qwen_n else "失败或未调用"
    )
    badges = (
        f'<span class="mode-badge {"mock" if is_mock else "real"}">运行：{"模拟 Mock" if is_mock else "真实 Real"}</span>'
        f'<span class="mode-badge {"real" if qwen_n and not is_mock else "info"}">模型调用：{esc(call_label)}</span>'
        f'<span class="mode-badge info">Mock 调用：{mock_n} 次</span>'
        f'<span class="mode-badge {"warn" if failed_n else "info"}">失败：{failed_n} 次</span>'
        f'<span class="mode-badge info">DeepResearch 本次：{esc(dr_txt)}</span>'
    )
    if usage.get("total_tokens"):
        badges += f'<span class="mode-badge info">Tokens：{usage.get("total_tokens")}</span>'
    st.markdown(f'<div class="mode-badge-row">{badges}</div>', unsafe_allow_html=True)


def render_evidence_wall(
    evidence_cards: list[dict], referenced_ids: Optional[set[str]] = None
) -> None:
    """渲染 Step 05：Evidence Cards 证据墙（筛选 + 卡片 + 图表）。"""
    st.markdown(
        '<div class="safe-warning">Evidence Wall 包含全部检索候选，并不等于报告参考文献。'
        '带“报告引用”标记的条目才被当前报告选中；即使已引用，也应打开原文核验。</div>',
        unsafe_allow_html=True,
    )
    if not evidence_cards:
        st.info("运行后展示证据卡。")
        return

    referenced = {str(item) for item in (referenced_ids or set())}
    st.caption(f"当前报告引用 {len(referenced)} 条 · 检索候选共 {len(evidence_cards)} 条")

    c1, c2 = st.columns([1, 1])
    with c1:
        st.plotly_chart(charts.make_evidence_distribution(evidence_cards), width="stretch",
                        key=make_widget_key("chart", "ev_dist"))
    with c2:
        st.plotly_chart(charts.make_relevance_histogram(evidence_cards), width="stretch",
                        key=make_widget_key("chart", "ev_relhist"))

    left, right = st.columns([1, 3])
    with left:
        source_types = sorted({c.get("source_type", "unknown") for c in evidence_cards})
        sel_sources = st.multiselect("来源过滤", source_types, default=source_types, key=make_widget_key("ev", "sources"))
        min_rel = st.slider("最小相关性", 0.0, 1.0, 0.0, 0.05, key=make_widget_key("ev", "minrel"))
        kw = st.text_input("证据关键词", "", key=make_widget_key("ev", "kw"))
    filtered = [
        c for c in evidence_cards
        if c.get("source_type") in sel_sources
        and float(c.get("relevance_score", 0) or 0) >= min_rel
        and (not kw.strip() or kw.strip().lower() in json.dumps(c, ensure_ascii=False).lower())
    ]
    with right:
        cols = st.columns(2)
        for i, card in enumerate(filtered):
            with cols[i % 2]:
                _render_evidence_card(card, is_referenced=str(card.get("id")) in referenced)


def _evidence_reference_html(card: dict) -> str:
    """Render a link only after rebuilding it from a trusted literature ID."""

    link = canonical_evidence_link(card)
    if link is None:
        has_raw_reference = bool(card.get("doi") or card.get("url"))
        return "链接不可用（未通过安全校验）" if has_raw_reference else "Not available"
    return (
        f'<a class="evidence-link" href="{esc(link.url)}" target="_blank" '
        f'rel="noopener noreferrer nofollow">{esc(link.display)} · {esc(link.label)} ↗</a>'
    )


def _render_evidence_card(card: dict, *, is_referenced: bool = False) -> None:
    """渲染单张证据卡（quoted_text 引用块；无 DOI/URL 显示 Not available）。"""
    src = card.get("source_type", "unknown")
    color = theme.SOURCE_COLORS.get(src, "#64748B")
    rel = float(card.get("relevance_score", 0) or 0)
    ref_html = _evidence_reference_html(card)
    mock_tag = '<span class="mock-tag">mock_for_testing</span>' if "mock_for_testing" in (card.get("reliability_note") or "") else ""
    usage_tag = (
        '<span class="evidence-use-tag is-cited">报告引用</span>'
        if is_referenced
        else '<span class="evidence-use-tag">检索候选</span>'
    )
    st.markdown(
        f"""<div class="evidence-card">
            <span class="src-badge" style="background:{color}">{esc(src)}</span> {usage_tag} {mock_tag}
            <div class="ev-title">{esc(card.get('title'))}</div>
            <div class="ev-quote">{esc((card.get('quoted_text') or '')[:280])}</div>
            <div class="ev-meta">文献链接：{ref_html}</div>
            <div class="ev-meta ev-verification">{esc(evidence_verification_note(card))}</div>
            <div class="rel-bar-track"><div class="rel-bar-fill" style="width:{int(rel*100)}%"></div></div>
            <div class="ev-meta" style="text-align:right">relevance {rel:.2f}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def render_hypothesis_cards(plan: dict) -> None:
    """渲染假设卡片列表。"""
    hyps = (plan or {}).get("generated_hypotheses", [])
    if not hyps:
        st.info("暂无假设。")
        return
    for i, h in enumerate(hyps):
        obs = "；".join(h.get("required_observations", []) or [])
        st.markdown(
            f"""<div class="hypothesis-card">
                <div class="hy-label">Hypothesis {i+1}</div>
                <div class="hy-text">{esc(h.get('hypothesis'))}</div>
                <div class="hy-field"><b>机制 Mechanism：</b>{esc(h.get('mechanism'))}</div>
                <div class="hy-field"><b>可证伪预测 Falsifiable Prediction：</b>{esc(h.get('falsifiable_prediction'))}</div>
                <div class="hy-field"><b>所需观测 Required Observations：</b>{esc(obs)}</div>
                <div class="hy-field"><b>被证伪风险 Risk of Being Wrong：</b>{esc(h.get('risk_of_being_wrong'))}</div>
            </div>""",
            unsafe_allow_html=True,
        )


def render_research_plan_tabs(
    plan: dict,
    evidence_cards: list[dict],
    agent_trace: list[dict],
    run_id: Optional[str] = None,
    file_reader=None,
    quality_gates: Optional[dict] = None,
    is_mock: bool = False,
    llm_summary: Optional[dict] = None,
) -> None:
    """
    渲染 ResearchPlan Studio（多 Tab）。展示前假定已通过选题-报告一致性校验。

    参数：
        plan:           ResearchPlan dict。
        evidence_cards: 证据 dict 列表。
        agent_trace:    trace dict 列表。
        run_id:         运行 ID（用于 Artifacts 下载）。
        file_reader:    回调 file_reader(run_id, filename)->bytes|None。
        quality_gates:  质量门 dict。
        is_mock:        当前是否 mock 运行（用于徽标）。
        llm_summary:    LLM 调用摘要（证明真实调用）。
    """
    if not plan:
        render_empty_state("尚无研究计划", "在 Run Console 点击 生成 ResearchPlan / 运行 Mock 演示，或从 Artifact Browser 加载历史运行。")
        return
    tabs = st.tabs([
        "Summary", "Hypotheses", "Research Plan", "Technical Validation",
        "References", "Reviewer & Quality Gates", "JSON",
    ])

    with tabs[0]:
        status = plan.get("validation_status", "draft")
        scolor = theme.status_color(status)
        mock_badge = '<span class="mock-tag">mock_for_testing</span>' if is_mock else '<span class="mode-badge real">真实 Real</span>'
        results = plan.get("results", "") or ""
        pending_badge = '<span class="mock-tag" style="background:rgba(59,130,246,0.15);color:#93C5FD">results: pending</span>' if "待执行验证实验" in results else ""
        status_zh = {"needs_data": "需补充数据", "draft": "草稿", "ready_for_validation": "待验证", "validated": "已验证"}.get(status, status)
        st.markdown(
            f"""<div class="report-panel">
                <span class="status-pill" style="background:{scolor}">{esc(status_zh)}</span> {mock_badge} {pending_badge}
                <h2>{esc(plan.get('paper_title') or plan.get('input_question'))}</h2>
                <div class="field-block"><b>当前问题：</b>{esc(plan.get('input_question'))}</div>
                <div class="field-block"><b>问题 ID：</b>{esc(plan.get('question_id'))} · <b>Domain：</b>{esc(plan.get('domain'))}</div>
                <div class="field-block"><b>Evidence：</b>{len(evidence_cards)} · <b>References：</b>{len(plan.get('references', []) or [])}</div>
                <div class="field-block"><b>校验状态：</b>{esc(status_zh)}（{esc(status)}）</div>
                <div class="field-block">{esc(plan.get('paper_abstract'))}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if llm_summary is not None:
            render_qwen_invocation_summary(llm_summary, is_mock)
        st.plotly_chart(charts.make_readiness_radar(plan), width="stretch",
                        key=make_widget_key("chart", "readiness", run_id))

    with tabs[1]:
        render_hypothesis_cards(plan)

    with tabs[2]:
        _render_plan_body(plan)

    with tabs[3]:
        _render_technical_validation(plan)

    with tabs[4]:
        _render_references(plan)

    with tabs[5]:
        _render_reviewer(plan)
        if quality_gates:
            st.markdown("#### Quality Gates")
            st.json(quality_gates)

    with tabs[6]:
        st.caption("结构化 ResearchPlan（便于检查字段规范）。")
        with st.expander("展开 ResearchPlan JSON", expanded=False):
            st.json(plan)


def _render_technical_validation(plan: dict) -> None:
    """渲染技术验证 Tab（数据构造/基线/指标/可复现/执行状态）。"""
    experiments = plan.get("experiments", {}) or {}
    datasets = plan.get("datasets", {}) or {}
    exec_meta = plan.get("actual_execution")
    st.markdown(
        f"""<div class="report-panel">
            <h3>Data Construction</h3>
            <div><b>Source：</b>{esc(datasets.get('source'))}</div>
            <div><b>Target：</b>{esc(datasets.get('target'))}</div>
            <h3>Baselines</h3><div>{esc(experiments.get('baselines'))}</div>
            <h3>Metrics</h3><div>{esc(experiments.get('metrics'))}</div>
            <h3>Validation Protocol</h3><div>{esc(experiments.get('validation_protocol'))}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.markdown("#### Reproducibility Checklist")
    for c in plan.get("reproducibility_checklist", []) or []:
        st.markdown(f"- {esc(c)}")
    if not exec_meta:
        st.warning("actual_execution = False：未执行真实实验，Results 为待验证状态（pending）。")


def _render_references(plan: dict) -> None:
    """渲染 References Tab（来自 EvidenceCards，缺失显示 Not available）。"""
    refs = plan.get("references", []) or []
    if not refs:
        st.warning("references 为空：证据待检索/待验证。")
        return
    for r in refs:
        rd = r if isinstance(r, dict) else {}
        ref_html = _evidence_reference_html(rd)
        tags = ""
        note = rd.get("reliability_note") or ""
        if "mock_for_testing" in note:
            tags += ' <span class="mock-tag">mock_for_testing</span>'
        if rd.get("source_type") == "deep_research":
            tags += ' <span class="mock-tag" style="background:rgba(139,92,246,0.15);color:#C4B5FD">requires verification</span>'
        st.markdown(
            f'<div class="evidence-card"><b>[{esc(rd.get("id"))}]</b> {esc(rd.get("title"))}{tags}'
            f'<div class="ev-meta">文献链接：{ref_html}</div>'
            f'<div class="ev-meta ev-verification">{esc(evidence_verification_note(rd))}</div></div>',
            unsafe_allow_html=True,
        )


def render_empty_state(title: str, hint: str) -> None:
    """渲染统一的空状态卡片（深色）。"""
    st.markdown(
        f"""<div class="glass-card" style="text-align:center;padding:28px">
            <div style="font-size:2rem">🔬</div>
            <div style="font-weight:700;color:#F8FAFC;margin:6px 0">{esc(title)}</div>
            <div style="color:#93A4BE;font-size:0.86rem">{esc(hint)}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _render_plan_body(plan: dict) -> None:
    """渲染研究计划正文（含 pending 提示与字段说明）。"""
    datasets = plan.get("datasets", {}) or {}
    experiments = plan.get("experiments", {}) or {}
    refs = plan.get("references", []) or []
    results = plan.get("results", "") or ""

    def _fmt(v):
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False, indent=2)
        return str(v)

    st.markdown(
        f"""<div class="report-panel">
            <h3>Problem Statement</h3><div>{esc(plan.get('problem_statement'))}</div>
            <h3>Rationale</h3><div>{esc(plan.get('rationale'))}</div>
            <h3>Technical Details</h3><div>{esc(plan.get('technical_details'))}</div>
            <h3>Datasets</h3>
            <div><b>Source：</b>{esc(_fmt(datasets.get('source')))}</div>
            <div><b>Target：</b>{esc(_fmt(datasets.get('target')))}</div>
            <h3>Methods</h3><div>{esc(plan.get('methods'))}</div>
            <h3>Experiments</h3>
            <div><b>Baselines：</b>{esc(_fmt(experiments.get('baselines')))}</div>
            <div><b>Metrics：</b>{esc(_fmt(experiments.get('metrics')))}</div>
            <div><b>Ablation：</b>{esc(_fmt(experiments.get('ablation')))}</div>
            <div><b>Validation Protocol：</b>{esc(_fmt(experiments.get('validation_protocol')))}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption("Technical Details 表示系统建议如何验证科学假设的技术路线，不是要求普通用户手动执行。")
    if "待执行验证实验" in results:
        st.warning(results)
    else:
        st.markdown(f'<div class="report-panel"><h3>Results</h3><div>{esc(results)}</div></div>', unsafe_allow_html=True)
    st.caption("未执行真实实验时，Results 只能显示待验证状态，不能编造指标。")

    _render_experiment_run_control(plan)

    st.markdown("<div class='report-panel'><h3>References（来自 EvidenceCards）</h3>", unsafe_allow_html=True)
    if refs:
        for r in refs:
            ref_html = _evidence_reference_html(r)
            st.markdown(
                f'<div class="field-block">• [{esc(r.get("id"))}] {esc(r.get("title"))} — {ref_html}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div class="field-block">references 待检索/待验证。</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_experiment_run_control(plan: dict) -> None:
    """
    渲染"运行真实实验"入口。

    每个题目都展示同一个按钮；目前只有 Q028 注册了可执行的科学入口
    （WDBC 旗舰案例），其它题目点击后会诚实提示暂无可执行入口，绝不
    编造实验结果。
    """
    from app.ui import api_client

    qid = str(plan.get("question_id") or "")
    state_key = make_widget_key("exp_run_result", qid)
    button_key = make_widget_key("btn_run_experiment", qid)

    st.markdown("<div class='report-panel'><h3>运行真实实验</h3>", unsafe_allow_html=True)
    if qid == "Q028":
        st.caption(
            "此按钮执行的是团队预先注册、可独立复现的固定实验协议（UCI WDBC 数据集 → "
            "标准化逻辑回归 → balanced_accuracy / malignant_recall），与上方由生成式流水线"
            "写出的研究计划文字可能不完全逐句一致；本次运行不会读取、也不会执行上方文字本身。"
        )
    if st.button("▶ 运行真实实验", width="stretch", key=button_key):
        with st.spinner("正在尝试执行真实实验（若该题暂无可执行入口，会诚实提示，不编造结果）…"):
            st.session_state[state_key] = api_client.run_experiment(qid)

    result = st.session_state.get(state_key)
    if result is None:
        st.caption("点击上方按钮，尝试运行该题目对应的真实科学实验（目前仅 Q028 有可执行入口）。")
    elif not result.get("available"):
        st.warning(result.get("reason") or "该题目当前没有可执行的真实科学实验入口。")
    elif result.get("status") != "succeeded":
        reason = result.get("reason") or (result.get("error") or {}).get("message") or result.get("status")
        st.error(f"真实实验执行未成功：{esc(str(reason))}")
    else:
        _render_q028_result(result)
    st.markdown("</div>", unsafe_allow_html=True)

    if qid == "Q028":
        _render_flagship_canonical_status(qid)


_CANON_CATEGORY_LABELS = {
    "selection": "选择与科学边界",
    "dataset": "数据集",
    "round1": "Round 1",
    "reviewer": "Reviewer / RevisionContext",
    "round2": "Round 2",
    "closure": "structured diff / stop reason",
    "identity": "跨文件一致性",
}


def _render_flagship_provenance(prov: dict) -> None:
    """
    渲染 GAP-01..04 加固后的 provenance 细节：代码 Commit 绑定、真实 Reviewer
    调用审计、V1/V2 prompt hash 变化、issue closure、no-clobber 发布、以及
    被取代的旧 attempt。全部字段直接来自磁盘证据，找不到就诚实显示"未知"，
    绝不编造。不展示任何 API Key / Authorization / workspace ID / 原始 prompt 正文。
    """
    if not prov:
        return
    with st.expander("Provenance 详情（Git Commit / Reviewer 审计 / Hash 变化）", expanded=False):
        def _v(x: object) -> str:
            return "未知" if x is None or x == "" else str(x)

        st.markdown(
            f"""<div class="field-block">
                <div><b>Producer Git SHA（canonical source_git_sha）：</b><code>{esc(_v(prov.get('producer_git_sha')))}</code></div>
                <div><b>Artifact snapshot Commit SHA（当前 HEAD）：</b><code>{esc(_v(prov.get('artifact_snapshot_commit_sha')))}</code></div>
                <div><b>Round 1 git_sha / git_dirty：</b><code>{esc(_v(prov.get('round1_git_sha')))}</code> / {esc(_v(prov.get('round1_git_dirty')))}</div>
                <div><b>Round 2 git_sha / git_dirty：</b><code>{esc(_v(prov.get('round2_git_sha')))}</code> / {esc(_v(prov.get('round2_git_dirty')))}</div>
                <div><b>Round 1 execution_id：</b><code>{esc(_v(prov.get('round1_execution_id')))}</code></div>
                <div><b>Round 2 execution_id：</b><code>{esc(_v(prov.get('round2_execution_id')))}</code></div>
            </div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""<div class="field-block">
                <div><b>Reviewer（Scientific Review）：</b>{esc(_v(prov.get('reviewer_provider')))} / {esc(_v(prov.get('reviewer_model')))}，request_id=<code>{esc(_v(prov.get('reviewer_request_id')))}</code></div>
                <div><b>V2 revision-plan 调用：</b>{esc(_v(prov.get('v2_provider')))} / {esc(_v(prov.get('v2_model')))}，request_id=<code>{esc(_v(prov.get('v2_request_id')))}</code></div>
                <div><b>Reviewer 是否真实驱动（reviewer_driven）：</b>{esc(_v(prov.get('reviewer_driven')))}</div>
                <div><b>Round 1 是否通过 Reviewer（reviewer_passed）：</b>{esc(_v(prov.get('reviewer_passed')))}</div>
                <div><b>Reviewer issue 是否注入 RevisionContext：</b>{esc(_v(prov.get('reviewer_issues_injected')))}</div>
                <div><b>Round 1 ExecutionResult 是否注入 RevisionContext：</b>{esc(_v(prov.get('execution_result_injected')))}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        issues = prov.get("critical_issues") or []
        if issues:
            st.markdown("**Reviewer 提出的 critical issue：**")
            for issue in issues:
                st.markdown(f"<div class='field-block'>• {esc(issue)}</div>", unsafe_allow_html=True)
        st.markdown(
            f"""<div class="field-block">
                <div><b>V1 prompt hash：</b><code>{esc(_v(prov.get('v1_prompt_hash')))}</code></div>
                <div><b>V2 prompt hash：</b><code>{esc(_v(prov.get('v2_prompt_hash')))}</code></div>
                <div><b>prompt hash 是否真实变化：</b>{esc(_v(prov.get('prompt_hash_changed')))}</div>
                <div><b>V1 input hash：</b><code>{esc(_v(prov.get('v1_input_hash')))}</code></div>
                <div><b>V2 input hash：</b><code>{esc(_v(prov.get('v2_input_hash')))}</code></div>
                <div><b>input hash 是否真实变化：</b>{esc(_v(prov.get('input_hash_changed')))}</div>
                <div><b>Policy validation（唯一实验变化是否合规）：</b>{esc(_v(prov.get('policy_validation_ok')))}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""<div class="field-block">
                <div><b>unresolved P0 / P1：</b>{esc(_v(prov.get('unresolved_p0')))} / {esc(_v(prov.get('unresolved_p1')))}</div>
                <div><b>stop_reason：</b>{esc(_v(prov.get('stop_reason')))}</div>
                <div><b>目标指标：</b>{esc(_v(prov.get('target_metric')))} ≥ {esc(_v(prov.get('target_value')))}，实测 {esc(_v(prov.get('observed_value')))}</div>
                <div><b>no-clobber 原子发布：</b>{esc(_v(prov.get('no_clobber_publication')))}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        superseded = prov.get("superseded_attempts") or []
        if superseded:
            st.markdown("**已被取代的旧 canonical attempt（PROVENANCE_SUPERSEDED，未删除未修改）：**")
            for event in superseded:
                st.markdown(
                    f"<div class='field-block'>• {esc(event.get('old_attempt_id'))} → {esc(event.get('new_attempt_id'))}"
                    f"（{esc(event.get('reason'))}，{esc(event.get('timestamp'))}）</div>",
                    unsafe_allow_html=True,
                )
        limitation = prov.get("scientific_limitation")
        if limitation:
            st.caption(f"科学边界：{limitation}")


def _render_flagship_canonical_status(qid: str) -> None:
    """
    只读展示旗舰案例 canonical package / 原子发布状态。

    数据完全来自 GET /experiments/{qid}/canonical-status（真实磁盘证据 +
    真实 canonical pointer），本函数不编造、不猜测、不填充占位指标。
    """
    from app.ui import api_client

    status_key = make_widget_key("flagship_canonical_status", qid)
    if st.button("刷新旗舰案例 canonical / 发布状态", key=make_widget_key("btn_refresh_canonical", qid)):
        st.session_state[status_key] = api_client.get_experiment_canonical_status(qid)
    status = st.session_state.get(status_key)
    if status is None:
        status = api_client.get_experiment_canonical_status(qid)
        st.session_state[status_key] = status

    st.markdown("<div class='report-panel'><h3>旗舰案例 Canonical Package / 原子发布状态</h3>", unsafe_allow_html=True)

    if not status.get("available"):
        st.warning(status.get("reason") or "该题目未接入 canonical 发布流水线。")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    if status.get("status") == "error":
        st.error(status.get("reason") or "读取 canonical 状态失败。")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    semantic_status = status.get("semantic_validation_status")
    published = bool(status.get("canonical_published"))
    round2_blocked = bool(status.get("round2_blocked"))

    badge = "PASS" if semantic_status == "PASS" else "FAIL"
    badge_class = "real" if semantic_status == "PASS" else "warn"
    st.markdown(
        f"""<div class="field-block">
            <div><b>案例 ID：</b>{esc(status.get('case_id'))}</div>
            <div><b>语义校验状态：</b><span class="mode-badge {badge_class}">{esc(badge)}</span></div>
            <div><b>Round 2 阻断（ROUND2_BLOCKED）：</b>{esc('是' if round2_blocked else '否')}</div>
            <div><b>Canonical 已发布（PUBLISHED_VERIFIED）：</b>{esc('是' if published else '否')}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    pointer = status.get("canonical_pointer")
    if published and pointer:
        st.markdown(
            f"""<div class="field-block">
                <div><b>attempt_id：</b>{esc(pointer.get('attempt_id'))}</div>
                <div><b>manifest_hash：</b>{esc(pointer.get('manifest_hash'))}</div>
                <div><b>policy_version：</b>{esc(pointer.get('policy_version'))}</div>
                <div><b>updated_at：</b>{esc(pointer.get('updated_at'))}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        st.caption("尚未发布为 PUBLISHED_VERIFIED canonical package（或已发布但校验状态非 PASS，consumer 会拒绝读取）。")

    _render_flagship_provenance(status.get("provenance") or {})

    checks = status.get("checks") or []
    if checks:
        by_category: dict[str, list[dict]] = {}
        for item in checks:
            by_category.setdefault(item.get("category", "?"), []).append(item)
        with st.expander(f"逐项校验清单（{status.get('check_count', len(checks))} 项，失败 {status.get('failed_count', 0)} 项）", expanded=not published):
            for category, items in by_category.items():
                label = _CANON_CATEGORY_LABELS.get(category, category)
                all_pass = all(i.get("status") == "PASS" for i in items)
                st.markdown(f"**{esc(label)}** — {'✅ 全部通过' if all_pass else '❌ 存在未通过项'}")
                for item in items:
                    icon = "✅" if item.get("status") == "PASS" else "❌"
                    st.markdown(
                        f"<div class='field-block'>{icon} `{esc(item.get('requirement_id'))}` {esc(item.get('detail'))}</div>",
                        unsafe_allow_html=True,
                    )

    fail_closed_reasons = status.get("fail_closed_reasons") or []
    if fail_closed_reasons:
        st.error("Fail-closed 原因：\n" + "\n".join(f"- {reason}" for reason in fail_closed_reasons))

    st.caption(
        "科学边界：本案例为受控二分类实验，用于验证 AI Scientist 的计划—执行—反馈—修订工作流；"
        "不证明能够治愈癌症，不构成临床有效性验证或医疗建议，不能外推到所有癌症，"
        "不替代领域专家与真实临床研究。"
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_q028_result(result: dict) -> None:
    """渲染一次成功的 Q028 真实实验结果：人话结论 + 图表，技术细节折叠展示。"""
    metrics = result.get("metrics") or {}
    confusion = result.get("confusion") or {}
    split = result.get("split") or {}
    balanced = metrics.get("balanced_accuracy")
    recall = metrics.get("malignant_recall")

    plain_summary = "本次真实运行已完成，但未取得可解读指标。"
    if balanced is not None and recall is not None and confusion:
        test_count = split.get("test_count", sum(confusion.values()))
        malignant_total = confusion.get("true_positive", 0) + confusion.get("false_negative", 0)
        plain_summary = (
            f"模型在 {test_count} 例留出测试样本上：平衡准确率 {balanced:.1%}，"
            f"{malignant_total} 例真实恶性肿瘤样本中正确识别出 "
            f"{confusion.get('true_positive', 0)} 例（召回率 {recall:.1%}），"
            f"漏诊 {confusion.get('false_negative', 0)} 例、误报 {confusion.get('false_positive', 0)} 例。"
        )
    st.markdown(
        f"""<div class="field-block">
            <span class="mode-badge real">真实 Real</span>
            <div style="margin-top:6px">{esc(plain_summary)}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    if balanced is not None and recall is not None:
        charts.render_plotly_chart(
            charts.make_experiment_metrics_bar(metrics),
            key=make_widget_key("chart", "exp_metrics", result.get("execution_id", "")),
        )
    if confusion:
        charts.render_plotly_chart(
            charts.make_confusion_matrix_heatmap(confusion),
            key=make_widget_key("chart", "exp_confusion", result.get("execution_id", "")),
        )

    if result.get("git_dirty"):
        st.caption("⚠ 当前工作区存在未提交改动：本次为演示性真实执行，非正式 Gate/PR 证据。")

    with st.expander("技术细节 / 可复现信息", expanded=False):
        st.markdown(
            f"""<div class="field-block">
                <div><b>执行状态：</b>{esc(result.get('status'))}</div>
                <div><b>execution_id：</b>{esc(result.get('execution_id'))}</div>
                <div><b>训练/测试样本数：</b>{esc(split.get('train_count'))} / {esc(split.get('test_count'))}</div>
                <div><b>数据集 SHA-256：</b>{esc(result.get('dataset_sha256'))}</div>
                <div><b>Git SHA：</b>{esc(result.get('git_sha'))}</div>
                <div><b>耗时：</b>{esc(result.get('duration_seconds'))} 秒</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if result.get("note"):
            st.caption(result["note"])


def _render_reviewer(plan: dict) -> None:
    """渲染评审信息（从 reviewer_comments 展示；详细结果在 quality_gates）。"""
    comments = plan.get("reviewer_comments", []) or []
    st.markdown("<div class='report-panel'><h3>Reviewer Comments</h3>", unsafe_allow_html=True)
    if comments:
        for c in comments:
            st.markdown(f'<div class="field-block">• {esc(c)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="field-block">（无评审意见）</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_feedback_panel(run_id: Optional[str], revise_fn) -> None:
    """渲染 Step 07：人在回路反馈。"""
    if not run_id:
        st.info("先生成一次研究计划，再进行反馈迭代。")
        return
    presets = ["让假设更保守", "加强可验证性", "减少因果过度推断", "换成公开数据集", "增加基线模型", "强化 References"]
    cols = st.columns(3)
    for i, p in enumerate(presets):
        if cols[i % 3].button(p, key=make_widget_key("fb", run_id, i), width="stretch"):
            st.session_state["feedback_text"] = p
    feedback = st.text_area("你的反馈（仅作修订偏好，不作为事实来源）", value=st.session_state.get("feedback_text", ""),
                            key=make_widget_key("fb", run_id, "text"))
    st.caption("用户反馈不能成为事实来源；要求编造结果、去掉引用或强行标记 validated 会被系统拒绝。")
    if st.button("🔁 依据反馈修订", type="primary", key=make_widget_key("fb", run_id, "submit")):
        if not feedback.strip():
            st.info("请输入反馈内容。")
            return
        with st.spinner("正在依据反馈修订…"):
            result = revise_fn(run_id, feedback.strip())
        if result.get("status") == "revised":
            st.success("修订完成，已生成新版本（不覆盖原始 run）。")
            with st.expander("修订历史 revision_history"):
                st.json(result.get("revision_history", []))
        elif result.get("status") == "rejected":
            st.error(f"反馈被拒绝：{result.get('message')}")
        else:
            st.warning(result.get("message", "修订失败。"))


def render_researchplan_export_center(run_id: Optional[str], file_reader) -> None:
    """
    渲染 Step 08：ResearchPlan Export Center（仅导出当前运行结果 artifacts）。

    参数：
        run_id:      当前运行 ID。
        file_reader: 回调 file_reader(run_id, filename) -> bytes|None。
    """
    if not run_id:
        st.info("先生成一次研究计划，再导出运行结果。")
        return
    items = [
        ("report.md", "科学假设与研究计划（Markdown）", "text/markdown"),
        ("report.json", "结构化 ResearchPlan（JSON）", "application/json"),
        ("report.html", "研究计划（HTML）", "text/html"),
        ("report.pdf", "研究计划报告（PDF，若已生成）", "application/pdf"),
        ("evidence_cards.json", "证据链数据", "application/json"),
        ("agent_trace.json", "多智能体执行追踪", "application/json"),
        ("context_pack.json", "上下文工程包", "application/json"),
        ("quality_gates.json", "质量门结果", "application/json"),
        ("llm_call_audit.json", "Qwen 调用审计（脱敏）", "application/json"),
        ("run_summary.txt", "运行摘要", "text/plain"),
    ]
    cols = st.columns(3)
    for i, (fname, desc, mime) in enumerate(items):
        content = file_reader(run_id, fname)
        with cols[i % 3]:
            available = content is not None
            st.markdown(
                f"""<div class="download-card">
                    <div class="dl-name">{esc(fname)}</div>
                    <div class="dl-desc">{esc(desc)}</div>
                    <div class="{'dl-available' if available else 'dl-missing'}">{'可下载' if available else '暂不可用'}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            # 全局唯一 key：namespace + run_id + 文件名 + 序号。
            dl_key = make_widget_key("download", run_id, fname, i)
            if available:
                st.download_button("下载", data=content, file_name=f"{run_id}_{fname}", mime=mime,
                                   key=dl_key, width="stretch")
            else:
                st.button("暂不可用", key=dl_key, disabled=True, width="stretch")

    st.markdown(
        '<div class="safe-warning" style="margin-top:10px">'
        '本系统导出的是 AI Scientist 当前运行结果，供检查与二次分析使用。'
        "</div>",
        unsafe_allow_html=True,
    )


def _wizard_icon(status: str) -> str:
    """返回检查项状态图标。"""
    return {"ok": "✅", "warning": "⚠️", "missing": "❌"}.get(status, "•")


def render_first_run_wizard(checks: list[dict]) -> Optional[str]:
    """
    渲染 First Run Wizard（首次运行向导）。

    参数：
        checks: 检查项列表，每项含 {label, status, detail, fix}。

    返回：
        用户触发的动作："mock" / "refresh" / "latest" / None。
    """
    with st.expander("🧭 First Run Wizard · 首次运行向导", expanded=False):
        st.caption("确认系统是否就绪；所有修复命令均在本地终端运行，前端不读取/输入任何 API Key。")
        for c in checks:
            cols = st.columns([0.5, 3, 5])
            cols[0].markdown(_wizard_icon(c.get("status", "missing")))
            cols[1].markdown(f"**{esc(c.get('label'))}**")
            detail = esc(c.get("detail", ""))
            fix = c.get("fix")
            if fix and c.get("status") != "ok":
                cols[2].markdown(f"{detail}<br><code>{esc(fix)}</code>", unsafe_allow_html=True)
            else:
                cols[2].markdown(detail)
        b1, b2, b3 = st.columns(3)
        action = None
        if b1.button("🧪 运行 Mock 演示", width="stretch", key=make_widget_key("wiz", "mock")):
            action = "mock"
        if b2.button("🔄 刷新诊断", width="stretch", key=make_widget_key("wiz", "refresh")):
            action = "refresh"
        if b3.button("📂 打开最近运行", width="stretch", key=make_widget_key("wiz", "latest")):
            action = "latest"
        return action


def render_run_browser(runs: list[dict]) -> Optional[str]:
    """
    渲染 Artifact Browser（历史运行浏览）。

    参数:
        runs: 运行摘要 dict 列表。

    返回：
        用户选择加载的 run_id，或 None。
    """
    if not runs:
        render_empty_state("暂无历史运行", "运行一次 生成 ResearchPlan / 运行 Mock 演示 后，这里会列出可加载的历史运行。")
        return None
    st.table({
        "run_id": [r.get("run_id") for r in runs],
        "question_id": [r.get("question_id") for r in runs],
        "mode": [r.get("mode") for r in runs],
        "status": [r.get("validation_status") for r in runs],
        "evidence": [r.get("evidence_count") for r in runs],
        "qwen_calls": [r.get("qwen_call_count") for r in runs],
    })
    labels = [f"{r.get('run_id')} · [{r.get('question_id')}] {(r.get('question') or '')[:36]}" for r in runs]
    idx = st.selectbox("选择历史运行", range(len(runs)), format_func=lambda i: labels[i], key=make_widget_key("runbrowser", "sel"))
    if st.button("📥 加载所选运行（历史结果浏览）", key=make_widget_key("runbrowser", "load")):
        return runs[idx].get("run_id")
    return None


def render_developer_diagnostics(health: dict, run_result: dict, llm_calls: Optional[dict] = None) -> None:
    """
    渲染 Developer Diagnostics（开发者诊断，默认折叠）。

    这是唯一允许展示"具体模型代号 / 内部模型名 / request_id / token usage /
    raw agent_trace / raw context_pack"的位置。不显示任何 API Key。

    参数：
        health:     /health 返回 dict（含 models）。
        run_result: 当前运行结果 dict。
        llm_calls:  llm 调用审计（含 records）。
    """
    with st.expander("🛠 Developer Diagnostics · 开发者诊断（默认折叠）", expanded=False):
        st.markdown('<div class="dev-note">以下为内部调试信息（模型代号、调用审计等），普通用户无需关心；不含任何 API Key。</div>',
                    unsafe_allow_html=True)
        # 模型档位 -> 内部模型名。
        models = (health or {}).get("models", {}) or {}
        st.markdown("**模型档位映射（Model Alias → 内部模型名）**")
        alias_rows = [
            ("fast", models.get("fast", "-")), ("balanced", models.get("balanced", "-")),
            ("strong", models.get("strong", "-")), ("deepresearch", models.get("deep_research", "-")),
            ("embedding", models.get("embedding", "-")), ("rerank", models.get("rerank", "-")),
        ]
        for alias, name in alias_rows:
            st.markdown(f'<div class="dev-kv"><span class="k">{esc(alias)}</span><span class="v">{esc(name)}</span></div>',
                        unsafe_allow_html=True)

        # LLM 调用审计摘要与明细。
        summary = (llm_calls or {}).get("summary") or run_result.get("llm_call_summary") or {}
        if summary:
            st.markdown("**LLM 调用审计摘要**")
            st.json(summary)
        records = (llm_calls or {}).get("records") or []
        if records:
            st.markdown("**LLM 调用明细（脱敏：含 model_alias / request_id / usage / status）**")
            st.json(records)

        # 原始 agent_trace 与 context_pack。
        if run_result.get("agent_trace"):
            st.markdown("**raw agent_trace.json**")
            st.json(run_result.get("agent_trace"))
        if run_result.get("context_pack"):
            st.markdown("**raw context_pack.json**")
            st.json(run_result.get("context_pack"))


def render_footer() -> None:
    """渲染页脚。"""
    st.markdown(
        '<div class="footer">Built with Qwen + Bailian + RAG + Multi-Agent Workflow · AI Scientist Track A.</div>',
        unsafe_allow_html=True,
    )
