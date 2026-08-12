# T02 Consumer Interface

## Purpose

`app.workflow.revision_consumer` is the stable, read-only Gate 0 boundary for
cross-owner consumers of T02 revision results. It composes existing frozen T02
models and does not generate revisions, mutate workflow state, or replace the
workflow persistence owner.

Wave C already emits `RevisionConsumerSummary` in AgentTrace for lightweight
T08/UI display. Gate 0 does not replace or modify that projection. It adds a
validated aggregate plus indexed reads for consumers that need the complete
`PlanVersion`, canonical structured diff, reviewer issue/closure history,
scores, lineage, and terminal state.

## Compatibility window

- Current `schema_version`: `1`
- Supported plan lineage in schema 1: V1, or the frozen V1-to-V2 revision flow
- Unknown, incomplete, inconsistent, or future schemas are rejected
- The wrapper returns defensive copies; changing a returned value cannot mutate
  the stored consumer snapshot

## Input addressing

Run-scoped reads accept exactly one of:

- `run_id`
- `job_id`

Version-scoped reads accept the canonical `version_id`, for example
`run-123:v2`. A diff is addressed by its target version.

`job_id` is the owning orchestrator's stable address for the same T02 run. It is
carried in the consumer snapshot and maps one-to-one to `run_id`; it is not added
to or inferred by the frozen `PlanVersion` contract.

Supplying both `run_id` and `job_id`, supplying neither, or addressing an
unknown identifier raises an exception. The interface never converts a missing
or ambiguous record into an empty successful result.

## Output models and reads

| Consumer need | Method | Output |
| --- | --- | --- |
| PlanVersion listing | `list_plan_versions(run_id=...)` or `list_plan_versions(job_id=...)` | Ordered `list[PlanVersion]` |
| One PlanVersion | `get_plan_version(version_id)` | `PlanVersion` |
| Version diff | `get_version_diff(target_version_id)` | `VersionDiffEnvelope` containing `StructuredRevisionDiff` |
| Reviewer issues | `get_reviewer_issues(run_id=...)` | `list[ReviewerIssueView]` |
| Issue closure state | `get_issue_closures(run_id=...)` | Latest `list[IssueClosure]` |
| Score change | `get_score_deltas(target_version_id)` | Reviewer score name to `ReviewScoreChange` |
| Lineage | `get_lineage(job_id=...)` | `LineageView` |
| Stop reason | `get_stop_reason(run_id=...)` | `str | None` |
| Unresolved P0/P1 | `get_open_p0_p1(job_id=...)` | Open `list[ReviewerIssueView]` |

The Gate 0 priority projection is explicit and deterministic:

- `critical_issue` maps to `P0`
- `required_revision` maps to `P1`

The original issue category and reviewer risk level remain present in each
`ReviewerIssueView`; the priority label does not alter the frozen revision
contract.

`VersionDiffEnvelope.diff_hash` is exactly
`StructuredRevisionDiff.fingerprint()`. Gate 0 deliberately reuses the existing
T02 canonical diff hash and does not introduce an envelope-specific hash.

## Construction example

```python
from app.workflow.revision_consumer import (
    RevisionConsumerRecord,
    RevisionConsumerStore,
)

record = RevisionConsumerRecord.model_validate(snapshot)
store = RevisionConsumerStore([record])

versions = store.list_plan_versions(job_id="job-123")
lineage = store.get_lineage(job_id="job-123")
open_blockers = store.get_open_p0_p1(job_id="job-123")
```

`snapshot` is a complete consumer record containing `run_id`, `job_id`,
`plan_versions`, revision control state, optional V2 context/audit/diff, and a
content-derived lineage hash.

## Fail-closed validation

`RevisionConsumerRecord` rejects a snapshot when any required relationship is
broken, including:

- non-contiguous versions, a wrong parent, or a run mismatch;
- a revision-controller version list that differs from PlanVersion lineage;
- a missing or incorrect lineage hash;
- a V2 record without its context, audit, or canonical diff;
- a diff with an incorrect content hash or audit mismatch;
- a RevisionContext whose V1 feedback, unresolved issues, previous plan, or
  failure reasons disagree with the PlanVersion/audit snapshots;
- reviewer issues that disappear, reopen, change identity, or contradict the
  current feedback, including invalid opening/closure version transitions;
- score deltas that do not equal the V1-to-V2 reviewer score change;
- an accepted/rejected audit whose terminal controller status or stop reason
  disagrees with the audit.

## Consumer fixtures

Fixtures live in `tests/workflow/fixtures/t02_consumer/`:

| Fixture | State represented |
| --- | --- |
| `v1_only.json` | Valid V1 with no revision |
| `v1_to_v2.json` | V1, feedback, RevisionContext, V2, diff, scores, and closures |
| `open_p0_p1.json` | Valid active run with unresolved P0 and P1 issues |
| `stopped_failed.json` | Stopped run with retry failures and stop reason |
| `invalid_lineage.json` | Intentionally broken parent lineage and incorrect hash |

The invalid fixture is evidence for rejection behavior and must not be consumed
as a successful workflow result.

## Ownership boundary

This interface is an in-process validated read facade. Storage, transport,
authorization, and pagination remain responsibilities of the owning service.
Consumers should persist and transmit the schema-versioned record rather than
depending on private store attributes.
