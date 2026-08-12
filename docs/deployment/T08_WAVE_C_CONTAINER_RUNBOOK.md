# T08 Wave C API + Streamlit 一键容器运行

状态：`IMPLEMENTED / RUNTIME_VERIFICATION_BLOCKED_NO_DOCKER`

分支：`t08/c-delivery-hardening`

## 1. 入口与边界

一键启动两个服务：

| 服务 | 容器入口 | 本地地址 | 健康检查 |
|---|---|---|---|
| API | `python -m scripts.start_api` | `http://127.0.0.1:8000` | `GET /health` |
| UI | `streamlit run frontend/streamlit_app.py` | `http://127.0.0.1:8501` | `GET /_stcore/health` |

Compose 明确启动 T08 API-only B4 页面，不使用 legacy
`app/ui/streamlit_app.py`。

## 2. PowerShell 一键启动

Docker Desktop 启动后，在仓库根执行：

```powershell
docker compose config
docker compose build --no-cache
docker compose up -d --wait
docker compose ps
```

访问：

```text
API health: http://127.0.0.1:8000/health
OpenAPI:    http://127.0.0.1:8000/docs
Streamlit:  http://127.0.0.1:8501
```

默认本地演示 API key：

```text
local-demo-key-change-me
```

它是公开占位值，不是生产密钥。需要自定义时仅在当前 PowerShell 会话设置：

```powershell
$env:SAGE125_DEMO_API_KEY = "replace-with-at-least-12-characters"
docker compose up -d --wait
```

真实模型凭据只作为容器运行时环境变量传入，不写入 Dockerfile 或镜像：

```powershell
$env:DASHSCOPE_API_KEY = "<local-secret>"
$env:WORKSPACE_ID = "<local-workspace>"
docker compose up -d --wait
```

不得把真实值写入 Git、Dockerfile、compose.yaml、日志、截图或本文件。

## 3. Health 函数级契约

### `GET /health`

该端点不再只证明 HTTP 进程存活。它实际探测：

- questions 清单数量；
- RAG index 状态；
- SQLite JobStore 可查询；
- SQLite ArtifactRegistry 可查询；
- artifact root 存在且当前非 root 用户可写；
- 配置声明的 storage 是否为 persistent。

新增响应字段：

```json
{
  "dependencies": {
    "job_store": "available",
    "artifact_registry": "available",
    "artifact_storage": "available"
  }
}
```

只有 questions、RAG 和三个本地持久依赖都可用时，`status` 才为 `ok`。
缺少模型密钥会在 `bailian.status` 中如实显示 `unavailable`，不会切换 Mock，
但不会阻止本地 API/UI 容器用于显式 Mock 演示。

### API 容器 `healthcheck`

Compose 内部 healthcheck 请求 `/health` 并同时要求：

```text
status == ok
storage.persistent == true
job_store == available
artifact_registry == available
artifact_storage == available
```

UI 使用 `depends_on.api.condition=service_healthy`。API 持久依赖未就绪时，
Streamlit 不会被提前标记为可用。

### UI 容器 `healthcheck`

UI 容器请求 Streamlit 自有 `/_stcore/health`，仅 HTTP 200 才视为健康。

## 4. 持久卷

| Named volume | 容器路径 | 持久内容 |
|---|---|---|
| `sage125-data` | `/opt/sage125/data` | questions、上传资料、RAG 数据；与现有 bootstrap 项目根路径一致 |
| `sage125-exports` | `/var/lib/sage125/exports` | exports、JobStore SQLite、Feedback SQLite、ArtifactRegistry SQLite、artifact bytes |
| `sage125-multimodal` | `/var/lib/sage125/multimodal` | T06 三键持久 read store |

JobStore 和 artifact registry 位于同一 export 持久卷的 `.api-state` 子目录；
artifact bytes 位于 `.api-artifacts` 子目录。重启或重新创建容器不会删除 named
volume。

