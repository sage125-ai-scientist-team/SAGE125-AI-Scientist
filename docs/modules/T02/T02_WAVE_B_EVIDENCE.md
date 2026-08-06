# T02 Wave B technical acceptance evidence

## Audited baseline

- Branch: `t02/b-explainable-experiment-revision`
- Three-redlight remediation input HEAD: `a19e790ed634fd162405434e618cdb9f9c1c08de`
- Paired T03 PR #32 HEAD: `eec7a9c85a5ba3df805aa5f63c96fe309f03d206`
- Captain-reviewed old HEAD: `0811a4a66148a962732d0729cedf3cc92a8bb093`
- Latest `upstream/integration/2026-08-10`:
  `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`
- Latest ordinary merge commit: `3224dba97c2e801f4feecb2daac2b5943b376e32`
- Three-redlight implementation commit:
  `62fd4b5394c067aa8949770d7c6377065725f388`
- Technical implementation and verification commit:
  `65b4fddf6e1cced59bc809a08bd6087bbc6b79da`
- Verification source: `docs/governance/task-requirements/T02.yaml`, especially
  `T02-B-001..021` and `T02-METRIC-003`.
- No code or commit from legacy PR #11 was merged or cherry-picked. Commit
  `ce9b079bdd2507475bd7ac4a998e89989210cb08` is not an ancestor of this branch.

All technical changes are under T02-owned paths from
`docs/governance/task-owner-map.yaml`: `app/workflow/**`, `tests/workflow/**`, and
`docs/modules/T02/**`. This change does not modify `app/contracts/**`, `app/agents/**`,
governance files, dependencies, or another task's implementation.

## ReviewFeedback / revision_context conflict

The conflict was real. The previous transport inserted `revision_context` into
`review_result`, but `ReviewFeedback` has `ConfigDict(extra="forbid")`. A serialized
revision-round `review_result` therefore failed `ReviewFeedback.model_validate`, even
though the main pipeline happened to snapshot the pure feedback before injection.
This made the public shape unsafe for deserialization and downstream reuse.

The fix keeps exactly one strict placement:

```text
revision input
├── review_result: ReviewFeedback
└── revision_context: ExperimentRevisionContext
```

`RevisionRoundInput` validates the pair with `extra="forbid"`. Workflow-owned
revision-aware Agent adapters preserve the sibling in the actual HypothesisGenerator,
ExperimentDesigner, and ScientificReviewer user messages. No `ValidationError` is
caught or discarded, no untyped transport dictionary replaces a structured model,
legacy inputs without `revision_context` still use the unchanged Agent path, and both
strict objects pass JSON round trips without field loss.

Tests:

- `test_revision_context_is_a_strict_sibling_of_review_feedback`
- `test_t01_bundle_and_t03_human_feedback_reach_revision_messages`
- `test_pipeline_uses_one_strict_revision_type_for_all_three_agents`

## Cross-contract pairing

- T01: `EvidenceBundle` from `app/contracts/evidence.py` is an optional strict member
  of `ExperimentRevisionContext`; its link and evidence integrity validators run
  before prompt injection.
- T03: `HumanFeedbackDirective` from `app/contracts/validation.py` is the only accepted
  human-feedback prompt object. It must target the V1 parent exactly; rejected or raw
  feedback is not forwarded.
- Pairing record: `docs/modules/T03/T03_INTERFACE_FREEZE.md`, section **T02 对齐**,
  explicitly keeps T02 ownership and requires T03 to avoid attaching fields to T02
  `extra="forbid"` objects. `docs/modules/T03/T03_VALIDATION_RFC.md`, section 3.3,
  freezes the `human_feedback` wire shape consumed here.
- The paired pipeline test proves the same validated `ReviewFeedback`,
  `EvidenceBundle`, and `HumanFeedbackDirective` reach all three second-round Agent
  messages.

## 2026-08-04 three-redlight remediation

