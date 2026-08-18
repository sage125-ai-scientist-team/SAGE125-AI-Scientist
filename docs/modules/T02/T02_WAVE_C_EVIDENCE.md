# T02 Wave C hardening evidence

## Scope and authority

- Requirements completed in this branch: `T02-C-001` through `T02-C-006`.
- Integration start: `c683ab29dae73705ea49d2d59faa813d8f6660ca`.
- Branch: `t02/c-revision-hardening`, created directly from
  `upstream/integration/2026-08-10` at the integration start above with
  ahead/behind `0/0` and a clean worktree.
- PR #21 was `MERGED` before the branch was created; the integration start is
  its merge commit.
- Existing PR: `#37` (`Draft`). No rebase, force-push, replacement PR, approval,
  or merge is part of this hardening work.

No frozen shared contract, T05/T06/T08 implementation, API, frontend, CI,
dependency, lockfile, or governance file is changed. New stability contracts
are workflow-owned sidecars under `app/workflow/**`.

## Red test evidence

The test file was added before the adapter implementation:

```text
.\.venv\Scripts\python.exe -m pytest -q tests\workflow\test_t02_wave_c_execution_multimodal_feedback.py
```

Initial result: `12 failed in 0.30s` (exit 1). Every failure reported the same
missing capability:

```text
No module named 'app.workflow.revision_feedback'
T02-C: bounded execution/multimodal feedback adapter is missing
```

The failures were produced by importing the required production adapter during
each test. No `assert False`, skip, or xfail was used.

The C-004/005 hardening test file was likewise added before its production
modules. Its first run was:

```text
.\.venv\Scripts\python.exe -m pytest -q tests\workflow\test_t02_wave_c_revision_integrity_recovery.py
```

Initial result: `13 failed in 0.50s` (exit 1). Five failures showed the missing
strict context builder timestamp/integrity behavior, and eight showed the
missing durable recovery coordinator/T08 consumer projection. These were real
capability failures; no forced failure, skip, xfail, removed assertion, or
formal mock result was introduced.

## Implementation and data flow

Implementation files:

- `app/workflow/revision_feedback.py`
- `app/workflow/revision_integrity.py`
- `app/workflow/revision_recovery.py`
- `app/workflow/explainable_revision.py`
- `app/workflow/pipeline.py`
- `tests/workflow/test_t02_wave_c_execution_multimodal_feedback.py`
- `tests/workflow/test_t02_wave_c_revision_integrity_recovery.py`

Data flow:

```text
validated ExecutionResult ----------------------+
                                                  |
validated MultimodalArtifact                     |
  -> frozen to_consumer_summary() ----------------+-> build_revision_feedback()
                                                       -> whitelist + limits
                                                       -> canonical SHA-256
                                                       -> ExperimentRevisionContext
                                                       -> RevisionRoundInput
                                                       -> HypothesisGenerator message
                                                       -> ExperimentDesigner message
                                                       -> ScientificReviewer message
```

`run_pipeline_with_state()` and `run_pipeline()` accept optional frozen-contract
instances. The adapter validates these inputs immediately, even if no revision
is eventually triggered. The bounded projection is attached only to the
existing strict second-round envelope. When neither optional input is present,
the builder returns `None`, the Wave C field/fingerprint are omitted from the
agent payload, and all existing Wave A/B calls remain valid.

The actual-execution production-path test uses T05's registered
`LocalProcessRunner`, a scientific entrypoint, validated dataset checksum,
validated artifact checksum, observed metric, and complete Git provenance. It
asserts `actual_execution=True`; no runner-owned truth field is fabricated. The
three revision-aware agents' real `build_messages()` outputs all contain the
same bounded projection. The controlled next-round ExperimentDesigner response
uses the observed execution metric to change `evaluation_metrics` and the T06
artifact validation/source to change `stopping_conditions`; the existing Wave B
audit records both as substantive structured sections rather than a narrative
only iteration.

## Bounded prompt policy

The projection uses explicit allowlists and deterministic ordering. Current
limits are:

