# T09 Evaluation RFC

## 范围

本 RFC 只定义评测合同。结果必须标注 `planned`、`mock` 或 `actual`；Wave A 不运行正式消融，不产生分数。

## 指标

| 指标 | 定义与规则 | 输入/粒度 | 缺失值与 owner |
| --- | --- | --- | --- |
| 引用正确率 | 经人工/规则核验的正确引用数 ÷ 已核验引用数。 | 每引用、每题、全题集。 | 缺失记 `null`，T01/T04 提供证据核验。 |
| 幻觉率 | 无证据支持或与证据冲突的声明数 ÷ 已核验声明数。 | 每声明、每题。 | 缺失记 `null`，T01/T03 提供判定。 |
| 可证伪性 | 满足预注册反证条件的假设数 ÷ 已核验假设数。 | 每假设、每题。 | 缺失记 `null`，T03/T05 提供。 |
| 可执行性 | 具备数据、方法、指标和资源限制的计划数 ÷ 已核验计划数。 | 每计划、每题。 | 缺失记 `null`，T05 提供。 |
| 迭代提升 | 修订后减修订前的同协议指标；无共同输入则不可计算。 | 每题、每轮。 | 缺失记 `null`，T02/T03 提供 lineage。 |
| 延迟 | 单次运行 wall-clock 毫秒。 | 每运行及分位数。 | planned/mock 不得冒充实际，T07/T08 提供。 |
| token | 脱敏调用审计的输入/输出/总 token。 | 每运行、每模型。 | 缺失记 `null`，T07/T08 提供。 |
| 成本 | 同一版本价格表下的 token × 单价。 | 每运行、每题集。 | 无价格表记 `null`，T07 提供。 |
| 通过率 | 通过全部质量门的运行数 ÷ 已完成运行数。 | 每题集。 | 未完成不进入分母，T03/T09 提供。 |
| 稳定性 | 同输入、同 seed 重复运行的通过率及指标离散度。 | 每配置、每题集。 | 少于三次记 `null`，T09 汇总。 |

## 结果格式与消融

每个结果 JSON 必须包含 `run_id`、`variant`、`mode`、`seed`、`input_manifest`、`status`、`metrics`、`artifacts`。CSV 使用同名扁平字段。固定变体为 `no-RAG`、`no-reviewer`、`no-HITL`、`single-agent`、`full-system`，必须共享同一输入 manifest、随机种子协议和评分规则。

`scripts/eval/benchmark_skeleton.py --dry-run` 只写入五个 `planned` 变体及 JSON/CSV schema；其中不存在分数、延迟、token 或成本值。
