# T01 Owner 状态板（2026-08-12）

只读状态汇总；**不**授权 Ready/Merge；**不**宣称正式指标。

## 1. 相关 PR

| PR | 主题 | State | Draft | HEAD（记录时） | T01 动作 |
|---|---|---|---|---|---|
| [#35](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/35) | Wave C evidence hardening | OPEN | yes | `e7e3ed1…` | 保持 Draft；等队长 + 门 B |
| [#43](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/43) | EvidenceBundle SQLite read port（T08） | OPEN | yes | `b5a9e51…` | 等队长审核 |
| [#45](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/45) | pytest 不写坏 tracked metrics（#44） | OPEN | **no** | `20341f1…` | 已 Ready for review；等队长 |
| [#47](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/47) | T04 `retrieve_hits` | OPEN | yes | `f77959b…` | **Gate A=PASS**（T01 已签字） |

## 2. 语义门

```text
GATE_A=PASS   PR=#47 HEAD=f77959b43f7f520119070181011e0d0713425cdd
GATE_B=WAIT   Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY
FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false
T07_REAL_RUN_STATUS=HOLD
READY_AUTHORIZED=false   # 对 #35 / #47
MERGE_AUTHORIZED=false
```

## 3. T01 已做 / 未做

| 项 | 状态 |
|---|---|
| Gate A 审查 + #47/#35 回帖 | 已做 |
| 门 A/B 清单与 T07 适配说明文档 | 已做（本轮） |
| 改 `app/rag/**` / 他任务路径 | **不做** |
| 标记 Ready / Merge | **不做**（无队长授权） |
| 门 B 签字 | **等待** Q001 + T04 loader |

## 4. 等待谁

| 人 | 等待事项 |
|---|---|
| `@liuyanbo12` | 审核 #47 / #45 / #43 / #35；受控交付 Q001 |
| `@YHY0728` | #47 合入后 + Q001 loader/provenance |
| `@myr-111` | 仅消费 T04 manifest + T01 signoff；勿提前五题真跑 |