| Item | Limit |
| --- | ---: |
| execution metrics | 8 |
| execution artifact manifests | 8 |
| multimodal summaries | 6 |
| units per multimodal summary | 8 |
| column-unit bindings per multimodal summary | 8 |
| failure message | 512 characters |
| source/relative path | 320 characters |
| identifier | 160 characters |
| unit | 96 characters |
| media type | 128 characters |
| complete serialized projection | 32,768 bytes |

Every capped list reports a named count in `dropped_counts`; every shortened
string increments `truncated_field_count` and receives a deterministic SHA-256
suffix. Conflicting duplicate multimodal artifact IDs, mappings passed in place
of validated contract instances, forged runner truth, and a fingerprint that
does not match its frozen projection content are rejected. Dropped counts are a
frozen strict model rather than a mutable post-fingerprint mapping.

The prompt projection excludes:

- full multimodal `data`, `data.rows`, axes, legends, and bounding boxes;
- execution `stdout`, `stderr`, datasets, warning strings, and dependency maps;
- raw artifact bytes, binary bodies, base64 content, and arbitrary large arrays.

It preserves only traceable allowlisted facts: execution/spec/question/parent
IDs, execution and validation status, runner truth flags, Git SHA when provided,
metric name/value/unit/source/artifact ID, artifact path/digest/status, bounded
failure code/message/stage/retryability, multimodal artifact ID/modality/source
path/type/page, units, confidence, validation status, and header/row counts.
No unit or confidence is synthesized: empty T06 units remain empty, confidence
`0.0` remains `0.0`, missing required confidence is rejected by the frozen T06
contract, and execution feedback has no invented confidence field.

## T02-C-004 context integrity

`build_experiment_revision_context()` is the authoritative production builder.
When Wave C evidence is supplied it now requires both a frozen
`ExecutionResult` projection and at least one
`MultimodalArtifact.to_consumer_summary()` projection. Partial Wave C context
fails explicitly instead of entering the next agent round.

The workflow-owned `RevisionContextIntegrity` sidecar contains and cross-checks:

- deterministic `review_id`, critical issues, required revisions, comments,
  and severity from the exact V1 `ReviewFeedback`;
- the bounded execution summary's execution/status/metrics/artifacts/failure
  and provenance flags/identifiers;
- modality, source, value shape (`header_count`/`row_count`), units,
  confidence, and validation status from the frozen multimodal consumer view;
- issue ID, previous/current status, and a required closure reason for every
  resolved issue;
- source version, parent version, generated version, timezone-aware timestamp,
  and a canonical SHA-256 binding all integrity fields.

The context model revalidates the complete V1 snapshot and rebuilds the
integrity envelope on restore. Missing reviewer feedback, execution feedback,
multimodal feedback, lineage provenance, mismatched generated versions, forged
feedback fingerprints, and mismatched context hashes all fail closed.
Legacy Wave A/B calls with no Wave C evidence retain the prior payload shape;
the optional Wave C fields are omitted rather than serialized as null.

## T02-C-005 idempotency and recovery

`RevisionRecoveryCoordinator` replaces the pipeline's separate event claim and
version-save steps with one event-to-version operation. A callback/event ID is
persisted as `in_progress` before generation and then bound to its exact
`PlanVersion`. Re-delivery returns the original version and never appends a
second V1/V2. A checkpoint taken during a paused operation restores the claim,
existing V1, issue state, retry count, failures, and controller status; resume
continues the same event.

Every checkpoint contains controller state, ordered plan snapshots, ordered
event records, issue closures, and a canonical SHA-256. Restore rejects:

- controller/version or controller/event lineage mismatches;
- non-contiguous parents or cross-run versions;
- events referencing missing versions;
- duplicate event/issue IDs;
- resolved issues when generated V2 does not exist;
- any checkpoint whose content no longer matches its digest.

LLM timeouts, empty outputs, and `AgentOutputError` use the existing bounded
retry controller. Frozen terminal execution failures are deduplicated by
`execution_id` before incrementing the same persisted retry/failure record.
The final state records the failure reason, retry count, and stop reason.
Neither a failed nor interrupted run can close an issue without V2; new issues
found by the V2 reviewer may only enter as `not_present -> open`.

## T02-C-006 external consumer view and conflict audit