The pre-change paired run used T02 `a19e790ed634fd162405434e618cdb9f9c1c08de`
and T03 `eec7a9c85a5ba3df805aa5f63c96fe309f03d206`. It executed T02's production
pipeline and Agent serialization path with Mock LLM output plus T03's real temporary
SQLite adapter. It collected 5 tests: 2 passed and 3 failed in 1.52 seconds (exit 1).
The first failure was `KeyError: 'human_feedback'`; the other failures were missing
`execution_metadata.revision_metadata` and a restored T03 lineage containing only
`feedback_submitted -> feedback_decided`.

T02 now emits one accepted-only frozen receipt at the final Agent boundary:

```json
{
  "human_feedback": {
    "schema_version": 1,
    "feedback_id": "feedback-pair-001",
    "source_version_id": "t02-t03-pair:v1",
    "disposition": "partially_accepted",
    "applied_instructions": ["<accepted instruction>"],
    "original_feedback_sha256": "<sha256>"
  }
}
```

`HumanFeedbackReceipt` is `extra="forbid"` and frozen. It is derived only from the
frozen `HumanFeedbackDirective`; rejected items, raw feedback, and decision reason
never enter the payload. The same receipt is present in the actual second-round
HypothesisGenerator, ExperimentDesigner, and ScientificReviewer JSON messages and
matches the nested `revision_context.human_feedback` identity.

The canonical structured diff is exactly `{changes, substantive_sections}` and is
hashed once. In the deterministic owner-path run, the complete value was:

```text
4f0f9fda9eef9b57a467fd243101aa4fce43af1789561f5ba92f7902d0070397
```

That value is identical in `StructuredRevisionDiff.fingerprint()`,
`execution_metadata.revision_metadata.diff_hash`, AgentTrace
`revision_diff_sha256`, `RevisionLineageHandoff.revision_diff_sha256`, and the
`revision_generated.payload_sha256` handoff event. The execution receipt also records
`feedback_id`, source `t02-t03-pair:v1`, direct child `t02-t03-pair:v2`, the actual
prompt fingerprint, and accepted instructions. Conflicting pre-existing metadata is
rejected rather than overwritten.

T02's stable append-ready event handoff from that run was:

| Sequence | Event | event_id | parent_event_id | payload SHA-256 |
| --- | --- | --- | --- | --- |
| 1 | `revision_requested` | `event:55f7ecda13127579` | external T03 `feedback_decided` required | `5d7cde2ed7296e3990a19129ffb73eba7336869dad67f704bf405833d3a9193e` |
| 2 | `revision_generated` | `event:73f66880eefc20da` | `event:55f7ecda13127579` | `4f0f9fda9eef9b57a467fd243101aa4fce43af1789561f5ba92f7902d0070397` |
| 3 | `issue_closed` | `event:a2c31e666da5b460` | `event:73f66880eefc20da` | `ea369a0934ae3c316531f7595141dc9760655e8a121f867ad097cbda5e2c92bc` |
| 4 | `issue_closed` | `event:d9d644bc57841591` | `event:a2c31e666da5b460` | `fe9dafe71bbff22d566ef3e63c9735670eeaaddbf71f5dea1bd395e206692d57` |

The handoff has a contiguous sequence, unique stable event IDs, canonical direct
parent/child versions, strict JSON round trip, deterministic rebuild, and tamper
fail-closed validation. Its first event deliberately declares
`required_parent_event_type="feedback_decided"` and leaves `parent_event_id` unset:
T02 receives only `HumanFeedbackDirective`, not T03's `FeedbackStore`, lineage ID,
decision ID, or last event ID. T03 must bind that external parent, add actor/time,
append these events atomically, then append its owner events `gate_evaluated` and
`validation_completed`. T02 does not fabricate those values or write another owner's
SQLite store.

