# T09 Deep Research 审计提取接口

本文记录 `QwenDeepResearchClient` 在正式 12 域实跑中必须遵守的审计字段提取契约。实现位于 `app/clients/qwen_deep_research_client.py`，由 `DeepResearchAgent` 写入 `LLMCallRecord`。

## 背景

百炼 `qwen-deep-research` 只在流式 `status=finished` 分片保证返回用量。官方示例中的 usage 通常只有 `input_tokens` 与 `output_tokens`，不一定带 `total_tokens`；`request_id` 也可能出现在顶层、`output` 或响应头。T09 runner 对每一次真实调用要求：

- 非空且唯一的真实 `request_id`；
- 非负整数 `input_tokens` / `output_tokens` / `total_tokens`；
- `total_tokens == input_tokens + output_tokens`；
- 不得把缺失用量写成 `0`，也不得编造 request_id。

## 接口

### `QwenDeepResearchClient._extract_request_id(response) -> str`

从单个流式分片提取服务端 request_id。

查找顺序：

1. 顶层 `request_id`
2. `output.request_id`
3. 响应头 `x-dashscope-request-id` / `x-request-id` / `request-id` / `request_id`（大小写不敏感）

找不到时返回空串。调用方必须保持字段为 `None`/空，不得生成占位 id。

### `QwenDeepResearchClient._extract_usage(response) -> dict[str, int]`

从顶层 `usage` 或 `output.usage` 提取用量，再交给 `_normalized_usage`。

### `QwenDeepResearchClient._normalized_usage(raw_usage) -> dict[str, int]`

接受 DashScope 或 OpenAI 风格字段：

- `input_tokens` 或 `prompt_tokens`
- `output_tokens` 或 `completion_tokens`
- 可选 `total_tokens`

规则：

- 只接受非负整数（含可无损转 int 的数字字符串 / 整值 float）；
- 缺少 `total_tokens` 时用 `input + output` 补齐；
- `total` 与 `input + output` 不一致时返回空映射；
- 任一必填字段缺失或非法时返回空映射，禁止写成 0。

成功时固定返回：

```json
{"input_tokens": 15, "output_tokens": 9, "total_tokens": 24}
```

### `QwenDeepResearchClient.run_deep_research(topic, context="") -> dict`

真实调用成功时，返回值必须回传已经提取到的：

- `request_id`
- `usage`

并同步写入 `last_request_id` / `last_usage`，供 `DeepResearchAgent` 写入 `LLMCallRecord`。

## 回归

离线测试：

- `tests/test_qwen_call_audit.py::test_deep_research_usage_accepts_official_finished_pair`
- `tests/test_qwen_call_audit.py::test_deep_research_usage_rejects_mismatched_total`
- `tests/test_qwen_call_audit.py::test_deep_research_request_id_from_output_and_headers`
- `tests/test_qwen_call_audit.py::test_deep_research_stream_finished_chunk_preserves_audit`
- `tests/test_qwen_call_audit.py::test_deep_research_real_audit_preserves_request_id_and_usage`

这些测试禁止访问 Provider。
