# T06 接口冻结记录（PR-A）

- **冻结日期**：2026-07-30
- **分支**：`t06/a-multimodal-contract`
- **契约模块**：`app/contracts/multimodal.py`
- **冻结符号**：
  - `BoundingBox`, `Provenance`, `AxisSpec`, `ColumnUnitBinding`, `TableData`
  - `MultimodalArtifact`, `MultimodalSummary`, `to_consumer_summary`
  - `Modality`, `ValidationStatus`, `ProvenanceSourceType`
- **兼容承诺（PR-A）**：
  - 不得静默删除/重命名上述公共字段；
  - 新增字段须有默认值或明确版本说明；
  - `extra="forbid"` 行为保持。
- **允许后续扩展（需在 PR-B/C 文档说明）**：
  - 适配器真实实现、审计落盘、跨模块映射辅助函数。

## PR-B 扩展说明（不破坏冻结字段）

- 未修改 `app/contracts/multimodal.py` 公共字段集合与 `extra="forbid"`。
- Wave B 新增实现位于 `app/multimodal/**`：`table_extract` / `chart_extract` / `timeseries_extract` / `evidence_bridge` / `workflow_hook` / `eval_metrics`。
- `VisionCallAudit` 扩展审计字段；保留 `VisionCallAuditStub` 兼容别名。
- EvidenceCard 通过消费 integration 既有 `EvidenceCardContract` 完成桥接，不改 T01 owner 路径。

破坏性变更须经队长确认，不得在队员 PR 中悄悄改写。
