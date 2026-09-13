# -*- coding: utf-8 -*-
"""
SAGE125-UI-API-HEALTH-HANDOFF-ROOT-FIX-01（附带修复项）：

用户复现步骤："设置页换成真实模式，再点其他页面然后回到设置也还是模拟模式，
根本没法用真实模式。"

诊断证据（不是猜测）：线上 sage125-ui-preview 服务运行日志里实测到一条
Streamlit 运行时 WARNING：

    The widget with key "mode__control" was created with a default value
    but also had its value set via the Session State API.

定位到 app/ui/components.py::render_mode_control：旧实现在无条件把
``resolved_current`` 写入 ``st.session_state[MODE_WIDGET_KEY]`` 之后，又同时
给 ``segmented_control``/``selectbox`` 传了 ``default=``/``index=`` 参数——
Streamlit 的规则是"key 已在 session_state 中时用 session_state 的值初始化，
default/index 被忽略"，但只要两者同时出现就会打这条 WARNING，说明控件初始值
判定处于两套机制的边界状态。

修复：
    1) render_mode_control 不再同时传 default=/index=（session_state 已经
       无条件回填，default/index 完全冗余）。
    2) apply_query_mode 把"用户已明确选择过的业务状态"
       （KEY_MODE_EXPLICIT + KEY_MODE，由 on_change 回调同步写入，不依赖任何
       widget key 的存活时间点）提到最高优先级，不再依赖
       "st.session_state[MODE_WIDGET_KEY] 是否还带着新鲜值"这个 Streamlit
       内部实现细节。
"""

from __future__ import annotations

import inspect

import streamlit as st

from app.ui import components, state, workspace


def _read(rel: str) -> str:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return (root / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. 源码级：render_mode_control 不能再同时使用 default=/index= 与无条件
#    session_state 回填（这正是触发 Streamlit WARNING 的组合）。
# ---------------------------------------------------------------------------


def test_render_mode_control_does_not_pass_default_alongside_preset_session_state():
    import ast

    src = inspect.getsource(components.render_mode_control)
    assert "st.session_state[MODE_WIDGET_KEY] = resolved_current" in src
    tree = ast.parse(src)
    func_node = tree.body[0]
    body_nodes = func_node.body[1:] if ast.get_docstring(func_node) else func_node.body
    code_only = "\n".join(ast.unparse(node) for node in body_nodes)
    assert "default=" not in code_only
    assert "index=" not in code_only


def test_render_mode_control_still_returns_valid_mode_via_fake_widgets(monkeypatch):
    """回归：去掉 default=/index= 后功能不变——widget 返回值仍然生效。"""
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]

    def fake_segmented_control(label, options, *, format_func=None, key=None, on_change=None, args=None, **kwargs):
        assert "default" not in kwargs
        return st.session_state.get(key)

    monkeypatch.setattr(components.st, "segmented_control", fake_segmented_control)
    try:
        mode = components.render_mode_control("real")
        assert mode == "real"
    finally:
        st.session_state = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 2. apply_query_mode 优先级：明确业务状态优先于 widget key 快照。
# ---------------------------------------------------------------------------


def test_apply_query_mode_prioritizes_explicit_state_over_widget_snapshot():
    """核心回归：即便 widget key 快照因为 Streamlit 内部时序残留成过期值，
    只要业务状态已经明确记录过真实选择，就必须以业务状态为准。"""
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        # 模拟：用户已经明确选过 real（on_change 回调已经同步写入业务状态），
        # 但 widget key 因为某种 Streamlit 内部时序原因残留着旧的 mock 快照。
        state.set_value(state.KEY_MODE, "real")
        st.session_state[state.KEY_MODE_EXPLICIT] = True
        st.session_state[components.MODE_WIDGET_KEY] = "mock"

        workspace.apply_query_mode(fallback="mock")

        assert state.current_mode() == "real"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_apply_query_mode_still_falls_back_to_widget_when_state_not_explicit_yet():
    """未明确选择过时（KEY_MODE_EXPLICIT 仍为 False），widget key 的新鲜值仍然
    是次级兜底，行为与修复前一致。"""
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        st.session_state[components.MODE_WIDGET_KEY] = "real"

        workspace.apply_query_mode(fallback="mock")

        assert state.current_mode() == "real"
    finally:
        st.session_state = original  # type: ignore[assignment]


