"""工作区 Job 指针与进度恢复。Session 只保存指针，状态以 Job Store 为准。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from app.api.contracts import (
    JOB_TYPE_CONTROLLED_DEMO,
    JOB_TYPE_FULL_RESEARCH_PIPELINE,
)
from app.api.job_commands import compute_idempotency_key, compute_input_digest
from app.core.run_progress import STAGE_PERCENT, friendly_stage_name
from app.ui import api_client, state


def esc(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

CLIENT_ID_KEY = "sage125_client_id"
ACTIVE_JOB_IDS_KEY = "active_job_ids"
LAST_EVENT_SEQ_KEY = "sage125_last_event_sequence"
FOCUS_JOB_KEY = "_sage_focus_job_id"
RESULT_APPLIED_KEY = "_sage_job_result_applied"

JOB_TYPE_FULL = JOB_TYPE_FULL_RESEARCH_PIPELINE
JOB_TYPE_DEMO = JOB_TYPE_CONTROLLED_DEMO

ACTIVE_BACKEND = frozenset({"queued", "running", "retrying"})
TERMINAL_BACKEND = frozenset(
    {"completed", "waiting_feedback", "failed", "timed_out", "cancelled"}
)
PIPELINE_STAGES = [name for name in STAGE_PERCENT if name != "completed"]


def _query_value(name: str) -> str | None:
    try:
        raw = st.query_params.get(name)
    except Exception:
        return None
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    return str(raw) if raw else None


def ensure_client_id() -> str:
    from_query = _query_value("client_id")
    if from_query:
        st.session_state[CLIENT_ID_KEY] = from_query
    elif CLIENT_ID_KEY not in st.session_state:
        st.session_state[CLIENT_ID_KEY] = str(uuid.uuid4())
    client_id = str(st.session_state[CLIENT_ID_KEY])
    try:
        st.query_params["client_id"] = client_id
    except Exception:
        pass
    return client_id


def _pointers() -> dict[str, dict[str, str]]:
    raw = st.session_state.setdefault(ACTIVE_JOB_IDS_KEY, {})
    if not isinstance(raw, dict):
        st.session_state[ACTIVE_JOB_IDS_KEY] = {}
        return st.session_state[ACTIVE_JOB_IDS_KEY]
    return raw


def set_active_job_id(question_id: str, job_type: str, job_id: str) -> None:
    pointers = _pointers()
    bucket = pointers.setdefault(str(question_id), {})
    if isinstance(bucket, dict):
        bucket[job_type] = job_id
    persist_query_job(job_id)


def get_pointer_job_id(question_id: str | None, job_type: str) -> str | None:
    if not question_id:
        return None
    bucket = _pointers().get(str(question_id)) or {}
    if not isinstance(bucket, dict):
        return None
    return bucket.get(job_type)


def persist_query_job(job_id: str | None) -> None:
    try:
        if job_id:
            st.query_params["job_id"] = str(job_id)
        elif "job_id" in st.query_params:
            del st.query_params["job_id"]
    except Exception:
        pass


def query_job_id() -> str | None:
    return _query_value("job_id")


def ui_status(job: dict[str, Any] | None) -> str:
    if not job:
        return "IDLE"
    status = str(job.get("status") or "")
    return {
        "queued": "QUEUED",
        "running": "RUNNING",
        "retrying": "RECOVERABLE",
        "waiting_feedback": "PARTIAL",
        "completed": "SUCCEEDED",
        "failed": "FAILED",
        "timed_out": "FAILED",
        "cancelled": "CANCELLED",
    }.get(status, status.upper() or "IDLE")


def is_active(job: dict[str, Any] | None) -> bool:
    return bool(job) and str(job.get("status") or "") in ACTIVE_BACKEND


def is_terminal(job: dict[str, Any] | None) -> bool:
    return bool(job) and str(job.get("status") or "") in TERMINAL_BACKEND


def stage_cursor(stage: str | None) -> tuple[int | None, int | None]:
    if not stage:
        return None, None
    if stage in PIPELINE_STAGES:
        return PIPELINE_STAGES.index(stage) + 1, len(PIPELINE_STAGES)
    return None, None


def _owns_job(job: dict[str, Any], *, client_id: str, question_id: str | None) -> bool:
    if question_id and str(job.get("question_id") or "") != str(question_id):
        return False
    job_client = job.get("client_id")
    if job_client and str(job_client) != str(client_id):
        return False
    return True


def rehydrate_job_state(
    client_id: str,
    question_id: str | None,
    job_type: str,
) -> dict[str, Any] | None:
    """按指针 / active / latest / URL 恢复同一 Job，不创建新任务。"""
    if not question_id:
        return None
    job = None
    pointer = get_pointer_job_id(question_id, job_type)
    if pointer:
        job = api_client.get_job(pointer)
    if job is None:
        url_id = query_job_id()
        if url_id and url_id != pointer:
            fetched = api_client.get_job(url_id)
            if fetched and _owns_job(
                fetched, client_id=client_id, question_id=question_id
            ) and str(fetched.get("job_type") or JOB_TYPE_FULL) == job_type:
                job = fetched
    if job is None:
        job = api_client.get_active_job(
            client_id=client_id, question_id=question_id, job_type=job_type
        )
    if job is None:
        job = api_client.get_latest_job(
            client_id=client_id, question_id=question_id, job_type=job_type
        )
    if job is None:
        for item in api_client.list_jobs(question_id=question_id, limit=20):
            if str(item.get("job_type") or JOB_TYPE_FULL) == job_type:
                job = item
                break
    if not job:
        return None
    set_active_job_id(question_id, job_type, str(job["job_id"]))
    if is_active(job):
        state.set_value(state.KEY_RUN_STATUS, "running")
    elif ui_status(job) == "FAILED":
        state.set_value(state.KEY_RUN_STATUS, "failed")
    apply_job_result_if_ready(job)
    return job


def apply_job_result_if_ready(job: dict[str, Any]) -> None:
    if not is_terminal(job):
        return
    run_id = job.get("upstream_run_id")
    if not run_id:
        return
    applied = st.session_state.setdefault(RESULT_APPLIED_KEY, set())
    if not isinstance(applied, set):
        applied = set()
        st.session_state[RESULT_APPLIED_KEY] = applied
    marker = f"{job.get('job_id')}:{run_id}"
    if marker in applied:
        return
    loaded = api_client.get_run(str(run_id))
    if loaded.get("status") == "missing" or not loaded.get("plan"):
        return
    state.set_run_result(loaded, question_id=str(job.get("question_id") or ""))
    applied.add(marker)


def submit_or_reuse_job(
    *,
    question_id: str,
    job_type: str,
    mode: str,
    switches: dict[str, Any],
) -> dict[str, Any]:
    client_id = ensure_client_id()
    existing = rehydrate_job_state(client_id, question_id, job_type)
    if is_active(existing):
        return {**existing, "created": False, "reused": True}
    options = {
        "use_deep_research": bool(switches.get("use_deep_research", True)),
        "use_open_literature": bool(switches.get("use_open_literature", True)),
        "use_local_rag": bool(switches.get("use_local_rag", True)),
        "reviewer_auto_revision": bool(switches.get("reviewer_auto_revision", True)),
    }
    try:
        digest = compute_input_digest(mode=mode, options=options)
    except TypeError:
        import json
        import hashlib

        digest = hashlib.sha256(
            json.dumps(
                {"mode": str(mode or ""), "options": options},
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:32]
    key = compute_idempotency_key(
        client_id=client_id,
        question_id=question_id,
        job_type=job_type,
        input_digest=digest,
    )
    accepted = api_client.create_job(
        question_id=question_id,
        mode=mode,
        job_type=job_type,
        client_id=client_id,
        input_digest=digest,
        idempotency_key=key,
        options=options,
    )
    job_id = accepted.get("job_id")
    if job_id:
        set_active_job_id(question_id, job_type, str(job_id))
        if accepted.get("created"):
            state.begin_run()
        else:
            state.set_value(state.KEY_RUN_STATUS, "running")
    return accepted


def retry_from_checkpoint(job_id: str, *, question_id: str, job_type: str) -> dict[str, Any]:
    accepted = api_client.retry_job(job_id, client_id=ensure_client_id())
    new_id = accepted.get("job_id")
    if new_id:
        set_active_job_id(question_id, job_type, str(new_id))
        state.begin_run()
    return accepted


def job_action_spec(job: dict[str, Any] | None, *, idle_label: str) -> dict[str, str]:
    kind = ui_status(job)
    if kind in {"QUEUED", "RUNNING", "RECOVERABLE"}:
        return {"label": "运行中，查看进度", "action": "view", "kind": kind}
    if kind == "SUCCEEDED":
        return {"label": "查看结果", "action": "view_result", "kind": kind}
    if kind == "PARTIAL":
        return {"label": "查看部分结果", "action": "view_result", "kind": kind}
    if kind == "FAILED":
        return {"label": "重新运行", "action": "rerun", "kind": kind}
    if kind == "CANCELLED":
        return {"label": idle_label, "action": "submit", "kind": kind}
    return {"label": idle_label, "action": "submit", "kind": "IDLE"}


def render_job_action_button(
    idle_label: str,
    *,
    job_type: str,
    question_id: str | None,
    key: str,
    primary: bool = True,
) -> str:
    """返回 submit / view / view_result / rerun / retry / none。不把按钮当任务状态。"""
    if not question_id:
        st.button(idle_label, type="secondary", width="stretch", key=key, disabled=True)
        st.caption("请先选择一个科学问题。")
        return "none"
    client_id = ensure_client_id()
    job = rehydrate_job_state(client_id, question_id, job_type)
    spec = job_action_spec(job, idle_label=idle_label)
    clicked = st.button(
        spec["label"],
        type="primary" if primary and spec["action"] in {"submit", "rerun"} else "secondary",
        width="stretch",
        key=key,
    )
    if spec["kind"] == "FAILED" and job:
        message = str(
            (job.get("error") or {}).get("message")
            or job.get("error_message")
            or job.get("message")
            or ""
        ).strip()
        if message:
            st.caption(f"上次失败：{message}")
    if spec["kind"] in {"SUCCEEDED", "PARTIAL"} and question_id:
        rerun_key = f"{key}_rerun_ack"
        if st.checkbox("确认重新运行（将创建新 attempt，保留旧 Job）", key=rerun_key):
            if st.button("重新运行", key=f"{key}_rerun"):
                return "submit"
    if not clicked:
        return "none"
    if spec["action"] == "submit":
        return "submit"
    if spec["action"] == "rerun" and job:
        retry_from_checkpoint(str(job["job_id"]), question_id=question_id, job_type=job_type)
        return "retry"
    if job:
        st.session_state[FOCUS_JOB_KEY] = job.get("job_id")
    return spec["action"]


def collect_visible_jobs(question_id: str | None) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    pointers = _pointers()
    for qid, bucket in pointers.items():
        if question_id and str(qid) != str(question_id):
            continue
        if not isinstance(bucket, dict):
            continue
        for job_type, job_id in bucket.items():
            fetched = api_client.get_job(str(job_id))
            job = fetched or {
                "job_id": str(job_id),
                "question_id": str(qid),
                "job_type": str(job_type),
                "status": "queued",
                "stage": "queued",
                "message": "正在从后台恢复任务状态",
            }
            if job["job_id"] not in seen:
                jobs.append(job)
                seen.add(str(job["job_id"]))
    return jobs


def _elapsed_text(job: dict[str, Any]) -> str:
    started = job.get("started_at") or job.get("created_at")
    if not started:
        return "—"
    try:
        started_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        if started_dt.tzinfo is None:
            started_dt = started_dt.replace(tzinfo=timezone.utc)
        seconds = max(0, int((datetime.now(timezone.utc) - started_dt).total_seconds()))
    except ValueError:
        return "—"
    minutes, rem = divmod(seconds, 60)
    return f"{minutes}分{rem}秒" if minutes else f"{rem}秒"


def run_progress_payload(job: dict[str, Any]) -> dict[str, Any]:
    """把 Job Store 快照转成旧版 ``render_run_progress`` 所需字段。"""
    current = job.get("progress_current")
    total = job.get("progress_total")
    if current is None or total is None:
        current, total = stage_cursor(job.get("stage"))
    mode = "determinate" if current and total else "indeterminate"
    mapped = {
        "queued": "queued",
        "running": "running",
        "retrying": "waiting",
        "completed": "completed",
        "waiting_feedback": "completed",
        "failed": "failed",
        "timed_out": "failed",
        "cancelled": "failed",
    }.get(str(job.get("status") or ""), "running")
    stage = str(job.get("stage") or "queued")
    percent = job.get("progress_percent")
    if percent is None:
        percent = STAGE_PERCENT.get(stage, STAGE_PERCENT.get("initializing", 2))
    return {
        "stage": stage,
        "status": mapped,
        "percent": int(percent or 0),
        "message": job.get("message") or friendly_stage_name(stage),
        "model_alias": job.get("model_alias") or "",
        "progress_mode": mode,
        "progress_current": current,
        "progress_total": total,
        "job_id": job.get("job_id"),
        "correlation_id": job.get("correlation_id"),
        "job_type": job.get("job_type"),
        "question_id": job.get("question_id"),
    }


def _progress_payload(job: dict[str, Any]) -> dict[str, Any]:
    return run_progress_payload(job)


def render_progress_card(job: dict[str, Any]) -> None:
    from app.ui import components

    title = "AI Scientist 正在运行"
    status = str(job.get("status") or "")
    if status in {"completed", "waiting_feedback"}:
        title = "AI Scientist 运行完成"
    elif status in {"failed", "timed_out"}:
        title = "AI Scientist 运行失败"
    components.render_run_progress(run_progress_payload(job), title=title)


def render_global_job_status_bar(question_id: str | None = None) -> None:
    jobs = [job for job in collect_visible_jobs(None) if is_active(job)]
    if not jobs:
        return
    lines = []
    for job in jobs:
        current, total = stage_cursor(job.get("stage"))
        step = f"{current}/{total}" if current and total else friendly_stage_name(str(job.get("stage") or ""))
        lines.append(
            f"{esc(str(job.get('question_id')))}｜{esc(str(job.get('job_type')))} "
            f"{esc(ui_status(job))} {esc(step)} · {_elapsed_text(job)}"
        )
    st.markdown(
        f"""<div class="ws-job-bar" data-testid="global-job-status-bar">
          <div class="ws-job-bar-count">活动任务 {len(jobs)}</div>
          <div class="ws-job-bar-list">{'<br/>'.join(lines)}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    if st.button("查看进度", key="ws_job_bar_focus"):
        st.session_state[FOCUS_JOB_KEY] = jobs[0].get("job_id")


