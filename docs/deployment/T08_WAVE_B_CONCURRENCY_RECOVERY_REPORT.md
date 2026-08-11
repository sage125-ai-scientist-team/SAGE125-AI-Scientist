# T08 Wave B B014 并发与恢复报告

状态：`DRAFT_EVIDENCE / NOT_READY`

日期：2026-08-11

审查基线：`d9ffb67ab5b0cf2e25c4a346bf0bef70a8b65485`

分支：`codex/t08-b-delivery-core`

## 1. 范围与结论

本报告覆盖 T08 自有的 SQLite JobStore、单进程有界队列、五任务隔离、并发写入、
停止/重启恢复和同一幂等请求并发重试。当前证据全部通过，但本文件随未提交
worktree 生成，尚未绑定 PR 最终 tip SHA，因此只能作为 B014 的 Draft 证据，不能
用于把 PR 转为 Ready。

当前结论：

- 五个不同 question 的并发 job ID、状态和持久化记录不互相覆盖；
- 单个进程内五任务队列执行保持 job/question 隔离；
- 中断的 Mock job 可重新排队；已经开始的 real job 不做不安全自动重放，而是明确
  失败为 `PROCESS_RESTARTED_UNSAFE_TO_RETRY`；
- 队列停止后未开始的 job 保持 `queued`，可由启动恢复扫描处理；
- 恢复扫描不受公共列表 limit 限制，恢复 backlog 大于内存队列 capacity 时仍会继续
  drain；
- 相同 capacity-retry 快照的并发请求只提交一次；
- 本报告不是 2 小时稳定性报告，也不证明 T01/T02/T03/T05/T06 production owner
  E2E 已完成。

## 2. 实际命令与精确结果

```text
.venv/bin/python -m pytest -q tests/api/test_v1_jobs.py \
  -k 'five_concurrent or five_writers or five_jobs_isolated or recovery or queue_stop or drains_recovery_backlog or concurrent_capacity' -vv

结果：9 passed, 29 deselected in 1.03s
```

覆盖的测试：

```text
test_sqlite_store_keeps_five_concurrent_jobs_isolated
test_sqlite_store_coordinates_five_writers_across_store_instances
test_queue_keeps_five_jobs_isolated
test_recovery_requeues_mock_and_fails_orphaned_real_job
test_recovery_scans_every_interrupted_job_beyond_public_list_limit
test_queue_stop_leaves_pending_jobs_for_restart_recovery
test_queue_stop_defers_retry_without_uncaught_worker_error
test_queue_drains_recovery_backlog_larger_than_capacity
test_v1_concurrent_capacity_retries_submit_only_once
```

API 回归：

```text
.venv/bin/python -m pytest -q tests/api

结果：67 passed in 5.81s
```

## 3. 状态恢复语义

| 场景 | 持久状态 | 恢复动作 | 对外真实性 |
|---|---|---|---|
| 未开始的 queued job | SQLite 保留 | 启动时重新入队 | 不标记 completed |
| 已开始的 Mock job | SQLite 保留 attempt/event | 可重新排队 | 继续保留 Mock 语义 |
| 已开始的 real job | SQLite 保留 attempt/event | 失败关闭，不自动重放 | 不推断 actual/completed |
| recovery 数量大于 queue capacity | SQLite + 内部 backlog | worker 逐步 drain | 状态不丢失 |
| 同一 capacity retry 并发提交 | 原子 claim/event | 仅一个提交成功 | 其余返回明确 in-progress |

## 4. 隔离与安全检查

- 主键与查询至少包含 `job_id`，任务记录同时持久化 `question_id`、
  `correlation_id` 与 `requested_by`；
- 五任务测试断言 5 个唯一 job ID 和 Q001-Q005 的完整集合；
- SQLite 使用 `BEGIN IMMEDIATE` 与 busy timeout 协调写入；
- 错误状态持久化稳定 machine code，不把本地绝对路径返回给 API；
- 本轮未修改 T02/T03/T05/T06/T07 owner 路径、公共 schema、依赖或 CI workflow。

## 5. 尚未满足的 Ready 证据

- 需要在最终提交后重跑以上命令，并把本报告的 evidence SHA 更新为该最终 tip；
- 需要在 Windows 和 Linux 都执行 export/API 回归，当前本轮直接执行环境是 macOS；
- B016/B017 production owner 全闭环 trace、浏览器证据与视频仍被 owner confirmation
  阻断；fixture/HTTP stub 结果不得替代；
- 2 小时稳定性、Docker 干净部署和 T09 验收属于后续门禁，不在本报告中冒充通过。
