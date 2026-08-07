# T06 Wave B implementation notes

## Branch

- `t06/b-multimodal-core`
- Base: `integration/2026-08-10`
- Independent of PR #29 (not derived; provenance package not copied)

## Delivered adapters

| Adapter | Module | Fail-closed / honesty |
| --- | --- | --- |
| TableAdapter | `table_extract.py` | missing fields, illegal bbox, duplicate headers, merge marking, missing units → needs_review, scored confidence, SHA-256 retained |
| ChartAdapter | `chart_extract.py` | PDF directives demoted to synthetic_fixture; raster requires vision; legend/unit/range checks |
| TimeseriesAdapter | `timeseries_extract.py` | schema/time/unit convert + cleaning_log |
| QwenVisionAdapter | `qwen_vision.py` + `vision_schema.py` | VL JSON schema → artifact; empty/invalid fail; no discard-on-success; denied without paid auth |

## Evidence

- T04 E2E helper: `evidence_rag.py` (MemoryVectorStore + chunk_to_retrieval_hit)
- Bundle-only helper: `evidence_live.py` (not a production live index)

## Shared-change

No shared/other-owner files modified.
`SHARED_CHANGE_REQUIRED=NO`
