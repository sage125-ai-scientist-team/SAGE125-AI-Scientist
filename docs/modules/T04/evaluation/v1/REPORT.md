# T04 Retrieval Evaluation v1

## Status

`PROVISIONAL_NOT_RUN`

`NOT_READY_FOR_ACTUAL_EVAL`

This dataset is only a provisional contract fixture. It is not an approved
actual-evaluation relevance gold set and must not be used to produce or claim
formal recall@10 or MRR results.

This package defines the 30-query evaluation contract and the offline metric computation path. It does not claim a formal retrieval score. The repository does not currently contain a completed result produced by a controlled real embedding, rerank, and indexed-corpus environment, so recall@10, MRR, latency, and cache hit rate remain `null` in `metrics.json`.

## Implemented metrics

- Macro recall@10 over the union of annotated document and chunk identifiers.
- Mean reciprocal rank of the first relevant identifier.
- Retrieval latency count, mean, median, and p95 in milliseconds.
- Cache hit rate over completed queries.

The evaluator rejects missing or extra query results, duplicate query IDs, negative/non-finite latency, and non-boolean cache indicators.

## Dataset limitations

The 30 labels are provisional offline contract fixtures. They are not validated scientific relevance judgments and are not claimed to represent the formal corpus. T01 pairing review and T09 independent reproduction remain pending.

## Formal run prerequisites

1. A fixed, reviewable corpus and index manifest.
2. Recorded embedding and rerank model identifiers and configuration.
3. One completed result for every gold query, including ranked IDs, wall-clock latency, and cache-hit state.
4. T01 confirmation of relevance labels.
5. T09 reproduction in an isolated environment.
