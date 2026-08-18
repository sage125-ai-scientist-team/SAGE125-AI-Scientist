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

## T08 production read-port alignment

The frozen Gate 0 interface above remains unchanged. T08 production reads use
the separate service in `app.workflow.revision_read_port`, which requires the
complete `(run_id, question_id)` identity and never infers `question_id` from a
version string.

```text
CONTRACT_FILE=app/workflow/revision_read_port.py
SERVICE_SYMBOL=RevisionProductionReadPort
STORAGE/READ_SOURCE=RevisionReadSnapshot (T02-owner persisted binding over a validated RevisionConsumerRecord)
SIGNATURES=list_plan_versions(*, run_id: str, question_id: str) -> list[PlanVersionView]; get_version_diff(*, run_id: str, question_id: str, from_version_id: str, to_version_id: str) -> VersionDiffEnvelope
IDENTITY_RULES=run_id, question_id, and every version_id must resolve to the same authoritative RevisionReadSnapshot
FAIL_CLOSED_RULES=no latest-run lookup; no cache/fixture/mock fallback; no question inference; no text-diff synthesis; no cross-run, cross-question, cross-lineage, reversed, same-version, or unpersisted interval diff
ERROR_BEHAVIOR=unknown run/version raises KeyError; identity mismatch raises RevisionIdentityError; invalid order/ancestry/storage lineage raises RevisionLineageError; malformed snapshots fail Pydantic validation
```

### Existing-field audit

This audit distinguishes fields in the frozen `RevisionConsumerRecord` from
facts that happen to exist elsewhere in workflow artifacts. A fact is not
treated as available to the frozen consumer merely because another file could
be guessed or searched for it.

| Required fact | Frozen consumer state | Production binding/result |
| --- | --- | --- |
| `run_id`, `job_id` | Stored on `RevisionConsumerRecord`; run repeated on each `PlanVersion` | Run is cross-checked; job remains available through the nested frozen record |
| `question_id` | **Missing** | Required on `RevisionReadSnapshot`; the storage adapter must bind it from the authoritative run/question record |
| PlanVersion, parent, version number | Stored and lineage-validated | Returned as `PlanVersionView` with canonical IDs |
| Per-version timestamp | **Missing** (the Wave C summary has only generated-version provenance, not complete V1/V2 timestamps) | Exact, timezone-aware `version_timestamps` are required for every stored version |
| Reviewer scores | Stored in each version's `review_feedback` | Returned as `reviewer.score` |
| Score deltas | Stored in `revision_audit.score_changes` for the owner diff | Returned only for its authoritative target version |
| Reviewer issues and severity | Issue history is stored; severity is stored on the opening version's reviewer snapshot, not on each issue | Returned together after fail-closed opening-version lookup |
| Required revision | Stored as issue category plus reviewer description | Returned as category, description, and explicit `required_revision` boolean |
| Opened/closed version and resolution note | Stored as numeric version positions and validated transitions | Returned as canonical version IDs, closure status, and note |
| Feedback IDs | **Missing from the frozen consumer record**; human-feedback flows may carry one in separate revision metadata | Required as explicit `FeedbackVersionBinding`; duplicate identical bindings collapse, conflicts reject |
| Validation status | **Missing** (`revision_control.status` is lifecycle state, not plan validation status) | Required from the authoritative plan/run record on `RevisionReadSnapshot` |
| Stop reason | Stored on revision control and cross-checked with the audit | Returned in the state view |
| Open P0/P1 | Derivable from validated open issue categories | Returned as owner-projected issue-ID lists; critical→P0, required_revision→P1 |
| Structured diff and hash | Stored and content-validated | Returned unchanged; no downstream text diff is generated |
| Lineage and lineage hash | Stored/validated across plan, context, audit, control, diff, and hash | Full lineage is returned and revalidated at query time |

The three frozen-record gaps are therefore `question_id`, complete per-version
timestamps, and plan `validation_status`; feedback IDs are also absent unless a
separate human-feedback record exists. `RevisionReadSnapshot` makes all four
bindings explicit and self-hashed. A production adapter must obtain them from
the owning run, plan, and feedback records. Missing bindings are errors, not
values to reconstruct from `latest`, a filename, a cache, or a fixture.

### Response ownership

`PlanVersionView` returns the canonical version identity and lineage, its
timestamp, reviewer score and delta maps, feedback IDs, issue lifecycle fields,
and current run state (`validation_status`, `stop_reason`, unresolved P0/P1).
`VersionDiffEnvelope` returns the exact T02 `StructuredRevisionDiff` and its
canonical hash. The read port only serves an interval for which the owner stored
one exact diff; it does not compose or approximate a diff across versions.

Issue opening/closure positions are converted to canonical version IDs only
after the nested frozen record passes its existing transition validation. This
guarantees that a resolution reported in V2 cannot be attached to V3 and that a
closure cannot precede its opening version.

### Non-sensitive production-shape example

The names below illustrate an adapter handoff shape; they are not fixture data
or evidence of a production run.

```python
from datetime import UTC, datetime

from app.workflow.revision_read_port import (
    FeedbackVersionBinding,
    RevisionProductionReadPort,
    RevisionReadSnapshot,
)

snapshot = RevisionReadSnapshot.create(
    run_id="run-public-example",
    question_id="Q001",
    consumer_record=owner_consumer_record,
    version_timestamps={
        "run-public-example:v1": datetime(2026, 8, 15, 8, 0, tzinfo=UTC),
        "run-public-example:v2": datetime(2026, 8, 15, 8, 1, tzinfo=UTC),
    },
    validation_status="ready_for_validation",
    feedback_bindings=(
        FeedbackVersionBinding(
            feedback_id="feedback-public-example",
            source_version_id="run-public-example:v1",
            resulting_version_id="run-public-example:v2",
        ),
    ),
)
read_port = RevisionProductionReadPort((snapshot,))

versions = read_port.list_plan_versions(
    run_id="run-public-example",
    question_id="Q001",
)
diff = read_port.get_version_diff(
    run_id="run-public-example",
    question_id="Q001",
    from_version_id="run-public-example:v1",
    to_version_id="run-public-example:v2",
)
```

The T08-owned adapter may transport these models, but must preserve all four
identity arguments and the fail-closed error behavior.
