# Migration or Configuration Example

T02 Code Freeze 不需要数据迁移、环境变量变更或配置迁移。

- `app/contracts/revision.py` 的冻结公共接口未修改。
- 现有 `RevisionContext`、`ReviewFeedback`、`PlanVersion` 和 `IssueClosure`
  调用保持兼容。
- 未提供 `ExecutionResult` 和 multimodal artifact 时，既有 Wave A/B 输入形状
  保持不变。
- 提供 Wave C 证据时，生产 builder 要求 execution 与 multimodal summary
  同时完整存在；部分输入会明确失败。

因此部署方无需新增配置文件。升级步骤仅为部署通过 PR #37 审核后的代码版本，
并沿用现有环境配置。
