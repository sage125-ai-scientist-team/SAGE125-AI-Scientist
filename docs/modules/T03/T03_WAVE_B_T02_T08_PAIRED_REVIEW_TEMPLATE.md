# T03 Wave B × T02/T08 配对审查记录模板

用途：记录 T03 Feedback/Revision/Validator 与 T02 版本修订、T08 API 的真实接线证据。

> 此文件是模板，不是验收证明。当前 T02 PR #21 HEAD 前缀为 `a19e790…`，review
> decision 为 `CHANGES_REQUESTED`；T08 没有 Wave B PR，feedback POST/GET 仍返回
> 503 `UPSTREAM_CONTRACT_UNAVAILABLE`。在完整 SHA、跨队测试和签字全部填完前，
> 结论只能是“待对接/待复审”，不能写成“已完成”。

## 1. 审查元数据

| 项目 | 填写内容 |
| --- | --- |
| 审查日期/时区 | 2026-08-03 / Asia/Shanghai；最终签字时间 TBD |
| T03 负责人 | `ybq-music` |
| T02 负责人 | `Mk007115`（PR #21 作者） |
| T08 负责人 | TBD |
| 独立复审人 | TBD |
| T03 PR / HEAD SHA | 核心实现 `a10dbb8ceb821a6a8f5e37b0bf18c58b09c2726f`；Draft PR/最终 HEAD TBD |
| T02 PR #21 / 被审 SHA | `a19e790ed634fd162405434e618cdb9f9c1c08de`；`CHANGES_REQUESTED` |
| T08 PR / 被审 SHA | 当前无 Wave B PR；被审 SHA/PR URL TBD；feedback 接口仍为 503 |
| 个人仓库 | `ybq-music/SAGE125-AI-Scientist`，`isFork=false` |
| 团队仓库权限 | `sage125-ai-scientist-team/SAGE125-AI-Scientist`，`viewerPermission=READ` |
| T03 本地 validation 测试 | `100 passed in 4.07s` |
| integration base SHA | `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c` |
| T02/T03 merge-base | `898cc08fd434caf926bd3b765870057399f1c788` |
| 测试环境/DB 类型 | Windows / Python 3.12 / SQLite 临时数据库 |
| correlation ID / E2E run ID | TBD |

## 2. 当前基线事实（审查开始前确认）

- [x] 已确认 T02 PR #21 当前 HEAD 为 `a19e790ed634fd162405434e618cdb9f9c1c08de`、
  review decision 为 `CHANGES_REQUESTED`。
- [x] 已确认 T08 当前没有 Wave B PR，feedback POST/GET 仍为 503 占位。
- [x] 已确认个人仓库 `isFork=false`、团队仓库权限为 READ；Draft PR 当前无法按私有 Fork
  流程创建。
- [x] 已确认 T03 使用 `schema_version=1`，且没有增删冻结字段/枚举；仅修复了一个引用不存在字段的验证器。
- [ ] 已确认三方分支均基于同一 integration 祖先，记录 merge-base：TBD。
- [ ] 已确认工作区无与本次配对无关的改动进入补丁。

基线备注：T03 本地 owner-path 测试通过不等于跨队生产接线通过。当前发布与配对状态均为
待处理：先解决 fork/权限阻断，再处理 T02 requested changes，并等待 T08 提交 Wave B 接线 PR。

## 3. T03 -> T02 接口核对

### 3.1 身份与版本

- [ ] `FeedbackRecord.run_id` 与 T02 `PlanVersion.run_id` 一致。
- [ ] `target_version_id` 使用 `<run_id>:vN`，没有把 `"v1"` 当 canonical ID。
- [ ] directive 目标等于当前被修订版本；陈旧目标被明确拒绝或按已批准策略处理。
- [ ] `resulting_version_id` 是直接下一版，parent 精确指向 target。
- [ ] 重试/并发不会为同一 decision 生成两个直接子版本。

证据（文件/行、测试、输出）：TBD

### 3.2 Prompt 真正接线

- [ ] T02 仍独占 `RevisionContext`、`PlanVersion`、`RevisionPromptBuilder`，T03 未向
  `extra="forbid"` 模型塞字段。
- [ ] record/decision 先经过 `RevisionFeedbackContextBuilder.build()` 交叉核对。
- [ ] 基础 payload 经 `RevisionPromptAdapter.inject()` / `build_*_input()` 返回新快照，调用方对象未被原地修改。
- [ ] 实际 Agent 调用 payload 顶层含 `human_feedback`。
- [ ] payload 含正确 `feedback_id`、target、disposition 和 accepted instructions。
- [ ] payload 不含 rejected item、原始 feedback 全文或 decision reason。
- [ ] `rejected` 决策无法触发 revision 调用。
- [ ] 保存了实际 Prompt payload fingerprint，并能关联新版本与 lineage。
- [ ] `RevisionPromptAdapter.build_execution_metadata()` 的 receipt 与实际 payload、source version
  和 diff hash 一致。
