# T08 Wave C API 接口文档

状态：`PRODUCTION_COMPOSITION_PARTIAL / FAIL_CLOSED`

适用分支：`t08/c-delivery-hardening`（PR #56）

本文只描述 T08 对外 HTTP 契约和 T08 自己的 composition 函数。上游算法、
Reviewer 判定、Gate 规则和真实执行判定不属于 T08。Context7 MCP 当前不可用，
字段以仓库源码 `app/api/v1.py`、`app/api/preview_catalog.py`、
`app/api/owner_composition.py` 为准。

Windows 11 PowerShell 通用前缀：

```powershell
$base = "http://127.0.0.1:8000"
$headers = @{
  "X-API-Key" = $env:SAGE_API_KEY
  "X-Correlation-ID" = [guid]::NewGuid().ToString()
}
```

统一失败信封：

```json
{
  "code": "STABLE_MACHINE_CODE",
  "message": "面向调用方的简洁说明",
  "details": {},
  "correlation_id": "...",
  "retryable": false
}
```

---

## 1. 运行时题库函数

文件：`app/api/preview_catalog.py`

### `preview_seed_allowed() -> bool`

判断当前进程能不能写 preview seed。仅当 `SAGE125_PREVIEW_SEED`、
`APP_ENV=preview` 或 `PREVIEW_EPHEMERAL_STORAGE` 为真时返回 True。
正式环境和 booklet gold 不得走这条路径。

### `configured_data_dir() -> Path`

解析可写数据根。显式环境变量 `DATA_DIR` 优先于 settings 默认值。
相对路径相对仓库根展开。

### `writable_catalog_path() -> Path`

返回 T08 应写入的题库路径：`DATA_DIR/processed/questions_125.json`。
不保证父目录已经存在。

### `repository_catalog_path() -> Path`

返回只读回退路径 `<repo>/data/processed/questions_125.json`。
Render 上该路径通常不可写，不能当作 preview 真源。

### `resolve_runtime_questions_path() -> Path`

按优先级解析运行时题库，不创建文件：

1. 已设置的 `SAGE_QUESTIONS_PATH`
2. 已存在的 `DATA_DIR` 题库
3. 已存在的仓库题库（仅当未显式设置 `DATA_DIR`）
4. 可写 `DATA_DIR` 目标（即使尚不存在）

### `catalog_is_usable(path: Path, *, expected: int = 125) -> bool`

检查路径是否存在、可解析，且列表长度等于 `expected`。
解析失败返回 False，不抛给调用方。

### `write_preview_catalog(path: Path) -> Path`

调用已有 `scripts.bootstrap_preview_data.build_preview_seed_questions`，
要求 125 条且每条 `preview_seed=true`，写入 `path`。
不拥有 booklet 抽取，不改 `scripts/**`。

### `ensure_preview_catalog() -> Path | None`

`create_app` lifespan 启动时调用。已有合法题库则导出 `SAGE_QUESTIONS_PATH`；
预览开关打开且缺失则写入 `DATA_DIR`；非预览缺失返回 None，
`/health.questions_count` 保持 0。

---

## 2. Composition 函数

文件：`app/api/owner_composition.py`

### `OwnerPortFailure`

T08 路由层可安全映射的 owner 失败。字段：`component`、`category`、`retryable`。
禁止把 owner 绝对路径或内部表名放进 `message`。

### `T01EvidenceReadAdapter.get_evidence_bundle(*, run_id, question_id) -> EvidenceBundle`

只调用 `app.evidence.read_port.get_evidence_bundle`。
空 store 映射 404，不返回空成功列表，不读 T01 私有 SQLite schema。

### `ComposedOwnerContractAdapter`

默认 `upstream_read_port`。T07 问题清单走文件系统；T01 证据走上面的适配器；
T02 versions/diff 继续 `OwnerContractUnavailable`。

### `T03FeedbackSubmitAdapter.submit(...) -> FeedbackSubmissionResult`

只调用 T03 `DefaultFeedbackService.submit_request`。
成功表示已持久化 `submitted`，不表示 accepted，不生成 resulting version，
不重算 Gate。

### `T06MultimodalReadAdapter.list_details(...)`

只调用 `app.multimodal.read_port.list_multimodal_details`。
保留 bbox、单位、坐标轴、图例、置信度和人工核验标记。
空集合是 200 + `items=[]`，不是 404。

---

## 3. HTTP 路由与当前生产行为

