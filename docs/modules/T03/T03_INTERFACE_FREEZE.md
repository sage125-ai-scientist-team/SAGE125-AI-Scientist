# T03 Wave A 接口冻结记录

冻结日期：2026-07-30

契约版本：`schema_version=1`

## 1. 冻结的公共符号

`app.contracts.validation`：

- `FeedbackRecord`
- `FeedbackDecision`
- `HumanFeedbackDirective`
- `ValidationContext`
- `Severity`
- `RevisionIssueSnapshot`
- `GateFinding`
- `GateResult`
- `ValidationReport`
- `AuditLineageEvent`
- `AuditLineage`

同一 schema version 内不得：

- 删除或重命名字段；
- 改变枚举拼写；
- 将可空字段改成必填；
- 放宽 P0/P1 阻断规则；
- 将短版本标签 `"v1"` 当成 canonical ID。

新增破坏性语义必须发布 schema version 2，并提供显式迁移。

Python 内存表示采用递归不可变快照；JSON wire shape 仍使用普通 object/array。
调用方不得依赖可原地修改的 list/dict，也不得用未经重新校验的 copy/update 绕过
契约。

## 2. T02 对齐

T02 仍是以下对象的唯一 owner：

- `ReviewFeedback`
- `IssueClosure`
- `RevisionContext`
- `PlanVersion`
- `RevisionState`
- `RevisionPromptBuilder`

T03 不向这些 `extra="forbid"` 对象附加字段。联调边界：

| T02 | T03 |
| --- | --- |
| `PlanVersion.version_id` | `target_version_id` / `version_id` |
| `IssueClosure.issue_id/status` | `RevisionIssueSnapshot` + T03 severity |
| `RevisionPromptBuilder` | 后续接收 `human_feedback` directive |
| `prompt_fingerprints` | AuditLineage payload hash / source ID |

`critical_issue` 不自动等于 P0。Severity 必须由 T03 policy 给出并保留依据。
任何 `resulting_version_id` 必须是 `target_version_id` 的直接下一版，与 T02 连续
PlanVersion lineage 一致。

## 3. T08 对齐

T08 可将请求映射为 `FeedbackRecord`：

| T08 字段 | T03 字段/规则 |
| --- | --- |
| `job_id` | 不是 run_id；先解析 `upstream_run_id` |
| `target_version_id` | 必须传完整 `<run_id>:vN` |
| `feedback` | `FeedbackRecord.feedback` |
| `correlation_id` | 原样保留 |
| receipt `status` | 映射 accepted/partially_accepted/rejected |
| `resulting_version_id` | 来自 `FeedbackDecision` |

`unavailable` 是 API/projection 状态，不是 T03 领域 decision。
T08 不得把 `job_id` 直接写入 `run_id`，也不得返回非直接子版本。

## 4. 冻结的状态与枚举

Feedback disposition：

```text
accepted
partially_accepted
rejected
```

Severity：

```text
P0
P1
P2
P3
```

Gate finding closure：

```text
open
resolved
not_applicable
```

Validation report status：

```text
passed
blocked
```

Audit event type：

```text
feedback_submitted
feedback_decided
revision_requested
revision_generated
gate_evaluated
validation_completed
issue_closed
legacy_unverified
```

## 5. Wave B 延后项

以下内容不属于 Wave A，不能从本 PR 的 Protocol 推断为已经投入生产：

- FeedbackStore 实现；
- 数据库/JSON 持久化；
- 幂等与并发锁；
- 权限、输入长度和 prompt-injection policy；
- API request/response 路由；
- T02 Prompt Builder 接线；
- 完整 Validator 与 Gate 聚合；
- 错误码、迁移脚本、指标和 E2E。

Wave B store 必须把 `save_feedback`、`save_decision`、`save_lineage` 实现为
create-only，并用 `append_lineage_event` 原子追加，不能覆盖既有审计历史。
`decision_sha256` 必须与已保存 FeedbackDecision 的确定性 wire hash 一致；rejected
决策不得关联 resulting version。决策写入使用 `save_decision_and_append` 原子绑定，
并通过 `get_lineage_by_feedback` 在进程重启后恢复对应 lineage。

## 6. 回滚

Wave A 没有修改 pipeline、API 或公共 PipelineState。回滚时删除新增 T03 owner
路径即可；T01/T02/T04 和现有运行产物不会发生格式变化。
