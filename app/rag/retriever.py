"""
app.rag.retriever —— 本地 RAG 检索器。

编排 EmbeddingClient -> VectorStore.search -> RerankClient -> EvidenceCard，
为多智能体 pipeline 提供可靠、可追溯的证据。

关键约束：
    - query embedding 失败抛出 RetrievalError，绝不伪造 embedding；
    - rerank 失败则使用向量原排序，并在每张 EvidenceCard 的 reliability_note
      标记 "rerank_failed_fallback_used"；
    - 每张 EvidenceCard 均含 quoted_text/source_type/title/relevance_score/reliability_note。
"""

from __future__ import annotations

from typing import Optional

from app.clients.embedding_client import EmbeddingClient
from app.clients.rerank_client import FALLBACK_MARKER, RerankClient
from app.core.logging import get_logger
from app.rag.evidence import chunk_to_evidence_card
from app.rag.zvec_store import SearchResult, VectorStoreProtocol

# 模块级日志器。
logger = get_logger("rag.retriever")

# source_scope 到 metadata 过滤条件的映射说明见 retrieve()。


class RetrievalError(Exception):
    """检索过程失败（如 embedding 失败）时抛出。"""


class LocalRAGRetriever:
    """本地 RAG 检索器：向量召回 + 重排序 + 证据转换。"""

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        rerank_client: RerankClient,
        vector_store: VectorStoreProtocol,
        top_k_vector: int = 30,
        top_k_final: int = 8,
    ) -> None:
        """
        初始化检索器。

        参数：
            embedding_client: 嵌入客户端。
            rerank_client:    重排序客户端。
            vector_store:     向量存储（Zvec 或 Memory）。
            top_k_vector:     向量召回条数。
            top_k_final:      重排序后最终返回条数。
        """
        # 保存依赖与参数。
        self.embedding_client = embedding_client
        self.rerank_client = rerank_client
        self.vector_store = vector_store
        self.top_k_vector = top_k_vector
        self.top_k_final = top_k_final

    def _scope_filters(self, source_scope: str, filters: Optional[dict]) -> Optional[dict]:
        """
        根据 source_scope 生成/合并元数据过滤条件。

        参数：
            source_scope: "booklet" / "user_upload" / "all"。
            filters:      调用方额外过滤条件。

        返回：
            合并后的过滤字典或 None。
        """
        # 拷贝调用方过滤条件，避免副作用。
        merged = dict(filters) if filters else {}
        # booklet：仅非用户上传的 PDF；user_upload：仅用户上传文件。
        if source_scope == "booklet":
            merged["is_user_upload"] = False
        elif source_scope == "user_upload":
            merged["is_user_upload"] = True
        # "all" 不追加范围过滤。
        return merged or None

    def retrieve(
        self,
        query: str,
        filters: Optional[dict] = None,
        source_scope: str = "all",
    ) -> list:
        """
        执行检索并返回 EvidenceCard 列表。

        参数：
            query:        查询文本。
            filters:      额外元数据过滤。
            source_scope: 检索范围（booklet/user_upload/all）。

        返回：
            EvidenceCard 列表（长度 <= top_k_final）。

        异常：
            ValueError:     query 为空时抛出。
            RetrievalError: embedding 失败时抛出（不伪造向量）。
        """
        # query 清理与非空校验。
        query = " ".join((query or "").split())
        if not query:
            raise ValueError("query 不能为空。")

        # query embedding，失败即抛出（禁止伪造）。
        try:
            query_vectors = self.embedding_client.embed_texts([query])
        except Exception as exc:
            raise RetrievalError(f"query embedding 失败：{exc}") from None
        if not query_vectors:
            raise RetrievalError("query embedding 返回空。")
        query_embedding = query_vectors[0]

        # 向量检索。
        scope_filters = self._scope_filters(source_scope, filters)
        hits: list[SearchResult] = self.vector_store.search(
            query_embedding, top_k=self.top_k_vector, filters=scope_filters
        )
        # 无结果返回空（不报错）。
        if not hits:
            logger.info("检索无结果：query=%s，scope=%s", query[:60], source_scope)
            return []

        # 重排序。
        documents = [h.text for h in hits]
        ranked = self.rerank_client.rerank(query, documents, top_k=self.top_k_final)
        used_fallback = self.rerank_client.last_used_fallback

        # 依据 rerank 结果重排 hits；fallback 时保持向量原顺序。
        evidence_cards = []
        for original_idx, rr_score in ranked:
            hit = hits[original_idx]
            # rerank 成功用 rr_score；fallback 用向量分数。
            rerank_score = None if used_fallback else rr_score
            extra_note = FALLBACK_MARKER if used_fallback else None
            # 决定 source_type；即使误连旧索引，也把题源显式标成 booklet，
            # 让质量门拒绝其进入研究证据/References。
            source_name = str(hit.metadata.get("source_name") or "").lower()
            source_role = str(hit.metadata.get("source_role") or "").lower()
            if hit.metadata.get("is_user_upload"):
                src_type = "user_upload"
            elif source_role == "question_source" or source_name == "sjtu-booklet.pdf":
                src_type = "booklet"
            else:
                src_type = "rag"
            card = chunk_to_evidence_card(
                {"text": hit.text, "metadata": hit.metadata, "chunk_id": hit.chunk_id},
                score=hit.score,
                source_type=src_type,
                query=query,
                rerank_score=rerank_score,
                reliability_note_extra=extra_note,
            )
            evidence_cards.append(card)

        # 查询日志（不含 API Key）。
        logger.info(
            "检索完成：query=%s，top_k_vector=%d，top_k_final=%d，result_count=%d，rerank_fallback=%s",
            query[:60],
            self.top_k_vector,
            self.top_k_final,
            len(evidence_cards),
            used_fallback,
        )
        return evidence_cards
