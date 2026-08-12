# T08 Wave B API v1 示例（Windows PowerShell）

状态：`REPRODUCIBLE_DRAFT / PRODUCTION_OWNER_PORTS_PENDING`

## 1. 启动

示例 key 必须与 `SAGE_API_KEYS_JSON` 对应；不要把真实 key 写入仓库、日志或截图。

```powershell
$env:SAGE_API_KEYS_JSON = '{"judge":"replace-with-at-least-12-characters"}'
$env:SAGE_API_BASE = "http://127.0.0.1:8000"
$env:SAGE_API_KEY = "replace-with-at-least-12-characters"

python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

以下命令在另一个 PowerShell 窗口执行。

## 2. 健康、OpenAPI 与问题列表

```powershell
Invoke-RestMethod "$env:SAGE_API_BASE/health"
Invoke-RestMethod "$env:SAGE_API_BASE/openapi.json"

$headers = @{"X-API-Key" = $env:SAGE_API_KEY}
Invoke-RestMethod `
  -Headers $headers `
  "$env:SAGE_API_BASE/api/v1/questions?limit=5"
```

`questions` 的 `availability=partial` 表示 owner 未提供完整状态，不等于 API 失败。

## 3. 创建任务与查询状态

```powershell
$runHeaders = @{
  "X-API-Key" = $env:SAGE_API_KEY
  "Idempotency-Key" = "judge-run-001"
  "Content-Type" = "application/json"
}
$body = @{
  question_id = "Q001"
  mode = "mock"
  options = @{
    use_deep_research = $true
    use_open_literature = $true
    use_local_rag = $true
    reviewer_auto_revision = $true
  }
} | ConvertTo-Json -Depth 4

$accepted = Invoke-RestMethod `
  -Method Post `
  -Headers $runHeaders `
  -Body $body `
  "$env:SAGE_API_BASE/api/v1/jobs"
$env:JOB_ID = $accepted.job_id

Invoke-RestMethod `
  -Headers $headers `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID"
```

重复相同 key 和 payload 应复用原 job；不同 payload 或不同 actor 使用相同 key 返回
`409 IDEMPOTENCY_CONFLICT`。

## 4. Owner 读取接口

```powershell
Invoke-RestMethod -Headers $headers `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/evidence"

Invoke-RestMethod -Headers $headers `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/versions"

Invoke-RestMethod -Headers $headers `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/versions/diff?from_version_id=run-1%3Av1&to_version_id=run-1%3Av2"

Invoke-RestMethod -Headers $headers `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/report"
```

当前默认 production composition 的预期结果：

- 尚无 `upstream_run_id`：`409 UPSTREAM_RESULT_NOT_READY`；
- owner port 未注入：`503 UPSTREAM_CONTRACT_UNAVAILABLE`；
- canonical source 未注入：`503 CANONICAL_REPORT_UNAVAILABLE`；
- run/question identity 不一致：`409 UPSTREAM_IDENTITY_MISMATCH`。

这些失败是 fail-closed 门禁，不应改成占位 200。

## 5. Feedback

```powershell
$feedbackHeaders = @{
  "X-API-Key" = $env:SAGE_API_KEY
  "Idempotency-Key" = "judge-feedback-001"
  "Content-Type" = "application/json"
}
$feedbackBody = @{
  target_version_id = "run-1:v1"
  feedback = "请补充可证伪阈值和对应证据。"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Headers $feedbackHeaders `
  -Body $feedbackBody `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/feedback"
```

在 T03 production orchestration 合入前，该请求必须返回
`503 UPSTREAM_CONTRACT_UNAVAILABLE`，不能由 T08 创建 decision。

## 6. Artifact 与导出

```powershell
Invoke-RestMethod -Headers $headers `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/artifacts"

$exportHeaders = @{
  "X-API-Key" = $env:SAGE_API_KEY
  "Idempotency-Key" = "judge-export-001"
  "Content-Type" = "application/json"
}
Invoke-RestMethod `
  -Method Post `
  -Headers $exportHeaders `
  -Body '{"formats":["json","markdown","pdf"]}' `
  "$env:SAGE_API_BASE/api/v1/jobs/$env:JOB_ID/exports"
```

默认 production canonical source 尚未接通，因此 export 预期 503。测试中注入的
`StaticCanonicalReportSource` 只验证 JSON/Markdown/PDF 一致性，不是生产数据。

## 7. 安全边界

- 不在命令历史中使用真实生产 key；本文件仅使用占位值。
- Job、artifact 与幂等请求按 actor 隔离。
- 下载 URL 只接受 artifact ID，不接受服务器路径。
- API 错误不返回 traceback、绝对路径、环境变量或 owner 私有对象。