After overlaying the implementation on the exact T03 paired branch, the same five
tests improved to 3 passed and 2 failed in 1.55 seconds (exit 1). The Agent receipt,
direct unique child, execution metadata, and trace hash assertions passed. Both
remaining failures occur only after reopening T03 SQLite: the stored lineage still
has `revision_diff_sha256=None` and no post-decision events because PR #32 does not
yet consume the new handoff. This is an explicit T03 integration blocker, not a T02
owner-path test failure. It is not counted as production/live E2E success.

## Complete Wave B matrix

| ID | Formal requirement | Implementation | Test / evidence | Result |
| --- | --- | --- | --- | --- |
| T02-B-001 | 从最新 integration 新建 B 分支；将 critical_issues、required_revisions、comments 和 issue_id 注入下一轮假设生成。 | `RevisionPromptBuilder`, `issues_for_revision`, revision-aware HypothesisGenerator path | `test_review_feedback_enters_second_hypothesis_input`; strict three-Agent pipeline test | PASS |
| T02-B-002 | Hypothesis revision prompt。 | `RevisionPromptBuilder.build_hypothesis_input`; sibling `RevisionRoundInput` | Wave A pipeline contract tests; strict three-Agent pipeline test | PASS |
| T02-B-003 | trace 可定位意见来源；输入 hash 发生合理变化。 | complete-input fingerprints, stable issue/failure IDs, `revision_trace_fields` | `test_feedback_changes_second_round_input_fingerprint`; trace audit tests | PASS |
| T02-B-004 | 让 ExperimentDesigner 读取评审意见、上一版实验、未关闭问题和失败原因；生成可解释修订理由。 | `ExperimentRevisionContext`, strict message adapters, `RevisionChange.reason` | context, message, and pipeline audit tests | PASS |
| T02-B-005 | Experiment revision prompt；问题关闭映射。 | `RevisionChange`, `ExplainableRevisionAudit`, `IssueClosure` mapping | mapping, false-closure, round-trip tests | PASS |
| T02-B-006 | 实验设计发生实质变化，而不是仅改措辞。 | `substantive_experiment_diff`; duplicate V2 is not saved | rewrite/bookkeeping rejection plus seven structural-section cases | PASS |
| T02-B-007 | 生成 V1/V2 structured diff、issue closure、评分变化和 lineage；最大轮数、无改进停止、人工暂停和重试；Draft PR-B。 | audit diff/closure/score/ranking/lineage; `RevisionExecutionController`; bounded retry; `no_improvement` | controller, retry, ranking, no-improvement, pipeline tests | PASS |
| T02-B-008 | 版本服务；停止策略；Draft PR-B。 | Wave A `PlanVersionStore` plus strict serialized control checkpoint; PR #21 is the Draft PR-B | version store tests; controller serialization test; PR #21 | PASS |
| T02-B-009 | 一次迭代可完整回放；无无限循环。 | V1/V2 inputs, hashes, audit, plan snapshots, control checkpoint, max iteration=2 | pipeline trace replay and controller bound tests | PASS |
| T02-B-010 | 测试超时、空 reviewer、重复事件、断点恢复和重复提交；失败不产生重复版本。 | `run_revision_step_with_retry`; event/version idempotency; serialized restore; no V2 on no improvement | timeout-once, empty-output, duplicate claim/save, restore tests | PASS |
| T02-B-011 | 稳定性测试报告。 | This document plus `revision_control` and `two_round_case_report` trace sidecars | 8 hardening tests; 120-item cross-contract regression | PASS |
| T02-B-012 | 重复回调幂等；失败可恢复且有停止原因。 | `claim_event`, `record_version`, retry budget, `stop_reason`, deserialize | controller idempotency/recovery test | PASS |
| T02-B-013 | 接入 EvidenceBundle 与人工反馈 RevisionContext；完成 T03 配对审查；补迁移测试。 | strict optional `EvidenceBundle` and `HumanFeedbackDirective`; frozen receipt, metadata, and lineage handoff | owner-path tests PASS; paired production-path test 3/5 after fix | T02 output PASS; T03 persistence consumption BLOCKED |
| T02-B-014 | 联调提交；配对审查记录。 | T01/T03 imports are consumed without modifying either module; this remediation records exact paired SHAs and failures | this document; T03 interface freeze; paired command below | BLOCKED pending T03 re-run and external sign-off |
| T02-B-015 | 评审与人工反馈均进入下一轮；字段兼容有测试。 | `RevisionRoundInput` plus revision-aware adapters | strict three-Agent pipeline and legacy/round-trip tests | PASS |
| T02-B-016 | 运行真实或准真实两轮案例，核对 input/output/hash/version/score/closure；补 candidate hypothesis 排名。 | `TwoRoundCaseReport`, score deltas, deterministic ranking | `T02_METRIC_003_CASE.json`; metric test | PASS |
| T02-B-017 | 两轮 trace；差异报告；排名结果。 | AgentTrace sidecars, `ExplainableRevisionAudit`, frozen metric result | `T02_METRIC_003_RESULT.json`; pipeline audit test | PASS |
| T02-B-018 | V2 明确回应 V1 问题；差异可解释。 | resolved V1 issue count and issue-change-evidence mapping | metric report resolves 2 V1 issues with 2 mapped changes | PASS |
| T02-METRIC-003 | V2 明确回应 V1 问题；差异可解释。（定量阈值：1 问题） | strict `TwoRoundCaseReport` and frozen manifest/result | responded_issue_count=2, threshold=1, passed=true | PASS |
| T02-B-019 | 同步最新 integration，全测试与最小 E2E；trace 导出、迁移和回滚；review 后转 Ready。 | latest integration merge; trace handoff; Wave A migration; controller rollback; full verification | commands below | T02 gates PASS; cross-owner persisted E2E BLOCKED at T03 consumption |
| T02-B-020 | PR-B Ready；可复现案例包。 | manifest, raw result, command, implementation commit, PR #21 | evidence files and post-push remote check | T02 package PASS; no new Ready/status action performed |
| T02-B-021 | 关键链路可复现；P0/P1 关闭；分支 up to date。 | T02 path reproducible; behind=0; six local gates PASS | final verification below | BLOCKED: paired persisted lineage P1 remains T03-owned |

