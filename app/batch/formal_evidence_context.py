"""Fail-closed T04-to-T01 evidence context for formal T07 runs.

The adapter accepts only lossless T04 ``RetrievalHit`` values.  It never asks
the report-writing model to create provenance and never upgrades the question
booklet, fixtures, metadata-only records, or incomplete retrieval results into
research evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError

from app.batch.errors import BatchRunnerError
from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.contracts.rag import (
    RetrievalHit,
    ScoreKind,
    SourceRole,
    SourceType,
    coerce_retrieval_hit,
)
from app.evidence import (
    ClaimText,
    evidence_card_to_validation_wire,
    precheck_bundle_for_validation,
)


class FormalRetrievalPort(Protocol):
    """T04-compatible retrieval boundary required by the formal adapter."""

    def retrieve(
        self,
        query: str,
        filters: Mapping[str, Any] | None = None,
        source_scope: str = "user_upload",
    ) -> Sequence[RetrievalHit | Mapping[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class FormalEvidenceQuery:
    question_id: str
    run_id: str
    question: str
    domain: str | None


@dataclass(frozen=True, slots=True)
class FormalEvidenceContext:
    """Trusted evidence that exists before the report-writing provider call."""

    bundle: EvidenceBundle
    cards: tuple[Mapping[str, Any], ...]

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(card.evidence_id for card in self.bundle.evidences)


@dataclass(frozen=True, slots=True)
class _PrecheckContext:
    evidence_cards: tuple[Mapping[str, Any], ...]


class FormalEvidenceContextAdapter:
    """Build and T01-precheck trusted evidence before any Qwen boundary."""

    def __init__(self, retriever: FormalRetrievalPort | None = None) -> None:
        self._retriever = retriever

    def build(self, query: FormalEvidenceQuery) -> FormalEvidenceContext:
        if self._retriever is None:
            raise _unavailable("EVIDENCE_RETRIEVER_UNAVAILABLE")
        try:
            raw_hits = self._retriever.retrieve(
                query.question,
                filters={"source_role": SourceRole.USER_UPLOAD.value},
                source_scope="user_upload",
            )
        except Exception:
            raise _unavailable("EVIDENCE_RETRIEVAL_FAILED") from None
        if isinstance(raw_hits, (str, bytes)) or not isinstance(raw_hits, Sequence):
            raise _unavailable("EVIDENCE_RETRIEVAL_RESULT_INVALID")
        if not raw_hits:
            raise _unavailable("EVIDENCE_CONTEXT_EMPTY")

        contracts: list[EvidenceCardContract] = []
        wires: list[Mapping[str, Any]] = []
        claims: list[ClaimText] = []
        links: list[ClaimEvidenceLink] = []
        seen_ids: set[str] = set()
        for index, raw_hit in enumerate(raw_hits):
            hit = _validated_hit(raw_hit)
            _reject_untrusted_source(hit)
            contract = _hit_to_contract(query, hit)
            if contract.evidence_id in seen_ids:
                raise _unavailable("EVIDENCE_ID_DUPLICATE")
            seen_ids.add(contract.evidence_id)
            contracts.append(contract)

            wire = evidence_card_to_validation_wire(
                contract,
                run_id=query.run_id,
                version_id=query.run_id,
                question_id=query.question_id,
            )
            wire.update(
                {
                    "source_role": hit.source_role.value,
                    "source_content_hash": hit.content_hash,
                    "retrieval_score": hit.retrieval_score,
                    "score_kind": hit.score_kind.value,
                    "relevance_score": _t03_relevance(hit),
                }
            )
            wires.append(wire)

            claim_id = f"{query.question_id}-evidence-context-{index + 1}"
            claims.append(
                ClaimText(
                    claim_id=claim_id,
                    text=contract.quoted_text,
                    evidence_ids=(contract.evidence_id,),
                    domain=query.domain,
                )
            )
            links.append(
                ClaimEvidenceLink(
                    claim_id=claim_id,
                    evidence_id=contract.evidence_id,
                    relation="supports",
                    confidence=0.5,
                    claim_domain=query.domain,
                    validation_status="pending",
                )
            )

        bundle = EvidenceBundle(
            bundle_id=f"{query.run_id}:trusted-evidence",
            evidences=contracts,
            links=links,
            token_budget=8000,
        )
        precheck = precheck_bundle_for_validation(
            bundle=bundle,
            claims=claims,
            context=_PrecheckContext(tuple(wires)),  # type: ignore[arg-type]
        )
        if (
            not precheck.gate.passed
            or precheck.field_loss
            or precheck.support_codes
        ):
            raise _unavailable("T01_EVIDENCE_PRECHECK_FAILED")
        return FormalEvidenceContext(bundle=bundle, cards=tuple(wires))


def _validated_hit(value: RetrievalHit | Mapping[str, Any]) -> RetrievalHit:
    try:
        return coerce_retrieval_hit(value)
    except (TypeError, ValueError, ValidationError):
        raise _unavailable("T04_RETRIEVAL_HIT_INVALID") from None


def _reject_untrusted_source(hit: RetrievalHit) -> None:
    if (
        hit.source_type is SourceType.BOOKLET
        or hit.source_role is SourceRole.QUESTION_SOURCE
    ):
        raise _unavailable("BOOKLET_EVIDENCE_FORBIDDEN")
    if hit.source_type is SourceType.UNKNOWN:
        raise _unavailable("EVIDENCE_SOURCE_TYPE_UNTRUSTED")
    if hit.source_role is SourceRole.SYSTEM_FIXTURE:
        raise _unavailable("FIXTURE_EVIDENCE_FORBIDDEN")


def _hit_to_contract(
    query: FormalEvidenceQuery,
    hit: RetrievalHit,
) -> EvidenceCardContract:
    quoted_text = hit.quoted_text.strip()
    title = hit.title.strip()
    if not quoted_text:
        raise _unavailable("EVIDENCE_QUOTE_MISSING")
    if _normalized_text(quoted_text) == _normalized_text(title):
        raise _unavailable("EVIDENCE_METADATA_ONLY")

    authors_value = hit.metadata.get("authors")
    authors = (
        [str(item).strip() for item in authors_value if str(item).strip()]
        if isinstance(authors_value, list)
        else []
    )
    year_value = hit.metadata.get("year")
    year = year_value if type(year_value) is int else None
    locator = hit.source_locator.model_dump(
        mode="json",
        exclude_none=True,
        exclude_computed_fields=True,
    )
    locator["document"] = hit.source_locator.document_id
    if hit.source_locator.chunk_id:
        locator["chunk"] = hit.source_locator.chunk_id
    source_type = {
        SourceType.PAPER: "paper",
        SourceType.WEB: "web",
        SourceType.DATASET: "dataset",
    }.get(hit.source_type)
    if source_type is None:
        raise _unavailable("EVIDENCE_SOURCE_TYPE_UNTRUSTED")

    quote_hash = hashlib.sha256(quoted_text.encode("utf-8")).hexdigest()
    identity = json.dumps(
        {
            "chunk_id": hit.chunk_id,
            "quote_hash": quote_hash,
            "source_id": hit.source_locator.document_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    evidence_id = "EV-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return EvidenceCardContract(
        evidence_id=evidence_id,
        source_id=hit.source_locator.document_id,
        source_type=source_type,  # type: ignore[arg-type]
        title=title,
        quoted_text=quoted_text,
        locator=locator,
        authors=authors,
        year=year,
        doi=hit.doi,
        url=hit.url,
        content_hash=f"sha256:{quote_hash}",
        domain=query.domain,
        verification_status="pending",
    )


def _t03_relevance(hit: RetrievalHit) -> float | None:
    if (
        hit.score_kind is ScoreKind.VECTOR_SIMILARITY
        and 0.0 <= hit.retrieval_score <= 1.0
    ):
        return hit.retrieval_score
    return None


def _normalized_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _unavailable(validation_code: str) -> BatchRunnerError:
    return BatchRunnerError(
        "FORMAL_EVIDENCE_CONTEXT_UNAVAILABLE",
        "trusted evidence context is unavailable for formal execution",
        stage="evidence_context",
        exception_type="EvidenceContextError",
        diagnostic_details={"validation_code": validation_code},
    )
