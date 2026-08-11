# T08 Wave B 自主验收矩阵

状态：`AUTONOMOUS_SCOPE_VERIFIED_DRAFT / OWNER_BLOCKED`

日期：2026-08-11

分支：`codex/t08-b-delivery-core`

## 1. 判定规则

- `PASS_CANDIDATE`：T08 自有实现和自动化证据已具备，仍需在最终 clean tip 复验。
- `FINAL_TIP_REVERIFY`：已有历史通过证据，但本地存在未提交改动或分支落后。
- `OWNER_BLOCKED`：必须由 T01/T02/T03/T05/T06 提供 production 真源或服务。
- `EXTERNAL_REVIEW`：必须由 T07 或队长完成，T08 不得自行签字。
- fixture、HTTP stub、planned 或 expected 数据只证明契约接线，不证明 production E2E。

Docker、干净部署和 2 小时稳定性属于 Wave C，不计入本矩阵的 Wave B 阻断。

## 2. B001—B021

| ID | 当前状态 | 当前证据 | 最小剩余动作 |
|---|---|---|---|
| B001 | `PASS_CANDIDATE` | v1 jobs/status/questions/artifacts、幂等、统一错误及测试 | 最终 tip 重跑 API |
| B002 | `PASS_CANDIDATE` | 真实 FastAPI 路由生成 OpenAPI | 最终 tip 重新生成快照 |
| B003 | `FINAL_TIP_REVERIFY` | API 示例、稳定失败码、correlation ID | 重跑 PowerShell 示例并记录结果 |
| B004 | `OWNER_BLOCKED` | T08 evidence/version/feedback projection 已存在且 fail-closed | T01/T02/T03 production ports |
| B005 | `OWNER_BLOCKED` | endpoints 与 Evidence panel 已存在 | feedback 不再固定 503 后联调 |
| B006 | `OWNER_BLOCKED` | quote/locator fixture 与 resulting-version UI 已测 | production feedback→version trace |
| B007 | `OWNER_BLOCKED + EXTERNAL_REVIEW` | Reviewer/Gate/Execution/Multimodal UI 骨架存在 | owner composition + T07 配对签字 |
| B008 | `PASS_CANDIDATE` | B4 Execution/Multimodal panels 与 Draft PR #39 | 最终浏览器复验 |
| B009 | `PASS_CANDIDATE` | `NOT ACTUAL`、低置信度和 unavailable 状态 | production 下复验不误标 |
| B010 | `FINAL_TIP_REVERIFY` | canonical JSON/MD/PDF 单真源及一致性测试 | 最终 tip 导出回归 |
| B011 | `FINAL_TIP_REVERIFY` | PDF 生成、下载和页面 QA 历史证据 | 重新生成代表性 PDF |
| B012 | `FINAL_TIP_REVERIFY` | 无裸 Markdown/空白页/异常字距历史检查 | 最终 PDF 人工复检 |
| B013 | `FINAL_TIP_REVERIFY` | 鉴权、限流、恢复、运行时 deadline、五并发 | 最终 tip 重跑专项 |
| B014 | `FINAL_TIP_REVERIFY` | `T08_WAVE_B_CONCURRENCY_RECOVERY_REPORT.md` | 更新最终 SHA/CI |
| B015 | `FINAL_TIP_REVERIFY` | retry/timeout/重启状态可见且持久 | 最终 tip 重跑 |
| B016 | `OWNER_BLOCKED` | 只有 fixture 级分段/闭环测试 | owner composition 后跑 production 全链路 |
| B017 | `OWNER_BLOCKED` | production trace/录像尚不存在 | 最终 tip 生成真实 trace/录像 |
| B018 | `PASS_CANDIDATE + OWNER_BLOCKED` | 默认 fail-closed，不伪造成功 | production 下校验跨模块字段完整 |
| B019 | `OWNER_BLOCKED + FINAL_TIP_REVERIFY` | API/前端/导出测试可运行 | owner E2E、同步 integration、全量复验 |
| B020 | `EXTERNAL_REVIEW` | 接口回归报告为 `NOT_READY` | 队长授权转 Ready |
| B021 | `FINAL_TIP_REVERIFY` | captain 已审 tip P0=0/P1=0 | 处理 dirty worktree、behind=0、重新审查 |

## 3. 当前自主完成项

- T01 evidence 与 T02 versions/diff 的 proposed T08 boundary 均绑定
  `run_id + question_id`；跨题返回 `UPSTREAM_IDENTITY_MISMATCH`。
- Job 幂等键不能跨 actor 复用；其他 actor 查询任务返回 403。
- 运行时持久 deadline 在 progress 或 runner 返回边界触发 `timed_out`，不会进入
  completed；无法合作取消的上游调用仍需 owner 提供可中断执行边界。
- Streamlit fixture-only 测试覆盖 evidence、Reviewer/diff、feedback decision、
  Gate、`NOT ACTUAL`、multimodal 低置信度和 artifacts。

## 4. 仍需外部完成

1. T01：持久 `get_evidence_bundle(run_id, question_id)`。
2. T02：持久 version history 与 owner-owned aggregate diff。
3. T03：Schema 冲突修复、feedback submit/status、持久 Gate read。
4. T05：execution history、re-attestation 和安全 artifact resolver。
5. T06：identity-bound multimodal detail/source/preview resolver。
6. T02+T03：decision、diff hash、resulting version 的原子闭环。
7. T07：配对审查。
8. 队长：composition、实施与 Ready 授权。

