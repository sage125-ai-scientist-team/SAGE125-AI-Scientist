# Reproduce T04 Retrieval Metrics

The checked-in `evaluation_result.json` is intentionally `not_run`. Running the command against that template must fail instead of creating synthetic metric values.

After a controlled retrieval run produces a JSON file with `status: "completed"` and exactly 30 query records, compute metrics with:

```powershell
python -m app.rag.evaluation `
  --gold tests/rag/fixtures/retrieval_gold_v1.json `
  --results path/to/completed_evaluation_result.json `
  --output path/to/computed_metrics.json `
  --k 10
```

Each item in `queries` must contain:

```json
{
  "query_id": "GQ001",
  "retrieved_ids": ["ranked-document-or-chunk-id"],
  "latency_ms": 0.0,
  "cache_hit": false
}
```

Verify the checked-in gold fixture before a run:

```powershell
$expected = "6b777359e43ff6c7241ef9489f30cd4438640c2c59ad66450b3bc923eca7a11a"
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath tests/rag/fixtures/retrieval_gold_v1.json).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "retrieval gold SHA-256 mismatch" }
```

Do not promote provisional metrics to formal scientific metrics until the corpus, relevance annotations, model configuration, and independent reproduction have been reviewed.
