"""Wave B4 API-only Streamlit delivery console.

Start with:
    SAGE_UI_API_KEY=... streamlit run frontend/streamlit_app.py --server.port 8501
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from frontend.api_client import APIClientError, B4APIClient
from frontend.view_models import ViewState, classify_job_view, confidence_state


st.set_page_config(
    page_title="SAGE125 Delivery Console",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_css() -> None:
    css = Path(__file__).with_name("style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _query_value(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value) if value else None


def _set_query(name: str, value: str | None) -> None:
    if value:
        st.query_params[name] = value
    elif name in st.query_params:
        del st.query_params[name]


def _error(error: APIClientError, *, label: str) -> None:
    text = f"{label}：{error.message}（{error.code}）"
    if error.status_code in {401, 403}:
        st.error(text, icon="🔒")
    elif error.status_code == 503:
        st.warning(text, icon="⚠️")
    elif error.status_code in {408, 504}:
        st.error(text, icon="⏱️")
    else:
        st.error(text)
    if error.correlation_id:
        st.caption(f"correlation_id: {error.correlation_id}")
    if error.retryable:
        st.caption("该错误可重试；刷新前不会展示旧缓存结果。")


def _fetch(label: str, operation: Callable[[], dict[str, Any]]) -> dict[str, Any] | None:
    try:
        with st.spinner(f"正在加载{label}…"):
            return operation()
    except APIClientError as exc:
        _error(exc, label=label)
        return None


@st.cache_resource(show_spinner=False)
def _cached_client(
    base_url: str,
    api_key: str,
    timeout_seconds: float,
) -> B4APIClient:
    """Reuse one bounded HTTP pool across Streamlit reruns."""

    return B4APIClient(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )


def _client() -> B4APIClient | None:
    api_key = os.getenv("SAGE_UI_API_KEY", "")
    if not api_key:
        st.error(
            "未配置 SAGE_UI_API_KEY。前端不会在页面或 session_state 中保存 API key。",
            icon="🔒",
        )
        return None
    timeout_value = os.getenv("SAGE_UI_TIMEOUT_SECONDS", "10")
    try:
        timeout_seconds = float(timeout_value)
    except ValueError:
        st.error("SAGE_UI_TIMEOUT_SECONDS 必须是数字。")
        return None
    if timeout_seconds <= 0:
        st.error("SAGE_UI_TIMEOUT_SECONDS 必须大于 0。")
        return None
    return _cached_client(
        os.getenv("SAGE_UI_API_BASE_URL", "http://localhost:8000"),
        api_key,
        timeout_seconds,
    )


def _status_banner(job: dict[str, Any] | None, error: APIClientError | None = None) -> None:
    view = classify_job_view(job, error=error)
    if view.state is ViewState.INITIAL:
        st.info(view.message)
    elif view.state is ViewState.STALE:
        st.warning(view.message, icon="🕰️")
    elif view.state is ViewState.TIMED_OUT:
        st.error(view.message, icon="⏱️")
    elif view.state is ViewState.FORBIDDEN:
        st.error(view.message, icon="🔒")
    elif view.state in {ViewState.FAILED, ViewState.UNAVAILABLE}:
        st.error(view.message)
    elif job:
        status = str(job.get("status") or "unavailable")
        if status in {"queued", "running", "retrying"}:
            st.info(f"任务正在进行：{status} / {job.get('stage', 'unavailable')}")
        elif status == "waiting_feedback":
            st.warning("任务正在等待人工反馈。")
        else:
            st.success(f"任务状态：{status}")


def _render_status(client: B4APIClient, job_id: str) -> dict[str, Any] | None:
    st.subheader("01 · 任务状态")
    try:
        with st.spinner("正在从 API 同步任务状态…"):
            job = client.job(job_id)
    except APIClientError as exc:
        _status_banner(None, exc)
        _error(exc, label="任务状态")
        return None
    _status_banner(job)
    columns = st.columns(4)
    columns[0].metric("Status", job.get("status", "N/A"))
    columns[1].metric("Stage", job.get("stage", "N/A"))
    columns[2].metric("Attempt", f"{job.get('attempt', 0)}/{job.get('max_attempts', 1)}")
    columns[3].metric("Question", job.get("question_id", "N/A"))
    retry = job.get("retry") or {}
    timeout = job.get("timeout") or {}
    st.caption(
        f"updated_at={job.get('updated_at', 'N/A')} · "
        f"retryable={retry.get('retryable', False)} · "
        f"deadline={timeout.get('deadline_at') or 'N/A'}"
    )
    if job.get("error"):
        st.error(f"{job['error'].get('code')}: {job['error'].get('message')}")
    return job


def _render_evidence(client: B4APIClient, job_id: str) -> None:
    payload = _fetch("证据", lambda: client.evidence(job_id))
    if payload is None:
        return
    items = payload.get("items") or []
    if not items:
        st.info("证据为空；不会用标题或占位文本冒充证据。")
        return
    if payload.get("truncated"):
        st.warning(f"证据已截断：{payload.get('truncation_reason') or '原因未提供'}")
    for item in items:
        relations = item.get("relations") or []
        confidence_values = [rel.get("confidence") for rel in relations if rel.get("confidence") is not None]
        confidence = min(confidence_values) if confidence_values else None
        low = confidence_state(confidence) is ViewState.LOW_CONFIDENCE
        with st.expander(f"{item.get('evidence_id')} · {item.get('title')}", expanded=low):
            if low:
                st.warning(f"低置信度证据：{confidence:.2f}，需要人工核验。")
            st.markdown(f"> {item.get('quoted_text') or 'N/A'}")
            st.write("Locator", item.get("locator") or "N/A")
            st.caption(
                f"authors={', '.join(item.get('authors') or []) or 'N/A'} · "
                f"year={item.get('year') or 'N/A'} · verification={item.get('verification_status') or 'N/A'}"
            )
            if item.get("url"):
                st.link_button("打开原始来源", item["url"])
            elif item.get("doi"):
                st.link_button("打开 DOI", f"https://doi.org/{item['doi']}")
            for relation in relations:
                st.markdown(
                    f"<span class='sage-chip'>{relation.get('relation')}</span>"
                    f"<span class='sage-chip'>{relation.get('confidence', 'N/A')}</span>",
                    unsafe_allow_html=True,
                )


def _render_versions(client: B4APIClient, job_id: str) -> list[dict[str, Any]]:
    payload = _fetch("版本与 Reviewer", lambda: client.versions(job_id))
    if payload is None:
        return []
    versions = payload.get("items") or []
    if not versions:
        st.info("暂无版本或 Reviewer issue。")
        return []
    for version in versions:
        st.markdown(f"#### V{version.get('ordinal')} · `{version.get('version_id')}`")
        st.caption(
            f"parent={version.get('parent_version_id') or 'N/A'} · "
            f"validation={version.get('validation_status') or 'N/A'} · "
            f"stop_reason={version.get('stop_reason') or 'N/A'}"
        )
        if version.get("scores"):
            st.write("Scores", version["scores"])
        issues = version.get("reviewer_issues") or []
        if not issues:
            st.info("该版本无结构化 Reviewer issue。")
        for issue in issues:
            severity = issue.get("severity") or "N/A"
            st.markdown(
                f"- **{severity} / {issue.get('closure_status', 'N/A')}** "
                f"`{issue.get('issue_id')}` — {issue.get('summary') or 'N/A'}"
            )

    if len(versions) >= 2:
        ids = [str(item.get("version_id")) for item in versions]
        left, right, action = st.columns([2, 2, 1])
        from_id = left.selectbox("From", ids[:-1], key=f"diff_from_{job_id}")
        to_id = right.selectbox("To", ids[1:], index=len(ids[1:]) - 1, key=f"diff_to_{job_id}")
        if action.button("查看 diff", key=f"load_diff_{job_id}", use_container_width=True):
            diff = _fetch(
                "结构化 diff",
                lambda: client.version_diff(
                    job_id,
                    from_version_id=from_id,
                    to_version_id=to_id,
                ),
            )
            if diff is not None:
                st.json(diff, expanded=True)
    return versions


def _render_feedback(client: B4APIClient, job_id: str, versions: list[dict[str, Any]]) -> None:
    version_ids = [str(item.get("version_id")) for item in versions if item.get("version_id")]
    if not version_ids:
        st.info("没有可反馈的目标版本。")
        return
    with st.form(f"feedback_form_{job_id}"):
        target = st.selectbox("目标版本", version_ids)
        text = st.text_area(
            "人工反馈",
            max_chars=10_000,
            placeholder="说明需要修订的内容；反馈不是事实来源。",
        )
        submitted = st.form_submit_button("提交反馈", use_container_width=True)
    if submitted:
        if not text.strip():
            st.warning("反馈不能为空。")
        else:
            try:
                receipt = client.submit_feedback(
                    job_id,
                    target_version_id=target,
                    feedback=text.strip(),
                    idempotency_key=f"ui-feedback-{uuid.uuid4()}",
                )
            except APIClientError as exc:
                _error(exc, label="反馈提交")
            else:
                feedback_id = str(receipt.get("feedback_id") or "")
                _set_query("feedback_id", feedback_id or None)
                st.success(f"反馈已提交：{feedback_id}")

    feedback_id = _query_value("feedback_id")
    if feedback_id:
        decision = _fetch("反馈决策", lambda: client.feedback(job_id, feedback_id))
        if decision is not None:
            st.write(decision)
            if decision.get("resulting_version_id"):
                st.success(f"新版本：{decision['resulting_version_id']}；刷新后从 API 读取版本。")


def _render_report(client: B4APIClient, job_id: str) -> None:
    report = _fetch("Gate / 执行 / 多模态", lambda: client.report(job_id))
    if report is None:
        return
    st.caption(
        f"truth_status={report.get('truth_status', 'unavailable')} · "
        f"content_sha256={report.get('content_sha256', 'N/A')}"
    )
    st.markdown("#### Validation Gates")
    gates = report.get("gates") or []
    if not gates:
        st.info("Gate 结果为空。")
    for gate in gates:
        if gate.get("passed") is True:
            st.success(f"{gate.get('gate_id')}: passed")
        else:
            st.error(f"{gate.get('gate_id')}: blocked")
        for finding in gate.get("findings") or []:
            st.write(finding)

    st.markdown("#### Execution")
    execution = report.get("execution") or {}
    actual = execution.get("actual_execution")
    if actual is True:
        st.markdown("<span class='sage-chip sage-actual'>ACTUAL EXECUTION</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='sage-chip sage-planned'>NOT ACTUAL</span>", unsafe_allow_html=True)
    st.write(
        {
            "availability": execution.get("availability", "unavailable"),
            "status": execution.get("status", "unavailable"),
            "execution_id": execution.get("execution_id"),
            "metrics": execution.get("metrics") or [],
            "warnings": execution.get("warnings") or [],
        }
    )

    st.markdown("#### Multimodal")
    multimodal = report.get("multimodal") or []
    if not multimodal:
        st.info("多模态结果为空。")
    for item in multimodal:
        confidence = item.get("confidence")
        if confidence_state(confidence, threshold=0.8) is ViewState.LOW_CONFIDENCE:
            st.warning(
                f"{item.get('artifact_id')}: 低置信度 {confidence}，需要人工核验。"
            )
        st.write(
            {
                "artifact_id": item.get("artifact_id"),
                "source": item.get("source"),
                "page": item.get("page"),
                "bbox": item.get("bbox"),
                "units": item.get("units") or [],
                "validation_status": item.get("validation_status"),
            }
        )


def _render_exports(client: B4APIClient, job_id: str) -> None:
    formats = st.multiselect(
        "导出格式",
        ["json", "markdown", "pdf"],
        default=["json", "markdown", "pdf"],
        key=f"export_formats_{job_id}",
    )
    if st.button("生成 canonical 导出", key=f"export_{job_id}", use_container_width=True):
        if not formats:
            st.warning("至少选择一种格式。")
        else:
            try:
                result = client.create_export(
                    job_id,
                    formats=formats,
                    idempotency_key=f"ui-export-{uuid.uuid4()}",
                )
            except APIClientError as exc:
                _error(exc, label="导出")
            else:
                st.success(f"导出已登记：{len(result.get('items') or [])} 个产物。")

    artifacts = _fetch("产物列表", lambda: client.artifacts(job_id))
    if artifacts is None:
        return
    items = artifacts.get("items") or []
    if not items:
        st.info("当前没有已登记产物。")
        return
    for item in items:
        columns = st.columns([3, 2, 2, 1])
        columns[0].write(item.get("name") or "N/A")
        columns[1].caption(f"{item.get('artifact_type')} · {item.get('truth_status')}")
        columns[2].caption(f"{item.get('size_bytes')} bytes · {str(item.get('sha256'))[:12]}…")
        if columns[3].button("准备", key=f"prepare_{item.get('artifact_id')}"):
            try:
                data = client.download(job_id, str(item.get("artifact_id")))
            except APIClientError as exc:
                _error(exc, label="产物下载")
            else:
                st.download_button(
                    "下载",
                    data=data,
                    file_name=str(item.get("name") or "artifact.bin"),
                    mime=str(item.get("media_type") or "application/octet-stream"),
                    key=f"download_{item.get('artifact_id')}",
                    on_click="ignore",
                )


def main() -> None:
    _load_css()
    st.markdown(
        """
        <div class="sage-hero">
          <div class="sage-eyebrow">T08 · Wave B4</div>
          <h1>SAGE125 Delivery Console</h1>
          <div class="sage-muted">API-only · 可恢复 · 不读取本地 exports · 不推断科研真值</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    client = _client()
    if client is None:
        st.stop()

    with st.sidebar:
        st.header("任务导航")
        st.caption(os.getenv("SAGE_UI_API_BASE_URL", "http://localhost:8000"))
        if st.button("从 API 刷新", use_container_width=True):
            st.rerun()
        recent = _fetch("最近任务", lambda: client.jobs(limit=20))
        recent_items = (recent or {}).get("items") or []
        if recent_items:
            choices = {f"{item.get('question_id')} · {item.get('status')} · {str(item.get('job_id'))[:8]}": item.get("job_id") for item in recent_items}
            selected = st.selectbox("恢复最近任务", ["请选择"] + list(choices))
            if selected != "请选择" and st.button("恢复", use_container_width=True):
                _set_query("job_id", str(choices[selected]))
                _set_query("feedback_id", None)
                st.rerun()
        st.caption("刷新或重连后根据 URL 中的 job_id 从服务端恢复。")

    questions = _fetch("问题列表", client.questions)
    items = (questions or {}).get("items") or []
    st.subheader("启动任务")
    if not items:
        st.info("问题列表为空或不可用，无法创建任务。")
    else:
        labels = {
            f"{item.get('question_id')} · {item.get('domain')} · {item.get('question')}": item
            for item in items
        }
        left, middle, right = st.columns([5, 1.4, 1.4])
        selected_label = left.selectbox("科学问题", list(labels), label_visibility="collapsed")
        mode = middle.selectbox("Mode", ["mock", "real"], label_visibility="collapsed")
        if right.button("运行", type="primary", use_container_width=True):
            selected = labels[selected_label]
            try:
                accepted = client.create_job(
                    question_id=str(selected.get("question_id")),
                    mode=mode,
                    options={
                        "use_deep_research": True,
                        "use_open_literature": True,
                        "use_local_rag": True,
                        "reviewer_auto_revision": True,
                    },
                    idempotency_key=f"ui-run-{uuid.uuid4()}",
                )
            except APIClientError as exc:
                _error(exc, label="运行任务")
            else:
                _set_query("job_id", str(accepted["job_id"]))
                _set_query("feedback_id", None)
                st.rerun()

    job_id = _query_value("job_id")
    if not job_id:
        _status_banner(None)
        return

    st.caption(f"Active job: `{job_id}`")
    job = _render_status(client, job_id)
    if job is None:
        return
    sections = [
        "证据",
        "Reviewer · 版本 · Diff",
        "反馈 · 决策 · 新版本",
        "Gate · 执行 · 多模态",
        "导出",
    ]
    section = st.radio(
        "闭环阶段",
        sections,
        horizontal=True,
        key=f"workspace_section_{job_id}",
    )
    if section == sections[0]:
        _render_evidence(client, job_id)
    elif section == sections[1]:
        _render_versions(client, job_id)
    elif section == sections[2]:
        versions = _render_versions(client, job_id)
        _render_feedback(client, job_id, versions)
    elif section == sections[3]:
        _render_report(client, job_id)
    else:
        _render_exports(client, job_id)


if __name__ == "__main__":
    main()
