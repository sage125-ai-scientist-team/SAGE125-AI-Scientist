# T06 Wave B evaluation notes (PR #36 substantive fix)

## Labels

| Kind | Status |
| --- | --- |
| `synthetic_fixture_offline` | RUN |
| `actual_gold` | **BLOCKED** — PR #29 not merged into integration |
| Paid / actual Qwen VL calls | **NOT PERFORMED** (`WAIT_PR29_MERGE` + credentials) |

## Chart metric (canonical)

- Non-zero gold: `relative_error = abs(pred-gold)/abs(gold)`; PASS iff `<= 0.05`
- Zero gold: absolute tolerance `1e-6` (declared in metrics.json)
- Implemented in `app/multimodal/metrics_relative.py` (not report-only)
- B012: canonical metric code + tests PASS; actual gold separately WAIT

## PDF / image honesty

- PDF `LEGEND/AXIS/SERIES` text directives = **preprocessed / synthetic_fixture**, confidence capped ≤0.55 — **not** real chart vision
- `sample_chart.pdf` is **not** evidence of real chart extraction (B004–B006 PARTIAL)
- Real vision path: PDF page render or PNG/JPEG/WebP → Qwen VL JSON → `vision_schema.parse_vision_chart_json` → `MultimodalArtifact`
- Successful VL parse is never discarded in favor of the text-directive parser
- Raster tables/charts without vision fail-closed

## Tables

- PDF native extract via PyMuPDF; merge heuristics marked; units from header or caller
- Missing units → `needs_review` + confidence capped; no fixed 0.86 PASS
- File SHA-256 retained on `source_path#sha256=` and EvidenceCard locator
- B001–B003 remain PARTIAL until stronger real evidence

## EvidenceCard E2E

- Bundle helper `evidence_live.py` is **not** a T01/T04 live index
- Cross-module path: `evidence_rag.index_and_retrieve_via_t04_store` → `MemoryVectorStore.add_documents` → `search` → `chunk_to_retrieval_hit`
- Locator fields (bbox/units/page/confidence/validation_status/file_sha256) preserved on retrieve
- Low confidence must not form factual `supports`
- B013/B014/B017 PARTIAL until production-grade index evidence; B015 PASS

## Qwen

- Requires explicit `QWEN_VL_MODEL` containing a vision hint; no silent fallback to balanced chat
- Audit records start/end, latency, attempt/retry, response id/hash, tokens/cost only when returned
- Mock success / invalid JSON / empty / timeout / auth / low confidence covered offline
- B016 = `PARTIAL_WAIT_EXTERNAL_EXECUTION` until PR29 merge + real call
