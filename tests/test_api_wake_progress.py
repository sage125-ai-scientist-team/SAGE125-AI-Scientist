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
    6. 用户只点一次「开始生成」：ready 后自动调用 submit_or_reuse_job（源码级结构
       断言——process_run_triggers 所在的 app/ui/streamlit_app.py 依赖
       sage125_landing 自定义组件的资产注册，在 pytest 裸模式下 import 会报
       "must be declared in pyproject.toml with asset_dir"，这是与本次改动
       无关的既有环境限制；因此项目里其它测试文件对这个函数也一直只做源码
       文本断言，不实际 import/调用，这里沿用同样的约定）；
    7. 本次改动不影响已有 AI Scientist 运行阶段进度条；
    8. 【最终产品要求】API 唤醒阶段绝不允许出现"超时失败"状态：不管等 5 分钟、
       10 分钟还是 30 分钟，只要还没 ready 就必须持续等待、持续更新进度，直到
       /health 真正 ready=True 才自动继续，绝不提示失败、绝不要求用户重新
       点击、绝不创建失败态 Job。
"""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from app.ui import api_client, job_state, state, wake_ui

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
#    唤醒阶段绝不允许出现"超时失败"状态（SAGE125-API-WAKE-PROGRESS-TIME-SYNC-
#    FINAL-PR-DEPLOY-01 最终产品要求：不管等 5 分钟、10 分钟还是 30 分钟，只
#    要 /health 还没 ready 就必须持续等待，不能提示失败、不能要求用户重新
#    点击、不能创建 Job）。
#
#    app/ui/streamlit_app.py 依赖 sage125_landing 自定义组件资产注册，在
#    pytest 裸模式下直接 import 会抛
#    "must be declared in pyproject.toml with asset_dir"——这是与本次改动
#    无关的既有环境限制（其它测试文件里涉及 process_run_triggers 的用例，
#    例如 test_render_deployment.py::test_real_start_preflight_allows_hosted_wake，
#    也都只读取源码文本断言，从不实际 import/调用）。这里沿用同一约定做
#    结构性断言。
# ---------------------------------------------------------------------------


def _wake_wait_block() -> str:
    """截取 process_run_triggers 里真实模式分支的代码段（唤醒等待 + 提交 Job）。"""
    trigger_src = _trigger_source()
    return trigger_src.split('if submit_ok and run_mode == "real":', 1)[1]


def test_wake_wait_uses_nonblocking_wake_ui_state_machine():
    """生产代码必须走 app.ui.wake_ui 的非阻塞状态机（start_or_resume_intent +
    poll_wake_intent），不能再用同步阻塞的 wait_for_api_ready_indefinitely /
    wait_for_api_ready（根因：一次性触发标志 + 同步 while 循环，切页/重跑会
    直接杀死等待意图，导致"API 已 ready 但页面卡住不动"）。"""
    block = _wake_wait_block()
    assert "wake_ui.start_or_resume_intent(" in block
    assert "wake_ui.poll_wake_intent(" in block
    assert "wait_for_api_ready_indefinitely(" not in block
    assert "wait_for_api_ready(" not in block


def test_wake_wait_never_shows_timeout_or_failure_text():
    """唤醒等待代码段里不能出现任何"超时/失败/重新点击"相关的用户可见文案或状态
    字段——这类分支已经被彻底移除，而不是被隐藏或跳过（本函数只检查会展示给
    用户或写进 accepted 状态的实际字符串，不检查解释性代码注释）。"""
    block = _wake_wait_block()
    for forbidden in (
        "API 服务启动超时",
        "\"status\": \"failed\"",
        "\"error_type\": \"api_not_ready\"",
        "请稍后重试",
        "再次点击",
    ):
        assert forbidden not in block


def test_ready_branch_auto_calls_submit_or_reuse_job_without_extra_click():
    """intent phase 变成 "ready" 后必须在同一次函数调用里自动继续建 Job，不等待
    用户再点一次；未就绪（phase == "waking"）分支必须直接 return，交给下一次
    重跑/fragment 继续探测，不能在本次调用里硬等。"""
    block = _wake_wait_block()
    assert 'intent["phase"] == wake_ui.PHASE_WAKING' in block
    assert "return" in block.split('intent["phase"] == wake_ui.PHASE_WAKING', 1)[1].split(
        "submit_or_reuse_job(", 1
    )[0]
    assert "submit_or_reuse_job(" in block


def test_wake_wait_call_site_has_no_ready_false_branch():
    """process_run_triggers 里不应再有 `if wake_state.get("ready")` /
    `if not wake_state.get("ready")` 这类分支判断——健康判定完全交给
    app.ui.wake_ui / app.ui.api_client 的结构化字段，不在调用点重复判断。"""
    trigger_src = _trigger_source()
    assert 'wake_state.get("ready")' not in trigger_src


def test_wake_wait_intent_is_cleared_after_consumption_exactly_once():
    """ready 分支消费后必须清除意图（wake_ui.clear_intent()），避免同一个
    "已就绪"状态在后续重跑里被重复提交。"""
    block = _wake_wait_block()
    after_ready = block.split('intent["phase"] == wake_ui.PHASE_WAKING', 1)[1]
    assert "wake_ui.clear_intent()" in after_ready


def test_process_run_triggers_does_not_early_exit_on_pending_wait():
    """守卫不能只看一次性触发标志：存在待消费的唤醒意图时，即使
    trigger_generate/trigger_mock 都是 False（例如切页后的普通重跑），也必须
    继续处理，否则等待状态会在中途被早退检查悄悄丢弃。"""
    trigger_src = _trigger_source()
    guard_section = trigger_src.split("fresh_click = trigger_generate or trigger_mock", 1)[1].split(
        "if fresh_click or resuming_pending_wait:", 1
    )[0]
    assert "resuming_pending_wait" in guard_section
    assert "wake_ui.get_intent()" in guard_section


def test_wait_for_api_ready_indefinitely_has_no_timeout_or_budget_parameter():
    """indefinitely 版本的函数签名里不能有预算参数；函数体的实际代码逻辑（去掉
    文档字符串后）也不能出现"预算耗尽退出循环"式的判断（docstring 里为了跟
    带预算版本对比，允许提及 max_wait_seconds 这个词，但代码本身不能有）。"""
    import ast
    import inspect

    sig = inspect.signature(api_client.wait_for_api_ready_indefinitely)
    assert "max_wait_seconds" not in sig.parameters
    assert "budget" not in sig.parameters

    src = inspect.getsource(api_client.wait_for_api_ready_indefinitely)
    tree = ast.parse(src)
    func_node = tree.body[0]
    # 去掉 docstring（ast 第一个 body 节点是 Expr(Constant) 时即为 docstring）。
    body_nodes = func_node.body[1:] if ast.get_docstring(func_node) else func_node.body
    code_only = "\n".join(ast.unparse(node) for node in body_nodes)
    for forbidden in ("max_wait_seconds", "budget", "WAKE_TIMEOUT", "API_TIMEOUT", "MAX_WAIT", "remaining"):
        assert forbidden not in code_only


def test_wait_for_api_ready_indefinitely_keeps_retrying_past_old_360s_budget():
    """即使探测次数远超过旧版 360 秒预算下可能达到的轮询次数，也必须继续等待，
    直到真正 ready 才返回；绝不提前放弃。"""
    calls = {"count": 0}
    # 旧的 360 秒预算 / 20 秒单次超时，最多约 18 次探测就会被放弃；这里故意让
    #它连续"未就绪" 50 次（远超旧预算的放弃阈值），第 51 次才 ready。
    NOT_READY_ATTEMPTS = 50

    def _fake_probe(*, timeout=None):  # noqa: ANN001 - 测试用 stub
        calls["count"] += 1
        if calls["count"] > NOT_READY_ATTEMPTS:
            return {"connected": True, "ready": True, "reason": None}
        return {"connected": False, "ready": False, "reason": "cold_start_placeholder"}

    events = []
    original_probe = api_client.probe_api_wake_state
    original_sleep = time.sleep
    api_client.probe_api_wake_state = _fake_probe
    time.sleep = lambda _seconds: None  # 测试里不真的等待
    try:
        result = api_client.wait_for_api_ready_indefinitely(
            poll_timeout_seconds=1,
            poll_interval_seconds=0.01,
            on_progress=events.append,
        )
    finally:
        api_client.probe_api_wake_state = original_probe
        time.sleep = original_sleep

    assert result["ready"] is True
    assert calls["count"] == NOT_READY_ATTEMPTS + 1
    assert len(events) == NOT_READY_ATTEMPTS + 1
    assert events[-1]["ready"] is True
    assert all(not e["ready"] for e in events[:-1])


def test_wake_card_shows_uncertain_progress_not_fixed_curve():
    """产品最新要求（SAGE125-UI-API-HEALTH-HANDOFF-ROOT-FIX-01）：唤醒卡片不再用
    固定 95% 封顶曲线/编造的剩余时间，而是展示已等待时间/探测次数/最近探测
    时间/错误分类，并明确提示"恢复时间暂无法估算"。"""
    import inspect

    src = inspect.getsource(wake_ui.render_waiting_card)
    assert "已等待" in src
    assert "探测次数" in src
    assert "最近一次探测" in src
    assert "恢复时间暂无法估算" in src
    # 不能再出现旧版"当前进度：XX%　预计总耗时"这种编造完成度的展示方式。
    assert "预计总耗时" not in src
    assert "预计剩余" not in src


def test_wake_poller_is_a_streamlit_fragment_not_a_blocking_loop():
    """探测器必须是 st.fragment(run_every=...)，每次只做一次有边界探测，不是
    while 循环同步阻塞整页脚本执行。"""
    import inspect

    assert getattr(wake_ui.poll_wake_intent, "__name__", "") == "poll_wake_intent"
    src = inspect.getsource(wake_ui)
    assert "@st.fragment(run_every=" in src
    poll_src = inspect.getsource(wake_ui.poll_wake_intent)
    assert "while " not in poll_src
    assert "time.sleep" not in poll_src


def test_ready_transition_triggers_full_app_rerun_not_direct_submit():
    """fragment 探测到 ready 后只负责触发一次全页 rerun，不在 fragment 内部直接
    调用 submit_or_reuse_job（提交动作统一收敛在 process_run_triggers 里，
    避免绕过一次性消费保护）。"""
    import inspect

    src = inspect.getsource(wake_ui.poll_wake_intent)
    assert 'st.rerun(scope="app")' in src
    assert "submit_or_reuse_job" not in src


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
