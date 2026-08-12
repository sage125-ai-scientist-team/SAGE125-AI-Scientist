# T03 最终 handoff

> 状态：DRAFT；本文件是交接模板，不是完成声明。
> 当前工作分支：`t03/c-validation-hardening`。
> 起始 base：`20592a0eeb9924d021e3ec75ec28d27e2f971e9f`。

## 1. 模块目的

T03 让人工反馈成为下一轮可审计输入，并以完整五类产物执行 fail-closed
Schema/质量门。它负责：

- feedback 提交、权限、安全校验、幂等、决策和 SQLite 持久化；
- accepted-only revision directive 与 T02 revision lineage handoff；
- ResearchPlan、EvidenceCards、AgentTrace、`execution_metadata`、`question_item`
  的不可变 `ValidationContext`；
- P0-P3 finding、gate 聚合、`ValidationReport`、指标和 audit lineage；
- 缺输入、虚构引用、错误执行声明、串题、异常和并发重放的 fail-closed 处理。

T03 不拥有 pipeline、HTTP API、T07 batch adapter 或 T08 部署。

## 2. PR 与提交链

| Wave | 分支 | PR | 记录 |
| --- | --- | --- | --- |
| A | `t03/a-validation-contract` | [#14](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/14) | integration merge `179d9cc` |
| B | `t03/b-validation-core` | [#32](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/32) | integration merge `592c874` |
| C | `t03/c-validation-hardening` | 【待回填：PR-C 链接/编号】 | HEAD【待回填：40 位 SHA】 |

最终目标 integration commit：**【待回填：PR-C merge 后 40 位 SHA】**。PR-A/PR-B 的历史
记录不能替代 PR-C 最终 HEAD 的复验。

## 3. 代码入口和关键符号

### 反馈闭环

- `app.feedback.DefaultFeedbackService`
  - `submit_request(...)`
  - `submit(...)`
  - `decide(...)`
  - `build_directive(...)`
  - `consume_revision_lineage_handoff(...)`
- `app.feedback.SQLiteFeedbackStore`
  - `get_feedback(...)`
  - `get_decision(...)`
  - `get_lineage_by_feedback(...)`
- `app.feedback.RevisionFeedbackContextBuilder`
- `app.feedback.RevisionPromptAdapter`
- `app.feedback.RevisionLineageConsumer`
- `app.feedback.import_legacy_feedback`

### Validator / 质量门

- `app.contracts.validation.ValidationContext`
- `app.quality.DefaultQualityGateRunner`
- `app.quality.build_default_quality_gates`
- `app.validation.DefaultValidationService`
- `app.validation.ValidationAuditWriter`
- `app.validation.ValidationMetricsCollector`

契约真值来源：`app/contracts/validation.py`。接口、错误码、指标和运维细节见
`docs/modules/T03/T03_WAVE_C_INTERFACE_MIGRATION_OPERATIONS.md`。

## 4. 配置

T03 不直接读取环境变量。上层必须显式传入：

- SQLite 持久路径；
- `timeout_seconds`（默认 `5.0`）；
- 真实 `FeedbackAuthorizer`（缺省 deny-all）；
- `max_feedback_length`（默认 `10_000`）；
- 可选 UTC-aware clock、ID factory 和 `ValidationMetricsCollector`。

生产禁止用 `AllowAllFeedbackAuthorizer` 或 `:memory:` 代替真实授权/持久化。SQLite schema
为 v1，WAL + foreign keys + `BEGIN IMMEDIATE`；未来 schema 必须 fail closed。

## 5. 安装与复现

在干净工作区、仓库根目录执行。依赖安装方式以仓库 README/锁定清单为准，不在 handoff
中升级依赖。

```powershell
.\.venv\Scripts\python.exe docs/modules/T03/wave_c/run_calibration.py --verify-only
.\.venv\Scripts\python.exe docs/modules/T03/wave_c/run_calibration.py `
  --output-dir docs/modules/T03/wave_c
.\.venv\Scripts\python.exe -m pytest -q tests/validation/test_wave_c_calibration.py
.\.venv\Scripts\python.exe -m pytest -q tests/validation/test_wave_c_security_stability.py
.\.venv\Scripts\python.exe -m pytest -q tests/validation/test_wave_c_flagship_t07_pairing.py
.\.venv\Scripts\python.exe -m pytest -q tests/validation
.\.venv\Scripts\python.exe -m pytest -q tests/validation -W error
.\.venv\Scripts\python.exe -m pytest -q tests/batch/test_completion_gate.py
.\.venv\Scripts\python.exe -m compileall -q app/feedback app/validation app/quality app/contracts/validation.py
```

Wave C 机器证据的最终命令、路径和结果：

```text
CALIBRATION COMMAND: python docs/modules/T03/wave_c/run_calibration.py --verify-only
CALIBRATION RESULT: exit 0; 12 synthetic contract fixtures / 24 cases; 0 mismatches
NEGATIVE/CONCURRENCY COMMAND: python -m pytest -q tests/validation/test_wave_c_security_stability.py
NEGATIVE/CONCURRENCY RESULT: 21 passed (20 cases + evidence consistency)
FLAGSHIP/Q028 COMMAND: python -m pytest -q tests/validation/test_wave_c_flagship_t07_pairing.py
FLAGSHIP/Q028 RESULT: 4 passed; actual receipt fail-closed without native T03 trace; T07 direct boundary passed
FULL TEST COMMAND: python -m pytest -q tests/validation
FULL TEST RESULT: 137 passed / 0 failed / 0 skipped
RAW RESULTS: docs/modules/T03/wave_c/calibration_raw_results.json
METRICS: docs/modules/T03/wave_c/calibration_metrics.json
EVIDENCE HEAD: PR-C 当前 HEAD（PR 创建后回填）
```

所有跳过项必须说明原因。未运行的 live/provider/private-data 测试不计入 Wave C 指标。

## 6. 最小运行流程

### 提交与决策

1. 构造 `SQLiteFeedbackStore`；
2. 注入真实 authorizer 并构造 `DefaultFeedbackService`；
3. 以 `FeedbackSubmission` 调用 `submit_request`；
4. 由授权 actor 写入 `FeedbackDecision`；
5. 对 accepted/partially accepted 调用 `build_directive`；rejected 必须返回 `None`；
6. T02 产生 revision 后调用 `consume_revision_lineage_handoff`；
7. validation 后由 `ValidationAuditWriter` 追加 gate/validation 事件；
8. 关闭并重开 SQLite，以 feedback ID 回查并核对事件父链和 SHA。

### 完整验证

1. 从同一 run/question/version 的五类实际产物构造 `ValidationContext`；
2. 调用 `DefaultValidationService(DefaultQualityGateRunner()).validate(context)`；
3. 只接受 `report.validation_status == "passed"` 且无 open P0/P1；
4. 保存 report/gates 并绑定输入 fingerprint 和当前 commit；
5. T07 只有在全部批量条件通过时才可标记 `complete`。

## 7. 失败处理

- `feedback.invalid_input` / `unsafe_input`：修正或拒绝；不得进入 prompt；
- `feedback.permission_denied`：重新鉴权；不得降级为 allow-all；
- conflict/idempotency/fingerprint conflict：保留旧快照，禁止覆盖；
- storage/corrupt/unsupported schema：停止写入，保全 DB/WAL，使用验证过的备份恢复；
- gate/runner 异常或空结果：视为 P0/P1 blocker，绝不能解释为 passed；
- 缺 EvidenceCards/AgentTrace、身份污染、虚构引用、错误 actual execution：阻断；
- 并发重放：只能产生单一 record、直接子版本和单链 lineage，否则升级 P0。

## 8. 备份与恢复

1. 停写或进入维护态；
2. 使用 SQLite 一致性 backup，不只复制主文件；
3. 记录 DB/backup SHA、UTC 时间、代码 commit；
4. 在隔离新路径恢复；
5. 通过 v1 store 打开并抽样读取 feedback/decision/lineage；
6. 核对事件父子链、diff hash、version、validation report；
7. 进程重启后复核；
8. 验证后切换，不原地覆盖唯一副本。

本 PR 未执行生产 DB 备份/切换演练。测试已覆盖临时 SQLite 阻断报告重试、关闭重开、
事件父链/SHA 不变与损坏快照 fail-closed；这不替代部署环境的业务级备份演练。

## 9. 已知限制

1. **T07 adapter 仍调用旧接口。**
   `app.batch.completion_gate.run_t03_quality_gates()` 目前走
   `app.workflow.quality_gates.run_all_quality_gates` + `GateResult.from_legacy()`；
   尚不能声称与冻结的 `DefaultQualityGateRunner` / `DefaultValidationService` 完成正式配对。
2. **live batch 未运行。** fixture/离线测试不能冒充生产批量结果。
3. **旗舰/Q028 只有 receipt 抽查，非 actual 全链路。** T05 actual receipt 已以 SHA-256
   绑定，但没有原生 T03 AgentTrace；因此 T03 正确阻断。构造 envelope 不计真实五类输入。
4. **T08 out of scope。** 本 Wave C 不处理 T08 API、503、路由、部署或 UI。
5. metrics collector 是进程内状态，持久导出由上层负责。
6. 备份调度、保留期、加密和告警由部署 composition root 负责。

## 10. 回滚

回滚 PR-C 时保留 PR-A/PR-B 的 v1 契约与 SQLite 数据；应用切回最后一个兼容 v1 的已知
commit。不得删除审计记录、直接编辑 `payload_json`、强改 `PRAGMA user_version` 或用旧
Mock 替代复验。数据异常时先保全 DB/WAL，再从验证过的备份恢复到新路径。

回滚目标：移除 PR-C 的测试与证据提交，不回滚已合并 PR-A/PR-B 的 v1 契约/数据。
回滚后复验 `tests/validation` 和 T02/T03 配对测试；生产数据不需要由本 PR 迁移。

## 11. 后续 Issue / 外部行动人

| 项目 | owner | 关闭条件 | 状态 |
| --- | --- | --- | --- |
| T07 改用冻结 T03 validator | T07 + T03 配对 | owner-path 接线、失败题不 complete、同 SHA 签字 | OPEN |
| live batch | T07 / captain | 授权运行、非 Mock 原始产物、审计结果 | OPEN |
| 旗舰/Q028 原生 T03 bundle | T03 + 数据 owner | 真实五类输入、输出 SHA、report 与 commit | receipt 已审计；缺 native AgentTrace，OPEN |
| PR-C review / Ready / merge | captain | checks、Codex/配对 review、P0/P1 关闭 | OPEN |

## 12. 最终交接签字

```text
PR-C: 【待回填】
PR-C HEAD: 【待回填：40 位 SHA】
TARGET INTEGRATION: integration/2026-08-10
TARGET INTEGRATION SHA: 20592a0eeb9924d021e3ec75ec28d27e2f971e9f（发布前再次核验）
BEHIND: 0（起始快照；发布前再次核验）
TESTS: tests/validation 137 passed；目标配对 30 passed
GITHUB CHECKS: 【待回填】
T03-METRIC-001: 20 PASS
T03-METRIC-002: 12 synthetic contract fixtures only / PARTIAL
OPEN P0/P1: T03 owner code 0；外部证据缺口见限制
T07 PAIRED REVIEW: direct GateResult boundary PASS；default adapter NO
CODEX REVIEW: 当前本地证据复核无 P0；远端 review 待 PR
CAPTAIN READY AUTHORIZATION: 【待回填】
HANDOFF_STATUS: NOT_READY
```
