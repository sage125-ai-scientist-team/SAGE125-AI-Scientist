# T06 Gate 0 fixtures (for T08)

Fixed JSON fixtures for cross-owner Gate 0.  
**Do not** relabel `mock` / `expected` as `actual`.

| Kind | Path | evidence_class |
| --- | --- | --- |
| validated | `validated.json` | mock |
| low-confidence / manual-review | `low_confidence_manual_review.json` | mock |
| missing provenance | `missing_provenance.json` | expected |
| invalid | `invalid.json` | expected |

Public ports (merged via PR #36):

- `app.multimodal.read_port.list_multimodal_artifacts`
- `app.multimodal.read_port.list_multimodal_details`

See `MANIFEST.json` for schema_version, error codes, compatibility window.
