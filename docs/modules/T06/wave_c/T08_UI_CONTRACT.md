# T06 → T08 UI Contract (Wave C)

Status: `FROZEN_FOR_T08_ADAPTER`
Owner: T06 (`ZBY-06`)
Aligned ports: `app.multimodal.read_port.list_multimodal_artifacts` /
`list_multimodal_details` / `put_multimodal_artifact`

T08 must consume these fields via thin adapter under `app/api/**` only.
Do **not** invent a second multimodal truth source.

## Identity

| Field | Required | Notes |
| --- | --- | --- |
| `run_id` | yes | T08 may map `upstream_run_id` → `run_id` before call |
| `question_id` | yes | |
| `version_id` | yes | |
| `job_id` | T08-owned | not required by T06 port |
| `correlation_id` | recommended | pass-through logging only |

## Detail panel fields (minimum)

| UI field | Source |
| --- | --- |
| thumbnail / preview | `public_source.preview_artifact_id` (+ optional case-pack thumbnail path) |
| source locator | `public_source.source_id`, `source_label`, `page`, `bbox`, `coordinate_space` |
| raw locator (redacted) | `artifact.provenance.source_path` (already sanitized on read) |
| extracted values | `artifact.data.headers` + `artifact.data.rows` |
| units | `artifact.units`, `artifact.column_units`, `artifact.axes[].unit` |
| axes / legend | `artifact.axes`, `artifact.legend` |
| confidence | `artifact.confidence` |
| validation_status | `artifact.validation_status` |
| needs_review | `needs_human_review` on `MultimodalDetailView` **or** status ∈ {needs_review,failed,pending} / low confidence |

## Payload shapes

1. **List artifacts**

```python
list_multimodal_artifacts(*, run_id, question_id, version_id) -> list[MultimodalArtifact]
```

2. **List details (preferred for UI)**

```python
list_multimodal_details(*, run_id, question_id, version_id) -> list[MultimodalDetailView]
# MultimodalDetailView.to_dict() includes artifact + public_source + needs_human_review
```

## Rules T08 must honor

- Empty list = no multimodal for identity (HTTP 200 empty), not silent fixture fill.
- `identity_mismatch` / `invalid_contract` / `unavailable` → fail closed; no path leakage.
- Low confidence / needs_review / failed must stay visible; T08 must not hide them.
- Absolute filesystem paths are forbidden in API responses (T06 already redacts).
- Chart raster without successful VL remains `needs_review` / blocked — never fabricate points.

## Showcase references

- Table+chart case: `docs/modules/T06/wave_c/cases/paper_table_chart_zenodo/`
- Timeseries case: `docs/modules/T06/wave_c/cases/timeseries_csv/`
