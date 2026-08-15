"""Local RAG retrieval orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.clients.embedding_client import EmbeddingClient
from app.clients.rerank_client import FALLBACK_MARKER, RerankClient
from app.contracts.rag import RetrievalHit, ScoreKind, SourceRole, SourceType
from app.core.logging import get_logger
from app.rag.evidence import chunk_to_evidence_card, chunk_to_retrieval_hit
from app.rag.zvec_store import SearchResult, VectorStoreProtocol

logger = get_logger("rag.retriever")


class RetrievalError(Exception):
    """Raised when retrieval cannot safely continue."""


@dataclass(frozen=True)
class _RankedHit:
    """One ranked raw hit produced by the shared retrieval core."""

    hit: SearchResult
    rerank_score: float | None
    used_fallback: bool


def _source_provenance(metadata: dict) -> tuple[SourceType, SourceRole]:
    """Consume ingestion provenance and use conservative defaults when absent."""
    try:
        source_type = SourceType(
            str(metadata.get("source_type") or SourceType.UNKNOWN.value).lower()
        )
    except ValueError:
        source_type = SourceType.UNKNOWN

    try:
        source_role = SourceRole(
            str(metadata.get("source_role") or SourceRole.USER_UPLOAD.value).lower()
        )
    except ValueError:
        source_role = SourceRole.USER_UPLOAD

    return source_type, source_role


def _evidence_source_type(source_type: SourceType) -> str:
    """Adapt T04 provenance to the legacy public EvidenceCard vocabulary."""
    if source_type is SourceType.BOOKLET:
        return "booklet"
    if source_type is SourceType.UNKNOWN:
        return "user_upload"
    return "rag"


def _provenance_note(
    metadata: dict, source_type: SourceType, source_role: SourceRole
) -> str:
    """Keep ingestion provenance visible across the legacy EvidenceCard boundary."""
    content_hash = metadata.get("content_hash") or metadata.get("content_sha256") or ""
    source_locator = metadata.get("source_locator")
    if source_locator is None:
        source_locator = {
            key: metadata[key]
            for key in (
                "doc_id",
                "document_id",
                "page",
                "section",
                "char_start",
                "char_end",
                "chunk_id",
            )
            if metadata.get(key) is not None
        }
    return (
        f"source_type={source_type.value}; source_role={source_role.value}; "
        f"source_id={metadata.get('source_id', '')}; content_hash={content_hash}; "
        f"source_locator={source_locator}"
    )


class LocalRAGRetriever:
    """Vector retrieval, reranking, and legacy EvidenceCard adaptation."""

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        rerank_client: RerankClient,
        vector_store: VectorStoreProtocol,
        top_k_vector: int = 30,
        top_k_final: int = 8,
    ) -> None:
        self.embedding_client = embedding_client
        self.rerank_client = rerank_client
        self.vector_store = vector_store
        self.top_k_vector = top_k_vector
        self.top_k_final = top_k_final

    def _scope_filters(
        self, source_scope: str, filters: Optional[dict]
    ) -> Optional[dict]:
        merged = dict(filters) if filters else {}
        if source_scope == "booklet":
            merged["source_type"] = SourceType.BOOKLET.value
        elif source_scope == "user_upload":
            merged["source_role"] = SourceRole.USER_UPLOAD.value
        return merged or None

    def retrieve(
        self,
        query: str,
        filters: Optional[dict] = None,
        source_scope: str = "all",
    ) -> list:
        ranked_hits = self._retrieve_ranked(query, filters, source_scope)
        if not ranked_hits:
            return []

        normalized_query = " ".join((query or "").split())
        evidence_cards = []
        for ranked_hit in ranked_hits:
            hit = ranked_hit.hit
            source_type, source_role = _source_provenance(hit.metadata)
            note_parts = [
                _provenance_note(hit.metadata, source_type, source_role)
            ]
            if ranked_hit.used_fallback:
                note_parts.append(FALLBACK_MARKER)
            card = chunk_to_evidence_card(
                {
                    "text": hit.text,
                    "metadata": hit.metadata,
                    "chunk_id": hit.chunk_id,
                },
                score=hit.score,
                source_type=_evidence_source_type(source_type),
                query=normalized_query,
                rerank_score=ranked_hit.rerank_score,
                reliability_note_extra="; ".join(note_parts),
            )
            evidence_cards.append(card)
        return evidence_cards

    def retrieve_hits(
        self,
        query: str,
        filters: Optional[dict] = None,
        source_scope: str = "all",
    ) -> tuple[RetrievalHit, ...]:
        """Return lossless, provenance-validated retrieval hits."""

        ranked_hits = self._retrieve_ranked(query, filters, source_scope)
        validated: list[RetrievalHit] = []
        try:
            for ranked_hit in ranked_hits:
                hit = ranked_hit.hit
                if not str(hit.metadata.get("source_id") or "").strip():
                    raise ValueError("persisted source_id is required")
                if ranked_hit.rerank_score is None:
                    score = hit.score
                    score_kind = hit.metadata.get(
                        "score_kind", ScoreKind.VECTOR_SIMILARITY
                    )
                else:
                    score = ranked_hit.rerank_score
                    score_kind = ScoreKind.RERANK_SCORE
                validated.append(
                    chunk_to_retrieval_hit(
                        {
                            "text": hit.text,
                            "metadata": hit.metadata,
                            "chunk_id": hit.chunk_id,
                        },
                        score=score,
                        score_kind=score_kind,
                    )
                )
        except (TypeError, ValueError) as exc:
            raise RetrievalError(f"invalid persisted retrieval provenance: {exc}") from None
        return tuple(validated)

    def _retrieve_ranked(
        self,
        query: str,
        filters: Optional[dict],
        source_scope: str,
    ) -> tuple[_RankedHit, ...]:
        """Run normalization, embedding, search, rerank, fallback, and top-k once."""

        query = " ".join((query or "").split())
        if not query:
            raise ValueError("query must not be empty")

        try:
            query_vectors = self.embedding_client.embed_texts([query])
        except Exception as exc:
            raise RetrievalError(f"query embedding failed: {exc}") from None
        if not query_vectors:
            raise RetrievalError("query embedding returned no vectors")
        query_embedding = query_vectors[0]

        scope_filters = self._scope_filters(source_scope, filters)
        hits: list[SearchResult] = self.vector_store.search(
            query_embedding, top_k=self.top_k_vector, filters=scope_filters
        )
        if not hits:
            logger.info(
                "retrieval returned no results: query=%s, scope=%s",
                query[:60],
                source_scope,
            )
            return ()

        documents = [hit.text for hit in hits]
        ranked = self.rerank_client.rerank(
            query, documents, top_k=self.top_k_final
        )
        used_fallback = self.rerank_client.last_used_fallback

        ranked_hits = []
        for original_idx, rerank_result_score in ranked:
            hit = hits[original_idx]
            rerank_score = None if used_fallback else rerank_result_score
            ranked_hits.append(_RankedHit(hit, rerank_score, used_fallback))

        logger.info(
            "retrieval complete: query=%s, top_k_vector=%d, "
            "top_k_final=%d, result_count=%d, rerank_fallback=%s",
            query[:60],
            self.top_k_vector,
            self.top_k_final,
            len(ranked_hits),
            used_fallback,
        )
        return tuple(ranked_hits)
