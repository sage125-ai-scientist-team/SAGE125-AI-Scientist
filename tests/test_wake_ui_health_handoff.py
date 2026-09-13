# -*- coding: utf-8 -*-
"""
SAGE125-UI-API-HEALTH-HANDOFF-ROOT-FIX-01

根因排查结论（已通过线上版本核实、代码追踪确认，不是猜测）：
    UI/API 部署版本一致、FRONTEND_API_BASE_URL 配置正确（已用只读 Render API
    直查确认），健康判定契约本身也认得出截图里的真实 /health JSON。真正卡住
    UI 的是承载"唤醒等待"的那次 Streamlit 脚本执行本身：旧实现在一次性触发
    标志（trigger_generate/trigger_mock）为真的那次脚本执行里，用同步 while
    循环（wait_for_api_ready_indefinitely）长期阻塞主线程；只要中途发生任何
    页面重跑（切页、其它交互、浏览器重连），这次脚本执行会被 Streamlit 直接
    杀掉重启，"还要不要继续等待"这个意图随之彻底丢失——下一次重跑时一次性
    触发标志已经是 False，process_run_triggers 顶部的早退检查直接跳过整个
    真实模式分支，页面上残留的是最后一次真正渲染出来的进度卡片，但背后已经
    没有代码在继续探测。这正是"API 已经 ready，页面却一直卡着不动"的根因。

本文件覆盖 app.ui.wake_ui 的非阻塞状态机：意图建立/复用/隔离、单步探测、
自动交接、幂等消费、暂停/取消、状态文案分类。
"""

from __future__ import annotations

import pytest

from app.ui import api_client, wake_ui


@pytest.fixture(autouse=True)
def _isolated_session_state(monkeypatch):
    """每个用例用一个全新的普通 dict 顶替 st.session_state，互不污染。"""
    fake_state: dict = {}
    monkeypatch.setattr(wake_ui.st, "session_state", fake_state)
    yield fake_state


# ---------------------------------------------------------------------------
# 1. 意图签名：输入不变即幂等；question_id/job_type/mode/switches 任一变化
#    都必须产生不同签名（禁止把旧问题的等待结果提交给新问题）。
# ---------------------------------------------------------------------------


def test_intent_signature_is_stable_for_same_inputs_regardless_of_switch_order():
    sig_a = wake_ui.intent_signature(
        question_id="Q001", job_type="full", mode="real", switches={"use_local_rag": True, "use_deep_research": False}
    )
    sig_b = wake_ui.intent_signature(
        question_id="Q001", job_type="full", mode="real", switches={"use_deep_research": False, "use_local_rag": True}
    )
    assert sig_a == sig_b


@pytest.mark.parametrize(
    "overrides",
    [
        {"question_id": "Q002"},
        {"job_type": "demo"},
        {"mode": "mock"},
        {"switches": {"use_local_rag": False, "use_deep_research": False}},
    ],
)
def test_intent_signature_changes_when_any_input_changes(overrides):
    base = dict(question_id="Q001", job_type="full", mode="real", switches={"use_local_rag": True, "use_deep_research": False})
    changed = dict(base, **overrides)
    assert wake_ui.intent_signature(**base) != wake_ui.intent_signature(**changed)


# ---------------------------------------------------------------------------
# 2. 建立 / 复用 / 隔离意图。
# ---------------------------------------------------------------------------


def test_start_or_resume_intent_creates_fresh_waking_intent():
    intent = wake_ui.start_or_resume_intent(
        question_id="Q001", job_type="full", mode="real", switches={"use_local_rag": True}
    )
    assert intent["phase"] == wake_ui.PHASE_WAKING
    assert intent["question_id"] == "Q001"
    assert intent["attempts"] == 0
    assert wake_ui.get_intent() is not None


def test_start_or_resume_intent_reuses_same_intent_for_same_signature():
    first = wake_ui.start_or_resume_intent(
        question_id="Q001", job_type="full", mode="real", switches={"use_local_rag": True}
    )
    # 模拟中间已经探测过几次。
    wake_ui.st.session_state[wake_ui._WAKE_STATE_KEY]["attempts"] = 7
    second = wake_ui.start_or_resume_intent(
        question_id="Q001", job_type="full", mode="real", switches={"use_local_rag": True}
    )
    assert second["signature"] == first["signature"]
    assert second["attempts"] == 7  # 复用，不是重置。


def test_start_or_resume_intent_resets_when_question_changes():
    """任务切换隔离：换了问题后必须建立全新意图，不能延续旧问题的等待状态。"""
    wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})
    wake_ui.st.session_state[wake_ui._WAKE_STATE_KEY]["attempts"] = 9
    wake_ui.st.session_state[wake_ui._WAKE_STATE_KEY]["phase"] = wake_ui.PHASE_READY

    fresh = wake_ui.start_or_resume_intent(question_id="Q002", job_type="full", mode="real", switches={})
    assert fresh["question_id"] == "Q002"
    assert fresh["attempts"] == 0
    assert fresh["phase"] == wake_ui.PHASE_WAKING


def test_clear_intent_removes_pending_state():
    wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})
    assert wake_ui.get_intent() is not None
    wake_ui.clear_intent()
    assert wake_ui.get_intent() is None


# ---------------------------------------------------------------------------
# 3. 单步探测：恰好一次有边界超时的探测，不是长阻塞轮询。
# ---------------------------------------------------------------------------


