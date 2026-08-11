# T08 Wave B Owner 接口缺口与确认请求

状态：`BLOCKED_ON_OWNER_CONFIRMATION`

日期：2026-08-11

目标分支：`codex/t08-b-delivery-core`

基线：`upstream/integration/2026-08-10@0371b67`

适用 owner：T01、T02、T03、T05、T06、队长

## 1. 请求目的

T08 已完成异步 Job、状态持久化、鉴权、限流、Artifact registry、统一导出和
API-only 前端的交付骨架，但生产默认 composition 仍对部分 owner 数据失败关闭。
本文件请求冻结 T08 可以消费的公开服务端口、身份字段、错误语义和恢复语义。

确认前，T08 不会：

- 修改 `app/evidence/**`、`app/workflow/**`、`app/feedback/**`、
  `app/validation/**`、`app/execution/**` 或 `app/multimodal/**`；
- 读取 owner 私有表、内部对象、`repr`、日志文本或临时文件名；
- 从文件存在、UI 状态或旧缓存推断 Gate、issue closure 或
  `actual_execution`；
- 将 fixture、Mock、planned 或 expected 数据包装成生产成功响应；
- 在接口语义未确认时维持第二套并行领域真源。

## 2. 当前事实与发布阻断

| Owner | 已存在公开契约 | 当前生产接线 | Wave B 阻断 |
|---|---|---|---|
| T01 | `EvidenceCardContract`、`ClaimEvidenceLink`、`EvidenceBundle` | 默认 adapter 仅能读取问题清单；evidence 固定 unavailable | 无法展示真实 evidence quote、locator、关系与 provenance |
| T02 | `ReviewFeedback`、`IssueClosure`、`PlanVersion`、`PlanVersionStore` | fixture 可读；没有确认的持久化 read/diff 端口 | versions/diff 生产返回 unavailable，停止原因和评分差异无权威来源 |
| T03 | `FeedbackRecord`、`FeedbackDecision`、`GateResult`、`ValidationReport`；`FeedbackService`、`FeedbackStore`、`ValidationService` | T08 feedback 路由固定返回 503；canonical report 未接 Gate source | 人工反馈不能进入闭环，不能读取权威 decision、resulting version 或 Gate |
| T05 | `ExecutionResult`、`ArtifactManifest` | 有 runner，但未发现按 run 读取已持久结果的公开端口 | 导出和 UI 无法读取权威执行结果；生产 canonical source 默认 unavailable |
| T06 | `MultimodalArtifact`、`MultimodalSummary` | process-local queue 有 snapshot，但未按 run/question 持久读取 | 无法稳定展示与恢复来源、bbox、轴、图例、单位和校验状态 |

当前 T08 明确失败关闭：

- `POST /api/v1/jobs/{job_id}/feedback`：503；
- `GET /api/v1/jobs/{job_id}/feedback/{feedback_id}`：503；
- 默认 evidence、versions、versions/diff owner adapter：unavailable；
- 默认 `CanonicalReportSource`：unavailable；
- 浏览器 feedback decision / resulting version 测试使用临时 HTTP 契约桩，
  不能作为 owner 集成证据。

## 3. 所有 owner 共同确认项

请队长协调所有 owner 对以下规则给出单一答案。

### X-01 身份绑定

所有读写端口最低必须绑定：

```text
question_id
run_id
version_id（版本、反馈、Gate 适用）
job_id（由 T08 持有，只作为外部交付关联）
actor_id（反馈、私有任务和下载适用）
correlation_id（所有跨模块调用）
```

需要确认：owner 是否接受 T08 通过 `upstream_run_id` 解析 `run_id`，以及响应中
如何证明 `question_id`、`run_id`、`version_id` 未串题或串版本。

### X-02 Schema 与兼容

每个端口需确认：

- 唯一 import path 和 Schema 版本；
- 新增字段、弃用字段和兼容窗口；
- 是否允许 T08 只做稳定 projection；
- 未提供的字段返回 `None`、空集合还是明确 unavailable；
- identity mismatch 必须失败，不能静默修正。

### X-03 错误语义

请统一以下 owner 错误类别，T08 再集中映射 HTTP：

