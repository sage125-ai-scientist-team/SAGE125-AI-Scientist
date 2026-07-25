"""
app.clients.qwen_deep_research_client —— Qwen Deep Research 客户端。

重要定位说明：
    DeepResearch 只是**调研资料来源**，不是最终报告生成器。其流式产出
    （研究纪要与引用线索）必须交由 EvidenceExtractor 抽取并经 Crossref/arXiv
    等核验后，才能进入最终 ResearchPlan 的 references，严禁直接当作最终报告。

技术约束：
    - 必须使用原生 dashscope SDK（禁止用 OpenAI-compatible client 调用）；
    - 设置 dashscope.base_http_api_url = settings.dashscope_deep_research_base_url；
    - 必须 stream=True（该模型仅支持流式输出，同步调用会超时）；
    - 调用失败不得中断整个 pipeline，返回 {"status":"failed","error":"masked error","content":""}。
"""

from __future__ import annotations

import time
from typing import Optional

from app.core.config import Settings, assert_qwen_model, get_settings
from app.core.logging import get_logger
from app.core.run_progress import emit_progress
from app.clients.outbound_http import build_outbound_requests_session, redact_outbound_error

# 模块级日志器（继承脱敏能力）。
logger = get_logger("clients.deep_research")


_DEEP_RESEARCH_ERROR_GUIDANCE: dict[str, str] = {
    "DEEP_RESEARCH_RATE_LIMIT": "DeepResearch 被限流或配额不足（429）；请稍后重试。",
    "DEEP_RESEARCH_SERVICE": "DeepResearch 服务暂时异常（5xx）；请稍后重试。",
    "DEEP_RESEARCH_TIMEOUT": "DeepResearch 请求超时；请检查网络后重试。",
    "DEEP_RESEARCH_CONNECTION_RESET": "DeepResearch HTTPS 流式连接被重置；请检查网络出口、VPN 或显式 HTTPS 代理。",
    "DEEP_RESEARCH_PROXY": "DeepResearch 代理连接失败；请检查项目 OUTBOUND_HTTPS_PROXY。",
    "DEEP_RESEARCH_AUTH": "DeepResearch 鉴权或模型权限失败（401/403）。",
    "DEEP_RESEARCH_ENDPOINT": "DeepResearch endpoint 或请求格式无效（400/404/422）。",
    "DEEP_RESEARCH_NETWORK": "无法连接 DeepResearch HTTPS 服务；请检查网络出口、VPN 或显式 HTTPS 代理。",
    "DEEP_RESEARCH_UNKNOWN": "DeepResearch 调用失败；请运行低成本 smoke 诊断。",
}


class _DeepResearchCallFailure(Exception):
    """Internal, secret-safe failure classification for one DeepResearch attempt."""

    def __init__(self, code: str, stage: str) -> None:
        self.code = code
        self.stage = stage
        super().__init__(code)


def _status_code(value: object) -> int | None:
    """Read an SDK response status without reading its body or headers."""
    try:
        status = int(getattr(value, "status_code", None))
    except (TypeError, ValueError):
        return None
    return status if status > 0 else None


def _classify_exception(exc: Exception, *, stage: str) -> _DeepResearchCallFailure:
    """Map transport and HTTP failures without returning raw exception text."""
    if isinstance(exc, _DeepResearchCallFailure):
        return exc
    status = _status_code(exc)
    if status == 429:
        code = "DEEP_RESEARCH_RATE_LIMIT"
    elif status in {401, 403}:
        code = "DEEP_RESEARCH_AUTH"
    elif status in {400, 404, 422}:
        code = "DEEP_RESEARCH_ENDPOINT"
    elif status is not None and status >= 500:
        code = "DEEP_RESEARCH_SERVICE"
    else:
        text = str(exc).lower()
        if "10054" in text or "connection reset" in text or "forcibly closed" in text:
            code = "DEEP_RESEARCH_CONNECTION_RESET"
        elif "proxy" in text or "tunnel" in text or "407" in text:
            code = "DEEP_RESEARCH_PROXY"
        elif "timeout" in text or "timed out" in text:
            code = "DEEP_RESEARCH_TIMEOUT"
        elif any(token in text for token in ("connect", "connection", "dns", "name resolution", "ssl", "certificate")):
            code = "DEEP_RESEARCH_NETWORK"
        else:
            code = "DEEP_RESEARCH_UNKNOWN"
    return _DeepResearchCallFailure(code, stage)


def _retryable(failure: _DeepResearchCallFailure) -> bool:
    """Keep retries bounded to the project policy and only transient failures."""
    return failure.code in {
        "DEEP_RESEARCH_RATE_LIMIT",
        "DEEP_RESEARCH_SERVICE",
        "DEEP_RESEARCH_TIMEOUT",
        "DEEP_RESEARCH_CONNECTION_RESET",
        "DEEP_RESEARCH_NETWORK",
    }


