# T03 Wave A 接口 RFC：人工反馈、完整验证与质量门

状态：v1 frozen

代码权威来源：`app/contracts/validation.py`

## 1. 设计目标

该契约建立三条独立但可关联的边界：

1. 人工反馈：提交、决策和可安全注入下一轮的指令。
2. 完整验证：一次性携带五类产物，执行可阻断验证。
3. 审计 lineage：以 sidecar 连接反馈、版本、决策、质量门和验证报告。

契约不修改 T02 `RevisionContext`/`PlanVersion`，不修改公共
`PipelineState`，也不直接接入 API 或 pipeline。

## 2. 版本标识

所有计划版本必须使用 T02 canonical 格式：

```text
<run_id>:v<positive integer>
```

示例：

```text
run-demo:v1
run-demo:v2
```

仅有 `"v1"` 的 UI 标签不是合法领域 ID。版本 ID 中的 `run_id` 必须与记录中的
`run_id` 一致，且首尾空白不得被静默规范化。

所有契约对象在内存中使用递归不可变快照：序列冻结为 tuple，JSON object 冻结为
`FrozenDict`；`model_dump(mode="json")` 仍输出标准 JSON array/object。

## 3. 人工反馈对象

### 3.1 FeedbackRecord

不可变的原始提交记录：

- `schema_version`
- `feedback_id`
- `run_id`
- `question_id`
- `target_version_id`
- `feedback`
- `source.channel`
- `source.actor_id`
- `correlation_id`
- `submitted_at`
- `request_fingerprint`
- `idempotency_key_hash`（可空，只保存 hash）
- `metadata`

`submitted_at` 必须带时区；fingerprint/hash 必须是小写 SHA-256。

### 3.2 FeedbackDecision

决策状态固定为：

- `accepted`
- `partially_accepted`
- `rejected`

每个决策必须有 `decision_reason`、决策人、时间和 policy version。

约束：

- accepted：`accepted_items` 非空，`rejected_items` 为空；
- partially_accepted：两侧均非空且不得有重叠项；
- rejected：`accepted_items` 为空，`rejected_items` 非空。

`resulting_version_id` 可在新版本产生后补充；存在时必须与目标版本属于同一 run，
且必须是目标版本的直接下一版。rejected 决策不能产生新版本。

### 3.3 HumanFeedbackDirective

这是供 T02 下一轮 Prompt 使用的最小安全对象，只包含：

- `feedback_id`
- `target_version_id`
- accepted/partially_accepted disposition
- `instructions`（仅接受的指令）
- 原始反馈 SHA-256

它不包含原始反馈、不包含 rejected items，也不包含可能复述拒绝文本的 decision
reason。被完全拒绝的反馈不能生成 directive。

建议 T02 后续使用以下 Prompt 键：

```json
{
  "human_feedback": {
    "schema_version": 1,
    "feedback_id": "feedback-001",
    "target_version_id": "run-demo:v1",
    "disposition": "partially_accepted",
    "instructions": ["收紧证伪阈值"],
    "original_feedback_sha256": "..."
  }
}
```

## 4. ValidationContext

五个核心产物均为无默认值的必填字段：

- `research_plan`
- `evidence_cards`
- `agent_trace`
- `execution_metadata`
- `question_item`

附加字段：

- `validation_id`
- `run_id`
- `version_id`
- `revision_issues`
- `human_feedback`
- `correlation_id`

构造阶段执行 fail-closed 身份检查：

1. canonical version ID 必须属于当前 run；
2. ResearchPlan `question_id` 必须等于 QuestionItem `id`；
3. 两侧问题正文规范化后必须一致；
4. ResearchPlan 和 execution metadata 都必须显式包含布尔型
   `actual_execution`；
5. 两侧 `actual_execution` 必须一致。
6. 每条 AgentTrace 必须携带 `run_id`，且必须属于当前 run。
7. 计划、执行元数据、证据和 trace 若携带 run/question/version 身份字段，必须与
   当前上下文一致；证据和 trace 可来自当前版本的祖先版本，但不能来自未来版本。
8. 人工反馈不得指向当前上下文之后的版本。
9. revision issue ID 必须唯一，且不得在未来版本开启或关闭。

`fingerprint()` 对完整 JSON wire shape 计算确定性 SHA-256，供 ValidationReport
绑定精确输入。

空 EvidenceCards/AgentTrace 可以构造上下文，随后由 presence gate 返回结构化失败。
这允许 Validator 报告“缺产物”，而不是调用前直接丢失审计信息。

## 5. Severity、GateFinding 与 GateResult

严重级别：

| Severity | 含义 | 未关闭时是否阻断 |
| --- | --- | --- |
| P0 | 科学真实性、安全或主链路灾难性错误 | 是 |
| P1 | 发布/验收阻断 | 是 |
| P2 | 应修复但可在批准后延期 | 否 |
| P3 | 警告或信息 | 否 |

