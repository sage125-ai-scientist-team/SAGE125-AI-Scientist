"""
app.ui.state —— 前端 session_state 统一管理（集中、防串线）。

关键修复（P0-1 选题-报告一致性）：
    - 唯一选题状态：selected_question_id / selected_question_text；
    - 唯一运行状态：active_run_id / active_run_question_id；
    - 切换问题时清空 active run（除非用户显式 Load Latest Run）；
    - 不自动加载历史 run，不自动套用任何 demo preset。

安全：绝不在 session_state 中存储 API Key。
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# ---- 统一 session key ----
KEY_SELECTED_QID = "selected_question_id"
KEY_SELECTED_QTEXT = "selected_question_text"
KEY_ACTIVE_RUN_ID = "active_run_id"
KEY_ACTIVE_RUN_QID = "active_run_question_id"
KEY_RUN_RESULT = "run_result"
KEY_MODE = "mode"  # "mock" | "real"
KEY_OFFLINE = "offline_browse"  # 是否处于历史结果浏览
KEY_FEEDBACK_TEXT = "feedback_text"
KEY_PENDING_QID = "pending_question_id"  # 外部选择（preset/history）在 selector 渲染前消费
KEY_PRESET_QID = KEY_PENDING_QID  # 向后兼容旧引用
KEY_RUN_STATUS = "run_status"  # idle | running | completed | failed | partial_failed

# 向后兼容别名（旧代码/测试可能引用）。
KEY_QUESTION_ID = KEY_SELECTED_QID
KEY_RUN_ID = KEY_ACTIVE_RUN_ID


def init_state() -> None:
    """初始化默认 session 状态（幂等）。"""
    st.session_state.setdefault(KEY_MODE, "mock")
    st.session_state.setdefault(KEY_RUN_RESULT, {})
    st.session_state.setdefault(KEY_ACTIVE_RUN_ID, None)
    st.session_state.setdefault(KEY_ACTIVE_RUN_QID, None)
    st.session_state.setdefault(KEY_SELECTED_QID, None)
    st.session_state.setdefault(KEY_SELECTED_QTEXT, None)
    st.session_state.setdefault(KEY_OFFLINE, False)
    st.session_state.setdefault(KEY_PENDING_QID, None)
    st.session_state.setdefault(KEY_RUN_STATUS, "idle")


def begin_run() -> None:
    """
    启动新运行前清空当前 plan/artifacts，避免失败时展示旧报告。

    保留 selected_question；active_run_id 在运行结束后写入。
    """
    st.session_state[KEY_RUN_RESULT] = {}
    st.session_state[KEY_ACTIVE_RUN_ID] = None
    st.session_state[KEY_ACTIVE_RUN_QID] = None
    st.session_state[KEY_OFFLINE] = False
    st.session_state[KEY_RUN_STATUS] = "running"


def fail_run(run_id: str | None = None) -> None:
    """标记运行失败，不写入 plan（ResearchPlan Studio 显示 Empty Failed State）。"""
    st.session_state[KEY_RUN_RESULT] = {"run_id": run_id, "status": "failed", "plan": None}
    st.session_state[KEY_ACTIVE_RUN_ID] = run_id
    st.session_state[KEY_RUN_STATUS] = "failed"
    st.session_state[KEY_OFFLINE] = False


def get(key: str, default: Any = None) -> Any:
    """读取 session_state（带默认值）。"""
    return st.session_state.get(key, default)


def set_value(key: str, value: Any) -> None:
    """写入 session_state。"""
    st.session_state[key] = value


def select_question(qid: str, qtext: str) -> None:
    """
    设置当前选中问题；若问题发生变化，则清空 active run（防止旧报告串线）。

    参数：
        qid:   选中问题 ID。
        qtext: 选中问题文本。
    """
    prev = st.session_state.get(KEY_SELECTED_QID)
    st.session_state[KEY_SELECTED_QID] = qid
    st.session_state[KEY_SELECTED_QTEXT] = qtext
    if prev is not None and prev != qid:
        # 切换问题：清空当前运行结果，不自动加载旧 run，不套用 demo。
        clear_run()


def queue_question_selection(qid: str | None) -> None:
    """排队一个由 preset/history 触发的选题，供 selector 创建前原子同步。"""

    st.session_state[KEY_PENDING_QID] = qid


def consume_question_selection() -> str | None:
    """读取并清空待同步 QID；必须在问题 selectbox 实例化前调用。"""

    qid = st.session_state.get(KEY_PENDING_QID)
    st.session_state[KEY_PENDING_QID] = None
    return str(qid) if qid else None


def set_run_result(result: dict, question_id: str | None = None) -> None:
    """
    保存一次运行结果，并记录该结果所属的 question_id（用于一致性校验）。

    参数：
        result:      运行结果 dict（含 run_id / plan 等）。
        question_id: 该运行对应的问题 ID（缺省从 plan.question_id 推断）。
    """
    result = result or {}
    st.session_state[KEY_RUN_RESULT] = result
    st.session_state[KEY_ACTIVE_RUN_ID] = result.get("run_id")
    plan = result.get("plan") or {}
    qid = question_id or plan.get("question_id") or result.get("question_id")
    st.session_state[KEY_ACTIVE_RUN_QID] = qid
    st.session_state[KEY_RUN_STATUS] = result.get("status", "completed")
    st.session_state[KEY_OFFLINE] = False


def get_run_result() -> dict:
    """读取当前运行结果。"""
    return st.session_state.get(KEY_RUN_RESULT, {}) or {}


def clear_run() -> None:
    """清空当前运行结果（Clear Current Run / 切题）。"""
    st.session_state[KEY_RUN_RESULT] = {}
    st.session_state[KEY_ACTIVE_RUN_ID] = None
    st.session_state[KEY_ACTIVE_RUN_QID] = None
    st.session_state[KEY_OFFLINE] = False
    st.session_state[KEY_RUN_STATUS] = "idle"


def run_status() -> str:
    """返回当前运行状态 idle/running/completed/failed/partial_failed。"""
    return st.session_state.get(KEY_RUN_STATUS, "idle")


def current_mode() -> str:
    """返回当前模式（mock/real）。"""
    return st.session_state.get(KEY_MODE, "mock")


def active_run_id() -> str | None:
    """返回当前 active run id。"""
    return st.session_state.get(KEY_ACTIVE_RUN_ID)


def is_run_consistent() -> bool:
    """
    校验当前 active run 是否与所选问题一致。

    返回：
        True 表示一致或无 run；False 表示 run 的 question_id 与所选不一致。
    """
    run_qid = st.session_state.get(KEY_ACTIVE_RUN_QID)
    sel_qid = st.session_state.get(KEY_SELECTED_QID)
    if not run_qid or not sel_qid:
        return True
    return str(run_qid) == str(sel_qid)
