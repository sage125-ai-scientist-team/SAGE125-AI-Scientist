# T07 PR-A Day 3 Resume and Failure-Isolation Report

## Provenance

- PR: `#12` — https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/12
- Tested code SHA: `07e1b1e13520db3ab2ca2027ff190fe812ed3d22`
- Integration SHA: `d2c4650164bc6e03e3bac847911c68ee79a4d0bb`
- Integration comparison: `ahead=11`, `behind=0`
- Branch: `t07/a-batch-contract`
- Validation date: `2026-08-01` (`Asia/Shanghai`)
- Environment: Windows / PowerShell
- Python: `3.12.10`
- Python executable: `D:\SAGE125-AI-Scientist\.venv\Scripts\python.exe`
- Evidence scope: commands were executed against the Tested code SHA above;
  subsequent report/evidence edits do not change the tested code provenance.
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
| `& ".\.venv\Scripts\python.exe" -m pytest -q tests\batch` | exit 0; collected 45; 45 passed, 0 failed, 0 skipped, 0 warnings in 7.62s; first failure: none |
| `& ".\.venv\Scripts\python.exe" -m pytest -q` | exit 0; collected 662; 625 passed, 0 failed, 37 skipped, 0 warnings in 35.39s; first failure: none |
| `& ".\.venv\Scripts\python.exe" -m scripts.batch_125.dry_run --source "tests/batch/fixtures/questions_125.synthetic.json" --source-kind synthetic --run-root ".pytest_tmp/pr_a_final" --batch-id "pr-a-final"` | exit 0; synthetic dry-run validation passed |

The synthetic dry-run stdout reported exactly:

- `jobs=125`
- `unique_workspaces=125`
- `unique_context_ids=125`
- `unique_cache_namespaces=125`
- `checkpoints=125`
- `provider_calls=0`
- `tokens_used=0`
- `actual_results=0`
- `research_artifacts=0`
- `temporary_files=0`
- `source_kind=synthetic`
- `dry_run=true`

Current UTF-8 (no BOM) evidence files:

- `docs/modules/T07/evidence/pr_a_final_batch_tests.txt`
- `docs/modules/T07/evidence/pr_a_final_dry_run.txt`
- `docs/modules/T07/evidence/pr_a_final_full_tests.txt`

## Remaining external and cross-owner items

- Current `upstream/integration/2026-08-10` is fully contained in the tested
  branch: `ahead=11`, `behind=0`. No integration sync blocker remains for this
  verification snapshot.
- PR #12 is closed and unmerged per the current task context. Reopening it is
  an explicit manual action; this task does not edit, reopen, or mark the PR
  Ready.
- `docs/contracts/T07.md` is outside the current explicit owner allowlist and
  was not modified. The P2 contract-doc alignment suggestion remains a
  cross-owner follow-up.
- The authoritative question catalog, booklet, and historical contamination
  outputs remain unavailable. Formal 125 validation remains not evaluated.
