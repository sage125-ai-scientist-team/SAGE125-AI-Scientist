# T01 Q028 Regression Report v1（08/02）

## Scope

Contract-layer / support-checker regression for Q028 handbook requirements.

Does **not** modify `app/workflow/pipeline.py` (T02 integration later).

Branch: `t01/b-evidence-core`  
Runner: `app.evidence.q028_regression.run_q028_regression()`  
Tests: `tests/evidence/test_q028_regression.py`

## Before / after matrix

| Scenario | Baseline risk (before) | After (current checker) | Decision |
|---|---|---|---|
| S1 fabricated `booklet_excerpt_Q028` | Could be invented and treated as real evidence_id | `FAKE_BOOKLET_EVIDENCE_ID` **BLOCK** | Pass |
| S2 booklet excerpt as support | Booklet context treated as scientific support | `BOOKLET_EXCLUDED` **BLOCK** | Pass |
| S3 lung adenocarcinoma → all cancers | Single-cancer quote over-claimed | `OVERGENERALIZATION` **DEGRADE** (no allow) | Pass |
| S4 in-scope lung adenocarcinoma claim | Control | **ALLOW** one link | Pass |

## Commands

```powershell
python -c "from app.evidence.q028_regression import run_q028_regression; r=run_q028_regression(); print(r.to_dict())"
python -m pytest -q tests/evidence/test_q028_regression.py -vv
```

## Also improved in this day

- Bundle builder: relevance sort + quote/hash dedupe
- Clearer truncation / unknown-id / metadata-only error messages

## Pairing / review notes

- T04 pairing: Q028 booklet isolation aligns with RAG “booklet not evidence” boundary; no `app/rag/**` edits in this PR.
- Codex/captain: please re-review Draft PR #13 after this push; still **Draft** (Ready target ~08/05).

## Limits

- This is contract-layer regression, not full pipeline E2E on live Q028 question JSON.
- 08/03 adds T01↔T02/T03 **contract** E2E via `integration_bridge` (still no `pipeline.py` edits).
- Live agent wiring into EvidenceExtractor / HypothesisGenerator / ExperimentDesigner remains T02-owned.

## Daily note

See also `docs/modules/T01/wave_b_2026-08-02.md`.