def test_navigate_away_and_back_keeps_real_mode_end_to_end(monkeypatch):
    """完整复现用户报告的步骤：设置页选真实模式 → 模拟切到其它页（widget key
    按 Streamlit 多页应用规则被清除）→ 切回设置页 → 必须仍是真实模式。"""
    original = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        monkeypatch.setattr(st, "query_params", {}, raising=False)

        # 第 1 步：进入设置页，首次渲染（尚无明确选择），apply_query_mode 无操作。
        workspace.apply_query_mode()
        assert state.current_mode() == "mock"

        # 第 2 步：设置页实际渲染一次，拿到 on_change 回调（渲染本身用 fake
        # segmented_control，不依赖真实 Streamlit 前端）。
        def fake_segmented_control_capture(label, options, *, format_func=None, key=None, on_change=None, args=None, **kwargs):
            captured["on_change"] = on_change
            captured["args"] = args or ()
            return st.session_state.get(key)

        captured: dict = {}
        monkeypatch.setattr(components.st, "segmented_control", fake_segmented_control_capture)
        components.render_mode_control(state.current_mode())

        # 第 3 步：用户点击"真实模式"。Streamlit 会先把新值写进 widget 的
        # session_state，再调用 on_change 回调，然后才重跑脚本主体。
        st.session_state[components.MODE_WIDGET_KEY] = "real"
        captured["on_change"](*captured["args"])
        assert state.current_mode() == "real"
        assert st.session_state.get(state.KEY_MODE_EXPLICIT) is True

        # 第 3 步：这次重跑里，设置页的 apply_query_mode 也会执行一次。
        workspace.apply_query_mode()
        assert state.current_mode() == "real"

        # 第 4 步：切换到另一个页面——该页面不渲染 render_mode_control，
        # 按 Streamlit 多页应用规则，widget key 在这次重跑结束后会被清除。
        st.session_state.pop(components.MODE_WIDGET_KEY, None)
        st.session_state.pop(components.MODE_WIDGET_FALLBACK_KEY, None)
        workspace.apply_query_mode()  # 其它页面同样会调用（通过 boot()）。
        assert state.current_mode() == "real"

        # 第 5 步：切回设置页。widget key 仍然缺失（本次重跑尚未执行到
        # render_mode_control），apply_query_mode 必须仍然给出 real。
        workspace.apply_query_mode()
        assert state.current_mode() == "real"

        # 第 6 步：设置页的 render_mode_control 实际渲染，用业务状态回填 widget。
        def fake_segmented_control(label, options, *, format_func=None, key=None, on_change=None, args=None, **kwargs):
            return st.session_state.get(key)

        monkeypatch.setattr(components.st, "segmented_control", fake_segmented_control)
        mode = components.render_mode_control(state.current_mode())
        assert mode == "real"
    finally:
        st.session_state = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 3. 文档化优先级顺序，防止未来又被颠倒回去。
# ---------------------------------------------------------------------------


def test_apply_query_mode_checks_explicit_state_before_widget_snapshot_in_source():
    src = _read("app/ui/workspace.py")
    body = src.split("def apply_query_mode", 1)[1].split("\ndef ", 1)[0]
    explicit_pos = body.find("if st.session_state.get(state.KEY_MODE_EXPLICIT):")
    widget_pos = body.find("live_widget = official_run_mode")
    assert explicit_pos != -1 and widget_pos != -1
    assert explicit_pos < widget_pos
