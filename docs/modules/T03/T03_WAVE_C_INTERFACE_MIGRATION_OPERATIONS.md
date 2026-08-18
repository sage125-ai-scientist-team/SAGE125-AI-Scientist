# T03 Wave C 接口、迁移与运维手册

> 状态：DRAFT；面向 T02/T07 调用方和运行维护人员。
> 契约基线：`schema_version=1`；base
> `20592a0eeb9924d021e3ec75ec28d27e2f971e9f`。
> T08 API 适配、HTTP 状态码映射和生产部署不在本次范围内。

## 1. 模块目的与所有权

T03 负责两条 fail-closed 边界：

1. 人工反馈从提交、决策、下一轮 directive、修订 handoff 到 audit lineage 的可追溯闭环；
2. 对 ResearchPlan、EvidenceCards、AgentTrace、`execution_metadata` 和
   `question_item` 的完整上下文执行质量门，并聚合为 `ValidationReport`。

owner 路径为 `app/feedback/**`、`app/validation/**`、`app/quality/**`、
`app/contracts/validation.py`、`tests/validation/**`、`docs/modules/T03/**`。
T03 不直接重构 `pipeline.py`、API 路由或 `app/batch/**`。

## 2. 公共入口与关键符号

### 2.1 契约

`app.contracts.validation` 的 v1 公共对象：

- `FeedbackSource`
- `FeedbackRecord`
- `FeedbackDecision`
- `HumanFeedbackDirective`
- `RevisionIssueSnapshot`
- `ValidationContext`
- `Severity`（`P0`、`P1`、`P2`、`P3`）
- `GateFinding`
- `GateResult`
- `ValidationReport`
- `AuditLineageEvent`
- `AuditLineage`

这些对象是 `extra="forbid"` 的不可变快照。调用方必须通过 JSON/wire shape 传递，
不得依赖内部可变 `dict/list`，不得在 v1 内删除/改名字段、改变枚举拼写或放宽 P0/P1
阻断语义。破坏性变化必须升 schema version 并提供显式迁移。

### 2.2 反馈服务与存储

```python
SQLiteFeedbackStore(path, timeout_seconds=5.0)
DefaultFeedbackService(
    store,
    authorizer=DenyAllFeedbackAuthorizer(),
    max_feedback_length=10_000,
)
```

公共调用：

- `DefaultFeedbackService.submit_request(FeedbackSubmission) -> FeedbackRecord`
- `DefaultFeedbackService.submit(...) -> FeedbackRecord`
- `DefaultFeedbackService.decide(feedback_id, decision) -> FeedbackDecision`
- `DefaultFeedbackService.build_directive(feedback_id) -> HumanFeedbackDirective | None`
- `DefaultFeedbackService.consume_revision_lineage_handoff(...) -> AuditLineage`
- `SQLiteFeedbackStore.get_feedback(feedback_id)`
- `SQLiteFeedbackStore.get_decision(feedback_id)`
- `SQLiteFeedbackStore.get_lineage_by_feedback(feedback_id)`
- `SQLiteFeedbackStore.close()`

安全默认值是 `DenyAllFeedbackAuthorizer`。`AllowAllFeedbackAuthorizer` 只允许用于可信本地
任务和测试，不能作为生产缺省策略。actor 身份位于 `FeedbackSubmission.source.actor_id`。

T02 桥接关键符号：

- `RevisionFeedbackContextBuilder.build(...)`
- `RevisionPromptAdapter.inject(...)`
- `RevisionPromptAdapter.build_hypothesis_input(...)`
- `RevisionPromptAdapter.build_experiment_input(...)`
- `RevisionPromptAdapter.build_reviewer_input(...)`
- `RevisionPromptAdapter.build_execution_metadata(...)`
- `RevisionLineageConsumer.consume(...)`
- `RevisionLineageHandoff`
- `RevisionExecutionMetadata`

所有原始反馈文本保存在受控、不可变的 `FeedbackRecord`/SQLite 记录中，供授权审计读取；
只有 accepted/partially accepted 中的 accepted items 可以进入 directive/prompt。decision 与
lineage 通过结构化原因、ID 和 hash 关联，禁止把 rejected 原文写入 prompt、错误或 metrics。
`resulting_version_id` 必须是 `target_version_id` 的直接子版本。

### 2.3 Validator 与质量门

```python
runner = DefaultQualityGateRunner()
metrics = ValidationMetricsCollector()
service = DefaultValidationService(runner, metrics=metrics)
report = service.validate(context)
snapshot = metrics.snapshot()
```

公共端口：

- `QualityGate.evaluate(context) -> GateResult`
- `QualityGateRunner.run(context) -> list[GateResult]`
- `ValidationService.validate(context) -> ValidationReport`
- `ValidationAuditWriter.record(...) -> AuditLineage`

默认 gate 包含：artifact presence、legacy evidence grounding、results integrity、research-plan
schema、model compliance、reference integrity、execution truth、agent trace 和 human-feedback
propagation。顺序与 gate ID 是审计面的一部分。

