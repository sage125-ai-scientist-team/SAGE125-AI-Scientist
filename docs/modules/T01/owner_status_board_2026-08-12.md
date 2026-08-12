# T01 Owner 状态板（2026-08-12，队长 #47 裁决后更新）

只读状态汇总。**不**宣称 Wave C Done；**不**宣称正式指标；T01 **不**代队长 merge。

## 1. 相关 PR

| PR | 主题 | State | Draft | HEAD（记录时） | T01 动作 |
|---|---|---|---|---|---|
| [#35](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/35) | Wave C evidence hardening | OPEN | yes | `b78981c…` | 保持 Draft；等队长 + 门 B |
| [#39](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/39) | T08 Delivery core / owner interface | **MERGED** | — | → `integration` @ `3d70e1f…` | 已合入；#43 需跟进同步 |
| [#43](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/43) | EvidenceBundle SQLite read port（T08） | OPEN | yes | `ae64360…` | 已 sync integration（behind=0）；仍 Draft |
| [#45](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/45) | pytest 不写坏 tracked metrics（#44） | OPEN | **no** | `20341f1…` | 等队长审核 |
| [#47](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/47) | T04 `retrieve_hits` | OPEN | **no（Ready）** | `f77959b…` | Gate A=PASS；等队长 squash merge |

## 2. 语义门 / 队长裁决（#47）

```text
GATE_A=PASS
GATE_A_TECHNICAL_REVIEW=PASS
T01_T04_RETRIEVE_HITS_SEMANTIC_SIGNOFF=PASS
BLOCKING_FINDINGS=NONE
REVIEWED_HEAD_SHA=f77959b43f7f520119070181011e0d0713425cdd
READY_AUTHORIZED=YES              # 仅 Gate A 接口；#47 已 Ready
MERGE_AUTHORIZED_NOW=NO
MERGE_AFTER_READY=YES             # 队长手工 squash；match-head 同上 SHA
WAVE_C_DONE=NO                    # 本合入不算 T04 Wave C Done
FORMAL_RETRIEVAL_METRICS=NOT_AUTHORIZED
T07_FIVE_REAL_RUNS=NOT_AUTHORIZED
GATE_B=WAIT
Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY
KEEP_PR_OPEN=YES
```

对 **#35**：仍无队长 Ready/Merge 授权 → 保持 Draft。

## 3. T01 已做 / 未做

| 项 | 状态 |
|---|---|
| Gate A 审查 + #47/#35 回帖 | 已做 |
| 对齐队长 #47 裁决更新文档 | 本轮 |
| 改 `app/rag/**` / 改 #47 tip / rebase / force-push | **不做** |
| 代队长 `gh pr merge` #47 | **不做** |
| 门 B 签字 | **等待** Q001 + T04 loader |
| #43 与最新 integration 同步 | 已做（merge tip `ae64360…`；store 测 10 passed） |

## 4. 等待谁

| 人 | 等待事项 |
|---|---|
| `@liuyanbo12` | 对 #47 按固定 SHA 手工 squash；审 #45/#43/#35；受控交付 Q001 |
| `@YHY0728` | #47 合入后继续 Wave C（安全/性能等）；Q001 loader/provenance |
| `@myr-111` | 仅消费 T04 manifest + T01 signoff；勿提前五题真跑 |
