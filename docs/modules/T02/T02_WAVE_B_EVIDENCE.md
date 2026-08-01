# T02 Wave B technical acceptance evidence

## Audited baseline

- Branch: `t02/b-explainable-experiment-revision`
- Captain-reviewed old HEAD: `0811a4a66148a962732d0729cedf3cc92a8bb093`
- Latest `upstream/integration/2026-08-10`: `898cc08fd434caf926bd3b765870057399f1c788`
- Ordinary merge commit: `f8d48c75a8e47994bbc899f9859854a55d9138d3`
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
| T02-B-013 | 接入 EvidenceBundle 与人工反馈 RevisionContext；完成 T03 配对审查；补迁移测试。 | strict optional `EvidenceBundle` and `HumanFeedbackDirective`; T03 frozen interface pairing | cross-contract message test; T03 contract examples; revision migration tests | PASS |
| T02-B-014 | 联调提交；配对审查记录。 | T01/T03 imports are consumed without modifying either module; T03 interface freeze is the written pair record | this commit; T03 interface freeze sections cited above | PASS |
| T02-B-015 | 评审与人工反馈均进入下一轮；字段兼容有测试。 | `RevisionRoundInput` plus revision-aware adapters | strict three-Agent pipeline and legacy/round-trip tests | PASS |
| T02-B-016 | 运行真实或准真实两轮案例，核对 input/output/hash/version/score/closure；补 candidate hypothesis 排名。 | `TwoRoundCaseReport`, score deltas, deterministic ranking | `T02_METRIC_003_CASE.json`; metric test | PASS |
| T02-B-017 | 两轮 trace；差异报告；排名结果。 | AgentTrace sidecars, `ExplainableRevisionAudit`, frozen metric result | `T02_METRIC_003_RESULT.json`; pipeline audit test | PASS |
| T02-B-018 | V2 明确回应 V1 问题；差异可解释。 | resolved V1 issue count and issue-change-evidence mapping | metric report resolves 2 V1 issues with 2 mapped changes | PASS |
| T02-METRIC-003 | V2 明确回应 V1 问题；差异可解释。（定量阈值：1 问题） | strict `TwoRoundCaseReport` and frozen manifest/result | responded_issue_count=2, threshold=1, passed=true | PASS |
| T02-B-019 | 同步最新 integration，全测试与最小 E2E；trace 导出、迁移和回滚；review 后转 Ready。 | integration merge; trace sidecars; Wave A migration; controller rollback; full verification | commands below; rollback and metric E2E tests | PASS (technical Ready criteria); external Ready transition follows the final push |
| T02-B-020 | PR-B Ready；可复现案例包。 | manifest, raw result, command, commit reference, PR #21 | evidence files plus final remote/PR state check | PASS (reproducibility and technical Ready criteria); external Ready transition follows the final push |
| T02-B-021 | 关键链路可复现；P0/P1 关闭；分支 up to date。 | all technical P1 items above; behind=0; six gates | final verification below | PASS; final remote equality is verified after push |

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

All technical Ready conditions are satisfied at the verified implementation commit.
The PR Draft-to-Ready transition is deliberately performed only after these evidence
files are committed, the branch is pushed without force, and the remote HEAD and
behind count are rechecked.

PR #11 closure and the #11/#21 relationship remain captain-owned process work. This
technical change does not modify, close, review, approve, or merge PR #11 or PR #21.