`GateFinding` 使用稳定 `code`、message、severity、closure status、path 和 source IDs。
`resolved`/`not_applicable` 都必须给出 `resolution_note`；P0/P1 关闭时还必须关联
`issue_id`。

`GateResult` 强制：

- 存在 open P0/P1 finding 时 `passed` 不得为 true；
- passed gate 不得带 errors；
- errors 必须按 P0/P1 处理；
- 只有 P2/P3 finding 时不得把 gate 标为失败；
- failed gate 必须至少有 finding 或 error；
- gate severity 不得低于其最严重 finding。

`from_legacy()`/`to_legacy()` 用于与现有
`{"passed","errors","warnings","score"}` 质量门逐步兼容。legacy `passed` 必须为
布尔值，errors/warnings 必须为字符串数组，禁止把字符串 `"false"` 当成 true。

## 6. ValidationReport

聚合状态为：

- `passed`
- `blocked`

同时给出现有 ResearchPlan 可理解的 `recommended_plan_status`：

- `draft`
- `needs_data`
- `ready_for_validation`
- `validated`

每份报告还必须包含：

- `validation_id`
- `validation_context_sha256`
- 完整 `revision_issues` 快照
- 非空 `gate_results`

推荐通过 `ValidationReport.from_context()` 构造，让报告自动绑定不可变
ValidationContext，而不是由调用方手工复制这些身份字段。

约束：

- 任一 GateResult 有 open P0/P1 时必须 `blocked`；
- 任一 RevisionIssueSnapshot 有 open P0/P1 时也必须 `blocked`；
- 任何阻断报告均不得建议 `ready_for_validation` 或 `validated`；
- `passed` 要求所有 gate 均通过。

因此 P0/P1 未关闭时不会出现“validation passed”。

## 7. AuditLineage

T03 使用 append-only sidecar，不向 T02 `PlanVersion` 塞入额外字段。

lineage 直接关联：

```text
feedback_id
  -> feedback_sha256
  -> target_version_id
  -> decision_id
  -> decision_disposition
  -> decision_sha256
  -> resulting_version_id
  -> revision_diff_sha256
  -> validation_report_id
  -> issue_ids
```

事件必须：

- `event_id` 唯一；
- 以 `feedback_submitted` 或 `legacy_unverified` 开始；
- 首事件 payload hash 必须等于完整 FeedbackRecord 的确定性 SHA-256；
- 首事件无 parent，后续 parent 必须精确指向紧邻前一事件，形成单链；
- event type 必须按提交、决策、修订、关闭、gate、验证的顺序推进；
- feedback/decision/result/report/issue 事件 subject 必须匹配顶层关联 ID；
- decision ID 必须同时携带 disposition 和完整决策 SHA-256；
- `feedback_decided.payload_sha256` 必须等于该完整决策 SHA-256；
- rejected 决策不得出现 revision request、resulting version 或 revision diff；
- resulting version 必须是 target version 的直接下一版；
- `revision_generated.payload_sha256` 就是结构化 diff 的 SHA-256，并必须等于
  顶层 `revision_diff_sha256`；
- 时间顺序非递减；
- 每个事件保留 payload SHA-256；
- append 返回新快照，不修改旧历史。

`AuditLineage.start()` 从 FeedbackRecord 建立提交事件；`bind_decision()` 原子校验
feedback/version 关联并写入 disposition 与决策 hash，避免只凭 decision ID 伪造
“拒绝后仍生成版本”的历史。

旧字符串历史只能迁移为 `legacy_unverified` 事件，不能自动解释为已接受、已修复或已
通过。

## 8. 服务端口

Wave A 仅冻结 Protocol，不提供生产持久化：

- `app.feedback.storage.FeedbackStore`
- `app.feedback.service.FeedbackService`
- `app.quality.service.QualityGate`
- `app.quality.service.QualityGateRunner`
- `app.validation.service.ValidationService`

`save_feedback`、`save_decision` 和 `save_lineage` 都是 create-only 语义；已有记录
不得覆盖。`save_decision_and_append` 必须在同一事务内保存决策并绑定审计事件；
`get_lineage_by_feedback` 提供重启后的稳定恢复寻址。Wave B 实现这些端口时不得改变
v1 JSON 字段，并须在持久化与 Prompt 边界重新执行 wire round-trip 校验；存储适配
还必须用 `decision_sha256` 与已保存的 FeedbackDecision 交叉核对。

## 9. 可执行示例

`docs/modules/T03/examples/` 包含：

- `feedback_record.submitted.json`
- `feedback_decision.partially_accepted.json`
- `human_feedback_directive.json`
- `validation_context.complete.json`
- `gate_result.blocked_p1.json`
- `validation_report.blocked.json`
- `audit_lineage.complete.json`
- `validation_context.missing_agent_trace.invalid.json`
- `baseline.feedback_not_propagated.json`
- `baseline.validator_question_only.json`
- `t08.feedback_projection.json`

契约示例会逐个执行 `model_validate`；invalid 文件必须稳定失败。两个 baseline 文件
由独立测试校验当前旧链路缺失键，作为可机器复核的失败样例。
