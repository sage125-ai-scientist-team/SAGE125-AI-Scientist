# T08 Wave A 收尾记录

日期：2026-08-10

分支：`codex/t08-wave-a-closeout-final`

基线：`upstream/integration/2026-08-10`（`54327aa`）
原交付 PR：[#8](https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/8)，已批准并合并

## 1. 收尾范围

本次只修改 T08 owner 路径：

- `app/api/**`；
- `tests/api/**`；
- `docs/deployment/**`。

未修改根 `.gitignore`、依赖、CI、共享 Schema 或 T01—T07 owner 实现。

## 2. 已关闭事项

- 同一 SQLite 数据库的进程内 writer 使用共享锁串行化，避免多个
  `SQLiteJobStore` 实例同时执行 `BEGIN IMMEDIATE` 的平台相关竞态；
- 该共享 `RLock` 只覆盖同一进程内的多个 store 实例；跨进程写入仍由 SQLite
  `BEGIN IMMEDIATE` 与 `busy_timeout` 保护；
- 启动恢复直接查询全部 `queued/retrying/running` 任务，不再受 HTTP 列表接口
  100 条上限影响；
- 恢复任务多于内存队列容量时进入内部 recovery backlog，worker 完成任务后继续
  补充，SQLite 仍是唯一状态真源；
- shutdown 发出后 worker 不再领取新的排队任务；未开始任务保持 `queued`，下次
  启动可恢复；
- RFC 已从“上游契约尚未冻结”更新为“公开契约已存在、Wave B adapter 尚未接入”。

## 3. 契约边界

当前仓库已有以下 owner 契约：

- T02：`app/contracts/revision.py`；
- T03：`app/contracts/validation.py`；
- T05：`app/contracts/execution.py`；
- T06：`app/contracts/multimodal.py`。

Wave A 继续让尚未完成 adapter 的 Artifact、Version、Feedback operation 以
`UPSTREAM_CONTRACT_UNAVAILABLE` / HTTP 503 失败关闭。完整 projection、鉴权、导出
和前端闭环属于 Wave B，不在收尾中提前实现。

## 4. 红灯与回归证据

修复前专项测试：

```text
.venv/bin/python -m pytest -q tests/api/test_v1_jobs.py \
  -k 'recovery_scans_every or queue_stop_leaves' -vv
2 failed
```

失败分别证明：恢复只覆盖前 100 条；停止信号后 worker 仍会执行排队任务。

停止期间可重试错误的专项红灯：

```text
.venv/bin/python -m pytest -q tests/api/test_v1_jobs.py \
  -k 'stop_defers_retry' -vv
1 failed
```

失败证明原 worker 会在 shutdown 重入队时抛出未捕获的 `RuntimeError`。

修复后：

```text
.venv/bin/python -m pytest -q tests/api/test_v1_jobs.py \
  -k 'recovery or queue_stop_leaves' -vv
3 passed

.venv/bin/python -m pytest -q tests/api
44 passed in 3.10s

.venv/bin/python -m compileall -q app/api tests/api
PASS

.venv/bin/python -m pytest -q
791 passed, 36 skipped, 5 warnings in 12.45s

.venv/bin/python scripts/api_smoke.py
API smoke summary: {"health": true, "questions": true, "diagnostics": true, "key_leak": false}
RESULT: PASS

.venv/bin/python scripts/frontend_smoke.py
RESULT: PASS

git diff --check
PASS
```

36 个 skip 来自 Windows 专用 junction 探测，以及缺少
`questions_125.json` / `data/raw/sjtu-booklet.pdf`。5 个 warning 来自 RAG PDF loader
依赖的 SWIG 类型弃用提示；本次 T08 差异未修改这些路径。

## 5. 科学真实性与安全

- 未改变完成资格五项门禁；缺少 owner 明确证明时不得写入 `completed`；
- 裸 `upstream_run_id` 仍只进入待核验，不等价于真实完成；
- 未根据文件名或文件存在推断 `actual_execution`；
- API smoke 未发现 `sk-` 密钥泄露；
- 默认 SQLite 路径位于 `exports/.api-state/jobs.sqlite3`，根 `.gitignore` 已通过
  `exports/` 覆盖，无需越权修改根文件。

## 6. 已知限制与 Wave B 交接

- `correlation_id` 已进入 T08 request/job/worker 日志，但上游 pipeline 尚无冻结的
  tracing 注入接口；T08 未越界修改 `app/workflow/**`；
- 运行中的外部 pipeline 不能被线程安全地强制终止；shutdown 超时会记录仍存活的
  worker，尚未开始的任务不会继续领取；
- Artifact、Version、Feedback 的真实 owner adapter、鉴权、速率限制、统一导出和
  完整前端闭环按 Wave B 实施；
- Docker、干净环境部署和 2 小时稳定性属于 Wave C，本记录不声称已经验证。

## 7. 回滚

SQLite writer 串行化和本次恢复/停止加固均不改变数据库 Schema，不需要迁移。
如需回滚，可回退收尾分支提交；已有 `jobs` 和 `job_events` 数据保持兼容。
