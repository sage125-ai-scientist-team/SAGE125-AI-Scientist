"""
Render 冷启动占位页兼容性回归测试。

背景（真实线上现象，已通过只读诊断确认）：
    Render Free 实例冷启动期间，边缘节点可能先用 **HTTP 200** 返回自己的静态占位页
    （"Application loading" / "Service waking up" / "Starting the instance"...），
    而不是我们的业务 JSON。旧代码把 "HTTP 200" 直接当成 "业务成功"，在
    ``create_job`` / ``retry_job`` 的成功分支里对这种占位页 body 无保护地调用
    ``response.json()``，会抛出 ``ValueError``（``requests`` 内部的
    ``JSONDecodeError``），并且这个调用点不在任何 ``try/except`` 内，异常会一路
    冒穿到 Streamlit 顶层，表现为页面报错/崩溃、"开始生成"无法使用。

本文件覆盖任务要求的 6 个场景，并额外用 test_naive_response_json_would_raise_*
显式证明了旧的裸调用模式在同一输入下确实会抛异常（对照组）。
"""

from __future__ import annotations

import json

import pytest

from app.ui import api_client, job_state


# Render 平台级冷启动占位页的典型 body（与业务无关，纯静态模板）。
RENDER_PLACEHOLDER_HTML = (
    "<html><body>11:19:44 Incoming HTTP request detected ...\n"
    "Service waking up ...\nAllocating compute resources ...\n"
    "Starting the instance ...\nApplication loading</body></html>"
)


