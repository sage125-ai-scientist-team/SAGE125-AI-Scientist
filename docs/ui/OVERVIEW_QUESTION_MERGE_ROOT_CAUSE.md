# 概览 / 科学问题信息架构重叠根因

任务：`CAPTAIN-LOCAL-SAGE125-MERGE-OVERVIEW-QUESTION-HUB-12`  
日期：2026-08-26  
MODE：LOCAL_ONLY

## 审计结论

| 项 | 值 |
|---|---|
| OVERVIEW_PAGE_PATH | `app/ui/workspace_pages.py` → `page_overview()` |
| QUESTION_PAGE_PATH | `app/ui/workspace_pages.py` → `page_questions()` |
| TOP_QUESTION_SELECTOR_PATH | `app/ui/workspace.py` → `render_workspace_header()` |
| PAGE_QUESTION_SELECTOR_PATH | `app/ui/components.py` → `render_question_selector()` |
| CURRENT_SELECTED_QUESTION_STATE_KEY | `selected_question_id`（`app/ui/state.py` `KEY_SELECTED_QID`） |
| CURRENT_TOP_SELECTOR_KEY | `ws_question_switcher` |
| CURRENT_PAGE_SELECTOR_KEY | `qsel__choice`（`make_widget_key("qsel","choice")`） |
| CURRENT_NAVIGATION_MODE | `st.navigation` + `st.Page` + `st.switch_page` + `st.query_params["qid"]` |
| DUPLICATE_SELECTOR_COUNT | 2 |
| DUPLICATE_DATA_LOAD_COUNT | 2（两页各自 `bootstrap()` / 题库 / 状态 / 运行列表） |
| STATE_DRIFT_REPRODUCED | True |

## 1. 页面与导航

左侧「研究工作区」同时注册：

- `st.Page(..., title="概览", url_path="workspace")` → `page_overview`
- `st.Page(..., title="科学问题", url_path="workspace-questions")` → `page_questions`

定义位置：`app/ui/streamlit_app.py` `main()`。

首页「进入研究工作区」走 `_HOOKS["page_overview"]`，因此工作区默认页是概览，不是科学问题。

未使用 `location.href` / 自定义 JS 切页。深链接只写 `qid`（不是规格中的 `question_id`）。

## 2. 两套题目选择器

### 顶部（每个工作区页面都会渲染）

`render_workspace_header` 在 `st.selectbox(..., key="ws_question_switcher")` 中列出全部题号。  
同一行还渲染 `span.ws-qid`（再次显示 Q039）和状态胶囊。

### 科学问题页

`render_question_selector` 使用另一套 widget：

- 搜索：`qsel__keyword`
- 领域：`qsel__domain`
- 选择器：`qsel__choice`

未选题引导按钮「选择科学问题」（`ws_guide_pick`）执行 `st.switch_page(科学问题页)`，用户必须再向下找第二个选择器。

## 3. 状态模型

运行时权威值意图上是 `st.session_state.selected_question_id`。  
`bootstrap()` → `apply_query_question()` 仅在 Session 为空时读取 `qid`。

但 Streamlit selectbox **一旦带 key，之后以 widget 自己的 session 值为准，忽略 `index=`**。

两个 key 互不同步：

- `apply_pending_question()` 只写 `qsel__choice`，不写 `ws_question_switcher`
- 顶部选择器从不写 `qsel__choice`
- 科学问题页 `select_question()` 更新 `selected_question_id`，但不更新顶部 widget

因此：

1. 顶部选 Q039 → `selected_question_id=Q039`，`ws_question_switcher=Q039`
2. 进入科学问题页 → 选择器靠 `selected_qid` 的 `index` 初值，**首次**可显示 Q039
3. 页内改选 Q028 → `selected_question_id=Q028`，`qsel__choice=Q028`，`ws_question_switcher` 仍是 Q039
4. 切到文献证据等页 → 顶栏再次实例化 `ws_question_switcher=Q039`，并调用 `select_question("Q039")`，把权威状态打回 Q039

`STATE_DRIFT_REPRODUCED=True`（代码路径 + 浏览器复现，见下）。

数据源表面上同为 `api_client.get_questions()` 缓存，但两套 widget 会在同一会话产出不同 `question_id`。

## 4. 切页 / 切题对 Job 的影响

- 切页：`active_job_ids` 不在页面函数里清空；Durable Job 指针按题号分桶。
- 切题：`state.select_question()` 在题号变化时调用 `clear_run()`，只清会话 `run_result`，不删 Job Store，也不删 `active_job_ids`。
- 顶部选择器在漂移回写时会把「当前题」改回旧题，页面展示的 Job 会跟着跳，但后台 Job 本身不会被取消。

## 5. 重复加载

| 内容 | 概览 | 科学问题 |
|---|---|---|
| 125 题清单 | `bootstrap()` | `bootstrap()` |
| 领域统计图 | 无 | `make_domain_coverage_chart` 每次进入重建 |
| 当前题目 / 状态 | header + KPI | header + 详情卡 + 筛选说明 |
| 历史运行 | `list_runs()` KPI / 动态 | `list_runs()` 最近运行 |

用户心智被拆成：顶栏选题 → 概览看状态 → 科学问题再选题 → 再回概览看计划。

## 6. 浏览器复现步骤

1. 进入工作区概览，顶部选择 Q039。
2. 侧栏进入科学问题：下方选择器应显示 Q039（首次进入通常一致）。
3. 下方改选 Q028。
4. 进入文献证据再回概览/任意工作区页：顶部 `ws_question_switcher` 仍持有 Q039，并回写权威状态。

## 7. 修复原则（本轮）

- 删除侧栏「概览」；合并进「科学问题」。
- 顶部改为只读上下文，删除 `ws_question_switcher` 与重复 QID 胶囊。
- 全系统只保留 `key="sage125_authoritative_question_selector"`。
- `selected_question_id` 为会话权威；`question_id` / 兼容 `qid` 仅用于深链接。
- 「选择科学问题」只滚动到 `#question-picker`，选中后滚回 `#research-overview`。
- 旧 `/workspace` 重定向到科学问题页，不渲染旧概览。
