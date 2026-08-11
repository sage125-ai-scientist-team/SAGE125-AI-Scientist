# T06 Wave C Final Evaluation Report

## Labels

| Item | Status |
| --- | --- |
| Draft PR-C | this branch (Ready) |
| Two case packs | PASS — `cases/paper_table_chart_zenodo`, `cases/timeseries_csv` |
| T08 UI contract | PASS — `T08_UI_CONTRACT.md` |
| Table cell accuracy | PASS — see `metrics.json` (≥0.95) |
| Chart relative_error≤5% | **NOT MET** — OpenRouter VL called; empty structure; `needs_human_review` |
| ≥2 non-text modalities in pipeline | PASS — table + timeseries |
| No silent fail-open | PASS — tests in `test_wave_c_fallback.py` |
| ACTUAL_EXTERNAL_CALLS | **≥1** (OpenRouter; see `actual_gold_openrouter_metrics.json`) |

## OpenRouter VL actual run (honesty)

- Endpoint: `https://openrouter.ai/api/v1` (via `DASHSCOPE_*` env aliases)
- Model: `qwen/qwen3-vl-32b-instruct`
- Auth gate: `T06_PAID_VISION_AUTHORIZED=1`
- Code path: `qwen_vision` reads API key + base URL from **environment** (not Settings `WORKSPACE_ID` rewrite)
- Service-reported tokens (example final gold eval): `tokens_in=376`, `tokens_out=72`, `response_id=gen-1786466716-ZSOK1PddnAVrfERr6Yza`
- `cost`: **null** (not invented; OpenRouter response had no cost field recorded by our client)
- Parse result: empty `legend` / `axes` / `series` → fail-closed (`invalid_or_empty_response`)
- Independent describe-image probe: model identifies `Picture1.png` as **experimental hardware photo** (petri-dish / sensor wiring), **not** multi-panel impedance plots
- Therefore chart ≤5% is **not claimed**; gold numeric chart labels remain CSV-linked anchors pending a true plot image or human digitization

Detailed machine record: `actual_gold_openrouter_metrics.json`.

## Reproduction

```bash
# Requires OpenRouter key in DASHSCOPE_API_KEY; do not commit secrets.
export DASHSCOPE_BASE_URL=https://openrouter.ai/api/v1
export QWEN_VL_MODEL=qwen/qwen3-vl-32b-instruct
export T06_PAID_VISION_AUTHORIZED=1

python -X utf8 docs/modules/T06/scripts/t06_build_wave_c_artifacts.py
python -X utf8 -m app.multimodal.eval_actual_gold \
  --gold-root docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0 \
  --package-head <HEAD_SHA> --in-integration --allow-vision-actual \
  --out docs/modules/T06/wave_c/actual_gold_openrouter_metrics.json
python -X utf8 -m pytest tests/multimodal -q
```

## C-001～C-009 matrix (implementation vs evidence)

| ID | Implementation | Evidence | Notes |
| --- | --- | --- | --- |
| C-001 | PASS | PASS | branch + 2 cases + T08 payload fields + PR-C |
| C-002 | PASS | PASS | case packs + `T08_UI_CONTRACT.md` |
| C-003 | PASS | PASS | inputs/outputs/human gold in MANIFEST |
| C-004 | PASS | PASS | fallback tests + perf probe |
| C-005 | PASS | PASS | `PERF_FALLBACK_REPORT.md` |
| C-006 | PASS | PASS | no-VL deny tests still valid; paid path gated |
| C-007 | PASS | PARTIAL | VL actual run recorded; chart unmet → human review |
| C-008 | PASS | PARTIAL | this report + metrics; Ready per gate |
| C-009 | PASS | PARTIAL | targets met or explicitly marked review; no forged chart |

## DoD

| ID | Result |
| --- | --- |
| T06-DOD-001 / METRIC-001 | PASS (table+timeseries) |
| T06-DOD-002 / METRIC-002 | PASS (table ≥95%) |
| T06-METRIC-003 | FAIL metric / PASS honesty (`needs_human_review` + actual VL evidence) |
| T06-DOD-003 | PASS (fail-closed + audit no secrets) |