## METRIC-003 reproducibility package

- Dataset manifest: `docs/modules/T02/evidence/T02_METRIC_003_CASE.json`
- Computation test:
  `tests/workflow/test_t02_wave_b_contract_hardening.py::test_metric_003_case_report_is_round_trip_safe_and_ready_gated`
- Raw result and metrics: `docs/modules/T02/evidence/T02_METRIC_003_RESULT.json`
- Reproduction command:

  ```powershell
  .venv\Scripts\python.exe -B -m pytest tests/workflow/test_t02_wave_b_contract_hardening.py::test_metric_003_case_report_is_round_trip_safe_and_ready_gated -ra
  ```

- Threshold: 1 V1 issue explicitly answered by V2.
- Actual: 2 resolved V1 issues, 2 issue-to-change mappings, distinct V1/V2
  fingerprints, structured experiment diff, score changes, candidate ranking, PASS.

## Verification results

The following table is the current three-redlight remediation run; older results
below it are retained only as historical evidence for the prior implementation.

| Layer | Command | Collected / result | Failed / errors / warnings | Skipped | Duration | Exit |
| --- | --- | --- | --- | --- | --- | --- |
| Paired baseline before fix | T03 `test_t02_t03_final_pairing_recheck.py` on `a19e790` | 5 collected, 2 passed | 3 / 0 / 0; first `KeyError: human_feedback` | 0 | 1.52s | 1 |
| New T02 red tests | `pytest -q tests/workflow/test_t02_t03_revision_handoff.py` before implementation | 3 collected, 0 passed | 3 / 0 / 0; three missing keys | 0 | 1.13s | 1 |
| New T02 tests after fix | same command after implementation | 3 collected, 3 passed | 0 / 0 / 0 | 0 | 0.85s | 0 |
| T02 core | four T02/revision pipeline files | 35 collected, 35 passed | 0 / 0 / 0 | 0 | 2.41s | 0 |
| Wave A/B + validation/pipeline/evidence | explicit workflow/validation/pipeline command | 123 collected, 114 passed | 0 / 0 / 0 | 9 existing | 2.71s | 0 |
| T02 + T03 paired after fix | T03 `test_t02_t03_final_pairing_recheck.py` with current T02 files | 5 collected, 3 passed | 2 / 0 / 0; first restored SQLite hash is `None` | 0 | 1.55s | 1 |
| Full pytest | `python -X utf8 -m pytest -q -ra` | 738 collected, 701 passed | 0 / 0 / 0 | 37 existing | 70.24s | 0 |
| lint | `wave_a_quality.py lint` | 3 contract files, no failures | 0 | n/a | combined lint/type 1.6s | 0 |
| type | `wave_a_quality.py type` | no failures | 0 | n/a | combined lint/type 1.6s | 0 |
| unit | CI command, inherited UTF-8 | 737 collected, 700 passed | 0 / 0 / 0 | 37 existing | 67.01s | 0 |
| integration | CI integration command | 1 collected, 1 passed | 0 / 0 / 0 | 0 | 0.32s | 0 |
| security | `scripts/audit_project.py` | PASS, critical=0 | 0 / 0 / 2 existing warnings outside T02 | n/a | 1.2s | 0 |
| build | compileall + benchmark dry-run + validate-result | all three PASS | 0 | n/a | 2.0s | 0 |
| owner / secrets / diff | owner map + targeted secret patterns + `git diff --check` | 0 violations; 0 secret matches; PASS | 0 | n/a | n/a | 0 |

