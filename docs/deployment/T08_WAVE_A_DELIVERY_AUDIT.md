# T08 Wave A 交付层盘点与基础冒烟

审计日期：2026-07-28
分支：`t08/a-delivery-contract`
基线提交：`1642ea0`（与 `upstream/integration/2026-08-10` 一致）

## 1. 范围与真源

本次只读盘点覆盖：

- `app/api/**`：FastAPI 应用、路由和 OpenAPI；
- `app/ui/**`：现有 Streamlit 与本地 API 适配，仅审计、不修改；
- `app/exporters/**`：现有 Markdown、HTML、PDF 导出器，仅审计；
- `scripts/api_smoke.py`、`scripts/frontend_smoke.py`：现有进程冒烟；
- `.streamlit/config.toml`、启动日志和本机端口监听；
- `tests/api/**`：本轮新增的基础交付冒烟。

当前 T08 宪法允许写入 `frontend/**`，但仓库现有前端位于 `app/ui/**`。
在 owner 未确认迁移或授权前，本轮不修改 `app/ui/**`，也不复制第二套前端。

## 2. API 路由盘点

| 方法与路径 | 当前实现 | T08 目标差距 |
|---|---|---|
| `GET /health` | 返回配置、RAG、问题数量和模型名；本轮改为依赖异常时 `degraded` | 尚无独立 liveness/readiness 路由和统一响应 DTO |
| `GET /diagnostics` | 返回问题、RAG、配置、最近运行和告警 | 直接依赖 `app.ui.run_browser`，API 与 UI 内部模块耦合 |
| `GET /questions` | 读取 `data/processed/questions_125.json` | 当前文件缺失，返回 `status=missing` 但 HTTP 仍为 200 |
| `POST /ingest` | 上传并写入本地 RAG | 非本轮核心交付接口 |
| `GET /library/status` | 返回文献库状态 | 非本轮核心交付接口 |
| `GET /library/documents` | 返回文献清单 | 非本轮核心交付接口 |
| `DELETE /library/documents/{document_id}` | 删除本地文献 | 非本轮核心交付接口 |
| `GET /preflight` | 真实模式预检 | 同步调用上游预检 |
| `POST /runs` | 同步执行完整 pipeline 后返回 | 不满足异步立即返回 `job_id`、持久状态、幂等和恢复 |
| `GET /runs` | 扫描现有 exports 并返回最近运行 | 不是可恢复的服务端任务状态仓库 |
| `GET /runs/{run_id}` | 读取已落盘报告、证据、trace、质量门 | 不是 job 生命周期/status API |
| `GET /runs/{run_id}/llm-calls` | 返回脱敏调用审计 | 可作为真实性展示的现有基础 |
| `GET /runs/{run_id}/artifacts` | 返回文件名、存在性和大小 | 缺 MIME、checksum、生成状态和权限归属 |
| `POST /runs/{run_id}/feedback` | 直接调用 `app.workflow.pipeline.revise_with_feedback` | 未通过 T03 公开反馈契约；无幂等、身份和版本字段 |
| `GET /runs/{run_id}/export/markdown` | 下载已生成 Markdown | 无统一 export 资源模型与权限检查 |
| `GET /runs/{run_id}/export/pdf` | 现有 PDF 则下载，否则直接调用 WeasyPrint | 绕过 `app.exporters.pdf_exporter` 的 ReportLab 兜底；无 JSON 导出路由 |

缺失的 T08 核心能力：

- 独立 job status、阶段、失败原因、超时和重试状态；
- versions/diff、issue closure、lineage 和停止原因；
- T03 `FeedbackRecord` / `FeedbackDecision` / `GateResult` 适配；
- 统一错误结构、`correlation_id` 和幂等键；
- 最小鉴权、速率限制和下载归属校验；
- PDF/Markdown/JSON 的 canonical report projection。

OpenAPI 由 FastAPI 真实路由生成。实测 `/openapi.json` 和 `/docs` 均返回 200。

## 3. Health 盘点与本轮修正

基线行为：

```json
{
  "status": "ok",
  "rag_index_status": "empty",
  "questions_count": 0
}
```