| 方法 | 路径 | 当前生产 | 说明 |
|---|---|---|---|
| GET | `/health` | 200 | 真实依赖计数；preview 题库来自 `DATA_DIR` |
| GET | `/openapi.json` | 200 | 由 FastAPI 生成，不手写第二份 |
| GET | `/questions` | 200 / 空 | 与 v1 同一 `resolve_runtime_questions_path` |
| GET | `/api/v1/questions` | 200 | 需 `X-API-Key` |
| POST | `/api/v1/jobs` | 202 | 异步；立即返回 `job_id` |
| GET | `/api/v1/jobs/{job_id}` | 200 / 403 / 404 | 跨 actor 403 |
| GET | `/api/v1/jobs/{job_id}/evidence` | 200 / 404 / 409 / 503 | T01 已接 |
| GET | `/api/v1/jobs/{job_id}/multimodal` | 200 / 409 / 503 | T06 已接 |
| POST | `/api/v1/jobs/{job_id}/feedback` | 202 / 403 / 409 / 422 / 503 | 只 submit |
| GET | `/api/v1/jobs/{job_id}/feedback/{id}` | **503** | T03 读口未冻结 |
| GET | `/api/v1/jobs/{job_id}/versions` | **503** | T02 Issue #53 |
| GET | `/api/v1/jobs/{job_id}/versions/diff` | **503** | T02 Issue #53 |
| GET | `/api/v1/jobs/{job_id}/report` | **503** | T05 / canonical source |
| GET | `/api/v1/jobs/{job_id}/artifacts` | 200 | 登记表，不等于 actual execution |
| POST | `/api/v1/jobs/{job_id}/exports` | 202 / **503** | canonical 未注入则失败关闭 |

### `GET /health`

```powershell
Invoke-RestMethod "$base/health"
```

关注字段：`status`、`questions_count`、`persistent`。
Preview 且 `DATA_DIR` 可写时，`questions_count` 应为 125。
不得把 `degraded` 改写成 `ok`。

### `GET /api/v1/questions`

```powershell
Invoke-RestMethod "$base/api/v1/questions?limit=5" -Headers $headers
```

### `POST /api/v1/jobs`

```powershell
$run = $headers.Clone()
$run["Idempotency-Key"] = "judge-run-Q001-v1"
Invoke-RestMethod -Method Post -Uri "$base/api/v1/jobs" `
  -Headers $run -ContentType "application/json" `
  -Body '{"question_id":"Q001","mode":"mock","options":{}}'
```

长任务不得阻塞该请求。重复幂等键必须回到同一 `job_id`。

### `GET /api/v1/jobs/{job_id}/evidence`

```powershell
Invoke-RestMethod "$base/api/v1/jobs/$jobId/evidence" -Headers $headers
```

成功时保留 quote、locator、作者、年份、DOI/URL、content hash、支持关系。
T01 空 store：404 `UPSTREAM_RESOURCE_NOT_FOUND`。

### `POST /api/v1/jobs/{job_id}/feedback`

```powershell
$fb = $headers.Clone()
$fb["Idempotency-Key"] = "judge-feedback-001"
Invoke-RestMethod -Method Post -Uri "$base/api/v1/jobs/$jobId/feedback" `
  -Headers $fb -ContentType "application/json" `
  -Body '{"target_version_id":"v1","feedback":"请补充可证伪阈值。"}'
```

202 只表示 T03 已保存。`decision_reason` 与 `resulting_version_id` 现为 null。

### 仍失败关闭的读口

```powershell
# 预期 503 UPSTREAM_CONTRACT_UNAVAILABLE
Invoke-RestMethod "$base/api/v1/jobs/$jobId/versions" -Headers $headers
Invoke-RestMethod "$base/api/v1/jobs/$jobId/versions/diff?from_version_id=run:v1&to_version_id=run:v2" -Headers $headers
Invoke-RestMethod "$base/api/v1/jobs/$jobId/feedback/$feedbackId" -Headers $headers
Invoke-RestMethod "$base/api/v1/jobs/$jobId/report" -Headers $headers
```

---

## 4. 前端函数

文件：`frontend/view_models.py`

### `empty_question_catalog_message() -> str`

空题库时的操作员文案。指向 `DATA_DIR/processed/questions_125.json`，
禁止暗示去写只读仓库 `data/processed`。前端不补种、不读本地文件。

---

## 5. 鉴权与限制

- 服务端校验 `X-API-Key`；页面隐藏按钮不等于授权。
- 下载、反馈、创建任务、查询私有 job 都检查 actor。
- 跨 actor 读 job 返回 403。
- `Idempotency-Key` 不能跨 actor 复用。
- 速率限制与请求体上界由现有 API 中间件执行。

## 6. 验证命令

```powershell
py -m pytest -q tests/api/test_preview_catalog.py
py -m pytest -q tests/api/test_owner_composition.py
py -m pytest -q tests/api/test_frontend_b4.py
py -m pytest -q tests/api
```

macOS / zsh 对等命令：

```text
python -m pytest -q tests/api
```
