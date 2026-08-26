# T06 Wave C — Correction Flow (owner-owned)

1. Extractor raises `ExtractionError` or returns `validation_status` ∈ {needs_review, failed, pending}.
2. Persist only via `put_multimodal_artifact` when artifact is contract-valid; failed status is not enqueued on `MultimodalQueue`.
3. UI/T08 reads `list_multimodal_details` and **must display** `needs_human_review`, confidence, validation_status.
4. Human correction: replace source or labels → re-run adapter → `put_multimodal_artifact` under same `run_id/question_id` new `version_id` (immutability of prior version).
5. Never: invent axis units, legend, or chart points; never treat denied VL as success; never expose absolute paths.
