# T08 Wave C Owner Composition

状态：`T01_READ_CONNECTED / T03_SUBMIT_CONNECTED / T06_READ_CONNECTED / T02_T05_WAIT`

基线：`upstream/integration/2026-08-10` at `c2fb04c`（含 T01 PR #43）

分支：`t08/c-delivery-hardening`

## 1. 边界结论

本轮只接入已经具备冻结公开端口的能力：

- T01：通过 `app.evidence.read_port.get_evidence_bundle` 读取权威 EvidenceBundle；
- T03：通过 `FeedbackService.submit_request` 持久化人工反馈；
- T06：通过 `list_multimodal_details` 读取三键绑定的多模态详情。

以下能力继续失败关闭，不解析 owner 私有文件、内部表或进程内对象：

- T02 version history / aggregate diff production read；
- T05 ExecutionResult history / artifact resolver；
- T03 feedback status、decision、resulting version 和 Validation Gate read。

对应 owner 请求：

- T01：[Issue #52](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/issues/52)
- T02：[Issue #53](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/issues/53)
- T05：[Issue #54](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/issues/54)

## 2. Composition 函数与职责

### `create_app(...)`

文件：`app/api/main.py`

新增注入参数：

```python
feedback_submit_port: FeedbackSubmitPort | None = None
multimodal_read_port: MultimodalReadPort | None = None
```

默认 production composition：

- T01 使用 `ComposedOwnerContractAdapter`，只调用
  `get_evidence_bundle(run_id, question_id)`；
- T03 使用与 JobStore 同一持久根下的
  `.api-state/feedback.sqlite3`；
- T06 使用 owner 的 `T06_MULTIMODAL_STORE_DIR` 或其冻结默认持久根；
- 测试可注入隔离 store，不读取开发者本地 exports。
- 不再在 `app/api/upstream.py` 另起 `ProductionOwnerContractAdapter`。

### `T01EvidenceReadAdapter.get_evidence_bundle(...)`

文件：`app/api/owner_composition.py`

输入身份：

```text
run_id + question_id
```

函数行为：

1. 只调用 T01 公开 `get_evidence_bundle`；
2. 对返回值再次 `EvidenceBundle.model_validate`；
3. 把 `EvidencePortError.category` 映射为 `OwnerPortFailure`；
4. 不打开 T01 SQLite schema，不扫描 `evidence_cards.json`。

HTTP 映射：

| T01 category | HTTP | T08 code |
| --- | --- | --- |
| `not_found` | 404 | `UPSTREAM_RESOURCE_NOT_FOUND` |
| `not_ready` | 409 | `UPSTREAM_RESOURCE_NOT_READY` |
| `invalid_contract` | 503 | `UPSTREAM_CONTRACT_INVALID` |
| `identity_mismatch` | 409 | `UPSTREAM_IDENTITY_MISMATCH` |
| `conflict` | 409 | `UPSTREAM_RESOURCE_CONFLICT` |
| `retryable_upstream_failure` | 503 | `UPSTREAM_READ_FAILED` |
| `non_retryable_upstream_failure` | 503 | `UPSTREAM_READ_FAILED` |
| `unavailable` | 503 | `UPSTREAM_CONTRACT_UNAVAILABLE` |

空 store 是 404，不是 200 空列表。空 `items` 只允许 T01 返回合法但
`evidences=[]` 的 bundle。

### `ComposedOwnerContractAdapter`

默认 `upstream_read_port`。问题清单仍走 T07 文件源；证据走
`T01EvidenceReadAdapter`；T02 versions/diff 继续
`OwnerContractUnavailable`。

### `T03FeedbackSubmitAdapter.submit(...)`

文件：`app/api/owner_composition.py`

输入身份：

```text
job_id
upstream run_id
question_id
target_version_id
authenticated actor_id
correlation_id
Idempotency-Key
```

函数行为：

1. 为当前请求构造只允许 `submit` 的 identity-bound authorizer；
2. 调用 `DefaultFeedbackService.submit_request`；
3. 让 T03 生成 feedback ID、请求指纹和幂等键 hash；
4. 返回最小 `FeedbackSubmissionResult`；
5. 不调用 `decide()`，不生成 resulting version，不重算 Gate。

`job_id` 仅写入 feedback metadata；T03 `run_id` 始终使用
`JobRecord.upstream_run_id`，两者不得混用。

### `T06MultimodalReadAdapter.list_details(...)`

文件：`app/api/owner_composition.py`

输入身份：

```text
run_id + question_id + version_id
```

函数只调用冻结的 `app.multimodal.read_port.list_multimodal_details`，并完整保留：

- public source ID、label、preview artifact ID；
- page、bbox、coordinate space；
- extracted table values；
- units、column units、axes、legend；
- confidence、validation status、needs human review。

函数不调用 `MultimodalQueue.snapshot()`，不扫描文件名，也不自行定义低置信度阈值。

## 3. HTTP 接口

### 3.0 读取证据包

```http
GET /api/v1/jobs/{job_id}/evidence
X-API-Key: ...
```

成功：`200 OK`，字段来自 T01 `EvidenceBundle` 投影，必须保留 quote、locator、
作者、年份、DOI/URL、content hash 和支持关系。

PowerShell：

```powershell
Invoke-RestMethod -Headers @{ "X-API-Key" = $env:SAGE_API_KEY } `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/evidence"
```

### 3.1 提交反馈

```http
POST /api/v1/jobs/{job_id}/feedback
X-API-Key: ...
Idempotency-Key: ...
X-Correlation-ID: ...
Content-Type: application/json
```

请求：

```json
{
  "target_version_id": "v1",
  "feedback": "请补充可证伪阈值和停止条件。"
}
```

兼容策略：

- 外部短标签 `v1` 集中转换为 `<upstream_run_id>:v1`；
- 已经使用 canonical `<run_id>:vN` 的输入保持不变；
- 其他格式交由 T03 冻结校验拒绝。

成功：`202 Accepted`

```json
{
  "feedback_id": "feedback-...",
  "job_id": "job-...",
  "target_version_id": "run-...:v1",
  "status": "submitted",
  "decision_reason": null,
  "resulting_version_id": null,
  "correlation_id": "..."
}
```

重要限制：

- `submitted` 只表示 T03 已持久化；
- T03 安全策略可以同步生成自动拒绝审计事件；
- 本接口不声称反馈已接受，也不声称已经生成新版本；
- `GET .../feedback/{feedback_id}` 在 status/Gate read port 冻结前继续返回 503。

错误：

| HTTP | code | 含义 |
|---|---|---|
| 403 | `FEEDBACK_PERMISSION_DENIED` | actor 与任务身份不匹配 |
| 409 | `UPSTREAM_RESULT_NOT_READY` | job 尚无 upstream run |
| 409 | `OWNER_STATE_CONFLICT` | 幂等键或 owner 状态冲突 |
| 422 | `OWNER_INPUT_INVALID` | 不符合 T03 冻结契约 |
| 503 | `UPSTREAM_CONTRACT_UNAVAILABLE` | T03 存储或端口不可用 |

### 3.2 读取多模态详情

```http
GET /api/v1/jobs/{job_id}/multimodal?version_id=<run_id>:v1
X-API-Key: ...
```

成功：`200 OK`

空 `items` 表示该 identity 没有多模态产物，不是 404，也不填充 fixture。

响应字段由 `MultimodalDetailProjection` 定义，包含 T06 冻结 UI contract 要求的
source、bbox、values、units、axes、legend、confidence 和 review 状态。

错误：

| HTTP | code | 含义 |
|---|---|---|
| 409 | `UPSTREAM_RESULT_NOT_READY` | job 尚无 upstream run |
| 409 | `UPSTREAM_IDENTITY_MISMATCH` | T06 持久 envelope 身份冲突 |
| 422 | `OWNER_INPUT_INVALID` | version identity 不合法 |
| 503 | `UPSTREAM_CONTRACT_UNAVAILABLE` | T06 store 不可读、契约损坏或 locator 仍含本地路径 |

## 4. 安全与科学真实性

- API 先验证 `X-API-Key` 与 job owner，再调用 T03/T06；
- T03 幂等键只以 SHA-256 写入 owner store；
- T06 source path 由 owner read port 脱敏；
- 若 owner projection 仍含 Windows/POSIX 本地路径语法，T08 整体失败关闭而不二次猜测路径；
- T08 不决定 accepted/partial/rejected；
- T08 不生成 resulting version；
- T08 不重算 Validation Gate；
- T08 不从文件存在性推断 `actual_execution`；
- T01 空 store 返回 404，不把 fixture 或旧缓存写成成功；
- T02/T05 缺少 production read port 时继续返回明确 503。

## 5. 验证命令

Windows 11 PowerShell：

```powershell
py -m pytest -q tests/api/test_owner_composition.py
py -m pytest -q tests/api
py -m compileall -q app/api tests/api
```

专项测试覆盖：

- T01 只调用公开读端口，重启后可读 SQLite；
- T01 空 store 404 且不泄露路径；
- T01 category 稳定映射，错误正文不含 owner 路径；
- T03 canonical run identity 与 actor 绑定；
- feedback 幂等重试和冲突；
- T03 prompt-injection 自动拒绝仍由 owner 保存；
- 无 upstream run 时失败关闭；
- T06 bbox、values、units、legend、confidence 和状态不丢失；
- T06 空集合语义和非法 identity 映射；
- OpenAPI 暴露 feedback 202 与 multimodal 200。

## 6. 未完成项

本文件不是 production 全闭环通过声明。以下事项继续阻断：

1. T02、T05 issues 尚未由 owner 交付生产读端口；
2. T03 status/decision/Gate read port 尚未冻结；
3. production feedback→decision→T02 resulting version trace 尚未执行；
4. T05 execution 与 canonical export 仍不可用；
5. Docker、2 小时稳定性、浏览器 E2E 和最终 handoff 属于后续 Wave C 门禁。
