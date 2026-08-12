# T06 Wave B evaluation notes (PR #36)

## Labels

| Kind | Status |
| --- | --- |
| `synthetic_fixture_offline` | RUN — see `metrics.json` |
| `actual_zenodo_gold` | RUN against in-repo package (PR #29 merged) — see `actual_gold_metrics.json` |
| `ACTUAL_GOLD_IN_INTEGRATION` | **YES** (PR #29 squash-merged into `integration/2026-08-10`) |
| Paid / actual Qwen VL | **NOT PERFORMED** (credentials + paid auth missing) |

## Reproduction

Synthetic offline:

```bash
python -X utf8 -m app.multimodal.eval_metrics
```

Actual gold (in-repo after #29 merge):

```bash
python -X utf8 -m app.multimodal.eval_actual_gold \
  --gold-root docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0 \
  --package-head 7b4a4c366f4ce25e5f05e2e948ec3938f11739ac \
  --in-integration
```

## Chart metric (canonical)

- Non-zero: `relative_error = abs(pred-gold)/abs(gold)` ≤ 0.05
- Zero gold: absolute tolerance from gold `domain_mapping` (deposited CSV exact zeros → 0.0)
- Code: `app/multimodal/metrics_relative.py`
- B012 (script/threshold code + tests): PASS
- Actual chart digitization from `Picture1.png`: **blocked without Qwen VL** (not fabricated)

## Actual gold result (post-#29 merge sync)

- Package provenance Head: `7b4a4c366f4ce25e5f05e2e948ec3938f11739ac`
- DOI: `10.5281/zenodo.13378442`
- Table (`raw/fishtrial_resistance.csv`, 84 labeled cells): **cell_accuracy=1.0** (≥0.95)
- Chart (`raw/Picture1.png`): **NOT OK** — vision path fail-closed without credentials (`vision_blocked=true`)
- `meets_full_wave_b_gold_bar=false` until authorized Qwen VL succeeds

## Acceptance artifacts

Under `docs/modules/T06/wave_b/acceptance/`:

- `table_pdf_sample.json` — native PDF table extract (page/bbox/sha; units missing → needs_review)
- `chart_preprocessed_pdf_demoted.json` — LEGEND/AXIS/SERIES PDF marked synthetic_fixture
- `timeseries_hook_sample.json` — cleaning_log + `binary_in_prompt=false`
- `evidence_rag_e2e.json` — T04 MemoryVectorStore retrieve; low confidence not supports

## Honesty

- Text-directive PDF chart ≠ real vision
- Denied/mock Qwen ≠ actual external success
- Missing units / low confidence → needs_review; no fixed fake high confidence PASS

## B001–B021 matrix (implementation vs evidence)

| ID | Implementation | Actual evidence | Notes |
| --- | --- | --- | --- |
| B001 | PASS | PASS | `acceptance/table_pdf_sample.json` + PDF path |
| B002 | PASS | PASS | `TableAdapter` + CSV/PDF extract |
| B003 | PASS | PASS | SHA/bbox/fail-closed tests + acceptance |
| B004 | PASS (schema/path) | PARTIAL | real VL chart digits not run |
| B005 | PASS (adapters) | PARTIAL | no successful actual VL call |
| B006 | PASS (fail-closed) | PARTIAL | mock/invalid paths only for VL |
| B007 | PASS | PASS | timeseries + `acceptance/timeseries_hook_sample.json` |
| B008 | PASS | PASS | adapter + Draft PR-B exists |
| B009 | PASS | PASS | `binary_in_prompt=false` |
| B010 | PASS (scripts) | PARTIAL | table actual gold OK; chart blocked |
| B011 | PASS (synth+runner) | PARTIAL | in-integration gold; full bar false (chart) |
| B012 | PASS | PASS (code) / PARTIAL (actual chart) | relative_error≤0.05 canonical |
| B013 | PASS (test-scope) | PASS | `acceptance/evidence_rag_e2e.json` via T04 store |
| B014 | PASS (test-scope) | PASS | same; not production index claim |
| B015 | PASS | PASS | locator retained; low conf not supports |
| B016 | PASS (non-paid path) | PARTIAL_WAIT_EXTERNAL_EXECUTION | ACTUAL_EXTERNAL_CALLS=0 |
| B017 | PASS | PASS | audit + workflow hook tests |
| B018 | PASS | PASS | redaction tests |
| B019 | PARTIAL | WAIT | sync done; Ready not performed |
| B020 | PARTIAL | WAIT | report present; Ready not performed |
| B021 | PARTIAL | WAIT | honesty P1 closed in code; Ready pending |
