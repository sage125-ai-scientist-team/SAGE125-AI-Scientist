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

## PR-B / PR #36 phase-1 fix

- Real PDF table/chart extraction via PyMuPDF (`pdf_io.py`).
- JSON packets require explicit `input_kind`.
- Chart metric: relative error ≤5% with declared zero absolute tolerance.
- Evidence live index/consume via T01 `EvidenceBundle` contracts.
- Qwen vision path implemented; phase-1 does not perform paid calls while PR #29 unmerged.
