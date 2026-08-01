# T06 任务笔记（Wave A / PR-A）

## 任务目标

为科学多模态产物冻结可消费契约 `MultimodalArtifact`，使 T01 / T02 / T07 / T08
可通过摘要字段接入，而不依赖 T06 内部解析实现。

## 模态选型

| 类别 | 模态 | PR-A 策略 |
|------|------|-----------|
| PDF 表格/图表 | `table` / `chart` | 合成 JSON 夹具证明契约；真实 PDF 提取延后 PR-B |
| CSV/时序 | `timeseries` | 小体积 CSV + 对应 artifact JSON；清洗算法延后 PR-B |

## 真值与评价方法（PR-A 仅定义，不算最终指标）

- 表格：单元格精确匹配准确率（目标 ≥95%，Wave C 定量验收）。
- 图表：数值相对误差（目标 ≤5%，未达标须 `needs_review`）。
- PR-A 夹具标记 `kind=synthetic`，**不得**当作真实提取结果或正式指标。

## 边界

- 不负责 T04 全局 RAG 存储，不负责 T02 工作流编排。
- 通过 `MultimodalArtifact` / `MultimodalSummary` 交付。
- 不调用云端视觉模型；审计字段仅定义安全骨架。

## 接口冻结

见同目录 `INTERFACE_FREEZE.md`。
