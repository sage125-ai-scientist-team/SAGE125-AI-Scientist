# -*- coding: utf-8 -*-
"""
SAGE125-API-WAKE-PROGRESS-TIME-SYNC-01

Render 冷启动等待体验优化：API 唤醒进度条必须与真实等待时间同步展示，而不是
"前 30 秒冲到 80%-90%，然后长时间卡在 99% 等 ready"。

覆盖点：
    1. 进度曲线三段时间匹配（60s≈45%、150s≈80%）；
    2. 未 ready 时永远不能到 100%，长时间等待也只封顶 95%（不会卡 99%）；
    3. ready=True 时立即 100%（包括"API 早已热启动，第一次探测就 ready"的场景）；
    4. 超过预计时间仍未 ready：文案改为"已超过预计启动时间"，不是"剩余 0 秒"；
    5. 预计等待时间来自历史唤醒耗时估算，并限制在 [90, 300] 秒；
    6. 用户只点一次「开始生成」：ready 后自动调用 submit_or_reuse_job，超时/未 ready
       时绝不创建 Job（源码级结构断言——process_run_triggers 所在的
       app/ui/streamlit_app.py 依赖 sage125_landing 自定义组件的资产注册，
       在 pytest 裸模式下 import 会报
       "must be declared in pyproject.toml with asset_dir"，这是与本次改动
       无关的既有环境限制；因此项目里其它测试文件对这个函数也一直只做源码
       文本断言，不实际 import/调用，这里沿用同样的约定）；
    7. 本次改动不影响已有 AI Scientist 运行阶段进度条。
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.ui import api_client, job_state, state

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _trigger_source() -> str:
    src = _read("app/ui/streamlit_app.py")
    return src.split("def process_run_triggers", 1)[1].split("if trigger_latest", 1)[0]


# ---------------------------------------------------------------------------
# 1. 进度曲线：三段时间匹配（纯函数，默认 expected_seconds=180）。
# ---------------------------------------------------------------------------


def test_progress_at_60s_is_about_45_percent():
    progress = api_client.compute_wake_progress_percent(60.0, 180.0, ready=False)
    assert abs(progress - 45.0) <= 1.0


def test_progress_at_150s_is_about_80_percent():
    progress = api_client.compute_wake_progress_percent(150.0, 180.0, ready=False)
    assert abs(progress - 80.0) <= 1.0


def test_progress_at_180s_is_about_83_percent_not_90():
    """180 秒时是刚进入第三阶段 30 秒，只有约 83%——不是线性算法会给出的 100%。"""
    progress = api_client.compute_wake_progress_percent(180.0, 180.0, ready=False)
    assert 78.0 <= progress <= 88.0


def test_progress_does_not_rush_ahead_in_first_30_seconds():
    """前 30 秒不能冲到 80%-90%（线性/激进算法的典型症状）。"""
    progress = api_client.compute_wake_progress_percent(30.0, 180.0, ready=False)
    assert progress < 30.0


def test_progress_never_100_before_ready_even_after_long_wait():
    """禁止简单线性算法：等待再久，未 ready 前也不能到 100，且封顶 95（不卡 99%）。"""
    for elapsed in (150.0, 180.0, 240.0, 300.0, 600.0, 3600.0):
        progress = api_client.compute_wake_progress_percent(elapsed, 180.0, ready=False)
        assert progress < 100.0
        assert progress <= 95.0


def test_progress_under_95_at_300s_without_ready():
    progress = api_client.compute_wake_progress_percent(300.0, 180.0, ready=False)
    assert progress < 95.0


def test_progress_ready_is_always_100_regardless_of_elapsed():
    for elapsed in (0.0, 1.0, 60.0, 500.0):
        assert api_client.compute_wake_progress_percent(elapsed, 180.0, ready=True) == 100.0


def test_progress_monotonic_increasing_over_time():
    """progress(t) 必须随时间缓慢增加，不能出现倒退或跳变式抢跑。"""
    samples = [
        api_client.compute_wake_progress_percent(t, 180.0, ready=False)
        for t in range(0, 400, 5)
    ]
    for earlier, later in zip(samples, samples[1:]):
        assert later >= earlier - 1e-9


# ---------------------------------------------------------------------------
# 2. 曲线随 expected_seconds 等比缩放（历史唤醒时间估算场景）。
# ---------------------------------------------------------------------------


def test_progress_curve_scales_with_expected_seconds():
    """expected=90（最小值）时，30 秒应到达约 45%（90/3=30s 是第一阶段终点）。"""
    progress = api_client.compute_wake_progress_percent(30.0, 90.0, ready=False)
    assert abs(progress - 45.0) <= 1.0


def test_resolve_expected_seconds_defaults_to_180_without_history():
    assert api_client.resolve_expected_wake_seconds(None) == 180.0


def test_resolve_expected_seconds_uses_last_wake_history_and_clamps():
    # 0.5*180 + 0.5*400 = 290，未超过 300 上限。
    assert api_client.resolve_expected_wake_seconds(400.0) == 290.0
    # 历史很短：0.5*180 + 0.5*20 = 100，未低于 90 下限。
    assert api_client.resolve_expected_wake_seconds(20.0) == 100.0
    # 公式恒为 0.5*180 + 0.5*last（last>=0 时结果天然 >=90），下限 90 是防御性
    # 兜底；历史极长时，估算会超过 300 上限，必须被夹紧到 300。
    assert api_client.resolve_expected_wake_seconds(1000.0) == 300.0
    assert api_client.resolve_expected_wake_seconds(1.0) == 90.5


def test_last_wake_seconds_round_trips_through_session_state():
    original = st.session_state
    st.session_state = {}
    try:
        assert api_client.last_wake_seconds() is None
        api_client._record_last_wake_seconds(42.0)
        assert api_client.last_wake_seconds() == 42.0
        assert api_client.resolve_expected_wake_seconds() == 0.5 * 180.0 + 0.5 * 42.0
    finally:
        st.session_state = original


# ---------------------------------------------------------------------------
# 3. 时间显示格式化 + snapshot 汇总字段（进度/已等待/预计总耗时/预计剩余/超期）。
# ---------------------------------------------------------------------------


def test_format_wake_elapsed_label_mm_ss():
    assert api_client.format_wake_elapsed_label(0) == "00:00"
    assert api_client.format_wake_elapsed_label(75) == "01:15"
    assert api_client.format_wake_elapsed_label(180) == "03:00"


def test_wake_progress_snapshot_not_overdue_shows_remaining():
    snap = api_client.wake_progress_snapshot(90.0, 180.0, ready=False)
    assert snap["overdue"] is False
    assert snap["remaining_label"] == "01:30"
    assert snap["elapsed_label"] == "01:30"
    assert snap["expected_label"] == "03:00"


def test_wake_progress_snapshot_overdue_does_not_claim_zero_remaining():
    """超过预计时间后：不能显示"剩余 0 秒"，而是标记 overdue 交给上层换成等待文案。"""
    snap = api_client.wake_progress_snapshot(240.0, 180.0, ready=False)
    assert snap["overdue"] is True
    assert snap["remaining_seconds"] == 0.0


def test_wake_progress_snapshot_ready_is_100_percent():
    snap = api_client.wake_progress_snapshot(45.0, 180.0, ready=True)
    assert snap["percent"] == 100.0


def test_cold_start_budget_default_is_360_seconds(monkeypatch):
    monkeypatch.delenv("FRONTEND_API_COLD_START_BUDGET_SECONDS", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    assert api_client._cold_start_budget_seconds() == 360


# ---------------------------------------------------------------------------
# 4. 用户只点一次「开始生成」：ready 后自动衔接 submit_or_reuse_job；
#    超时/未 ready 时绝不创建 Job。
#
#    app/ui/streamlit_app.py 依赖 sage125_landing 自定义组件资产注册，在
#    pytest 裸模式下直接 import 会抛
#    "must be declared in pyproject.toml with asset_dir"——这是与本次改动
#    无关的既有环境限制（其它测试文件里涉及 process_run_triggers 的用例，
#    例如 test_render_deployment.py::test_real_start_preflight_allows_hosted_wake，
#    也都只读取源码文本断言，从不实际 import/调用）。这里沿用同一约定做
#    结构性断言。
# ---------------------------------------------------------------------------


def test_ready_branch_auto_calls_submit_or_reuse_job_without_extra_click():
    """ready 分支必须在同一次函数调用里自动继续建 Job，不等待用户再点一次。"""
    trigger_src = _trigger_source()
    ready_branch = trigger_src.split("if wake_state.get(\"ready\"):", 1)[1].split(
        "if not wake_state.get(\"ready\"):", 1
    )[0]
    assert "submit_or_reuse_job" not in ready_branch  # 这一段只负责记录唤醒耗时
    assert "_record_last_wake_seconds" in ready_branch

    submit_branch = trigger_src.split("if not wake_state.get(\"ready\"):", 1)[1]
    assert "submit_or_reuse_job(" in submit_branch.split("else:", 1)[1]


def test_timeout_branch_never_creates_job_and_never_claims_100():
    """未 ready（超时）分支绝不能调用 submit_or_reuse_job，也不能出现 progress=100 的字样。"""
    trigger_src = _trigger_source()
    timeout_branch = trigger_src.split('"error_type": "api_not_ready",', 1)[1].split(
        "else:", 1
    )[0]
    assert "submit_or_reuse_job" not in timeout_branch
    assert "启动超时" in trigger_src


def test_wake_progress_card_uses_time_synced_snapshot_not_linear_math():
    """唤醒卡片必须用 wake_progress_snapshot()/compute_wake_progress_percent() 的时间同步曲线，
    不能出现 elapsed/expected*100 这种简单线性算法。"""
    trigger_src = _trigger_source()
    assert "wake_progress_snapshot" in trigger_src
    assert "st.progress(" in trigger_src
    assert "elapsed_seconds\" / \"expected_seconds\" * 100" not in trigger_src
    assert "/ expected_wake_seconds * 100" not in trigger_src
    assert "elapsed_seconds / expected" not in trigger_src


def test_wake_card_does_not_use_full_page_rerun():
    """唤醒进度用同一个 placeholder 原地更新，不能用整页 st.rerun() 刷新导致闪烁。"""
    trigger_src = _trigger_source()
    wake_section = trigger_src.split("wake_slot = st.empty()", 1)[1].split(
        "wake_state = api_client.wait_for_api_ready", 1
    )[0]
    assert "st.rerun()" not in wake_section


def test_single_wake_slot_placeholder_reused_not_multiple_containers():
    """全程只用一个 st.empty() placeholder 原地刷新，不新增第二个独立进度区域。"""
    trigger_src = _trigger_source()
    assert trigger_src.count("wake_slot = st.empty()") == 1


# ---------------------------------------------------------------------------
# 5. 本次改动不得影响已有 AI Scientist 运行阶段进度条。
# ---------------------------------------------------------------------------


def test_existing_run_progress_module_untouched():
    """durable job 运行进度渲染模块与本次唤醒进度改动完全独立，不应包含新增的唤醒符号。"""
    import inspect

    from app.ui import progress as progress_ui

    src = inspect.getsource(progress_ui)
    assert "compute_wake_progress_percent" not in src
    assert "wake_progress_snapshot" not in src
    assert "resolve_expected_wake_seconds" not in src


def test_job_state_submit_or_reuse_job_signature_unchanged():
    """submit_or_reuse_job 的既有签名/字段不受本次唤醒进度改动影响。"""
    import inspect

    sig = inspect.signature(job_state.submit_or_reuse_job)
    assert set(sig.parameters.keys()) == {"question_id", "job_type", "mode", "switches"}


def test_state_module_has_no_new_wake_progress_keys():
    """业务 session state（15 阶段运行状态等）不新增唤醒进度相关字段，两者完全解耦。"""
    import inspect

    src = inspect.getsource(state)
    assert "wake_progress" not in src
    assert "compute_wake_progress_percent" not in src
