"""
app.ui.api_client —— 前端与本地 FastAPI 的通信 helper。

策略：优先通过 HTTP 调用本地 FastAPI（默认 http://localhost:8000，可用
FRONTEND_API_BASE_URL 覆盖）；当 API 不可达时，自动回退到**进程内**直接调用
pipeline / 读取产物，保证仅运行 `streamlit run` 也能完成 mock 演示。

安全：绝不在请求中携带 API Key；前端只与本地服务/本地进程交互。
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote

import requests
import streamlit as st

from app.core.logging import get_logger
from app.workflow.artifacts import resolve_artifact_base

_LOGGER = get_logger(__name__)

# 项目根与产物目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORTS_DIR = PROJECT_ROOT / "exports"
QUESTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "questions_125.json"

# 请求超时（秒）：普通短请求、Render 冷启动探测、上传和长运行分开配置。
# Render Free API 唤醒可能明显超过本地短请求时延，因此不能用 3 秒健康探测
# 作为上传前置门禁。


def _positive_env_int(name: str, default: int) -> int:
    """读取正整数环境变量；非法值安全回退，避免前端导入失败。"""
    try:
        return max(int(os.getenv(name, str(default)) or default), 1)
    except (TypeError, ValueError):
        return default


def _short_timeout_seconds() -> int:
    """普通 API 查询的超时；本地默认保持紧凑，部署时可显式覆盖。"""
    return _positive_env_int("FRONTEND_API_SHORT_TIMEOUT_SECONDS", 10)


def _wake_timeout_seconds() -> int:
    """允许托管 API 从休眠中唤醒的健康探测超时。"""
    value = max(_positive_env_int("FRONTEND_API_WAKE_TIMEOUT_SECONDS", 180), 10)
    if os.getenv("APP_ENV", "").strip().lower() == "preview":
        return max(value, 180)
    return value


def _ingest_timeout_seconds() -> int:
    """PDF 解析、远程嵌入和索引构建的 HTTP 读超时。"""
    return max(_positive_env_int("FRONTEND_INGEST_TIMEOUT_SECONDS", 900), 60)


# 上传批次的前端早期保护。LibraryManager 返回更严格的配额时，
# validate_upload_batch() 会优先使用服务端配额。
_SUPPORTED_LIBRARY_EXTENSIONS = {".pdf", ".txt", ".md", ".csv"}
_DEFAULT_UPLOAD_MAX_FILES = _positive_env_int("MAX_UPLOAD_FILES", 10)
_DEFAULT_UPLOAD_MAX_MB = _positive_env_int("MAX_UPLOAD_MB", 25)
_DEFAULT_UPLOAD_TOTAL_MB = _positive_env_int(
    "MAX_UPLOAD_TOTAL_MB", _DEFAULT_UPLOAD_MAX_FILES * _DEFAULT_UPLOAD_MAX_MB
)


def _exports_dir() -> Path:
    return resolve_artifact_base(EXPORTS_DIR)


def _run_timeout_seconds(mode: str = "mock", use_deep_research: bool = False) -> int:
    """
    返回 POST /runs 的 HTTP 读超时（秒）。

    Mock 默认 120s；Real 默认 900s；启用 DeepResearch 时至少 1200s。
    可通过 FRONTEND_RUN_TIMEOUT_SECONDS 覆盖。
    """
    override = os.getenv("FRONTEND_RUN_TIMEOUT_SECONDS", "").strip()
    if override.isdigit():
        return max(int(override), 60)
    if mode == "real":
        return 1200 if use_deep_research else 900
    return 120


def _coerce_run_payload(body: Any) -> dict:
    """把 FastAPI `{detail: RunResponse}` 或字符串 detail 收成前端可用的运行结果。"""
    if not isinstance(body, dict):
        text = str(body or "未知错误")
        return {"status": "failed", "errors": [text], "message": text}
    detail = body.get("detail")
    if isinstance(detail, dict):
        payload = dict(detail)
        if not payload.get("errors") and isinstance(detail.get("details"), dict):
            nested = detail.get("details") or {}
            if nested.get("errors"):
                payload["errors"] = list(nested["errors"])
        if not payload.get("errors") and detail.get("message"):
            payload["errors"] = [str(detail["message"])]
        if body.get("status") and not payload.get("status"):
            payload["status"] = body["status"]
        return payload
    if isinstance(detail, str) and not body.get("errors"):
        return {**body, "status": body.get("status", "failed"), "errors": [detail], "message": body.get("message") or detail}
    return body


def _prefer_inprocess_run() -> bool:
    """
    是否优先在 Streamlit 进程内直接跑 pipeline（默认 True，避免 HTTP 读超时）。

    仅当 FRONTEND_RUN_VIA_API=1 时才走 HTTP POST /runs（供 API 集成测试）。
    """
    return os.getenv("FRONTEND_RUN_VIA_API", "").strip().lower() not in ("1", "true", "yes")


def _api_only() -> bool:
    """Whether this UI is explicitly isolated from all in-process backend work."""
    return not _prefer_inprocess_run()


def api_base() -> str:
    """返回 API 基础 URL（可由 FRONTEND_API_BASE_URL 覆盖）。"""
    return os.getenv("FRONTEND_API_BASE_URL", "http://localhost:8000").rstrip("/")


@st.cache_resource(show_spinner=False)
def _http_session() -> requests.Session:
    """全进程共享的 HTTP 连接池（st.cache_resource）。

    避免每次页面交互都新建 TCP/TLS 连接；同一 Session 在多次 rerun 间
    复用底层连接，显著降低本地 API 往返延迟。
    """
    s = requests.Session()
    s.headers.update({"Connection": "keep-alive"})
    return s


# 只缓存成功的健康结果。失败（休眠、502、超时）不得锁住 60 秒，否则评委
# 点「开始生成」会继续看到「暂不可用」。
#
# 缓存必须按 api_base() 隔离（键 = 当前 FRONTEND_API_BASE_URL）：同一浏览器
# session 里如果目标地址发生变化（例如运维改了环境变量后重启 UI 进程，或者
# 单测里 monkeypatch 了 api_base），旧地址探测成功缓存的 payload 不能被当成
# 新地址已经就绪——否则会出现"配置已经改对了，但 UI 仍然认为服务未就绪/或
# 反过来误判为就绪"的诡异现象，且很难从现象直接联想到"缓存没有跟着地址切换"。
_HEALTH_CACHE_TTL_SECONDS = 60
_DIAG_CACHE_TTL_SECONDS = 60
_QUESTIONS_CACHE_TTL_SECONDS = 300
_HEALTH_OK_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _clear_health_ok_cache() -> None:
    _HEALTH_OK_CACHE.clear()


def _store_health_ok(payload: dict[str, Any]) -> None:
    _HEALTH_OK_CACHE[api_base()] = (time.monotonic(), payload)


def _peek_health_ok_cache() -> tuple[float, dict[str, Any]]:
    """读取当前 api_base() 对应的成功缓存；地址不匹配时视为无缓存。"""
    return _HEALTH_OK_CACHE.get(api_base(), (0.0, {}))


# ---------------------------------------------------------------------------
# 健康判定契约（单一事实来源）。
#
# 硬约束（对应线上截图复现的问题）：HTTP 200 + 合法 JSON dict 不等于"就绪"。
# 必须能识别出响应确实来自 sage125-api 本身（``service`` 字段），而不是任意
# 一个恰好返回 200 JSON 的其它服务/占位服务。反之，也不能因为
# ``rag_index_status == "empty"`` 或 ``storage.persistent == False`` 这类
# "业务子状态未达到最佳状态"就误判为"未就绪"——那些是任务前置条件层面的
# 判断（由 /preflight 负责），不属于"API 进程是否已经从休眠中启动完成"这一层。
# ---------------------------------------------------------------------------

EXPECTED_HEALTH_SERVICE = "sage125-api"


def evaluate_health_contract(
    payload: dict[str, Any] | None,
    *,
    connected: bool,
) -> dict[str, Any]:
    """把一次 /health 探测的（连接状态, 原始 JSON）翻译成结构化健康判定。

    返回字段：
        connected:            是否拿到了 HTTP 响应（不代表业务已就绪）。
        is_sage125:           响应是否可辨认地来自 sage125-api 本身。
        core_ready:           唤醒阶段的"就绪"定义——``connected and is_sage125``，
                               与 ``status`` 是 "ok" 还是 "degraded" 无关（进程已经
                               启动并能以 sage125-api 身份应答，剩下的依赖是否齐全
                               属于任务前置条件层，不影响"是否还在冷启动"这一层）。
        status:               原始 status 字段（"ok" / "degraded" / None）。
        dependencies:         原始 dependencies 子对象（job_store / artifact_* 等）。
        rag_index_status:     原始 rag_index_status（仅供展示，不参与 core_ready）。
        qwen_config_loaded:   原始 qwen_config_loaded（仅供展示，不参与 core_ready）。
        bailian_configured:   原始 bailian.configured（仅供展示，不参与 core_ready）。
        storage_persistent:   原始 storage.persistent（仅供展示，不参与 core_ready）。
        questions_count:      原始 questions_count（仅供展示）。
    """
    result: dict[str, Any] = {
        "connected": bool(connected),
        "is_sage125": False,
        "core_ready": False,
        "status": None,
        "dependencies": {},
        "rag_index_status": None,
        "qwen_config_loaded": None,
        "bailian_configured": None,
        "storage_persistent": None,
        "questions_count": None,
    }
    if not connected or not isinstance(payload, dict) or not payload:
        return result
    status_value = payload.get("status")
    result["status"] = status_value if isinstance(status_value, str) else None
    result["is_sage125"] = (
        payload.get("service") == EXPECTED_HEALTH_SERVICE and result["status"] is not None
    )
    result["core_ready"] = result["is_sage125"]
    deps = payload.get("dependencies")
    if isinstance(deps, dict):
        result["dependencies"] = deps
    rag = payload.get("rag_index_status")
    if isinstance(rag, str):
        result["rag_index_status"] = rag
    qwen_loaded = payload.get("qwen_config_loaded")
    if isinstance(qwen_loaded, bool):
        result["qwen_config_loaded"] = qwen_loaded
    bailian = payload.get("bailian")
    if isinstance(bailian, dict) and isinstance(bailian.get("configured"), bool):
        result["bailian_configured"] = bailian["configured"]
    storage = payload.get("storage")
    if isinstance(storage, dict) and isinstance(storage.get("persistent"), bool):
        result["storage_persistent"] = storage["persistent"]
    qcount = payload.get("questions_count")
    if isinstance(qcount, int):
        result["questions_count"] = qcount
    return result


# Render Free 实例冷启动期间，边缘节点可能先用 HTTP 200 返回自己的静态占位页
# （不是我们的业务 JSON），例如 "Application loading" / "Service waking up" /
# "Starting the instance"。HTTP 状态码成功 ≠ 业务成功，必须先识别出这种占位页，
# 否则调用方会把"连上了"误判成"可以用了"，进而对占位页 body 做 response.json()
# 崩溃，或者把假阳性的"已连接"当成"已就绪"。
_RENDER_PLACEHOLDER_MARKERS = (
    "Application loading",
    "Service waking up",
    "Starting the instance",
    "Allocating compute resources",
    "Preparing instance for initialization",
)


def _looks_like_render_placeholder(text: str) -> bool:
    """识别 Render 平台级冷启动占位页；与我们的业务响应无关。"""
    if not text:
        return False
    return any(marker in text for marker in _RENDER_PLACEHOLDER_MARKERS)


def parse_json_response(response: requests.Response) -> tuple[dict[str, Any] | None, str | None]:
    """安全解析 HTTP 响应为业务 JSON；HTTP 状态码成功不等于业务成功。

    返回 ``(data, reason)``：
        - 解析成功且是 dict：``(data, None)``。
        - HTTP 状态成功但 body 是 Render 冷启动占位页（非 JSON）：``(None, "render_waking")``。
        - HTTP 状态成功但 body 既不是占位页也不是合法 JSON：``(None, "invalid_json")``。

    ``create_job`` / ``retry_job`` / ``get_job`` / ``_probe_health`` 等都必须调用
    这一个函数解析响应，不要各自重复 ``response.json()``。
    """
    try:
        data = response.json()
    except ValueError:
        try:
            body_text = response.text or ""
        except Exception:  # noqa: BLE001 - response.text 本身也可能异常，不能因此崩溃
            body_text = ""
        if _looks_like_render_placeholder(body_text):
            return None, "render_waking"
        return None, "invalid_json"
    if not isinstance(data, dict):
        return None, "invalid_json"
    return data, None


_PROBE_ID_HEADER = "X-SAGE125-Probe-ID"
_PROBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")
_PROBE_COUNTER = {"n": 0}


def new_probe_id(prefix: str = "wake") -> str:
    """生成一个用于前后端日志关联的探测 ID；字符集/长度受限，安全可放进 HTTP 头。"""
    _PROBE_COUNTER["n"] += 1
    safe_prefix = re.sub(r"[^A-Za-z0-9_\-]", "-", str(prefix))[:20] or "probe"
    raw = f"{safe_prefix}-{int(time.time())}-{os.getpid()}-{_PROBE_COUNTER['n']}"
    return raw[:80]


def _classify_transport_exception(exc: Exception) -> str:
    """把 requests 抛出的异常分类成有限的几种，供 UI 展示错误分类而不是笼统的"不可用"。"""
    if isinstance(exc, requests.exceptions.SSLError):
        return "tls_error"
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return "connect_timeout"
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return "read_timeout"
    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection_error"
    return "request_exception"


def _classify_http_status(status_code: int) -> str:
    if status_code in (401, 403):
        return "auth_error"
    if status_code == 404:
        return "not_found"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code < 600:
        return "server_error"
    return f"http_error_{status_code}"


def probe_health_detailed(
    *, timeout: int | None = None, probe_id: str | None = None
) -> dict[str, Any]:
    """探测 /health 并返回完整结构化结果；是 ``_probe_health`` / ``probe_api_wake_state``
    共用的唯一实现，也是本模块对外暴露的"健康判定单一事实来源"。

    返回字段（超集，向后兼容旧的 ``connected``/``ready``/``reason``）：
        connected, ready(=core_ready), reason,
        http_status, response_kind, exception_type,
        target_url, probe_id, duration_ms,
        以及 ``evaluate_health_contract`` 的全部展示字段
        （status / dependencies / rag_index_status / qwen_config_loaded /
        bailian_configured / storage_persistent / questions_count）。

    ``probe_id`` 会通过 ``X-SAGE125-Probe-ID`` 请求头带给服务端；服务端按长度
    /字符白名单校验后原样记录进日志，方便把某一次前端探测与服务端日志对上号。
    失败（连不上/超时/HTTP 非 200/非法 JSON）不写入成功缓存。
    """
    started = time.monotonic()
    url = f"{api_base()}/health"
    pid = probe_id or new_probe_id()
    headers = {"User-Agent": "SAGE125-UI-HealthProbe"}
    if _PROBE_ID_PATTERN.match(pid):
        headers[_PROBE_ID_HEADER] = pid
    base_result: dict[str, Any] = {
        "probe_id": pid,
        "target_url": url,
        "http_status": None,
        "response_kind": None,
        "exception_type": None,
    }

    def _finish(**extra: Any) -> dict[str, Any]:
        base_result["duration_ms"] = round((time.monotonic() - started) * 1000, 1)
        base_result.update(extra)
        return base_result

    try:
        r = requests.get(
            url,
            timeout=_wake_timeout_seconds() if timeout is None else timeout,
            headers=headers,
        )
    except requests.RequestException as exc:
        exc_type = _classify_transport_exception(exc)
        contract = evaluate_health_contract(None, connected=False)
        return _finish(
            exception_type=exc_type,
            reason=exc_type,
            **contract,
        )

    base_result["http_status"] = r.status_code
    if r.status_code != 200:
        contract = evaluate_health_contract(None, connected=False)
        return _finish(
            response_kind=_classify_http_status(r.status_code),
            reason=_classify_http_status(r.status_code),
            **contract,
        )

    payload, parse_reason = parse_json_response(r)
    if payload is None:
        _LOGGER.info(
            "sage125-api health probe not ready: probe_id=%s endpoint=%s status_code=%s "
            "content_type=%s ready=%s reason=%s",
            pid,
            "/health",
            r.status_code,
            str(r.headers.get("Content-Type", "")),
            False,
            parse_reason,
        )
        contract = evaluate_health_contract(None, connected=True)
        return _finish(response_kind=parse_reason or "invalid_json", reason=parse_reason, **contract)

    contract = evaluate_health_contract(payload, connected=True)
    if contract["core_ready"]:
        _store_health_ok(payload)
        return _finish(response_kind="json", reason=None, **contract)
    # 连上了、也是合法 JSON，但认不出是 sage125-api（陌生/占位服务）：不算就绪，
    # 也绝不能写入成功缓存，否则会把别的服务误判成"我们的 API 已经就绪"。
    _LOGGER.info(
        "sage125-api health probe connected but payload is not recognizable as %s: "
        "probe_id=%s service=%r status=%r",
        EXPECTED_HEALTH_SERVICE,
        pid,
        payload.get("service"),
        payload.get("status"),
    )
    return _finish(response_kind="not_sage125", reason="not_sage125", **contract)


def _probe_health(*, timeout: int | None = None) -> tuple[bool, bool, dict]:
    """向后兼容的三元组包装；新代码请直接用 ``probe_health_detailed``。

    返回 ``(connected, ready, payload)``：
        - ``connected``：拿到了 HTTP 响应（不代表业务已就绪；Render 冷启动占位页
          同样会让 ``connected=True``）。
        - ``ready``：响应可辨认地来自 sage125-api 本身，才代表 API 真正可用
          （不再是"任意 200 JSON dict 即算就绪"——那会把陌生服务/占位服务误判
          成我们的 API）。
    """
    detailed = probe_health_detailed(timeout=timeout)
    connected = bool(detailed.get("connected"))
    ready = bool(detailed.get("core_ready"))
    payload = _HEALTH_OK_CACHE.get(api_base(), (0.0, {}))[1] if ready else {}
    return connected, ready, payload


def probe_api_wake_state(*, timeout: int | None = None, probe_id: str | None = None) -> dict[str, Any]:
    """结构化唤醒状态，供 UI 轮询展示；不写健康缓存之外的副作用。

    返回形如
    ``{"connected": bool, "ready": bool, "reason": str | None, ...}``（超集，
    额外字段见 :func:`probe_health_detailed`），向后兼容旧调用方只读
    ``connected``/``ready``/``reason`` 三个键的用法。
    """
    detailed = probe_health_detailed(timeout=timeout, probe_id=probe_id)
    connected = bool(detailed.get("connected"))
    ready = bool(detailed.get("core_ready"))
    reason = detailed.get("reason")
    if not connected and not reason:
        reason = "network_unreachable"
    elif connected and not ready and not reason:
        reason = "render_waking"
    result = dict(detailed)
    result["connected"] = connected
    result["ready"] = ready
    result["reason"] = reason
    return result


def _fetch_health_cached(_cache_bust: int = 0) -> tuple[bool, dict]:
    """复用最近一次成功的健康检查；页面探测用短超时，失败不缓存。

    返回 ``(ready, payload)``：只有业务真正就绪（可辨认地来自 sage125-api 本身）
    才算 ``ready=True``——历史上这里叫 ``connected``，但语义一直是"能不能用"，
    现在用更准确的名字对齐 ``_probe_health`` 的 connected/ready 拆分。

    缓存严格按当前 ``api_base()`` 隔离，见 ``_peek_health_ok_cache``。
    """
    del _cache_bust
    cached_at, cached_payload = _peek_health_ok_cache()
    now = time.monotonic()
    if cached_at and now - cached_at < _HEALTH_CACHE_TTL_SECONDS and cached_payload:
        return True, cached_payload
    _connected, ready, payload = _probe_health(timeout=_short_timeout_seconds())
    return ready, payload


_fetch_health_cached.clear = _clear_health_ok_cache  # type: ignore[attr-defined]


def api_available() -> bool:
    """探测 API 是否已就绪可用（只复用成功的健康缓存；Render 冷启动占位页不算就绪）。"""
    ready, _ = _fetch_health_cached(0)
    return ready


def refresh_api_available() -> bool:
    """作废成功缓存后再用唤醒超时探测一次；返回业务是否真正就绪。"""
    _clear_health_ok_cache()
    _connected, ready, _payload = _probe_health()
    return ready


def wake_hosted_api(*, wait: bool = False) -> bool:
    """打开页面时轻量戳醒托管 API；wait=True 时允许完整冷启动等待。返回是否已就绪。"""
    timeout = _wake_timeout_seconds() if wait else min(3, _short_timeout_seconds())
    _connected, ready, _payload = _probe_health(timeout=timeout)
    return ready


def _cold_start_budget_seconds() -> int:
    """"正在唤醒 API"整体轮询预算；覆盖 Render Free 实例实测的 2-4 分钟冷启动。

    这不是单次 HTTP 请求超时（那是 ``_wake_timeout_seconds``），而是"允许连续
    短超时轮询多久"的总预算；不要靠无限拉长单次请求超时来覆盖冷启动。

    默认 360 秒（覆盖实测冷启动上限，超过仍未 ready 才提示"启动超时"）。
    """
    default = 360
    value = _positive_env_int("FRONTEND_API_COLD_START_BUDGET_SECONDS", default)
    if os.getenv("APP_ENV", "").strip().lower() == "preview":
        return max(value, default)
    return value


# ---------------------------------------------------------------------------
# 正在唤醒 sage125-api：时间同步进度曲线。
#
# 这里展示的"进度"不是 Render 内部真实启动百分比（我们无法知道 Render 真实
# 启动阶段），而是"按历史冷启动耗时估算的等待完成度"。硬约束：
#   - progress == 100 与 API_READY == True 严格等价，ready 之前永远 < 100；
#   - 禁止线性 elapsed/expected*100（会前 30 秒冲到 80%-90%，然后长时间停在
#     99% 等 ready，体验很差）；
#   - 未 ready 时最高只能到 95%，不会长时间"卡在 99%"。
# ---------------------------------------------------------------------------

_DEFAULT_EXPECTED_WAKE_SECONDS = 180.0
_MIN_EXPECTED_WAKE_SECONDS = 90.0
_MAX_EXPECTED_WAKE_SECONDS = 300.0
_WAKE_PROGRESS_CAP_BEFORE_READY = 95.0
_LAST_WAKE_SECONDS_SESSION_KEY = "_sage125_last_wake_seconds"


def _record_last_wake_seconds(elapsed_seconds: float) -> None:
    """记录本次成功唤醒耗时（当前浏览器 session 内），供下次估算预计等待时间。"""
    try:
        if elapsed_seconds and float(elapsed_seconds) > 0:
            st.session_state[_LAST_WAKE_SECONDS_SESSION_KEY] = float(elapsed_seconds)
    except Exception:  # noqa: BLE001 - 没有 ScriptRunContext 时静默跳过，不影响主流程
        pass


def last_wake_seconds() -> float | None:
    """读取最近一次成功唤醒耗时（当前 session 内）；无历史返回 None。"""
    try:
        value = st.session_state.get(_LAST_WAKE_SECONDS_SESSION_KEY)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def resolve_expected_wake_seconds(last_seconds: float | None = None) -> float:
    """按最近一次成功唤醒耗时估算本次预计等待时间（秒）。

    ``expected = 0.5 * 180 + 0.5 * last_wake_seconds``，限制在 ``[90, 300]``
    秒；``last_seconds`` 未传入时读取当前 session 历史，无历史则用默认 180 秒。
    """
    if last_seconds is None:
        last_seconds = last_wake_seconds()
    if last_seconds is None or last_seconds <= 0:
        return _DEFAULT_EXPECTED_WAKE_SECONDS
    estimated = 0.5 * _DEFAULT_EXPECTED_WAKE_SECONDS + 0.5 * float(last_seconds)
    return min(max(estimated, _MIN_EXPECTED_WAKE_SECONDS), _MAX_EXPECTED_WAKE_SECONDS)


def compute_wake_progress_percent(
    elapsed_seconds: float, expected_seconds: float, *, ready: bool
) -> float:
    """把"已等待时间"映射成"预计等待完成度"（0-100）；不是 Render 真实启动百分比。

    - ``ready=True``：严格返回 ``100.0``（唯一能到 100 的入口）。
    - ``ready=False``：无论等多久都不能到 100，最高封顶
      ``_WAKE_PROGRESS_CAP_BEFORE_READY``（95），不会长时间停在 99%。
    - 三段时间匹配型曲线，形状按 ``expected_seconds=180`` 秒校准，随
      ``expected_seconds`` 等比缩放：
        阶段一 ``[0, expected/3]``：             0%  → 45%，线性；
        阶段二 ``(expected/3, expected*5/6]``：  45% → 80%，减速曲线（0.8 次幂）；
        阶段三 ``(expected*5/6, +inf)``：         80% → 95%，指数衰减，
          永远逼近但摸不到 95%（由 ``min(..., 95)`` 再兜底一层硬上限）。
    """
    if ready:
        return 100.0
    elapsed = max(float(elapsed_seconds), 0.0)
    expected = max(float(expected_seconds), 1.0)
    if elapsed <= 0:
        return 0.0

    t1 = expected / 3.0  # expected=180 时 = 60s
    t2 = expected * 5.0 / 6.0  # expected=180 时 = 150s
    tau = expected * 2.0 / 3.0  # expected=180 时 = 120s

    if elapsed <= t1:
        progress = 45.0 * elapsed / t1
    elif elapsed <= t2:
        frac = (elapsed - t1) / max(t2 - t1, 1e-6)
        progress = 45.0 + 35.0 * (frac**0.8)
    else:
        progress = 80.0 + 15.0 * (1.0 - math.exp(-(elapsed - t2) / max(tau, 1e-6)))

    return min(progress, _WAKE_PROGRESS_CAP_BEFORE_READY)


def format_wake_elapsed_label(seconds: float) -> str:
    """``MM:SS`` 格式，用于"已等待/预计总耗时/预计剩余"展示。"""
    total = max(int(round(float(seconds))), 0)
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def wake_progress_snapshot(
    elapsed_seconds: float, expected_seconds: float, *, ready: bool
) -> dict[str, Any]:
    """汇总一次探测后 UI 需要展示的全部字段（进度/已等待/预计总耗时/预计剩余/是否超期）。"""
    elapsed = max(float(elapsed_seconds), 0.0)
    expected = max(float(expected_seconds), 1.0)
    percent = compute_wake_progress_percent(elapsed, expected, ready=ready)
    overdue = elapsed > expected
    remaining = max(expected - elapsed, 0.0)
    return {
        "percent": percent,
        "elapsed_seconds": elapsed,
        "expected_seconds": expected,
        "remaining_seconds": remaining,
        "overdue": overdue,
        "ready": ready,
        "elapsed_label": format_wake_elapsed_label(elapsed),
        "expected_label": format_wake_elapsed_label(expected),
        "remaining_label": format_wake_elapsed_label(remaining),
    }


def wait_for_api_ready(
    *,
    poll_timeout_seconds: int = 20,
    max_wait_seconds: int | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """轮询 /health 直到业务就绪或预算耗尽；用多次短超时轮询代替一次超长阻塞。

    每次探测使用较短超时（默认 20s），探测之间短暂休眠；即使某一次探测正好
    命中 Render 的冷启动占位页，下一次探测也能很快重试，不必等到单个请求超时
    才有机会重新连接。

    这是一个**带预算上限**的通用轮询原语，保留给需要"允许放弃"语义的调用方
    （以及既有单元测试）。生产环境里"点击开始生成"触发的唤醒等待，出于产品
    要求（SAGE125-API-WAKE-PROGRESS-TIME-SYNC-FINAL-PR-DEPLOY-01：唤醒阶段
    不允许出现超时失败状态），改用下面完全没有预算上限的
    :func:`wait_for_api_ready_indefinitely`，不再调用这个带预算版本。

    参数：
        poll_timeout_seconds: 每次 /health 探测的超时。
        max_wait_seconds:     总预算；默认取 ``_cold_start_budget_seconds()``。
        on_progress:          每次探测后调用一次，传入
            ``{"attempt": int, "elapsed_seconds": float, "connected": bool,
              "ready": bool, "reason": str | None}``，供 UI 展示检查次数/等待时长。

    返回：
        ``{"ready": bool, "attempts": int, "elapsed_seconds": float, "reason": str | None}``。
    """
    budget = max(
        max_wait_seconds if max_wait_seconds is not None else _cold_start_budget_seconds(),
        poll_timeout_seconds,
    )
    start = time.monotonic()
    attempt = 0
    last_reason: str | None = None
    while True:
        attempt += 1
        remaining = budget - (time.monotonic() - start)
        if remaining <= 0:
            break
        this_timeout = max(1, int(min(poll_timeout_seconds, remaining)))
        state = probe_api_wake_state(timeout=this_timeout)
        last_reason = state.get("reason")
        if on_progress:
            on_progress({
                "attempt": attempt,
                "elapsed_seconds": round(time.monotonic() - start, 1),
                **state,
            })
        if state.get("ready"):
            return {
                "ready": True,
                "attempts": attempt,
                "elapsed_seconds": round(time.monotonic() - start, 1),
                "reason": None,
            }
        remaining = budget - (time.monotonic() - start)
        if remaining <= 0:
            break
        time.sleep(min(3.0, max(0.5, remaining)))
    return {
        "ready": False,
        "attempts": attempt,
        "elapsed_seconds": round(time.monotonic() - start, 1),
        "reason": last_reason,
    }


def wait_for_api_ready_indefinitely(
    *,
    poll_timeout_seconds: int = 20,
    poll_interval_seconds: float = 3.0,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """持续轮询 /health 直到业务真正 ready；**没有任何超时/预算上限**。

    产品要求（SAGE125-API-WAKE-PROGRESS-TIME-SYNC-FINAL-PR-DEPLOY-01 最终版）：
    用户点击「开始生成」以后，API 唤醒阶段绝不允许出现"超时失败"状态——不管
    实际等了 5 分钟、10 分钟还是 30 分钟，只要 /health 还没有返回真实 JSON 且
    ``ready=True``，就必须继续等待、继续在 UI 上更新唤醒进度/已等待时间/当前
    状态，不能提示失败、不能要求用户重新点击、不能结束当前流程。

    与 :func:`wait_for_api_ready` 的关键区别：这里**没有** ``max_wait_seconds``
    / 预算的概念——函数体内不存在任何 timeout/budget 判断，因此调用方也不需要
    处理"未 ready"的返回分支：本函数只会在真正 ready 后返回一次，正常情况下
    不会以 ``ready=False`` 结束（唯一的退出方式是探测过程中抛出未被
    ``probe_api_wake_state`` 内部吞掉的异常，交由调用方最外层的 try/except
    兜底，这属于"未预料异常"而不是"唤醒超时"）。

    参数：
        poll_timeout_seconds:  每次 /health 探测的超时（探测本身不能无限阻塞）。
        poll_interval_seconds: 两次探测之间的休眠时间。
        on_progress:           每次探测后调用一次，传入
            ``{"attempt": int, "elapsed_seconds": float, "connected": bool,
              "ready": bool, "reason": str | None}``。

    返回：
        ``{"ready": True, "attempts": int, "elapsed_seconds": float, "reason": None}``。
    """
    start = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        state = probe_api_wake_state(timeout=poll_timeout_seconds)
        if on_progress:
            on_progress({
                "attempt": attempt,
                "elapsed_seconds": round(time.monotonic() - start, 1),
                **state,
            })
        if state.get("ready"):
            return {
                "ready": True,
                "attempts": attempt,
                "elapsed_seconds": round(time.monotonic() - start, 1),
                "reason": None,
            }
        time.sleep(max(0.1, poll_interval_seconds))


# ---- 各接口：HTTP 优先，失败回退进程内 ----

def get_health() -> dict:
    """获取健康状态（HTTP 优先并短 TTL 缓存，首次加载允许托管 API 唤醒）。"""
    connected, payload = _fetch_health_cached(0)
    if connected and payload:
        return payload
    if _api_only():
        return {
            "status": "unavailable",
            "service": "sage125-api",
            "bailian": {"configured": False, "status": "unavailable"},
            "storage": {"mode": "unavailable", "persistent": False},
            "qwen_config_loaded": False,
            "deep_research_config_loaded": False,
            "openalex_config_loaded": False,
            "rag_index_status": "unavailable",
            "questions_count": 0,
            "models": {},
        }
    # 回退：进程内直接读取 settings。
    from app.api.routes import health as _health

    return _health()


@st.cache_data(ttl=_DIAG_CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_diagnostics_cached(_cache_bust: int) -> dict | None:
    try:
        r = _http_session().get(f"{api_base()}/diagnostics", timeout=_short_timeout_seconds())
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def get_diagnostics() -> dict:
    """获取系统诊断（HTTP 优先并短 TTL 缓存，回退进程内）。"""
    cached = _fetch_diagnostics_cached(0)
    if cached is not None:
        return cached
    if _api_only():
        return {
            "status": "error",
            "api_connected": False,
            "qwen": {"configured": False},
            "deepresearch": {"configured": False},
            "openalex": {"configured": False},
            "warnings": [],
            "errors": ["sage125-api 暂不可用。"],
        }
    # 回退：进程内调用诊断逻辑。
    from app.api.routes import diagnostics as _diag

    return _diag()


def get_runs(limit: int = 20) -> list[dict]:
    """获取最近运行列表（HTTP 优先，复用连接池，回退进程内 run_browser）。"""
    try:
        r = _http_session().get(
            f"{api_base()}/runs",
            params={"limit": limit},
            timeout=_short_timeout_seconds(),
        )
        if r.status_code == 200:
            return r.json().get("runs", [])
    except requests.RequestException:
        pass
    if _api_only():
        return []
    from app.ui.run_browser import list_runs

    return list_runs(limit=limit)


def _questions_file_fingerprint() -> float:
    """官方 Catalog 的 mtime；digest/path 变化后自动失效缓存。"""
    try:
        from app.catalog.official import official_catalog_path

        path = official_catalog_path()
        return path.stat().st_mtime
    except OSError:
        try:
            return QUESTIONS_PATH.stat().st_mtime
        except OSError:
            return 0.0


@st.cache_data(ttl=_QUESTIONS_CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_questions_cached(_fingerprint: float) -> dict | None:
    try:
        r = _http_session().get(f"{api_base()}/questions", timeout=_short_timeout_seconds())
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def get_questions() -> dict:
    """获取 125 问题清单（HTTP 优先并缓存，回退读取本地文件）。

    缓存键包含 `questions_125.json` 的 mtime：manifest 更新后自动失效，
    不依赖固定 TTL 也能拿到新数据；不必每次 rerun 都重新遍历/请求。
    """
    cached = _fetch_questions_cached(_questions_file_fingerprint())
    if cached is not None and cached.get("status") == "ok" and cached.get("questions"):
        return cached
    try:
        from app.catalog.official import load_official_catalog
        from app.catalog.query import questions_as_api_items

        catalog = load_official_catalog()
        items = questions_as_api_items(catalog)
        return {
            "status": "ok",
            "count": len(items),
            "catalog_source": "official",
            "catalog_digest": catalog.get_catalog_digest(),
            "questions": items,
        }
    except Exception as exc:
        if _api_only():
            return {
                "status": "failed",
                "message": "官方题目目录加载失败",
                "error": type(exc).__name__,
                "questions": None,
            }
        if not QUESTIONS_PATH.exists():
            return {"status": "failed", "message": "官方题目目录加载失败", "questions": None}
        raise


def _as_dict(value: Any) -> dict:
    """将 LibraryManager/API 返回值安全转成 dict。"""
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dict(dumped) if isinstance(dumped, dict) else {}
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


# UI 的最后一道脱敏防线：兼容第三方 SDK 常见的 Header、Bearer 与 URL
# 查询参数格式。嵌入错误会先被归类成固定中文指引；这些表达式只用于无法
# 归类的本地文献库错误，避免把认证信息原样展示给用户。
_BEARER_SECRET_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{6,}", re.IGNORECASE)
_NAMED_SECRET_PATTERN = re.compile(
    r"\b(api[_ -]?key|authorization|access[_ -]?token|token|secret|password)"
    r"(\s*[:=]\s*)(?:Bearer\s+)?[^\s,;\]}\)]+",
    re.IGNORECASE,
)
_QUERY_SECRET_PATTERN = re.compile(
    r"([?&](?:api[_-]?key|access[_-]?token|token|secret|signature)=)[^&#\s]+",
    re.IGNORECASE,
)


def _safe_library_error_text(value: Any) -> str:
    """脱敏无法归类的文献库错误；不记录也不返回原始凭据。"""
    from app.ui.errors import mask_sensitive_text

    safe = mask_sensitive_text(str(value or ""))
    safe = _BEARER_SECRET_PATTERN.sub("Bearer ****MASKED", safe)
    safe = _NAMED_SECRET_PATTERN.sub(r"\1\2****MASKED", safe)
    safe = _QUERY_SECRET_PATTERN.sub(r"\1****MASKED", safe)
    return safe.strip()


def _collect_library_error_values(target: list[Any], value: Any) -> None:
    """从 API/LibraryManager 的多种错误结构中提取待展示值。"""
    if value is None or value == "":
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_library_error_values(target, item)
        return
    if isinstance(value, dict):
        for key in ("error", "message", "reason", "detail"):
            if value.get(key):
                _collect_library_error_values(target, value[key])
                return
        target.append("文献索引失败：服务返回了无法识别的错误格式。")
        return
    target.append(value)


def format_library_errors(payload: Any) -> list[str]:
    """
    将文献索引错误转换为可行动且不泄密的中文提示。

    ``EmbeddingError`` 的稳定错误码及旧版 SDK 异常文本都会被识别；原始
    网络响应、URL、Header 和 Key 不会进入面向用户的提示。
    """
    from app.clients.embedding_client import (
        classify_embedding_error_text,
        embedding_error_guidance,
    )

    result = _as_dict(payload)
    raw_messages: list[Any] = []
    for field in ("errors", "rejected"):
        _collect_library_error_values(raw_messages, result.get(field))
    if not raw_messages:
        _collect_library_error_values(raw_messages, result.get("message"))

    user_messages: list[str] = []
    for raw_value in raw_messages:
        code = classify_embedding_error_text(str(raw_value or ""))
        message = (
            embedding_error_guidance(code)
            if code is not None
            else _safe_library_error_text(raw_value)
        )
        if message and message not in user_messages:
            user_messages.append(message)
    return user_messages or [
        "文献索引失败，原文件未丢失。请稍后重试；若持续失败，请运行 "
        "`py -3 scripts/smoke_bailian.py --embedding`。"
    ]


def _first_int(*values: Any) -> int | None:
    """返回第一个可转换为非负整数的值。"""
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def _new_library_manager():
    """
    延迟创建本地文献库服务。

    新实现的规范类名为 ``LibraryManager``；为兼容开发中命名，也接受
    ``LibraryService``。故意不回退到手工落盘 + IndexingService，避免绕过配额、
    删除和题源隔离策略。
    """
    try:
        from app.rag import library_manager as manager_module
    except ImportError as exc:
        raise RuntimeError("本地文献库服务尚未安装（缺少 app.rag.library_manager）。") from exc
    manager_cls = getattr(manager_module, "LibraryManager", None) or getattr(
        manager_module, "LibraryService", None
    )
    if manager_cls is None:
        raise RuntimeError("本地文献库服务缺少 LibraryManager/LibraryService。")
    return manager_cls()


def _call_library_method(manager: Any, names: tuple[str, ...], *args: Any) -> Any:
    """以规范方法名为主，兼容开发中的少量别名。"""
    for name in names:
        method = getattr(manager, name, None)
        if callable(method):
            return method(*args)
        if method is not None and not args:
            return method
    raise RuntimeError(f"本地文献库服务缺少方法：{' / '.join(names)}")


def _normalize_library_status(payload: Any) -> dict:
    """
    将 HTTP/LibraryManager 的状态统一为前端稳定结构。

    核心实现可返回 ``usage/quota/documents``，也兼容早期的顶层字段命名。
    """
    raw = _as_dict(payload)
    documents_raw = raw.get("documents") or raw.get("files") or []
    documents: list[dict] = []
    for value in documents_raw if isinstance(documents_raw, list) else []:
        item = _as_dict(value)
        document_id = item.get("document_id") or item.get("id") or item.get("doc_id")
        documents.append(
            {
                **item,
                "document_id": str(document_id or ""),
                "name": str(item.get("name") or item.get("filename") or item.get("source_name") or "未命名文献"),
                "size_bytes": _first_int(item.get("size_bytes"), item.get("bytes"), item.get("file_size")) or 0,
                "chunk_count": _first_int(item.get("chunk_count"), item.get("chunks")) or 0,
                "created_at": item.get("created_at") or item.get("uploaded_at") or "",
            }
        )

    usage_raw = _as_dict(raw.get("usage"))
    quota_raw = _as_dict(raw.get("quota") or raw.get("limits"))
    used_documents = _first_int(
        usage_raw.get("document_count"), usage_raw.get("file_count"), usage_raw.get("documents"),
        raw.get("document_count"), len(documents)
    )
    used_bytes = _first_int(
        usage_raw.get("total_bytes"), usage_raw.get("used_bytes"), raw.get("total_bytes"), raw.get("used_bytes")
    )
    max_documents = _first_int(
        quota_raw.get("max_documents"), quota_raw.get("max_files"), raw.get("max_documents"), raw.get("max_files")
    )
    max_raw_bytes = _first_int(quota_raw.get("max_raw_bytes"), raw.get("max_raw_bytes"))
    max_index_bytes = _first_int(quota_raw.get("max_index_bytes"), raw.get("max_index_bytes"))
    max_total_bytes = _first_int(
        quota_raw.get("max_total_bytes"), quota_raw.get("total_bytes"), raw.get("max_total_bytes")
    )
    if max_total_bytes is None and max_raw_bytes is not None and max_index_bytes is not None:
        max_total_bytes = max_raw_bytes + max_index_bytes
    max_files_per_upload = _first_int(
        quota_raw.get("max_files_per_upload"), quota_raw.get("max_batch_files"), raw.get("max_files_per_upload")
    )
    max_batch_bytes = _first_int(
        quota_raw.get("max_batch_bytes"), quota_raw.get("max_upload_bytes"), raw.get("max_batch_bytes")
    )
    max_file_bytes = _first_int(quota_raw.get("max_file_bytes"), raw.get("max_file_bytes"))
    policy = _as_dict(raw.get("policy"))

    return {
        **raw,
        "status": str(raw.get("status") or "ok"),
        "documents": documents,
        "usage": {
            **usage_raw,
            "document_count": used_documents or 0,
            "total_bytes": used_bytes or 0,
        },
        "quota": {
            **quota_raw,
            "max_documents": max_documents,
            "max_total_bytes": max_total_bytes,
            "max_raw_bytes": max_raw_bytes,
            "max_index_bytes": max_index_bytes,
            "max_files_per_upload": max_files_per_upload,
            "max_batch_bytes": max_batch_bytes,
            "max_file_bytes": max_file_bytes,
        },
        "policy": {
            **policy,
            "question_source_excluded": bool(
                policy.get("question_source_excluded", raw.get("question_source_excluded", False))
            ),
        },
    }


def get_library_status() -> dict:
    """读取本地文献库配额与文档清单（HTTP 优先，进程内回退）。"""
    try:
        response = requests.get(
            f"{api_base()}/library/status", timeout=_short_timeout_seconds()
        )
        if response.status_code == 200:
            return _normalize_library_status(response.json())
    except (requests.RequestException, ValueError):
        pass

    if _api_only():
        return _normalize_library_status(
            {
                "status": "unavailable",
                "message": "sage125-api 暂不可用。",
                "documents": [],
                "usage": {"document_count": 0, "total_bytes": 0},
                "quota": {},
            }
        )

    try:
        manager = _new_library_manager()
        payload = _call_library_method(manager, ("get_status", "status", "library_status"))
        return _normalize_library_status(payload)
    except Exception as exc:  # noqa: BLE001 - 前端须降级为可读状态
        return _normalize_library_status(
            {
                "status": "unavailable",
                "message": str(exc),
                "documents": [],
                "usage": {"document_count": 0, "total_bytes": 0},
                "quota": {},
            }
        )


def validate_upload_batch(files: list[tuple[str, bytes]], library_status: Optional[dict] = None) -> dict:
    """
    在网络请求/落盘之前检查文件数、总字节、单文件与文献库剩余配额。
    """
    status = _normalize_library_status(library_status or {})
    usage = status.get("usage") or {}
    quota = status.get("quota") or {}
    file_count = len(files)
    total_bytes = sum(len(content) for _name, content in files)
    max_files_value = _first_int(quota.get("max_files_per_upload"))
    max_batch_value = _first_int(quota.get("max_batch_bytes"))
    max_file_value = _first_int(quota.get("max_file_bytes"))
    max_files = _DEFAULT_UPLOAD_MAX_FILES if max_files_value is None else max_files_value
    max_batch_bytes = (_DEFAULT_UPLOAD_TOTAL_MB * 1024 * 1024) if max_batch_value is None else max_batch_value
    max_file_bytes = (_DEFAULT_UPLOAD_MAX_MB * 1024 * 1024) if max_file_value is None else max_file_value
    max_documents = _first_int(quota.get("max_documents"))
    max_total_bytes = _first_int(quota.get("max_raw_bytes"), quota.get("max_total_bytes"))
    used_documents = _first_int(usage.get("document_count")) or 0
    used_bytes = _first_int(usage.get("raw_bytes"), usage.get("total_bytes")) or 0

    validation_errors: list[str] = []
    if file_count == 0:
        validation_errors.append("请先选择文件。")
    if file_count > max_files:
        validation_errors.append(f"单次最多上传 {max_files} 个文件，当前为 {file_count} 个。")
    if total_bytes > max_batch_bytes:
        validation_errors.append(f"本批文件总计 {total_bytes} 字节，超过单次上限 {max_batch_bytes} 字节。")
    if max_documents is not None and used_documents + file_count > max_documents:
        validation_errors.append(f"文献数配额不足：已用 {used_documents}/{max_documents}，本次尝试添加 {file_count} 个。")
    if max_total_bytes is not None and used_bytes + total_bytes > max_total_bytes:
        validation_errors.append(f"存储配额不足：已用 {used_bytes}/{max_total_bytes} 字节。")

    for name, content in files:
        safe_name = Path(name).name
        if Path(safe_name).suffix.lower() not in _SUPPORTED_LIBRARY_EXTENSIONS:
            validation_errors.append(f"{safe_name}: 不支持的文件类型。")
        if len(content) > max_file_bytes:
            validation_errors.append(f"{safe_name}: 文件大小 {len(content)} 字节，超过单文件上限 {max_file_bytes} 字节。")

    return {
        "ok": not validation_errors,
        "errors": validation_errors,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "limits": {
            "max_files": max_files,
            "max_batch_bytes": max_batch_bytes,
            "max_file_bytes": max_file_bytes,
        },
    }


def ingest_files(files: list[tuple[str, bytes]]) -> dict:
    """
    上传文件并加入 RAG 索引（HTTP 优先，回退进程内索引）。

    参数：
        files: (filename, content_bytes) 列表。

    返回：
        ingest 结果字典。
    """
    # UI 外调用也必须经过批次与配额预检，避免绕过组件层。
    precheck = validate_upload_batch(files, get_library_status())
    if not precheck["ok"]:
        return {
            "status": "failed",
            "error_type": "upload_precheck_failed",
            "message": "上传前检查未通过。",
            "errors": precheck["errors"],
            "files": [],
            "chunks_added": 0,
        }

    # 直接提交，不再用短时 GET /health 作为上传门禁。Render Free API 可能正在
    # 冷启动，而 POST 本身有足够的连接/处理等待时间。非幂等上传不自动重试，
    # 避免服务端已完成但响应丢失时重复入库。
    remote_failure: dict | None = None
    try:
        multipart = [("files", (name, content)) for name, content in files]
        r = requests.post(
            f"{api_base()}/ingest",
            files=multipart,
            timeout=(_short_timeout_seconds(), _ingest_timeout_seconds()),
        )
        if r.status_code == 200:
            return r.json()
        try:
            body = r.json()
        except ValueError:
            body = {"message": r.text or f"HTTP {r.status_code}"}
        return {
            **body,
            "status": "failed",
            "error_type": body.get("error_type", "http_error"),
            "files": body.get("files", []),
            "chunks_added": body.get("chunks_added", 0),
        }
    except requests.Timeout:
        remote_failure = {
            "status": "failed",
            "files": [],
            "chunks_added": 0,
            "error_type": "ingest_result_unconfirmed",
            "message": (
                "API 唤醒或索引处理超时，本次上传结果尚未确认。"
                "请先刷新文献清单；确认未入库后再重试。"
            ),
        }
    except requests.RequestException:
        remote_failure = {
            "status": "failed",
            "files": [],
            "chunks_added": 0,
            "error_type": "api_unavailable",
            "message": "sage125-api 正在唤醒或暂不可达，本次上传未写入。请稍后重试。",
        }

    if _api_only():
        return remote_failure or {
            "status": "failed",
            "files": [],
            "chunks_added": 0,
            "error_type": "api_unavailable",
            "message": "sage125-api 正在唤醒或暂不可达，本次上传未写入。请稍后重试。",
        }

    # 回退：与 HTTP /ingest 使用同一 LibraryManager，不允许绕过治理层。
    try:
        manager = _new_library_manager()
        result = _as_dict(
            _call_library_method(manager, ("ingest_files", "add_files", "upload_files"), files)
        )
        if "files" in result:
            indexed_files = result.get("files") or []
        elif "files_indexed" in result:
            indexed_files = result.get("files_indexed") or []
        else:
            indexed_files = [Path(name).name for name, _ in files]
        return {
            **result,
            "status": result.get("status", "ok"),
            "files": indexed_files,
            "chunks_added": result.get("chunks_added", result.get("chunks", 0)),
            "errors": result.get("errors", []),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "files": [],
            "chunks_added": 0,
            "error_type": "library_unavailable",
            "message": f"本地文献库写入失败：{exc}",
            "errors": [str(exc)],
        }


def delete_library_document(document_id: str) -> dict:
    """显式删除文献及其索引数据（HTTP 优先，进程内回退）。"""
    document_id = str(document_id or "").strip()
    if not document_id:
        return {"status": "failed", "message": "缺少 document_id。", "error_type": "invalid_document_id"}

    try:
        response = requests.delete(
            f"{api_base()}/library/documents/{quote(document_id, safe='')}",
            timeout=_short_timeout_seconds(),
        )
        if response.status_code in (200, 202, 204):
            if response.status_code == 204 or not response.content:
                return {"status": "ok", "document_id": document_id}
            return _as_dict(response.json())
        # API 存在时尊重其明确拒绝，避免在另一进程重复删除。
        if response.status_code != 404:
            try:
                body = _as_dict(response.json())
            except ValueError:
                body = {"message": response.text or f"HTTP {response.status_code}"}
            return {**body, "status": "failed", "error_type": body.get("error_type", "http_error")}
    except requests.RequestException:
        pass

    if _api_only():
        return {
            "status": "failed",
            "document_id": document_id,
            "error_type": "api_unavailable",
            "message": "sage125-api 暂不可用，未在 UI 服务内删除数据。",
        }

    try:
        manager = _new_library_manager()
        result = _as_dict(
            _call_library_method(manager, ("delete_document", "remove_document"), document_id)
        )
        return {**result, "status": result.get("status", "ok"), "document_id": document_id}
    except Exception as exc:
        return {
            "status": "failed",
            "document_id": document_id,
            "error_type": "library_unavailable",
            "message": f"删除失败：{exc}",
        }


def recover_run_after_timeout(question_id: str, min_mtime: float | None = None) -> dict | None:
    """
    HTTP 超时后尝试从 exports 恢复已完成的运行（后端可能仍在跑并已成功落盘）。

    参数：
        question_id: 期望的问题 ID。
        min_mtime:   仅考虑此 Unix 时间之后写入的 run 目录。

    返回：
        与 start_run 相同结构的 dict；未找到则 None。
    """
    from app.ui.run_browser import list_runs

    for item in list_runs(limit=30):
        rid = item.get("run_id", "")
        if item.get("question_id") != question_id:
            continue
        run_dir = _exports_dir() / rid
        report = run_dir / "report.json"
        if not report.exists():
            continue
        if min_mtime is not None and report.stat().st_mtime < min_mtime:
            continue
        loaded = get_run(rid)
        if loaded.get("plan"):
            summary = loaded.get("llm_call_summary") or {}
            return {
                "run_id": rid,
                "question_id": question_id,
                "mode": item.get("mode", "real"),
                "status": "completed",
                "plan": loaded["plan"],
                "plan_question_id": loaded["plan"].get("question_id", ""),
                "evidence_cards": loaded.get("evidence_cards") or [],
                "agent_trace": loaded.get("agent_trace") or [],
                "quality_gates": loaded.get("quality_gates") or [],
                "llm_call_summary": summary,
                "warnings": ["recovered_after_http_timeout"],
                "errors": [],
                "mock": loaded.get("mock"),
                "recovered_from_timeout": True,
            }
    return None


_TRANSIENT_HTTP = frozenset({408, 409, 429, 500, 502, 503, 504})
_BUSY_MARKERS = ("HTTP 429", "限流", "繁忙", "RATE_LIMIT", "Too Many Requests")


def _preflight_payload(response: requests.Response) -> dict[str, Any] | None:
    """把 /preflight 的 JSON 或 FastAPI detail 收成前端可用的检查结果。"""
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    detail = data.get("detail")
    if isinstance(detail, dict):
        data = {**data, **detail}
    if "ok" not in data and not data.get("errors"):
        return None
    data.setdefault("ok", False)
    data.setdefault("errors", [])
    data.setdefault("warnings", [])
    if not isinstance(data["errors"], list):
        data["errors"] = [str(data["errors"])]
    if not isinstance(data["warnings"], list):
        data["warnings"] = [str(data["warnings"])]
    return data


def _retry_wait_seconds(response: requests.Response | None, attempt: int) -> float:
    """尊重 Retry-After，但把等待压在评委可接受的几秒内。"""
    if response is not None:
        raw = str(response.headers.get("Retry-After") or "").strip()
        if raw.isdigit():
            return min(max(float(raw), 0.2), 8.0)
    return min(0.4 * (2 ** max(attempt - 1, 0)), 3.0)


def _is_authoritative_preflight(parsed: dict[str, Any] | None, status_code: int) -> bool:
    """配置类失败（缺 Key 等）立即返回；429/502 等瞬时状态继续重试。"""
    if not parsed:
        return False
    if parsed.get("ok") is True:
        return True
    errors = [str(item) for item in parsed.get("errors") or []]
    if not errors:
        return False
    joined = " ".join(errors)
    if status_code in _TRANSIENT_HTTP and any(marker in joined for marker in _BUSY_MARKERS):
        return False
    return True


def _health_allows_real_start() -> dict[str, Any] | None:
    """/preflight 被限流时，用已唤醒的 /health 决定能否启动真实任务。"""
    refresh_api_available()
    health = get_health()
    if not isinstance(health, dict):
        return None
    status = str(health.get("status") or "")
    if status == "unavailable":
        return None
    bailian = health.get("bailian") if isinstance(health.get("bailian"), dict) else {}
    configured = bool(health.get("qwen_config_loaded")) or bool(bailian.get("configured"))
    if configured:
        return {
            "ok": True,
            "errors": [],
            "warnings": ["预检接口暂时繁忙，已根据健康检查继续启动。"],
            "recovered_from_transient": True,
        }
    if status in {"ok", "degraded"}:
        return {
            "ok": False,
            "errors": ["未配置 DASHSCOPE_API_KEY 或 WORKSPACE_ID"],
            "warnings": [],
        }
    return None


def _preflight_attempt_timeout_seconds() -> int:
    """单次 /preflight 探测的超时；比通用唤醒超时短，避免单次尝试就吃掉整个预算。

    Render 冷启动期间连接通常会被代理挂起直到容器就绪（而不是快速返回错误），
    因此单次尝试本身就足够充当唤醒探测；不需要在每次重试之间再叠加一次完整的
    唤醒等待（那只会让总耗时成倍增加，且更容易在用户点击"开始生成"触发的
    Streamlit 重跑取消当前请求前，连一次探测都没有真正完成）。
    """
    return min(_wake_timeout_seconds(), 90)


def _run_api_preflight(
    use_local_rag: bool,
    use_deep_research: bool,
    *,
    allow_wake: bool,
) -> dict[str, Any]:
    """API-only 真实模式预检：用户点击启动时允许唤醒托管 API，横幅探测保持短超时。

    只做少量尝试且不在尝试之间叠加独立的完整唤醒等待：单次探测的超时本身就足够
    覆盖一次冷启动；预检的目的是快速区分"配置缺失"与"服务暂时不可达"，真正的
    唤醒与重试预算留给 create_job（它有自己的、更长的重试序列）。
    """
    timeout = _preflight_attempt_timeout_seconds() if allow_wake else _short_timeout_seconds()
    attempts = 2 if allow_wake else 1
    last_errors = ["sage125-api 暂不可用。"]
    params = {
        "use_local_rag": use_local_rag,
        "use_deep_research": use_deep_research,
    }
    for attempt in range(1, attempts + 1):
        response: requests.Response | None = None
        try:
            response = requests.get(
                f"{api_base()}/preflight",
                params=params,
                timeout=timeout,
            )
        except requests.Timeout:
            last_errors = ["sage125-api 正在唤醒，请稍候再点击开始生成。"]
            if allow_wake and attempt < attempts:
                time.sleep(_retry_wait_seconds(None, attempt))
            continue
        except (requests.RequestException, ValueError):
            last_errors = ["sage125-api 暂不可用。"]
            if allow_wake and attempt < attempts:
                time.sleep(_retry_wait_seconds(None, attempt))
            continue
        parsed = _preflight_payload(response)
        if _is_authoritative_preflight(parsed, response.status_code):
            return parsed or {"ok": False, "errors": last_errors, "warnings": []}
        if response.status_code == 200:
            last_errors = ["sage125-api 返回了无法解析的 preflight 结果。"]
            continue
        if response.status_code in _TRANSIENT_HTTP:
            last_errors = ["sage125-api 暂时繁忙，正在自动重试。"]
            if allow_wake and attempt < attempts:
                time.sleep(_retry_wait_seconds(response, attempt))
            continue
        last_errors = [f"sage125-api 返回 HTTP {response.status_code}。"]
    if allow_wake:
        fallback = _health_allows_real_start()
        if fallback is not None:
            return fallback
        return {
            "ok": False,
            "errors": ["服务正在恢复或请求过多，请等待几秒后再次点击开始生成。"],
            "warnings": [],
        }
    if last_errors and any("繁忙" in item or "唤醒" in item for item in last_errors):
        return {
            "ok": True,
            "errors": [],
            "warnings": ["预检接口暂时繁忙，启动时会再次检查。"],
            "deferred": True,
        }
    return {"ok": False, "errors": last_errors, "warnings": []}


def run_preflight(
    use_local_rag: bool = True,
    use_deep_research: bool = True,
    *,
    check_connectivity: bool = False,
    progress_callback: Callable[[dict], None] | None = None,
    allow_wake: bool = False,
) -> dict:
    """运行真实模式 preflight；API-only UI 不得加载后端配置或模型客户端。"""
    if _api_only():
        return _run_api_preflight(
            use_local_rag,
            use_deep_research,
            allow_wake=allow_wake,
        )
    from app.workflow.preflight import run_real_preflight
    from app.core.run_progress import progress_reporting

    with progress_reporting(progress_callback):
        return run_real_preflight(
            use_local_rag=use_local_rag,
            use_deep_research=use_deep_research,
            check_connectivity=check_connectivity,
        )


def _start_run_inprocess(
    payload: dict,
    mode: str,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    """在 Streamlit 进程内直接运行 pipeline（无 HTTP 超时限制）。"""
    from app.core.logging import mask_text
    from app.core.run_response import build_run_response_from_state, failed_run_response

    question_id = payload["question_id"]
    if mode == "real":
        pf = run_preflight(
            payload["use_local_rag"],
            payload["use_deep_research"],
            check_connectivity=True,
            progress_callback=progress_callback,
        )
        if not pf.get("ok"):
            resp = failed_run_response(
                question_id, mode, pf.get("errors", []), message="preflight 未通过"
            )
            d = resp.to_api_dict()
            d["preflight"] = pf
            d["error_type"] = "preflight_failed"
            return d

    try:
        from app.workflow.pipeline import run_pipeline_with_state

        plan, state = run_pipeline_with_state(
            question_id=question_id,
            user_feedback=payload.get("user_feedback") or None,
            use_local_rag=payload["use_local_rag"],
            use_deep_research=payload["use_deep_research"],
            use_open_literature=payload["use_open_literature"],
            reviewer_auto_revision=payload["reviewer_auto_revision"],
            mock_mode=(mode == "mock"),
            progress_callback=progress_callback,
        )
        status = "completed"
        if state.errors:
            status = "failed"
        elif state.warnings and any("deep_research_failed" in w for w in state.warnings):
            status = "partial_failed"
        resp = build_run_response_from_state(
            question_id=question_id, mode=mode, state=state, plan=plan, status=status, message=status
        )
        return resp.to_api_dict()
    except Exception as exc:
        err = mask_text(str(exc))
        resp = failed_run_response(
            question_id,
            mode,
            [err],
            message="pipeline 异常",
            run_id=getattr(exc, "run_id", None),
        )
        d = resp.to_api_dict()
        d["error_type"] = type(exc).__name__
        return d


def start_run(
    question_id: str,
    feedback: str,
    switches: dict,
    mode: str = "mock",
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    """
    启动一次 pipeline 运行（HTTP 优先，回退进程内）。

    参数：
        question_id: 问题 ID。
        feedback:    可选用户反馈。
        switches:    能力开关字典。
        mode:        "mock" | "real"。

    返回：
        运行结果字典（含 question_id / plan.question_id / llm_call_summary）。
    """
    payload = {
        "question_id": question_id,
        "mode": mode,
        "user_feedback": feedback or "",
        "use_deep_research": switches.get("use_deep_research", True),
        "use_open_literature": switches.get("use_open_literature", True),
        "use_local_rag": switches.get("use_local_rag", True),
        "reviewer_auto_revision": switches.get("reviewer_auto_revision", True),
    }
    # 默认进程内运行（真实模式常需 15–25 分钟，HTTP 易触发读超时）。
    if _prefer_inprocess_run():
        return _start_run_inprocess(payload, mode, progress_callback=progress_callback)

    if not api_available():
        return {
            "status": "failed",
            "errors": ["sage125-api 暂不可用，未在 UI 服务内执行模型调用。"],
            "mock": mode == "mock",
            "error_type": "api_unavailable",
        }

    # 显式 FRONTEND_RUN_VIA_API=1 时走 HTTP；超时后尝试从 exports 恢复。
    import time

    started_at = time.time()
    timeout_s = _run_timeout_seconds(mode, payload.get("use_deep_research", False))
    if progress_callback:
        progress_callback({
            "stage": "preflight", "status": "waiting", "percent": 4,
            "message": "已交给本地 API，正在等待真实运行进度",
        })
    try:
        r = requests.post(f"{api_base()}/runs", json=payload, timeout=timeout_s)
        if r.status_code == 200:
            if progress_callback:
                progress_callback({"stage": "completed", "status": "completed", "percent": 100,
                                   "message": "AI Scientist 运行完成"})
            return {**_coerce_run_payload(r.json()), "mock": mode == "mock"}
        try:
            raw_body = r.json() if "json" in r.headers.get("content-type", "") else {"errors": [r.text]}
        except ValueError:
            raw_body = {"errors": [r.text or f"HTTP {r.status_code}"]}
        body = _coerce_run_payload(raw_body)
        error_type = body.get("error_type") or "http_error"
        if body.get("preflight") or body.get("message") == "preflight 未通过":
            error_type = "preflight_failed"
        return {
            **body,
            "status": body.get("status", "failed"),
            "errors": body.get("errors") or [body.get("message") or f"HTTP {r.status_code}"],
            "mock": mode == "mock",
            "error_type": error_type,
        }
    except requests.exceptions.ReadTimeout:
        recovered = recover_run_after_timeout(question_id, min_mtime=started_at - 5)
        if recovered:
            return recovered
        return {
            "status": "failed",
            "errors": [
                f"真实模式运行超时（{timeout_s}s）。可先关闭 DeepResearch 或运行 smoke_bailian 检查百炼链路。"
            ],
            "mock": mode == "mock",
            "error_type": "read_timeout",
        }
    except requests.RequestException as exc:
        err = str(exc)
        if "Read timed out" in err or "read timeout" in err.lower():
            recovered = recover_run_after_timeout(question_id, min_mtime=started_at - 5)
            if recovered:
                return recovered
            return {
                "status": "failed",
                "errors": [err],
                "mock": mode == "mock",
                "error_type": "read_timeout",
            }
        return {"status": "failed", "errors": [err], "mock": mode == "mock", "error_type": "connection_error"}


def run_experiment(question_id: str) -> dict:
    """
    触发一次真实实验执行（HTTP 优先，回退进程内）。

    目前仅 Q028 有可执行的科学入口；其它题目服务端会诚实返回
    ``available=False``，前端不编造结果。
    """
    qid = str(question_id or "").strip()
    try:
        r = requests.post(
            f"{api_base()}/experiments/{quote(qid, safe='')}/run",
            timeout=max(_short_timeout_seconds(), 180),
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    if _api_only():
        return {
            "question_id": qid,
            "available": False,
            "status": "not_available",
            "reason": "sage125-api 暂不可用，无法运行真实实验。",
        }
    from app.api.routes import run_experiment as _run_experiment

    return _run_experiment(qid)


def get_experiment_canonical_status(question_id: str) -> dict:
    """
    只读地获取旗舰案例 canonical package / 原子发布状态（HTTP 优先，回退进程内）。

    绝不在此调用中触发实验执行或发布动作；仅读取现有磁盘证据与已发布的
    canonical pointer（如有）。
    """
    qid = str(question_id or "").strip()
    try:
        r = requests.get(
            f"{api_base()}/experiments/{quote(qid, safe='')}/canonical-status",
            timeout=_short_timeout_seconds(),
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    if _api_only():
        return {
            "question_id": qid,
            "available": False,
            "status": "not_available",
            "reason": "sage125-api 暂不可用，无法读取 canonical 状态。",
        }
    from app.api.routes import get_experiment_canonical_status as _get_status

    return _get_status(qid)


def get_llm_calls(run_id: str) -> dict:
    """获取某次运行的脱敏 LLM 调用审计（HTTP 优先，回退读取本地文件）。"""
    if api_available():
        try:
            r = requests.get(
                f"{api_base()}/runs/{run_id}/llm-calls",
                timeout=_short_timeout_seconds(),
            )
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
    if _api_only():
        return {"exists": False, "status": "unavailable", "records": [], "summary": {}}
    from app.ui.run_browser import get_llm_call_audit

    return get_llm_call_audit(run_id)


def get_run(run_id: str) -> dict:
    """读取某次运行产物（HTTP 优先，回退读取 exports）。"""
    if api_available():
        try:
            r = requests.get(
                f"{api_base()}/runs/{run_id}", timeout=_short_timeout_seconds()
            )
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
    if _api_only():
        return {"status": "unavailable", "message": "sage125-api 暂不可用。"}
    run_dir = _exports_dir() / run_id
    if not run_dir.exists():
        return {"status": "missing", "message": f"运行不存在：{run_id}"}

    def _rj(p: Path):
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    plan = _rj(run_dir / "report.json")
    audit = _rj(run_dir / "llm_call_audit.json") or {}
    return {
        "run_id": run_id, "plan": plan,
        "question_id": (plan or {}).get("question_id", ""),
        "evidence_cards": _rj(run_dir / "evidence_cards.json"),
        "agent_trace": _rj(run_dir / "agent_trace.json"),
        "quality_gates": _rj(run_dir / "quality_gates.json"),
        "llm_call_summary": audit.get("summary", {}),
        "mock": audit.get("run_mode") == "mock" if audit else None,
    }


def revise_run(run_id: str, feedback: str) -> dict:
    """触发反馈修订（HTTP 优先，回退进程内）。"""
    if api_available():
        try:
            r = requests.post(f"{api_base()}/runs/{run_id}/feedback", json={"feedback": feedback}, timeout=_run_timeout_seconds("real"))
            if r.status_code == 200:
                return r.json()
            return {"status": "failed", "message": r.text}
        except requests.RequestException as exc:
            return {"status": "failed", "message": str(exc)}
    if _api_only():
        return {
            "status": "failed",
            "error_type": "api_unavailable",
            "message": "sage125-api 暂不可用。",
        }
    from app.workflow.pipeline import revise_with_feedback

    try:
        plan = revise_with_feedback(run_id, feedback)
        return {"run_id": run_id, "status": "revised", "plan": plan.model_dump(),
                "revision_history": plan.revision_history}
    except ValueError as exc:
        # 非法反馈被拒绝。
        return {"status": "rejected", "message": str(exc)}
    except FileNotFoundError as exc:
        return {"status": "failed", "message": str(exc)}


_REMOTE_RUN_FILE_CACHE: dict[tuple[str, str], bytes] = {}


def _allowed_export_file_name(file_name: str) -> bool:
    """Whether file_name is an exact allowlisted artifact name."""
    from app.ui.run_browser import ARTIFACT_FILES

    return bool(file_name) and file_name in ARTIFACT_FILES and Path(file_name).name == file_name


def _clear_remote_run_file_cache() -> None:
    """Drop cached remote artifact bytes (tests / new run)."""
    _REMOTE_RUN_FILE_CACHE.clear()


def local_file_path(run_id: str, file_name: str) -> Optional[Path]:
    """返回某运行产物文件的本地路径（存在则返回，否则 None）。"""
    if not run_id or not _allowed_export_file_name(file_name):
        return None
    if Path(run_id).name != run_id or run_id in {".", ".."}:
        return None
    run_dir = (_exports_dir() / run_id).resolve()
    p = (run_dir / file_name).resolve()
    try:
        p.relative_to(run_dir)
    except ValueError:
        return None
    return p if p.is_file() else None


def _fetch_remote_run_file(run_id: str, file_name: str) -> Optional[bytes]:
    """GET /runs/{run_id}/files/{file_name}; missing or errors return None."""
    cache_key = (run_id, file_name)
    cached = _REMOTE_RUN_FILE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        response = _http_session().get(
            f"{api_base()}/runs/{quote(run_id, safe='')}/files/{quote(file_name, safe='')}",
            timeout=_short_timeout_seconds(),
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    content = response.content
    _REMOTE_RUN_FILE_CACHE[cache_key] = content
    return content


def read_local_file(run_id: str, file_name: str) -> Optional[bytes]:
    """读取某运行产物文件内容字节（本地优先，预览站回退 API；不存在返回 None）。"""
    if not run_id or not _allowed_export_file_name(file_name):
        return None
    p = local_file_path(run_id, file_name)
    if p is not None:
        return p.read_bytes()
    if api_available():
        return _fetch_remote_run_file(run_id, file_name)
    return None


def _job_headers() -> dict[str, str]:
    return {"Accept": "application/json"}


def _job_error_payload(response: requests.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        body = {"message": response.text}
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        body = {**body, **detail}
    return body if isinstance(body, dict) else {"message": str(body)}


def _job_create_attempt_timeout_seconds() -> int:
    """单次 POST /api/v1/jobs 的超时；比通用唤醒超时短，配合多次直接重试更快获得反馈。

    Render 冷启动期间连接通常会被代理挂起直到容器就绪，因此每次尝试本身就足够
    覆盖一次唤醒；不再在重试之间额外插入一次独立的 /health 唤醒等待——那只会让
    单次尝试的耗时翻倍，并显著增加"用户等得不耐烦、再次点击导致 Streamlit 重跑、
    从而取消掉正在等待的请求"这一失败模式出现的概率。"""
    return min(_wake_timeout_seconds(), 60)


