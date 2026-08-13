# T08 Wave B Owner 接口缺口与确认请求

状态：`BLOCKED_ON_OWNER_CONFIRMATION`

日期：2026-08-11

目标分支：`codex/t08-b-delivery-core`

实现分支基线：`upstream/integration/2026-08-10@0371b67`

当前 integration 事实基线：`upstream/integration/2026-08-10@2d36df2`

适用 owner：T01、T02、T03、T05、T06、队长

当前回复状态：T01、T05 已在 PR #39 直接 `CONDITIONAL_AGREE`；T06 已直接
`ACCEPT` 并在 Draft PR #36 Head `116bb3a9` 实现冻结 read port；T02、T03 已从
owner 历史 PR 与最新 `integration/2026-08-10@2d36df2` 补齐现有冻结事实。T06
实现尚未合并，其他 production read/orchestration 端口仍不完整；队长最终
composition/实施授权仍待回复。

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

### 2.1 PR #39 Owner 回复跟踪

| Owner | PR 回复 | 结论 | T08 当前动作 | 尚需确认/交付 |
|---|---|---|---|---|
| T01 | [issuecomment-5250445405](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/39#issuecomment-5250445405) | `CONDITIONAL_AGREE` | `get_evidence_bundle` 边界已按 `run_id + question_id` 收紧；production 继续 unavailable | 队长批准 T01 小 PR、权威持久化位置及 owner read port 落地 |
| T02 | [PR #10](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/10)、[PR #21](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/21)、[Open PR #37](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/37)、integration | merged contract/audit found；checkpoint candidate 未合并；production read gap | T08 proposed fixture/read boundary 已绑定 run+question；不把 in-process store/checkpoint/AgentTrace 当 production history | 按 question 绑定的持久 version/diff read port 仍缺失 |
| T03 | [PR #14](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/14)、[Draft PR #32](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/32)、integration | Wave A merged；Wave B candidate 未合并 | feedback submit/status 继续 503；Gate 不自行计算 | production store/orchestration/read port 未进 integration；共享契约冲突待 T03/队长处理 |
| T05 | [issuecomment-5250843063](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/39#issuecomment-5250843063) | `CONDITIONAL_AGREE` | 仅保留 typed projection；production execution/report 继续 unavailable | 队长批准 T05 history store、re-attestation read port 与受控 resolver |
| T06 | [PR #39 confirmation](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/39#issuecomment-5252856232)、[Draft PR #36](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/36) | `ACCEPT`；read port 已在 `116bb3a9` 实现但未合并 | 等 integration 获得 `app.multimodal.read_port` 后在 `app/api/**` 接薄 adapter；当前继续 unavailable | PR #36 合并/可消费后，执行 production identity/source/redaction E2E |
| 队长 | re-review 要求 Draft/Open | `READY_AUTHORIZED=NO` | 保持 Draft/Open/fail-closed | 批准 owner 小 PR、T08 adapter 边界、composition 规则、冲突裁决人与进入实现 |

T01/T05 的条件同意与 T02/T03 的历史合并事实都不表示对应 production read port
已存在；T06 虽已接受并实现，未合入 integration 前同样不能解除 Wave B owner E2E
阻断。

### 2.2 历史 PR 与 integration 追溯结论

本节使用的 integration 真源是远端最新
`integration/2026-08-10@2d36df2fb391be68b8d24cd30f73e7ed5495044a`。此前本地
tracking ref 停在 `0371b67`；更新后发现新增提交仅为 T08 PR #40，T02/T03/T06
owner 路径相对 `0371b67` 无变化。

#### T02

- PR #10 已合并并冻结 `app.contracts.revision`：`ReviewFeedback`、
  `IssueClosure`、`PlanVersion`、`PlanVersionStore`；队长在最终 Head `bc1c17b` 上
  `APPROVE`。
- PR #21 已合并并提供 `app.workflow.explainable_revision`：
  `ExplainableRevisionAudit`、`StructuredRevisionDiff`、score changes、lineage 与
  `stop_reason`；队长在最终 Head `7d5e7ec` 上 `APPROVE`。
- Open PR #37 在 Head `7ba73ce` 上新增候选
  `RevisionRecoveryCheckpoint` / `RevisionRecoveryCoordinator`。checkpoint 对
  controller、versions、events 和 issue closures 做自校验与 hash，并支持
  `serialize()/deserialize()`，但 coordinator 仍由调用方提供 payload 恢复，没有
  owner-owned 存储后端、持久资源寻址或读取服务。
- PR #37 的 recovery identity 仍只有 `run_id`；checkpoint 与
  `RevisionRecoveryCoordinator.create()` 都没有 `question_id`。因此它只能作为恢复
  schema/算法候选，不能满足 T08 的 `run_id + question_id` production history port。
- 当前 `PlanVersionStore` 明确是 **in-process** store。它支持
  `serialize()/deserialize()`，但没有 owner-owned 持久介质、重启寻址或按
  `run_id + question_id` 的读取端口；`PlanVersion` 本身也没有 `question_id`。
- `StructuredRevisionDiff` 只有 `changes + substantive_sections`；完整 score、issue、
  lineage、stop reason 位于 `ExplainableRevisionAudit`。当前没有冻结的服务端口把这些
  对象按 identity 返回给 T08。因此 T08 不能扫描 AgentTrace 或自行拼接两种对象。
- `IssueClosure` 没有 severity。integration 已明确 severity 属 T03
  `RevisionIssueSnapshot`，`critical_issue` 不自动等于 P0。

结论：T02 DTO/规则已收集完整；T08 所需 production version/diff history port 仍不存在，
对应 adapter 继续 unavailable。

#### T03

- PR #14 已合并并冻结 `app.contracts.validation` schema v1，以及
  `app.feedback.storage.FeedbackStore`、`app.feedback.service.FeedbackService`、
  `app.validation.service.ValidationService` 等 Protocol；队长在 Head `1be9530` 上
  `APPROVE`。
- `T03_INTERFACE_FREEZE.md` 明确这些只是 Protocol：Wave A **不提供生产持久化**，
  API 路由、幂等锁、权限、完整 validator、错误码和 E2E 均为延后项。
- integration 已冻结 T08 映射规则：`job_id` 不能当 `run_id`；
  `target_version_id` 必须为完整 `<run_id>:vN`；receipt disposition 来自
  `FeedbackDecision`；`resulting_version_id` 必须是直接下一版。
- Draft PR #32 提供 SQLite store、默认 service、原子 lineage 和重启/幂等候选实现，
  但它尚未合并，且 captain review 明确 `production_api_connected=false`、live API
  E2E 缺失；不能作为当前 integration production port。
- PR #32 的候选服务已经定义 `FeedbackSubmission` 与
  `DefaultFeedbackService.submit_request()`，候选 SQLite store 也提供
  `get_feedback(feedback_id)`、`get_decision(feedback_id)` 和 lineage 读取。这些可以
  作为 owner 后续冻结 orchestration 的实现依据，但当前未进入 integration，且读取
  仍主要按 feedback/lineage ID，未形成包含 run/question/actor 权限校验的 T08 状态端口。
- PR #32 的 `DefaultValidationService.validate(context)` 只即时计算
  `ValidationReport`；该分支没有持久化 report store 或按
  `run_id + question_id + version_id` 读取既有 Gate 结论的端口。
- 当前 integration 的 `FeedbackDecision` 模型存在冻结契约冲突：validator 在
  `resulting_version_id` 非空时访问 `self.revision_diff_sha256`，但该字段未声明在
  `FeedbackDecision`。T08 不得绕过、复制或修补共享 schema；需要 T03 owner 与队长
  指定唯一修复版本。
- PR #32 对该冲突的候选补丁是删除
  “`resulting_version_id` 必须伴随 `revision_diff_sha256`”的四行 validator 校验，
  而不是在 `FeedbackDecision` 增加字段。该选择会改变 lineage 完整性语义，只能由
  T03 owner/公共 Schema editor 与队长确认，不能由 T08 将其视为已批准修复。

结论：T03 DTO、T08 mapping 和 Protocol 已收集完整；production submit/status/Gate
read 仍未落地且存在共享契约阻断，feedback 路由继续 503。

#### T06

- PR #16 已合并并冻结 `app.contracts.multimodal`：完整
  `MultimodalArtifact`、瘦身 `MultimodalSummary` 与 `to_consumer_summary`；队长在
  Head `2a1d980` 上 `APPROVE`。
- PR #29 已合并真实来源 provenance/gold package，但其 PR 明确不是完整 Wave B
  adapter Done。
- integration 的 `MultimodalQueue` 明确是内存队列；`snapshot()` 没有
  run/question/version identity，也没有重启恢复。
- PR #36 Head `d45ef6b` 的 `app/multimodal/**` 模块树中仍只有 `queue.py` 命中
  queue/store/read/resolver 类存储命名，没有新增持久 store 或受控 resolver。
  `workflow_hook.build_revision_hook_payload(artifacts)` 只接收 artifact 列表，不携带
  `run_id`、`question_id` 或 `version_id` identity envelope。
- `MultimodalSummary` 保留 `source_path`，但缺 bbox、axes、legend 和完整 data；因此
  既不能原样对外暴露路径，也不足以满足 T08 详情面板。完整 Artifact 虽有这些字段，
  当前没有 owner-owned 持久 detail read port 或受控 source/preview resolver。
- Draft PR #36 是未合并候选，并且 captain review 将真实 PDF/chart、Qwen B016 与
  完整 Evidence E2E 标为 PARTIAL/WAIT；不能作为 integration production read port。
- T06 owner 于 PR #39 评论
  [`issuecomment-5252856232`](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/39#issuecomment-5252856232)
  正式 `ACCEPT`，并在 PR #36 Head
  `116bb3a9f11f921774a2e21538c933bd7cd88120` 新增
  `app.multimodal.read_port.list_multimodal_artifacts(*, run_id, question_id,
  version_id) -> list[MultimodalArtifact]`、持久 JSON store、脱敏 public source 与
  `preview_artifact_id`。owner 声明 bbox、units、confidence、validation status 和
  `needs_human_review` 均由 T06 保留/判定。

结论：T06 接口语义与 owner 实现已确认，但 PR #36 仍为 Draft/Open 且未进入
integration。当前 T08 checkout 无法导入该模块，因此 production adapter 继续
unavailable；PR #36 合并后即可在 T08 owner 路径接线，不再需要重新讨论签名。

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

### 已收到的 owner 结论

T01 已在 PR #39 条件同意目标接口：

```python
get_evidence_bundle(*, run_id: str, question_id: str) -> EvidenceBundle
```

T08 已将 `app/api/upstream.py` 的 Protocol、默认 unavailable adapter、fixture adapter
和 v1 evidence route 对齐到这组 identity；同一 `run_id` 绑定其他 `question_id` 时失败
关闭为 `UPSTREAM_IDENTITY_MISMATCH`。该变更不读取 `evidence_cards.json`，也不代表
T01 store 已落地。

当前可直接消费的 frozen contract/projection 是：

- `app.contracts.evidence.EvidenceBundle`；
- `app.evidence.serialization.serialize_evidence_bundle`；
- `app.evidence.citation_renderer.build_t08_citation_payload`。

仍需队长确认 T01 后续小 PR 及权威持久化位置；在此之前，本节“生产读取端口”验收
保持未完成，production evidence 继续 unavailable/fail-closed。

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

## 5. T02 已收集事实与接口缺口：Versions、Reviewer 与 Diff

### 已从 owner PR / integration 确认

- 唯一 DTO import path：`app.contracts.revision`；schema version 为 1。
- `PlanVersionStore.list_versions(run_id)` 返回按版本号连续排序的 defensive copies；
  `PlanVersion.version_id` 必须为 `<run_id>:vN`，parent 必须指向上一版。
- `ReviewFeedback.is_effective_pass` 的 owner 规则为：`passed=True` 且
  `critical_issues=[]` 且 `required_revisions=[]`。
- `app.workflow.explainable_revision.StructuredRevisionDiff` 是 canonical
  `changes + substantive_sections`；`ExplainableRevisionAudit` 另含 issue closures、
  score changes、lineage、remaining blockers、stop reason 与 accepted。
- severity 不属于 T02 `IssueClosure`；应从 T03 `RevisionIssueSnapshot` 消费。没有
  T03 severity projection 时，T08 显示 `N/A`，不得从 category 推断 P0/P1。

这些规则已由合并的 PR #10/#21 和 integration 固定；仍缺的是服务端持久 read
boundary，而不是 DTO 名称。

T08 工作区已把 proposed `list_plan_versions` / `get_version_diff` 边界收紧到
`run_id + question_id`，并为 fixture adapter 增加跨题 409 测试。该改动只证明消费
边界已准备，不代表 T02 接受方法名或 production port 已存在。

### 当前可复用

- `ReviewFeedback`、`IssueClosure`、`PlanVersion`；
- `PlanVersionStore` 提供进程内 `get/list_versions`，但 T08 需要确认生产持久真源；
- 当前 T08 的 `OwnerVersionDiff` 是外部适配占位，不应成为第二套领域真源。

### T02-01 版本读取端口

目标 production 端口仍需由 T02 落地并冻结：

```python
list_plan_versions(*, run_id: str, question_id: str) -> list[PlanVersion]
```

已确认排序和版本不可变性；仍需落地持久化位置、重启恢复、空列表/not-ready
区分，以及 `question_id` 与只有 `run_id` 的现有 DTO/store 如何建立权威绑定。

### T02-02 结构化 diff 端口

现有两个 owner DTO 不应由 T08 自行拼接；仍需 T02 冻结一个面向 T08 的聚合 read
端口：

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

severity 规则已由 integration 明确：它属于 T03 sidecar，不应向 T02
`IssueClosure` 增加第二套字段。T03 数据不可用时显示明确 `N/A`。

### T02-03 停止与完成资格

Reviewer pass 与 stop reason 的 owner 字段已定位，但未关闭 P0/P1 属 T03 severity
sidecar。T08 只消费聚合结论，不从两段文本或分数自行判定 closure/completion。

### T02 验收

- V1/V2+ 顺序、parent 与 lineage 可验证；
- diff 完全由 T02 返回；
- identity mismatch、未知版本和 not-ready 有不同错误；
- 服务重启后相同 run 返回一致版本快照。

## 6. T03 已收集事实与接口缺口：Feedback、Decision 与 Validation Gate

### 已从 owner PR / integration 确认

- 唯一 DTO import path：`app.contracts.validation`，冻结 `schema_version=1`。
- 已冻结 Protocol：`app.feedback.storage.FeedbackStore`、
  `app.feedback.service.FeedbackService`、`app.validation.service.ValidationService`、
  `app.quality.service.QualityGate/QualityGateRunner`。
- `FeedbackRecord` 已绑定 run/question/target version/actor/correlation/fingerprint/
  idempotency hash；`FeedbackDecision` 拥有 accepted/partial/rejected 与
  `resulting_version_id`；`ValidationReport`/`GateResult` 拥有 fail-closed 结论。
- PR #14 与接口冻结文档明确：integration 中这些只是 Protocol，不是生产
  persistence/orchestration；T08 不得把 Protocol 存在误写成反馈闭环已接通。
- Draft PR #32 是 durable SQLite/service 候选，但未合并且没有 live T08 API E2E。
- integration 当前 `FeedbackDecision` validator 引用了未声明的
  `revision_diff_sha256`。这是共享契约冲突，T08 不得本地兼容两套真相。

### 当前可复用

- `FeedbackService.submit/decide/build_directive`；
- `FeedbackStore.get_feedback/get_decision/get_lineage_by_feedback`；
- `ValidationService.validate`；
- `FeedbackRecord`、`FeedbackDecision`、`ValidationReport`、`GateResult`。

### T03-01 外部反馈提交 orchestration

T08 不应创建 T03 决策或自行计算 fingerprint/policy。当前 integration 的
`FeedbackService.submit(record)` 要求调用方先构造完整 owner DTO，不是安全的外部
orchestration。Draft PR #32 已提供以下候选入口，但它未合并，不能作为当前生产端口：

```python
submit_request(request: FeedbackSubmission) -> FeedbackRecord
```

仍需 T03 在最终 integration 上落地并冻结面向调用方的公开提交入口，输入至少包括：

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

历史 PR #21/#32 已证明 T02 lineage handoff → T03 原子 SQLite 消费的候选技术配对，
但 T03 PR #32 未合并，当前 integration 不具备该路径。仍需 T02/T03 在最终合并 tip
共同确认：

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

### 已收到的 owner 结论

T05 已条件同意 T08 只消费 owner-authoritative typed result，并建议把原单数三参数
读取改为显式列表与显式 execution identity：

```python
list_execution_results(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
) -> tuple[ExecutionResult, ...]

get_execution_result(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
    execution_id: str,
) -> ExecutionResult
```

现有 `ExecutionResult` 不含 `run_id/version_id`，因此未来 owner store 必须以外层
identity index 绑定 `run_id + question_id + version_id + execution_id`。没有 owner
明确持久化的 `canonical_execution_id` 时，T08 不得自行选择“最好/成功/actual/latest”
结果。序列化 JSON 不携带 attestation，T08 也不得从 raw JSON 恢复
`actual_execution=true`。

当前 T05 尚无 production history read port、re-attestation 或受控 artifact resolver。
在队长批准 T05 小 PR 且这些端口落地前，本节验收保持未完成，execution/canonical
report 继续 unavailable/fail-closed。

### 当前可复用

- `ExecutionResult` 对 `actual_execution` 有 runner-owned fail-closed 门禁；
- `ArtifactManifest` 保留相对路径、MIME、hash、大小和校验状态；
- `LocalProcessRunner.run` 是执行入口，不是按 run 查询历史结果的 read port。

### T05-01 执行结果读取端口

原请求的单数读取方向经 T05 owner 修改为上面的列表 + 显式 execution 读取。若最终
仍保留单数三参数端口，则必须由 owner store 额外返回明确的
`canonical_execution_id`：

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

## 8. T06 已收集事实与接口缺口：Multimodal

### 已从 owner PR / integration 确认

- 唯一 DTO import path：`app.contracts.multimodal`；PR #16 冻结
  `MultimodalArtifact`、`MultimodalSummary`、`to_consumer_summary` 与严格枚举。
- `MultimodalArtifact` 是唯一保留 bbox、axes、legend、data、units、confidence 和
  validation status 的完整 DTO。
- `MultimodalSummary` 是 prompt 用瘦身摘要：保留 `source_path`、page、units、
  confidence、validation status 和行列数，但丢失 bbox/axes/legend/data。
- integration 的 `MultimodalQueue` 明确是 process-local 内存队列；没有 identity
  envelope、持久 store 或重启恢复。
- PR #29 只合并 provenance/gold package；Draft PR #36 的 adapter/Evidence bridge
  尚未合并，且 captain 将真实 chart/Qwen/full Evidence E2E 标为 PARTIAL/WAIT。
- PR #36 Head `116bb3a9` 已新增 `app.multimodal.read_port`、持久 store 和
  `tests/multimodal/test_read_port.py`；T06 owner 已在 PR #39 明确接受下述端口。

### 当前可复用

- `MultimodalArtifact` 保留 provenance、page、bbox、units、axes、legend、data、
  confidence 和 validation status；
- `MultimodalSummary` 不保留 bbox、axes、legend 和完整 data，不足以单独满足
  T08 详情面板；
- `MultimodalQueue.snapshot()` 是进程内快照，未按 run/question/version 绑定。

### T06-01 持久读取端口

T06 已冻结并在未合并 PR #36 实现：

```python
list_multimodal_artifacts(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
) -> list[MultimodalArtifact]
```

Schema/policy 为 `t06.multimodal_store.v1` / `t06.multimodal_detail.v1`。合法无产物
返回空列表；invalid contract、identity mismatch 与 unavailable 均由 owner 标记为
不可重试。完整 data 可返回，另有 `list_multimodal_details` 详情投影。

### T06-02 来源与预览

T06 已确认：

- 对外仅使用 `public_source.source_id`、`source_label` 和
  `preview_artifact_id`；
- 绝对路径在 owner read 时脱敏；
- coordinate space 为 `pdf_user_space`、`image_pixel`、`csv_placeholder` 或
  `unknown`；
- T06 以 `needs_human_review` 返回低置信状态，当前 owner 阈值为 0.70，T08 不自定。

### T06 验收

- table/chart/timeseries 至少各一条 owner 数据；
- bbox、axes、legend、单位和 validation status 不丢失；
- `needs_review` 和 failed 明确可见；
- 重启后可按 identity 读取，不依赖进程内 queue。
- PR #36 合并后，在 integration tip 运行 owner read-port 测试与 T08 production
  adapter E2E；合并前保持 unavailable。

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

### 10.1 已追溯后仍待 owner/队长处理的最小任务清单

- T02 owner：在现有 in-process `PlanVersionStore` 之外提供按
  `run_id + question_id` 持久读取的 version history，并冻结聚合
  `StructuredRevisionDiff + ExplainableRevisionAudit` 的 read DTO/端口；明确
  not-found/not-ready/identity-mismatch 与重启语义。Open PR #37 的 self-hashed
  checkpoint 可作为恢复 schema 候选，但必须增加 owner-owned storage/read boundary
  和 question identity 后才满足该任务。
- T03 owner + 队长：先解决 integration `FeedbackDecision` 对未声明
  `revision_diff_sha256` 的共享契约冲突，再决定 Draft PR #32 的 SQLite/service
  候选如何进入 integration，并提供 identity/权限绑定的 submit/status 及持久
  `ValidationReport` read orchestration；明确采用“删除 hash 校验”还是“补齐字段及
  lineage 语义”。
- T02 + T03：在最终合并 tip 重新验证历史 #21/#32 技术配对，确认重复回调不重复
  生成版本，以及长 revision 是由谁创建/恢复持久 job。
- T06 owner：提供按 `run_id + question_id + version_id` 的持久详情读取、受控 source/
  preview artifact、page/bbox 坐标系与安全 source ID。该项已在 PR #36
  `116bb3a9` 获 owner `ACCEPT` 并实现；剩余动作是合并到 integration、T08 薄 adapter
  接线及 production E2E，不能直接从未合并分支复制实现。
- 队长：确认 T01/T05 owner 小 PR 是否批准、T08 是否只在 `app/api/**` 实现薄 adapter、
  mandatory/partial/complete/stale/cache composition 规则、冲突裁决人，以及
  `是否允许进入实现=是/否`。

上述任一项未回复时，对应 production adapter 保持 unavailable；不得用 fixture、旧
export、process-local queue、workspace 扫描或 HTTP stub 填补。

### 10.2 可直接发送的最小确认文本

```text
T02：请确认并落地 run_id + question_id 绑定的持久 version history 与聚合 diff
read port；PR #37 checkpoint 只能作为恢复 schema，不能代替 store/read service。

T03/Schema editor：请裁决 FeedbackDecision.revision_diff_sha256 冲突，并在最终
integration 提供 identity/actor 绑定的 submit/status 与持久 ValidationReport read。

T06：请提供 run_id + question_id + version_id 绑定的持久 MultimodalArtifact/detail
read，以及不暴露 source_path 的 source/preview resolver。

T02+T03：请共同确认 accepted feedback → revision → diff hash → resulting version
的原子 owner、重复回调幂等和长任务恢复边界。

队长：请确认 T01/T05 owner 小 PR、T08 app/api 薄 adapter、mandatory/partial
composition、冲突裁决人，以及是否允许开始 production 接线。
```

T01/T05 的批准不是形式性签字。T01 批准后由 evidence owner 对持久 bundle 的
provenance、run/question identity 和缺失语义负责；T05 批准后由 execution owner
重新核验 persisted result 的 attestation，并以受控 resolver 交付 artifact。没有这两项，
T08 只能看到普通 JSON 或文件路径，无法合法证明 evidence 权威性或
`actual_execution=true`。

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
8. 全链路绿、behind=0 且 P0/P1 清零后，才请求队长授权把现有 PR 转 Ready。

## 12. 当前决策

在 owner 与队长回复“允许进入实现”前：

```text
Wave B status = blocked_on_owner_confirmation
PR #39 status = Draft / keep open / not Ready
production fallback = fail_closed
```

截至 2026-08-11，PR #39 的 captain re-review 仍要求保持 Draft/Open，并明确
`KEEP_PR_OPEN=YES`、`READY_AUTHORIZED=NO`、`MERGE_AUTHORIZED=NO`。历史 PR 与
integration 已足以确认现有 DTO/Protocol 和缺失能力，但不构成对尚不存在的
production read/orchestration 端口或 T08 composition 的实施授权。在第 10.1 节缺口
关闭且队长明确允许实现前，T08 不接 production adapter，不移除默认
unavailable/fail-closed 行为。

实现提交 `57e8fa2a851acdda87ed469dd3fb7b3ffb36f60c` 已修复 captain 指出的 Windows
导出 P1；captain 已审交付 tip `04b733081d6c1b7bbebf2b83db1b103bb2fe3a73`
在 GitHub Actions `windows-latest` run `31467308686` 上通过 lint、type、unit、
integration、security、build 六项检查。该工程证据不改变 owner confirmation 状态，
也不构成 `READY_AUTHORIZED=YES`。

```text
REVIEWED_HEAD=04b733081d6c1b7bbebf2b83db1b103bb2fe3a73
ENGINEERING_COMPLIANCE=FAIL
CONTENT_COMPLIANCE=FAIL
P0=0
P1_OPEN=0
P1_CLOSED=windows_export_filenotfound
MERGE_AUTHORIZED=NO
KEEP_PR_OPEN=YES
READY_AUTHORIZED=NO
```

当前唯一安全的下一实施条件是：T01/T05 缺失 owner ports、T02/T03 第 10.1 节缺口、
T03 共享契约冲突关闭，T06 PR #36 实现进入 integration，且队长明确确认 adapter
边界与 composition 规则。此前不生成 production 成功 trace，不把 fixture、HTTP
stub、planned 或 expected 结果作为 B016/B017 证据。