class QwenDeepResearchClient:
    """
    Qwen Deep Research 封装（基于原生 dashscope SDK）。

    通过流式调用收集各阶段（phase）与状态（status）产出，聚合为结构化结果。
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        初始化 Deep Research 客户端并校验模型合规性。

        参数：
            settings: 可选注入配置；缺省使用全局单例。

        异常：
            ValueError: 当配置的深度研究模型不是千问模型时抛出。
        """
        # 允许注入配置以便测试。
        self.settings = settings or get_settings()
        # 校验深度研究模型必须为千问。
        assert_qwen_model(self.settings.qwen_deep_research_model)

    def run_deep_research(self, topic: str, context: str = "") -> dict:
        """
        执行一次深度研究任务并聚合流式产出。

        参数：
            topic:   研究主题/问题。
            context: 额外上下文（如问题背景、已知证据摘要）。

        返回：
            结构化字典，字段包括：
                status      —— "succeeded" / "failed"；
                content     —— 聚合后的研究纪要文本（answer 阶段内容）；
                phases      —— 出现过的阶段名去重列表；
                references  —— 深度研究给出的引用线索（未核验，需下游核验）；
                usage       —— token 用量（若返回）；
                request_id  —— 最后一次响应的 request_id（若返回）；
                error       —— 失败时的脱敏错误信息。
        失败时不抛出异常，返回 {"status":"failed","error":...,"content":""}，
        以保证整个 pipeline 不被中断。
        """
        # 未配置深度研究 endpoint 时，直接返回失败结构（不中断 pipeline）。
        if not self.settings.deep_research_configured:
            logger.warning("DeepResearch 未配置，跳过（返回 failed）。")
            return {"status": "failed", "error": "deep_research_not_configured", "content": ""}

        # 延迟导入 dashscope，避免在无该依赖的测试环境强依赖。
        try:
            import dashscope
            from dashscope import Generation
        except ImportError:
            logger.warning("未安装 dashscope SDK，DeepResearch 跳过（返回 failed）。")
            return {"status": "failed", "error": "dashscope_not_installed", "content": ""}

        # 关键：将 dashscope 的 HTTP endpoint 指向深度研究专用 base_url。
        dashscope.base_http_api_url = self.settings.dashscope_deep_research_base_url

        # 组装消息：将上下文与主题拼为单轮用户输入。
        user_content = topic if not context else f"{context}\n\n研究主题：{topic}"
        messages = [{"role": "user", "content": user_content}]

        # DeepResearch 仅支持 stream=True。DashScope 允许注入 requests.Session，
        # 因此这里复用所有百炼客户端共享的显式代理策略，而不读取系统代理。
        max_retries = int(getattr(self.settings, "llm_max_retries", 1))
        for attempt in range(max_retries + 1):
            collected_content: list[str] = []
            phases: list[str] = []
            references: list[dict] = []
            usage: dict = {}
            request_id: str = ""
            session = build_outbound_requests_session(self.settings)
            try:
                emit_progress(
                    "deep_research", status="waiting", percent=38,
                    message="正在等待千问 DeepResearch 返回调研阶段",
                    model_alias="deepresearch", model_name_internal=self.settings.qwen_deep_research_model,
                )
                responses = Generation.call(
                    api_key=self.settings.dashscope_api_key,
                    model=self.settings.qwen_deep_research_model,
                    messages=messages,
                    stream=True,
                    timeout=getattr(self.settings, "deep_research_timeout_seconds", 900),
                    session=session,
                )
                # 逐个消费流式响应，解析 phase/status/content 与引用线索。
                for response in responses:
                    # HTTP 错误必须稳定映射，不能误报为“空成功”。
                    status = _status_code(response)
                    if status is not None and status >= 400:
                        raise _classify_exception(response, stage="http_response")
                    rid = getattr(response, "request_id", None)
                    if rid:
                        request_id = str(rid)
                    resp_usage = getattr(response, "usage", None)
                    if resp_usage:
                        usage = dict(resp_usage) if not isinstance(resp_usage, dict) else resp_usage
                    output = getattr(response, "output", None)
                    if not output:
                        continue
                    message = output.get("message", {}) if isinstance(output, dict) else {}
                    phase = message.get("phase")
                    content = message.get("content", "")
                    if phase and phase not in phases:
                        phases.append(phase)
                        phase_labels = {
                            "search": "正在检索资料",
                            "analysis": "正在分析资料",
                            "answer": "正在生成调研纪要",
                        }
                        emit_progress(
                            "deep_research", status="running", percent=38,
                            message=f"千问 DeepResearch：{phase_labels.get(phase, str(phase))}",
                            model_alias="deepresearch", model_name_internal=self.settings.qwen_deep_research_model,
                        )
                    if phase == "answer" and content:
                        collected_content.append(content)
                    extra = message.get("extra", {}) if isinstance(message, dict) else {}
                    deep = extra.get("deep_research", {}) if isinstance(extra, dict) else {}
                    for ref in deep.get("references", []) or []:
                        references.append(ref)

                return {
                    "status": "succeeded",
                    "content": "".join(collected_content),
                    "phases": phases,
                    "references": references,
                    "usage": usage,
                    "request_id": request_id,
                    "note": "DeepResearch 输出仅为调研资料来源，需经证据抽取与核验后使用。",
                }
            except Exception as exc:
                stage = "stream_read" if collected_content else "http_stream_open"
                failure = _classify_exception(exc, stage=stage)
                if attempt < max_retries and not collected_content and _retryable(failure):
                    logger.warning(
                        "DeepResearch 短暂失败，将进行有限重试：code=%s stage=%s exception_type=%s",
                        failure.code, failure.stage, type(exc).__name__,
                    )
                    time.sleep(min(1.5 * (attempt + 1), 3.0))
                    continue
                logger.warning(
                    "DeepResearch 调用失败：code=%s stage=%s exception_type=%s detail=%s",
                    failure.code, failure.stage, type(exc).__name__, redact_outbound_error(exc),
                )
                emit_progress(
                    "deep_research", status="running", percent=42,
                    message="DeepResearch 未完成，主流程将继续使用其他证据来源",
                    model_alias="deepresearch", model_name_internal=self.settings.qwen_deep_research_model,
                )
                return {
                    "status": "failed",
                    "error": _DEEP_RESEARCH_ERROR_GUIDANCE[failure.code],
                    "error_code": failure.code,
                    "error_stage": failure.stage,
                    "content": "",
                }
            finally:
                session.close()
