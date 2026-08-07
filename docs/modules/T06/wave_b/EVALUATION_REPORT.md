# T06 Wave B evaluation notes (PR #36 phase-1 fix)

## Labels

| Kind | Status |
| --- | --- |
| `synthetic_fixture_offline` | RUN |
| `actual_gold` | **BLOCKED** — PR #29 not merged into integration |
| Paid Qwen calls | **NOT PERFORMED** in phase-1 (`STOP` until PR29 merge + gates) |

## Chart metric (canonical)

- Non-zero gold: `relative_error = abs(pred-gold)/abs(gold)`; PASS iff `<= 0.05`
- Zero gold: absolute tolerance `1e-6` (declared in metrics.json)
- Implemented in `app/multimodal/metrics_relative.py` (not report-only)

## PDF / image

- Tables/charts: real PDF via PyMuPDF (`pdf_io.py`)
- JSON packets require `input_kind=offline_fixture|preprocessed_input`
- Raster-only images fail-closed without authorized vision path

## EvidenceCard live path

- `evidence_live.py` indexes via T01 `EvidenceBundle` / `validate_evidence_card` and consumes back locator fields
- Low confidence cannot create factual `supports` links

## Qwen

- Path: `qwen_vision.py` using `DASHSCOPE_*` + `QWEN_VL_MODEL` / balanced model
- Phase-1 keeps `allow_actual=False`
