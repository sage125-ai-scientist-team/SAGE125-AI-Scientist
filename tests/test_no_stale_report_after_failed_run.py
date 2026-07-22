# -*- coding: utf-8 -*-
"""tests/test_no_stale_report_after_failed_run.py — 失败运行不保留旧 plan。"""

from __future__ import annotations

from app.ui import state


def test_begin_run_clears_plan(monkeypatch):
    """begin_run 清空 run_result。"""
    store = {
        state.KEY_RUN_RESULT: {"plan": {"paper_title": "old"}},
        state.KEY_ACTIVE_RUN_ID: "old-run",
        state.KEY_RUN_STATUS: "completed",
    }

    class FakeSession:
        def get(self, k, default=None):
            return store.get(k, default)

        def __setitem__(self, k, v):
            store[k] = v

        def __getitem__(self, k):
            return store[k]

    monkeypatch.setattr(state.st, "session_state", store)
    state.begin_run()
    assert store[state.KEY_RUN_RESULT] == {}
    assert store[state.KEY_RUN_STATUS] == "running"


def test_fail_run_no_plan(monkeypatch):
    """fail_run 不保留 plan。"""
    store = {state.KEY_RUN_RESULT: {}, state.KEY_RUN_STATUS: "running"}

    class FakeSession:
        def get(self, k, default=None):
            return store.get(k, default)

        def __setitem__(self, k, v):
            store[k] = v

    monkeypatch.setattr(state.st, "session_state", store)
    state.fail_run("failed-run-001")
    assert store[state.KEY_RUN_RESULT].get("plan") is None
    assert store[state.KEY_RUN_STATUS] == "failed"
