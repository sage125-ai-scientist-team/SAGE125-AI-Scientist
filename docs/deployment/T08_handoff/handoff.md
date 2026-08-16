# T08 Wave C Handoff

状态：`T08_OWNED_CLOSEOUT / EXTERNAL_GATES_WAIT`

## Purpose

T08 提供鉴权异步 API、API-only Streamlit 控制台、受控产物/导出、T03 反馈提交、
T01 证据读取、T06 多模态投影、容器配置和发布证据。T08 不拥有科研结论。

## Entry points

```text
API:      python -m scripts.start_api
Streamlit: streamlit run frontend/streamlit_app.py
Compose:  docker compose up -d --wait
```

Windows 11 PowerShell：

```powershell
py -m scripts.start_api
streamlit run frontend/streamlit_app.py
docker compose up -d --wait
```

## Key classes and functions

- `app.api.main.create_app`：composition root；lifespan 先 `ensure_preview_catalog()`
- `app.api.preview_catalog.ensure_preview_catalog`：preview 题库写入 `DATA_DIR`
- `app.api.job_store.SQLiteJobStore`：可恢复 job/event
- `app.api.owner_composition.ComposedOwnerContractAdapter`：T07 题单 + T01 证据
- `app.api.owner_composition.T03FeedbackSubmitAdapter`：只 submit
- `app.api.owner_composition.T06MultimodalReadAdapter`：冻结 T06 详情
- `app.export.service.ExportService`：canonical JSON/Markdown/PDF

## Configuration

- API auth: `SAGE_API_KEYS_JSON`
- UI: `SAGE_UI_API_BASE_URL`, `SAGE_UI_API_KEY`
- 持久根: `DATA_DIR`, `EXPORT_DIR`, `T06_MULTIMODAL_STORE_DIR`
- Preview: `APP_ENV=preview` 或 `SAGE125_PREVIEW_SEED` 或 `PREVIEW_EPHEMERAL_STORAGE`
- 模型密钥只在运行时注入，不进镜像

See:

- `../T08_WAVE_C_CONTAINER_RUNBOOK.md`
- `../T08_WAVE_C_OWNER_COMPOSITION.md`
- `../T08_WAVE_C_API_INTERFACE.md`
- `../T08_WAVE_C_CLOSEOUT.md`

## Verification

本轮 T08 可做项收口后重新记录。精确命令和数字以
`acceptance_evidence/test_output.md` 为准；未跑过的项保持 WAIT。

```text
production T01 evidence read: CONNECTED
production T03 feedback submit: CONNECTED
production T06 multimodal read: CONNECTED
production T02 versions/diff: 503 WAIT
production T03 feedback GET / Gate: 503 WAIT
production T05 / canonical report: 503 WAIT
Docker runtime: WAIT_NO_DOCKER
120-minute stability: WAIT_NO_DOCKER
T07 / T09 sign-off: WAIT
PR-C Ready: NO
```

## Truth boundary

浏览器和 PDF 包里的合成 rehearsal 只证明 UI 行为、失败关闭和导出排版。
它们不证明生产 owner 全闭环、真实执行或反馈已生成新版本。

## Open blockers

- T02 version/diff：Issue #53
- T05 execution/history：Issue #54
- T03 status/decision/Gate 读口未冻结
- 本机无 Docker，正式 7200 秒与干净部署未跑
- T07 配对审查、T09 部署验收未签字
- #41 Render 热修仍需作者迁到 T08 路径

## Final acceptance rule

在最终干净 SHA 上完成生产浏览器 E2E、Docker 干净部署、7200 秒稳定性、
T07 和 T09 签字之前，本包必须保持 `WAIT`。fixture 截图和 planned PDF
不得替换这些门禁。
