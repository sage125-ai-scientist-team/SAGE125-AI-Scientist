# 概览 → 科学问题 功能对齐

任务：`CAPTAIN-LOCAL-SAGE125-MERGE-OVERVIEW-QUESTION-HUB-12`

合并前把原「概览」能力一一映射到合并后的「科学问题」页，禁止丢功能。

## 计数

| 指标 | 值 |
|---|---|
| OVERVIEW_FEATURE_COUNT_BEFORE | 22 |
| OVERVIEW_FEATURE_COUNT_AFTER | 22 |
| LOST_OVERVIEW_FEATURE_COUNT | 0 |
| QUESTION_PAGE_FEATURE_COUNT_BEFORE | 10 |
| QUESTION_PAGE_FEATURE_COUNT_AFTER | 10 |

## 原概览功能映射

| ID | 原概览能力 | 合并后位置 | 状态 |
|---|---|---|---|
| OV01 | 首屏 Skeleton | `page_questions` 顶部 | 保留 |
| OV02 | 工作区顶栏标题 | 只读上下文栏 A | 保留（去掉下拉） |
| OV03 | 全局 Job 状态栏 | 顶栏下方 | 保留 |
| OV04 | 页面 Job 卡片 | 科学问题页 | 保留 |
| OV05 | 未选题引导 +「选择科学问题」 | `#research-overview` 空状态 | 保留；改为滚动到 `#question-picker` |
| OV06 | KPI：当前研究状态 | C 当前研究状态卡 | 保留 |
| OV07 | KPI：当前流程进度 | C | 保留 |
| OV08 | KPI：已用证据 | C | 保留 |
| OV09 | KPI：运行次数 / 可加载运行 | C | 保留 |
| OV10 | 当前研究计划概览 | D | 保留 |
| OV11 | 查看完整计划 | D → 研究计划页 | 保留 |
| OV12 | 候选假设预览行 | D | 保留 |
| OV13 | 假设空状态 | D | 保留 |
| OV14 | 快速操作：生成研究计划 | E | 保留 |
| OV15 | 快速操作：开始文献调研 | E | 保留 |
| OV16 | 快速操作：运行受控演示 | E | 保留 |
| OV17 | 快速操作：查看历史运行 | E | 保留 |
| OV18 | 提交人工反馈 | E 更多操作 | 保留 |
| OV19 | 导出当前结果 | E 更多操作 | 保留 |
| OV20 | 清空当前草稿 | E 更多操作 | 保留 |
| OV21 | Job 提交 / `process_run_triggers` | E | 保留；选题本身不提交 |
| OV22 | 最新研究动态 | F | 保留 |

## 原科学问题页功能映射

| ID | 原科学问题能力 | 合并后位置 | 状态 |
|---|---|---|---|
| Q01 | 步骤标题 | `#question-picker` | 保留 |
| Q02 | 125 题领域分布图 | `#question-catalog-overview` | 保留；`st.cache_data` |
| Q03 | 关键词搜索 | H | 保留 |
| Q04 | 领域筛选 | I | 保留 |
| Q05 | 状态筛选 | J | 接入唯一选择器过滤 |
| Q06 | 题目选择器 | K 唯一选择器 | key 改为 `sage125_authoritative_question_selector` |
| Q07 | 当前题目详情卡 | L | 只读，不选题 |
| Q08 | 快速示例 | M | 只改 `selected_question_id` |
| Q09 | 刷新题目索引 | `#question-picker` | 保留 |
| Q10 | 领域 / 证据 / 最近运行摘要 | L 详情卡 | 保留 |

## 明确删除（导航/重复入口，不是业务功能）

- 侧栏独立「概览」项
- 顶部 `ws_question_switcher` 下拉
- 顶部重复 QID 胶囊
- 未选题时 `st.switch_page` 到第二套科学问题页

## 不得丢失的 Durable Job 行为

选题、滚动、切页不得取消 Job、不得清空 `active_job_ids`、不得因选题自动创建 Job。