```text
not_found
not_ready
unavailable
invalid_contract
identity_mismatch
permission_denied
conflict
retryable_upstream_failure
non_retryable_upstream_failure
```

需要确认每类错误是否可重试，以及是否允许向外展示安全的 `details`。

### X-04 持久化与重启

所有生产 read port 必须从 owner 的可恢复真源读取，不得依赖 T08 进程内对象。
请确认服务重启后资源是：

- 可恢复读取；或
- 明确返回不可恢复原因和稳定错误码。

### X-05 Composition ownership

建议由 T08 在 `app/api/**` 内实现薄 adapter 和 canonical report projection；
owner 保留领域判定与数据真源。请队长确认该边界，并指定跨 owner 冲突的最终裁决人。

## 4. T01 确认请求：Evidence

### 当前可复用

- `app.contracts.evidence.EvidenceBundle`；
- bundle 已保留 quote、locator、作者、年份、DOI/URL、content hash、关系、
  confidence、verification/validation status 和截断信息。

### T01-01 生产读取端口

请求冻结等价于以下语义的公开端口；名称可由 T01 决定：

```python
get_evidence_bundle(*, run_id: str, question_id: str) -> EvidenceBundle
```

需要确认：

- `run_id` 与 `question_id` 的一致性校验位置；
- bundle 未生成、生成中、为空和生成失败的区分；
- 是否允许合法空 bundle；若不允许，not-ready 与 no-evidence 如何区分；
- locator 的稳定键集合及 DOI/URL 可点击定位规则；
- `truncated=True` 时 `truncation_reason` 是否强制。

### T01-02 权限与敏感内容

请确认 evidence 是否存在用户隔离或受限全文；若存在，T01 返回什么权限信号，
以及 T08 可展示的 quote 最大长度。

### T01 验收

- 生产 composition 注入真实 T01 read port；
- 用 owner 提供的代表性 run 验证 quote、locator、关系、hash 和截断信息；
- 错误路径不读取旧 exports，不回退 fixture。

## 5. T02 确认请求：Versions、Reviewer 与 Diff

### 当前可复用

- `ReviewFeedback`、`IssueClosure`、`PlanVersion`；
- `PlanVersionStore` 提供进程内 `get/list_versions`，但 T08 需要确认生产持久真源；
- 当前 T08 的 `OwnerVersionDiff` 是外部适配占位，不应成为第二套领域真源。

### T02-01 版本读取端口

请求冻结：

```python
list_plan_versions(*, run_id: str, question_id: str) -> list[PlanVersion]
```

需要确认：排序、空列表语义、持久化位置、重启恢复和版本不可变性。

### T02-02 结构化 diff 端口

请求 T02 拥有并冻结结构化 diff DTO 与端口：

```python
get_version_diff(
    *,
    run_id: str,
    question_id: str,
    from_version_id: str,
    to_version_id: str,
) -> <T02-owned structured diff>
```

最低需覆盖：

- changes；
- issue_changes；
- score_delta；
- stop_reason；
- from/to identity；
- lineage。

需要确认：`IssueClosure` 当前没有 severity，T08 应展示明确 `N/A`，还是由 T02
新增 owner-owned severity 字段。T08 不会自行从 category 推断 P0/P1。

### T02-03 停止与完成资格

请确认读取未关闭 P0/P1、停止原因和 Reviewer pass 的唯一公共字段。T08 只消费
结论，不从两段文本或分数自行判定 closure/completion。

### T02 验收

- V1/V2+ 顺序、parent 与 lineage 可验证；
- diff 完全由 T02 返回；
- identity mismatch、未知版本和 not-ready 有不同错误；
- 服务重启后相同 run 返回一致版本快照。

## 6. T03 确认请求：Feedback、Decision 与 Validation Gate

### 当前可复用

- `FeedbackService.submit/decide/build_directive`；
- `FeedbackStore.get_feedback/get_decision/get_lineage_by_feedback`；
- `ValidationService.validate`；
- `FeedbackRecord`、`FeedbackDecision`、`ValidationReport`、`GateResult`。

### T03-01 外部反馈提交 orchestration

