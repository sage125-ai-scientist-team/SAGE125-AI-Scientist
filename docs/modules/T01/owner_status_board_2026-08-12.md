# T01 Owner 状态板（2026-08-14 更新）

只读状态汇总。**不**宣称 Wave C Done / Gate B final；**不**自行 Ready/Merge。

## 1. 相关 PR

| PR | 主题 | State | Draft | HEAD（记录时） | T01 动作 |
|---|---|---|---|---|---|
| [#35](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/35) | Wave C evidence hardening | OPEN | yes | `fc99ace…` | 保持 Draft |
| [#43](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/43) | EvidenceBundle SQLite read port | OPEN | yes | `097c46b…` | behind=0 + CI 绿；等队长授权 Ready |
| [#45](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/45) | pytest metrics 副作用 | **MERGED** | — | → integration | 已合入 |
| [#47](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/47) | T04 `retrieve_hits` | **MERGED** | — | 2026-08-14 | Gate A 已合入 |
| [#59](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/59) | T04 frozen chunks builder（Gate B1） | OPEN | **yes** | `cf65aa8…` | **Gate B1=PASS**；Gate B final 仍 BLOCKED |

## 2. 语义门

```text
GATE_A=PASS          # #47 MERGED
GATE_B1=PASS         # #59 tip cf65aa8…（请求 SHA 3c7230b… 为其父提交）
GATE_B2=NOT_EXECUTED
GATE_B_FINAL=BLOCKED
Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY
FORMAL_RETRIEVAL_METRICS=NOT_AUTHORIZED
T07_FIVE_REAL_RUNS=NOT_AUTHORIZED
READY_AUTHORIZED=false   # 对 #59 / #35 / #43
MERGE_AUTHORIZED=false
```

## 3. 等待谁

| 人 | 等待事项 |
|---|---|
| `@liuyanbo12` | 审 #43 Ready；受控交付 Q001；#59 不因 B1 签字而自动 Ready |
| `@YHY0728` | Gate B2 / 真实包 loader（未授权前勿 production index） |
| `@myr-111` | 可按 B1 契约准备适配；勿消费测试夹具 / `UNKNOWN` placeholder 作 supports |
