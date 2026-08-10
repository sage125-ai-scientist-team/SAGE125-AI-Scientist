# T08 Wave B4：API-only 前端闭环

## 启动

前端只通过冻结的 `/api/v1/**` HTTP 契约读取和提交数据，不导入科研流水线，也不扫描本地 `exports`。API key 仅从服务端进程环境读取，不进入页面表单或 `session_state`。

```bash
export SAGE_UI_API_KEY='replace-with-configured-api-key'
export SAGE_UI_API_BASE_URL='http://127.0.0.1:8000'
python -m streamlit run frontend/streamlit_app.py \
  --server.address 127.0.0.1 \
  --server.port 8501
```

可选的 `SAGE_UI_TIMEOUT_SECONDS` 默认为 10 秒。生产 API 必须使用与 `SAGE_API_KEYS_JSON` 对应的 key。

## 闭环和恢复

页面按以下阶段消费服务端真源：

```text
问题 → run → status → evidence → Reviewer / versions / diff
     → feedback → decision → resulting version → Gate
     → execution / multimodal → canonical export / artifact download
```

当前 `job_id` 和最近一次 `feedback_id` 写入 URL query。刷新或重连后，页面使用这些标识重新查询 API；`session_state` 不保存任务真源。侧栏最近任务也来自 `GET /api/v1/jobs`。

各阶段显式覆盖初始、加载、空、失败、超时、无权限、不可用、stale 和低置信度状态。API 失败时不回退到旧缓存、进程内 pipeline 或本地导出文件；未返回 `actual_execution=true` 时只显示 `NOT ACTUAL`。

## 新增读取投影

```text
GET /api/v1/jobs/{job_id}/report
```

该接口与 PDF、Markdown、JSON 导出共用同一个 `CanonicalReportSource`，供前端读取 Validation Gate、执行和多模态投影。它会校验 `job_id`、`question_id`、`run_id` 一致性；生产未注入 owner adapter 时返回 `503 CANONICAL_REPORT_UNAVAILABLE`，不会读取旧导出冒充结果。

反馈写入仍由 T03 公共契约拥有。当前生产默认 adapter 未冻结时会返回明确的 `503 UPSTREAM_CONTRACT_UNAVAILABLE`；浏览器闭环中的 accepted decision / resulting version 仅使用临时 HTTP 契约桩验证前端行为，不能作为 T03 集成完成证据。

## 验收

```bash
python -m pytest -q tests/api/test_frontend_b4.py
python -m pytest -q tests/api
python -m pytest -q
python -m compileall -q app/api app/export frontend tests/api
git diff --check
```

浏览器验收至少验证：任务创建后请求立即返回、状态刷新、低置信度警告、Reviewer issue、结构化 diff、反馈决策与新版本、Gate、`NOT ACTUAL`、多模态 bbox/单位、API 导出和受控下载；随后刷新页面确认 job 恢复，并用不存在的 job 验证统一失败态不泄露 traceback 或旧证据。