def _parse_job_success_payload(response: requests.Response) -> tuple[dict[str, Any] | None, str | None]:
    """``create_job`` / ``retry_job`` 共用的成功响应解析；两者不允许各自实现一套。

    HTTP 状态码 200/202 只代表"网关认为请求处理成功"，不代表 body 就是我们期望
    的业务 JSON——Render 冷启动占位页同样可能顶着 200/202 出现。
    """
    data, reason = parse_json_response(response)
    if data is None:
        return None, reason or "invalid_json"
    if not data.get("job_id"):
        return None, "missing_job_id"
    data["created"] = bool(data.get("created", not data.get("reused")))
    return data, None


def _api_not_ready_failure(reason: str | None) -> dict[str, Any]:
    """把"HTTP 成功但业务未就绪"统一转成可重试的失败 dict，绝不让异常冒给调用方。"""
    message = {
        "render_waking": "sage125-api 仍在从休眠中唤醒（收到 Render 冷启动占位响应），正在自动重试。",
        "missing_job_id": "sage125-api 返回了不完整的任务数据，正在自动重试。",
    }.get(reason or "", "sage125-api 返回了无法解析的响应，正在自动重试。")
    _LOGGER.info(
        "sage125-api job endpoint not ready: ready=%s reason=%s",
        False,
        reason or "invalid_json",
    )
    return {"status": "failed", "error_type": "api_not_ready", "errors": [message]}