## 3. 配置与部署约定

当前 T03 代码没有自行读取环境变量；composition root 必须显式注入：

| 配置 | 默认值/约束 | 运维要求 |
| --- | --- | --- |
| SQLite `path` | 必填；测试可用 `:memory:` | 生产使用明确、持久、可备份的绝对路径；不得落入临时目录 |
| `timeout_seconds` | `5.0`，必须 `>0` | 按写竞争观测调整；超时不得重试为“成功” |
| `max_feedback_length` | `10_000`，必须 `>=1` | 变更需兼容性审查并记录 |
| `authorizer` | deny-all | 生产必须注入真实授权器；鉴权异常按拒绝处理 |
| `clock` | UTC aware now | 测试可注入；生产不得返回 naive datetime |
| metrics collector | 可选、进程内 | 不含原始 feedback；进程重启后会清空，需由上层导出 |

SQLite 初始化启用 foreign keys、WAL、`busy_timeout` 和 `PRAGMA user_version=1`；写入使用
`BEGIN IMMEDIATE`。数据库 schema 高于 1 时拒绝启动，不自动降级。

## 4. 稳定错误码与处理策略

反馈边界可安全映射的机器码：

| code | 含义 | 调用方动作 |
| --- | --- | --- |
| `feedback.invalid_input` | 字段、ID、版本、时间或长度非法 | 修正请求；不要盲重试 |
| `feedback.unsafe_input` | 不安全输入 | 拒绝并审计；不要进入 prompt |
| `feedback.permission_denied` | actor 无权限或鉴权器失败 | 重新鉴权；不要写入 |
| `feedback.not_found` | feedback 不存在 | 核对 ID/租户边界 |
| `feedback.lineage_not_found` | lineage 不存在 | 阻断后续 revision/validation |
| `feedback.conflict` | 已有不可变快照与请求冲突 | 人工检查；不得覆盖 |
| `feedback.idempotency_conflict` | 幂等键已绑定其他语义 | 换正确请求/键；不得重试覆盖 |
| `feedback.fingerprint_conflict` | 指纹碰撞但语义不同 | 阻断并升级审计 |
| `feedback.storage_failure` | SQLite 读写/初始化失败 | 停止写入，检查磁盘/锁/权限后恢复 |
| `feedback.corrupt_snapshot` | 存量 JSON 不能通过 v1 契约 | 隔离数据库，禁止自动修复 |
| `feedback.unsupported_schema` | DB schema 高于当前代码 | 部署兼容版本，禁止降级写入 |

Validator 的稳定 blocker 包括但不限于：

- `NO_QUALITY_GATES`、`VALIDATION_RUNNER_ERROR`、`GATE_EXECUTION_ERROR`；
- `EMPTY_EVIDENCE_CARD`、`EVIDENCE_CARD_ID_MISSING`、
  `EVIDENCE_CARD_ID_DUPLICATE`、`UNKNOWN_EVIDENCE_REFERENCE`；
- `EXECUTION_TRUTH_NOT_BOOLEAN`、`EXECUTION_TRUTH_MISMATCH`、
  `EXECUTION_PROOF_INVALID`、`EXECUTION_PROOF_INCOMPLETE`；
- `AGENT_TRACE_*`、`ACTUAL_EXECUTION_HAS_UNTRUSTED_TRACE`；
- `FEEDBACK_DIRECTIVE_MISSING`、`FEEDBACK_TARGET_NOT_PREVIOUS_VERSION`、
  `REVISION_*_MISSING`、`REVISION_*_MISMATCH`。

错误消息不得包含原始反馈、密钥或完整内部异常。稳定 code 用于聚合，详细堆栈仅进入受控
应用日志。

## 5. 指标说明

`ValidationMetricsCollector` 按 `(question_id, version_id)` 聚合，并按 `report_id` 幂等去重。
`ValidationMetricBucket` 包括：

- `validations`、`passed_validations`、`blocked_validations`；
- `evaluated_gates`、`passed_gates`、`gate_pass_rate`；
- `findings_by_code`、`findings_by_severity`；
- `tracked_revision_issues`、`resolved_revision_issues`、
  `revision_closure_rate`。

指标不保存原始反馈文本。进程内 collector 不是持久时序数据库；发布环境需要由 composition
root 在固定间隔或运行结束时导出 `ValidationMetricsSnapshot`。导出失败不得改变 validation
结论，但要生成运维告警。

## 6. 旧反馈迁移

入口：

- `migrate_legacy_feedback_payload(payload)`：只转换，不写库；
- `import_legacy_feedback(payload, store)`：转换并持久化；
- `migrate_legacy_feedback`：前者的别名。

迁移流程：

1. 在只读副本上解析旧 JSON；
2. 核对 run/question 与 canonical `<run_id>:vN`；
3. 生成确定性的 feedback/lineage ID 和 request fingerprint；
4. 以 `source.channel="migration"` 写入；
5. 首事件固定为 `legacy_unverified`；
6. 重复导入必须幂等；关闭并重开 SQLite 后再次校验；
7. 只有审阅后的新决策才能进入下一轮。

