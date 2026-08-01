# T02 Reviewer 假迭代失败轨迹

## 目的

复现以下失败模式：

1. 第一轮 Reviewer 明确返回失败及修订意见；
2. 工作流记录 `auto_revision_1`；
3. 第二轮 HypothesisGenerator 和 ExperimentDesigner 没有收到 Reviewer 意见；
4. 两轮生成输入、输出和 `prompt_hash` 相同；
5. mock Reviewer 仍从失败变为通过。

该复现只使用 mock 和内存对象，不调用真实模型，不读取 `.env`，不写
`exports/`，并通过 `-B` 禁止 Python 写入字节码。

## 审计使用的命令

准入与代码检索：

```powershell
git branch --show-current
git status --short --branch
git remote -v
git branch -a --list *integration/2026-08-10*
git rev-parse HEAD integration/2026-08-10 origin/integration/2026-08-10 upstream/integration/2026-08-10
git merge-base --is-ancestor integration/2026-08-10 HEAD
rg --files app/workflow tests/workflow
rg --files tests
rg -n "critical_issues|required_revisions|comments|prompt_hash|version|iteration|max_iterations|stop|retry" app tests
```

关键实现逐行检查：

```powershell
rg -n "^" app/workflow/pipeline.py
rg -n "^" app/agents/base.py
rg -n "^" app/agents/hypothesis_generator.py app/agents/experiment_designer.py app/agents/scientific_reviewer.py
rg -n "^" app/workflow/artifacts.py app/workflow/context_builder.py
```

## 等价的纯内存可复现命令

下列命令与调查时执行的 `python -B -c` 最小复现等价，便于复核：

```powershell
@'
import json
import os
from types import SimpleNamespace

os.environ["MOCK_LLM"] = "true"
os.environ["MOCK_REVIEW_FAIL"] = "true"

from app.agents import (
    ExperimentDesignerAgent,
    HypothesisGeneratorAgent,
    ScientificReviewerAgent,
)
from app.core.schemas import EvidenceCard, PipelineState, QuestionItem
from app.workflow.mock_outputs import build_mock_evidence_cards
from app.workflow.pipeline import (
    _evidence_catalog,
    _experiment_designer_input,
    _reviewer_input,
)

q = {
    "id": "Q001",
    "domain": "Mathematical Sciences",
    "question": "Are the prime numbers scattered randomly?",
    "source_page": 1,
    "booklet_excerpt": "prime excerpt",
    "metadata": {},
}

# 显式注入设置，避免调用 get_settings() 和读取 .env。
settings = SimpleNamespace(
    qwen_fast_model="qwen3.6-flash",
    qwen_balanced_model="qwen3.7-plus",
    qwen_strong_model="qwen3.7-max",
    qwen_deep_research_model="qwen-deep-research",
)

state = PipelineState(
    run_id="audit-memory-only",
    selected_question=QuestionItem(**q),
    mock_mode=True,
    run_mode="mock",
)
state.retrieved_evidence = [
    EvidenceCard(**item) for item in build_mock_evidence_cards(q)
]
state.evidence_extraction = {
    "established_facts": [],
    "knowledge_gaps": [],
}

hypothesis_input = {
    "question_item": q,
    "evidence_catalog": _evidence_catalog(state.retrieved_evidence),
    "evidence_extraction": state.evidence_extraction,
}

h1 = HypothesisGeneratorAgent(settings).run(hypothesis_input, state, 0)
state.hypothesis_generation = h1
e1 = ExperimentDesignerAgent(settings).run(
    _experiment_designer_input(state, q), state, 1
)
state.experiment_design = e1
r1 = ScientificReviewerAgent(settings).run(_reviewer_input(state, q), state, 2)
state.review_result = r1

state.revision_history.append("auto_revision_1")

h2 = HypothesisGeneratorAgent(settings).run(hypothesis_input, state, 3)
state.hypothesis_generation = h2
e2 = ExperimentDesignerAgent(settings).run(
    _experiment_designer_input(state, q), state, 4
)
state.experiment_design = e2
r2 = ScientificReviewerAgent(settings).run(_reviewer_input(state, q), state, 5)
state.review_result = r2

trace = state.agent_trace
print(json.dumps({
    "h_output_equal": h1 == h2,
    "e_output_equal": e1 == e2,
    "h_hashes": [trace[0]["prompt_hash"], trace[3]["prompt_hash"]],
    "e_hashes": [trace[1]["prompt_hash"], trace[4]["prompt_hash"]],
    "r_hashes": [trace[2]["prompt_hash"], trace[5]["prompt_hash"]],
    "r_passed": [r1["passed"], r2["passed"]],
    "h_inputs_equal": trace[0]["input_summary"] == trace[3]["input_summary"],
    "e_inputs_equal": trace[1]["input_summary"] == trace[4]["input_summary"],
    "r_inputs_equal": trace[2]["input_summary"] == trace[5]["input_summary"],
}, ensure_ascii=False))
'@ | .\.venv\Scripts\python.exe -B -
```

## 第一轮与第二轮生成输入

### HypothesisGenerator

第一轮和第二轮都由 `app/workflow/pipeline.py:499-507,538-546` 构造为：

