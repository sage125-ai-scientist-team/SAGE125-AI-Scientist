# T08 UI Flow — 异步运行、版本、反馈与导出

状态：Wave A 信息架构
说明：当前前端位于 `app/ui/**`，未获得 owner 授权，因此本轮仅冻结 flow，
不修改现有 Streamlit。

## 1. 主闭环

```text
选择问题
  -> POST /api/v1/jobs
  -> 保存 job_id 和 correlation_id
  -> 轮询 GET /api/v1/jobs/{job_id}
  -> completed 后加载证据、versions、artifacts
  -> 选择目标 version 并提交 feedback
  -> 轮询 feedback 决策或修订 job
  -> 展示新 version 与结构化 diff
  -> 查看 gate / execution / multimodal
  -> 下载 PDF / Markdown / JSON
```

## 2. 页面状态

| 后端状态 | UI 行为 |
|---|---|
| `queued` | 展示排队时间，不显示假进度 |
| `running` | 展示真实 stage、更新时间和 correlation ID |
| `waiting_feedback` | 打开反馈入口，明确目标 version |
| `retrying` | 展示 attempt、失败摘要和有限重试状态 |
| `completed` | 加载证据、版本、执行、多模态和产物入口 |
| `failed` | 展示错误码、是否可重试、correlation ID |
| `timed_out` | 停止轮询，展示超时原因与允许动作 |
| `cancelled` | 只读展示取消来源和时间 |

当 Artifact、Version 或 Feedback 返回
`UPSTREAM_CONTRACT_UNAVAILABLE` 时，页面显示 `unavailable` 和缺失原因，
不得回退到旧缓存后伪装成功。

## 3. 轮询与恢复

- 首次 1 秒轮询，逐步退避到 5 秒；
- 终态立即停止轮询；
- 页面刷新后通过 `GET /api/v1/jobs` 恢复最近任务；
- URL 或视图状态只保存 job ID，不保存唯一业务状态；
- 重复点击运行复用同一 `Idempotency-Key`；
- HTTP 错误卡始终展示 correlation ID，供日志追踪。

## 4. 真实性展示

- `mock` 必须显式标为测试/演示替身；
- `planned`、`expected`、`actual` 分开展示；
- 只有 T05 明确返回 `actual_execution=true` 才显示“真实执行”；
- Reviewer issue closure、Feedback decision 和 GateResult 只展示上游字段；
- 低置信度、多模态单位、bbox、来源和人工核验状态不得隐藏。

## 5. 交互幂等

- 运行、反馈、导出按钮在请求发出后立即禁用；
- 网络重试沿用原 `Idempotency-Key`；
- 相同 key 不同 payload 的 409 必须提示用户刷新上下文，不自动换 key；
- 浏览器重连不得再次创建任务。
