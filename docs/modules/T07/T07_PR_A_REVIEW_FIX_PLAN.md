# T07 PR-A Request Changes Fix Plan

## Review provenance

- PR: `#12` — https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/12
- Reviewed head: `ea9ca2190457a861782d6c543e989474704039c0`
- Reviewer: `liuyanbo12`
- Review state: `CHANGES_REQUESTED`
- Review URL:
  https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/12#pullrequestreview-4814989999
- Review submitted: `2026-07-30T03:29:46Z`
- Review submissions read: 1
- Inline review comments read: 0
- Conversation comments read: 0
- Review threads read: 0; therefore unresolved inline threads: 0

All reviewer requirements below come from that review submission. Planned
implementation details are kept separate from reviewer wording.

## Issue matrix

| Requirement ID | Severity | Category | Reviewer requirement | Reviewer evidence | Affected path/function | Current behavior | Expected behavior | Reproduction | Regression test | Planned minimal fix |
|---|---|---|---|---|---|---|---|---|---|---|
| `T07-METRIC-007` | P1 | 指标计算不真实；测试覆盖不足 | “检查/识别 3 个 Mock 串题（定量阈值：3）”；在不伪造产物的前提下提供可执行复现或等价自动检测器，证明至少 3 个跨题污染模式，并逐条绑定 Requirement ID。 | Review section `P1-1`; `docs/modules/T07/evidence/day1_contamination_audit.txt:11-19` reports `Count: 0`. | `docs/modules/T07/evidence/day1_contamination_audit.txt`; no owner-scoped executable detector currently exists. | Three static risks are documented, but no command produces three question-bound findings and no metric is computed from executed detector results. | A real command evaluates explicitly marked synthetic Mock records and emits at least three distinct, question-bound contamination findings. The result remains synthetic evidence, not a historical or formal-run claim. | Reviewer command: `Get-Content docs/modules/T07/evidence/day1_contamination_audit.txt`; current output shows zero confirmed reproducible cases. | `test_contamination_detector_reports_three_distinct_cross_question_patterns` | Add an owner-scoped detector plus explicitly marked synthetic fixture and CLI. Compute count and codes from detector output rather than a constant; save command and actual output. |
| `T07-A-003` | P1 | 测试覆盖不足；文档或 PR 证据不足 | “能识别同一疫情方案污染不同题目”； current evidence must move beyond static code locations to executable, question-bound evidence. | Review section `P1-1`; reviewer states there are no reproducible samples and outputs bound to different `question_id` values. | New owner-scoped contamination detector; `tests/batch/**`; T07 evidence. | The audit can name the identical-pandemic-plan risk but cannot execute a check that identifies it across different questions. | Detector flags identical normalized content reused across distinct question IDs and reports both IDs without classifying the result as actual. | Run the planned detector against the marked-synthetic review fixture and inspect the emitted finding containing both question IDs. | `test_detector_flags_identical_content_across_question_ids` | Detect cross-question content fingerprint reuse from supplied records, return stable finding code and sorted question IDs, and document the exact synthetic limitation. |
| `T07-A-007` | P1 | 失败隔离缺失；resume 行为缺失；状态序列化测试不足 | “实现 resume、失败隔离、状态序列化”； inject one failed Job, allow the other 124 Jobs to continue/finish the skeleton step, and report correct status counts. | Review section `P1-2`; reviewer identifies `app/batch/runner.py` as single-job bookkeeping only and `tests/batch/test_runner.py` as missing a one-fails/others-continue test. | `BatchRunner`; `register_failure`; `resume_job`; `BatchJob`; `CheckpointRecord`; `BatchManifest`; `tests/batch/**`. | `register_failure` records one job failure, but there is no batch scheduler loop that catches one job exception, persists it, and continues. Resume does not bind `source_hash`; negative coverage for corrupt JSON, cross-question checkpoints, route identity, and report-existence completion is incomplete. | Batch processing isolates processor exceptions per job, records a stable error code/attempt/reason, persists each resulting checkpoint, continues all remaining jobs, and serializes an aggregate manifest with truthful status counts. Resume fails closed on identity, source/input hashes, schema/checkpoint, route/model, and prompt provenance mismatch. | Reviewer command: `python -m pytest -q tests/batch -vv`; inject a processor failure for one selected ID and inspect 1 failed plus 124 continued skeleton states. | `test_batch_failure_is_isolated_and_remaining_124_jobs_continue`; focused resume and serialization tests for source hash, question mismatch, corrupt JSON, route mismatch, and round-trip. | Add a provider-independent isolated batch step that passes a deep job copy to an injected processor, validates immutable identity, converts one exception into `JOB_EXECUTION_FAILED`, persists each checkpoint, and continues. Extend checkpoint provenance and fail-closed tests without implementing a real model run. |
| `T07-A-008` | P1 | 文档或 PR 证据不足 | “PR-A Ready；dry-run/resume 报告”； complete the Day 3 report and failure isolation, then the team member changes the PR from Draft to Ready and requests re-review. | Review section `P1-3`; PR #12 is Draft and the PR checklist leaves Day 3 and Ready unchecked. | `docs/modules/T07/**`; PR #12 external state. | Day 2 dry-run evidence exists, but there is no review-round resume/failure-isolation report. PR remains Draft. | Current-head report contains reproducible resume, failure-isolation, serialization, output-contract, and dry-run evidence. Ready remains an explicit manual GitHub action after the authorized push. | Reviewer command: `gh pr view 12 --repo sage125-ai-scientist-team/SAGE125-AI-Scientist --json isDraft,url`. | Evidence validation commands plus focused tests mapped to this Requirement ID. | Create a T07 owner-scoped Day 3 review report and four evidence files from actual commands. Do not edit the PR, mark Ready, push, reply, or resolve threads in this task; report Draft as the remaining external blocker. |
| `P2 review cluster` | P2 | 契约增强；负向测试密度；其他 owner 路径依赖 | Reviewer suggests: align `docs/contracts/T07.md`; enhance manifest with `total` / `status_counts` / `manifest_sha256`; add path traversal, atomic-write fault, corrupt-checkpoint, and batch-failure negative tests. | Review section `P2（不阻断本轮设计方向）`; no inline thread or separate reproduction command was supplied. | `app/contracts/batch.py`; `app/batch/checkpoint.py`; `tests/batch/**`; `docs/contracts/T07.md` is outside the current task allowlist. | Manifest has no derived total/status count fields. Existing tests cover invalid `batch_id`, stale hash/version, and successful atomic writes, but not all suggested fault paths. | Owner-scoped metrics are derived from actual jobs and reject inconsistent serialized values; negative tests prove fail-closed behavior. | Inference / requires verification: run focused contract/checkpoint tests and compare serialized totals to actual job states. | `test_manifest_derives_total_and_status_counts`; atomic-write failure cleanup and corrupt checkpoint tests. | Implement derived `total` and `status_counts` with consistency validation plus owner-scoped negative tests. Defer `manifest_sha256` unless a non-self-referential contract is explicitly approved. Record `docs/contracts/T07.md` as a cross-owner blocker and do not modify it. |