验证卷：

```powershell
docker volume ls --filter "name=sage125"
docker compose restart api
Invoke-RestMethod http://127.0.0.1:8000/health
```

正常停止：

```powershell
docker compose down
```

以上命令保留 named volumes。只有明确确认删除本地演示数据后，才允许执行：

```powershell
docker compose down --volumes
```

## 5. 镜像安全

### 白名单 build context

`.dockerignore` 默认排除整个仓库，仅重新允许：

```text
Dockerfile
requirements.txt
app/**
frontend/**
scripts/**
```

因此 `.env`、`.git`、`.cursor`、测试、docs、本地 data、exports 和缓存都不会进入
Docker build context。

### 白名单镜像 COPY

Dockerfile 只执行：

```text
COPY requirements.txt
COPY app
COPY frontend
COPY scripts
```

不存在 `COPY . .`。

### 非 root 与运行时约束

- 镜像最终 `USER 10001:10001`；
- Compose 再次固定 `user: 10001:10001`；
- root filesystem 为 read-only；
- `/tmp` 使用限额 tmpfs；
- `cap_drop: ALL`；
- `no-new-privileges:true`；
- 仅三个声明的 named volumes 可持久写入。

检查：

```powershell
docker compose exec api id
docker compose exec ui id
docker image inspect sage125-ai-scientist:wave-c `
  --format '{{.Config.User}}'
docker history sage125-ai-scientist:wave-c --no-trunc
```

期望 UID/GID 与镜像用户均为 `10001`。检查输出时不得复制或发布环境变量值。

## 6. API 冒烟

```powershell
$headers = @{
  "X-API-Key" = $env:SAGE125_DEMO_API_KEY
  "X-Correlation-ID" = "wave-c-container-smoke"
}

Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/questions -Headers $headers
Invoke-RestMethod http://127.0.0.1:8000/openapi.json
```

如果没有设置 `$env:SAGE125_DEMO_API_KEY`，使用默认公开演示值：

```powershell
$env:SAGE125_DEMO_API_KEY = "local-demo-key-change-me"
```

## 7. 已知限制

- preview seed 明确标注为 `preview_seed`，不能作为正式 booklet 结果；
- 未配置模型凭据时 real run 必须失败关闭，不得回退为 Mock；
- T01/T02/T05 production read issues 仍在等待 owner；
- T03 status/Gate read 尚未冻结；
- 本文件不替代 5 并发和 2 小时稳定性正式报告；
- 当前直接执行环境没有 `docker` 命令，尚未实际 build/up/inspect；
- Runtime verification 完成前不得把本文状态改为 `VERIFIED`。

## 8. 当前提交前验证记录

实际执行：

```text
docker version
结果：command not found: docker

docker compose config
结果：command not found: docker

ruby YAML.load_file("compose.yaml")
结果：compose yaml parsed

python -m pytest -q tests/api
结果：85 passed, 5 warnings in 14.90s

python -m compileall -q app/api tests/api
结果：exit 0

python scripts/eval/wave_a_quality.py lint
结果：{"check":"wave_a_lint","files":8,"failures":[]}

python scripts/eval/wave_a_quality.py type
结果：{"check":"wave_a_type_contract","failures":[]}

git diff --check -- Dockerfile compose.yaml .dockerignore app/api tests/api docs/deployment
结果：exit 0
```

以上只证明 YAML 可解析、静态容器约束与 API/health 代码通过测试。它不证明：

- 基础镜像和系统包可以下载；
- Python wheels 可在 Linux 镜像安装；
- API/UI 容器实际变为 healthy；
- 非 root 用户对 named volumes 实际可写；
- 容器重建后 SQLite job 与 artifact bytes 仍存在；
- 镜像层扫描无密钥。

这些项必须在安装 Docker Desktop 的 Windows 11 或 T09 指定干净环境中按第 2、4、5
节命令补测，并把输出绑定最终提交 SHA。
