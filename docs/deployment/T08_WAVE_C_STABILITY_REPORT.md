# T08 Wave C 稳定性与恢复报告

状态：`SHORT_HOST_HISTORICAL / FORMAL_120_MIN_WAIT_DOCKER`

2026-08-16 收口：本机仍无 `docker`；`ffmpeg` 可用但无生产闭环可录。
T01 证据读口已在 composition 接通，不改变正式 7200 秒仍 WAIT 的结论。
历史 90 秒短测绑定旧 SHA `5471fbd`，不能当作当前 tip 的定量 PASS。

## 1. 证据有效性

当前短测绑定：

```text
git_sha=5471fbda9729d4c06cf61a923b8c878be693e3ac
worktree_clean=false
runtime=host_synthetic_runner
formal_evidence_valid=false
```

该 SHA 是分支起点，不包含当前未提交实现，因此短测只能作为开发证据，不能作为
最终 Wave C 定量验收。正式证据必须在当前改动提交后、工作区干净时重新生成。

## 2. 宿主机短测结果

### Attempt 1

结果：`FAIL`

原因：探针子进程从 `tests/api` 启动时未把仓库根加入 `sys.path`，API 未启动。

证据：

```text
docs/deployment/evidence/T08_WAVE_C_SHORT_HOST_20260813/
```

精确结果：

```text
requested_duration_seconds=90
elapsed_seconds=31.209
failure_count=1
failure_code=PROBE_EXCEPTION
```

该失败已保留，未删除或改写。

### Attempt 2

结果：`PASS_SHORT`

证据：

```text
docs/deployment/evidence/T08_WAVE_C_SHORT_HOST_20260813_ATTEMPT2/
```

精确指标：

```text
requested_duration_seconds=90
elapsed_seconds=91.258
concurrency=5
failure_count=0
recovery_event_count=2
terminal_jobs_completed=5/5
cross_actor_forbidden=5/5
api_outage_observed=true
ui_survived_api_outage=true
ui_reconnected_after_api_restart=true
max_api_rss_kib=108832
max_ui_rss_kib=70816
api_health_status=degraded
api_persistent_dependencies=3/3 available
resource_leak_result=UNVERIFIED_SHORT_HOST_RUN
```

API RSS 在采样期间由约 `103008 KiB` 增长至 `108832 KiB`；UI 约
`70672–70816 KiB`。90 秒数据不足以判定不存在资源泄漏，因此该项保持
`UNVERIFIED_SHORT_HOST_RUN`，不能写 PASS。

短测使用隔离 synthetic runner，未加载正式 questions/RAG，因此 `/health.status`
如实为 `degraded`；JobStore、ArtifactRegistry、artifact storage 三个持久依赖均为
`available`。正式 Docker 测试必须要求完整 `/health.status=ok`。

### 短测覆盖

- 5 个并发 HTTP job，获得 5 个唯一 job ID；
- actor B 读取 actor A 的 5 个 job，全部返回 403；
- API 进程强制中断，客户端确认 API 不可达；
- API 中断期间 Streamlit health 保持 200；
- API 重启后 UI 根页面重新返回 200；
- SQLite 中断任务经 startup recovery 恢复；
- 5 个 job 最终均为 completed；
- 每 5 秒记录 API/UI RSS、CPU、文件描述符行数、health 和每个 job 状态。

## 3. 原始证据目录

每次 attempt 均保存：

```text
api-initial.log
api-restart.log（成功进入重启阶段时）
ui.log（成功启动 UI 时）
metrics.json
reproduction.txt
summary.md
```

`metrics.json` 是机器真源；`summary.md` 不覆盖原始失败或样本。

## 4. 复现短测

Windows 11 PowerShell：

```powershell
py tests/api/wave_c_stability_probe.py run `
  --duration-seconds 90 `
  --concurrency 5 `
  --sample-interval-seconds 5 `
  --output-dir docs/deployment/evidence/T08_WAVE_C_SHORT_HOST_REPRO
```

探针使用 deterministic synthetic runner，不调用外部模型，不把 Mock 结果标成正式科研结果。

## 5. 120 分钟 Docker 正式测试前置条件

必须同时满足：

1. 当前改动已提交；
2. `git status --porcelain` 无输出；
3. 已记录最终 `git rev-parse HEAD`；
4. Docker Desktop 正常；
5. `docker compose config` 与 `docker compose build --no-cache` 成功；
6. API 和 UI 均为 healthy；
7. 输出目录为空且带最终 SHA；
8. 使用两个仅限本地测试的 actor key；
9. 不使用旧短测日志覆盖正式证据。

当前环境缺少 `docker`，因此正式测试保持 WAIT。

## 6. PowerShell 正式测试流程

