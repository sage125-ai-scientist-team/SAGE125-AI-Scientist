# T08 API v1 RFC — Job/Status 与交付 Projection

状态：Wave A 冻结候选
日期：2026-07-28
前缀：`/api/v1`

## 1. 边界

API v1 拥有 HTTP DTO、任务调度状态、幂等、correlation 和错误映射。
它不拥有科学结论、Reviewer 判定、质量门、真实执行判定或多模态抽取。

当前实际接通 Job/Status。Artifact、Version、Feedback 路由用于冻结 OpenAPI
形状，在对应 owner 的公开契约可用前返回：

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

`job_id` 是 T08 任务 ID。pipeline 生成的 `run_id` 只在完成后出现在
`upstream_run_id`，不得把两者当作同一标识。

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

`stage` 来自真实 worker/pipeline 事件。API 不根据耗时生成百分比。

## 4. 持久化、队列与恢复

默认数据库：`${EXPORT_DIR}/.api-state/jobs.sqlite3`。

- `jobs`：请求 hash、状态、stage、时间戳、attempt、上游引用和脱敏错误；
- `job_events`：每次转换、progress 和被拒绝的非法转换；
- SQLite 启用 WAL、foreign keys 和 5 秒 busy timeout；
- 默认 1 worker、有界队列容量 100；
- worker 通过现有 `run_pipeline_with_state` 调用上游，不复制 workflow。

启动恢复：

- `queued`：重新入队；
- `retrying`：回到 `queued` 后重新入队；
- 遗留 mock `running`：最多重试一次；
- 遗留 real `running`：转为 `failed`，
  `PROCESS_RESTARTED_UNSAFE_TO_RETRY`，防止重复计费。

## 5. Artifact、Version、Feedback 冻结契约

### Artifact

`GET /api/v1/jobs/{job_id}/artifacts`

每项保留 artifact ID、类型、MIME、大小、SHA-256、生成状态、下载 URL，
以及 `planned/expected/mock/actual`。T08 不依据文件存在推断 `actual`。

### Version

- `GET /api/v1/jobs/{job_id}/versions`
- `GET /api/v1/jobs/{job_id}/versions/diff?from_version_id=...&to_version_id=...`

响应 projection 包含 lineage、反馈 ID、Reviewer issue、关闭状态、评分、
差异和停止原因。只有 T02 可以判定 issue closure。

### Feedback

- `POST /api/v1/jobs/{job_id}/feedback`
- `GET /api/v1/jobs/{job_id}/feedback/{feedback_id}`

请求必须指定目标 version。接受、部分接受、拒绝、决策理由和 resulting
version 均来自 T03；T08 只做校验、传播和展示。

## 6. 后续冻结事项

Wave B 接入前仍需 T02/T03/T05/T06 owner 提供可导入、可序列化的公开契约。
在此之前，不允许通过解析内部对象、私有字段或文件命名补齐业务字段。