T08 不应创建 T03 决策或自行计算 fingerprint/policy。请求 T03 确认一个面向调用方
的公开提交入口，输入至少包括：

```text
run_id
question_id
target_version_id
feedback
actor_id
correlation_id
idempotency_key
source/channel
```

输出应是已持久化 `FeedbackRecord` 或 owner-owned receipt。需要确认：

- `feedback_id`、timestamp、request fingerprint 和 idempotency hash 的 owner；
- 相同 key 相同 payload 的复用语义；
- 相同 key 不同 payload 的 conflict；
- 超长、非法版本、无权限和跨 run/version 的错误。

### T03-02 Decision 查询

请求冻结读取端口：

```python
get_feedback_status(
    *,
    feedback_id: str,
    run_id: str,
    question_id: str,
    actor_id: str,
) -> <FeedbackRecord + FeedbackDecision | pending>
```

需要确认 decision pending、accepted、partially accepted、rejected，以及
`resulting_version_id` 尚未生成时的状态。

### T03-03 新版本触发边界

请 T02/T03 共同确认：

- 谁把 accepted directive 传入 T02 revision；
- 谁原子记录 decision、revision diff hash 和 resulting version；
- 重复回调如何避免重复版本；
- T08 收到反馈后是返回 202 receipt，还是创建独立 `feedback_revision` job。

推荐：长时间 revision 使用持久 Job，HTTP feedback 提交快速返回；T08 不在请求
线程运行 revision。

### T03-04 Gate 读取

T08 需要读取已经产生的权威 ValidationReport，而不是为展示重新运行规则。请求冻结：

```python
get_validation_report(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
) -> ValidationReport
```

如 owner 要求 T08 调用 `ValidationService.validate`，请明确授权、输入
`ValidationContext` 的唯一构造者以及幂等/成本语义。

### T03 验收

- submit → pending/decision → resulting version 全链路持久且幂等；
- accepted/partial/rejected 三类真实 owner decision 均有测试；
- Gate 的 P0/P1、passed、errors、warnings 和 score 不由 T08改写；
- 重启和重复回调不产生重复 decision/version。

## 7. T05 确认请求：Execution 与 Artifact Manifest

### 当前可复用

- `ExecutionResult` 对 `actual_execution` 有 runner-owned fail-closed 门禁；
- `ArtifactManifest` 保留相对路径、MIME、hash、大小和校验状态；
- `LocalProcessRunner.run` 是执行入口，不是按 run 查询历史结果的 read port。

### T05-01 执行结果读取端口

请求冻结：

```python
get_execution_result(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
) -> ExecutionResult
```

需要确认：一个版本多个 execution/round 时的 canonical 选择、latest 语义、
not-started/running/failed/timed-out/not-found 的区分，以及重启恢复。

### T05-02 受控 Artifact 访问

T08 对外不能暴露 `relative_path` 或服务器绝对路径。请确认 owner 提供：

- artifact ID 与 run/question/version identity；
- MIME、大小、SHA-256、生成与 validation status；
- 受控读取句柄或经过校验的 resolver；
- 文件缺失、checksum mismatch 和权限拒绝语义。

### T05-03 真实性

请确认 T08 只能直接消费 `ExecutionResult.actual_execution`，不得根据
`status=completed`、exit code 或 artifact 存在重新推断。

### T05 验收

- actual 与非 actual 各一个 owner 样例；
- stdout/stderr 截断、依赖/环境/seed/Git provenance 可展示；
- checksum 篡改时下载和导出失败关闭；
- 不泄露 workspace URI、本地路径或环境敏感信息。

## 8. T06 确认请求：Multimodal

### 当前可复用

- `MultimodalArtifact` 保留 provenance、page、bbox、units、axes、legend、data、
  confidence 和 validation status；
- `MultimodalSummary` 不保留 bbox、axes、legend 和完整 data，不足以单独满足
  T08 详情面板；
- `MultimodalQueue.snapshot()` 是进程内快照，未按 run/question/version 绑定。

### T06-01 持久读取端口

请求冻结：

```python
list_multimodal_artifacts(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
) -> list[MultimodalArtifact]
```

