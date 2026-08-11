# T06 Wave C Final Evaluation Report

## Labels

| Item | Status |
| --- | --- |
| Draft PR-C | this branch |
| Two case packs | PASS — `cases/paper_table_chart_zenodo`, `cases/timeseries_csv` |
| T08 UI contract | PASS — `T08_UI_CONTRACT.md` |
| Table cell accuracy | PASS — see `metrics.json` (≥0.95) |
| Chart relative_error≤5% | **NOT MET** — no VL credentials; marked `needs_human_review` |
| ≥2 non-text modalities in pipeline | PASS — table + timeseries |
| No silent fail-open | PASS — tests in `test_wave_c_fallback.py` |
| ACTUAL_EXTERNAL_CALLS | **0** |

## Reproduction

```bash
python -X utf8 scripts/t06_build_wave_c_artifacts.py
python -X utf8 -m app.multimodal.eval_actual_gold \
  --gold-root docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0 \
  --package-head 7b4a4c366f4ce25e5f05e2e948ec3938f11739ac --in-integration
python -X utf8 -m pytest tests/multimodal -q
```

## C-001～C-009 matrix (implementation vs evidence)

| ID | Implementation | Evidence | Notes |
| --- | --- | --- | --- |
| C-001 | PASS | PASS | branch + 2 cases + T08 payload fields + Draft PR-C |
| C-002 | PASS | PASS | case packs + `T08_UI_CONTRACT.md` + Draft |
| C-003 | PASS | PASS | inputs/outputs/human gold in MANIFEST |
| C-004 | PASS | PASS | fallback tests + perf probe |
| C-005 | PASS | PASS | `PERF_FALLBACK_REPORT.md` |
| C-006 | PASS | PASS | no-VL deny tests |
| C-007 | PASS | PARTIAL | final metrics run; chart unmet → human review |
| C-008 | PASS | PARTIAL | this report + metrics; Ready per gate |
| C-009 | PASS | PARTIAL | targets met or explicitly marked review; no forged chart |

## DoD

| ID | Result |
| --- | --- |
| T06-DOD-001 / METRIC-001 | PASS (table+timeseries) |
| T06-DOD-002 / METRIC-002 | PASS (table ≥95%) |
| T06-METRIC-003 | FAIL metric / PASS honesty (`needs_human_review`) |
| T06-DOD-003 | PASS (fail-closed + audit no secrets) |
