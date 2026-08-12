# T03 Wave C 冻结审计表

> 审计状态：DRAFT / NOT READY。
> 审计 base：`20592a0eeb9924d021e3ec75ec28d27e2f971e9f`。
> PR-C、最终 HEAD、远端 checks 与批准记录待回填；本地机器证据已执行。

## 1. 发布链

| 阶段 | PR | integration 记录 | 状态 |
| --- | --- | --- | --- |
| Wave A | [PR #14](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/14) | merge commit `179d9cc` | 已进入当前 base 历史 |
| Wave B | [PR #32](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/32) | merge commit `592c874` | 已进入当前 base 历史 |
| Wave C | [PR #50](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/50) | evidence commit `815b7fee98f45034964f3eb27816358a924340d7` | Draft / NOT READY |

本表中的“当前 base 历史”只说明 Git 历史包含相应 merge commit，不代替 PR-C 当前 HEAD 的
CI、审核或发布签字。

## 2. C-001..009 验收矩阵

| ID | 要求 | 需要的最终证据 | 当前状态 |
| --- | --- | --- | --- |
| T03-C-001 | C 分支；12 题 Schema/质量门校准；补并发、恶意输入、缺产物回归；Draft PR-C | manifest、脚本、原始结果、测试、PR/HEAD | PARTIAL：12 synthetic fixtures 与 20 安全案例完成；actual 12题/PR 待完成 |
| T03-C-002 | 校准报告；Draft PR-C | 本报告对应文档 + PR 链接 | PARTIAL：报告与执行证据完成；PR 待创建 |
| T03-C-003 | 无普遍误阻断或缺输入仍通过 | 12 题结果与负向断言 | PASS（离线 contract-fixture 边界）；actual 题集未证明 |
| T03-C-004 | API 契约、迁移、运维、错误码、指标；T07 联调；处理审查 | 接口运维文档、联调 HEAD、审查记录 | PARTIAL：文档已建；T07 仍走旧入口 |
| T03-C-005 | 接口文档；审查修订提交 | 文档 + 审查 commit | PARTIAL：文档与本地复核完成；commit 待创建 |
| T03-C-006 | 批量失败题不进入 complete；无未登记共享改动 | T07 配对测试 + owner map/diff | BLOCKED：live batch 未运行，T07 正式新接口联调未完成 |
| T03-C-007 | 抽查旗舰、Q028、批量输出；同步 integration、全测试、Codex review | actual 输入/输出 SHA、测试、review、behind=0 | PARTIAL：Q028 receipt SHA 已验且因缺 native trace 正确 blocked；T07 direct boundary 通过；live batch/远端 review 未完成 |
| T03-C-008 | 冻结审计表；PR-C Ready | 本表 + Ready 授权/PR 状态 | PARTIAL：本表草案已建；不得据此转 Ready |
| T03-C-009 | 无“缺输入仍通过”；P0/P1 关闭 | negative suite + open issue register | T03 owner-path PASS：20/20 安全案例；外部配对缺口仍 OPEN |

## 3. FINAL DoD

| ID | Definition of Done | 验证方法 | 当前状态 |
| --- | --- | --- | --- |
| T03-DOD-001 | 下一轮 prompt 可找到 `feedback_id` 和具体意见；输出变化或有可审计拒绝理由 | accepted/partial/rejected 精确 payload、T02 handoff 与 lineage | PASS：T02/T03 配对复验随目标套件通过 |
| T03-DOD-002 | open P0/P1 时 `validation_status` 不得为 `passed` | contract/service/gate negative tests | PASS：Q102 P1、Q028 trace 缺失和安全负例均 blocked |
| T03-DOD-003 | 至少 10 个无效/恶意/缺产物/并发失败用例，审计链不丢失 | `T03-METRIC-001` manifest、原始结果、SQLite 重启/并发证明 | PASS：20/20，含重启、并发、篡改 |

必须交付对象 `FeedbackRecord`、`FeedbackDecision`、`ValidationContext`、`GateResult`、
`Severity`、audit lineage 及五类 validator 输入均需在 PR-C HEAD 上重新检查，不能只引用旧
PR 的成功记录。

## 4. 定量门

| 指标 | 门槛 | 结果 | 结论 |
| --- | ---: | ---: | --- |
| `T03-METRIC-001` | `>=10` 个独立负向/并发案例 | 20 | PASS |
| `T03-METRIC-002` | `=12` 个 actual 代表题 | 12 synthetic contract fixtures | PARTIAL；不可冒充 actual |

计数只接受与最终 HEAD 绑定的 machine-readable manifest、计算脚本、raw results、metrics 和
复现命令。`skipped`、旧 Mock、旧失败产物和未授权 live 数据不计数。

## 5. 接口冻结检查

- [x] `schema_version=1` 的公共字段、枚举和 JSON shape 未删除/改名；
- [x] P0/P1 阻断规则未放宽；
- [x] `FeedbackService`、`FeedbackStore`、`QualityGateRunner`、
  `ValidationService` 的公共签名兼容；
- [x] 变更只落在 T03 owner 路径，或共享改动有队长登记；
- [x] 无 `pipeline.py`、API route、`app/batch/**` 的越权修改；
- [x] 无依赖升级、密钥、私有数据或不可分发产物；
- [ ] 所有截图、trace、metrics 都绑定最终 HEAD，且不是旧 Mock；
- [ ] 分支相对目标 integration `behind=0`；
- [ ] GitHub checks 和配对审查均针对同一完整 HEAD。

owner map / changed-files：Wave C 暂存与提交将只包含 `tests/validation/**`、
`docs/modules/T03/**`；测试产生或暴露的 T01/T06/多模态 fixture 修改与临时缓存均明确排除。

## 6. P0/P1 发布阻断登记

| ID | 严重度 | 事实 | owner | 关闭条件 | 状态 |
| --- | --- | --- | --- | --- | --- |
| T03-C-BLOCK-001 | P1 | T07 adapter 仍调用旧 `app.workflow.quality_gates.run_all_quality_gates`，未直接使用冻结 T03 validator | T07（T03 配对） | T07 owner-path 接线 + 同 HEAD 配对测试 | OPEN |
| T03-C-BLOCK-002 | P1 | live batch 尚未运行，不能证明批量失败题在真实运行中不进入 complete | T07 / captain | 授权 live run、原始产物与审计结果 | OPEN |
| T03-C-BLOCK-003 | P1 | Q028 receipt 已绑定，但缺原生 T03 AgentTrace；构造 envelope 不算 actual 五类 bundle | T03 / 上游数据 owner | 提供原生五类输入并按 receipt SHA 联合复验 | OPEN |
| T03-C-BLOCK-004 | P1 | PR-C HEAD、CI、review、Ready 授权未产生 | T03 / captain | Draft PR-C、checks、review 和授权 | OPEN |

若实际测试发现“缺输入仍通过”、open P0/P1 被标记 passed、审计链分叉/丢失或损坏快照被
接受，必须新增 P0 阻断并停止 Ready/merge。

## 7. 已知限制与范围声明

1. T07 当前 adapter 仍走旧接口；文档和 T03 单测不等于 T07 配对完成。
2. live batch 未运行；fixture 校准不能声明生产准确率、稳定性或批量完成。
3. Q028 actual receipt 已绑定并严格 blocked；只有补齐真实五类 T03 输入后才算 actual 全链路。
4. T08 API/部署/503 替换明确 out of scope，本 PR 不修改也不据此阻断 T03 owner-path
   技术实现；若最终项目 DoD 另有跨任务门，由队长单独登记。
5. `ValidationMetricsCollector` 是进程内聚合器，不是持久监控后端；重启后需由上层重新装载
   或从已保存 report 重建。
6. SQLite v1 没有内建业务级备份调度；备份、保留期、加密和恢复演练由部署 composition
   root/运维负责。

## 8. 冻结日核对

Code Freeze 以后只允许处理队长、CI 或 Codex 指出的发布阻断：

- 不新增功能；
- 不改名公共接口；
- 不升级依赖；
- 不继续在已合并的旧分支开发；
- 只补阻断修复、证据、handoff、复现命令、已知限制和回滚说明。

最终签字区：

```text
PR-C: https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/50
PR-C EVIDENCE COMMIT: 815b7fee98f45034964f3eb27816358a924340d7
PR-C CURRENT HEAD: 以 GitHub PR 元数据为准（本签字文档回填提交晚于 evidence commit）
BASE: 20592a0eeb9924d021e3ec75ec28d27e2f971e9f
BEHIND: 0（起始 base；发布前再次核验）
TESTS: tests/validation 137 passed；目标配对 30 passed；非 integration 1373 passed/41 skipped；integration 32 passed
GITHUB CHECKS: 【待回填】
CODEX REVIEW: 【待回填】
PAIRED REVIEW: 【待回填】
OPEN P0: 0（T03 owner-path）
OPEN P1: 4 个外部/发布证据项见第 6 节
READY AUTHORIZATION: 【待回填：队长链接】
FREEZE_DECISION: NOT_READY
```
