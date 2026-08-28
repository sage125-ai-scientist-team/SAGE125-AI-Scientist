# Render Dashboard 必核对项

Blueprint：`render.yaml`  
服务：`sage125-api-preview`、`sage125-ui-preview`  
分支：`integration/2026-08-10`  
plan：free  

本 PR 已在 UI 服务 Blueprint 写入：

- `FRONTEND_API_BASE_URL=https://sage125-api-preview.onrender.com`

若 Dashboard 已有同名变量，以服务级值为准。不要把密钥写入 Git。

## UI 服务应有的非密钥变量

- `APP_ENV=preview`
- `FRONTEND_RUN_VIA_API=1`
- `FRONTEND_API_BASE_URL=https://sage125-api-preview.onrender.com`
- `FRONTEND_API_SHORT_TIMEOUT_SECONDS=10`
- `FRONTEND_API_WAKE_TIMEOUT_SECONDS=75`
- `FRONTEND_INGEST_TIMEOUT_SECONDS=900`

## API 服务

- `healthCheckPath=/health`
- 新增只读 `GET /api/v1/deployment-info` 与 `GET /deployment-info`
- 不得把 `DASHSCOPE_API_KEY` / `WORKSPACE_ID` 写入 Blueprint

## 自动部署

`autoDeployTrigger: off`。合入 `integration/2026-08-10` 且 quality-gates 全绿后，由 `preview-deploy` 调用 Render API。  
不得用自我请求绕过 Free 休眠。
