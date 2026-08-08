# T01 Handoff Draft（Code Freeze 预备，非最终）

**Status:** DRAFT — 在 PR #35 合并且队长确认前，不得当作最终 handoff。

## Module

- Purpose: Evidence grounding, claim–evidence support checks, citations, Wave C quality gates.
- Owner paths: `app/evidence/**`, `app/contracts/evidence.py`, `tests/evidence/**`, `docs/modules/T01/**`, `docs/contracts/T01.md`
- Forbidden: `app/workflow/pipeline.py` (T02)

## Entry points

- `build_evidence_bundle`
- `check_claim_evidence_support` / `run_quality_gate`
- `build_t08_citation_payload` / `build_output_envelope_v125`
- `run_q028_regression` / `build_wave_c_signoff_report`

## PRs

| Wave | PR | State |
|---|---|---|
| A | #7 | MERGED |
| B | #25 | MERGED (`73ce7c0…`) |
| C | #35 | OPEN Draft（等 T09 复验 + 队长授权 Ready） |

## Reproduce

```powershell
python -m pytest -q tests/evidence
python -c "from app.evidence.q028_regression import run_q028_regression; print(run_q028_regression().to_dict())"
python -c "from app.evidence.wave_c_signoff import build_wave_c_signoff_report; print(build_wave_c_signoff_report().to_dict())"
```

## Known limits

- Live pipeline wiring is T02-owned.
- T04 retrieval pairing: STRUCTURE_OK / ACTUAL_RELEVANCE_GOLD=NOT_READY / no formal retrieval metrics.
- Human signoff on `wave_c_2026-08-08_signoff.md` must be completed before Ready.

## Rollback

Revert PR #35 squash commit on integration if Wave C regresses; Wave A/B remain on integration via #7/#25.