def create_job(
    *,
    question_id: str,
    mode: str,
    job_type: str,
    client_id: str,
    input_digest: str,
    idempotency_key: str,
    options: dict | None = None,
) -> dict[str, Any]:
    """创建或复用后台 Job；不因瞬时 /health 失败而拒绝提交。

    Idempotency-Key 在同一 question_id/job_type/input_digest 下保持稳定，因此即使
    本次调用最终仍失败，用户再次点击「开始生成」也是安全的：不会重复创建任务，
    只是对同一个 Idempotency-Key 发起新一轮直接重试。
    """
    payload = {
        "question_id": question_id,
        "mode": mode,
        "job_type": job_type,
        "client_id": client_id,
        "input_digest": input_digest,
        "options": options
        or {
            "use_deep_research": True,
            "use_open_literature": True,
            "use_local_rag": True,
            "reviewer_auto_revision": True,
        },
    }
    last_failure: dict[str, Any] = {
        "status": "failed",
        "error_type": "http_error",
        "errors": ["无法创建后台任务。"],
    }
    attempts = 5
    timeout_s = _job_create_attempt_timeout_seconds()
    for attempt in range(1, attempts + 1):
        try:
            response = _http_session().post(
                f"{api_base()}/api/v1/jobs",
                json=payload,
                headers={**_job_headers(), "Idempotency-Key": idempotency_key},
                timeout=timeout_s,
            )
        except requests.RequestException as exc:
            last_failure = {
                "status": "failed",
                "error_type": "network",
                "errors": [
                    "sage125-api 正在从休眠中唤醒（通常需要 30-90 秒）。请保持本页面打开，"
                    "稍后再次点击「开始生成」——同一任务不会被重复创建。"
                    if attempt >= attempts
                    else str(exc)
                ],
            }
            if attempt < attempts:
                time.sleep(_retry_wait_seconds(None, attempt))
                continue
            return last_failure
        if response.status_code in (200, 202):
            data, failure_reason = _parse_job_success_payload(response)
            if data is not None:
                return data
            last_failure = _api_not_ready_failure(failure_reason)
            if attempt < attempts:
                time.sleep(_retry_wait_seconds(response, attempt))
                continue
            last_failure["errors"] = [
                "sage125-api 正在从休眠中唤醒（通常需要 2-4 分钟）。请保持本页面打开，"
                "稍后再次点击「开始生成」——同一任务不会被重复创建。"
            ]
            return last_failure
        body = _job_error_payload(response)
        last_failure = {
            "status": "failed",
            "error_type": body.get("code") or "http_error",
            "errors": [body.get("message") or f"HTTP {response.status_code}"],
            **body,
        }
        if response.status_code in _TRANSIENT_HTTP and attempt < attempts:
            time.sleep(_retry_wait_seconds(response, attempt))
            continue
        if attempt >= attempts:
            last_failure["errors"] = [
                "sage125-api 正在从休眠中唤醒（通常需要 30-90 秒）。请保持本页面打开，"
                "稍后再次点击「开始生成」——同一任务不会被重复创建。"
            ]
        return last_failure
    return last_failure