def _render_job_cards() -> None:
    """渲染当前题目的 Job 卡片；供 Fragment 与静态路径共用。"""
    slot = st.empty()
    jobs = collect_visible_jobs(state.get(state.KEY_SELECTED_QID))
    if not jobs:
        slot.empty()
        return
    sequences = st.session_state.setdefault(LAST_EVENT_SEQ_KEY, {})
    if not isinstance(sequences, dict):
        sequences = {}
        st.session_state[LAST_EVENT_SEQ_KEY] = sequences
    with slot.container():
        for job in jobs:
            job_id = str(job["job_id"])
            live = api_client.get_job(job_id) or job
            events: list[dict[str, Any]] = []
            if is_active(live):
                after = int(sequences.get(job_id) or 0)
                events = api_client.list_job_events(job_id, after_sequence=after)
                if events:
                    sequences[job_id] = max(int(item.get("sequence") or 0) for item in events)
                    live = {**live, "last_event": events[-1]}
            render_progress_card(live)
            apply_job_result_if_ready(live)
            if events:
                with st.expander("最近事件", expanded=False):
                    for item in events[-8:]:
                        st.caption(
                            f"{item.get('sequence')} · {item.get('event_type')} · "
                            f"{item.get('stage') or ''} · {item.get('message') or ''}"
                        )


@st.fragment(run_every="1s")
def render_job_progress_fragment() -> None:
    """只刷新进度区域；不重建题库、侧栏或科学管线。"""
    _render_job_cards()


def render_page_job_surface(question_id: str | None, *job_types: str) -> None:
    try:
        jobs = collect_visible_jobs(question_id)
        if any(is_active(job) for job in jobs):
            render_job_progress_fragment()
        else:
            _render_job_cards()
    except Exception as exc:  # noqa: BLE001 — 进度区失败不得阻断工作区
        st.caption(f"任务进度区暂时不可用：{type(exc).__name__}")