The paired post-fix exit 1 is retained as a blocking cross-owner result. It is not
hidden by the six green repository gates and is not represented as live T08 E2E.

### Historical verification for `65b4fdd` / `a19e790`

| Layer | Command | Collected / result | Failed / errors / warnings | Skipped | Duration | Exit |
| --- | --- | --- | --- | --- | --- | --- |
| Red baseline | `pytest tests/workflow/test_t02_wave_b_contract_hardening.py -ra` | 5 collected, 0 passed | 5 expected capability failures / 0 / 0 | 0 | 0.31s | 1 |
| New hardening | same file after implementation | 8 collected, 8 passed | 0 / 0 / 0 | 0 | 0.43s | 0 |
| Wave B | two `test_t02_wave_b_*` files | 25 collected, 25 passed | 0 / 0 / 0 | 0 | 0.71s | 0 |
| Wave A + Wave B | `pytest tests/workflow -ra` | 39 collected, 39 passed | 0 / 0 / 0 | 0 | 1.25s | 0 |
| Pipeline/Evidence/T03 | exact 120-file-set command recorded in review log | 120 collected, 109 passed | 0 / 0 / 0 | 11 existing | 1.38s | 0 |
| Full pytest | `pytest -ra` | 681 collected, 644 passed | 0 / 0 / 0 | 37 existing | 53.31s | 0 |
| lint | `wave_a_quality.py lint` | 3 files, no failures | 0 | n/a | 0.8s | 0 |
| type | `wave_a_quality.py type` | no failures | 0 | n/a | 0.8s | 0 |
| unit | CI command with inherited `PYTHONUTF8=1` on Windows | 680 collected, 643 passed | 0 / 0 / 0 | 37 existing | 52.43s | 0 |
| integration | CI integration command | 1 collected, 1 passed | 0 / 0 / 0 | 0 | 0.27s | 0 |
| security | `scripts/audit_project.py` | PASS, critical=0 | 0 / 0 / 1 existing warning | n/a | 0.9s | 0 |
| build | compileall + benchmark dry-run + validate-result | all three PASS | 0 | n/a | 1.4s | 0 |
| diff | `git diff --check` and branch diff check | PASS | 0 | n/a | n/a | 0 |