The V2 AgentTrace now carries `revision_consumer_summary`, a flat self-hashed
projection for T08/UI consumers. It exposes only:

- source/parent/generated version provenance and context hash;
- issue transitions and closure reasons;
- compact change ID, issue ID, affected section, evidence references, and
  closure status;
- current status, retry count, failure/stop reasons, and ordered status events.

It does not contain previous plan objects, hypothesis/experiment snapshots,
stdout/stderr, multimodal rows, or raw execution objects. Therefore no frontend
or T08 parser change is required for consumers to read versions, issues, diffs,
status events, and the stop reason. The internal self-hashed recovery checkpoint
is retained separately for replay and is not the external projection.

The owner-map scan permits every changed path (`app/workflow/**`,
`tests/workflow/**`, `docs/modules/T02/**`). `app/contracts/revision.py` remains
byte-for-byte unchanged, and there are no changes under API, frontend, T05/T06,
CI, or another task owner's path. This satisfies the no-unregistered-shared-file
conflict gate for the current diff.

## Determinism evidence

For the fixed valid test ExecutionResult plus T06 artifact:

- projection fingerprint:
  `4bbba356d85a8f597bb745df269606a2aee8037c9c7996b3afdb3e177019d47a`
- ExperimentDesigner production prompt-hash algorithm:
  `da6a3ed88f84`
- serialized projection: `1552` bytes

Reversing valid multimodal input order produces the same canonical projection,
serialization, and fingerprint. Changing successful execution feedback to a
timed-out failure changes both the complete input fingerprint and prompt hash.

## Verification results

| Layer | Command/result | Exit |
| --- | --- | ---: |
| Wave C red | targeted test before implementation: 12 failed, missing adapter | 1 |
| hardening red | C-004/005 test before implementation: 13 failed on missing integrity/recovery behavior | 1 |
| C-001..005 green | two Wave C files: `25 passed in 1.00s` | 0 |
| production trace + hardening | production pipeline case plus C-004/005 file: `14 passed in 0.97s` | 0 |
| workflow | `pytest -q tests\workflow`: `67 passed in 2.24s` | 0 |
| full pytest | `pytest -q`: `797 passed, 37 skipped in 62.21s` | 0 |
| lint | `wave_a_quality.py lint`: 3 files, no failures | 0 |
| type | `wave_a_quality.py type`: no failures | 0 |
| unit | CI command with inherited UTF-8: `796 passed, 37 skipped in 60.04s` | 0 |
| integration | CI command: `1 passed in 0.22s` | 0 |
| security | `scripts/audit_project.py`: PASS, critical=0, 2 existing warnings | 0 |
| build | compileall + benchmark dry-run + validate-result: all PASS | 0 |
| owner map | final seven-file diff: 7 owned, 0 violations | 0 |
| sensitive scan | final seven-file credential/private-key pattern scan: 0 matches | 0 |
| whitespace | `git diff --check`: PASS | 0 |

The 37 skips are existing conditional tests for unavailable booklet/questions
fixtures and two Windows symlink-privilege probes. No test was deleted,
weakened, skipped, or xfail-marked. The two security warnings refer to existing
T09/T07 documentation and not this change.

The first exact unit attempt on this workstation exposed a Windows parent/child
code-page mismatch in `test_doctor_mock_runs` (`UnicodeDecodeError` while the
`-X utf8` parent decoded redirected child output). The same test had passed in
the full suite. Re-running the unchanged CI unit command with inherited
`PYTHONUTF8=1`, matching the CI UTF-8 environment, passed as reported above; no
test or production behavior was modified to hide it.

Full/unit pytest generated T01 metrics timestamps and `.pytest_tmp` governance
fixtures. The pre-test worktree was clean, so those exact test artifacts were
restored/removed before this evidence file. They are absent from the final diff.

## Formal C-007/C-008/C-009 attempt (2026-08-14)