```json
{
  "question_item": "<同一 qdict>",
  "evidence_catalog": "<同一 retrieved_evidence 序列化目录>",
  "evidence_extraction": "<同一 evidence_extraction>"
}
```

缺失字段：

```text
review_result
critical_issues
required_revisions
reviewer_comments
issue_id
iteration
version
```

### ExperimentDesigner

两轮都通过 `_experiment_designer_input()` 构造：

```json
{
  "question_item": "<同一 qdict；build_messages 时不发送>",
  "question_type": "<同一 parsed_question.question_type>",
  "recommended_hypothesis": "<当假设重复时相同>",
  "hypothesis_generation": "<当假设重复时相同>",
  "evidence_extraction": "<同一 evidence_extraction>",
  "evidence_catalog": "<同一 evidence_catalog>"
}
```

`ExperimentDesignerAgent.build_messages()` 发送的 payload 不包含任何 Reviewer 字段。
证据：`app/agents/experiment_designer.py:45-55`。

### ScientificReviewer

两轮都通过 `_reviewer_input()` 构造：

```json
{
  "question_item": "<同一 qdict；build_messages 时不发送>",
  "recommended_hypothesis": "<重复时相同>",
  "hypothesis_generation": "<重复时相同>",
  "experiment_design": "<重复时相同>",
  "evidence_extraction": "<同一 evidence_extraction>",
  "evidence_catalog": "<同一 evidence_catalog>"
}
```

`revision_history` 不在 Reviewer 消息中。mock Reviewer 却直接读取整个
`PipelineState.revision_history` 决定返回失败还是通过。

## 两轮输入与 hash 证据

调查时的实际最小复现输出：

```json
{
  "h_output_equal": true,
  "e_output_equal": true,
  "h_hashes": ["755cc4d3404e", "755cc4d3404e"],
  "e_hashes": ["7c06f1c08f46", "7c06f1c08f46"],
  "r_hashes": ["8aaaa8e58519", "8aaaa8e58519"],
  "r_passed": [false, true],
  "h_inputs_equal": true,
  "e_inputs_equal": true,
  "r_inputs_equal": true
}
```

解释：

- HypothesisGenerator 两轮输入摘要相同，输出相同，hash 相同。
- ExperimentDesigner 两轮输入摘要相同，输出相同，hash 相同。
- ScientificReviewer 两轮输入摘要和 hash 相同。
- Reviewer 的业务判定仍从 `false` 变为 `true`。

hash 算法证据：`app/agents/base.py:314-327,471-474`。

## 实际行为

1. 首轮 mock Reviewer 在 `MOCK_REVIEW_FAIL=true` 且
   `state.revision_history` 为空时返回：

   ```json
   {
     "passed": false,
     "reviewer_comments": ["假设的可证伪预测不够具体。"],
     "critical_issues": ["缺少明确的证伪判据。"],
     "required_revisions": ["为推荐假设补充明确的证伪阈值与观测。"]
   }
   ```

   证据：`app/workflow/mock_outputs.py:464-476`。

2. pipeline 只追加 `auto_revision_1` 文本，不把上述字段传给生成 Agent。
3. mock HypothesisGenerator 和 ExperimentDesigner 产生与首轮相同的输出。
4. 第二轮 mock Reviewer 因 `state.revision_history` 已非空，直接改用通过结果。
5. 第二轮 Reviewer 之后无再次失败判断，工作流继续写报告。

关键代码：

- 修订分支：`app/workflow/pipeline.py:535-555`
- mock Reviewer 的状态分支：`app/agents/scientific_reviewer.py:57-68`
- 确定性 mock 假设：`app/workflow/mock_outputs.py:392-426`
- 确定性 mock 实验：`app/workflow/mock_outputs.py:429-442`

## 预期行为

一次可计数的 Reviewer 驱动修订至少应满足：

1. 第二轮生成输入包含首轮 `critical_issues`、`required_revisions`、
   `reviewer_comments` 及可追踪 issue ID；
2. 第二轮实际消息可与第一轮区分；
3. 首轮完整假设、实验和 Reviewer 输出仍可按 V1 访问；
4. 第二轮产物具有 V2/iteration=2 等显式版本标识；
5. 相同 prompt/等价输入不得被计为有效修订；
6. 第二轮仍失败时保存明确停止原因，而不是无条件进入报告阶段。

## 是否构成假迭代

**是。**

判定依据不是“文本看起来相似”，而是以下四项同时成立：

1. Reviewer 首轮提出了具体阻断意见；
2. 意见没有进入第二轮 HypothesisGenerator 或 ExperimentDesigner 的输入；
3. 两轮生成输入摘要、输出及 `prompt_hash` 实测相同；
4. 第二轮 Reviewer 仍由失败变为通过，变化来源只是
   `state.revision_history` 是否为空。

因此，当前 mock 自动修订证明的是“控制流走过第二遍”，不能证明方案依据 Reviewer
意见发生了真实修订。仓库治理回归场景也把
`T02-B-001 — Reviewer feedback saved but not fed into next round`
列为阻断问题，见 `tests/governance/test_content_acceptance.py:367-379`。
