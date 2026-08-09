# T01 Wave C 接口文档

本文档描述 Wave C 新增公共函数级接口。注释密度按函数说明维护；实现见 `app/evidence/`。

## `run_quality_gate(bundle, status_by_id=None, disposition=KEEP_BOTH_FLAGGED, expected_conflict_claim_ids=None, prior_links=None) -> QualityGateReport`

运行冲突保留 + 撤稿占位质量门。

- 输入：`EvidenceBundle`；可选来源生命周期映射；可选 `expected_conflict_claim_ids` / `prior_links`。
- 输出：`QualityGateReport`（冲突两侧 ID、撤稿阻断列表、占位列表、passed）。
- 不变量：冲突两侧不得静默丢弃；**任一 RETRACTED/WITHDRAWN supports → passed=False**（与 disposition 无关）。

## `detect_conflicts_preserving_both_sides(bundle, expected_conflict_claim_ids=None, prior_links=None) -> list[ConflictRecord]`

检测冲突并强制两侧 ID 完整；可通过 `prior_links` / `expected_conflict_claim_ids` 发现上游静默丢一侧（`silently_overwritten=True`）。

## `ContentHashCache.get_or_compute(quoted_text, hash_fn=...) -> str`

按摘录计算/复用 content_hash；**命中时不调用 `hash_fn`**。

## `deterministic_bundle_digest(bundle) -> str`

Bundle 确定性 sha256 指纹。

## `assert_same_input_stable_evidence_set(left, right) -> None`

同输入证据集合不一致时抛 `AssertionError`。

## `build_output_envelope_v125(bundle, citations, quality, ...) -> dict`

构建可完整 JSON 序列化的 125 输出信封（bundle + citations + T08 payload + quality_gate）。

## `build_api_example_payload(claim_id, card, support_status) -> dict`

最小 T08 API 样例。

## `dumps_output_envelope(envelope) -> str`

`sort_keys=True` 的确定性 JSON 文本。

## `write_separated_signoff_artifacts(...)`

写出契约回归报告与真实来源人工签字表（分离）。

- `reviewed_subject_sha` 冻结被审提交，禁止为追 tip 连续 rebind。
- Q028 contract regression 不得计入真实原文签字样本。
- 真实行仅允许 eval_gold（DOI/URL/仓库路径 + quote 命中 XML）。
- 人工姓名/日期/签字不得自动生成；artifact commit SHA 只写 PR 评论。

## 边界

- `PAIRING_STRUCTURE=STRUCTURE_OK`
- `ACTUAL_RELEVANCE_GOLD=NOT_READY`
- `FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false`
- 不 Ready / 不 Merge（除非队长明确授权）
