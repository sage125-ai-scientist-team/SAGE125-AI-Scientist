# T06 Multimodal — Handoff

Owner: **T06 / ZBY-06**  
Status: Wave A–C delivered on PR **#42** (`t06/c-showcase-handoff`); FREEZE handoff package (this file).  
Base branch for ordinary PRs: `integration/2026-08-10`

## 1. Module purpose

T06 owns **scientific multimodal extraction and verifiable structured artifacts** (table / chart / timeseries):

- Contract types in `app/contracts/multimodal.py`
- Adapters, vision path, metrics, gold package, Wave C showcase + T08 UI contract
- Production **read/write port** for T08 (and other consumers): durable store keyed by `run_id` + `question_id` + `version_id`
- Honesty gates: no forged tokens/cost; no silent fail-open on raster charts; mock/expected ≠ actual

## 2. Entry points

| Role | Import / path |
| --- | --- |
| Public list | `app.multimodal.read_port.list_multimodal_artifacts` |
| Public detail | `app.multimodal.read_port.list_multimodal_details` |
| Public write | `app.multimodal.read_port.put_multimodal_artifact` |
| Adapters | `app.multimodal.adapters` (`TableAdapter`, `QwenVisionAdapter`, `TimeseriesAdapter`, …) |
| Actual gold eval | `python -m app.multimodal.eval_actual_gold` |
| Wave C builder | `python -X utf8 docs/modules/T06/scripts/t06_build_wave_c_artifacts.py` |
| Contracts | `app.contracts.multimodal` |

T08 must use the read port only (thin adapter). Do **not** scan TEMP dirs or invent validation conclusions.

## 3. Key types / functions

- **Contract**: `MultimodalArtifact`, `Provenance`, `AxisSpec`, `BoundingBox`, `TableData`, `to_consumer_summary`, …
- **Store**: `MultimodalArtifactStore`, `PublicSourceRef`, `MultimodalDetailView`
- **Errors**: `ExtractionError`; port categories `invalid_contract` | `identity_mismatch` | `unavailable` (non-retryable)
- **Vision**: `run_qwen_vision` — env `DASHSCOPE_API_KEY` + `DASHSCOPE_BASE_URL` + `QWEN_VL_MODEL` + `T06_PAID_VISION_AUTHORIZED` (OpenRouter-compatible; does not rely on Settings `WORKSPACE_ID` rewrite)
- **Policy**: `T06_LOW_CONFIDENCE_THRESHOLD = 0.70` (display ownership stays with T06 status fields)

Schema / policy versions in use: `t06.multimodal_store.v1`, `t06.multimodal_detail.v1`, `t06.gate0_fixture.v1`, vision prompt `t06-vision-chart-v3`.

## 4. Configuration (no secrets in git)

| Variable | Purpose |
| --- | --- |
| `DASHSCOPE_API_KEY` | API key (e.g. OpenRouter team key; never commit) |
| `DASHSCOPE_BASE_URL` | e.g. `https://openrouter.ai/api/v1` |
| `QWEN_VL_MODEL` | Vision model id containing `vl` / `vision`, Qwen-prefixed |
| `T06_PAID_VISION_AUTHORIZED` | `1` / `true` / `yes` to allow paid actual VL |

Never commit `.env` or raw keys. Cost fields: record service values only; else `null`.

## 5. Tests

```bash
python -X utf8 -m pytest tests/multimodal -q
python -X utf8 -m pytest tests/multimodal/test_wave_c_fallback.py tests/multimodal/test_gate0_fixtures.py -q
```

Gold provenance validator (from gold package directory):

```bash
python -X utf8 docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --validate
```

## 6. Run / reproduce Wave C

```bash
# Offline packs / metrics merge (demo store under %TEMP%/t06wc/store on Windows)
python -X utf8 docs/modules/T06/scripts/t06_build_wave_c_artifacts.py

# Optional: authorized OpenRouter VL actual gold (requires env above)
python -X utf8 -m app.multimodal.eval_actual_gold \
  --gold-root docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0 \
  --package-head <INTEGRATION_OR_PR_HEAD> --in-integration --allow-vision-actual \
  --out docs/modules/T06/wave_c/actual_gold_openrouter_metrics.json
```

Evidence roots:

- Wave C: `docs/modules/T06/wave_c/`
- Gate0 fixtures: `docs/modules/T06/gate0_fixtures/`
- Gold: `docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/`

## 7. Failure handling

- Missing VL creds / unpaid: deny path; raster chart **fail-closed** (no text-directive silent fallback)
- Invalid / empty VL JSON: `invalid_or_empty_response`; artifact not marked success
- Identity mismatch on store keys: `identity_mismatch`, non-retryable
- Empty list from `list_multimodal_artifacts` is success (no rows), not HTTP 404 semantics

## 8. Known limits

- Zenodo `Picture1.png` is a **hardware photo**, not multi-panel impedance plots
- Chart `relative_error ≤ 5%` is **not claimed** on Wave C; marked `needs_human_review`
- OpenRouter VL actual call recorded (`ACTUAL_EXTERNAL_CALLS=1`); cost left `null` when service field absent
- Preprocessed LEGEND/AXIS/SERIES PDF path remains synthetic / non-vision honesty from Wave B
- Windows: avoid ultra-long TEMP extract paths; builder demo store uses short `%TEMP%/t06wc/store`

## 9. Rollback

- Ordinary delivery is PR-scoped: revert / not-merge the T06 PR tip on `integration/2026-08-10`
- Do not force-push shared branches; do not weaken CI to “pass”
- Consumer rollback: stop calling read port; Gate0 fixtures remain mock/expected only

## 10. PR / Issue links

| Item | Link |
| --- | --- |
| Wave C PR | https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/42 |
| Read port merge (Wave B) | PR #36 |
| Gold package | PR #29 |
| **Follow-up: real chart digitization ≤5%** | https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/issues/48 |

## 11. Owner paths (governance)

See `docs/governance/task-owner-map.yaml` → T06:

- `app/multimodal/**`, `app/contracts/multimodal.py`
- `tests/multimodal/**`
- `docs/modules/T06/**`, `docs/contracts/T06.md`

Builder lives under `docs/modules/T06/scripts/` (not repo-root `scripts/`).
