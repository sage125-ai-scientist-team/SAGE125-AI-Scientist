# T06 MultimodalArtifact 契约说明（PR-A）

## 顶层模型：`MultimodalArtifact`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `artifact_id` | `str` | 非空 | 产物唯一 ID |
| `modality` | `table` \| `chart` \| `timeseries` | 枚举 | 模态 |
| `provenance` | `Provenance` | 必填 | 来源路径、类型、页码、可选 bbox |
| `units` | `list[str]` | 默认 `[]` | 单位提示列表 |
| `column_units` | `list[ColumnUnitBinding]` | 默认 `[]` | 列→单位映射；列必须存在于 headers |
| `axes` | `list[AxisSpec]` \| `null` | 可选 | 坐标轴；表格常为 null |
| `legend` | `list[str]` | 默认 `[]` | 图例 |
| `data` | `TableData` | 必填 | `headers` + `rows`（单元格为字符串） |
| `confidence` | `float` | `[0, 1]` | 提取置信度 |
| `validation_status` | `passed` \| `needs_review` \| `failed` \| `pending` | 枚举 | 校验状态 |

所有模型 `extra="forbid"`：未声明字段一律拒绝。

## 关键拒绝规则

1. 行宽 ≠ 表头列数 → `ValidationError`（含行号、预期/实际列数）。
2. 完全相同的重复 headers → `ValidationError`。
3. `provenance` 缺失或 `source_path` 空白 → `ValidationError`。
4. `confidence` 越界 → `ValidationError`。
5. 额外未知字段 → `ValidationError`。
6. `column_units.column` 不在 headers → `ValidationError`。

## 下游摘要：`MultimodalSummary` / `to_consumer_summary`

保留：`source_path`、`source_type`、`page`、`units`、`column_units`、`confidence`、`validation_status`、行列计数。
不包含完整 `data` 行，避免大对象进入 prompt。

## detect / queue / adapter 边界

| 组件 | 路径 | PR-A 行为 |
|------|------|-----------|
| detect | `app/multimodal/detect.py` | 扩展名/hint 识别；未知扩展名报错 |
| queue | `app/multimodal/queue.py` | 仅接受通过契约且非 `failed` 的产物 |
| adapters | `app/multimodal/adapters.py` | 抽象接口；`process()` 为 `NotImplementedError` |
| audit | `app/multimodal/audit.py` | 审计字段骨架；禁止敏感标记 |

## 下游消费方式

- **T01**：可将摘要中的来源/页码/置信度写入证据侧字段（联调在 PR-B）。
- **T02**：消费摘要与 `validation_status`，避免整表进入 revision prompt。
- **T07**：批量任务按 `artifact_id` 挂载产物引用。
- **T08**：UI 展示缩略信息与单位/置信度（完整面板在后续 Wave）。

## 安全审计

- 不写 API Key、不写完整 prompt/response。
- `VisionCallAuditStub.key_masked` 恒为 `True`。
- 夹具为合成数据，不含个人隐私。

## 明确未实现（非本 PR 范围）

- 真实 PDF 表格/图表提取、OCR、曲线读数。
- CSV 缺失/异常清洗算法与单位换算。
- Qwen 视觉真实调用与成本审计落地。
- 与 T01/T04 EvidenceCard 索引联调、正式准确率评测。
