# T02 Wave C Day 1 evidence

## Scope and authority

- Requirements completed: `T02-C-001`, `T02-C-002`, `T02-C-003` only.
- Integration start: `c683ab29dae73705ea49d2d59faa813d8f6660ca`.
- Branch: `t02/c-revision-hardening`, created directly from
  `upstream/integration/2026-08-10` at the integration start above with
  ahead/behind `0/0` and a clean worktree.
- PR #21 was `MERGED` before the branch was created; the integration start is
  its merge commit.
- This evidence is not authorization to mark a PR Ready, approve it, merge it,
  or start `T02-C-004` through `T02-C-009`.

No shared contract, T05/T06/T08 implementation, API, frontend, CI, dependency,
lockfile, or governance file is changed.

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

## Implementation and data flow

Implementation files:

- `app/workflow/revision_feedback.py`
- `app/workflow/explainable_revision.py`
- `app/workflow/pipeline.py`
- `tests/workflow/test_t02_wave_c_execution_multimodal_feedback.py`

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
| Wave C green | targeted test: `12 passed in 1.03s` | 0 |
| workflow | `pytest -q tests\workflow`: `54 passed in 2.19s` | 0 |
| full pytest | `pytest -q`: `784 passed, 37 skipped in 59.78s` | 0 |
| lint | `wave_a_quality.py lint`: 3 files, no failures | 0 |
| type | `wave_a_quality.py type`: no failures | 0 |
| unit | CI command with inherited UTF-8: `783 passed, 37 skipped in 59.46s` | 0 |
| integration | CI command: `1 passed in 0.22s` | 0 |
| security | `scripts/audit_project.py`: PASS, critical=0, 2 existing warnings | 0 |
| build | compileall + benchmark dry-run + validate-result: all PASS | 0 |
| owner map | repository review-script parser/glob check: 5 owned, 0 violations | 0 |
| sensitive scan | final five-file credential/private-key pattern scan: 0 matches | 0 |
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

Full/unit pytest generated a T01 metrics timestamp and `.pytest_tmp` governance
fixtures. The pre-test worktree was clean, so those exact test artifacts were
restored/removed before this evidence file. They are absent from the final diff.

## Known limitations and next work

- Feedback is available to the next revision only when the existing Reviewer
  policy triggers that revision; it does not create an extra revision round.
- The adapter carries result evidence into planning, but it does not execute a
  plan or validate scientific causality.
- Dropped counts report bounded omission; omitted raw values are intentionally
  unrecoverable from the prompt projection and must be retrieved from their
  source systems by trace ID when authorized.
- `T02-C-004` through `T02-C-009` have not started.
- The resulting PR must remain Draft. Ready, Approve, Merge, and Close are not
  authorized by this work.
