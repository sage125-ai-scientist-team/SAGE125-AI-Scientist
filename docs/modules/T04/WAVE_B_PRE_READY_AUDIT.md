# T04 Wave B Pre-Ready Audit

Audit basis: PR #23 at `785d8fa7ee94203ab8c760107b74b6755839cf9c` before this documentation update.

## Completed in T04

- Stable source policy and booklet content-hash registry. The controlled booklet is `BOOKLET` / `QUESTION_SOURCE` and cannot enter the evidentiary user library.
- Provenance-preserving ingestion and retrieval adapter behavior.
- Loader v2 metadata and parse states: `parsed`, `empty`, `needs_ocr`, and `failed`.
- DOI-first/document-hash identity registry and versioned atomic parse cache.
- Validated staging rebuild, writer lock, backup, automatic switch recovery, stale-staging cleanup, and explicit rollback.
- A 30-query provisional retrieval evaluation contract.
- Offline implementations of recall@10, MRR, latency summary, and cache hit rate.
- Controlled archive-to-PDF provenance chain with fixed byte identities and a Windows reproduction procedure.

## Status consistency

The controlled booklet artifact and the retrieval evaluation dataset have different status dimensions:

- Booklet byte identity: verified against the historical review SHA-256; non-synthetic and not a test fixture.
- Booklet corpus status: `NOT_CLAIMED_IN_FORMAL_CORPUS` and `AWAITING_T09_FORMAL_CORPUS_ACCEPTANCE`.
- Retrieval labels: `provisional` contract fixtures.
- Retrieval execution: `not_run`.
- Retrieval metrics: `not_computed`; numeric values remain `null`.
- Formal scientific metric claim: `false`.

No checked-in document claims that provisional labels or unexecuted retrieval results are formal scientific metrics.

## Not completed

- OCR execution for pages classified as `needs_ocr`.
- A controlled real-corpus retrieval run using recorded embedding/rerank versions and an index manifest.
- Verified relevance labels for the 30-query set.
- Non-null recall@10, MRR, latency, or cache-hit metrics.
- Independent isolated reproduction and formal-corpus acceptance.
- Synchronization with the latest `integration/2026-08-10` tip and final CI on the synchronized head.

## Required collaboration

- **T01:** review query-to-document/chunk relevance labels and confirm the downstream adapter boundary.
- **T09:** provide or approve the isolated evaluation environment, record model/index identities, reproduce metrics, and decide formal-corpus acceptance.
- **Captain:** confirm all blocking review items are closed after integration synchronization and current-head CI.

## Ownership audit

PR #23 changes are confined to T04 owner paths:

- `app/rag/**`
- `tests/rag/**`
- `docs/modules/T04/**`

No `app/multimodal/**`, `tests/multimodal/**`, `docs/modules/T06/**`, workflow, API, UI, raw PDF, or archive file is part of the PR diff.

## Ready decision

`NOT_READY`

The implementation and local T04 test suite are prepared for review, but Ready prerequisites are not met until T01 label review, T09 real-run/reproduction evidence, integration synchronization, and current-head CI are complete.
