"""
app.clients.rerank_client —— 检索结果重排序客户端。

默认使用百炼 qwen3-rerank，通过 OpenAI-compatible 重排序 endpoint
（.../compatible-api/v1/reranks，由 settings.rerank_base_url() 推导）。

约束与降级策略：
    - 百炼 rerank 的确切请求/响应字段以线上为准，调用封装在 _call_bailian_rerank，
      并标注 TODO_REQUIRES_BAILIAN_API_TEST，待联网验证后固化；
    - 测试模式（MOCK_RERANK=true）允许 mock；生产模式禁止随机 rerank；
    - rerank 失败时可 fallback 到“保持原顺序”（视作 embedding 相似度原排序），
      但必须在日志与调用方证据的 reliability_note 中标记 "rerank_failed_fallback_used"。
"""

from __future__ import annotations

import os
from typing import Optional

from app.core.config import Settings, assert_qwen_model, get_settings
from app.core.logging import get_logger, mask_text

# 模块级日志器。
logger = get_logger("clients.rerank")

# fallback 标记：写入日志与 evidence.reliability_note，便于审计。
FALLBACK_MARKER = "rerank_failed_fallback_used"


def _mock_enabled() -> bool:
    """
    判断是否启用 rerank mock 模式（环境变量 MOCK_RERANK=true）。

    返回：
        True 表示启用 mock（仅测试用），返回可预测的排序。
    """
    # 仅测试环境应设置该变量；生产环境严禁 mock。
    return os.getenv("MOCK_RERANK", "").strip().lower() in ("1", "true", "yes")


class RerankClient:
    """重排序客户端：对候选文档按与查询的相关性打分并排序。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        初始化重排序客户端。

        参数：
            settings: 可选注入配置；缺省使用全局单例。
        """
        # 允许注入配置以便测试。
        self.settings = settings or get_settings()
        # 记录使用的重排序模型名（qwen3-rerank）。
        self.model = self.settings.bailian_rerank_model
        # 标记最近一次调用是否触发了 fallback（供调用方读取以写 reliability_note）。
        self.last_used_fallback = False

    def rerank(
        self, query: str, documents: list[str], top_k: int = 5
    ) -> list[tuple[int, float]]:
        """
        对候选文档按与查询的相关性重排序。

        参数：
            query:     查询文本。
            documents: 候选文档文本列表。
            top_k:     返回的前 k 个结果数量。

        返回：
            (原始索引, 相关性分数) 的列表，按分数降序，长度 <= top_k。
            当 rerank 失败并 fallback 时，返回“原顺序 + 分数 0.0”，
            同时将 self.last_used_fallback 置 True 并在日志标记 FALLBACK_MARKER。
        """
        # 每次调用重置 fallback 标记。
        self.last_used_fallback = False

        # 空文档直接返回空结果。
        if not documents:
            return []

        # mock 模式：按“文档在列表中的原顺序”返回递减分数，结果可预测。
        if _mock_enabled():
            logger.debug("rerank 使用 mock 模式：model=%s, n=%d", self.model, len(documents))
            scored = [(i, 1.0 - i * 0.01) for i in range(len(documents))]
            return scored[:top_k]

        # 校验模型名（qwen3-rerank 在白名单内）。
        assert_qwen_model(self.model)

        try:
            # 真实调用封装在私有方法中（字段以线上为准）。
            results = self._call_bailian_rerank(query, documents, top_k)
            return results
        except Exception as exc:
            # 失败时 fallback：保持原顺序，分数置 0.0，并打标记。
            logger.warning(
                "rerank 调用失败，启用 fallback（%s）：%s",
                FALLBACK_MARKER,
                mask_text(str(exc)),
            )
            self.last_used_fallback = True
            fallback = [(i, 0.0) for i in range(len(documents))]
            return fallback[:top_k]

    def _call_bailian_rerank(
        self, query: str, documents: list[str], top_k: int
    ) -> list[tuple[int, float]]:
        """
        调用百炼 qwen3-rerank 的 OpenAI-compatible 重排序接口。

        TODO_REQUIRES_BAILIAN_API_TEST:
            百炼 reranks endpoint 的确切请求体与响应结构需联网实测确认。
            当前实现遵循已公开文档：
                POST {rerank_base_url}
                body: {"model", "query", "documents", "top_n", "return_documents"}
                resp: {"results": [{"index": int, "relevance_score": float}, ...]}
            若线上字段有差异，请在此处调整解析逻辑。

        参数：
            query:     查询文本。
            documents: 候选文档列表。
            top_k:     返回条数。

        返回：
            (原始索引, 相关性分数) 列表，按分数降序。

        异常：
            RuntimeError: 未配置、网络失败或响应结构不符合预期时抛出（供上层 fallback）。
        """
        # 未配置百炼时无法调用，交由上层 fallback。
        if not self.settings.qwen_configured:
            raise RuntimeError("百炼未配置，无法调用 rerank。")

        # 推导 reranks endpoint（与 chat 的路径不同）。
        url = self.settings.rerank_base_url()
        if not url:
            raise RuntimeError("无法推导 rerank endpoint（缺少 WORKSPACE_ID / base_url）。")

        # 使用 requests 直接调用（rerank 非 chat/embeddings 标准方法）。
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("未安装 requests，无法调用 rerank。") from exc

        # 组装请求头与请求体（遵循已公开文档）。
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_k,
            "return_documents": False,
        }
        # 禁用 Windows/环境隐式代理，仅尊重项目显式 OUTBOUND_HTTPS_PROXY。
        session = requests.Session()
        session.trust_env = False
        explicit_proxy = str(getattr(self.settings, "outbound_https_proxy", "") or "").strip()
        if explicit_proxy:
            session.proxies.update({"http": explicit_proxy, "https": explicit_proxy})
        # 发起请求，设置连接/读取超时。
        connect_timeout = float(getattr(self.settings, "llm_connect_timeout_seconds", 20.0))
        resp = session.post(
            url,
            headers=headers,
            json=payload,
            timeout=(connect_timeout, 30),
        )
        # 非 2xx 视为失败，交由上层 fallback。
        if resp.status_code >= 300:
            raise RuntimeError(f"rerank HTTP {resp.status_code}")
        data = resp.json()

        # 解析响应中的 results 列表（index + relevance_score）。
        results_raw = data.get("results")
        if not isinstance(results_raw, list):
            raise RuntimeError("rerank 响应缺少 results 字段（结构不符合预期）。")
        parsed: list[tuple[int, float]] = []
        for item in results_raw:
            idx = item.get("index")
            score = item.get("relevance_score", item.get("score"))
            # 结构不符合预期时抛错，交由上层 fallback。
            if idx is None or score is None:
                raise RuntimeError("rerank 结果项缺少 index/relevance_score。")
            parsed.append((int(idx), float(score)))
        # 按分数降序并截断到 top_k。
        parsed.sort(key=lambda x: x[1], reverse=True)
        return parsed[:top_k]
