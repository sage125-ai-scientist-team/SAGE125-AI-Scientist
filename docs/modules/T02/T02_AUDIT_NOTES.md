# T02 工作流迭代契约审计记录

## 审计元信息

- 审计日期：2026-07-27
- 材料整理日期：2026-07-29
- 分支：`t02/a-revision-contract`
- 基线：`integration/2026-08-10`
- 审计时 `HEAD` 与本地、`origin`、`upstream` 的该基线引用：`1642ea05e88b853f18d24739d9d2134c3448eb7b`
- 工作方式：静态代码检查，加一次不写仓库、禁用字节码写入的纯内存 mock 最小复现
- 规则文件：仓库根目录、隐藏目录及适用子目录均未发现 `AGENTS.md`
- 安全边界：未读取或输出 `.env`、API Key；未调用真实模型

## 调查范围

已实际检查：

- `app/workflow/**`
- `app/workflow/pipeline.py`
- `app/agents/hypothesis_generator.py` 中的 `HypothesisGeneratorAgent`
- `app/agents/experiment_designer.py` 中的 `ExperimentDesignerAgent`
- `app/agents/scientific_reviewer.py` 中的 `ScientificReviewerAgent`
- `app/agents/base.py` 中的 `BaseAgent`
- `app/core/schemas.py` 中的 `PipelineState`
- `app/core/agent_schemas.py` 中的 `AgentTraceEvent`、`ReviewResult`
- 与 pipeline、Agent trace、反馈修订相关的 `tests/test_*.py`

仓库中不存在 `tests/workflow/`；工作流相关测试平铺在 `tests/`。检索词包括：

`critical_issues`、`required_revisions`、`comments`、`prompt_hash`、`version`、
`iteration`、`max_iterations`、`stop`、`retry`。

## 真实代码调用链

主流程位于 `app.workflow.pipeline._run_pipeline_with_state_impl()`：

1. `HypothesisGeneratorAgent.run()`
   输入由 `question_item`、`evidence_catalog`、`evidence_extraction` 构成
   证据：`app/workflow/pipeline.py:498-509`
2. `_experiment_designer_input()` → `ExperimentDesignerAgent.run()`
   输入包含最新假设、问题类型与证据上下文
   证据：`app/workflow/pipeline.py:241-260,525-529`
3. `_reviewer_input()` → `ScientificReviewerAgent.run()`
   输入包含假设、实验设计与证据上下文
   证据：`app/workflow/pipeline.py:263-281,531-534`
4. 若 Reviewer 未通过、启用自动修订且 `revision_history` 为空，则追加
   `auto_revision_1` 文本，再按“假设 → 实验 → Reviewer”重跑一次
   证据：`app/workflow/pipeline.py:535-555`
5. 第二次 Reviewer 完成后无再次判断，直接进入 `ReportWriterAgent`
   证据：`app/workflow/pipeline.py:557-578`

## 第一轮中间产物保存位置

| 产物 | 第一轮运行时位置 | 第二轮行为 | 最终持久化情况 |
|---|---|---|---|
| 假设完整结果 | 局部变量 `hyp_result`；`PipelineState.hypothesis_generation` | 两者均被第二轮覆盖 | `pipeline_state.json.hypothesis_generation` 只含最新轮 |
| 假设规范化列表 | `PipelineState.hypotheses` | 第二轮未重建该字段 | 可能作为首轮陈旧副本进入 `pipeline_state.json` |
| 实验方案完整结果 | 局部变量 `exp_result`；`PipelineState.experiment_design` | 两者均被第二轮覆盖 | 只持久化最新轮完整结果 |
| Reviewer 完整结果 | 局部变量 `review`；`PipelineState.review_result` | 两者均被第二轮覆盖 | 只持久化最新轮完整结果 |
| 各轮执行摘要 | `PipelineState.agent_trace[*].output_summary` | 每次调用追加事件 | 两轮摘要可进入 `agent_trace.json`，但每条最多 600 字符 |

字段定义证据：