旧字段 `accepted`、`passed` 或字符串历史**不会**自动升级为接受决策、validation pass 或
已核验 lineage。未来 schema、非法 ID、naive timestamp、控制字符和超长内容均 fail closed。

## 7. 备份、恢复与完整性核验

备份前：

1. 暂停 T03 写入或让上层进入维护态；
2. 确认所有 `SQLiteFeedbackStore` 写事务结束；
3. 使用 SQLite 官方 backup API/运维工具生成一致性副本；不要只复制主文件而遗漏 WAL；
4. 对备份文件计算 SHA-256，记录源 DB 路径、UTC 时间和当前代码 commit；
5. 在隔离目录打开备份并执行读取/契约往返检查。

恢复流程：

1. 保留故障 DB、`-wal`、`-shm` 的只读副本；
2. 停止写入，验证待恢复文件的 SHA-256 和 `PRAGMA user_version`；
3. 恢复到新路径，不原地覆盖唯一副本；
4. 用 `SQLiteFeedbackStore(new_path)` 打开；
5. 按抽样 feedback ID 调用 `get_feedback`、`get_decision`、
   `get_lineage_by_feedback`；
6. 核对事件父链、payload SHA、source/resulting version、diff hash、report ID；
7. 重启进程后重复读取；确认通过后才切换 composition root；
8. 恢复演练结果、文件 SHA、执行人和 commit 写入发布证据。

Wave C 仅完成临时 SQLite 自动化恢复证据：阻断报告在重复写入、关闭重开后保持同一事件
ID、父链和 payload SHA；篡改 snapshot 会返回 `feedback.corrupt_snapshot`。未执行生产 DB
切换或业务级备份演练，不能把上述测试描述成部署演练。

## 8. 日常运行与故障处置

启动顺序：

1. 挂载持久目录并检查剩余空间/权限；
2. 打开 `SQLiteFeedbackStore`，让初始化检查 schema；
3. 注入真实 authorizer；
4. 构造 `DefaultFeedbackService`、`DefaultQualityGateRunner`、
   `DefaultValidationService` 和 metrics exporter；
5. 以已知只读 feedback ID 做读取探针；
6. 启用上层流量。

关闭顺序：停止新请求、等待短事务结束、导出 metrics、关闭 in-memory anchor（如使用），再停止
进程。文件型 store 每次操作使用短连接，不需要长期连接池。

故障分级：

- P0：缺关键输入仍通过、open P0/P1 被放行、审计链分叉/丢失、损坏快照被接受；立即停止发布/写入；
- P1：存储不可用、未来 schema、授权器异常、批量失败题进入 complete；保持 fail closed；
- P2/P3：非阻断指标或文档问题；不得借此放宽 gate。

排查优先级：稳定 code → DB/磁盘/锁 → schema version → 输入 identity → gate findings →
受控内部日志。不得通过删除失败记录或直接编辑 `payload_json` 恢复服务。

## 9. T07 联调状态与迁移建议

当前 T07 `app.batch.completion_gate.run_t03_quality_gates()` 仍调用旧入口
`app.workflow.quality_gates.run_all_quality_gates`，之后使用 `GateResult.from_legacy()` 转换。
这不是冻结 T03 v1 validator 的正式接线证明。

由 T07 owner 完成的后续迁移应：

1. 在 T07 owner 路径中构造真实 `ValidationContext`；
2. 调用 T03 公共 `DefaultQualityGateRunner` 或 `ValidationService`，不得复制规则；
3. 将空结果、异常、P0/P1、缺产物稳定映射为 `gates_pending`；
4. 保存完整 `ValidationReport`/`GateResult`，并绑定当前 question/version；
5. 证明任一批量失败题不能进入 `complete`；
6. 由双方对同一 commit、同一输入 SHA 签字。

T03 不在本 PR 直接编辑 `app/batch/**`。live batch 尚未运行；只有 T07 owner 的真实输出和
联合复验可以关闭这一限制。

## 10. 回滚

应用回滚和数据回滚必须分开：

- 优先把应用切回最后一个已知兼容 v1 的 commit；
- v1 SQLite 数据可由兼容版本继续读取，不删除新记录；
- 若 schema 已高于代码支持版本，旧代码必须拒绝打开，不能强改 `user_version`；
- 若 PR-C 只改变校准规则/测试/文档，回滚 PR-C commit 后仍要保留 PR-A/PR-B 的 v1 数据；
- 若发现错误写入，保全 DB 和 WAL 作为审计证据，从已验证备份恢复到新路径，再由队长决定切换；
- 回滚后重跑关键 validation、重启恢复和 lineage 单链测试。

本 PR 只新增测试、离线 harness 与文档，不迁移 schema 或生产数据。回滚是撤销 PR-C
证据提交并重跑 `tests/validation`；已合并 PR-A/PR-B 的 v1 数据与接口必须保留。
