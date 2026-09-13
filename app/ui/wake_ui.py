"""
app.ui.wake_ui —— "开始生成"点击后、真实模式下 sage125-api 唤醒等待的
非阻塞状态机（SAGE125-UI-API-HEALTH-HANDOFF-ROOT-FIX-01）。

根因（已通过线上日志 + 代码追踪确认，不是猜测）：
    旧实现在 ``process_run_triggers`` 内部用一个同步 while 循环
    （``wait_for_api_ready_indefinitely``）**阻塞当前脚本执行**，直到探测到
    ``ready=True``。这个写法在 Streamlit 的重跑模型下有一个致命缺陷：脚本
    正在执行期间，只要用户做了任何其它交互（切页、点别的控件，甚至
    Streamlit/浏览器自身触发的重连重跑），Streamlit 会直接终止这次脚本执行去
    跑一个新的；而"要不要继续等待"这个意图，只存在于刚被杀掉的那次脚本的
    本地变量里，**没有任何地方持久化它**。下一次重跑时，触发按钮对应的
    一次性布尔标志（``trigger_generate``/``trigger_mock``）已经变回 False，
    ``process_run_triggers`` 顶部的早退检查会直接跳过整个真实模式分支——
    背后已经没有任何代码还在探测，但页面上最后一次真正渲染出来的"进度卡片"
    会原地保留（Streamlit 不会主动清空一个不再被当前脚本触达的区域）。这就是
    "API 明明已经 ready，页面却一直卡在 95% 不动"的真正根因：不是就绪判定
    逻辑错了，而是承载这个判定循环的那次脚本执行本身已经被提前杀死。

修复方式（本模块）：
    1) 点击「开始生成」只做一件事——把"待提交意图"写进
       ``st.session_state``（普通业务 key，不是 widget key，不受切页时
       widget 清理机制影响，也不依赖一次性触发标志），然后立即返回。
    2) 用 ``st.fragment(run_every=...)`` 挂一个短周期探测器：它只依赖
       session_state 里是否存在意图，不依赖任何一次性触发标志。不管中间
       发生多少次全页重跑/切页，只要浏览器 session 还活着、用户没有主动
       取消，这个 fragment 就会按周期继续探测、继续更新"已等待时间/最近
       探测时间/连接状态/错误分类"，且探测本身有边界超时，不会长期占用
       主线程。
    3) 探测到 ``core_ready`` 后，fragment 自己触发一次全页 rerun；下一次全页
       重跑里，调用方发现意图状态是 "ready"，就消费且只消费这一次
       （调用 submit_or_reuse_job 后立即清除意图），避免重复提交。

健康判定契约（"就绪"的定义）完全委托给 ``app.ui.api_client``：
``rag_index_status == "empty"``、``storage.persistent == False`` 等都不影响
"API 是否已经从冷启动中恢复"这一层判断；那些属于任务前置条件，由
``run_preflight``（服务端 ``/preflight``）负责，本模块不重复其逻辑。
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import streamlit as st

from app.ui import api_client

_WAKE_STATE_KEY = "_sage125_wake_intent"
_POLL_INTERVAL_SECONDS = 2.0
_PROBE_TIMEOUT_SECONDS = 20

PHASE_WAKING = "waking"
PHASE_READY = "ready"

_REASON_LABELS = {
    "render_waking": "Render 平台仍在分配/启动实例",
    "not_sage125": "收到了响应，但无法识别为 sage125-api",
    "invalid_json": "收到了响应，但内容不是合法业务 JSON",
    "network_unreachable": "网络不可达",
    "connection_error": "无法建立连接",
    "connect_timeout": "连接超时",
    "read_timeout": "读取响应超时",
    "timeout": "请求超时",
    "tls_error": "TLS/证书错误",
    "auth_error": "鉴权失败（HTTP 401/403）",
    "not_found": "目标地址返回 404",
    "rate_limited": "触发限流（HTTP 429）",
    "server_error": "目标服务返回 5xx",
}


def intent_signature(*, question_id: str, job_type: str, mode: str, switches: dict[str, Any]) -> str:
    """从一次点击的关键输入构造稳定签名。

    输入不变时视为同一个意图（幂等，允许多次重跑复用同一次等待/避免重复
    提交）；question_id/job_type/mode/switches 任一变化，则视为一个新意图
    （不得把旧问题的等待结果，提交成新问题的 Job）。
    """
    payload = {
        "question_id": str(question_id),
        "job_type": str(job_type),
        "mode": str(mode),
        "switches": {str(k): bool(v) for k, v in sorted((switches or {}).items())},
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _fresh_intent(*, signature: str, question_id: str, job_type: str, mode: str, switches: dict[str, Any]) -> dict[str, Any]:
    return {
        "signature": signature,
        "phase": PHASE_WAKING,
        "question_id": str(question_id),
        "job_type": str(job_type),
        "mode": str(mode),
        "switches": dict(switches or {}),
        "probe_id_prefix": api_client.new_probe_id("wake-intent"),
        "attempts": 0,
        "started_at": time.monotonic(),
        "last_probe_at": None,
        "next_probe_at": 0.0,
        "last_reason": None,
        "last_http_status": None,
        "last_exception_type": None,
        "paused": False,
        "cancelled": False,
    }


def start_or_resume_intent(
    *, question_id: str, job_type: str, mode: str, switches: dict[str, Any]
) -> dict[str, Any]:
    """建立（或复用同一签名的）等待意图；返回当前意图状态字典（浅拷贝，避免调用方误改内部状态）。"""
    signature = intent_signature(question_id=question_id, job_type=job_type, mode=mode, switches=switches)
    existing = st.session_state.get(_WAKE_STATE_KEY)
    if isinstance(existing, dict) and existing.get("signature") == signature:
        return dict(existing)
    intent = _fresh_intent(
        signature=signature, question_id=question_id, job_type=job_type, mode=mode, switches=switches
    )
    st.session_state[_WAKE_STATE_KEY] = intent
    return dict(intent)


def get_intent() -> dict[str, Any] | None:
    intent = st.session_state.get(_WAKE_STATE_KEY)
    return dict(intent) if isinstance(intent, dict) else None


def clear_intent() -> None:
    st.session_state.pop(_WAKE_STATE_KEY, None)


def cancel_intent() -> None:
    intent = st.session_state.get(_WAKE_STATE_KEY)
    if isinstance(intent, dict):
        intent["cancelled"] = True
        st.session_state[_WAKE_STATE_KEY] = intent


def toggle_pause() -> None:
    intent = st.session_state.get(_WAKE_STATE_KEY)
    if isinstance(intent, dict):
        intent["paused"] = not intent.get("paused")
        st.session_state[_WAKE_STATE_KEY] = intent


def perform_one_probe_step(intent: dict[str, Any]) -> dict[str, Any]:
    """对一个"正在唤醒"的意图做**恰好一次**有边界超时的 /health 探测并返回更新后的字典。

    纯函数风格（不读写 st.session_state），方便单测直接驱动、不依赖
    ScriptRunContext；调用方负责把返回值写回 session_state。
    """
    updated = dict(intent)
    probe_id = f"{updated.get('probe_id_prefix', 'wake')}-{updated.get('attempts', 0) + 1}"
    state = api_client.probe_api_wake_state(timeout=_PROBE_TIMEOUT_SECONDS, probe_id=probe_id)
    updated["attempts"] = int(updated.get("attempts", 0)) + 1
    now = time.monotonic()
    updated["last_probe_at"] = now
    updated["next_probe_at"] = now + _POLL_INTERVAL_SECONDS
    updated["last_reason"] = state.get("reason")
    updated["last_http_status"] = state.get("http_status")
    updated["last_exception_type"] = state.get("exception_type")
    if state.get("ready"):
        updated["phase"] = PHASE_READY
        updated["ready_elapsed_seconds"] = now - float(updated.get("started_at", now))
    return updated


def _format_ago(monotonic_ts: float | None) -> str:
    if not monotonic_ts:
        return "尚未探测"
    delta = max(time.monotonic() - float(monotonic_ts), 0.0)
    return f"{api_client.format_wake_elapsed_label(delta)} 前"


def describe_status(intent: dict[str, Any]) -> str:
    """把一个意图翻译成一行人类可读状态说明；不编造百分比/剩余时间。"""
    if intent.get("cancelled"):
        return "状态：已取消等待"
    if intent.get("phase") == PHASE_READY:
        return "状态：API 已就绪"
    if intent.get("paused"):
        return "状态：已暂停探测（点击「继续探测」恢复）"
    if not intent.get("attempts"):
        return "状态：即将开始第一次探测"
    reason = intent.get("last_reason")
    label = _REASON_LABELS.get(reason, reason or "正在等待响应")
    http_status = intent.get("last_http_status")
    extra = f"（HTTP {http_status}）" if http_status else ""
    return f"状态：{label}{extra}"


def render_waiting_card(intent: dict[str, Any]) -> None:
    """不确定进度展示：已等待时间/探测次数/最近探测时间/状态分类；不使用固定 95% 曲线。"""
    elapsed = time.monotonic() - float(intent.get("started_at", time.monotonic()))
    st.markdown("**sage125-api 正在唤醒**")
    # 这里的进度条只是"正在持续进行中"的活体指示（不会停在某个固定百分比不动，
    # 也不会用 elapsed/expected 编造一个虚假的完成度），真正的完成判据只有
    # core_ready == True 这一条。
    pulse = min(0.08 + 0.015 * intent.get("attempts", 0), 0.9)
    st.progress(pulse)
    cols = st.columns(3)
    with cols[0]:
        st.caption(f"已等待：{api_client.format_wake_elapsed_label(elapsed)}")
    with cols[1]:
        st.caption(f"探测次数：{intent.get('attempts', 0)}")
    with cols[2]:
        st.caption(f"最近一次探测：{_format_ago(intent.get('last_probe_at'))}")
    st.caption(describe_status(intent))
    st.caption(
        "恢复时间暂无法估算——Render 免费实例冷启动时长不固定；系统会持续探测、"
        "不会超时放弃，也不会要求你重新点击。"
    )
    btn_cols = st.columns(2)
    with btn_cols[0]:
        label = "继续探测" if intent.get("paused") else "暂停探测"
        st.button(label, key="_sage125_wake_pause_btn", on_click=toggle_pause, width="stretch")
    with btn_cols[1]:
        st.button("取消本次等待", key="_sage125_wake_cancel_btn", on_click=cancel_intent, width="stretch")


@st.fragment(run_every=_POLL_INTERVAL_SECONDS)
def poll_wake_intent() -> None:
    """短周期探测片段：每次触发最多做一次有边界的探测，不阻塞整页脚本执行。"""
    intent = st.session_state.get(_WAKE_STATE_KEY)
    if not isinstance(intent, dict) or intent.get("phase") != PHASE_WAKING:
        return
    if intent.get("cancelled"):
        st.info("已取消本次等待；重新点击「开始生成」可以再次尝试。")
        return
    if intent.get("paused"):
        render_waiting_card(intent)
        return
    if time.monotonic() < float(intent.get("next_probe_at", 0.0)):
        render_waiting_card(intent)
        return
    updated = perform_one_probe_step(intent)
    st.session_state[_WAKE_STATE_KEY] = updated
    if updated.get("phase") == PHASE_READY:
        api_client._record_last_wake_seconds(updated.get("ready_elapsed_seconds") or 0.0)
        # 跳出 fragment 的局部刷新范围，让下一次全页重跑去消费"已就绪"并建立后台
        # 任务；本函数自身不直接触发任务创建，那一步统一收敛在调用方顶层，
        # 避免绕过页面顶部的一次性消费保护、增加重复提交风险。
        st.rerun(scope="app")
        return
    render_waiting_card(updated)