- `PipelineState.hypotheses`：`app/core/schemas.py:270-273`
- `PipelineState.hypothesis_generation`：`app/core/schemas.py:294-295`
- `PipelineState.experiment_design`：`app/core/schemas.py:296-297`
- `PipelineState.review_result`：`app/core/schemas.py:298-299`
- `AgentTraceEvent.output_summary` 上限：`app/core/agent_schemas.py:62-64`
- 完整状态落盘：`app/workflow/artifacts.py:147-148`

首轮假设在 `app/workflow/pipeline.py:510-523` 被复制到 `state.hypotheses`；第二轮
`app/workflow/pipeline.py:538-548` 只更新 `state.hypothesis_generation`，没有同步
更新 `state.hypotheses`。这是一个可观察的状态一致性缺口。

## Reviewer 反馈是否进入下一轮

`ReviewResult` 的真实反馈字段为：

- `reviewer_comments`
- `critical_issues`
- `required_revisions`

证据：`app/core/agent_schemas.py:248-260`。

| Reviewer 字段 | 第二轮 `HypothesisGeneratorAgent` | 第二轮 `ExperimentDesignerAgent` |
|---|---|---|
| `critical_issues` | 未传入 | 未传入 |
| `required_revisions` | 未传入 | 未传入 |
| `reviewer_comments` | 未传入 | 未传入 |
| 整体 `review_result` | 未传入 | 未传入 |

第二轮 HypothesisGenerator 的实际输入仍只有：

```text
question_item
evidence_catalog
evidence_extraction
```

证据：`app/workflow/pipeline.py:538-543`。

`_experiment_designer_input()` 也没有任何 Reviewer 字段；其返回字段见
`app/workflow/pipeline.py:252-260`。`ExperimentDesignerAgent.build_messages()` 发送给
LLM 的 payload 同样没有 Reviewer 字段，见
`app/agents/experiment_designer.py:35-55`。

结论：Reviewer 结果被保存到 `state.review_result`，但没有形成下一轮生成契约。

## `prompt_hash` 的计算、保存和比较

计算流程：

1. `BaseAgent.safe_summarize_input()` 将 `input_data` JSON 化、脱敏并截断到 600 字符
   证据：`app/agents/base.py:166-182`
2. `BaseAgent.hash_prompt()` 对
   `model_name | system_prompt | input_summary` 做 SHA-256，只保留前 12 位
   证据：`app/agents/base.py:314-327`
3. `BaseAgent.run()` 在调用前计算 hash，并在 `finally` 中写入 trace
   证据：`app/agents/base.py:471-474,549-563`

保存位置：

- `AgentTraceEvent.prompt_hash`
- `PipelineState.agent_trace`
- `exports/{run_id}/agent_trace.json`
- `exports/{run_id}/pipeline_state.json`
- `context_pack.json.prompt_hashes`

`ContextBuilder.build_context_pack()` 使用
`{agent_name: prompt_hash}` 字典推导式；同名 Agent 运行两次时，后轮 hash 覆盖前轮
hash。证据：`app/workflow/context_builder.py:136-152`。

比较情况：

- 工作流中没有比较第一轮与第二轮 `prompt_hash`
- 没有“相同则拒绝计为新版本”的判断
- `tests/test_agent_trace.py:46-52` 只验证 hash 非空，不验证两轮不同

限制：该 hash 基于截断的输入摘要，而不是 `build_messages()` 产生的完整实际消息；
600 字符之后的差异不会改变 hash。对重写了 `build_messages()` 的 Agent，hash 内容
还可能包含实际未发送的输入字段。

## 版本是否真正递增

没有。

主自动修订路径中不存在 `version`、`iteration`、`max_iterations` 字段，也没有
V1/V2 产物。唯一的修订标记是：

```text
auto_revision_1: 依据评审意见重做假设与实验设计。
```

证据：`app/workflow/pipeline.py:535-537`。

`revise_with_feedback()` 是另一条独立路径，会将报告写入
`revisions/{revision_id}/report.json`，但 `revision_id` 是新的 run-style ID，不是
递增的 V1/V2 版本号。证据：`app/workflow/pipeline.py:725-839`。

## 当前停止与重试条件

自动修订触发条件是：

