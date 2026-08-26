# 长任务进度跨页面丢失：根因报告

任务：`CAPTAIN-LOCAL-SAGE125-DURABLE-JOB-PROGRESS-ACROSS-PAGES-11`  
日期：2026-08-26  
模式：`LOCAL_ONLY`  
审计时 HEAD：`bfac1de2c64801ecc6964147dadcb26e6a4d0730`

本报告在修改页面之前完成。结论来自源码路径审计，不是猜测。

---

## 必填字段

```
CURRENT_BUTTON_TO_JOB_FLOW=
  按钮 (workspace_pages / components.render_run_console)
  → process_run_triggers()  [app/ui/streamlit_app.py]
  → state.begin_run()       [清空 result，run_status="running"]
  → _execute_run()          [with st.status + st.empty 同步阻塞]
  → api_client.start_run()
      默认：_start_run_inprocess() → run_pipeline_with_state()
      仅 FRONTEND_RUN_VIA_API=1：同步 POST /runs
  → _handle_run_result() → session KEY_ACTIVE_RUN_ID = run_id（不是 job_id）
  UI 从未调用 POST /api/v1/jobs

CURRENT_JOB_STORAGE=
  API SQLiteJobStore: ${EXPORT_DIR}/.api-state/jobs.sqlite3
  表 jobs + job_events 已存在
  UI 不读写该 Store；页面权威状态是 st.session_state + 当次 rerun 局部变量

CURRENT_EVENT_STORAGE=
  job_events 为 append-only（event_id AUTOINCREMENT）
  UI 不订阅、不轮询、切页不恢复

CURRENT_WORKER_MODE=
  UI 主路径：Streamlit 页面进程内同步执行 pipeline
  API 另有 InProcessJobQueue（同进程 daemon 线程 + SQLite claim）
  UI 创建任务时不走该队列
  Compose 仅 api + ui，无独立 worker 容器

CURRENT_SESSION_STATE_KEYS=
  selected_question_id, selected_question_text, active_run_id,
  active_run_question_id, run_result, mode, offline_browse,
  feedback_text, pending_question_id, run_status
  无 job_id / active_job_ids / client_id

CURRENT_NAVIGATION_MODE=
  st.navigation + st.Page + st.switch_page + st.query_params["qid"]
  无 location.href，无自定义 JS 路由

ORIGINAL_JOB_ID=NONE（UI 启动路径不创建 API Job）
JOB_ID_AFTER_PAGE_SWITCH=NONE
JOB_ID_AFTER_RETURN=NONE
DUPLICATE_JOB_CREATED=True（再点按钮会再次 begin_run + 整管线重跑）
TASK_ACTUALLY_CANCELLED=True（主路径：切页/刷新中断页面进程内同步 pipeline）
TASK_CONTINUED_BUT_UI_LOST_POINTER=False（主路径任务随页面中断；若误开 FRONTEND_RUN_VIA_API 且已 POST /runs，则可能是同步 HTTP 被掐断）
FIRST_FAILED_CONDITION=
  进度只存在于当次 Streamlit script run 的 st.status / st.empty / 局部变量；
  切页是新的 script run，指针与进度对象全部丢弃；
  按钮 True/False 被当成“是否在跑”的唯一触发，返回页面后再次点击会从头提交。
```

---

## 1. 四个按钮的真实位置与调用

| 界面文案 | 文件 | 实际按钮 | key | 调用 |
|---|---|---|---|---|
| 开始生成 | `app/ui/workspace_pages.py` `page_overview` | 「开始生成」 | `ov_gen` | `process_run_triggers(trigger_generate=True)` → **完整 pipeline** |
| 生成研究计划 | 同文件 `page_plan` | 「生成研究计划」 | `plan_gen` | **同一条 pipeline** |
| 开始文献调研 | 概览卡片标题；按钮是「开始调研」 | `ov_ev` | **只 `st.switch_page` → 文献证据，不跑 pipeline** |
| 运行受控演示 | 卡片标题；按钮是「开始运行」 | `ov_mock` | `trigger_mock=True`，**强制 mock 完整 pipeline** |

同链路其它入口：

- `components.render_run_console()`：「生成 ResearchPlan / 启动 AI Scientist（真实）」+「运行模拟演示」
- 向导「运行 Mock 演示」
- 「▶ 运行真实实验」走 `api_client.run_experiment`，**不是**主科研 pipeline

### 按钮与 Job 类型结论（实现约束）

```
START_GENERATE_JOB_TYPE=FULL_RESEARCH_PIPELINE
GENERATE_RESEARCH_PLAN_JOB_TYPE=FULL_RESEARCH_PIPELINE
SAME_UNDERLYING_PIPELINE=True
```

「开始生成」与「生成研究计划」必须共用同一幂等域。  
受控演示 / 开始运行 / 运行模拟演示 → `CONTROLLED_DEMO`（mode=mock）。  
「开始调研」当前只是导航；实现上复用 `FULL_RESEARCH_PIPELINE` 域，避免第二套管线。

---

## 2. API 是否返回 job_id？保存在哪里？

