# Pipeline Agent 输入与 Schema 校验接口文档

本文档说明 **真实模式** 下多智能体流水线的关键输入契约、Schema 校验与前端错误处理，便于排查「测试脚本能跑、前端点击失败」类问题。

---

## 1. 问题根因（已修复）

| 场景 | 行为 |
|------|------|
| **Mock / pytest** | `build_mock()` 根据 `question_item` 自动生成完整 `ExperimentDesignResult` 字段，测试通过 |
| **真实 Qwen** | 若只传 `{"question_item": ...}`，模型常**回显输入**而非输出 schema，导致 Pydantic 报 `missing: technical_details, methods, results` |

**修复要点：**

1. `app/workflow/pipeline.py` — `_experiment_designer_input()` / `_reviewer_input()` 向 Agent 传入假设、证据、实验设计等完整上下文  
2. `app/agents/experiment_designer.py` / `scientific_reviewer.py` — `build_messages()` **不再**把 `question_item` 发给 LLM  
3. `app/agents/base.py` — `_focus_schema_fields()` + `_repair_schema_output()` 在真实模式下对不完整 JSON 尝试一次修复  

---

## 2. Pipeline 辅助函数

### `_recommended_hypothesis(hyp_result: dict | None) -> dict`

从 `HypothesisGenerationResult` 中提取推荐假设 dict。

- **参数**：`hyp_result` — 假设生成阶段输出  
- **返回**：推荐假设 dict；无假设时返回 `{}`

### `_experiment_designer_input(state: PipelineState, qdict: dict) -> dict`

构造 ExperimentDesigner 的完整输入。

- **参数**  
  - `state` — 当前流水线状态（含 `hypothesis_generation`、`evidence_extraction`、`retrieved_evidence`）  
  - `qdict` — 问题 dict  
- **返回字段**  
  - `question_item` — 保留供 mock / trace  
  - `question_type` — 来自 `state.parsed_question`  
  - `recommended_hypothesis`  
  - `hypothesis_generation`  
  - `evidence_extraction`  
  - `evidence_catalog`  

### `_reviewer_input(state: PipelineState, qdict: dict) -> dict`

构造 ScientificReviewer 的完整输入。

- **返回字段**：在 experiment designer 基础上增加 `experiment_design`

---

## 3. Agent 层接口

### `ExperimentDesignerAgent.build_messages(input_data: dict) -> list[dict]`

- **用途**：向 Qwen 发送结构化上下文（假设 + 证据），避免回显 `question_item`  
- **user 消息 JSON 键**：`question_type`, `recommended_hypothesis`, `hypothesis_generation`, `evidence_extraction`, `evidence_catalog`

### `ScientificReviewerAgent.build_messages(input_data: dict) -> list[dict]`

- **user 消息 JSON 键**：`recommended_hypothesis`, `hypothesis_generation`, `experiment_design`, `evidence_extraction`, `evidence_catalog`

### `BaseAgent.validate_output(data: dict, schema_cls) -> BaseModel`

- **流程**：`_focus_schema_fields` → Pydantic 校验 → 失败且非 mock 时 `_repair_schema_output` 再校验一次  
- **异常**：`AgentOutputError` — 消息已脱敏，含 schema 名与校验摘要  

### `BaseAgent._focus_schema_fields(data, schema_cls) -> dict`

- **用途**：从模型输出中只保留 schema 定义的字段，丢弃 `question_item` 等输入回显  

### `BaseAgent._repair_schema_output(data, schema_cls, error_msg) -> dict | None`

- **用途**：真实模式下用一次 LLM 调用补全缺失字段  
- **返回**：修复后的 dict；mock 模式或 repair 失败时返回 `None`  

---

## 4. 输出 Schema（ExperimentDesignResult）

必填字段（`app/core/agent_schemas.py`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `technical_details` | str | 技术细节 |
| `datasets` | dict | 须含 `source` / `target` |
| `methods` | str | 方法 |
| `experiments` | dict | 须含 `baselines`、`metrics` |
| `results` | str | 未真实执行时必须为 pending 文案 |
| `reproducibility_checklist` | list[str] | 可复现清单 |
| `execution_metadata` | dict | `actual_execution: false` 当未跑实验 |

---

## 5. 前端错误 API（`app/ui/errors.py`）

### `run_failed(error, run_id=None, fix_commands=None, details=None, *, error_type=None, mode="mock")`

- **Schema 校验失败**：若错误含「未通过」「校验」，提示重启 Streamlit 并重试，而非一律显示百炼/RAG 修复命令  
- **参数**  
  - `mode`: `"real"` \| `"mock"` — 影响默认修复命令  
  - `error_type`: `"read_timeout"` 时转 `run_timeout()`  

---

## 6. 验收命令

```powershell
# 单元测试（含新增上下文与 repair 测试）
py -3 -m pytest tests/test_pipeline_experiment_designer_input.py tests/test_agent_schema_repair.py -q

# 全量回归
py -3 -m pytest -q

# 真实模式 CLI 冒烟（约 15–20 分钟，建议关 DeepResearch）
py -3 scripts/check_real_qwen_invocation.py --question-id Q001 --no-deepresearch
```

**前端注意**：修改 `app/ui/` 或 `app/agents/` 后需**重启 Streamlit**（不能仅靠页面 rerun），并确保 8501 端口只有一个进程。

---

## 7. FastAPI 运行接口（不变）

启动：`uvicorn app.api.main:app --reload --port 8000`  
交互文档：`http://127.0.0.1:8000/docs`

与本次修复相关的主要端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/preflight` | 真实模式启动前检查 Key / RAG / DeepResearch |
| POST | `/runs` | 触发 pipeline；返回统一 `RunResponse` |

详见 README §8 与 OpenAPI `/docs`。