同一进程的 `/diagnostics` 同时返回 `status=error`，原因为
`data/processed/questions_125.json` 缺失。因此原 `/health` 顶层状态属于硬编码成功。

本轮最小修正：

- `questions_count == 125` 且 `rag_index_status != unavailable` 时返回 `ok`；
- 其他情况返回 `degraded`；
- 保留 HTTP 200，供进程存活探测使用；
- 现有字段继续给出具体依赖状态，不伪造可用性。

未把 Qwen 未配置单独判为服务不可用，因为 Mock 交付入口仍可运行；真实模式能否运行继续由
`qwen_config_loaded` 和 `/preflight` 明确展示。

## 4. Streamlit 盘点

现有入口为 `app/ui/streamlit_app.py`，配置位于 `.streamlit/config.toml`。

已存在的能力：

- 问题选择、运行、证据、研究计划、反馈、导出和开发者诊断视图；
- HTTP API 不可用时的进程内回退；
- `streamlit.testing.v1.AppTest` 可实际执行入口；
- `/` 与 `/_stcore/health` 可用于进程级探测。

主要差距：

- 默认 `FRONTEND_RUN_VIA_API` 未开启时，Streamlit 进程会直接执行完整 pipeline；
- 前端会直接读取本地 `exports`，不是仅消费受权后端 API；
- `session_state` 虽主要保存选择状态，但刷新恢复仍依赖本地 exports 扫描；
- `.streamlit/config.toml` 设置 `showErrorDetails=true`，生产演示存在暴露内部异常细节风险；
- 现有目录 `app/ui/**` 不在本轮 T08 唯一可写前端路径 `frontend/**` 中，需 owner/队长确认后再改。

本轮在 `tests/api/test_delivery_smoke.py` 中使用 AppTest 真正执行入口，
而不是只检查静态 HTML 外壳；实测无 Streamlit exception。

## 5. 导出盘点

现有导出真源分散：

- `app/exporters/markdown_exporter.py`：`ResearchPlan -> Markdown`；
- `app/exporters/html_exporter.py`：`ResearchPlan -> HTML`；
- `app/exporters/pdf_exporter.py`：HTML/Markdown -> PDF，WeasyPrint 失败后回退 ReportLab；
- `app.workflow.artifacts`：额外写出 `report.json` 和其他运行产物；
- API PDF 路由：再次实现一套 Markdown -> WeasyPrint 逻辑；
- Streamlit：通过 `api_client` 直接读取本地文件并提供下载。

因此当前尚未满足“PDF、Markdown、JSON 由同一个 canonical report projection 生成”。
本轮没有修改 `app.workflow/**`、`app/ui/**` 或上游 Schema。

## 6. 启动日志与 8501 端口

仓库没有持久化 `.log` 文件。项目日志由 `app/core/logging.py` 输出到 stdout，
并对疑似 `sk-...` 密钥做掩码；Uvicorn/Streamlit 自身启动日志由各自运行时输出。

实际启动现有 Streamlit：

```text
2026-07-28 14:02:08.624 Uvicorn server started on 0.0.0.0:8501
```

实际监听：

```text
Python 20336 ... TCP *:8501 (LISTEN)
```

探测结果：

```text
GET /               -> 200 text/html; charset=utf-8
GET /_stcore/health -> 200 text/plain; charset=utf-8, body=ok
```

在同一端口启动第二个实例时，精确错误为：

```text
2026-07-28 14:02:28.897 Port 8501 is not available
```

根因与覆盖盲点：

- `.streamlit/config.toml` 未固定 `server.port`，普通启动命令使用默认 8501；
- 旧进程仍监听 8501 时，新进程直接失败；
- `scripts/frontend_smoke.py` 固定使用 8531，所以能证明前端可启动，但不会发现 8501 被占用；
- 现有脚本轮询期间不检查子进程是否提前退出，端口绑定失败时会等满 30 秒才失败。

排障命令：

```text
lsof -nP -iTCP:8501 -sTCP:LISTEN
```