### 6.1 初始化并绑定 SHA

```powershell
$ErrorActionPreference = "Stop"
$sha = (git rev-parse HEAD).Trim()
$dirty = git status --porcelain
if ($dirty) { throw "Formal evidence requires a clean worktree." }

$evidence = "docs/deployment/evidence/T08_WAVE_C_FORMAL_$sha"
New-Item -ItemType Directory -Path $evidence -ErrorAction Stop | Out-Null

$env:SAGE125_DEMO_API_KEY = "local-formal-actor-a-key"
$env:SAGE125_ISOLATION_API_KEY = "local-formal-actor-b-key"

"git_sha=$sha" | Set-Content "$evidence\run-metadata.txt"
"started_at=$([DateTimeOffset]::UtcNow.ToString('o'))" |
  Add-Content "$evidence\run-metadata.txt"
```

### 6.2 构建和启动

```powershell
docker compose config | Set-Content "$evidence\compose-config.txt"
docker compose build --no-cache *>&1 |
  Tee-Object "$evidence\build.log"
docker compose up -d --wait *>&1 |
  Tee-Object "$evidence\startup.log"
docker compose ps --format json |
  Set-Content "$evidence\compose-ps-start.jsonl"
```

### 6.3 5 并发与跨 actor

使用 actor A 同时提交 Q001–Q005，保存五个 job ID。随后使用
`local-formal-actor-b-key` 查询每个 job，必须全部得到 HTTP 403。任何非 403 都计入
`failure_count`。

### 6.4 断网

```powershell
$api = (docker compose ps -q api).Trim()
$network = (
  docker inspect $api --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}'
).Trim()

docker network disconnect $network $api
# 记录 UI /_stcore/health；同时确认 UI 到 API 的调用失败关闭。
docker network connect $network $api
```

必须保存 disconnect/connect 命令输出、UI health 和 API 不可达证据。不得把超时写成成功。

### 6.5 API 强制重启、队列恢复与 UI 重连

在至少一个 job 为 running、其余为 queued 时执行：

```powershell
docker compose kill -s SIGKILL api
docker compose up -d --wait api
Invoke-RestMethod http://127.0.0.1:8501/_stcore/health
Invoke-WebRequest http://127.0.0.1:8501
```

重启后逐个查询原 job ID；job 不得消失、串题或跨 actor 可见。Mock running job 只允许按
有限重试语义恢复，real job 不允许不安全自动重放。

### 6.6 7200 秒采样

```powershell
$deadline = [DateTimeOffset]::UtcNow.AddMinutes(120)
$failureCount = 0

while ([DateTimeOffset]::UtcNow -lt $deadline) {
  $at = [DateTimeOffset]::UtcNow.ToString("o")
  try {
    $health = Invoke-RestMethod http://127.0.0.1:8000/health
    if ($health.status -ne "ok") { $failureCount++ }
  } catch {
    $failureCount++
    $_ | Out-String | Add-Content "$evidence\request-errors.log"
  }

  docker stats --no-stream --format '{{json .}}' `
    (docker compose ps -q api) (docker compose ps -q ui) |
    Add-Content "$evidence\docker-stats.jsonl"

  [ordered]@{
    at = $at
    failure_count = $failureCount
    health = $health
  } | ConvertTo-Json -Depth 8 -Compress |
    Add-Content "$evidence\health-samples.jsonl"

  Start-Sleep -Seconds 60
}
```

结束时必须写入：

```powershell
"ended_at=$([DateTimeOffset]::UtcNow.ToString('o'))" |
  Add-Content "$evidence\run-metadata.txt"
"failure_count=$failureCount" |
  Add-Content "$evidence\run-metadata.txt"
docker compose logs --no-color |
  Set-Content "$evidence\compose.log"
docker compose ps --format json |
  Set-Content "$evidence\compose-ps-end.jsonl"
```

## 7. 正式 PASS 条件

只有同时满足以下条件才可将状态改为 PASS：

- 实际持续时间不少于 7200 秒；
- 最终 SHA 与 clean worktree 已记录；
- 5 个并发 job 身份和状态均不丢失；
- 跨 actor 访问 5/5 被拒绝；
- 断网期间 UI/API 明确失败关闭，恢复后可重新连接；
- API 强制重启后队列按冻结语义恢复；
- health 请求失败数为 0；
- 无容器重启循环；
- RSS、PID/线程、文件描述符没有持续无界增长；
- SQLite 和 artifact named volume 在容器重建后仍可读取；
- 原始日志无密钥、绝对私有路径或伪造 actual 结果。

当前结论：

```text
SHORT_HOST=PASS
FORMAL_120_MIN=WAIT
FINAL_SHA_BOUND=NO
CONTENT_COMPLIANCE=FAIL
```
