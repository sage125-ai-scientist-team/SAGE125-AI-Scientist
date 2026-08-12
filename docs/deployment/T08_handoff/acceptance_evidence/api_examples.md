# Final API Examples

状态：`CONTRACT_VERIFIED / PRODUCTION_OWNER_PORTS_WAIT`

PowerShell setup:

```powershell
$base = "http://127.0.0.1:8000"
$headers = @{
  "X-API-Key" = "local-demo-key-change-me"
  "X-Correlation-ID" = "judge-demo-001"
}
```

Health and OpenAPI:

```powershell
Invoke-RestMethod "$base/health"
Invoke-RestMethod "$base/openapi.json"
```

Questions:

```powershell
Invoke-RestMethod "$base/api/v1/questions?limit=5" -Headers $headers
```

Create one idempotent job:

```powershell
$runHeaders = $headers.Clone()
$runHeaders["Idempotency-Key"] = "judge-run-Q001-v1"
$job = Invoke-RestMethod `
  -Method Post `
  -Uri "$base/api/v1/jobs" `
  -Headers $runHeaders `
  -ContentType "application/json" `
  -Body '{"question_id":"Q001","mode":"mock","options":{}}'
```

Read status:

```powershell
Invoke-RestMethod "$base/api/v1/jobs/$($job.job_id)" -Headers $headers
```

Evidence, versions, diff, and multimodal:

```powershell
Invoke-RestMethod "$base/api/v1/jobs/$($job.job_id)/evidence" -Headers $headers
Invoke-RestMethod "$base/api/v1/jobs/$($job.job_id)/versions" -Headers $headers
Invoke-RestMethod `
  "$base/api/v1/jobs/$($job.job_id)/versions/diff?from_version_id=run-id:v1&to_version_id=run-id:v2" `
  -Headers $headers
Invoke-RestMethod `
  "$base/api/v1/jobs/$($job.job_id)/multimodal?version_id=run-id:v2" `
  -Headers $headers
```

Feedback submit:

```powershell
$feedbackHeaders = $headers.Clone()
$feedbackHeaders["Idempotency-Key"] = "judge-feedback-001"
Invoke-RestMethod `
  -Method Post `
  -Uri "$base/api/v1/jobs/$($job.job_id)/feedback" `
  -Headers $feedbackHeaders `
  -ContentType "application/json" `
  -Body '{"target_version_id":"v1","feedback":"Add a falsification threshold."}'
```

The current production feedback status endpoint remains 503 until the owner read
port is frozen. Do not treat submit as accepted or as a resulting version.

Three-format export:

```powershell
$exportHeaders = $headers.Clone()
$exportHeaders["Idempotency-Key"] = "judge-export-001"
Invoke-RestMethod `
  -Method Post `
  -Uri "$base/api/v1/jobs/$($job.job_id)/exports" `
  -Headers $exportHeaders `
  -ContentType "application/json" `
  -Body '{"formats":["json","markdown","pdf"]}'
```

Never place real API keys in this file, shell history, screenshots, or exported reports.
