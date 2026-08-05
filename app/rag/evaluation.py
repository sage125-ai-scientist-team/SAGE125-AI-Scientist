"""Offline, reproducible retrieval metrics for T04 Wave B."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


class RetrievalEvaluationError(ValueError):
    """Raised when gold annotations or retrieval results are incomplete."""


def _ids(values: Iterable[Any]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _relevant_ids(query: dict[str, Any]) -> set[str]:
    return set(_ids(query.get("relevant_document_ids", []))) | set(
        _ids(query.get("relevant_chunk_ids", []))
    )


def _validate_gold(gold: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not gold:
        raise RetrievalEvaluationError("gold dataset must not be empty")
    indexed: dict[str, dict[str, Any]] = {}
    required = {
        "query_id",
        "query",
        "domain",
        "relevant_document_ids",
        "relevant_chunk_ids",
        "annotation_status",
        "version",
    }
    for position, item in enumerate(gold, start=1):
        missing = required - item.keys()
        if missing:
            raise RetrievalEvaluationError(
                f"gold query {position} missing fields: {sorted(missing)}"
            )
        query_id = str(item["query_id"]).strip()
        if not query_id or query_id in indexed:
            raise RetrievalEvaluationError(f"invalid or duplicate query_id: {query_id}")
        if not _relevant_ids(item):
            raise RetrievalEvaluationError(f"gold query {query_id} has no relevant ids")
        indexed[query_id] = item
    return indexed


def _validate_results(
    results: list[dict[str, Any]], expected_ids: set[str]
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in results:
        query_id = str(item.get("query_id") or "").strip()
        if not query_id or query_id in indexed:
            raise RetrievalEvaluationError(
                f"invalid or duplicate result query_id: {query_id}"
            )
        latency = float(item.get("latency_ms", -1))
        if not math.isfinite(latency) or latency < 0:
            raise RetrievalEvaluationError(
                f"result {query_id} latency_ms must be finite and non-negative"
            )
        if not isinstance(item.get("cache_hit"), bool):
            raise RetrievalEvaluationError(
                f"result {query_id} cache_hit must be boolean"
            )
        if not isinstance(item.get("retrieved_ids"), list):
            raise RetrievalEvaluationError(
                f"result {query_id} retrieved_ids must be a list"
            )
        indexed[query_id] = item
    actual_ids = set(indexed)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise RetrievalEvaluationError(
            f"results must cover the gold query set; missing={missing}, extra={extra}"
        )
    return indexed


def recall_at_k(
    gold: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    k: int = 10,
) -> float:
    """Return macro recall over relevant document and chunk identifiers."""
    if k <= 0:
        raise ValueError("k must be positive")
    gold_by_id = _validate_gold(gold)
    results_by_id = _validate_results(results, set(gold_by_id))
    values = []
    for query_id, annotation in gold_by_id.items():
        relevant = _relevant_ids(annotation)
        retrieved = set(_ids(results_by_id[query_id]["retrieved_ids"][:k]))
        values.append(len(relevant & retrieved) / len(relevant))
    return mean(values)


def mean_reciprocal_rank(
    gold: list[dict[str, Any]], results: list[dict[str, Any]]
) -> float:
    """Return the mean reciprocal rank of the first relevant identifier."""
    gold_by_id = _validate_gold(gold)
    results_by_id = _validate_results(results, set(gold_by_id))
    reciprocal_ranks: list[float] = []
    for query_id, annotation in gold_by_id.items():
        relevant = _relevant_ids(annotation)
        rank = next(
            (
                index
                for index, item in enumerate(
                    _ids(results_by_id[query_id]["retrieved_ids"]), start=1
                )
                if item in relevant
            ),
            None,
        )
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)
    return mean(reciprocal_ranks)


def latency_summary(results: list[dict[str, Any]]) -> dict[str, float | int]:
    """Summarize per-query wall-clock retrieval latency in milliseconds."""
    if not results:
        raise RetrievalEvaluationError("results must not be empty")
    values = sorted(float(item["latency_ms"]) for item in results)
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise RetrievalEvaluationError("latency_ms must be finite and non-negative")
    p95_index = max(0, math.ceil(0.95 * len(values)) - 1)
    return {
        "count": len(values),
        "mean_ms": mean(values),
        "median_ms": median(values),
        "p95_ms": values[p95_index],
    }


def cache_hit_rate(results: list[dict[str, Any]]) -> float:
    """Return cache hits divided by completed retrieval queries."""
    if not results:
        raise RetrievalEvaluationError("results must not be empty")
    if any(not isinstance(item.get("cache_hit"), bool) for item in results):
        raise RetrievalEvaluationError("cache_hit must be boolean")
    return sum(bool(item["cache_hit"]) for item in results) / len(results)


def evaluate_retrieval(
    gold: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    k: int = 10,
) -> dict[str, Any]:
    """Compute auditable metrics without performing retrieval or network calls."""
    gold_by_id = _validate_gold(gold)
    _validate_results(results, set(gold_by_id))
    provisional = any(
        str(item["annotation_status"]).lower() != "verified" for item in gold
    )
    return {
        "status": "computed",
        "query_count": len(gold),
        "cutoff": k,
        "recall_at_10": recall_at_k(gold, results, k=k),
        "mrr": mean_reciprocal_rank(gold, results),
        "latency": latency_summary(results),
        "cache_hit_rate": cache_hit_rate(results),
        "provisional": provisional,
        "formal_scientific_metric_claim": False,
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute T04 retrieval metrics")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args(argv)

    gold = _read_json(args.gold)
    result_payload = _read_json(args.results)
    if result_payload.get("status") != "completed":
        raise RetrievalEvaluationError(
            "results status must be completed; provisional not_run templates cannot produce metrics"
        )
    metrics = evaluate_retrieval(gold, result_payload.get("queries", []), k=args.k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
