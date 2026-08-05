# T03 Wave B 实现与交接手册

文档状态：Draft PR 已发布（T03 实现、本地全仓 CI 等价检查已完成；远端 CI 正在运行，跨队配对签字仍待补）

更新日期：2026-08-03

适用契约：`app.contracts.validation`，`schema_version=1`

| 交付元数据 | 当前值 |
| --- | --- |
| T03 Wave B 分支 | `t03/b-validation-core` |
| integration base SHA | `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c` |
| Wave A 契约修复提交 | `82a3d254dffd4ce89a94d082fc28af172786d712` |
| Wave B 核心实现提交 | `a10dbb8ceb821a6a8f5e37b0bf18c58b09c2726f` |
| T03 Wave B PR 开立 HEAD | `337bb412a58c45054a1bff10fb3a24192177c8b6`；后续文档提交见 PR 最新 HEAD |
| T03 Wave B Draft PR | [#32](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/32)，`isDraft=true`，`mergeable=MERGEABLE` |
| T03 本地验证测试 | `tests/validation`：`100 passed in 4.07s` |
| 本地 CI 等价检查 | unit `730 passed, 37 skipped`；integration `1 passed`；lint/type/build 通过；security PASS |
| GitHub CI | PR #32 已触发 lint/type/unit/integration/security/build；最终结论见 PR Checks |
| 发布 Fork | `ybq-music/SAGE125-AI-Scientist-T03`：`isFork=true`，parent 为团队仓库 |
| 原个人仓库 | `ybq-music/SAGE125-AI-Scientist`：仍为独立备份仓库，未改名、未删除 |
| 团队仓库权限 | `sage125-ai-scientist-team/SAGE125-AI-Scientist`：`viewerPermission=READ` |
| T02 配对审查 | PR #21，HEAD `a19e790ed634fd162405434e618cdb9f9c1c08de`，`CHANGES_REQUESTED`；本地候选组合测试 `139 passed, 3 skipped`，生产接线验收未完成 |
| T08 配对审查 | 当前无 Wave B PR；反馈 POST/GET 仍为 503，占位状态不代表已经接线 |

> 本文描述 T03 自有边界、计划中的接线方式和可验收条件。凡是标为 TBD 的内容，
> 在获得真实测试输出、SHA 或配对签字前，不得改写为“已完成”。

原发布阻断已经解决：原个人仓库不是团队仓库的 GitHub fork，且团队仓库只授予 READ 权限。
因此新建了不同名称的真实 fork `ybq-music/SAGE125-AI-Scientist-T03`，保留原仓库不变，并从
该 fork 向团队 `integration/2026-08-10` 创建 Draft PR #32。发布链路已恢复；是否转 Ready
仍取决于远端 CI 与 T02/T08 配对证据。

本地复核命令与结果：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\validation -q
# 100 passed in 4.07s
```

另按 `.github/workflows/ci.yml` 的 UTF-8 环境完成本地等价检查：unit `730 passed, 37 skipped`，
integration `1 passed`，lint/type/compile/build manifest 均通过，安全审计 PASS
（`critical=0, warnings=2`）。这些结果仍不证明 T02/T08 生产接线、跨队 E2E 或 GitHub CI 已完成。

## 1. Wave B 要解决什么

Wave B 的目标不是“把反馈存下来”这么简单，而是打通一条可证明的闭环：

```text
人工提交反馈
  -> 权限与输入检查
  -> 幂等持久化并开始审计链
  -> 接受 / 部分接受 / 拒绝决策
  -> 只把获准指令送入下一轮 Prompt
  -> T02 生成连续的新 PlanVersion 和结构化 diff
  -> 用完整五类产物执行 Validator / Quality Gates
  -> 未关闭 P0/P1 必须阻断
  -> 按 question_id + version_id 记录指标并闭合审计链
```

核心验收语义如下：

1. 同一个请求重放不会产生两条反馈或两条 lineage；同一幂等键换了内容必须冲突。
2. `accepted`、`partially_accepted`、`rejected` 都有明确理由和审计身份。
3. 下一轮输入必须保留 `feedback_id`、目标版本和被接受的具体指令；拒绝内容不能偷渡进 Prompt。
4. Validator 同时检查 ResearchPlan、EvidenceCards、AgentTrace、execution metadata 和 QuestionItem。
5. 缺产物、伪造引用、错误的 `actual_execution`、跨问题/跨 run/未来版本数据都要安全失败。
6. 任一未关闭 P0/P1 finding 或 issue 存在时，`validation_status` 不得为 `passed`。
7. 能从 `feedback_id` 查询到反馈、决策、版本、diff、验证报告和 issue closure 的审计链。

## 2. 边界与不越权原则

T03 只负责下列 owner 路径：

- `app/feedback/**`
- `app/validation/**`
- `app/quality/**`
- `app/contracts/validation.py`
- `tests/validation/**`
- `docs/modules/T03/**`

T03 不直接修改：

- T02 的 `app/contracts/revision.py`、PlanVersion 状态机和生产 Prompt Builder；
- T08 的 `app/api/**` 路由、JobStore 和 API response model；
- 公共 `app/workflow/pipeline.py`。

因此本分支提供稳定领域接口、存储适配器、Prompt/Revision 适配边界、Validator、质量门和
指标；真正写入 T02/T08 owner 路径的接线改动必须由对应队员完成并配对审查。没有配对
提交与测试证据，不能把“接口已经提供”写成“生产链路已经接通”。

## 3. 架构与数据流

### 3.1 分层

| 层 | T03 稳定对象/端口 | 职责 |
| --- | --- | --- |
| 冻结领域契约 | `FeedbackRecord`、`FeedbackDecision`、`HumanFeedbackDirective`、`ValidationContext`、`GateResult`、`ValidationReport`、`AuditLineage` | 严格字段、不可变快照、跨对象身份和阻断规则 |
| Feedback 应用端口 | `FeedbackService`、`FeedbackSubmission`、`DefaultFeedbackService` | 提交、决策、生成安全 directive；默认无 authorizer 时拒绝所有写操作 |
| Feedback 持久化端口 | `FeedbackStore` | create-only 保存、幂等读取、原子 decision + lineage |
| SQLite 适配器 | `SQLiteFeedbackStore` | WAL、短事务、并发去重、JSON round-trip 重校验 |
| Revision/Prompt 边界 | `RevisionFeedbackContextBuilder`、`RevisionPromptAdapter`（别名 `FeedbackPromptAdapter`） | 将记录/决策变成 sidecar，把获准指令注入 T02 实际调用 payload，不扩展 T02 `extra="forbid"` 模型 |
| 质量门端口 | `QualityGate`、`QualityGateRunner` | 每个门返回冻结 `GateResult`；稳定顺序执行 |
| 默认门聚合器 | `build_default_quality_gates()`、`DefaultQualityGateRunner` | 构造固定门序列；门异常转成阻断 finding，继续收集其余门结果 |
| Validator | `DefaultValidationService` | 完整上下文校验、fail-closed 聚合、生成 hash-bound report |
| 指标 | `ValidationMetricsCollector`、`ValidationMetricsSnapshot` | 按问题和版本聚合 gate 通过率、错误类型、revision closure rate；不保留原始反馈 |
| Validation 审计 | `ValidationAuditWriter` | 以确定性 event ID 追加每个 gate 和最终 report，重试不分叉审计链 |
| 旧数据迁移 | `migrate_legacy_feedback_payload()`、`import_legacy_feedback()` | 单条旧反馈转成 `legacy_unverified`，不推断 accepted/pass |

以上符号已经通过各包 `__all__` 暴露；最终交付仍须用合并 SHA 与测试证明其行为。

### 3.2 Feedback 稳定接口

冻结的 `FeedbackService` 端口：

```python
submit(record: FeedbackRecord) -> FeedbackRecord
decide(feedback_id: str, decision: FeedbackDecision) -> FeedbackDecision
build_directive(feedback_id: str) -> HumanFeedbackDirective | None
```

具体实现的推荐入口：

```python
store = SQLiteFeedbackStore(path)
service = DefaultFeedbackService(store, authorizer=deployment_authorizer)
record = service.submit_request(FeedbackSubmission(...))
```

冻结 Protocol 的 `submit()` 参数保持 `FeedbackRecord`；具体 `DefaultFeedbackService.submit()`
还接受 `FeedbackSubmission` 或同形 mapping，`submit_request()` 是推荐给 T08 的明确入口。

`DefaultFeedbackService` 没有显式 `authorizer` 时使用
`DenyAllFeedbackAuthorizer`，所有 submit/decide 都被拒绝。`AllowAllFeedbackAuthorizer`
只适用于可信本地任务和测试，不是生产默认值。默认反馈上限是 10,000 个 Python 字符，
原始幂等键上限 256 个字符；部署可收紧反馈上限。

调用约束：

- `target_version_id` 必须是完整的 `<run_id>:vN`，不能把 UI 标签 `"v1"` 当领域 ID。
- API 提供的幂等键只保存 SHA-256，不保存原文。
- `request_fingerprint` 绑定语义请求；相同语义重放返回原记录，冲突请求显式失败。
- 原始提交、决策和 lineage 都是 create-only；不得覆盖已有快照。
- 决策与 `feedback_decided` 事件必须在一个 SQLite 事务中提交。
- `DefaultFeedbackService.decide()` 要求 decision 暂不携带 `resulting_version_id`；新版本和
  diff 在真正生成后通过 AuditLineage 事件绑定，避免“决策已接受”被误写成“版本已生成”。
- `rejected` 返回 `None` directive，且不能产生 `resulting_version_id`。
- `partially_accepted` directive 只能包含 `accepted_items`，不能包含 rejected items、原始反馈或拒绝理由。
- 默认安全分类器发现明确的 prompt-injection 模式时，先保存原始审计记录，再原子写入一个
  自动 `rejected` 决策；该文本不能进入 revision prompt。
- 即使原始反馈通过初筛，decision 的 `accepted_items` 在写入前仍会再次检查长度、控制字符
  和 prompt-injection 模式；不安全的获准项不会形成 decision 或 directive。

`SQLiteFeedbackStore` 另外提供 `save_submission(record, lineage)`，用于在同一事务中保存
首次反馈与起始 lineage。该方法是具体适配器能力，不是对冻结 `FeedbackStore` Protocol
的破坏性扩展。

### 3.3 Revision / Prompt 稳定接口

服务层用 `HumanFeedbackDirective` 表示 accepted-only 的最小指令对象：

```json
{
  "schema_version": 1,
  "feedback_id": "feedback-001",
  "target_version_id": "run-demo:v1",
  "disposition": "partially_accepted",
  "instructions": ["收紧证伪阈值"],
  "original_feedback_sha256": "<64 位小写 SHA-256>"
}
```

`RevisionFeedbackContextBuilder.build(record, decision)` 先把分别持久化的记录和决策交叉
核对，生成冻结的 `RevisionFeedbackContext`。该 sidecar 同时保留 accepted/rejected
decision 事实供状态机与审计使用；真正进入 Prompt 的内容由 `RevisionPromptAdapter` 再次
裁剪。

公开入口：

```python
feedback_context = RevisionFeedbackContextBuilder.build(record, decision)
payload = RevisionPromptAdapter.inject(base_payload, feedback_context)

# 或直接复用 T02 的三个 builder，再注入反馈
payload = RevisionPromptAdapter.build_hypothesis_input(...)
payload = RevisionPromptAdapter.build_experiment_input(...)
payload = RevisionPromptAdapter.build_reviewer_input(...)

execution_metadata = RevisionPromptAdapter.build_execution_metadata(
    execution_metadata,
    feedback_context,
    prompt_payload=payload,
    diff_hash=diff_hash,
)
```

`inject()` 对 accepted/partially accepted 新增的 wire shape 是：

```json
{
  "human_feedback": {
    "schema_version": 1,
    "feedback_id": "feedback-001",
    "source_version_id": "run-demo:v1",
    "disposition": "partially_accepted",
    "applied_instructions": ["收紧证伪阈值"],
    "original_feedback_sha256": "<64 位小写 SHA-256>"
  }
}
```

注意：上面的 Prompt receipt 与冻结 `HumanFeedbackDirective` 是相邻但不同的 wire shape；
前者使用 `source_version_id`/`applied_instructions` 供 T02/T03 联调，后者使用
`target_version_id`/`instructions` 作为 service 的 accepted-only 最小对象。调用方不得混用键名。

这些入口必须满足以下不变条件：

1. 接受一个由 T02 构造并校验过的 `RevisionContext`，不向该对象添加字段。
2. 调用 T02 `RevisionPromptBuilder` 得到基础 payload 后，返回一个新的 payload，并在顶层添加
   `human_feedback`；不得原地修改调用方对象。
3. feedback context 的 `source_version_id`/`original_version_id` 必须等于被修订的当前 PlanVersion。
4. 下一版必须是直接子版本，例如 `run-demo:v1 -> run-demo:v2`。
5. 实际 Agent 调用 payload 的指纹和新版本 diff hash 要进入 lineage；仅在日志中出现
   `feedback_id` 不算接线成功。
6. rejected 决策可形成审计 sidecar，但 `should_resume=false`，`inject()` 返回不含
   `human_feedback` 的 payload；T02 必须据此停止 revision，不能把“payload 未注入”误当作继续执行许可。

### 3.4 Validator / Quality Gate 稳定接口

Validator 输入必须是完整 `ValidationContext`：

- `research_plan`
- `evidence_cards`
- `agent_trace`
- `execution_metadata`
- `question_item`
- 可选 `revision_issues`、`human_feedback`、`correlation_id`

推荐调用组合：

```python
runner = DefaultQualityGateRunner(build_default_quality_gates())
validator = DefaultValidationService(runner, metrics=metrics)
report = validator.validate(context)
```

`build_default_quality_gates()` 当前按以下固定顺序构造默认门；调用方不得自行重排后仍声称
使用了默认审计序列：

| 顺序 | gate ID | 默认级别 | 重点检查/代表性 finding code |
| --- | --- | --- | --- |
| 1 | `artifact-presence` | P1 | 五类产物非空；`MISSING_*`、`EMPTY_EVIDENCE_CARD`、`EMPTY_AGENT_TRACE_EVENT` |
| 2 | `evidence_grounding` | P0 | 旧门兼容；`EVIDENCE_GROUNDING_ERROR/WARNING` |
| 3 | `results_integrity` | P0 | 旧门兼容；`RESULTS_INTEGRITY_ERROR/WARNING` |
| 4 | `research_plan_schema` | P1 | 旧门兼容；`RESEARCH_PLAN_SCHEMA_ERROR/WARNING` |
| 5 | `model_compliance` | P1 | 旧门兼容；`MODEL_COMPLIANCE_ERROR/WARNING` |
| 6 | `reference_integrity` | P0 | 伪造/未知引用；`REFERENCE_INTEGRITY_ERROR/WARNING` |
| 7 | `execution-truth` | P0 | boolean/mismatch/proof chain；`EXECUTION_TRUTH_*`、`EXECUTION_PROOF_*` |
| 8 | `agent-trace` | P1（不可信真实执行可升 P0） | 必填字段、ID/step 唯一、状态、prompt hash、错误；`AGENT_TRACE_*` |
| 9 | `human-feedback-propagation` | P1 | directive、previous version、revision metadata、prompt fingerprint、diff hash 和 applied instructions 一致 |

精确 finding code 仍以交付 SHA 对应的 `app/quality/gates.py` 和测试为准。已冻结的聚合语义如下：

- 没有任何 gate 运行：P0 `NO_QUALITY_GATES`，报告阻断。
- runner 自身异常、重复 gate ID 或返回非法对象：P0 `VALIDATION_RUNNER_ERROR`，报告阻断。
- 单个 gate 异常：`GATE_EXECUTION_ERROR`，至少按 P1 阻断；异常详情不回显到不可信输出。
- 任一 gate 或 revision issue 有 open P0/P1：`blocked`。
- 只有所有 gate 均通过且没有 open P0/P1，报告才可为 `passed`。
- 通过但尚未真实执行时最多建议 `ready_for_validation`；只有可信
  `actual_execution=true` 的完整上下文才可建议 `validated`。

`ValidationAuditWriter(store).record(feedback_id, report, actor_id=...)` 把每个
`GateResult` 和最终 `ValidationReport` 的确定性 hash 写成 audit event。event ID 由
lineage/report/gate 身份派生，进程在中途失败后可安全重试；writer 还会拒绝跨 run、错误
version 或用另一份 report 覆盖既有 validation 的请求。

### 3.5 Metrics 稳定接口

`ValidationMetricsCollector.record(context, report)` 在验证 report 与 context 的
`validation_id`、`version_id` 和完整上下文 hash 一致后才计数。同一 `report_id` 重放只计
一次。`snapshot()` 返回按 `(question_id, version_id)` 稳定排序的只读快照，包含：

- validations / passed / blocked；
- evaluated gates / passed gates / gate pass rate；
- findings by code / severity；
- tracked / resolved revision issues / revision closure rate。

指标快照不保存原始反馈文本。指标的持久化、跨进程汇总和外部监控导出属于后续接线，
当前状态：TBD。

## 4. T02 配对接线说明

当前事实：T02 PR #21 的 HEAD 为 `a19e790ed634fd162405434e618cdb9f9c1c08de`，review
decision 为 `CHANGES_REQUESTED`。将该候选 HEAD 与 T03 分支临时合并时无代码冲突，选定的
T02/T03 组合套件为 `139 passed, 3 skipped`；3 项均因缺少可选 `questions_125.json` 数据而跳过。
这只证明候选分支在现有离线测试下兼容，不代表 requested changes 已关闭，也不能据此宣称
T03 已经接入生产 Prompt 或版本状态机。后续 review 结论与双方确认仍待补。

T02 owner 需要完成：

1. 从当前 `PlanVersion.version_id` 确定 canonical target，不接受来源不明的短标签。
2. 根据 `feedback_id` 读取已持久化 record/decision，并用
   `RevisionFeedbackContextBuilder.build()` 做交叉核对；`should_resume=false` 代表拒绝，停止 revision。
3. 用 T02 自有 `RevisionContext` 和 `RevisionPromptBuilder` 构造基础输入，再经
   `RevisionPromptAdapter.build_*_input()` 或 `inject()` 注入独立的 `human_feedback`。
4. 在实际 HypothesisGenerator / ExperimentDesigner / Reviewer 调用边界断言
   `feedback_id` 与 accepted instructions 均存在。
5. 产生连续 `PlanVersion`，保证 parent 指向目标版本；并生成可确定性 hash 的结构化 diff，
   再用 `RevisionPromptAdapter.build_execution_metadata()` 保存 prompt receipt 和 diff hash。
6. 把 revision requested/generated、diff hash、new version ID 和 issue closure 回传给 T03
   lineage；重试不得产生第二个直接子版本。
7. 增加正向、部分接受、拒绝、陈旧目标版本、并发重试和 Prompt payload 集成测试。

配对通过的最低证据：PR #21 精确 SHA、T03 adapter 精确 SHA、实际 Agent payload 断言、
连续版本断言、lineage 回查结果和双方签字；记录在
`T03_WAVE_B_T02_T08_PAIRED_REVIEW_TEMPLATE.md` 的副本中。

## 5. T08 配对接线说明

当前事实：T08 目前没有 Wave B PR；`POST /api/v1/jobs/{job_id}/feedback` 与
`GET /api/v1/jobs/{job_id}/feedback/{feedback_id}` 仍是明确的 503
`UPSTREAM_CONTRACT_UNAVAILABLE` 占位实现。这个 503 是“尚未接线”的证据，不是 T03
服务失败，也不能记为完成。

T08 owner 需要完成：

1. 从 JobStore 查询 `job_id`，再读取可信 `upstream_run_id`；`job_id` 绝不能直接当 `run_id`。
2. 将 `target_version_id` 解析成该 run 下存在的完整 `<run_id>:vN`；不能只做字符串拼接。
3. 从已认证主体生成 `FeedbackSource.actor_id/channel`，并在调用 T03 前执行资源级权限检查。
4. 将原始 `Idempotency-Key` 只放入进程内 `FeedbackSubmission.idempotency_key`；由
   `DefaultFeedbackService` 计算 SHA-256 后写入 `FeedbackRecord`。T08 自己不得持久化或记录
   原始 header，也不要预先 hash 后再让 service 二次 hash。
5. 保留或生成 `correlation_id`，并将 T03 `feedback_id` 返回给调用方。
6. POST 重放同一请求返回同一反馈；同键不同内容返回 409；并发重放也只能产生一个记录。
7. GET 返回真实 decision/receipt；`unavailable` 只是 API projection，不能伪造为 T03
   `FeedbackDecision.disposition`。
8. 移除 503 占位前必须补齐 API contract、鉴权、状态映射、错误映射和重启后查询测试。

建议的领域错误到 HTTP 映射如下。机器错误码来自 T03；HTTP 状态由 T08 最终确认：

| T03 错误码 | 含义 | 建议 HTTP | 是否建议重试 |
| --- | --- | --- | --- |
| `feedback.invalid_input` | 空值、格式、版本关联或长度无效 | 422 | 否 |
| `feedback.unsafe_input` | 预留给显式拒收型不安全输入策略；当前默认 injection 分类采用“持久化后自动 rejected” | 422 | 否，需人工改写 |
| `feedback.permission_denied` | 主体无权修改该 run/version | 403 | 否 |
| `feedback.not_found` | feedback 不存在 | 404 | 否 |
| `feedback.lineage_not_found` | lineage 不存在或尚未正确创建 | 404 或 500 | 由 T08/T03 配对决定 |
| `feedback.conflict` | 反馈、决策、版本或 lineage 状态冲突 | 409 | 读取最新状态后决定 |
| `feedback.idempotency_conflict` | 同一幂等键被不同语义请求复用 | 409 | 否，换键前先核对请求 |
| `feedback.fingerprint_conflict` | 指纹相同但语义快照不同 | 409 | 否，需审计 |
| `feedback.storage_failure` | SQLite 不可用、锁超时或事务失败 | 503 | 是，必须保持同一幂等键 |
| `feedback.corrupt_snapshot` | 已保存 JSON 无法通过 v1 契约重校验 | 500 | 否，隔离并人工恢复 |
| `feedback.unsupported_schema` | 数据库 schema 比本实现更新，拒绝降级写入 | 503 | 否，需使用兼容版本或受控迁移 |

错误响应不得回显 SQL、文件路径、异常堆栈、原始幂等键或被拒绝的恶意文本。

## 6. SQLite schema、迁移和回滚

### 6.1 当前 v1 schema

`SQLiteFeedbackStore.initialize()` 以 additive、可重复执行的 DDL 创建：

| 表 | 主键/唯一约束 | 关键内容 |
| --- | --- | --- |
| `feedback_records` | PK `feedback_id`；UNIQUE `request_fingerprint`；UNIQUE nullable `idempotency_key_hash` | run/question/target version 索引列 + 完整 `FeedbackRecord` JSON |
| `feedback_idempotency_keys` | PK `key_hash`；FK -> feedback | 同一语义请求可绑定后续重试键；键一旦绑定后不能改指向，避免 alias 重放投毒 |
| `feedback_decisions` | PK `decision_id`；UNIQUE `feedback_id`；FK -> feedback | 完整 `FeedbackDecision` JSON |
| `feedback_lineages` | PK `lineage_id`；UNIQUE `feedback_id`；FK -> feedback | 最新 `AuditLineage` 聚合快照；快照内部 events 只能追加，存储行只能经校验后的 append 更新 |

辅助索引：

- `idx_feedback_run_question(run_id, question_id)`
- `idx_feedback_target_version(target_version_id)`

写事务使用 `BEGIN IMMEDIATE`，外键开启，文件库使用 WAL，`busy_timeout` 由
`timeout_seconds` 配置。每次读取都把 `payload_json` 重新通过冻结 v1 Pydantic 契约校验；
列只用于寻址和唯一性，JSON 是完整领域快照。

数据库使用 SQLite `PRAGMA user_version=1` 作为最小 schema 门禁：`0` 可按 additive DDL
初始化为 v1，`>1` 会以 `feedback.unsupported_schema` fail closed，绝不在较新库上降级写入。
当前没有独立 migration ledger 表，也没有把每个 lineage event 拆成独立行；正式长期运行前
是否增加迁移历史表、备份策略与 event 表，状态为 TBD。

### 6.2 部署迁移顺序

1. **盘点**：记录 DB 绝对路径、文件 owner、备份位置、现有表和行数；TBD 填入变更单。
2. **备份**：停止 T03 写入或使用 SQLite 在线备份；计算备份 hash 并执行一次只读恢复演练。
3. **加表**：部署仅创建 T03 新表/索引的代码；此阶段 T08 继续 503，不切流量。
4. **契约验证**：对新库执行 create/reopen/round-trip、外键、幂等、并发和损坏快照测试。
5. **旧数据处理**：旧 `reviewer_feedback: list[str]` 不能自动解释为 accepted。对已经整理成
   单条 JSON object、且能可靠映射 run/question/version 的记录，可先调用
   `migrate_legacy_feedback_payload(payload)` 预览冻结 record/lineage，再调用
   `import_legacy_feedback(payload, store)` 导入为 `legacy_unverified`；当 store 是
   `SQLiteFeedbackStore` 时会使用原子 `save_submission`。其他 Protocol 实现的 fallback
   是分步保存，必须由该适配器另行证明失败恢复安全。函数会忽略旧
   `accepted`/`passed` 布尔值，不创建 decision 或 pass 状态。批量清单、失败隔离和操作审批
   runner 仍为 TBD。
6. **T02/T08 接线**：先 shadow/read-only 验证身份映射，再小流量启用 POST/GET 和 revision；
   保持同一 idempotency key 贯穿重试。
7. **放量与观察**：核对冲突率、存储失败、阻断 finding、revision closure rate 与 lineage
   缺口；真实证据填入交接记录。

### 6.3 回滚

回滚优先回滚“调用接线”，默认保留 T03 表和审计数据：

1. 停止新反馈写入，记录最后成功的 correlation/feedback ID。
2. 将 T08 feedback 路由恢复为明确 unavailable 或关闭 feature flag；停止 T02 消费 directive。
3. 等待在途事务结束并执行一致性检查，再备份 DB/WAL/SHM。
4. 回滚应用代码，保留新表只读，避免丢失已经形成的审计链。
5. 验证旧主流程仍可运行，并记录未完成 feedback 的人工处置。

只有在数据保留策略允许、完整导出已校验且负责人明确批准后，才能反向删除 T03 表；删除
顺序必须先子表、后父表。本文不提供自动删库命令，防止把“代码回滚”误做成“审计数据
销毁”。恢复时使用备份副本演练，不能直接覆盖唯一生产库。

## 7. 威胁模型与安全控制

| 威胁 | 主要控制 | 仍需关注 |
| --- | --- | --- |
| Prompt injection / 指令越权 | 默认模式分类后自动 rejected；正常反馈经决策，只将 `accepted_items` 放进 Prompt receipt；拒绝内容不进 Prompt | 模式匹配不是完备检测；人工/策略误接受恶意指令仍有风险；accepted item 仍应作为不可信数据被模板定界 |
| 空白、超长或资源耗尽输入 | API 与 service 双层长度/格式检查；SQLite 超时；异常安全失败 | 最终最大 UTF-8 字节数、逐 actor 限流：TBD |
| 伪造 actor/channel | T08 鉴权并做资源级授权；T03 只消费可信 actor identity | `actor_id` 字段本身不是认证证明，不能单独作为授权依据 |
| 重放与幂等键投毒 | 哈希后的 idempotency key + request fingerprint + unique constraint + 事务 | 客户端重试必须复用原键；同键异义必须告警 |
| 并发双写/双版本 | SQLite `BEGIN IMMEDIATE`、唯一约束、create-only 语义 | 多主机/网络文件系统不适合作为该 SQLite 方案的扩展路径 |
| IDOR / 跨 run、问题或版本污染 | canonical version、上下文身份交叉验证、T08 job -> upstream run 映射 | 短版本标签不能凭猜测展开；陈旧版本策略需 T02 明确 |
| 伪造证据或执行状态 | evidence/reference legacy gate、question identity、trace、`actual_execution` proof gate；异常 fail closed | finding code 与覆盖范围仍须以交付 SHA 和测试证据复核 |
| 绕过 P0/P1 阻断 | `GateResult` 和 `ValidationReport` 契约双重拒绝 false pass | API/前端不得自行根据 score 改写 report 状态 |
| 数据库内容被篡改/损坏 | 每次读做 v1 round-trip 校验；hash 绑定 feedback/decision/diff/context | 当前不是带密钥签名；有 DB 写权限者仍可能同时重写 JSON 与 hash |
| 隐私和敏感信息泄漏 | metrics 不存原始反馈；错误不回显异常细节；幂等键不明文落库 | 原始 FeedbackRecord 仍持久化全文，保留期限、加密和删除策略：TBD |

## 8. 已知限制

1. T02 PR #21 HEAD `20a5b356364051c86dac3698fc836c790b6c2c79` 的实际 Agent
   Prompt、revision metadata 和 lineage handoff 已与 T03 实现提交
   `e4248e8ad215b0b77279990eb2bf6553b60b52d1` 完成技术组合复验；仍需 T02 owner
   使用 PR #32 新远端 HEAD 复跑并签字，队长仍需处理既有 review decision。
2. T08 feedback POST/GET 仍返回 503；生产 API 尚未接通。
3. T03 不修改 pipeline，因此完整上下文如何从生产产物收集，仍需 T02/T08 或公共 owner 接线。
4. SQLite 适合单节点最小持久化；不提供跨主机分布式锁或高可用复制。
5. 当前只有 `PRAGMA user_version` 门禁，没有逐次 migration ledger；已有单条
   `legacy_unverified` 转换/导入函数，
   但批量 backfill runner、失败隔离清单和生产恢复演练均为 TBD。
6. metrics 当前是进程内聚合；跨进程持久化、采集窗口和监控告警为 TBD。
7. 授权、限流、密钥管理、数据保留由 API/部署层提供，领域记录中的 actor ID 不能替代鉴权。
8. 默认质量门集合已有实现，但攻击测试数量、真实案例结果、CI 状态、提交 SHA 和 PR 状态
   均须在主任务完成后用真实证据填写。
9. 已建立真实发布 fork 并创建 Draft PR #32；原独立仓库保留不变。PR 在远端 CI 与
   T02/T08 配对证据完成前保持 Draft。

## 9. 最小 E2E 操作步骤

以下是接线完成后的最小验收剧本，不是当前完成声明。每一步都要保存 correlation ID、对象
ID、版本 ID、hash 和测试输出；真实值目前均为 TBD。

1. 建立临时 SQLite 库，创建一个可查询的 `run-e2e:v1` 和具有修改权限的测试 actor。
2. 用固定 `Idempotency-Key` 向 T08 POST 一条可部分接受的反馈，目标必须解析为
   `run-e2e:v1`；记录返回的 `feedback_id`。
3. 查询 DB/service，确认只有一条 FeedbackRecord 和一条起始 lineage，且 correlation ID 一致。
4. 形成 `partially_accepted` decision：至少一个 accepted item 和一个 rejected item；检查
   decision 与 audit event 原子写入。
5. 用 `RevisionFeedbackContextBuilder.build()` 和 `RevisionPromptAdapter.build_*_input()`，
   确认实际下一轮 Agent payload 包含 `feedback_id` 和
   accepted instructions，不含 rejected item 与原始全文。
6. 让 T02 生成 `run-e2e:v2`，检查 parent=`run-e2e:v1`，并把结构化 diff hash 写入 lineage。
7. 用 `RevisionPromptAdapter.build_execution_metadata()` 写入 prompt fingerprint/diff receipt；
   汇集 V2 的 ResearchPlan、EvidenceCards、AgentTrace、execution metadata 和 QuestionItem，
   构造完整 `ValidationContext` 并运行 `build_default_quality_gates()` + validator。
8. 查询 ValidationReport：若无阻断项，应全部 gate 通过；若人为加入 open P1，则报告必须
   `blocked`，不得建议 `ready_for_validation` 或 `validated`。
9. 查询 metrics，确认只在对应 `(question_id, run-e2e:v2)` bucket 中增加一次，且不含原始反馈。
10. 在验证前追加已经核验的 issue closure，再调用 `ValidationAuditWriter.record()`；由
    `feedback_id` 回查完整 lineage：submitted -> decided -> revision requested/generated ->
    issue closure（若有）-> gate evaluation -> validation completion，相邻
    parent 和 payload hash 均一致。
11. 重放步骤 2 的同一请求，确认返回同一 `feedback_id` 且行数/指标不重复；再用同键换内容，
    确认 409 conflict 且没有污染版本或审计链。
12. 重启进程后再次查询 feedback/decision/lineage，确认 SQLite 快照可恢复。记录所有真实命令、
    测试名、输出与 SHA：TBD。

本仓库内已有两份可机器校验、且明确标注非生产 API 的离线证据：

- `examples/wave_b_offline_e2e_summary.json`
- `examples/wave_b_e2e_metrics.json`
- `examples/t02_t03_revision_lineage_pairing_evidence.json`（T02/T03 精确 SHA 技术配对；
  不含 T08 live API）

### 9.1 2026-08-06 T02 revision lineage 持久化接线整改

T03 新增 `RevisionLineageConsumer` 与
`DefaultFeedbackService.consume_revision_lineage_handoff()`，以纯 JSON 边界校验 T02 的
`revision_lineage_handoff` 和完整 `revision_metadata`，不导入 T02 私有实现类，也不修改
T02 workflow。消费器执行以下步骤：

1. 核对 persisted feedback/decision、source version、直接子版本、prompt/diff hash 与
   accepted-only instructions；rejected、篡改、断链或身份冲突全部 fail closed。
2. 把 T02 首个 `revision_requested.parent_event_id=None` 绑定到 SQLite 中真实的
   `feedback_decided.event_id`，保留其余 T02 event ID、subject、payload hash 和父链。
3. 由 `SQLiteFeedbackStore.append_lineage_events_atomically()` 在单个
   `BEGIN IMMEDIATE` 事务内完成整批 requested -> generated -> issue_closed 写入，最后只
   更新一次 lineage snapshot；完整重放为 no-op，冲突不会留下半条事件链。
4. 将完整 revision metadata 放入冻结事件的 `metadata` sidecar；SQLite 关闭并重开后
   `feedback_id`、source/resulting version、prompt fingerprint、diff hash、instructions、
   issues 和事件父链全部恢复。
5. 之后复用 `ValidationAuditWriter.record()` 继续追加 9 个 `gate_evaluated` 和一个
   `validation_completed`；重复完成回写不产生第二条事件。

真实 T02 组合案例恢复出的 diff hash 为
`4f0f9fda9eef9b57a467fd243101aa4fce43af1789561f5ba92f7902d0070397`，父链为：

```text
feedback_decided
-> event:55f7ecda13127579 (revision_requested)
-> event:73f66880eefc20da (revision_generated)
-> event:a2c31e666da5b460 (issue_closed)
-> event:d9d644bc57841591 (issue_closed)
-> gate_evaluated x 9
-> validation_completed
```

验证结果：指定配对文件 `5 passed`；T03 validation `105 passed`；T02
`20a5b356…` + T03 `e4248e8…` 临时普通合并无冲突，validation、T02 handoff 与实际
模型消费合计 `109 passed`；全仓 unit `735 passed, 37 skipped`。这些结果关闭本次
T03-owned SQLite consumer 技术缺口，但不替代 T02 签字、T08 live API E2E 或队长 Ready
授权。

## 10. 验收矩阵（T03-B-001..021）

本地 `tests/validation` 已有 `105 passed in 4.34s` 的套件级证据。T02 lineage consumer
相关项已回填精确测试与 SHA；T08 配对和生产 API E2E 仍未完成。

| ID | 验收项 | 最低证据 | 状态 |
| --- | --- | --- | --- |
| T03-B-001 | SQLite v1 可创建、关闭、重开，并按 v1 wire shape 往返 Feedback/Decision/Lineage | 指定测试名、临时 DB 路径策略与输出 | TBD |
| T03-B-002 | 同一 feedback ID / fingerprint / 幂等键的同义重放返回原记录，不新增行 | 重放测试和三表行数断言 | TBD |
| T03-B-003 | 同一幂等键用于不同语义请求时返回稳定 conflict，旧快照不变 | `feedback.idempotency_conflict` 测试 | TBD |
| T03-B-004 | fingerprint 冲突、feedback/decision ID 冲突和目标版本冲突均 fail closed | 对应错误码与不可覆盖断言 | TBD |
| T03-B-005 | 空白、超长、非法版本/ID 输入安全失败，不泄漏内部异常 | 输入边界测试；最大长度配置记录 | TBD |
| T03-B-006 | 未授权 actor 不能提交或决定反馈 | 权限策略单元/接口测试 | TBD |
| T03-B-007 | 并发重复提交只产生一个 FeedbackRecord 与一个起始 lineage | 多线程/多连接测试和行数断言 | TBD |
| T03-B-008 | accepted 决策有理由、accepted items 和审计 hash，并可生成 directive | service + lineage 测试 | TBD |
| T03-B-009 | partially accepted 只把 accepted items 送入 directive，拒绝片段不进入 Prompt | Prompt payload 精确断言 | TBD |
| T03-B-010 | rejected 决策不生成 directive、revision 或 resulting version | 负向状态机与 lineage 测试 | TBD |
| T03-B-011 | directive 保留 feedback ID、目标版本和原文 SHA，且能证明下一轮实际输入发生变化 | T02 `test_t02_t03_revision_handoff.py` + 精确 SHA 实际模型消费 | PASS（T03/T02 technical；待双边签字） |
| T03-B-012 | resulting version 是目标版本直接子版本；diff hash 与 revision_generated 事件一致 | `test_t02_t03_final_pairing_recheck.py` + evidence JSON | PASS |
| T03-B-013 | 审计链可在重启后由 feedback ID 回查，事件单链、时序、subject 与 hash 一致 | 原子批量、重启、篡改、重复与 16 线程并发测试 | PASS |
| T03-B-014 | ValidationContext 同时接收五类完整产物并绑定 run/question/version | 完整上下文正向测试 | TBD |
| T03-B-015 | 缺 EvidenceCards/AgentTrace 等关键产物时输出结构化阻断，不静默跳过 | presence gate 负向测试 | TBD |
| T03-B-016 | 计划中的伪造/未知 evidence reference 被阻断 | reference gate 负向测试 | TBD |
| T03-B-017 | 非布尔、缺失、与 metadata 不一致的 `actual_execution` 均不能通过 | contract/gate 负向测试 | TBD |
| T03-B-018 | 跨问题、跨 run、未来版本和不匹配 question text 均被拒绝 | identity/contamination 测试 | TBD |
| T03-B-019 | open P0/P1、无 gates、重复 gate ID、gate/runner 异常均不能 false pass | Validator fail-closed 测试 | TBD |
| T03-B-020 | 至少 10 个无效输入、恶意反馈、缺失产物和并发失败案例；指标按 question/version 幂等聚合 | 攻击测试清单 + metrics 测试输出 | TBD |
| T03-B-021 | 最小 E2E 闭环通过，T02/T08 配对审查签字，T08 不再返回占位 503，迁移/回滚证据齐全 | E2E 输出、PR/SHA/CI、配对记录、恢复演练 | PARTIAL：T02 technical PASS；T02 签字与 T08 live API 尚缺 |

## 11. 最终交接时必须回填

- PR #32 的最终远端 HEAD、GitHub Checks 结论及是否由 Draft 转为 Ready；
- 已记录 `tests/validation = 105 passed` 与本地全仓 CI 等价检查；仍需回填新 HEAD 的远端 GitHub Checks，
  并保留 unit 的 `37 skipped` 说明；
- lint/type/security/build 的本地结果已记录，远端结果仍待 PR CI；
- 默认 gate 列表与稳定 finding code 的交付 SHA 复核结果；
- `DefaultFeedbackService`、`RevisionFeedbackContextBuilder`、`RevisionPromptAdapter` 等公开
  符号的最终签名复核结果；
- T02 PR #21 完整 SHA `20a5b356364051c86dac3698fc836c790b6c2c79` 已用于技术组合；
  仍需回填 T02 owner 复跑/签字、`CHANGES_REQUESTED` 后续处理及双方最终审查结论；
- T08 Wave B PR/SHA（当前无），以及 503 替换后的 API E2E；
- SQLite 备份/恢复演练记录、迁移负责人、实际 DB 配置；
- 每一项 T03-B-001..021 的证据链接与状态。