本次验证结束后已正常停止测试实例，8501 无遗留监听。

## 7. 基础冒烟与结果

新增 `tests/api/test_delivery_smoke.py`：

- health 依赖不可用时返回 `degraded`；
- health 基础依赖就绪时返回 `ok`；
- `/health`、`/questions`、`/openapi.json` 可访问；
- OpenAPI 包含 health、questions、runs 和 artifacts；
- Streamlit 入口在 Mock 配置下实际执行且无 exception。

实际结果：

```text
.venv/bin/python -m pytest -q tests/api tests/test_api_smoke.py
9 passed in 0.59s

.venv/bin/python -m pytest -q
241 passed, 35 skipped in 5.65s

.venv/bin/python scripts/api_smoke.py
API smoke summary: {"health": true, "questions": true, "diagnostics": true, "key_leak": false}
RESULT: PASS

.venv/bin/python scripts/frontend_smoke.py
RESULT: PASS
```

全仓 35 个 skip 均带明确原因：缺少 `questions_125.json` 或
`data/raw/sjtu-booklet.pdf`。本轮没有把缺失真源替换成 Mock 数据。

环境注意事项：

- 当前 shell 没有 `python` 命令；
- 系统 `python3` 没有安装 pytest；
- 当前可复现解释器为 `.venv/bin/python`（Python 3.14.5）。

## 8. 建议的下一步

1. 由队长/前端 owner 确认 `app/ui/**` 是否授权 T08 修改，或批准迁移到 `frontend/**`；
2. 与 T02/T03/T05/T06 冻结公开 DTO，避免 API 解析内部文件和对象；
3. 在 `app/api/**` 和 `tests/api/**` 先建立 job DTO、统一错误、幂等与持久状态抽象；
4. 将导出收敛到 `app/export/**` 的 canonical report projection，再接 PDF/MD/JSON；
5. 后续部署阶段为 8501 增加显式端口、healthcheck、PID/端口诊断和干净环境证据。

## 9. 2026-07-28 Wave A 异步骨架更新

本轮后续已实现：

- `/api/v1/jobs` 202 异步创建、任务查询和列表恢复；
- SQLite `jobs` / `job_events` 持久状态、幂等 hash 与状态转换审计；
- 有界进程内 worker、lifespan 启停、Mock/Real 差异化重启恢复；
- `X-Correlation-ID` 生成、校验、响应头传播和 Job 记录；
- v1 统一错误结构；
- Artifact、Version、Feedback OpenAPI projection 与明确 unavailable 响应；
- 旧 `POST /runs` 标记 deprecated，行为保持兼容。
- 完成资格门禁：上游正常返回但缺少产物、质量门、阻断问题、真实性或回链证明时，
  状态停在 `waiting_feedback / awaiting_completion_verification`，不再伪报
  `completed`。

契约和 UI flow 分别见：

- `docs/deployment/T08_API_V1_RFC.md`
- `docs/deployment/T08_UI_FLOW.md`

最新全仓回归：

```text
.venv/bin/python -m pytest -q tests/api
27 passed in 1.29s

.venv/bin/python -m pytest -q
264 passed, 35 skipped in 8.62s
```

完成资格门禁先以缺失 `CompletionEvidence` 的 ImportError 建立红灯，再实现并转绿；
测试覆盖完整证明允许完成、无证明进入待核验、默认 pipeline adapter 不自行推断，
五个证明条件任一缺失均不得完成，以及旧 runner 的裸 run ID 只能进入待核验。

真实进程验证中，`POST /api/v1/jobs` 返回 HTTP 202 和调用方提供的
`X-Correlation-ID`。由于当前缺少 `questions_125.json`，worker 随后如实进入
`failed`，未产生假完成或 Mock 正式结果。

发布前只读审计发现并已关闭以下问题：

- lifespan 测试替身在目标 HTTP 路径前提前失败；
- multipart 解析前 413 响应缺少 `X-Correlation-ID`；
- 测试夹具使用疑似真实密钥形态；
- v1 OpenAPI 成功与失败响应缺少可复制 example；
- 测试证据与当前 Commit 漂移。
