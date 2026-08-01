# T02 Reviewer 自动修订契约

## 1. 范围与术语

本文定义 Reviewer 驱动的两轮自动修订最小契约。它约束
`HypothesisGeneratorAgent`、`ExperimentDesignerAgent`、`ScientificReviewerAgent`
之间的输入、阻断、迭代和可测试证据，不在本阶段规定生产代码的具体实现方式。

- 第一轮：Reviewer 尚未给出反馈的初始生成轮。
- 第二轮：首轮 Reviewer 判定存在阻断意见后执行的修订轮。
- 有效修订：Reviewer 反馈真实进入下一轮，语义迭代递增，实质输入发生可解释变化。
- 假迭代：控制流重复执行，但 Reviewer 反馈未进入下一轮，或两轮实质输入相同。

当前最小范围保持最多两轮。全局流水线 `step_index` 是执行顺序，不是语义迭代。

## 2. ReviewResult 反馈载体

下一轮 HypothesisGenerator 和 ExperimentDesigner 必须收到完整的首轮
`ReviewResult`，统一输入键名为：

```python
input_data["review_result"]
```

该对象必须原样保留真实 `ReviewResult` 字段：

```text
critical_issues
required_revisions
reviewer_comments
```

不存在 `comments` 字段；契约和测试均不得创建该别名。

当前 `ReviewResult` 没有目标 Agent 标签，无法可靠判断某条意见仅属于假设或仅属于
实验。因此不得猜测性拆分反馈：三个字段必须完整传给下一轮 HypothesisGenerator
和 ExperimentDesigner。

HypothesisGenerator 必须能用反馈修订假设、机制和可证伪预测；ExperimentDesigner
必须能用同一反馈修订数据集、基线、指标、消融和验证协议。

## 3. revision_iteration 权威位置

语义迭代的权威位置确定为：

```python
input_data["revision_iteration"]
```

规则：

| Agent | 第一轮 | 第二轮 |
|---|---:|---:|
| HypothesisGenerator | `revision_iteration=1` | `revision_iteration=2` |
| ExperimentDesigner | `revision_iteration=1` | `revision_iteration=2` |

`step_index` 不得替代 `revision_iteration`。AgentTrace可以保存该信息作为辅助证据，
但输入字段是本契约的权威位置。

`revision_iteration` 必须是确定性业务字段，不得使用随机值、UUID或时间戳模拟版本
变化。

## 4. 有效通过与阻断谓词

只有同时满足以下条件，Reviewer结果才构成有效通过：

```text
passed is True
critical_issues == []
required_revisions == []
```

以下任一条件成立，都构成阻断并要求修订：

```text
passed is False
critical_issues 非空
required_revisions 非空
```

`reviewer_comments` 单独非空时只作为上下文，不单独触发修订。

如果出现 `passed=True`，但 `critical_issues` 或 `required_revisions` 非空，
pipeline仍必须按阻断处理，不能仅相信 `passed` 并提前停止。该规则是pipeline的
防御性契约；本阶段不要求Pydantic直接拒绝构造这种 `ReviewResult`。

## 5. 完整输入指纹

测试必须捕获 Agent 实际收到的完整 `input_data`，按以下方式规范化：

```python
json.dumps(
    value,
    sort_keys=True,
    ensure_ascii=False,
    default=str,
)
```

随后对规范化字符串计算SHA-256。

存在实质Reviewer反馈时，同一Agent第一轮和第二轮的完整输入指纹必须不同。差异必须
来自以下确定性业务内容：

- `review_result`
- `revision_iteration`

不得使用随机值、UUID或时间戳制造差异。

当前生产端 `prompt_hash` 基于最多600字符的 `input_summary`，不能覆盖完整实际消息，
因此只能作为辅助证据，不能作为本契约的唯一输入指纹。

对重写了 `build_messages()` 的 Agent，还必须检查最终user消息。仅在pipeline字典中
出现反馈、但被 `build_messages()` 丢弃，不构成反馈已进入真实调用。

## 6. 假迭代判定

以下任一情况意味着第二次调用不能被认定为有效修订：

- 首轮 Reviewer 的三个反馈字段没有进入下一轮；
- 同一 Agent 两轮实质输入相同；
- 仅 `revision_history` 增加，但生成输入没有变化；
- mock Reviewer 仅因 `revision_history` 非空而从失败改为通过；
- 仅能证明pipeline执行了第二次，不能证明反馈被消费。

当检测到相同输入时，不得把该调用计作成功修订，也不得据此宣称Reviewer问题已经
解决。

## 7. 最大轮次与终态

当前最小契约允许最多两轮。

第二轮 Reviewer 仍返回阻断意见时：

- 不得宣称无问题完成；
- 最终状态不得为 `ready_for_validation` 或 `validated`；
- 必须保留未解决的 `critical_issues`、`required_revisions` 和
  `reviewer_comments`。

当前生产接口没有明确的 `stop_reason` 字段。增加明确停止原因属于后续生产实现要求；
本契约不声称该字段已经存在。

## 8. 可测试证据

一次有效修订至少需要以下证据：

1. 两次 HypothesisGenerator 输入均被捕获；
2. 两次 ExperimentDesigner 输入均被捕获；
3. 第二轮输入包含首轮完整 `review_result`；
4. 两个 Agent 分别观察到 `[1, 2]` 的 `revision_iteration`；
5. 两轮完整输入指纹不同；
6. ExperimentDesigner最终user消息包含三个Reviewer字段；
7. 非空阻断字段不会导致第一轮提前停止；
8. 相同输入、历史增加、mock转为通过的组合不能被认定为成功修订。

## 9. A–F 验收映射

| 契约编号 | 测试名称 | 当前预期状态 | 后续转绿条件 |
|---|---|---|---|
| A | `test_review_feedback_enters_second_hypothesis_input` | RED：第二轮缺少 `review_result` 和 `revision_iteration` | 第二轮输入携带首轮完整ReviewResult且iteration为2 |
| B | `test_review_feedback_enters_second_experiment_input` | RED：pipeline输入和最终user消息均无Reviewer反馈 | 第二轮输入及 `build_messages()` user消息都包含三个字段 |
| C | `test_revision_iteration_increments_from_one_to_two` | RED：两个Agent均不存在 `revision_iteration` | 两个Agent分别观察到 `[1, 2]` |
| D | `test_feedback_changes_second_round_input_fingerprint` | RED：HypothesisGenerator两轮完整输入相同 | 注入反馈与iteration后完整输入指纹不同 |
| E | `test_required_revisions_prevent_early_stop` | RED：停止条件只检查 `passed` | 非空 `required_revisions` 强制进入第二轮 |
| F | `test_identical_prompt_hash_cannot_count_as_successful_revision` | RED：相同输入仍增加历史并被mock判为通过 | 输入发生实质变化，或相同输入不再被认定为成功修订 |

防御性一致性测试
`test_passed_review_with_blocking_revisions_is_not_effectively_passing`
补充验证pipeline最终状态不得保留“有效通过但仍有阻断修订”的矛盾组合。

## 10. 生产契约落点与边界

正式状态对象、确定性 Prompt Builder、PlanVersion 存储、兼容迁移、序列化往返和
IssueClosure 已落在 `app/contracts/revision.py`，权威生产说明见
`docs/contracts/T02.md`。`app/workflow/pipeline.py` 使用这些正式对象构造真实输入，
并保持最多两轮及阻断终态规则。

本阶段不修改公共 `ReviewResult` 或 `PipelineState` schema，不实现超过两轮的通用
循环，也不擅自增加公共 `stop_reason` 字段。
