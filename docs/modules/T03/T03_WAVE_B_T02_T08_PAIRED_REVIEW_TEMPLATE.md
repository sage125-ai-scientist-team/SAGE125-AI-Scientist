# T03 Wave B × T02/T08 配对审查记录模板

用途：记录 T03 Feedback/Revision/Validator 与 T02 版本修订、T08 API 的真实接线证据。

> 此文件同时记录阶段性技术证据，但不是最终三方验收证明。T02 PR #21 当前 HEAD 为
> `20a5b356364051c86dac3698fc836c790b6c2c79`，T03 已在实现提交
> `e4248e8ad215b0b77279990eb2bf6553b60b52d1` 完成 lineage 持久化消费接线；
> T08 仍没有 Wave B PR，feedback POST/GET 仍返回 503
> `UPSTREAM_CONTRACT_UNAVAILABLE`。在 T02/T08/独立复审签字完成且队长授权前，
> 结论仍为“待对接/待复审”，PR #32 保持 Draft。

## 1. 审查元数据

| 项目 | 填写内容 |
| --- | --- |
| 审查日期/时区 | 2026-08-03 首轮；2026-08-06 T02 lineage 接线复验 / Asia/Shanghai；最终签字时间 TBD |
| T03 负责人 | `ybq-music` |
| T02 负责人 | `Mk007115`（PR #21 作者） |
| T08 负责人 | TBD |
| 独立复审人 | TBD |
| T03 PR / HEAD SHA | [Draft PR #32](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/32)；lineage consumer 实现 HEAD `e4248e8ad215b0b77279990eb2bf6553b60b52d1`；最终远端 HEAD 见 PR |
| T02 PR #21 / 被审 SHA | `20a5b356364051c86dac3698fc836c790b6c2c79`；open/Ready、六项 CI SUCCESS，既有 `CHANGES_REQUESTED` 尚待队长处理 |
| T08 PR / 被审 SHA | 当前无 Wave B PR；被审 SHA/PR URL TBD；feedback 接口仍为 503 |
| 发布 Fork | `ybq-music/SAGE125-AI-Scientist-T03`，`isFork=true`，parent 为团队仓库 |
| 原个人仓库 | `ybq-music/SAGE125-AI-Scientist`，保持独立备份，未改动 |
| 团队仓库权限 | `sage125-ai-scientist-team/SAGE125-AI-Scientist`，`viewerPermission=READ` |
| T03 本地 validation 测试 | `105 passed in 4.34s` |
| integration base SHA | `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c` |
| T02/T03 merge-base | `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c` |
| 测试环境/DB 类型 | Windows / Python 3.12 / SQLite 临时数据库 |
| correlation ID / E2E run ID | TBD |

## 2. 当前基线事实（审查开始前确认）

- [x] 已确认 T02 PR #21 当前 HEAD 为 `20a5b356364051c86dac3698fc836c790b6c2c79`；
  open/Ready、六项 CI SUCCESS，既有 review decision `CHANGES_REQUESTED` 尚未解除。
- [x] 已确认 T08 当前没有 Wave B PR，feedback POST/GET 仍为 503 占位。
- [x] 已通过新建不同名称的真实 Fork 解决发布阻断，并创建 Draft PR #32；原独立仓库未改动。
- [x] 已确认 T03 使用 `schema_version=1`，且没有增删冻结字段/枚举；仅修复了一个引用不存在字段的验证器。
- [ ] 已确认三方分支均基于同一 integration 祖先；T02/T03 merge-base 已记录为
  `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`，T08 仍待 PR/SHA。
- [x] 已确认本次 T03 补丁只修改 T03 owner 路径，未修改 T02 workflow、T08 API 或队长专属文件。

基线备注：T03 本地 owner-path 测试通过不等于跨队生产接线通过。当前发布与配对状态均为
待处理：先解决 fork/权限阻断，再处理 T02 requested changes，并等待 T08 提交 Wave B 接线 PR。

## 3. T03 -> T02 接口核对

### 3.1 身份与版本

- [x] `FeedbackRecord.run_id` 与 T02 `PlanVersion.run_id` 一致。
- [x] `target_version_id` 使用 `<run_id>:vN`，没有把 `"v1"` 当 canonical ID。
- [x] directive 目标等于当前被修订版本；错误 source/identity fail closed。
- [x] `resulting_version_id` 是直接下一版，parent 精确指向 target。
- [x] 重试/16 线程并发消费不会为同一 decision 生成两个直接子版本绑定。

证据：`tests/validation/test_t02_t03_final_pairing_recheck.py`；精确 T02/T03 SHA
临时组合测试；`examples/t02_t03_revision_lineage_pairing_evidence.json`。

### 3.2 Prompt 真正接线

- [ ] T02 仍独占 `RevisionContext`、`PlanVersion`、`RevisionPromptBuilder`，T03 未向
  `extra="forbid"` 模型塞字段。
- [ ] record/decision 先经过 `RevisionFeedbackContextBuilder.build()` 交叉核对。
- [ ] 基础 payload 经 `RevisionPromptAdapter.inject()` / `build_*_input()` 返回新快照，调用方对象未被原地修改。
- [x] 实际 Agent 调用 payload 顶层含 `human_feedback`。
- [x] payload 含正确 `feedback_id`、target、disposition 和 accepted instructions。
- [x] payload 不含 rejected item、原始 feedback 全文或 decision reason。
- [ ] `rejected` 决策无法触发 revision 调用。
- [x] 保存了实际 Prompt payload fingerprint，并能关联新版本与 lineage。
- [ ] `RevisionPromptAdapter.build_execution_metadata()` 的 receipt 与实际 payload、source version
  和 diff hash 一致。
- [ ] 对比无反馈基线，能证明获准反馈改变输出；若未改变，有结构化、可审计的拒绝/无影响理由。

证据：T02 `tests/workflow/test_t02_t03_revision_handoff.py` 3 passed；T02 实际模型输出已由
T03 consumer 写入 SQLite 并重启恢复，完整 metadata 见脱敏 evidence JSON。

### 3.3 Version / diff / issue closure

- [x] 新 PlanVersion 连续且可 round-trip。
- [x] 结构化 diff 的 SHA-256 与 lineage `revision_generated.payload_sha256` 一致。
- [ ] issue open/resolved 状态映射到 T03 severity sidecar，没有把 `critical_issue` 自动当 P0。
- [ ] open P0/P1 时 T02 不把状态提升到 ready/validated。
- [x] revision requested/generated 与 issue closure 事件按顺序原子追加，没有覆盖历史。

证据：SQLite 重启恢复值
`revision_diff_sha256=4f0f9fda9eef9b57a467fd243101aa4fce43af1789561f5ba92f7902d0070397`；
真实父链为 `feedback_decided -> event:55f7ecda13127579 -> event:73f66880eefc20da ->
event:a2c31e666da5b460 -> event:d9d644bc57841591`。

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
| 指定最终配对复验 | `.\.venv\Scripts\python.exe -m pytest -q tests\validation\test_t02_t03_final_pairing_recheck.py` | `5 passed in 1.48s` | 2026-08-06 |
| T03 `tests/validation` 套件 | `.\.venv\Scripts\python.exe -m pytest -q tests\validation` | `105 passed in 4.34s` | 2026-08-06 |
| Feedback SQLite/并发/攻击测试 | 包含于 `tests/validation` | 原子批量、重启、重复、16 线程并发与冲突回滚均通过 | 2026-08-06 |
| T02 + T03 精确 SHA 组合测试 | 临时普通合并 T02 `20a5b356…` 与 T03 `e4248e8…`，运行 validation + T02 handoff + 实际模型消费测试 | `109 passed in 6.09s`；无合并冲突；T03 技术接线通过，待 T02 签字 | 2026-08-06 |
| T08 + T03 API/idempotency 集成 | 当前无 T08 Wave B PR | 未执行；接口仍为占位 503 | TBD |
| 最小 E2E | 仅有 T03 离线 owner-path 证据；生产跨队命令 TBD | 生产 T02/T08 E2E 未完成 | TBD |
| 全仓 unit | `pytest -q --ignore=tests/integration`（CI UTF-8 环境） | `735 passed, 37 skipped in 63.52s` | 2026-08-06 |
| integration | `pytest -q tests/integration` | `1 passed in 0.18s` | 2026-08-06 |
| lint | `wave_a_quality.py lint` | 通过，`failures=[]` | 2026-08-06 |
| type | `wave_a_quality.py type` | 通过，`failures=[]` | 2026-08-06 |
| security | `scripts/audit_project.py` | PASS，`critical=0, warnings=2` | 2026-08-06 |
| build | compileall + benchmark dry-run + validate-result | 通过，`failures=[]` | 2026-08-06 |

skip/xfail 说明：`tests/validation` 无 skip/xfail；全仓 unit 有 `37 skipped`，原因包括缺少
可选数据文件及 Windows 无符号链接特权。远端 GitHub CI 仍为 TBD。

## 8. 阻断项与处理决定

当前协调/发布状态：

| Blocker ID | 已确认事实 | 所需处理 | Owner | 状态 |
| --- | --- | --- | --- | --- |
| PUBLISH-001 | 已创建真实 fork `ybq-music/SAGE125-AI-Scientist-T03` 并开立 Draft PR #32；原独立仓库不变 | 观察远端 CI；配对完成前保持 Draft | T03 | resolved |
| PAIR-T02-001 | T02 `20a5b356…` 与 T03 `e4248e8…` 的实际 handoff 已持久化并重启恢复；组合测试 `109 passed` | T02 使用 PR #32 新远端 HEAD 再跑指定 5 项并签字；队长处理既有 review decision | T02 / T03 | T03 technical resolved；external sign-off open |
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
- [x] 待对接/待复审：当前真实状态；发布阻断 PUBLISH-001 已解决，仍存在 PAIR-T02-001、PAIR-T08-001。

| 角色 | 姓名/账号 | 结论 | 日期 | 审查链接/签字 |
| --- | --- | --- | --- | --- |
| T03 | `ybq-music` | lineage consumer 接线与 owner-path 复验通过；保持 Draft，等待跨队签字 | 2026-08-06 | PR #32 / implementation `e4248e8ad215b0b77279990eb2bf6553b60b52d1` |
| T02 | TBD | TBD | TBD | TBD |
| T08 | TBD | TBD | TBD | TBD |
| 独立复审 | TBD | TBD | TBD | TBD |

最终备注：T02 lineage 持久化缺口已由 T03 修复；本记录不宣称 T08 live API 已完成，
也不授权将 PR #32 转 Ready、Approve 或 Merge。