The first Windows unit invocation used `-X utf8` only in the parent process; the
`test_doctor` child emitted local-codepage bytes, causing one decode warning and one
test failure. No test or production file was changed. Setting inherited
`PYTHONUTF8=1`, which makes parent and child match the CI UTF-8 environment, made the
specific test pass and the complete unit gate pass as recorded above.

The 37 skips are unchanged conditional skips for absent repository-scale fixtures
(`questions_125.json`, the booklet PDF) and two Windows symlink-privilege probes. No
test was deleted, weakened, skipped, or xfailed by this change.

## Ready and rollback

`evaluate_wave_b_readiness` is a strict technical gate: accepted revision audit,
passing METRIC-003 report, validated EvidenceBundle, branch up-to-date, and all quality
gates. It does not approve or merge a PR. `RevisionExecutionController` supports an
explicit rollback from V2 to V1 while preserving canonical lineage; original V1 data
and the two-round audit remain addressable.

T02 owner-path implementation and repository quality gates are satisfied at
`62fd4b5394c067aa8949770d7c6377065725f388`. Full paired content compliance remains
blocked until T03 consumes `revision_lineage_handoff`, persists it, appends gate and
validation events, restarts SQLite, and reruns the five-test pairing suite without
failures. This remediation does not change PR Draft/Ready state.

PR #11 closure and the #11/#21 relationship remain captain-owned process work. This
technical change does not modify, close, review, approve, or merge PR #11 or PR #21.

## 2026-08-06 final T02/T03 exact-head pairing sign-off

This section is the authoritative T02-owner recheck for the frozen pair below and
supersedes the earlier cross-owner persistence blockers in this document for this
exact pair only. It does not approve either PR, clear `CHANGES_REQUESTED`, authorize a
merge, or claim that the branches include later integration changes.

### Frozen inputs and isolation

- T02 PR #21 HEAD:
  `20a5b356364051c86dac3698fc836c790b6c2c79`
- T03 PR #32 HEAD:
  `b3c1746530fa9c6f228e030ef281c255ab6b4c47`
- Common PR base used by both frozen heads:
  `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`
- Latest remote `integration/2026-08-10` at sign-off time:
  `f1e2ecd68b075bb8df82992a58397dee71795a60`
- Sign-off time: `2026-08-06T21:50:48+08:00` (Asia/Shanghai)
- Reviewer role/account: T02 owner / `Mk007115`
- Isolation method: detached local clone of the exact T02 HEAD plus the official
  six-commit PR #32 patch whose final `From` commit is the exact T03 HEAD. The patch
  passed three-way apply checking and applied without conflicts. The temporary
  combination was neither committed nor pushed.
- The remote heads were checked before and after creating the combination and were
  unchanged. At sign-off time T02 was `ahead=7, behind=4` relative to the newer
  integration tip; no later integration code was folded into this frozen pairing
  result.

### Independent commands and results

| Layer | Command | Collected | Passed | Failed | Skipped | Warnings | Duration | Exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Formal five-test pairing | `.\.venv\Scripts\python.exe -m pytest -q tests\validation\test_t02_t03_final_pairing_recheck.py` | 5 | 5 | 0 | 0 | 0 | 0.73s | 0 |
| T02 real pipeline/Agent boundary | `.\.venv\Scripts\python.exe -m pytest -q tests\workflow\test_t02_t03_revision_handoff.py` | 3 | 3 | 0 | 0 | 0 | 0.94s | 0 |
| T02 handoff + all T03 validation regressions | `.\.venv\Scripts\python.exe -m pytest -q tests\workflow\test_t02_t03_revision_handoff.py tests\validation` | 108 | 108 | 0 | 0 | 0 | 3.12s | 0 |
| Ephemeral actual-output persistence probe | `.\.venv\Scripts\python.exe -m pytest -q -s pairing_runtime_probe.py` in the isolated combination | 1 | 1 | 0 | 0 | 0 | 1.00s | 0 |

