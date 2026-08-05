"""Retrieval metric formulas and provisional dataset contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rag.evaluation import (
    RetrievalEvaluationError,
    cache_hit_rate,
    evaluate_retrieval,
    latency_summary,
    mean_reciprocal_rank,
    recall_at_k,
)


GOLD_PATH = Path("tests/rag/fixtures/retrieval_gold_v1.json")


def _gold():
    return [
        {
            "query_id": "Q1",
            "query": "first",
            "domain": "test",
            "relevant_document_ids": ["D1"],
            "relevant_chunk_ids": ["C1"],
            "annotation_status": "provisional",
            "version": "1.0",
        },
        {
            "query_id": "Q2",
            "query": "second",
            "domain": "test",
            "relevant_document_ids": ["D2"],
            "relevant_chunk_ids": [],
            "annotation_status": "verified",
            "version": "1.0",
        },
    ]


def _results():
    return [
        {
            "query_id": "Q1",
            "retrieved_ids": ["X", "C1", "D1"],
            "latency_ms": 10.0,
            "cache_hit": True,
        },
        {
            "query_id": "Q2",
            "retrieved_ids": ["X", "Y"],
            "latency_ms": 30.0,
            "cache_hit": False,
        },
    ]


def test_recall_mrr_latency_and_cache_hit_rate():
    gold = _gold()
    results = _results()

    assert recall_at_k(gold, results, k=10) == pytest.approx(0.5)
    assert mean_reciprocal_rank(gold, results) == pytest.approx(0.25)
    assert latency_summary(results) == {
        "count": 2,
        "mean_ms": 20.0,
        "median_ms": 20.0,
        "p95_ms": 30.0,
    }
    assert cache_hit_rate(results) == pytest.approx(0.5)

    metrics = evaluate_retrieval(gold, results)
    assert metrics["query_count"] == 2
    assert metrics["provisional"] is True
    assert metrics["formal_scientific_metric_claim"] is False


def test_incomplete_result_set_is_rejected():
    with pytest.raises(RetrievalEvaluationError, match="cover the gold query set"):
        evaluate_retrieval(_gold(), _results()[:1])


def test_retrieval_gold_v1_has_30_complete_provisional_queries():
    dataset = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    assert len(dataset) == 30
    assert len({item["query_id"] for item in dataset}) == 30
    required = {
        "query",
        "domain",
        "relevant_document_ids",
        "relevant_chunk_ids",
        "annotation_status",
        "version",
    }
    for item in dataset:
        assert required.issubset(item)
        assert item["query"].strip()
        assert item["domain"].strip()
        assert item["relevant_document_ids"] or item["relevant_chunk_ids"]
        assert item["annotation_status"] == "provisional"
        assert item["version"] == "1.0"
