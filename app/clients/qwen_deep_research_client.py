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

from typing import Any, Optional

from app.core.config import Settings, assert_qwen_model, get_settings
from app.core.logging import get_logger, mask_text
from app.core.run_progress import emit_progress

# 模块级日志器（继承脱敏能力）。
logger = get_logger("clients.deep_research")


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
        # 最近一次真实调用的审计元数据；与 QwenChatClient 保持同一读取契约。
        self.last_request_id: Optional[str] = None
        self.last_usage: dict[str, int] = {}

    @staticmethod
    def _response_value(response: Any, name: str) -> Any:
        """兼容 SDK 对象和映射响应，提取一个顶层字段。"""
        if isinstance(response, dict):
            return response.get(name)
        return getattr(response, name, None)

    @classmethod
    def _normalized_usage(cls, raw_usage: Any) -> dict[str, int]:
        """将 DashScope/OpenAI 风格 usage 统一为严格的三项 token 计数。"""
        if raw_usage is None:
            return {}
        if isinstance(raw_usage, dict):
            source = raw_usage
        else:
            source = {
                name: getattr(raw_usage, name, None)
                for name in (
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "prompt_tokens",
                    "completion_tokens",
                )
            }
        input_tokens = source.get("input_tokens", source.get("prompt_tokens"))
        output_tokens = source.get("output_tokens", source.get("completion_tokens"))
        total_tokens = source.get("total_tokens")
        values = (input_tokens, output_tokens, total_tokens)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            return {}
        if total_tokens != input_tokens + output_tokens:
            return {}
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

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

        # 聚合容器：内容、阶段、引用、用量、request_id。
        collected_content: list[str] = []
        phases: list[str] = []
        references: list[dict] = []
        usage: dict[str, int] = {}
        request_id: str = ""
        self.last_request_id = None
        self.last_usage = {}

        try:
            # 必须 stream=True：深度研究为长耗时多轮任务，同步会超时。
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
                timeout=self.settings.deep_research_timeout_seconds,
            )
            # 逐个消费流式响应，解析 phase/status/content 与引用线索。
            for response in responses:
                # 记录 request_id（若存在）。
                rid = self._response_value(response, "request_id")
                if isinstance(rid, str) and rid.strip():
                    request_id = rid
                    self.last_request_id = rid
                # 记录用量（若存在）。
                normalized_usage = self._normalized_usage(self._response_value(response, "usage"))
                if normalized_usage:
                    usage = normalized_usage
                    self.last_usage = normalized_usage
                # 解析 output.message。
                output = self._response_value(response, "output")
                if not output:
                    continue
                message = output.get("message", {}) if isinstance(output, dict) else {}
                phase = message.get("phase")
                content = message.get("content", "")
                # 记录去重后的阶段名。
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
                # 仅在 answer 阶段收集正文内容（其余阶段多为进度信息）。
                if phase == "answer" and content:
                    collected_content.append(content)
                # 收集引用线索（未核验），供下游 EvidenceExtractor 处理。
                extra = message.get("extra", {}) if isinstance(message, dict) else {}
                deep = extra.get("deep_research", {}) if isinstance(extra, dict) else {}
                for ref in deep.get("references", []) or []:
                    references.append(ref)

            # 聚合成功结果。
            return {
                "status": "succeeded",
                "content": "".join(collected_content),
                "phases": phases,
                "references": references,
                "usage": usage,
                "request_id": request_id,
                # 明确提示：以下内容为调研资料，非最终报告。
                "note": "DeepResearch 输出仅为调研资料来源，需经证据抽取与核验后使用。",
            }
        except Exception as exc:
            # 任何异常都不得中断 pipeline：脱敏后返回 failed 结构。
            logger.warning("DeepResearch 调用失败：%s", mask_text(str(exc)))
            emit_progress(
                "deep_research", status="running", percent=42,
                message="DeepResearch 未完成，主流程将继续使用其他证据来源",
                model_alias="deepresearch", model_name_internal=self.settings.qwen_deep_research_model,
            )
            return {
                "status": "failed",
                "error": mask_text(str(exc)),
                "content": "",
                "usage": usage,
                "request_id": request_id,
            }