```python
not review.get("passed")
and reviewer_auto_revision
and not state.revision_history
```

证据：`app/workflow/pipeline.py:535`。

当前实际语义：

- 首轮通过：不重试
- 首轮失败但关闭 `reviewer_auto_revision`：不重试
- 首轮失败且已有 `revision_history`：不重试
- 首轮失败、启用自动修订且历史为空：固定重跑一次
- 第二轮无论通过或失败：停止修订并进入报告阶段

这不是循环；没有 `max_iterations`，没有第二轮失败后的重试，也没有“输入或版本未
变化则停止并报错”的条件。

## 已确认问题

1. **Reviewer 反馈丢失**：三个反馈字段均未进入第二轮 HypothesisGenerator 或
   ExperimentDesigner。
2. **存在假迭代**：第二轮可以在输入、输出及 hash 均不变时被计作自动修订。
3. **首轮完整产物被覆盖**：假设、实验和 Reviewer 没有轮次化完整快照。
4. **状态字段不一致**：第二轮更新 `hypothesis_generation`，但不更新
   `state.hypotheses`。
5. **没有真实 V1→V2**：只有一条 `revision_history` 文本。
6. **停止条件固定为一次重跑**：第二轮 Reviewer 失败也会继续生成报告。
7. **hash 不参与契约判断**：只记录，不比较；上下文包还会折叠同名 Agent 的多轮
   hash。
8. **mock 可制造“无变化但通过”**：`ScientificReviewerAgent.build_mock()` 在
   `state.revision_history` 非空后直接返回通过结果，见
   `app/agents/scientific_reviewer.py:57-68`。
9. **现有测试缺少行为断言**：没有测试要求 Reviewer 字段进入下一轮、两轮 prompt
   不同或版本递增。

## 尚未确认问题

以下事项未运行或缺乏现成样本，因此不作事实断言：

- 真实 Qwen 模式下重复生成完全相同文本的发生频率
- 真实生产 artifacts 中首轮摘要被 600 字符截断后损失的具体比例
- 第二轮 Reviewer 仍失败时，前端是否会向用户明确展示“自动修订失败”
- 在并发运行或异常恢复场景中，陈旧 `state.hypotheses` 对下游的实际影响
- 真实调用中不同完整 prompt 因前 600 字符相同而产生相同 hash 的实际样本数

## 2026-07-28 应建立的红灯测试

以下测试应先以当前实现失败为验收基线；本次仅记录，不实现：

1. `test_failed_review_fields_enter_second_hypothesis_input`
   spy 第二次 `HypothesisGeneratorAgent.run()`，断言输入包含
   `critical_issues`、`required_revisions`、`reviewer_comments` 及稳定 issue ID。
2. `test_failed_review_fields_enter_second_experiment_input`
   断言 ExperimentDesigner 第二轮收到结构化 Reviewer 修订合同。
3. `test_second_round_prompt_differs_from_first_round`
   断言真实 `build_messages()` 输出不同，而不只是摘要 hash 不同。
4. `test_identical_prompt_cannot_count_as_revision`
   两轮消息相同时，工作流不得记录新版本或把第二轮视为成功修订。
5. `test_revision_versions_increment_v1_to_v2`
   断言假设、实验、Reviewer 产物具有显式 `version`/`iteration`，并由 V1 递增到 V2。
6. `test_first_round_artifacts_remain_addressable_after_revision`
   断言 V1 完整假设、实验和 Reviewer 结果不会被覆盖。
7. `test_pipeline_state_hypotheses_matches_latest_generation`
   断言 `state.hypotheses` 与最新 `state.hypothesis_generation` 一致。
8. `test_second_review_failure_has_explicit_stop_reason`
   断言达到最大轮次且仍失败时保存明确 `stop_reason`，不得静默进入报告。
9. `test_trace_preserves_hash_per_iteration`
   断言 context pack 不以 Agent 名称折叠多轮 hash，并保存轮次与版本。
10. `test_prompt_hash_covers_actual_full_messages`
    断言 hash 基于完整 `build_messages()` 结果，不受 600 字符摘要截断影响。