- `POST /api/v1/jobs` **会**返回 `job_id`（HTTP 202，`JobAccepted`）。
- 前端 **从不调用** 该接口。
- 页面保存的是 `active_run_id`（pipeline `run_id`），在 `_handle_run_result` 写入 session。
- 进度 **不** 写入 jobs 表；`InProcessJobQueue` 的 `update_progress` 只写 `jobs.stage`，且 UI 没用这条路径。

---

## 3. 进度目前存在哪里？

| 候选 | 是否为当前进度载体 |
|---|---|
| 页面局部变量 `latest_progress` | **是**（`_execute_run` 内） |
| `st.button` 返回值 | 只触发一次动作，切页后丢失 |
| `st.status` 对象 | **是**（当次 rerun） |
| 当前 Fragment | 否。现有 fragment 是 KPI/时间线，**不轮询任务** |
| React local state | 否 |
| Streamlit session state | 只存 `run_status="running"` 和最终 `run_result`，**不存阶段事件** |
| asyncio Task | 否 |
| Thread / Future | 否（API 队列有线程，UI 主路径没有把 Future 塞进 session） |
| 内存字典 | API JobStore 有，UI 不读 |

---

## 4. jobs / job_events / checkpoint 是否存在？

- **jobs 表：存在**（`app/api/job_store.py` `initialize`）
- **job_events 表：存在**，append-only，`event_id` 自增
- **T07 checkpoint**：`app/batch/checkpoint.py`，与 API Job **无关联**
- API 重启恢复：`recover_interrupted_jobs()`  
  - queued 再入队  
  - running + mock：有限重试（会再跑 runner）  
  - running + real：`failed` / `PROCESS_RESTARTED_UNSAFE_TO_RETRY`

现有 `jobs` 字段不足（无 `job_type` / `client_id` / 细粒度 progress / `checkpoint_uri`）。只允许 **加法 migration**，不得另建 `jobs_v2`。

现有正式 status 枚举（必须保留）：

`queued | running | waiting_feedback | retrying | completed | failed | timed_out | cancelled`

UI 适配：`completed`→SUCCEEDED，`waiting_feedback`→PARTIAL，`retrying`→RECOVERABLE。

---

## 5. 任务由谁启动？离开页面后怎样？

**主路径（本地 UI 默认）：** Streamlit 页面进程同步 `run_pipeline_with_state`。

同一次 script run 被 pipeline 堵住，用户实际上无法在运行中切页，除非：

- 刷新 / 关页 / 新的浏览器会话；或
- 运行已结束后才切页，回来时 session 若还在则有 result，**刷新或新 rerun 丢了 `st.status` 进度卡**，按钮回到「开始生成」。

离开后：

- 进程内 pipeline **被中断**（不是“后台继续但 UI 丢指针”）。
- 再点按钮 → `begin_run()` + 再跑整条 pipeline → **重复 Provider 调用和产物**。

**API 路径（UI 未接）：** FastAPI lifespan 启动 `InProcessJobQueue` 线程，任务可在 API 进程内存活；UI 切页不会取消该队列里的 Job——但 UI 根本没创建这类 Job。

---

## 6. 导航方式

`streamlit_app.main()`：

- `st.Page` + `st.navigation(..., position="sidebar")`
- 页内 `st.switch_page`
- `st.query_params["qid"]`（`workspace.apply_query_question` / `persist_query_question`）
- **没有** `job_id` query param

---

## 7. 重复提交与 Provider

- 按钮每次 rerun 都可以再次为 True。
- 没有 idempotency_key，没有活动 Job 查询。
- 双击、返回再点、两个页面各点一次 = 多次完整 pipeline。
- **会增加 Provider 调用。**

---

## 8. 重启与数据库

- UI 重启：session 清空；无 job 指针；认为没有任务。
- API 重启：JobStore SQLite **持久**；队列可 `recover_interrupted_jobs`。UI 仍不可见，因为没查。
- 浏览器刷新：qid 可恢复；进度与 running 指针丢失。

---

## 9. 复现记录（代码级，未打真实 Provider）

A. 使用 mock / 离线路径（`mode=mock` 或不调用真实模型）。  
B–L. 按源码：点击「开始生成」不会得到 API `job_id`；切到文献证据/假设/计划/实验再回概览后，`st.status` 进度卡不存在；`run_status` 若仍为 running 且无 result，按钮仍显示「开始生成」；再次点击会第二次 `_execute_run`。

```
ORIGINAL_JOB_ID=NONE
JOB_ID_AFTER_PAGE_SWITCH=NONE
JOB_ID_AFTER_RETURN=NONE
DUPLICATE_JOB_CREATED=True
```

---

## 10. 修复方向（本轮实现，不在本文件改页面）

1. 复用现有 `jobs` / `job_events`，加法 migration。  
2. 按钮只 `POST /api/v1/jobs`，立刻返回；由已有 `InProcessJobQueue` 执行。  
3. Session 只存 `client_id` + `active_job_ids` 指针。  
4. 每页 `rehydrate_job_state` + Fragment 轮询 `GET /jobs/{id}`。  
5. 同一 `client_id + question_id + job_type` 的活动 Job 幂等复用。  
6. 「开始生成」与「生成研究计划」同一 `FULL_RESEARCH_PIPELINE` 幂等域。

**不改：** 125 题/Q028 科学结果、Prompt、模型、Evidence Policy、质量门；不 PR、不 Push、不改远端、不改 Railway/Render。