Captain authority is no longer missing. The formal runner read comment
[`issuecomment-5291084709`](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/37#issuecomment-5291084709)
directly through GitHub CLI, verified publisher `liuyanbo12`, timestamp
`2026-08-14T08:13:44Z`, and all seven frozen authorization fields. The evidence
is bound to runner commit `d09bf87fe25e1a9f29c8bc7a0612652a7f42e3d5`.

The official Science booklet was independently hashed as
`4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576`,
rebuilt in memory to contiguous Q001-Q125 with no quality issues, normalized and
sorted, and reduced to the 124-item population by excluding Q028. Python
`random.Random(20260814).sample(population, 3)` reproduced exactly
`[Q095, Q045, Q100]`. The four selected canonical record hashes are stored in
the dataset manifest; Q028 revalidated as
`badcae2fec281a0bbaec81b36d8ed4a149696db855d0f399e7cbe382fdc78da8`,
and the flagship manifest revalidated as Q028.

The real-provider preflight then failed before any model call because
`DASHSCOPE_API_KEY`/`WORKSPACE_ID` and a substituted compatible-mode
`DASHSCOPE_BASE_URL` are not configured. The runner did not fall back to mock,
fixtures, synthetic output, or another question. It emitted exactly four unique
`CASE_BLOCKED` records in frozen order; Q028 appears only once in raw results
with both `Q028_REGRESSION` and `FLAGSHIP` labels. The derived matrix contains
five logical rows, with both Q028 rows marked `shared_run=true`, but there is no
actual run ID because the provider was never invoked.

| Acceptance item | Result | Evidence-derived value |
| --- | --- | --- |
| T02-C-007 | **BLOCKED** | 0/4 unique actual runs; four `CASE_BLOCKED` records |
| T02-METRIC-004 | **FAIL** | required=3, selected=3, executed=0, passed=0 |
| T02-C-008 | **BLOCKED** | five logical rows derived from four blocked raw records |
| T02-C-009 | **BLOCKED** | no V1/V2 provider runs; false-iteration count is `null` |
| P0/P1 closure | **BLOCKED** | unresolved P0/P1 are `null`, not falsely reported as zero |

Formal evidence package:

- [selection manifest](wave_c_release/selection_manifest.json)
- [dataset manifest](wave_c_release/dataset_manifest.json)
- [provider preflight](wave_c_release/provider_preflight.json)
- [raw results](wave_c_release/raw_results.json)
- [METRIC-004](wave_c_release/metrics.json)
- [regression matrix JSON](wave_c_release/regression_matrix.json) and
  [Markdown](wave_c_release/regression_matrix.md)
- [prompt-hash audit](wave_c_release/prompt_hash_audit.json)
- [P0/P1 closure audit](wave_c_release/p0_p1_closure.json)
- [artifact manifest](wave_c_release/artifact_manifest.json)
- [checksums](wave_c_release/checksums.json)
- [reproduction](wave_c_release/reproduction.md)

All generated evidence checksums revalidated with zero mismatches. Formal runner
tests passed `13/13`; all workflow tests passed `90/90`. Full pytest first
recorded the existing Windows child-codepage failure in `test_doctor_mock_runs`
(`1463 passed, 41 skipped, 1 failed`), then passed unchanged under the exact CI
UTF-8 environment (`1464 passed, 41 skipped`). The formal gates passed: lint,
type, unit (`1432 passed, 41 skipped`), integration (`32 passed`), coverage
(`79.93%`, threshold `65%`), security (`critical=0`), and build. These software
gates do not convert the provider-blocked acceptance items into PASS.

## Known limitations and next work

- Feedback is available to the next revision only when the existing Reviewer
  policy triggers that revision; it does not create an extra revision round.
- The adapter carries result evidence into planning, but it does not execute a
  plan or validate scientific causality.
- Dropped counts report bounded omission; omitted raw values are intentionally
  unrecoverable from the prompt projection and must be retrieved from their
  source systems by trace ID when authorized.
- `T02-C-007` through `T02-C-009` have formally started and are blocked by the
  real-provider preflight described above. A rerun must retain Q095/Q045/Q100;
  it may not substitute cases or reuse these zero-call blocked records as actual
  runs.
- The technical C-004/005/006 gates are satisfied. PR #37 is open and no longer
  a draft, but this blocked local evidence is not eligible for push or Captain
  re-review. This work does not approve or merge the PR.
