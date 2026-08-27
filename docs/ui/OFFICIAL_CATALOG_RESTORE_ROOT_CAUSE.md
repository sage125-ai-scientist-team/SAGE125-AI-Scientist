# CAPTAIN-LOCAL-SAGE125-OFFICIAL-CATALOG-RESTORE-14

## 污染范围

| 分类 | 命中 |
| --- | --- |
| A 正式运行代码 | `app/api/preview_catalog.py` 在 `APP_ENV=preview` / `SAGE125_PREVIEW_SEED` / `PREVIEW_EPHEMERAL_STORAGE` 时写入 Preview Seed |
| B API 路径 | `scripts/start_api.py` `ensure_preview_questions()` 调用 bootstrap seed；`GET /questions` 读 `SAGE_QUESTIONS_PATH` / DATA_DIR |
| C Streamlit 前端 | `workspace_pages.py` / `components.py` 用 API 的 `question` 字段做 selectbox 文案 |
| D React Custom Component | 落地页无题目清单；未命中 PREVIEW-SEED |
| E UI 索引脚本 | `app/ui/ui_index.py` 若 catalog 是 seed 会写入 preview 标题 |
| F 测试夹具 | `tests/api/test_preview_catalog.py`、`tests/test_bootstrap_preview_data.py`、`scripts/bootstrap_preview_data.py` |
| G 文档 | `docs/deployment/RENDER_PREVIEW.md` 等明确允许 preview seed |
| H 本地生成结果 | 未改正式 result.json |
| I 缓存 | `@st.cache_data` `get_questions` 以 mtime 为键；旧 Preview 响应可残留 |
| J 前端 bundle | 未静态打包 Preview Seed 题面 |

CURRENT_API_CATALOG_SOURCE=DATA_DIR_or_preview_seed_when_APP_ENV=preview
CURRENT_UI_CATALOG_SOURCE=GET_/questions.question
CURRENT_INDEX_SOURCE=data/ui/ui_question_index.json（本地已是官方标题）
CURRENT_RESULTS_CATALOG_SOURCE=exports/ 只读
CURRENT_PREVIEW_SEED_SOURCE=scripts/bootstrap_preview_data.py::build_preview_seed_questions

PREVIEW_SEED_PRODUCTION_IMPORT_PATHS=app/api/preview_catalog.py,scripts/start_api.py
PREVIEW_SEED_TEST_ONLY_PATHS=tests/api/test_preview_catalog.py,tests/test_bootstrap_preview_data.py

API_QUESTION_COUNT=125（线上曾为 Preview Seed）
UI_QUESTION_COUNT=125
OFFICIAL_CATALOG_COUNT=125

AUTHORITATIVE_CATALOG_PATH=data/processed/questions_125.json
AUTHORITATIVE_CATALOG_SHA256=b6712a3b53f9776d7f695ea67f810c30b7d97ee59c183009432870d3224cdebb
AUTHORITATIVE_CATALOG_SOURCE=official_booklet_extract
PACKAGED_CATALOG_PATH=app/catalog/official_question_catalog.json

Q028_OFFICIAL_TITLE=Will it be possible to cure all cancers?
Q028_API_TITLE_BEFORE=[PREVIEW-SEED] Biology placeholder question 06?
Q028_UI_TITLE_BEFORE=同上（来自 API）

## 根因

1. 官方 booklet 抽取 `data/processed/questions_125.json` 含 `booklet_excerpt`，被 `.gitignore` 排除，Render 镜像里没有。
2. Preview 启动把「无题库」当成允许写 seed：`APP_ENV=preview` 即 `preview_seed_allowed=True`。
3. `GET /questions` 原样返回 seed 的 `question` 字段。
4. 选题器 `format_func` 显示该字段，于是出现 `Q028 · [PREVIEW-SEED] ...`。
5. `data/ui/ui_question_index.json` 本地是官方标题，但 picker 不读索引标题。

## 修复

- 从官方抽取生成无摘录精简 Catalog，纳入部署包。
- `OfficialQuestionCatalog` 为唯一读源。
- 正式 / preview / staging 禁止 Preview Seed 回退。
- 选题器只存 `question_id`，顶栏按 ID 回查官方标题。
