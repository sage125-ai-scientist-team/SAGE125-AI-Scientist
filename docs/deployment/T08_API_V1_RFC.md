# T08 API v1 RFC — Job/Status 与交付 Projection

状态：Wave A 冻结候选
日期：2026-07-29
前缀：`/api/v1`

## 1. 边界

API v1 拥有 HTTP DTO、任务调度状态、幂等、correlation 和错误映射。
它不拥有科学结论、Reviewer 判定、质量门、真实执行判定或多模态抽取。

当前实际接通 Job/Status。Artifact、Version、Feedback 的 DTO 代码只作为后续
owner 联调的候选 projection，不是当前 operation 的成功响应。对应五个 operation
在公开契约可用前失败关闭：OpenAPI 主状态和运行时均为 HTTP 503
`ErrorResponse`，不声明任何 2xx：

```json
{
  "code": "UPSTREAM_CONTRACT_UNAVAILABLE",
  "message": "...公开契约尚未接入。",
  "details": {
    "component": "...",
    "availability": "unavailable"
  },
  "correlation_id": "...",
  "retryable": true
}
```

旧 `POST /runs` 行为不变，并在 OpenAPI 中标为 deprecated。

## 2. 通用协议

### Correlation

- 客户端可传 `X-Correlation-ID`，允许字符为字母、数字、`.`、`_`、`-`，
  长度 1—128；
- 缺失时服务生成 UUID；
- 响应头始终回传 `X-Correlation-ID`；
- Job 记录保留创建请求的 correlation ID；
- 非法值返回 HTTP 400 `INVALID_CORRELATION_ID`。

### 幂等

`POST /api/v1/jobs` 接受可选 `Idempotency-Key`：

- 相同 key、相同 canonical request：返回原任务，`reused=true`；
- 相同 key、不同 request：HTTP 409 `IDEMPOTENCY_CONFLICT`；
- SQLite 只保存 key 的 SHA-256，不保存原文。
- 首次因队列容量被拒绝时，原 Job 记录为
  `failed / queue_rejected / QUEUE_CAPACITY_EXCEEDED`，并返回带原
  `job_id` 的 HTTP 503；
- 同 key 只可恢复 `attempt=0`、`started_at=null`、`upstream_run_id=null`
  的上述容量拒绝 Job。SQLite 使用 `BEGIN IMMEDIATE` 与原状态快照原子认领为
  `retrying / queue_retry_claimed`，不开放通用 `failed -> retrying`；
- 认领后队列仍满则恢复为 `failed / queue_rejected` 并继续返回 503；成功入队
  才返回 202 并复用原 `job_id`；
- 其他请求看到尚未确认入队的 `queue_retry_claimed` 时返回可重试 503
  `QUEUE_RETRY_IN_PROGRESS`，不得返回假 202；
- 已有 attempt、启动时间或上游引用的 Job 返回 409
  `QUEUE_CAPACITY_RETRY_UNSAFE`，不得通过容量恢复机制再次执行。

### 错误

所有 v1 错误使用：

```json
{
  "code": "STABLE_MACHINE_CODE",
  "message": "简洁说明",
  "details": {},
  "correlation_id": "...",
  "retryable": false
}
```

## 3. Job 与 Status

### 创建任务

```http
POST /api/v1/jobs
Content-Type: application/json
Idempotency-Key: demo-q001-001
X-Correlation-ID: judge-demo-001
```

```json
{
  "question_id": "Q001",
  "mode": "mock",
  "options": {
    "use_deep_research": true,
    "use_open_literature": true,
    "use_local_rag": true,
    "reviewer_auto_revision": true
  }
}
```

成功返回 HTTP 202：

```json
{
  "job_id": "c4ef4580-e351-4b44-b9a2-19edac5ec977",
  "correlation_id": "judge-demo-001",
  "status": "queued",
  "created_at": "2026-07-28T06:30:00Z",
  "status_url": "/api/v1/jobs/c4ef4580-e351-4b44-b9a2-19edac5ec977",
  "reused": false
}
```

`job_id` 是 T08 任务 ID。pipeline 生成的 `run_id` 在上游返回后记录为
`upstream_run_id`，即使完成资格仍待核验，也不得把两者当作同一标识。

### 查询

- `GET /api/v1/jobs/{job_id}`：单个任务状态；
- `GET /api/v1/jobs?question_id=Q001&status=running&limit=20`：任务列表。

