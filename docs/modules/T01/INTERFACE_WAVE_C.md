# T01 Wave C 接口文档

本文档描述 Wave C 新增公共函数级接口。每个入口附函数职责、参数语义、返回值与不变量；实现见 `app/evidence/`。  
最终交接总览见 [`handoff.md`](./handoff.md)。  
（说明：环境未挂载 Context7 MCP；本文以仓库内实现与类型注解为准，不引用外部未经验证的 SDK 片段。）

## `run_quality_gate(bundle, status_by_id=None, disposition=KEEP_BOTH_FLAGGED, expected_conflict_claim_ids=None, prior_links=None) -> QualityGateReport`

**职责：** 对 `EvidenceBundle` 执行冲突双侧保留与来源生命周期（撤稿/撤回）质量门。  
**参数：** `bundle` 为待检证据包；`status_by_id` 可选 source 生命周期；`disposition` 仅影响冲突展示策略，**不**放行撤稿 supports；`expected_conflict_claim_ids` / `prior_links` 用于检测静默覆盖。  
**返回：** `QualityGateReport`（冲突两侧 ID、撤稿阻断、占位、`passed`）。  
**不变量：** 冲突两侧不得静默丢弃；**任一 RETRACTED/WITHDRAWN supports → passed=False**（与 disposition 无关）。

## `detect_conflicts_preserving_both_sides(bundle, expected_conflict_claim_ids=None, prior_links=None) -> list[ConflictRecord]`

**职责：** 检测 claim 级冲突并强制两侧 evidence ID 完整。  
**参数：** 可选 `prior_links` / `expected_conflict_claim_ids` 作为“冲突前完整集合”对照。  
**返回：** `ConflictRecord` 列表；若上游丢一侧则 `silently_overwritten=True`。  
**不变量：** 不得把单侧残留冲突伪装成无冲突。

## `ContentHashCache.get_or_compute(quoted_text, hash_fn=...) -> str`

**职责：** 按摘录计算或复用 `content_hash`。  
**参数：** `quoted_text` 原文；`hash_fn` 仅在缓存未命中时调用。  
**返回：** 稳定哈希字符串。  
**不变量：** **命中时不调用 `hash_fn`**（见红灯测试）。

## `deterministic_bundle_digest(bundle) -> str`

**职责：** 计算 Bundle 的确定性 sha256 指纹。  
**参数：** `EvidenceBundle`。  
**返回：** 十六进制 digest。  
**不变量：** 同语义输入排序规范化后 digest 一致。

## `assert_same_input_stable_evidence_set(left, right) -> None`

**职责：** 断言两次构建的证据 ID 集合稳定。  
**参数：** 左右两个 bundle/集合指纹输入。  
**返回：** 无；不一致抛 `AssertionError`。  
**不变量：** 同输入不得出现非确定性丢证。

## `build_output_envelope_v125(bundle, citations, quality, ...) -> dict`

**职责：** 构建可完整 JSON 序列化的 125 输出信封。  
**参数：** bundle、citations、quality_gate 等可序列化片段。  
**返回：** `dict`（bundle + citations + T08 payload + quality_gate）。  
**不变量：** 字段均可 `json` 序列化，无隐藏运行时对象。

## `build_api_example_payload(claim_id, card, support_status) -> dict`

**职责：** 生成最小 T08 API 样例载荷。  
**参数：** claim、卡片、支持状态枚举/字符串。  
**返回：** 示例 `dict`。  
**不变量：** 仅示例用途，不作正式评测金标。

## `dumps_output_envelope(envelope) -> str`

**职责：** 将信封转为确定性 JSON 文本。  
**参数：** `envelope` 映射。  
**返回：** `sort_keys=True` 的 JSON 字符串。  
**不变量：** 相同输入字节级稳定（在默认分隔符下）。

## `build_separated_signoff_package(...)` / `write_separated_signoff_artifacts(...)`

**职责：** 构建并写出“契约回归”与“真实来源人工签字”分离产物。  
**参数：** 可选输出路径；主体 SHA 使用冻结的 `reviewed_subject_sha`。  
**返回：** `SeparatedSignoffPackage` / 写出的文件路径集合。  
**不变量：**

- `reviewed_subject_sha` 冻结被审提交，禁止为追 tip 连续 rebind。
- Q028 contract regression 不得计入真实原文签字样本。
- 真实行仅允许 eval_gold（DOI/URL/仓库路径 + quote 命中 XML）。
- 人工姓名/日期/签字不得自动伪造；artifact commit SHA 只写 PR 评论。

## 边界

- `PAIRING_STRUCTURE=STRUCTURE_OK`
- `ACTUAL_RELEVANCE_GOLD=NOT_READY`
- `FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false`
- 不 Ready / 不 Merge（除非队长明确授权）