class FakeResponse:
    """极简 requests.Response 替身：足够覆盖 api_client.py 实际用到的接口面。"""

    def __init__(self, status_code, *, json_data=None, text="", headers=None, content=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.content = content if content is not None else (text.encode() if text else b"")

    def json(self):
        if self._json_data is not None:
            return self._json_data
        # 与真实 requests 行为一致：非 JSON body 会抛出 ValueError 的子类。
        raise json.JSONDecodeError("Expecting value", self.text or "", 0)


class FakeSession:
    """替代 api_client._http_session()：按顺序返回预置响应，多余调用复用最后一个。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def _next(self):
        self.calls += 1
        idx = min(self.calls - 1, len(self._responses) - 1)
        return self._responses[idx]

    def post(self, *_args, **_kwargs):
        return self._next()

    def get(self, *_args, **_kwargs):
        return self._next()


@pytest.fixture(autouse=True)
def _fast_and_clean(monkeypatch):
    """所有测试共用：不真的 sleep，且不让健康缓存跨用例污染。"""
    monkeypatch.setattr(api_client.time, "sleep", lambda *_a, **_k: None)
    api_client._clear_health_ok_cache()
    yield
    api_client._clear_health_ok_cache()


def _job_kwargs(**overrides):
    base = dict(
        question_id="Q001",
        mode="real",
        job_type="full_research_pipeline",
        client_id="client-1",
        input_digest="digest-1",
        idempotency_key="idem-1",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 对照组：证明"旧写法"在同样的输入上确实会崩。
# ---------------------------------------------------------------------------


def test_naive_response_json_would_raise_on_render_placeholder():
    """旧 bug 的最小复现：对占位页 body 直接 response.json() 会抛异常。"""
    response = FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"})
    with pytest.raises(ValueError):
        response.json()


def test_parse_json_response_handles_the_same_case_safely():
    """新的安全解析函数对同一响应不抛异常，明确返回 render_waking。"""
    response = FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"})
    data, reason = api_client.parse_json_response(response)
    assert data is None
    assert reason == "render_waking"


def test_parse_json_response_accepts_normal_json():
    response = FakeResponse(200, json_data={"status": "ok"})
    data, reason = api_client.parse_json_response(response)
    assert data == {"status": "ok"}
    assert reason is None


# ---------------------------------------------------------------------------
# 测试 1 / 2：health 接口的 connected / ready 拆分。
# ---------------------------------------------------------------------------


def test_health_html_is_connected_but_not_ready(monkeypatch):
    monkeypatch.setattr(
        api_client.requests,
        "get",
        lambda *a, **k: FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"}),
    )
    state = api_client.probe_api_wake_state(timeout=5)
    assert state["connected"] is True
    assert state["ready"] is False
    assert api_client.wake_hosted_api(wait=True) is False
    assert api_client.refresh_api_available() is False


def test_health_json_is_ready(monkeypatch):
    monkeypatch.setattr(
        api_client.requests,
        "get",
        lambda *a, **k: FakeResponse(200, json_data={"status": "ok"}, headers={"Content-Type": "application/json"}),
    )
    state = api_client.probe_api_wake_state(timeout=5)
    assert state["connected"] is True
    assert state["ready"] is True
    assert api_client.wake_hosted_api(wait=True) is True
    assert api_client.refresh_api_available() is True


# ---------------------------------------------------------------------------
# 测试 3：create_job 收到 HTML 不能抛异常，必须返回可重试的失败结构。
# ---------------------------------------------------------------------------


def test_create_job_html_does_not_raise_and_reports_api_not_ready(monkeypatch):
    placeholder = FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"})
    fake_session = FakeSession([placeholder] * 5)
    monkeypatch.setattr(api_client, "_http_session", lambda: fake_session)

    result = api_client.create_job(**_job_kwargs())

    assert result["status"] == "failed"
    assert not result.get("job_id")
    assert fake_session.calls == 5  # 5 次重试全部用尽，期间没有任何异常冒出来


# ---------------------------------------------------------------------------
# 测试 4：retry_job 收到 HTML，行为与 create_job 一致（同一套安全解析）。
# ---------------------------------------------------------------------------


def test_retry_job_html_does_not_raise_and_reports_api_not_ready(monkeypatch):
    placeholder = FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"})
    fake_session = FakeSession([placeholder])
    monkeypatch.setattr(api_client, "_http_session", lambda: fake_session)
    monkeypatch.setattr(api_client, "api_available", lambda: True)  # 跳过前置门禁，直击 retry 端点本身

    result = api_client.retry_job("job-existing", client_id="client-1")

    assert result["status"] == "failed"
    assert result["error_type"] == "api_not_ready"


# ---------------------------------------------------------------------------
# 测试 5：连续点击「开始生成」三次，只能创建一个 Job（幂等性）。
# ---------------------------------------------------------------------------


def test_repeated_submit_clicks_create_only_one_job(monkeypatch):
    session_state = {"active_job_ids": {}}
    monkeypatch.setattr(job_state.st, "session_state", session_state)

    job_store: dict[str, dict] = {}
    created_ids: list[str] = []

    def fake_create_job(*, question_id, mode, job_type, client_id, input_digest, idempotency_key, options=None):
        job_id = f"job-{len(created_ids) + 1}"
        created_ids.append(job_id)
        job = {
            "job_id": job_id,
            "status": "queued",
            "question_id": question_id,
            "job_type": job_type,
            "client_id": client_id,
            "created": True,
        }
        job_store[job_id] = job
        return job

    monkeypatch.setattr(job_state.api_client, "create_job", fake_create_job)
    monkeypatch.setattr(job_state.api_client, "get_job", lambda jid: job_store.get(jid))
    monkeypatch.setattr(job_state.api_client, "get_active_job", lambda **_k: None)
    monkeypatch.setattr(job_state.api_client, "get_latest_job", lambda **_k: None)
    monkeypatch.setattr(job_state.api_client, "list_jobs", lambda **_k: [])
    monkeypatch.setattr(job_state.state, "begin_run", lambda: None)
    monkeypatch.setattr(job_state.state, "set_value", lambda *_a, **_k: None)

    switches = {
        "use_deep_research": False,
        "use_open_literature": False,
        "use_local_rag": False,
        "reviewer_auto_revision": False,
    }
    for _ in range(3):
        job_state.submit_or_reuse_job(
            question_id="Q001", job_type=job_state.JOB_TYPE_FULL, mode="real", switches=switches
        )

    assert len(created_ids) == 1


# ---------------------------------------------------------------------------
# 测试 6：冷启动模拟——前两次 HTML，第三次 JSON，最终成功创建 Job。
# ---------------------------------------------------------------------------


def test_create_job_cold_start_then_success(monkeypatch):
    responses = [
        FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"}),
        FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"}),
        FakeResponse(200, json_data={"job_id": "job-42", "status": "queued", "reused": False}),
    ]
    fake_session = FakeSession(responses)
    monkeypatch.setattr(api_client, "_http_session", lambda: fake_session)

    result = api_client.create_job(**_job_kwargs())

    assert result["job_id"] == "job-42"
    assert result["created"] is True
    assert fake_session.calls == 3


# ---------------------------------------------------------------------------
# wait_for_api_ready：状态轮询，而不是一次性长阻塞。
# ---------------------------------------------------------------------------


def test_wait_for_api_ready_recovers_after_cold_start(monkeypatch):
    call_count = {"n": 0}

    def fake_get(*_a, **_k):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"})
        return FakeResponse(200, json_data={"status": "ok"})

    monkeypatch.setattr(api_client.requests, "get", fake_get)
    progress_events: list[dict] = []
    result = api_client.wait_for_api_ready(
        poll_timeout_seconds=5, max_wait_seconds=30, on_progress=progress_events.append
    )

    assert result["ready"] is True
    assert call_count["n"] == 3
    assert len(progress_events) == 3
    assert progress_events[0]["reason"] == "render_waking"


def test_wait_for_api_ready_gives_up_gracefully_after_budget(monkeypatch):
    monkeypatch.setattr(
        api_client.requests,
        "get",
        lambda *a, **k: FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"}),
    )
    result = api_client.wait_for_api_ready(poll_timeout_seconds=1, max_wait_seconds=1)

    assert result["ready"] is False
    assert result["reason"] == "render_waking"


# ---------------------------------------------------------------------------
# get_job 轮询路径同样不能因为占位页崩溃（进度条每 2 秒轮询一次，风险敞口更大）。
# ---------------------------------------------------------------------------


def test_get_job_html_falls_back_to_cache_without_raising(monkeypatch):
    good = FakeResponse(200, json_data={"job_id": "job-1", "status": "running"})
    placeholder = FakeResponse(200, text=RENDER_PLACEHOLDER_HTML, headers={"Content-Type": "text/html"})
    fake_session = FakeSession([good])
    monkeypatch.setattr(api_client, "_http_session", lambda: fake_session)

    api_client._JOB_STATUS_MEMO.clear()
    first = api_client.get_job("job-1")
    assert first["status"] == "running"

    # 让缓存过期，再制造一次占位页响应：不能抛异常，应退回上次已知状态。
    api_client._JOB_STATUS_MEMO["job-1"] = (0.0, first)
    fake_session._responses = [placeholder]
    fake_session.calls = 0
    second = api_client.get_job("job-1")
    assert second == first
