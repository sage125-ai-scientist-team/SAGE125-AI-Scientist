# T07 WB5 Formal Evidence Context Adapter

Date: 2026-08-08  
Scope: offline interface and source audit; no Provider call or formal question run

## Latest deterministic failure

Run `20260808-025522/T07-WB5-20260807-v2/Q001` persisted:

```json
{
  "schema_version": "t07.provider-failure-diagnostic.v1",
  "error_code": "FORMAL_PROVIDER_EVIDENCE_INVALID",
  "http_status": null,
  "stage": "response_validation",
  "exception_type": "EvidenceContractError",
  "validation_code": "EVIDENCE_CARDS_MISSING"
}
```

The response did not provide a non-empty EvidenceCard collection. Requiring a
JSON object or repeating prompt field names cannot establish provenance.

## Public integration interfaces

T04 currently publishes:

- `app.contracts.rag.RetrievalHit` and `SourceLocator`: lossless quote,
  structured locator, source type/role, document content hash, and score kind.
- `app.contracts.rag.coerce_retrieval_hit()`: strict boundary validation.
- `app.rag.evidence.chunk_to_retrieval_hit()`: chunk-to-contract adapter.
- `app.rag.retriever.LocalRAGRetriever.retrieve()`: operational retrieval, but
  its current return value is the legacy runtime EvidenceCard rather than
  `RetrievalHit`; therefore it is not accepted directly by the formal adapter.
- `app.rag.open_literature_retriever.OpenLiteratureRetriever.search()`: an
  external, legacy EvidenceCard path. It is not an approved offline evidence
  snapshot and is not invoked by the formal adapter.

T01 currently publishes:

- `EvidenceCardContract`, `ClaimEvidenceLink`, and `EvidenceBundle`.
- `evidence_card_to_validation_wire()` for a lossless T03 projection.
- `precheck_bundle_for_validation()` and its `gate`, `field_loss`, and
  `support_codes` results.
- `build_evidence_bundle()` for legacy runtime cards. The builder reports
  missing fields but can create fallback quote/locator values, so the formal
  adapter does not use those fallbacks as trusted evidence.

No T01 or T04 implementation is changed by this work.

## Current Q001 source availability

The inspected workspace has no `data/index/user_library`, no user-library
`chunks.jsonl`, and no files in `data/raw/uploads`. The only local PDF is the
controlled SJTU question booklet, whose T04 role is `QUESTION_SOURCE`; it is
forbidden as research evidence. Consequently, no approved real EvidenceBundle
for Q001 is currently available.

## Adapter boundary

`app.batch.formal_evidence_context.FormalEvidenceContextAdapter` consumes only
validated T04 `RetrievalHit` objects supplied through an injected retrieval
port. Before the report-writing Provider boundary it:

1. requires a non-empty retrieval result;
2. rejects booklet, question-source, fixture, unknown-source, metadata-only,
   missing quote/locator/hash, and invalid T04 results;
3. preserves the exact quote, structured locator, source ID and source hash;
4. computes the T01 quote `content_hash` in runtime;
5. constructs `EvidenceCardContract`, `EvidenceBundle`, and lossless T03 wires;
6. executes T01 precheck and rejects failed gates, field loss, or support codes;
7. returns `FORMAL_EVIDENCE_CONTEXT_UNAVAILABLE` before client construction if
   any requirement fails.

The Provider receives the trusted context and may output only hypotheses,
`supporting_evidence_ids`, contradiction IDs, and reference IDs. Runtime rejects
unknown IDs and any attempt to return or rewrite EvidenceCards, quote, locator,
source ID/type, or content hash. Completion-gate behavior is unchanged.

## Formal retry decision

The code path is ready to consume a valid injected T04 RetrievalHit source, but
Q001 is not ready for another formal Provider call until a real, approved,
non-booklet source has been ingested and can pass this adapter and T01 precheck.
