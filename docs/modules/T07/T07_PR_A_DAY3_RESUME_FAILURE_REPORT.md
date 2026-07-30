# T07 PR-A Day 3 Resume and Failure-Isolation Report

## Provenance

- PR: `#12` — https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/12
- Reviewed/current HEAD: `ea9ca2190457a861782d6c543e989474704039c0`
- Branch: `t07/a-batch-contract`
- Python: `3.12.10`
- Evidence scope: current uncommitted Request Changes fixes in T07 owner paths
- Provider/API calls: none
- Formal/actual research results: none

## Review requirements addressed

| Requirement | Executed evidence | Result |
|---|---|---|
| `T07-METRIC-007` | Synthetic Mock contamination detector CLI | 3 distinct findings computed from 3 scanned records |
| `T07-A-003` | Identical normalized pandemic-plan content across Q901/Q902 | `CROSS_QUESTION_CONTENT_REUSE` |
| `T07-A-007` | Q063 injected failure in a 125-job isolated skeleton step | 1 failed, 124 checkpointed, all 125 visited |
| `T07-A-008` | Resume/failure tests, full batch tests, full pytest, synthetic dry-run | Report and four requested evidence files created |
| P2 owner portion | Derived manifest summaries and negative tests | Implemented within T07 owner paths |

## Contamination detection

The executable detector consumed
`tests/batch/fixtures/contamination_cases.synthetic.json`, which declares
`synthetic=true` and `mock=true`. It calculated:

| Finding code | Bound IDs | Actual observed condition |
|---|---|---|
| `CROSS_QUESTION_CONTENT_REUSE` | Q901, Q902 | Identical normalized pandemic-plan title and abstract |
| `CROSS_QUESTION_EVIDENCE_ID_REUSE` | Q901, Q903 | `EV-MOCK-0001` reused across questions |
| `OUTPUT_QUESTION_ID_MISMATCH` | Q903, Q999 | Q903-owned output declares Q999 |

`finding_count=3` is the length of the detector result, not a fixed metric
string. These controlled findings prove the detector behavior only; they do
not claim reproduction of unavailable historical outputs.

## Batch failure isolation

`BatchRunner.run_isolated` receives an already validated manifest and a
provider-independent job processor. It passes a deep copy of each non-terminal
job to the processor, validates immutable identity on return, writes a
checkpoint, and continues.

The regression test injected one `RuntimeError` for Q063:

- processor visit count: 125
- Q063: `failed`, attempt 1, `JOB_EXECUTION_FAILED`
- Q001-Q062 and Q064-Q125: `checkpointed`
- derived manifest total: 125
- derived status counts: `{"checkpointed": 124, "failed": 1}`
- completed actual jobs: 0

No exception is silently accepted and no failure is converted to completed.

## Resume fail-closed matrix

| Condition | Result / stable code |
|---|---|
| batch ID mismatch | `CHECKPOINT_BATCH_MISMATCH` |
| question ID mismatch | `CHECKPOINT_QUESTION_MISMATCH` |
| source hash mismatch | `STALE_CHECKPOINT_SOURCE_HASH` |
| input hash mismatch | `STALE_CHECKPOINT_INPUT_HASH` |
| route/provider/model mismatch | `STALE_CHECKPOINT_MODEL_ROUTE` |
| model or prompt version mismatch | `STALE_CHECKPOINT_VERSION` |
| prompt hash mismatch | `STALE_CHECKPOINT_PROMPT_HASH` |
| unknown schema/checkpoint version | Pydantic validation rejection |
| corrupted checkpoint JSON | `CHECKPOINT_INVALID` |
| existing `report.json` beside a dry-run job | job remains `queued/planned` |

Checkpoint records bind the source hash and complete model/prompt route
provenance to the embedded job. Resume never infers completion from artifact
existence.

## State and serialization

- `BatchManifest`, `BatchJob`, and `CheckpointRecord` JSON round-trip tests
  pass.
- Unknown batch/checkpoint versions are rejected.
- Duplicate question IDs and isolation identities are rejected.
- Terminal jobs are not sent back through the isolated processor.
- Retry attempts remain hard-limited.
- Manifest `total` and `status_counts` are derived from jobs and inconsistent
  serialized values are rejected.

## Output-contract guardrails

- Mock jobs cannot be completed.
- Synthetic manifests cannot contain completed actual jobs.
- Missing standard fields or required artifacts prevents completed.
- Unassigned provider/model/prompt route prevents completed actual.
- A prompt hash is required for an assigned actual-completion route.
- Dry-run creates no report, result, evidence-card, or agent-trace artifact.

## Verification results

| Command | Result |
|---|---|
| `python -m compileall app/batch app/contracts/batch.py scripts/batch_125 tests/batch` | exit 0 |
| `python -m pytest -q tests/batch/test_contamination.py tests/batch/test_review_fixes.py` | 19 passed in 5.10s |
| `python -m pytest -q tests/batch -vv` | 45 passed in 9.43s |
| `python -m pytest -q tests/batch` | 45 passed in 9.63s |
| `python -m pytest -q` | 283 passed, 35 skipped in 60.20s |
| synthetic dry-run | 125 jobs/checkpoints, 125 unique isolation keys, 0 provider/token/actual/artifact/temp |

## Remaining external and cross-owner items

- Central `integration/2026-08-10` advanced after the reviewed snapshot:
  current tip `3addcea5eaf0ec582b29c1e6288b9d0351ed2932`, while the PR head is
  `ea9ca2190457a861782d6c543e989474704039c0`. The GitHub Compare API reports
  `status=diverged`, `ahead_by=5`, `behind_by=6`, merge base
  `5c7fbff91bca49498aaa0b01d87dfd70345314f8`. This task forbids merge/rebase,
  so an authorized integration sync and complete re-verification are required
  before push/Ready.
- PR #12 remains Draft. This task explicitly forbids editing the PR or marking
  it Ready; the team member must perform that action after an authorized
  commit/push.
- `docs/contracts/T07.md` is outside the current explicit owner allowlist and
  was not modified. The P2 contract-doc alignment suggestion remains a
  cross-owner follow-up.
- The authoritative question catalog, booklet, and historical contamination
  outputs remain unavailable. Formal 125 validation remains not evaluated.
