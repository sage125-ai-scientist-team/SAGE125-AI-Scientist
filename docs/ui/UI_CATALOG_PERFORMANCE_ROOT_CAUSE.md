# UI Catalog 搜索 / 筛选 / 性能根因

CATALOG_AUTHORITATIVE_PATH=app/catalog/official_question_catalog.json  
CATALOG_COUNT=125  
CATALOG_DOMAIN_COUNT=12  
CATALOG_SHA256=7ef0d7886daf7836a7ccf5a5a71f37ed28779a6ea00d1b593578e7846b2cf431  

API_CATALOG_SOURCE=OfficialQuestionCatalog（`GET /questions`，线上已 ok）  
UI_CATALOG_SOURCE=bootstrap() → `api_client.get_questions()` HTTP，失败则 `questions=[]` 写入 session  
SEARCH_SOURCE=仅 `q.get("question").lower()` 包含匹配，无结果区  
DOMAIN_FILTER_SOURCE=从当前 `ctx["questions"]` 推导；空清单时只剩「全部」  
QUICK_EXAMPLE_SOURCE=`st.pills` + `PRESET_KEYWORDS` 关键词扫描 `question` 字段；无 on_click ID  
QUESTION_SELECTOR_SOURCE=过滤后的 `by_id` 子集，不是固定 Q001—Q125  

DEPLOYED_API_BASE_URL_MODE=Dashboard 手工变量（`render.yaml` 修复前未声明 `FRONTEND_API_BASE_URL`）；默认回退 `http://localhost:8000`  
CATALOG_PACKAGED_IN_DEPLOYMENT=True（`app/catalog/official_question_catalog.json`）  
EMPTY_CATALOG_FALLBACK_FOUND=True（`bootstrap` 非 ok 时缓存 `[]`）  
STALE_EMPTY_CACHE_FOUND=True（`BOOT_QUESTIONS` / `_fetch_questions_cached` 10s 超时后不再重试）  
PREVIEW_SEED_FALLBACK_FOUND=False（正式模式已禁止）  
LOCAL_ABSOLUTE_PATH_FOUND=False（Catalog 已打包；旧 `questions_125.json` 路径仍存在但不再作为正式源）  
FULL_REPOSITORY_SCAN_ON_RERUN=False  
FULL_RESULTS_SCAN_ON_RERUN=部分（`ui_index` 重建与首页 summary 会 stat 125 题目录；筛选本身读索引）  
SYNC_REMOTE_CALL_ON_RERUN=True（每次 `bootstrap()` 调 `get_health()`，TTL 仅 6s；`FRONTEND_API_WAKE_TIMEOUT_SECONDS=75`）  
DOUBLE_RERUN_FOUND=部分（更换问题 `st.rerun(scope="fragment")`；快速示例 pills 每次 rerun 重读同一值）  

PRIMARY_ROOT_CAUSE=选题/搜索/领域/快速示例没有统一使用进程内官方 Catalog；UI 把 HTTP `/questions` 失败得到的空列表缓存进 session，搜索只静默过滤 selectbox 且不展示匹配区，快速示例没有把官方 question_id 写入 session。  

SECONDARY_ROOT_CAUSES=

1. 搜索不规范化、不展示「匹配 N 题 / 未找到匹配题目」，输入 prime/gravity/pandemic 后界面可完全不变。  
2. 选题器 options 使用过滤子集；搜索后下拉看起来像没有 Q001—Q125。  
3. 领域选项从当前（可能为空的）清单生成，而不是官方 12 领域。  
4. 状态筛选只有「已有运行 / 尚无运行」，并可能触发索引重建。  
5. 快速示例用 pills + 关键词，点击不写 `selected_question_id` / `?question_id=`。  
6. 每次切页 `bootstrap()` 同步请求远端 health（短 TTL），Render Free 冷启动约 54s，热状态往返 1.5—4s，叠加 Streamlit 重绘出现 5—6s 空白。  
7. `render.yaml` 未声明 `FRONTEND_API_BASE_URL`；`/api/v1/deployment-info` 不存在，无法核验部署 commit。  
8. UI `/health` 不是 Catalog 健康接口。  

## 修复原则

- 所有选题面使用 `OfficialQuestionCatalog` + `app/catalog/query.py`。  
- 正式加载失败 fail-closed：显示「官方题目目录加载失败」+ correlation_id，禁止只剩「全部」。  
- 搜索在内存轻量索引上完成；选题器固定 125 个 ID。  
- 快速示例按官方英文原题解析 5 个 ID，`on_click` 只写 ID。  
- Catalog 用 `st.cache_data(digest, schema, mtime)`；health session TTL 60s。  
- 不扫描正式结果、不调用模型、不改 Q028 指标。  