The ephemeral probe invoked T02's production pipeline and three real Agent message
builders, then passed their actual JSON `revision_metadata` and
`revision_lineage_handoff` to T03's `DefaultFeedbackService` and
`SQLiteFeedbackStore`. It used no replacement persistence mock and is not part of the
commit. Its first draft compared an in-memory frozen mapping directly with a mutable
`dict` and failed once; changing only that temporary probe to compare serialized JSON
values produced the final result above. No production or repository test file was
changed for that probe.

### Receipt, versions, hashes, persistence, and replay

- All three V2 Agent JSON messages contained the same top-level frozen, strict
  `human_feedback` receipt with `feedback_id=feedback-pair-001`, source
  `t02-t03-pair:v1`, `partially_accepted`, and only
  `Keep the reviewer-requested negative control explicit.` The rejected instruction
  and the raw combined feedback were absent. Strict JSON round-trip and unknown-field
  rejection passed in the T02 tests.
- The actual plan versions were exactly `[1, 2]`; V1 had no parent, V2 was
  `t02-t03-pair:v2`, and `V2.parent_version_id=t02-t03-pair:v1`.
- The complete actual diff SHA-256 was
  `4f0f9fda9eef9b57a467fd243101aa4fce43af1789561f5ba92f7902d0070397`.
  It matched the canonical `{changes, substantive_sections}` structured diff,
  `execution_metadata.revision_metadata.diff_hash`, AgentTrace
  `revision_diff_sha256`, `RevisionLineageHandoff.revision_diff_sha256`, the
  `revision_generated.payload_sha256`, and the value reloaded from SQLite after
  close/reopen.
- The restored IDs were `feedback-pair-001` and `lineage-lineage-001`; source/result
  were `t02-t03-pair:v1` / `t02-t03-pair:v2`. The stored full revision metadata,
  issue IDs, event order, event IDs, parent IDs, subjects, payload hashes, and times
  survived restart.
- The real SQLite row counts after sequential replay, 8 concurrent duplicate
  submissions, 16 concurrent duplicate handoff consumptions, duplicate validation
  completion, close/reopen, and a post-restart handoff replay were exactly one row in
  each of `feedback_records`, `feedback_decisions`, and `feedback_lineages`.
- Same key/same payload returned the original record; same key/different payload and
  tampered metadata/handoff failed closed. Only one `revision_generated` and one
  `validation_completed` event existed after all replays.

### Restored event chain

The lineage identity for every event is `feedback-pair-001`, source
`t02-t03-pair:v1`, resulting version `t02-t03-pair:v2`, and revision diff
`4f0f9fda9eef9b57a467fd243101aa4fce43af1789561f5ba92f7902d0070397`.
The restored chain was:

| # | event_type | event_id | parent_event_id |
| ---: | --- | --- | --- |
| 1 | `feedback_submitted` | `event-submitted-001` | `None` |
| 2 | `feedback_decided` | `event-decision-ad126a2392737c79be6b` | `event-submitted-001` |
| 3 | `revision_requested` | `event:55f7ecda13127579` | `event-decision-ad126a2392737c79be6b` |
| 4 | `revision_generated` | `event:73f66880eefc20da` | `event:55f7ecda13127579` |
| 5 | `issue_closed` | `event:a2c31e666da5b460` | `event:73f66880eefc20da` |
| 6 | `issue_closed` | `event:d9d644bc57841591` | `event:a2c31e666da5b460` |
| 7 | `gate_evaluated` | `gate-event-3019c994a7200a9645a6bb68` | `event:d9d644bc57841591` |
| 8 | `gate_evaluated` | `gate-event-ac7045178d1f915253a3adf3` | `gate-event-3019c994a7200a9645a6bb68` |
| 9 | `gate_evaluated` | `gate-event-20da65329d7df2da0aba9df6` | `gate-event-ac7045178d1f915253a3adf3` |
| 10 | `gate_evaluated` | `gate-event-b35ca5f041491261281cc723` | `gate-event-20da65329d7df2da0aba9df6` |
| 11 | `gate_evaluated` | `gate-event-793cc28800e2521be7658771` | `gate-event-b35ca5f041491261281cc723` |
| 12 | `gate_evaluated` | `gate-event-f57c95ad37f73ff8e3f839c9` | `gate-event-793cc28800e2521be7658771` |
| 13 | `gate_evaluated` | `gate-event-611a6162589cee9fa3ebd39b` | `gate-event-f57c95ad37f73ff8e3f839c9` |
| 14 | `gate_evaluated` | `gate-event-3437942472af41fc6a61f2a5` | `gate-event-611a6162589cee9fa3ebd39b` |
| 15 | `gate_evaluated` | `gate-event-f1ad0467092e23423863c261` | `gate-event-3437942472af41fc6a61f2a5` |
| 16 | `validation_completed` | `validation-event-cdcba9ca99320fbc91cec730` | `gate-event-f1ad0467092e23423863c261` |

