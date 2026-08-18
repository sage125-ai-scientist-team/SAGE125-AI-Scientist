# T02 Gate 0 Interface Report

## Decision

PASS. T02 now has a schema-versioned, fail-closed, read-only consumer wrapper
and five cross-owner fixtures. The change does not modify the frozen revision
contract or the core workflow pipeline.

## Context

- Repository: `sage125-ai-scientist-team/SAGE125-AI-Scientist`
- Branch: `t02/c-revision-hardening`
- Pull request: `#37`
- Initial draft date: `2026-08-10`
- Final verification date: `2026-08-12` (Asia/Shanghai)
- Baseline commit at task start: `7ba73ce70de5702720e467fac2c4396ebef7f64c`
- Latest observed `upstream/integration/2026-08-10`:
  `20592a0eeb9924d021e3ec75ec28d27e2f971e9f`
- Frozen branch comparison before the Gate 0 commit: ahead=3, behind=9
- Consumer schema version: `1`

The task explicitly targets the existing frozen PR #37 branch. No integration
merge, rebase, history rewrite, or unrelated owner update was performed. The
observed branch lag is reported for the repository owner to handle separately;
it does not change the Gate 0 interface test result.

## Existing capability audit

| Capability | Existing T02 source | Gate 0 result |
| --- | --- | --- |
| PlanVersion listing | `PlanVersionStore.list_versions()` | Reused through run/job wrapper |
| Version diff | `StructuredRevisionDiff` and revision audit changes | Reused in a target-version envelope with content hash |
| Reviewer issue read | `ReviewFeedback` and PlanVersion issue snapshots | Projected as stable issue views |
| IssueClosure read | `IssueClosure` on PlanVersion and audit | Latest closure snapshot exposed |
| Score change | `ExplainableRevisionAudit.score_changes` | Exposed by target version |
| Lineage query | PlanVersion parent chain and audit lineage | Exposed with deterministic lineage hash |
| Stop reason | `RevisionExecutionState.stop_reason` and audit | Exposed from validated controller state |
| Unresolved P0/P1 | Categories existed; no stable priority query existed | Added read projection: critical=P0, required=P1 |
| Lightweight cross-owner summary | `RevisionConsumerSummary` and `build_revision_consumer_summary()` | Preserved unchanged; Gate 0 adds complete indexed reads beside it |

No existing capability was refactored. `app.workflow.revision_consumer` composes
the frozen models and adds addressing, validation, and defensive-copy behavior.
The diff envelope uses the existing `StructuredRevisionDiff.fingerprint()`;
Gate 0 does not maintain a second diff-hash algorithm.

## Consumer reads

The `RevisionConsumerStore` provides:

- PlanVersion listing by exactly one of `run_id` or `job_id`;
- PlanVersion and structured diff reads by canonical version ID;
- Reviewer issue and latest IssueClosure reads;
- score delta and lineage reads;
- stop reason and unresolved P0/P1 reads.

Unknown or ambiguous identifiers raise. Broken parent lineage, mismatched
controller state, incorrect lineage/diff hashes, missing V2 artifacts,
contradictory RevisionContext or issue history, invalid issue chronology, invalid
score deltas, and audit/controller terminal-state conflicts are rejected during
record validation.

## Fixtures

Added under `tests/workflow/fixtures/t02_consumer/`:

- `v1_only.json`: V1 with no revision;
- `v1_to_v2.json`: V1, reviewer feedback, RevisionContext, V2, diff, score
  changes, closures, and lineage;
- `open_p0_p1.json`: unresolved critical and required issues;
- `stopped_failed.json`: failure history and terminal stop reason;
- `invalid_lineage.json`: intentionally broken parent and incorrect hash.

## Test evidence

| Command | Result |
| --- | --- |
| Red baseline after canonical-hash/context/terminal checks were added | 6 passed, 3 failed as expected |
| `pytest tests/workflow/test_t02_gate0_consumer_interface.py -q` | 10 passed, 0 failed |
| `pytest tests/workflow -q` | 77 passed, 0 failed |
| `pytest -q` | 807 passed, 37 skipped, 0 failed |
| `python -X utf8 -m compileall -q app/workflow/revision_consumer.py` | PASS |

The full-suite skips are pre-existing environment/data capability skips,
including Windows symlink privilege probes and unavailable optional source
datasets. No Gate 0 test was skipped.

Full pytest regenerated a T01 metrics timestamp/line-ending view and the
repository `.pytest_tmp` directory. The worktree was checked before the run;
these command-generated artifacts were precisely restored/removed and are not
part of this change.

## Scope check

Gate 0 files are limited to the approved owner paths:

- `app/workflow/revision_consumer.py`
- `tests/workflow/test_t02_gate0_consumer_interface.py`
- `tests/workflow/fixtures/t02_consumer/*.json`
- `docs/modules/T02/T02_CONSUMER_INTERFACE.md`
- `docs/modules/T02/T02_GATE0_INTERFACE_REPORT.md`

No file under `app/contracts/`, another owner module, `.github/`, frontend,
data, cache, or dependency manifests was changed for this task. No dependency
was added.

## Security and artifact check

- Common private-key, AWS key, GitHub token, and API-key patterns: 0 matches
- Largest new file: 21,548 bytes
- Secrets, environment files, data, cache, and large binaries: none
- Fixture hashes are deterministic content fingerprints, not credentials

## Gate 0 result

T02 Gate 0 consumer interface requirements are satisfied. The wrapper is ready
for cross-owner read integration within schema version 1. Merge authority
remains with the repository owner; this task does not merge or rewrite history.
