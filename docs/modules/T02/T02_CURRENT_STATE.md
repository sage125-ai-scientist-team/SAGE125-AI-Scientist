# T02 当前工作流状态与数据流

## 当前状态机

```mermaid
stateDiagram-v2
    [*] --> HypothesisV1
    HypothesisV1: "HypothesisGenerator 第1轮"
    HypothesisV1 --> ExperimentV1
    ExperimentV1: "ExperimentDesigner 第1轮"
    ExperimentV1 --> ReviewerV1
    ReviewerV1: "ScientificReviewer 第1轮"

    ReviewerV1 --> Report: "passed=true"
    ReviewerV1 --> Report: "reviewer_auto_revision=false"
    ReviewerV1 --> Report: "revision_history 非空"
    ReviewerV1 --> RevisionMarker: "passed=false 且允许修订且历史为空"

    RevisionMarker: "追加 auto_revision_1 文本\n无 version/iteration 字段"
    RevisionMarker --> HypothesisV2
    HypothesisV2: "HypothesisGenerator 第2次调用\n覆盖 hypothesis_generation"
    HypothesisV2 --> ExperimentV2
    ExperimentV2: "ExperimentDesigner 第2次调用\n覆盖 experiment_design"
    ExperimentV2 --> ReviewerV2
    ReviewerV2: "ScientificReviewer 第2次调用\n覆盖 review_result"
    ReviewerV2 --> Report: "无条件继续；不再判断 passed"

    Report: "ReportWriter / Quality Gates / Artifacts"
    Report --> [*]

    note right of RevisionMarker
        这不是 V1→V2 版本递增；
        只是 revision_history 增加一条字符串。
    end note

    note right of ReviewerV2
        固定最多重跑一次；
        无 max_iterations；
        第二轮失败也停止修订。
    end note
```

代码依据：

- 首轮假设、实验、Reviewer：`app/workflow/pipeline.py:498-534`
- 自动修订条件与第二次调用：`app/workflow/pipeline.py:535-555`
- 第二轮后直接进入报告：`app/workflow/pipeline.py:557-578`

## 当前数据流

```mermaid
flowchart TD
    Q["question_item"]
    E["evidence_catalog + evidence_extraction"]

    H1I["第1轮 Hypothesis 输入"]
    H1["HypothesisGenerator 输出 H1"]
    SH["state.hypothesis_generation = H1"]
    SHL["state.hypotheses = H1 的规范化列表"]

    E1I["第1轮 Experiment 输入"]
    E1["ExperimentDesigner 输出 E1"]
    SE["state.experiment_design = E1"]

    R1I["第1轮 Reviewer 输入"]
    R1["ReviewResult R1"]
    SR["state.review_result = R1"]

    FB["critical_issues\nrequired_revisions\nreviewer_comments"]
    LOST["反馈丢失点\n只保存，不注入下一轮"]
    MARK["revision_history += auto_revision_1"]

    H2I["第2轮 Hypothesis 输入\n仍只有 question + evidence"]
    H2["HypothesisGenerator 输出 H2"]
    SH2["state.hypothesis_generation = H2\n覆盖 H1"]

    E2I["第2轮 Experiment 输入\nH2 + evidence；无 Reviewer 字段"]
    E2["ExperimentDesigner 输出 E2"]
    SE2["state.experiment_design = E2\n覆盖 E1"]

    R2I["第2轮 Reviewer 输入\nH2 + E2 + evidence"]
    R2["ReviewResult R2"]
    SR2["state.review_result = R2\n覆盖 R1"]

    TRACE["state.agent_trace\n保留每次最多600字符摘要和 prompt_hash"]
    REPORT["最终 Report / pipeline_state.json"]

    Q --> H1I
    E --> H1I
    H1I --> H1
    H1 --> SH
    H1 --> SHL

    SH --> E1I
    E --> E1I
    E1I --> E1
    E1 --> SE

    SH --> R1I
    SE --> R1I
    E --> R1I
    R1I --> R1
    R1 --> SR
    R1 --> FB

    FB -. "未复制到 H2I 或 E2I" .-> LOST
    R1 -->|"passed=false 且允许自动修订"| MARK
    MARK --> H2I
    Q --> H2I
    E --> H2I

    H2I --> H2
    H2 --> SH2
    SH2 --> E2I
    E --> E2I
    E2I --> E2
    E2 --> SE2

    SH2 --> R2I
    SE2 --> R2I
    E --> R2I
    R2I --> R2
    R2 --> SR2

    H1 --> TRACE
    E1 --> TRACE
    R1 --> TRACE
    H2 --> TRACE
    E2 --> TRACE
    R2 --> TRACE

    SH2 --> REPORT
    SE2 --> REPORT
    SR2 --> REPORT
    SHL -. "未在第2轮同步，可能仍是 H1" .-> REPORT
    TRACE --> REPORT

    classDef loss fill:#ffdddd,stroke:#b00020,stroke-width:2px,color:#111;
    classDef overwrite fill:#fff2cc,stroke:#b36b00,stroke-width:2px,color:#111;
    classDef trace fill:#ddeeff,stroke:#2457a6,stroke-width:1px,color:#111;
    class FB,LOST loss;
    class SH2,SE2,SR2,SHL overwrite;
    class TRACE trace;
```