## Reviewer requirement meanings

### `T07-METRIC-007`

The reviewed metric is not “write the number 3.” It requires executable
evidence that actually detects three Mock cross-question contamination
patterns. The reviewer explicitly accepts an equivalent automatic detector,
provided findings are tied to question IDs and are not fabricated formal
artifacts.

### `T07-A-003`

The acceptance evidence must demonstrate that the same pandemic-style plan
reused for different questions is detectable. Static references to risky code
are insufficient; an executed detector must identify the cross-question reuse.

### `T07-A-007`

Wave A requires batch-level failure isolation in addition to the existing
single-job failure record and resume compatibility functions. One injected
failure must not abort the other 124 skeleton jobs, and serialized states and
counts must remain correct. The review also includes Ready status, but GitHub
state changes are outside this task's authorization.

### `T07-A-008`

The missing deliverable is a current-head dry-run/resume/failure-isolation
report plus PR Ready state. This task can produce the report and evidence only.
Changing Draft to Ready remains a manual team-member action.

### P2 cluster

The reviewer supplied one non-blocking cluster with three suggestions:
contract-doc alignment, richer manifest summary fields, and denser negative
tests. Only the latter two are within the explicit current owner allowlist.

## Scope and cross-owner decision

The requested review fixes can otherwise remain within:

- `app/batch/**`
- `scripts/batch_125/**`
- `app/contracts/batch.py`
- `tests/batch/**`
- `docs/modules/T07/**`

`docs/contracts/T07.md` is not in this task's explicit allowlist. It will not
be created or modified. This is recorded as a P2 cross-owner blocker rather
than treated as authorization inferred from the review.

## Planned execution order

1. Reproduce the current zero executable-contamination-evidence state.
2. Add failing contamination detector tests for three distinct patterns.
3. Implement the minimal detector and marked-synthetic CLI evidence.
4. Add failing batch-isolation and resume provenance tests.
5. Implement source/prompt provenance, derived manifest counts, and isolated
   per-job processing with atomic checkpoint/manifest persistence.
6. Add corrupt-checkpoint and atomic-write-failure negative tests.
7. Run reviewer commands, compileall, targeted tests, all `tests/batch`, full
   pytest, and the synthetic dry-run.
8. Write only current-head evidence under `docs/modules/T07/evidence/**`.
9. Verify owner scope and report PR #12 as Draft without changing GitHub state.

## Implementation result

- `T07-METRIC-007`: detector CLI computed 3 distinct findings from an
  explicitly marked synthetic Mock fixture.
- `T07-A-003`: identical pandemic-plan content across Q901/Q902 is detected.
- `T07-A-007`: isolated processor visits all 125 jobs; injected Q063 failure
  produces 1 failed and 124 checkpointed jobs with truthful derived counts.
- `T07-A-008`: Day 3 resume/failure report and all four required evidence
  files are present. PR Ready remains a prohibited external write in this task.
- P2: manifest total/status counts and owner-scoped negative tests are
  implemented; cross-owner contract-doc alignment remains deferred.
- Final read-only comparison found the PR head is now 6 commits behind the
  current central integration tip. Sync is not performed because this task
  explicitly prohibits merge/rebase.