The formerly missing binding is explicit: `revision_requested.parent_event_id` is
the actual restored `feedback_decided.event_id`.

### Final pre-commit gates

| Gate | Current command/result | Exit |
| --- | --- | ---: |
| lint | `wave_a_quality.py lint`: 3 files, `failures=[]` | 0 |
| type | `wave_a_quality.py type`: `failures=[]` | 0 |
| unit | CI-equivalent UTF-8 command: 700 passed, 37 existing conditional skips in 63.39s | 0 |
| integration | CI command: 1 passed in 0.22s | 0 |
| security | `audit_project.py`: PASS, critical=0, 2 existing warnings outside T02 | 0 |
| build | compileall + benchmark dry-run + validate-result: PASS | 0 |
| T02 targeted | five revision/pipeline/pairing files: 42 passed in 1.53s | 0 |
| formal pairing final rerun | exact frozen combination: 5 passed in 0.63s | 0 |
| owner/diff/secrets | one T02-owned evidence file; no violations or secret matches; `git diff --check` PASS | 0 |

The unit skips are the existing missing booklet/questions fixtures and two Windows
symlink privilege probes. The security warnings point to pre-existing non-T02
evidence files. No test was changed, deleted, skipped, xfailed, or weakened.

### T02 owner conclusion and text for the T03-owned pairing record

T02 owner conclusion: **PASS for the exact frozen T02/T03 technical pairing**. The
former T03 persistence blocker for T02-B-013/T02-B-014 is closed for these two HEADs.
T02-B-019/T02-B-021 pairing-path evidence is also technically satisfied, while the
newer integration tip, PR #21 `CHANGES_REQUESTED`, the T03-owned common record, T08
503 work, Ready authorization, approval, and merge remain outside this sign-off.

Text for T03 owner to copy into the T03-owned common pairing record:

> T02 owner `Mk007115` independently rechecked T02 PR #21
> `20a5b356364051c86dac3698fc836c790b6c2c79` with T03 PR #32
> `b3c1746530fa9c6f228e030ef281c255ab6b4c47` on 2026-08-06T21:50:48+08:00.
> The official five-test suite passed 5/5 in 0.73s; T02 production-path plus T03
> validation regressions passed 108/108 in 3.12s. Actual diff hash
> `4f0f9fda9eef9b57a467fd243101aa4fce43af1789561f5ba92f7902d0070397`
> matched structured diff, execution metadata, AgentTrace, handoff, generated event,
> and restarted SQLite. Accepted-only receipt, V1-to-V2 direct lineage, the complete
> 16-event parent chain, same/different-key behavior, 8-way submission concurrency,
> 16-way handoff concurrency, duplicate completion, restart recovery and post-restart
> replay all passed with one child and one lineage. T02 pairing verdict: PASS. This is
> T02 technical sign-off only, not captain approval or merge authorization. Common
> base was `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`; latest integration observed at
> sign-off was `f1e2ecd68b075bb8df82992a58397dee71795a60`.
