# T02 Wave B explainable experiment revision evidence

## Scope and baseline

- Branch: `t02/b-explainable-experiment-revision`
- Fresh upstream baseline: `d2c4650164bc6e03e3bac847911c68ee79a4d0bb`
- Requirements: `T02-B-004`, `T02-B-005`, and `T02-B-006`
- The branch was created from the refreshed `upstream/integration/2026-08-10`.
- No code was taken from legacy PR #11 or commit `ce9b079`.
- Wave A contracts from PR #10 are reused; they are not duplicated.

All production and evidence files are inside the T02 paths allowed by
`docs/governance/task-owner-map.yaml`. No captain-only path, public Agent schema,
`app/agents/**`, or shared-change-required `app/contracts/**` path is modified.

## Implemented data flow

1. The first Reviewer result is snapshotted as a complete `ReviewFeedback`.
2. Stable `IssueClosure` records and source-bound failure reasons are derived from
   `critical_issues`, `required_revisions`, and the Reviewer pass decision.
3. V1 is frozen as the existing Wave A `PlanVersion`, including the full hypothesis,
   experiment, Reviewer feedback, open issues, and complete-input fingerprints.
4. The second-round input contains `previous_plan`, `previous_plan_version`,
   `parent_version_id`, `lineage`, `unresolved_issues`, `failure_reasons`, and the
   complete `reviewer_feedback`. The same structured object is nested under the
   existing `review_result.revision_context`, so the current ExperimentDesigner
   message builder sends it without a change to `app/agents/**`.
5. V1 and V2 experiment structures are compared only across supported substantive
   sections. Narrative rewrites and revision bookkeeping do not count.
6. Each prior blocking issue is mapped to a machine-readable change with its reason,
   before/after values, affected section, evidence references, and closure status.
7. Resolution requires a substantive change, a validated evidence reference, and
   absence of the stable issue from the V2 Reviewer result. Otherwise the issue stays
   open with a reason and the pipeline terminal status stays `draft`.
8. V2 links to V1, and the complete audit plus both `PlanVersion` snapshots is attached
   to the existing V2 AgentTrace event. This preserves the real Agent identity while
   making a complete replayable sidecar available in `agent_trace.json`.

Production locations:

- `app/workflow/explainable_revision.py`
  - `build_experiment_revision_context`
  - `substantive_experiment_diff`
  - `assess_experiment_revision`
  - `revision_trace_fields`
- `app/workflow/pipeline.py`
  - second-round input construction
  - V1/V2 `PlanVersionStore` integration
  - audit attachment and fail-closed terminal status

## Issue-change-evidence-closure contract

Every `RevisionChange` contains:

| Field | Meaning |
| --- | --- |
| `change_id` | Deterministic SHA-256-derived change identity |
| `issue_id` | Stable Wave A `IssueClosure.issue_id` |
| `reason` | Reviewer item and affected experiment section |
| `before` / `after` | Canonical V1/V2 structural values |
| `evidence_refs` | References validated against the evidence catalog |
| `affected_plan_section` | The substantive experiment section |
| `closure_status` | `open` or `resolved` |
| `unresolved_reason` | Required when the mapped change remains open |

False closure claims fail closed: equal before/after values cannot form a change, and a
resolved change must contain validated evidence references. A required revision without
a mapped change, an open critical issue, contradictory Reviewer closure, a missing
reason/evidence, or an exhausted two-round budget remains blocking.

## Substantive change rule

The detector accepts canonical structural changes to:

- experimental variables;
- control groups / baselines;
- experiment steps;
- evaluation metrics;
- safety constraints;
- stopping conditions;
- evidence references.

It ignores changes limited to `technical_details`, `methods`, `revision_iteration`, or
`revision_history`. List order is ignored where order has no experimental meaning;
experiment step order remains meaningful.

## Acceptance matrix

| ID | Formal requirement | Implementation | Test evidence | Result | Status |
| --- | --- | --- | --- | --- | --- |
| T02-B-004 | 让 ExperimentDesigner 读取评审意见、上一版实验、未关闭问题和失败原因；生成可解释修订理由。 | `build_experiment_revision_context`, `inject_revision_context`, and the two-round pipeline integration | `test_experiment_revision_context_carries_previous_plan_and_full_feedback`, `test_failure_reason_ids_are_stable_and_source_bound`, `test_pipeline_experiment_prompt_and_trace_preserve_revision_audit` | Wave B suite: 17/17 passed | PASS |
| T02-B-005 | Experiment revision prompt；问题关闭映射。 | `RevisionChange`, `ExplainableRevisionAudit`, `assess_experiment_revision`, and V1/V2 trace persistence | `test_explainable_mapping_has_required_machine_readable_fields`, `test_issue_closure_requires_change_evidence_and_final_reviewer_clearance`, `test_revision_change_rejects_false_resolution_claims`, `test_issue_closure_round_trip_and_legacy_state_remain_compatible` | Mapping, closure, contradiction, round-trip, and legacy cases passed | PASS |
| T02-B-006 | 实验设计发生实质变化，而不是仅改措辞。 | `substantive_experiment_diff` and pipeline acceptance blocking | `test_non_substantive_rewrites_and_bookkeeping_are_rejected`, seven parameterized structural cases, substantive and repeated-output pipeline cases | Rewrite-only and bookkeeping-only revisions rejected; all seven structural classes accepted | PASS |

## Verification evidence

Implementation-red baseline:

- Command: `python -B -m pytest tests/workflow/test_t02_wave_b_explainable_revision.py -ra`
- Result: 17 collected, 1 passed, 16 expected functional failures, 0 skipped,
  0 errors, 0 warnings, 0.71 s, exit 1.
- First failure: explicit missing Wave B explainable-revision capability.

Focused verification:

- Wave B: 17 passed, 0 failed/skipped/errors/warnings, 0.59 s, exit 0.
- Wave B + Wave A pipeline and revision contracts: 31 passed,
  0 failed/skipped/errors/warnings, 1.14 s, exit 0.
- T02 and pipeline group: 44 passed, 10 existing conditional skips,
  0 failed/errors/warnings, 1.31 s, exit 0.
- ExperimentDesigner group: 34 passed, 1 existing conditional skip,
  0 failed/errors/warnings, 1.17 s, exit 0.
- ScientificReviewer group: 41 passed, 1 existing conditional skip,
  0 failed/errors/warnings, 1.75 s, exit 0.

Repository verification:

- Full pytest: 634 collected, 597 passed, 37 existing conditional skips,
  0 failed/errors/warnings, 30.26 s, exit 0.
- CI lint contract: 3 files checked, 0 failures, exit 0.
- CI type contract: 0 failures, exit 0.
- CI unit: 633 collected, 596 passed, 37 existing conditional skips,
  0 failed/errors/warnings, 27.16 s, exit 0.
- CI integration: 1 passed, 0 failed/skipped/errors/warnings, 0.23 s, exit 0.
- CI security: PASS, critical 0, one pre-existing warning for
  `docs/reproducibility/T09_QUALITY_BASELINE.md`, exit 0.
- CI build: compile, benchmark dry-run, and benchmark schema validation all exit 0.
- `git diff --check`: exit 0.

The existing skips are caused by unavailable repository-scale source fixtures
(`questions_125.json`, booklet PDF) and two Windows symlink privilege probes. No test was
deleted, weakened, marked skip, or marked xfail by this change.
