# T01 Owner 状态板（2026-08-13 更新）

只读状态汇总。**不**宣称 Wave C Done；**不**自行 Ready/Merge（除队长明确授权且条件满足外）。

## 1. 相关 PR

| PR | 主题 | State | Draft | HEAD（记录时） | T01 动作 |
|---|---|---|---|---|---|
| [#35](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/35) | Wave C evidence hardening | OPEN | yes | `95df1eb…` | 保持 Draft；另册审 |
| [#39](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/39) | T08 Delivery core | **MERGED** | — | → integration | 已合入 |
| [#43](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/43) | EvidenceBundle SQLite read port | OPEN | **yes** | `097c46b…` | **behind=0**（sync #45 后）；等 CI 全绿后 @队长授权 Ready |
| [#45](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/45) | pytest metrics 副作用修复（#44） | **MERGED** | — | → integration @ 2026-08-13 | 已合入 |
| [#47](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/47) | T04 `retrieve_hits` | OPEN | **no（Ready）** | 仍 `f77959b…` | Gate A 对旧 tip 有效；**T04 须先 merge 消 behind=3**；新 tip 后 T01 再确认签字 |

## 2. 队长裁决摘要

### #43（T08 read port）

```text
T01_T08_READ_PORT_TECHNICAL=PASS
WAVE_C_DONE=NO
READY_AUTHORIZED=NO_UNTIL_BEHIND_0   # 2026-08-13：behind 已清零；仍 Draft，等 CI + 队长授权 Ready
MERGE_AUTHORIZED=NO
KEEP_PR_OPEN=YES
BEHIND=0
NEW_HEAD=097c46b2b7895d6f6584dce718b84feda6129b26
```

### #47（T04 Gate A）

```text
GATE_A prior PASS 仍有效（同一 SHA f77959b…）
MERGE_AUTHORIZED=NO
BLOCKER=behind_3                     # T04 须普通 merge integration；勿 force-push
KEEP_PR_OPEN=YES
WAVE_C_DONE=NO
T01_ACTION=等 T04 推新 tip 后快速确认 Gate A 签字（或声明纯 sync 无功能差）
```

### 语义门 / 材料

```text
GATE_A=PASS_ON_f77959b（待 T04 sync 后重确认）
GATE_B=WAIT
Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY
FORMAL_RETRIEVAL_METRICS=NOT_AUTHORIZED
T07_FIVE_REAL_RUNS=NOT_AUTHORIZED
```

## 3. T01 已做 / 未做（本轮）

| 项 | 状态 |
|---|---|
| #43 merge upstream → behind=0 + push | **已做** |
| #43 保持 Draft / 不 Ready / 不 force-push | **已做** |
| #43 本地 store+metrics 测 | 17 passed |
| 代 T04 同步 #47 分支 | **不做**（非 T01 路径） |
| 对 #47 新 tip 重签 Gate A | **等待** T04 推送（当前 tip 未变） |
| #35 Ready/Merge | **不做** |

## 4. 等待谁

| 人 | 等待事项 |
|---|---|
| `@liuyanbo12` | #43 CI 全绿后授权 Ready 并按 tip squash；#47 在 T04 sync+T01 重确认后 squash |
| `@YHY0728` | #47 merge `integration` 消 behind=3，推新 tip，等 CI |
| `@Yqqxz`（己） | #47 新 tip 后 Gate A 快速确认；#43 CI 绿后 @队长 |
| `@myr-111` | 勿提前五题真跑 |