_JOB_STATUS_MEMO: dict[str, tuple[float, dict[str, Any]]] = {}


def get_job(job_id: str) -> dict[str, Any] | None:
    if not job_id:
        return None
    now = time.monotonic()
    cached = _JOB_STATUS_MEMO.get(job_id)
    if cached and now - cached[0] < 1.0:
        return cached[1]
    try:
        response = _http_session().get(
            f"{api_base()}/api/v1/jobs/{job_id}",
            headers=_job_headers(),
            timeout=_short_timeout_seconds(),
        )
    except requests.RequestException:
        return cached[1] if cached else None
    if response.status_code == 429 and cached:
        return cached[1]
    if response.status_code != 200:
        return cached[1] if cached else None
    payload, _reason = parse_json_response(response)
    if payload is not None:
        _JOB_STATUS_MEMO[job_id] = (now, payload)
        return payload
    # 200 但不是合法业务 JSON（例如 Render 冷启动占位页）：不能当成功，退回上次
    # 已知状态，避免进度条因为一次瞬时抖动就整体消失。
    return cached[1] if cached else None


def list_job_events(job_id: str, *, after_sequence: int = 0) -> list[dict[str, Any]]:
    if not job_id or not api_available():
        return []
    try:
        response = _http_session().get(
            f"{api_base()}/api/v1/jobs/{job_id}/events",
            params={"after_sequence": after_sequence},
            headers=_job_headers(),
            timeout=_short_timeout_seconds(),
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else []
    return items if isinstance(items, list) else []


def get_active_job(
    *,
    client_id: str,
    question_id: str,
    job_type: str | None = None,
) -> dict[str, Any] | None:
    params = {"client_id": client_id, "question_id": question_id}
    if job_type:
        params["job_type"] = job_type
    try:
        response = _http_session().get(
            f"{api_base()}/api/v1/jobs/active",
            params=params,
            headers=_job_headers(),
            timeout=_short_timeout_seconds(),
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    payload = response.json()
    return payload if isinstance(payload, dict) else None


def get_latest_job(
    *,
    client_id: str,
    question_id: str,
    job_type: str | None = None,
) -> dict[str, Any] | None:
    params = {"client_id": client_id, "question_id": question_id}
    if job_type:
        params["job_type"] = job_type
    try:
        response = _http_session().get(
            f"{api_base()}/api/v1/jobs/latest",
            params=params,
            headers=_job_headers(),
            timeout=_short_timeout_seconds(),
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    payload = response.json()
    return payload if isinstance(payload, dict) else None


def list_jobs(
    *,
    question_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    if question_id:
        params["question_id"] = question_id
    if status:
        params["status"] = status
    try:
        response = _http_session().get(
            f"{api_base()}/api/v1/jobs",
            params=params,
            headers=_job_headers(),
            timeout=_short_timeout_seconds(),
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else []
    return items if isinstance(items, list) else []


def retry_job(job_id: str, *, client_id: str | None = None) -> dict[str, Any]:
    if not api_available():
        return {
            "status": "failed",
            "error_type": "api_unavailable",
            "errors": ["sage125-api 暂不可用，无法重试。"],
        }
    try:
        response = _http_session().post(
            f"{api_base()}/api/v1/jobs/{job_id}/retry",
            json={"client_id": client_id} if client_id else {},
            headers=_job_headers(),
            timeout=_short_timeout_seconds(),
        )
    except requests.RequestException as exc:
        return {"status": "failed", "error_type": "network", "errors": [str(exc)]}
    if response.status_code not in (200, 202):
        body = _job_error_payload(response)
        return {
            "status": "failed",
            "error_type": body.get("code") or "http_error",
            "errors": [body.get("message") or f"HTTP {response.status_code}"],
            **body,
        }
    data, failure_reason = _parse_job_success_payload(response)
    if data is None:
        return _api_not_ready_failure(failure_reason)
    return data