Reviewer 反馈的明确丢失位置是：

1. `state.review_result = review` 保存了 R1
   `app/workflow/pipeline.py:532-534`
2. 修订分支只追加 `revision_history` 文本
   `app/workflow/pipeline.py:535-537`
3. 紧接着构造第二轮 Hypothesis 输入时没有读取 `review` 或
   `state.review_result`
   `app/workflow/pipeline.py:538-546`
4. `_experiment_designer_input()` 也没有 Reviewer 字段
   `app/workflow/pipeline.py:241-260`

## 当前版本、停止与重试逻辑

| 主题 | 当前实现 |
|---|---|
| 版本 | 无 `version` 字段，无 V1/V2；只有 `revision_history` 字符串 |
| iteration | 无显式 `iteration` |
| max iterations | 无 `max_iterations`；代码结构固定最多重跑一次 |
| 重试触发 | `not passed and reviewer_auto_revision and not revision_history` |
| 第二轮停止 | 无条件停止修订并进入 ReportWriter |
| 相同 prompt | 不比较，不阻止记录自动修订 |
| 首轮完整产物 | `hypothesis_generation`、`experiment_design`、`review_result` 被覆盖 |
| trace | 每轮事件仍在 `agent_trace`，但输出只是最多 600 字符摘要 |
| context hash | `context_pack.prompt_hashes` 按 Agent 名折叠，多轮只保留最后一个 |

## 当前 `prompt_hash` 流程

```mermaid
flowchart LR
    IN["Agent input_data"]
    SUM["JSON化、脱敏、截断600字符"]
    SYS["model_name + system_prompt"]
    HASH["SHA-256 前12位"]
    EVENT["AgentTraceEvent.prompt_hash"]
    TRACEFILE["agent_trace.json\n保留每轮事件"]
    PACK["context_pack.prompt_hashes\n按 agent_name 覆盖"]
    CMP["无比较逻辑"]

    IN --> SUM
    SUM --> HASH
    SYS --> HASH
    HASH --> EVENT
    EVENT --> TRACEFILE
    EVENT --> PACK
    HASH -. "未用于判断是否真实修订" .-> CMP

    classDef gap fill:#ffdddd,stroke:#b00020,stroke-width:2px,color:#111;
    class PACK,CMP gap;
```

代码依据：

- 输入摘要：`app/agents/base.py:166-182`
- hash：`app/agents/base.py:314-327`
- trace 保存：`app/agents/base.py:329-380,549-563`
- context pack 折叠：`app/workflow/context_builder.py:136-152`

## 当前状态结论

当前实现拥有“Reviewer 失败后再调用一次生成链”的控制流，但没有 Reviewer 驱动的
数据流，也没有可审计的版本递增。因此第二次调用只能称为重跑，不能仅凭
`revision_history` 证明它是一次真实修订。
