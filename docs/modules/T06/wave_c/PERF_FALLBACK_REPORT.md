# T06 Wave C — Performance & Fail-closed Fallback Report

Date: 2026-08-11
Branch: `t06/c-showcase-handoff`
Offline builder probe: `ACTUAL_EXTERNAL_CALLS=0` / tokens=`null` / cost=`null`  
OpenRouter gold VL evidence (separate): see `actual_gold_openrouter_metrics.json` / `metrics.json` (`ACTUAL_EXTERNAL_CALLS=1`, cost still `null`).
Demo artifact store root: `%TEMP%/t06wc/store` (short path; avoids Windows MAX_PATH).

## Scope (C-004～C-006)

| Scenario | Result | Evidence |
| --- | --- | --- |
| Offline extract timing (table/CSV gold) | ~10–20ms class on local probe | `perf_probe.json` / `metrics.json` timings_ms |
| Timeseries extract timing | ~few ms | same |
| No vision model / unpaid path | denied / ExtractionError; **no fabricated points** | `tests/multimodal/test_wave_c_fallback.py::test_no_vision_model_denied_no_fabricated_points` |
| Raster PNG via ChartAdapter | fail-closed | `test_raster_chart_not_silently_parsed_by_chart_adapter` |
| Missing legend | ExtractionError | `test_chart_unit_and_legend_fail_closed` |
| Unknown axis unit | ExtractionError | same |
| Quota / timeout | mock path supports timeout simulation in `run_qwen_vision(simulate_error=\"timeout\")`; production unpaid path never calls network | `app/multimodal/qwen_vision.py` |
| Unit conflict / low confidence | needs_review/failed owned by T06; UI must show | `T06_LOW_CONFIDENCE_THRESHOLD` + UI contract |

## Safety claims

- Without VL credentials + paid auth: chart digitization **must not** PASS.
- Preprocessed LEGEND/AXIS/SERIES PDF remains synthetic/preprocessed (Wave B honesty).
- Correction flow: see `CORRECTION_FLOW.md`.

## Reproduction

```bash
python -X utf8 docs/modules/T06/scripts/t06_build_wave_c_artifacts.py
python -X utf8 -m pytest tests/multimodal/test_wave_c_fallback.py -q
```