状态枚举：

```text
queued
running
waiting_feedback
retrying
completed
failed
timed_out
cancelled
```

合法转换：

```text
queued -> running | failed | cancelled
running -> waiting_feedback | retrying | completed | failed | timed_out | cancelled
waiting_feedback -> queued | completed | failed | cancelled
retrying -> queued | running | failed | timed_out | cancelled
terminal -> no transition
```

`failed / queue_rejected` 的容量恢复是受上述字段和原状态快照约束的专用原子
操作，不属于通用状态转换表。认领、成功提交、再次容量拒绝和拒绝原因均写入
`job_events`。

`stage` 来自真实 worker/pipeline 事件。API 不根据耗时生成百分比。

### 完成资格门禁

上游函数正常返回只代表本轮 pipeline 执行结束，不自动代表对外交付完成。
worker 只有在 adapter 通过冻结 owner 契约明确提供以下全部证明时，才允许写入
`completed`：

- 必需产物存在；
- T03 质量门通过；
- P0/P1 阻断问题已关闭；
- `planned/expected/mock/actual` 真实性状态明确；
- 关键字段可序列化并可回链。

任一证明缺失时，任务进入
`waiting_feedback / awaiting_completion_verification`，保留 `upstream_run_id`，
但不得显示为已完成。当前 T02/T03/T05 公开契约尚未冻结，因此默认 pipeline
adapter 不自行推断这些证明。

为兼容 Wave A 早期的 runner 抽象，旧实现若只返回裸 `upstream_run_id`，会被
集中转换为“无完成证明”的结果并进入待核验；裸字符串绝不等价于 `completed`。

## 4. 持久化、队列与恢复

默认数据库：`${EXPORT_DIR}/.api-state/jobs.sqlite3`。

- `jobs`：请求 hash、状态、stage、时间戳、attempt、上游引用和脱敏错误；
- `job_events`：每次转换、progress 和被拒绝的非法转换；
- SQLite 启用 WAL、foreign keys 和 5 秒 busy timeout；
- 默认 1 worker、有界队列容量 100；
- worker 通过现有 `run_pipeline_with_state` 调用上游，不复制 workflow。
- worker 使用 T08 完成资格门禁保护外部状态，不依据上游函数返回、文件名或
  内部对象自行推断 `completed`。

启动恢复：

- `queued`：重新入队；
- `retrying`：回到 `queued` 后重新入队；
- 遗留 mock `running`：最多重试一次；
- 遗留 real `running`：转为 `failed`，
  `PROCESS_RESTARTED_UNSAFE_TO_RETRY`，防止重复计费。

## 5. Artifact、Version、Feedback 候选契约与当前 503

以下 DTO 保留在 `app/api/contracts.py` 作为未来候选契约。当前五个 operation
只声明实际可达的 400、404、422、500、503，其中 503 schema 指向
`ErrorResponse`；不存在 200/202 unavailable 成功体。

### Artifact

`GET /api/v1/jobs/{job_id}/artifacts`

每项保留 artifact ID、类型、MIME、大小、SHA-256、生成状态、下载 URL，
以及 `planned/expected/mock/actual`。这是未来候选成功 projection；当前请求
返回 503。T08 不依据文件存在推断 `actual`。

### Version

- `GET /api/v1/jobs/{job_id}/versions`
- `GET /api/v1/jobs/{job_id}/versions/diff?from_version_id=...&to_version_id=...`

响应 projection 包含 lineage、反馈 ID、Reviewer issue、关闭状态、评分、
差异和停止原因。这是未来候选成功 projection；当前请求返回 503。只有 T02
可以判定 issue closure。

### Feedback

- `POST /api/v1/jobs/{job_id}/feedback`
- `GET /api/v1/jobs/{job_id}/feedback/{feedback_id}`

请求必须指定目标 version。接受、部分接受、拒绝、决策理由和 resulting
version 均来自 T03；T08 只做校验、传播和展示。请求体继续由
`FeedbackCreateRequest` 校验，但当前有效请求仍返回 503，不返回 202。

## 6. 后续冻结事项

Wave B 接入前仍需 T02/T03/T05/T06 owner 提供可导入、可序列化的公开契约。
在此之前，不允许通过解析内部对象、私有字段或文件命名补齐业务字段。