若不允许返回完整 data，请 T06 提供另一个保留 bbox、axes、legend、单位、原始值、
提取值、confidence、validation status 与人工核验标记的 owner-owned详情 DTO。

### T06-02 来源与预览

`provenance.source_path` 不能原样暴露。请确认：

- 对外 source ID/label；
- 缩略图或原始来源的受控 artifact ID；
- page 与 bbox 坐标系；
- 低置信度阈值是否由 T06 返回状态，而不是 T08 自定。

### T06 验收

- table/chart/timeseries 至少各一条 owner 数据；
- bbox、axes、legend、单位和 validation status 不丢失；
- `needs_review` 和 failed 明确可见；
- 重启后可按 identity 读取，不依赖进程内 queue。

## 9. Canonical report 组合确认

建议 T08 的 `CanonicalReportSource` 只做以下 projection：

```text
T01 EvidenceBundle
+ T02 PlanVersion / owner diff
+ T03 FeedbackRecord / Decision / ValidationReport
+ T05 ExecutionResult / ArtifactManifest
+ T06 MultimodalArtifact or approved detail DTO
-> T08 CanonicalReport
-> JSON / Markdown / PDF / frontend report
```

请队长确认：

- canonical report 的 identity 校验规则；
- 某 owner not-ready 时整体返回 503，还是返回标明原因的 partial；
- complete job 所需的 mandatory sections；
- stale 数据的版本标记和刷新策略；
- T08 是否可以缓存 projection，以及缓存键必须包含哪些 identity/version 字段。

推荐 fail-closed：mandatory owner 缺失时不得把 Job 标记 completed；报告可返回
partial 的前提是每个缺失 section 明确 unavailable，不得使用旧结果替补。

## 10. Owner 回复模板

每个 owner 请复制并填写：

```text
Owner / 任务：
确认项 ID：
结论：接受 / 修改后接受 / 拒绝
唯一公共 import path：
方法签名：
Schema / policy version：
identity 校验规则：
持久化与重启语义：
错误类型与 retryable：
权限规则：
代表性非 Mock 输入/输出：
owner reviewer：
补充限制：
```

队长最终回复还需明确：

```text
T08 adapter owner 路径是否批准：
跨 owner composition 规则：
冲突裁决人：
是否允许进入实现：是 / 否
```

## 11. 确认后的 T08 实施与门禁

只有收到上述确认后，T08 才会：

1. 在 `app/api/**` 实现集中 owner adapters，不修改 owner 内部模块；
2. 接通 evidence、versions/diff、feedback、Gate、execution 和 multimodal；
3. 用生产 composition 替换默认 unavailable source；
4. 增加真实 public-contract 集成测试，不把 fixture-only 测试当完成证据；
5. 运行完整浏览器闭环：run → evidence/version → feedback → decision/new version
   → Gate → execution/multimodal → PDF/MD/JSON；
6. 复验五并发、重启、幂等、权限、失败、超时和跨题隔离；
7. 生成与最终 commit 对应的 OpenAPI、截图、trace 和导出一致性证据；
8. P0/P1 清零后才把 Wave B 标记 Ready 并创建 PR。

## 12. 当前决策

在 owner 与队长回复“允许进入实现”前：

```text
Wave B status = blocked_on_owner_confirmation
PR #39 status = Draft / keep open / not Ready
production fallback = fail_closed
```

截至 2026-08-11，PR #39 的 captain review 为 `CHANGES_REQUESTED`，并明确
`KEEP_PR_OPEN=YES`、`READY_AUTHORIZED=NO`、`MERGE_AUTHORIZED=NO`。该审查不构成
T01/T02/T03/T05/T06 owner 接口确认；在本文件第 10 节回复齐套且队长明确允许实现
前，T08 不接生产 adapter，不移除默认 unavailable/fail-closed 行为。

实现提交 `57e8fa2a851acdda87ed469dd3fb7b3ffb36f60c` 已修复 captain 指出的 Windows
导出 P1，并在 GitHub Actions `windows-latest` run `31466958039` 上通过 lint、type、
unit、integration、security、build 六项检查。该工程证据不改变 owner confirmation
状态，也不构成 `READY_AUTHORIZED=YES`。