def test_perform_one_probe_step_advances_attempts_and_records_reason(monkeypatch):
    monkeypatch.setattr(
        api_client,
        "probe_api_wake_state",
        lambda *, timeout=None, probe_id=None: {
            "connected": True,
            "ready": False,
            "reason": "render_waking",
            "http_status": 200,
            "exception_type": None,
        },
    )
    intent = wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})
    updated = wake_ui.perform_one_probe_step(intent)

    assert updated["attempts"] == 1
    assert updated["phase"] == wake_ui.PHASE_WAKING
    assert updated["last_reason"] == "render_waking"
    assert updated["last_probe_at"] is not None


def test_perform_one_probe_step_transitions_to_ready(monkeypatch):
    monkeypatch.setattr(
        api_client,
        "probe_api_wake_state",
        lambda *, timeout=None, probe_id=None: {
            "connected": True,
            "ready": True,
            "reason": None,
            "http_status": 200,
            "exception_type": None,
        },
    )
    intent = wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})
    updated = wake_ui.perform_one_probe_step(intent)

    assert updated["phase"] == wake_ui.PHASE_READY
    assert updated["ready_elapsed_seconds"] >= 0.0


def test_perform_one_probe_step_passes_a_fresh_probe_id_each_call(monkeypatch):
    seen_probe_ids = []

    def _fake_probe(*, timeout=None, probe_id=None):
        seen_probe_ids.append(probe_id)
        return {"connected": False, "ready": False, "reason": "connection_error"}

    monkeypatch.setattr(api_client, "probe_api_wake_state", _fake_probe)
    intent = wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})
    intent = wake_ui.perform_one_probe_step(intent)
    intent = wake_ui.perform_one_probe_step(intent)

    assert len(seen_probe_ids) == 2
    assert seen_probe_ids[0] != seen_probe_ids[1]
    assert all(pid for pid in seen_probe_ids)


def test_perform_one_probe_step_never_sleeps_or_blocks(monkeypatch):
    """单步探测必须只做一次探测就返回；不能在函数内部自己 sleep/重试循环。"""
    import inspect

    src = inspect.getsource(wake_ui.perform_one_probe_step)
    assert "sleep" not in src
    assert "while " not in src
    assert "for " not in src


# ---------------------------------------------------------------------------
# 4. 自动交接：多次未就绪后终于就绪，全程恰好探测一次即完成一次交接，
#    且不需要用户二次点击（交接逻辑由调用方在 phase 变为 ready 后处理）。
# ---------------------------------------------------------------------------


def test_auto_handoff_after_several_not_ready_probes(monkeypatch):
    calls = {"n": 0}

    def _fake_probe(*, timeout=None, probe_id=None):
        calls["n"] += 1
        if calls["n"] < 4:
            return {"connected": True, "ready": False, "reason": "render_waking"}
        return {"connected": True, "ready": True, "reason": None}

    monkeypatch.setattr(api_client, "probe_api_wake_state", _fake_probe)
    intent = wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})

    for _ in range(3):
        intent = wake_ui.perform_one_probe_step(intent)
        assert intent["phase"] == wake_ui.PHASE_WAKING

    intent = wake_ui.perform_one_probe_step(intent)
    assert intent["phase"] == wake_ui.PHASE_READY
    assert intent["attempts"] == 4


# ---------------------------------------------------------------------------
# 5. 幂等：意图一旦被消费清除，不会残留导致重复提交。
# ---------------------------------------------------------------------------


def test_cleared_intent_cannot_be_resumed_accidentally():
    wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})
    wake_ui.st.session_state[wake_ui._WAKE_STATE_KEY]["phase"] = wake_ui.PHASE_READY
    wake_ui.clear_intent()

    assert wake_ui.get_intent() is None
    # 清除之后即使再查询，也不会"复活"出一个 ready 状态的意图。
    resumed = wake_ui.get_intent()
    assert resumed is None


# ---------------------------------------------------------------------------
# 6. 暂停 / 取消。
# ---------------------------------------------------------------------------


def test_toggle_pause_flips_flag():
    wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})
    assert wake_ui.get_intent()["paused"] is False
    wake_ui.toggle_pause()
    assert wake_ui.get_intent()["paused"] is True
    wake_ui.toggle_pause()
    assert wake_ui.get_intent()["paused"] is False


def test_cancel_intent_sets_cancelled_flag():
    wake_ui.start_or_resume_intent(question_id="Q001", job_type="full", mode="real", switches={})
    wake_ui.cancel_intent()
    assert wake_ui.get_intent()["cancelled"] is True


# ---------------------------------------------------------------------------
# 7. 状态文案分类：不确定进度展示的一部分，必须能区分不同错误类型，不能
#    笼统展示成同一句"服务不可用"。
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason,expected_snippet",
    [
        ("render_waking", "Render"),
        ("not_sage125", "无法识别"),
        ("connection_error", "无法建立连接"),
        ("rate_limited", "429"),
        ("server_error", "5xx"),
        ("auth_error", "401/403"),
    ],
)
def test_describe_status_classifies_reason(reason, expected_snippet):
    intent = {"attempts": 1, "last_reason": reason, "last_http_status": None, "phase": wake_ui.PHASE_WAKING}
    assert expected_snippet in wake_ui.describe_status(intent)


def test_describe_status_before_first_probe():
    intent = {"attempts": 0, "phase": wake_ui.PHASE_WAKING}
    assert "第一次探测" in wake_ui.describe_status(intent)


def test_describe_status_when_paused():
    intent = {"attempts": 3, "paused": True, "phase": wake_ui.PHASE_WAKING}
    assert "已暂停" in wake_ui.describe_status(intent)


def test_describe_status_when_ready():
    intent = {"attempts": 3, "phase": wake_ui.PHASE_READY}
    assert "已就绪" in wake_ui.describe_status(intent)