- [ ] 对比无反馈基线，能证明获准反馈改变输出；若未改变，有结构化、可审计的拒绝/无影响理由。

证据（实际 payload 摘要需脱敏）：TBD

### 3.3 Version / diff / issue closure

- [ ] 新 PlanVersion 连续且可 round-trip。
- [ ] 结构化 diff 的 SHA-256 与 lineage `revision_generated.payload_sha256` 一致。
- [ ] issue open/resolved 状态映射到 T03 severity sidecar，没有把 `critical_issue` 自动当 P0。
- [ ] open P0/P1 时 T02 不把状态提升到 ready/validated。
- [ ] revision requested/generated 与 issue closure 事件按顺序追加，没有覆盖历史。

证据：TBD

## 4. T03 -> T08 接口核对

### 4.1 API 身份、权限与输入

- [ ] `job_id` 先通过 JobStore 解析到可信 `upstream_run_id`，没有直接当 `run_id`。
- [ ] target version 通过版本存储验证存在，短标签没有被无依据拼接。
- [ ] actor 已认证，并对 run/version 做资源级授权；`actor_id` 字段没有被当作鉴权本身。
- [ ] 空白、超长、非法 Unicode/ID/版本输入返回稳定安全错误。
- [ ] correlation ID 贯穿 API、FeedbackRecord、lineage 和日志。
- [ ] 原始 Idempotency-Key 只短暂进入 `FeedbackSubmission`，由 `DefaultFeedbackService`
  单次 hash；T08 不落库、不输出，也没有先 hash 后被 service 二次 hash。

证据：TBD

### 4.2 POST / GET 行为

- [ ] POST 不再固定返回 503，占位代码已由真实 T03 adapter 替换。
- [ ] POST 首次提交返回稳定 `feedback_id` 和 `submitted/processing` 等真实 projection。
- [ ] 同键同请求重放返回同一反馈且不重复写。
- [ ] 同键不同请求返回 409 `feedback.idempotency_conflict`（或已记录的等价 API code）。
- [ ] 并发重放只创建一条 feedback 与 lineage。
- [ ] GET 在进程重启后仍能查询 record/decision/resulting version。
- [ ] `unavailable` 只作为 API projection，不伪造为 T03 disposition。
- [ ] 403/404/409/422/500/503 映射已按审查结论固定，错误不泄漏内部异常或恶意文本。

证据（请求/响应需脱敏）：TBD

## 5. Validator / Gate / Metrics 联合核对

- [ ] E2E 收集 ResearchPlan、EvidenceCards、AgentTrace、execution metadata、QuestionItem 五类产物。
- [ ] run/question/version/`actual_execution` 身份一致。
- [ ] 缺产物、伪造引用、跨问题污染、错误 execution 标记至少各有一个阻断用例。
- [ ] 无 gate、重复 gate ID、gate 异常、runner 异常均 fail closed。
- [ ] 任一 open P0/P1 时 ValidationReport 必为 blocked。
- [ ] 通过报告绑定完整 ValidationContext hash，不能拿别的版本报告复用。
- [ ] `ValidationAuditWriter.record()` 追加确定性 gate/report 事件，失败后重试不重复、不分叉。
- [ ] metrics 按 `(question_id, version_id)` 聚合，同 report 重放不重复计数。
- [ ] metrics/错误响应不含原始 feedback、rejected text、幂等键或内部堆栈。

证据：TBD

## 6. SQLite / migration / rollback 核对

- [ ] 已记录 DB 路径、owner、权限、备份和保留期限（不要在公开记录暴露敏感绝对路径）。
- [ ] v1 三表、外键、唯一约束和索引与交付文档一致。
- [ ] WAL、busy timeout、并发写和锁超时行为已测试。
- [ ] 部署前备份已计算 hash，且已在副本上完成恢复演练。
- [ ] 旧字符串 feedback 只迁成 `legacy_unverified` 或进入隔离清单，没有自动当 accepted。
- [ ] 回滚优先断开 T02/T08 接线并保留审计表，不会自动删库。
- [ ] 在途/失败 feedback 的人工处置 owner 和时限已记录。

证据：TBD

## 7. 测试与 CI 证据

不要只粘贴“绿灯”截图；填写可复跑命令、精确 SHA 和完整摘要。

