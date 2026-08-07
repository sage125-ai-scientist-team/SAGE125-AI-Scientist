# T06 Wave B implementation notes

## Branch

- `t06/b-multimodal-core`
- Base: `integration/2026-08-10`
- Independent of PR #29 (not derived; provenance package not copied)

## Delivered adapters

| Adapter | Module | Fail-closed behaviors |
| --- | --- | --- |
| TableAdapter | `table_extract.py` | missing fields, illegal bbox, duplicate headers, merge conflicts, empty units |
| ChartAdapter | `chart_extract.py` | missing legend, unknown axis unit, inverted axis, out-of-range points |
| TimeseriesAdapter | `timeseries_extract.py` | missing schema/columns, unsorted time, unsupported unit convert; cleaning_log |
| QwenVisionAdapter | `adapters.py` + `audit.py` | denies paid calls; offline chart fallback marked `needs_review` |

## Shared-change

No shared/other-owner files modified. EvidenceCard consumed via T01 contract import only.
