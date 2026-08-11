"""Offline tests for the trusted T04-to-T01 formal evidence adapter."""

from __future__ import annotations

import hashlib

import pytest

from app.batch.errors import BatchRunnerError
from app.batch.formal_evidence_context import (
    FormalEvidenceContextAdapter,
    FormalEvidenceQuery,
)
from app.contracts.rag import (
    RetrievalHit,
    ScoreKind,
    SourceLocator,
    SourceRole,
    SourceType,
)
from app.workflow.quality_gates import run_all_quality_gates


class _Retriever:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def retrieve(self, query, filters=None, source_scope="user_upload"):
        self.calls.append((query, filters, source_scope))
        return self.hits


def _query() -> FormalEvidenceQuery:
    return FormalEvidenceQuery(
        question_id="Q001",
        run_id="formal-run-001",
        question="What makes prime numbers so special?",
        domain="Mathematical Sciences",
    )


def _hit(**updates) -> RetrievalHit:
    payload = {
        "chunk_id": "paper-001-chunk-04",
        "quoted_text": (
            "Every integer greater than one can be represented uniquely as a "
            "product of prime numbers, apart from ordering."
        ),
        "retrieval_score": 0.91,
        "score_kind": ScoreKind.VECTOR_SIMILARITY,
        "source_type": SourceType.PAPER,
        "source_role": SourceRole.USER_UPLOAD,
        "source_locator": SourceLocator(
            document_id="paper-001",
            page=4,
            section="Fundamental theorem of arithmetic",
            chunk_id="paper-001-chunk-04",
        ),
        "content_hash": "c" * 64,
        "title": "Unique factorization into prime numbers",
        "doi": "10.1000/prime.001",
        "url": "https://example.test/paper-001",
        "metadata": {"authors": ["A. Mathematician"], "year": 2024},
    }
    payload.update(updates)
    return RetrievalHit.model_validate(payload)


def test_missing_retriever_fails_before_evidence_context_exists() -> None:
    with pytest.raises(BatchRunnerError) as captured:
        FormalEvidenceContextAdapter().build(_query())

    assert captured.value.error_code == "FORMAL_EVIDENCE_CONTEXT_UNAVAILABLE"
    assert captured.value.diagnostic_details == {
        "validation_code": "EVIDENCE_RETRIEVER_UNAVAILABLE"
    }


def test_empty_retrieval_fails_closed() -> None:
    with pytest.raises(BatchRunnerError) as captured:
        FormalEvidenceContextAdapter(_Retriever([])).build(_query())

    assert captured.value.diagnostic_details == {
        "validation_code": "EVIDENCE_CONTEXT_EMPTY"
    }


def test_trusted_hit_builds_bundle_and_runtime_quote_hash() -> None:
    hit = _hit()
    retriever = _Retriever([hit])

    context = FormalEvidenceContextAdapter(retriever).build(_query())

    assert retriever.calls == [
        (
            _query().question,
            {"source_role": "user_upload"},
            "user_upload",
        )
    ]
    card = context.bundle.evidences[0]
    expected = hashlib.sha256(card.quoted_text.encode("utf-8")).hexdigest()
    assert card.content_hash == f"sha256:{expected}"
    assert card.content_hash != f"sha256:{hit.content_hash}"
    assert context.cards[0]["source_content_hash"] == hit.content_hash
    assert context.cards[0]["locator"]["page"] == 4


@pytest.mark.parametrize(
    ("updates", "validation_code"),
    [
        (
            {
                "source_type": SourceType.BOOKLET,
                "source_role": SourceRole.QUESTION_SOURCE,
            },
            "BOOKLET_EVIDENCE_FORBIDDEN",
        ),
        ({"source_type": SourceType.UNKNOWN}, "EVIDENCE_SOURCE_TYPE_UNTRUSTED"),
        ({"source_role": SourceRole.SYSTEM_FIXTURE}, "FIXTURE_EVIDENCE_FORBIDDEN"),
    ],
)
def test_untrusted_source_is_rejected(updates, validation_code) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        FormalEvidenceContextAdapter(_Retriever([_hit(**updates)])).build(_query())

    assert captured.value.diagnostic_details == {
        "validation_code": validation_code
    }


def test_metadata_only_quote_is_rejected() -> None:
    title = "Metadata title without a verified passage"
    with pytest.raises(BatchRunnerError) as captured:
        FormalEvidenceContextAdapter(
            _Retriever([_hit(title=title, quoted_text=title)])
        ).build(_query())

    assert captured.value.diagnostic_details == {
        "validation_code": "EVIDENCE_METADATA_ONLY"
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quoted_text", ""),
        ("source_locator", {}),
        ("content_hash", "not-a-sha256"),
    ],
)
def test_missing_quote_locator_or_source_hash_is_rejected_at_t04_boundary(
    field,
    value,
) -> None:
    raw = _hit().model_dump(mode="json")
    raw[field] = value

    with pytest.raises(BatchRunnerError) as captured:
        FormalEvidenceContextAdapter(_Retriever([raw])).build(_query())

    assert captured.value.diagnostic_details == {
        "validation_code": "T04_RETRIEVAL_HIT_INVALID"
    }


def test_t01_precheck_failure_rejects_incomplete_provenance() -> None:
    hit = _hit(metadata={"authors": [], "year": 2024})

    with pytest.raises(BatchRunnerError) as captured:
        FormalEvidenceContextAdapter(_Retriever([hit])).build(_query())

    assert captured.value.diagnostic_details == {
        "validation_code": "T01_EVIDENCE_PRECHECK_FAILED"
    }


def test_valid_bundle_and_binding_enter_t03_without_evidence_errors() -> None:
    context = FormalEvidenceContextAdapter(_Retriever([_hit()])).build(_query())
    evidence_id = context.evidence_ids[0]
    plan = {
        "actual_execution": False,
        "results": "待执行验证实验",
        "datasets": {"source": "trusted evidence", "target": "analysis"},
        "experiments": {"baselines": [], "metrics": []},
        "reproducibility_checklist": ["preserve evidence IDs"],
        "generated_hypotheses": [
            {
                "hypothesis": "Prime numbers define unique integer factorization.",
                "supporting_evidence_ids": [evidence_id],
                "contradicted_by_evidence_ids": [],
            }
        ],
        "references": [dict(context.cards[0])],
    }

    result = run_all_quality_gates(
        plan,
        list(context.cards),
        [{"agent_name": "offline", "model_name": "qwen3.6-flash"}],
    )

    assert result["gates"]["evidence_grounding"]["passed"]
    assert result["gates"]["reference_integrity"]["passed"]