| 检查 | 命令/工作流 URL | 结果（passed/failed/skipped） | 证据时间 |
| --- | --- | --- | --- |
| T03 `tests/validation` 套件 | `.\.venv\Scripts\python.exe -m pytest -q tests\validation` | `100 passed in 4.07s` | 2026-08-03 |
| Feedback SQLite/并发/攻击测试 | 包含于 `tests/validation` | 通过；套件共 `100 passed` | 2026-08-03 |
| T02 + T03 候选组合测试 | 临时合并 T02 `a19e790…` 与 T03 分支后运行 validation + revision suites | `139 passed, 3 skipped`；合并无冲突，但 `CHANGES_REQUESTED`/生产接线仍未关闭 | 2026-08-03 |
| T08 + T03 API/idempotency 集成 | 当前无 T08 Wave B PR | 未执行；接口仍为占位 503 | TBD |
| 最小 E2E | 仅有 T03 离线 owner-path 证据；生产跨队命令 TBD | 生产 T02/T08 E2E 未完成 | TBD |
| 全仓 unit | `pytest -q --ignore=tests/integration`（CI UTF-8 环境） | `730 passed, 37 skipped` | 2026-08-03 |
| integration | `pytest -q tests/integration` | `1 passed` | 2026-08-03 |
| lint | `wave_a_quality.py lint` | 通过，`failures=[]` | 2026-08-03 |
| type | `wave_a_quality.py type` | 通过，`failures=[]` | 2026-08-03 |
| security | `scripts/audit_project.py` | PASS，`critical=0, warnings=2` | 2026-08-03 |
| build | compileall + benchmark dry-run + validate-result | 通过，`failures=[]` | 2026-08-03 |

skip/xfail 说明：`tests/validation` 无 skip/xfail；全仓 unit 有 `37 skipped`，原因包括缺少
可选数据文件及 Windows 无符号链接特权。远端 GitHub CI 仍为 TBD。

## 8. 阻断项与处理决定

当前协调/发布阻断：

| Blocker ID | 已确认事实 | 所需处理 | Owner | 状态 |
| --- | --- | --- | --- | --- |
| PUBLISH-001 | 个人仓库 `isFork=false`，团队仓库权限为 READ，无法按既定 Fork 流程创建 Draft PR | 创建一个不同名称的真实 fork（不改动现有仓库），或由管理员授予写入权限；随后推送并补 PR URL/HEAD | T03 / 仓库管理员 | open |
| PAIR-T02-001 | T02 PR #21 HEAD `a19e790ed634fd162405434e618cdb9f9c1c08de` 与 T03 候选组合测试 `139 passed, 3 skipped`，但 review decision 仍为 `CHANGES_REQUESTED` | T02 处理 requested changes；双方记录最终 SHA、复跑组合测试并签字 | T02 / T03 | open |
| PAIR-T08-001 | 当前无 T08 Wave B PR，feedback POST/GET 仍为 503 | T08 提交真实 adapter 路由改动并完成 API/idempotency E2E | T08 / T03 | open |

以下表格保留给代码/契约 finding；上面的协作状态不自动等同于 P0/P1 技术 finding：

| Finding ID | Severity | 描述 | Owner | 截止 | 证据/关闭理由 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| TBD | P0/P1/P2/P3 | TBD | TBD | TBD | TBD | open/resolved |

规则：

- open P0/P1 时结论不得为“通过”；
- resolved P0/P1 必须给 issue ID、修复 SHA、复测输出与 reviewer；
- P2/P3 延期必须记录接受风险的人与到期时间；
- “在我机器上能跑”或口头确认不是关闭证据。

## 9. 最终结论与签字

审查结论（只能选一项）：

- [ ] 通过：三方精确 SHA 已验证，T03-B-001..021 均有证据，open P0/P1 为 0。
- [ ] 有条件通过：仅存在已明确接受的 P2/P3，列于上表。
- [ ] 不通过：仍有 open P0/P1、T08 仍是占位 503、实际 Prompt 未接入，或 E2E/恢复证据缺失。
- [x] 待对接/待复审：当前真实状态；存在 PUBLISH-001、PAIR-T02-001、PAIR-T08-001。

| 角色 | 姓名/账号 | 结论 | 日期 | 审查链接/签字 |
| --- | --- | --- | --- | --- |
| T03 | TBD | TBD | TBD | TBD |
| T02 | TBD | TBD | TBD | TBD |
| T08 | TBD | TBD | TBD | TBD |
| 独立复审 | TBD | TBD | TBD | TBD |

最终备注：TBD
