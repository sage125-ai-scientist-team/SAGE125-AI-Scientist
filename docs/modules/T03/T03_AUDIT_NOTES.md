# T03 Wave A 基线审计与失败复现

审计日期：2026-07-30

基线分支：`upstream/integration/2026-08-10`

基线提交：`c8229de`（`[T02-A] Define reviewer revision contract (#10)`）

工作分支：`t03/a-validation-contract`

## 1. 审计范围

本次审计只读取既有实现，并将新增内容限制在 T03 owner 路径：

- `app/feedback/**`
- `app/validation/**`
- `app/quality/**`
- `app/contracts/validation.py`
- `tests/validation/**`
- `docs/modules/T03/**`

没有修改 `app/workflow/pipeline.py` 或 `app/api/routes.py`。

## 2. 已复现的旧链路问题

### 2.1 人工反馈只写历史，没有进入下一轮输入

既有 `revise_with_feedback` 将原始字符串追加到：

- `PipelineState.reviewer_feedback`
- `revision_history` 中截断为 80 字符的说明

随后重跑 `HypothesisGeneratorAgent` 时，输入只包含：

- `question_item`
- `evidence_catalog`
- `evidence_extraction`

输入中没有稳定的 `feedback_id`、决策状态、接受指令或目标版本。因此现有历史记录
不能证明反馈已影响下一轮 Prompt。

复现命令：

```powershell
rg -n -C 12 "state.reviewer_feedback.append|HypothesisGeneratorAgent.settings..run" app/workflow/pipeline.py
```

机器可读失败样例：
`examples/baseline.feedback_not_propagated.json`。

### 2.2 SchemaValidator 只接收 question_item

生产调用仍为：

```python
SchemaValidatorAgent(settings).run({"question_item": qdict}, state, step)
```

它没有通过一个冻结的输入边界同时接收：

- ResearchPlan
- EvidenceCards
- AgentTrace
- execution_metadata
- question_item

复现命令：

```powershell
rg -n -C 5 "SchemaValidatorAgent.settings..run" app/workflow/pipeline.py
```

机器可读失败样例：
`examples/baseline.validator_question_only.json`。

### 2.3 现有质量门缺少统一严重级别与关闭状态

`app/workflow/quality_gates.py` 当前返回：

```json
{
  "passed": false,
  "errors": [],
  "warnings": [],
  "score": 0.0
}
```

该结构没有稳定 finding code、P0-P3 severity、issue closure 或 lineage。因此调用方
不能仅凭旧字典可靠判断“P0/P1 是否已关闭”。

### 2.4 旧 feedback API 缺少审计身份

现有请求仅包含 `{ "feedback": "..." }`，缺少：

- `feedback_id`
- `target_version_id`
- `correlation_id`
- request fingerprint
- 决策与拒绝理由
- resulting version identity

Wave A 只冻结领域契约和接口；API 路由改造、鉴权、长度限制、幂等与并发控制属于
Wave B。

## 3. Validator 输入矩阵

| 产物 | 当前生产调用 | T03 v1 契约 | 缺失时策略 |
| --- | --- | --- | --- |
| ResearchPlan | 未传给 SchemaValidatorAgent | `research_plan`，必填 | 构造上下文失败或 presence gate 阻断 |
| EvidenceCards | 质量门单独读取 | `evidence_cards`，必填 | 空集合由 presence/evidence gate 判定 |
| AgentTrace | 质量门单独读取 | `agent_trace`，必填 | 空集合由 presence/model gate 判定 |
| execution_metadata | 未独立传入 Validator | `execution_metadata`，必填 | 缺少 `actual_execution` 时 fail closed |
| question_item | 已传入 | `question_item`，必填 | 缺失或与报告不一致时 fail closed |
| T02 issues | 未统一传入 | `revision_issues` sidecar | 未关闭 P0/P1 阻断 |
| 人工反馈 | 只写字符串历史 | `human_feedback` directive | 只允许 accepted 指令进入 Prompt |

“字段必填”和“集合非空”是两件事。`ValidationContext` 要求五项字段均存在；空证据或
空 trace 仍需进入质量门，输出结构化失败，而不是在调用层被悄悄丢弃。

## 4. 红灯测试证据

测试先于实现创建。第一次运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/validation/test_validation_contract.py -q
```

稳定失败于测试收集阶段：

```text
ModuleNotFoundError: No module named 'app.contracts.validation'
1 error
```

实现契约、端口和示例后：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/validation -q -W error
```

结果：

```text
42 passed in 0.16s
```

测试不依赖私有 `questions_125.json`，没有 `skip` 或 `xfail`。

T02 契约、现有反馈链路和 T03 模块联合回归：

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/workflow/test_revision_contract.py `
  tests/workflow/test_pipeline_reviewer_revision_contract.py `
  tests/test_schema.py `
  tests/test_quality_gate_evidence_links.py `
  tests/test_pipeline_feedback_revision.py `
  tests/validation -q
```

结果：

```text
66 passed, 3 skipped
```

其中 3 项均为既有测试因本地缺少私有 `questions_125.json` 而跳过；T03 新测试没有
跳过。

全仓回归：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：

```text
331 passed, 35 skipped
```

35 项跳过均来自既有测试缺少私有 `questions_125.json` 或未分发的
`data/raw/sjtu-booklet.pdf`，没有测试失败。

独立边界审查曾复现 `frozen=True` 的浅冻结可被 list/dict 原地突变，从而在验证后
注入 P0、篡改上下文或改写审计事件。最终实现将所有关键序列冻结为 tuple，将所有
JSON object 递归冻结为可安全深拷贝的 `FrozenDict`，并新增 mutation regression。
复审未发现剩余 P0/P1。

## 5. 兼容结论

- T02 已拥有 `RevisionContext`、`ReviewFeedback`、`IssueClosure` 与
  `PlanVersion`。T03 不重复定义或向其 `extra="forbid"` 模型添加字段。
- T03 以 sidecar 方式通过 canonical version ID（`<run_id>:vN`）关联 T02。
- `HumanFeedbackDirective` 是预留给 T02 Prompt Builder 的稳定边界，键名建议固定为
  `human_feedback`。
- 拒绝的原始片段只留在 `FeedbackDecision` 和 audit lineage；不会进入 directive。
- T08 的 `job_id` 不是 T02/T03 `run_id`，由 T08 通过 `upstream_run_id` 映射。

## 6. Wave B 前仍存在的已知缺口

- 尚未把 `HumanFeedbackDirective` 接入生产 Prompt Builder。
- 尚未实现持久化、幂等、权限、长度限制和并发写入。
- 尚未把完整 `ValidationContext` 接入 SchemaValidator/质量门。
- 尚未实现 P0/P1 Gate 聚合、指标和 API 错误码。
- 尚未迁移旧 `reviewer_feedback: list[str]`；旧记录只能标为
  `legacy_unverified`，不能默认视为 accepted。
