# T08 Wave C Closeout — T08 可做项收口

状态：`T08_OWNED_CLOSEOUT / EXTERNAL_GATES_WAIT`

日期：2026-08-16

分支：`t08/c-delivery-hardening`

PR-C：https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/56

本文件只记录 **T08 owner 路径上能做完的事项**。它不是 Wave C Definition of Done
通过声明，也不把 Docker / 2 小时 / T07 / T09 / 上游生产读口写成 PASS。

## 1. 判定规则

- `DONE`：T08 已实现、已测或已写成可复现命令，且不依赖缺失的运行时。
- `WAIT_ENV`：T08 脚本和文档已齐，当前机器缺少 Docker / 干净第二环境。
- `WAIT_OWNER`：必须等 T02 / T03 读口 / T05 冻结端口，T08 不得抄内部实现。
- `WAIT_EXTERNAL`：必须由 T07、T09 或队长签字，T08 不得代填 PASS。

## 2. T08 已收口

| 项 | 状态 | 证据 |
|---|---|---|
| Draft PR-C | `DONE` | #56 Draft，base `integration/2026-08-10` |
| Dockerfile / compose / healthcheck / 卷 / `.dockerignore` | `DONE` | 静态测试 `tests/api/test_wave_c_container.py` |
| `.env` 使用说明 | `DONE` | `T08_handoff/config_example.md`、`T08_WAVE_C_CONTAINER_RUNBOOK.md` |
| T01 `get_evidence_bundle` 薄适配 | `DONE` | `owner_composition.py` + `tests/api/test_owner_composition.py` |
| T03 feedback **submit** | `DONE` | 同一文件；`GET` 仍 503 |
| T06 multimodal read | `DONE` | `list_multimodal_details` 薄适配 |
| Preview 题库写入 `DATA_DIR` | `DONE` | `app/api/preview_catalog.py`；实现备份供 #41 cherry-pick |
| 前端空题库提示 | `DONE` | `frontend.streamlit_app.empty_question_catalog_message` |
| 5 并发宿主机短测 | `DONE`（非正式） | 90s probe，`formal_evidence_valid=false` |
| 合成浏览器 rehearsal / PDF QA | `DONE`（非正式） | fixture，不得当生产 E2E |
| `tests/api` | `DONE` | **102 passed**, 5 warnings, 9.30s |
| 接口文档 | `DONE` | `T08_WAVE_C_API_INTERFACE.md` |
| 回滚说明 | `DONE` | `T08_handoff/rollback.md` |
| 演示 runbook 草稿 | `DONE` | 标明 synthetic |

## 3. T08 文档和脚本已齐、本机做不了

| 项 | 状态 | 原因 |
|---|---|---|
| `docker compose` 干净构建与启动 | `WAIT_ENV` | 本机 `docker: command not found` |
| 镜像密钥扫描 / 非 root / 卷重启 | `WAIT_ENV` | 同上 |
| 第二干净环境 | `WAIT_ENV` | 需 T09 或另一台有 Docker 的机器 |
| 正式 7200 秒稳定性 | `WAIT_ENV` | 探针写明不能用宿主机短测替代 |
| 资源泄漏 PASS | `WAIT_ENV` | 90s 不足；正式项绑 Docker |
| 备用录屏 | `WAIT_ENV` | `ffmpeg` 已有，但无生产闭环可录；禁止用 fixture 冒充 |

## 4. 必须等 owner / 外部

| 项 | 状态 | 阻塞 |
|---|---|---|
| T02 versions / diff 生产读 | `WAIT_OWNER` | Issue #53；integration 无 T02 `read_port.py` |
| T03 feedback GET / decision / Gate | `WAIT_OWNER` | 读口未冻结 |
| T05 execution / canonical report | `WAIT_OWNER` | Issue #54 |
| 生产「反馈 → 新版本」闭环 | `WAIT_OWNER` | 依赖 T02+T03 |
| T07 配对审查 | `WAIT_EXTERNAL` | `review_acceptance.md` 保持空签字栏 |
| T09 部署验收 | `WAIT_EXTERNAL` | 同上 |
| PR-C Ready / 队长合并 | `WAIT_EXTERNAL` | 上列 WAIT 未关前不转 Ready |

## 5. 明确不做

- 不新开 Wave B PR。
- 不改 #41 队友分支。
- 不实现 T02 / T05 / T03 内部读口。
- 不把 90 秒短测、fixture 截图或 planned PDF 写成定量 PASS。
- 不代签 T07 / T09。
- 不暂存 T06 CRLF 幻影脏文件或 `uv.lock`。

## 6. 下一步（非 T08 单方可完成）

1. #41 作者同步 integration 并 cherry-pick `8ef2a85` 的 T08 路径实现。
2. 有 Docker 的机器按 `T08_WAVE_C_STABILITY_REPORT.md` §6 跑正式 7200 秒。
3. T02 #53、T05 #54、T03 读口冻结后，再在 `owner_composition` 接薄适配。
4. T07 / T09 签字后，再请求队长把 #56 转 Ready。
