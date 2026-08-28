# 线上 UI Catalog 交互故障基线

采集时间：2026-08-28T06:07:59Z  
预览 UI：https://sage125-ui-preview.onrender.com  
预览 API：https://sage125-api-preview.onrender.com  
证据：`docs/ui/online_failure_network.json`、`docs/ui/online_failure_console.txt`、`docs/ui/screenshots/before/`

## 探测摘要

ONLINE_HOME_HTTP_STATUS=200  
ONLINE_HOME_TTFB_MS=1687  
ONLINE_API_BASE_URL=https://sage125-api-preview.onrender.com  
ONLINE_API_HEALTH=PASS  
ONLINE_CATALOG_HEALTH=PASS  

API `/health` 冷启动 53694 ms 后返回 200；`questions_count=125`，`catalog.source=official`，`digest=7ef0d7886daf7836a7ccf5a5a71f37ed28779a6ea00d1b593578e7846b2cf431`。  
`GET /health/catalog`：status=ok count=125 preview_markers=0。  
`GET /questions`：count=125，Q001=`What makes prime numbers so special?`。  
`GET /api/v1/questions`：200。  
`GET /api/v1/jobs/latest`：422（缺 question_id，预期）。  
`GET /api/v1/deployment-info`：404（接口不存在）。  
UI `/health` 与 `/health/catalog` 返回 Streamlit HTML，不是 API JSON。

ONLINE_QUESTION_COUNT=125（API）  
ONLINE_DOMAIN_COUNT=12（官方 Catalog）  
ONLINE_PREVIEW_MARKER_COUNT=0  
ONLINE_CONSOLE_ERROR_COUNT=7（均为 multipage 路径下 `_stcore/*` 的 404，不是 5xx）  
ONLINE_NETWORK_4XX_COUNT=7  
ONLINE_NETWORK_5XX_COUNT=0  

RENDER_FREE_INSTANCE=True  
IDLE_COLD_START_EXPECTED=True  
COLD_START_MS=53694（API `/health` 首次）  
WARM API `/health/catalog`=1511 ms  

## 浏览器复现（Playwright，线上已唤醒后）

首页加载 21699 ms。进入研究工作区 4802 ms。切到文献证据/候选假设时 `domcontentloaded` 后 body 仍为 0 字符（短暂空白）。

SEARCH_PRIME_RESULT_COUNT=0（无匹配数量、无结果列表；界面不展示 prime）  
SEARCH_GRAVITY_RESULT_COUNT=0  
SEARCH_PANDEMIC_RESULT_COUNT=0（`visible_change=false`）  

DOMAIN_OPTION_COUNT=10（DOM 可见项；含「全部」+ 9 个中文领域。Streamlit 下拉虚拟化，未滚完 12 个正式领域）  
STATUS_OPTION_COUNT=3（全部 / 已有运行 / 尚无运行，不是完整状态集）  

QUICK_EXAMPLE_SUCCESS_COUNT=0  
五个中文标签均可找到，点击后 URL 无 `question_id`，页面无选题变化。

QUESTION_SELECTOR_OPTION_COUNT=10（DOM 可见项；首项为「选择科学问题」，随后为 Q001—Q009 官方英文题。下拉未虚拟化完整 125 项，搜索后选项会被过滤子集替换）

## 结论

API 官方 Catalog 已是 125 题。用户可见故障来自 UI 交互层：搜索不展示结果、快速示例无 callback、选题器/领域下拉被过滤或虚拟化、切页同步打 API 导致空白。不得用 Mock 或假题掩盖。
