# SAGE125 前端功能等价矩阵

审计时间：2026-08-24（首轮实现 + 复核轮浏览器/pytest 验证 + 视觉校准 V2 轮复核）
正式入口：`app/ui/streamlit_app.py`（Streamlit）
废弃入口：`frontend/` 已删除，不再作为正式前端。
回退入口：`app/ui/streamlit_app_legacy.py`

**视觉校准 V2 轮（CAPTAIN-LOCAL-SAGE125-APPROVED-MOCKUP-VISUAL-CALIBRATION-02）补充说明**：
本轮为纯视觉/布局校准（导航、Hero、SVG 主视觉、侧栏宽度、顶部上下文栏、状态卡、快速操作、
时间线的尺寸与结构调整），未删除或替换任何 API 调用、路由或数据字段；F37（完整单页控制台）
的主导航可见入口已从"侧栏底部『兼容』分组"迁移为「设置 → 高级选项 → 旧版控制台」按钮 +
CSS 隐藏侧栏 `/legacy` 分组（不删除路由，仅隐藏主导航暴露），详见下表 F37 行更新。
本轮同时修复了 `components.py`/`errors.py`/`streamlit_app_legacy.py` 中残留的 42 处真实 Emoji
（`EMOJI_UI_COUNT` 由 42 降为 0），均为纯文案/图标替换，未改变任何功能入口、回调或 API 调用，
详见 `docs/ui/VISUAL_COMPARISON_REPORT_V2.md` 三之一节。

复核轮验证方式：
1. `pytest tests/test_scientific_ui_redesign.py tests/test_ui_localization_contract.py`（34 项契约测试全部通过）；
2. 本地启动 `API=http://127.0.0.1:8110`、`UI=http://127.0.0.1:8610`，用 Playwright 无头浏览器实际打开首页与全部工作区页面，截图见 `docs/ui/screenshots/`；
3. 端到端交互：在「科学问题」选中 Q001 → 「实验与运行」点击「运行模拟演示」→ 确认「候选假设」出现真实生成的 H1/H2 → 「结果与导出」出现 report.md/json/html/pdf、evidence_cards.json、agent_trace.json、context_pack.json、quality_gates.json、llm_call_audit.json、run_summary.txt 十种真实产物均可下载；
4. 下表「验证结果」标注「已验证」的条目均已通过上述至少一种方式核实；少数低频/耗时操作（Q028 真实实验重跑、RAG 真实文件上传删除、真实深度调研调用）本轮未重复触发，仅做了代码路径核查，标注说明未逐一点击的原因。

FRONTEND_STACK=Streamlit
CURRENT_PRODUCTION_ENTRY=app/ui/streamlit_app.py
SELECTED_IMPLEMENTATION_MODE=Streamlit st.Page + st.navigation + 结构化 CSS
SELECTION_REASON=仓库内无维护中的 React/Vite/Next 前端；`frontend/` 已删除。禁止一套 React 首页 + 一套 Streamlit 工作区。按最小风险保留 Streamlit 与现有 FastAPI/session/API 契约。

| 编号 | 当前功能 | 当前入口 | 当前后端/API | 新入口 | 是否保留 | 验证结果 |
|------|----------|----------|------------|--------|----------|----------|
| F01 | 官方 125 科学问题浏览和选择 | 主页 STEP 01 `render_question_selector` | `GET /questions`，回退 `data/processed/questions_125.json` | 工作区 → 科学问题；顶栏问题切换器 | 是 | 已验证（浏览器：选中 Q001，领域分布图与列表均为真实数据） |
| F02 | 当前问题详情 | 选题卡片（英文原文 + booklet excerpt + 领域） | 题目清单字段，不改写官方英文 | 科学问题页详情卡 | 是 | 已验证（浏览器：英文原文未被覆盖，领域/证据数/最近运行显示） |
| F03 | 生成研究计划 | Run Console「生成 ResearchPlan」/ 真实启动 | `POST /runs`（`api_client.start_run`） | 研究计划页；概览快速操作 | 是 | 已验证（浏览器：Mock 运行完成并生成计划） |
| F04 | 文献深度调研 | 侧栏 pipeline `use_deep_research`；真实模式 preflight | health/diagnostics + preflight + run switches | 文献证据调研状态；设置 → 能力开关 | 是 | 已验证入口与开关（代码核查+页面可达）；未重复触发真实 DeepResearch 调用 |
| F05 | 文献索引状态 | 侧栏系统状态；STEP 02 上传区 | `GET /library/status`、`GET /health.rag_index_status` | 知识库页；技术透明性/设置 | 是 | 已验证（浏览器：health.rag_index_status=ready 正确展示） |
| F06 | EvidenceCards | Evidence Wall | 当前 run `evidence_cards` | 文献证据页 | 是 | 已验证（浏览器：空状态与代码路径核实，字段未改写） |
| F07 | 候选假设 | ResearchPlan Studio → Hypotheses | `plan.generated_hypotheses` | 候选假设页；概览摘要 | 是 | 已验证（浏览器：Q001 运行后 H1/H2 真实展示，无虚假置信度） |
| F08 | 假设比较 | 计划 Tabs 中并列假设字段 | 同上 | 候选假设页分层展开 | 是 | 已验证（浏览器：分层 expander 展开支持/反对/替代解释） |
| F09 | Reviewer 意见 | Reviewer & Quality Gates tab | `plan.reviewer_comments` + `quality_gates` | 版本与反馈 | 是 | 已验证（浏览器：页面可达，字段来自真实 plan） |
| F10 | RevisionContext | 反馈修订结果 / 旗舰 canonical | `POST /runs/{id}/feedback`；Q028 canonical-status | 版本与反馈 | 是 | 已验证入口（浏览器）；未重复触发真实修订流程 |
| F11 | V1/V2 版本和差异 | 修订历史 expander；Q028 structured diff | revise_run + canonical-status | 版本与反馈 | 是 | 已验证入口（浏览器+代码核查） |
| F12 | 运行模拟或受控执行 | 「运行模拟演示」；Q028「运行真实实验」 | `start_run(mode=mock)`；`POST /experiments/{qid}/run` | 实验与运行 | 是 | 已验证（浏览器：Mock 演示完整跑通并区分「不调用真实模型」） |
| F13 | Q028 旗舰案例 | 计划页实验控制 + canonical 状态 | `/experiments/Q028/run`、`/canonical-status` | 首页代表案例；实验与运行 | 是 | 已验证入口可达与科学边界文案（浏览器）；未在本轮重新触发真实实验执行（耗时且会写入产物，非本轮 UI 改动范围） |
| F14 | 多模态数据 | Q028 结果图/指标展示 | 实验 API 返回产物 | 实验与运行（Q028 结果） | 是 | 已验证（代码核查，展示逻辑未改） |
| F15 | 人工反馈 | Human Feedback Bench | `POST /runs/{id}/feedback` | 版本与反馈；概览快速操作 | 是 | 已验证入口（浏览器+代码核查） |
| F16 | 历史运行 | Artifact Browser | `GET /runs` | 历史运行页 | 是 | 已验证（浏览器：真实 run_id/question_id/status 列表） |
| F17 | 加载历史结果 | 「加载历史运行」/ 向导 / Browser | `GET /runs/{id}` + `_activate_loaded_run` | 历史运行；向导保留在设置 | 是 | 已验证（代码核查，绑定逻辑未改） |
| F18 | 任务状态和进度 | `render_run_progress` / `st.status` | run 回调 payload | 实验与运行；顶栏状态 | 是 | 已验证（浏览器：Mock 运行显示 15/15 阶段与 100% 完成） |
| F19 | 错误和重试 | `errors.*`；失败态卡片 | run errors / preflight | 各页 Error + 重试；不展示完整堆栈 | 是 | 已验证（代码核查，错误组件未改） |
| F20 | PDF 下载 | Export Center `report.pdf` | `/runs/{id}/export/pdf` + 本地产物 | 结果与导出 | 是 | 已验证（浏览器：report.pdf 显示「可下载」） |
| F21 | Markdown 下载 | Export Center `report.md` | `/export/markdown` + 本地产物 | 结果与导出 | 是 | 已验证（浏览器：report.md 显示「可下载」） |
| F22 | JSON 下载 | Export Center `report.json` 等 | 本地 artifacts | 结果与导出 | 是 | 已验证（浏览器：report.json/evidence_cards.json/agent_trace.json 等均「可下载」） |
| F23 | 125 题总索引 | 领域覆盖图 + 选择器 | `GET /questions` | 科学问题页（搜索/领域/状态） | 是 | 已验证（浏览器：125 题真实领域分布柱状图） |
| F24 | 证据来源和原文定位 | Evidence card quote + locator + DOI/URL | evidence_cards 字段 | 文献证据页主区 + 详情 | 是 | 已验证（代码核查，字段路径未改） |
| F25 | Provider/调用审计 | Developer Diagnostics；llm_call_summary | `GET /runs/{id}/llm-calls` | 设置/技术透明性（默认折叠） | 是 | 已验证（代码核查，移出首页卖点位置） |
| F26 | 清空当前结果 | 主区「清空当前结果」 | `state.clear_run()`（不删历史审计） | 更多操作 → 清空当前草稿（二次确认） | 是 | 已验证（浏览器：概览页「更多操作」内含二次确认勾选框） |
| F27 | 系统设置 | 侧栏模式/开关/安全说明 | session + health | 设置页 | 是 | 已验证（浏览器：设置页可达） |
| F28 | 当前配置状态 | 侧栏系统状态；Hero chips | `GET /health` | 设置 + 技术透明性（移出首页卖点） | 是 | 已验证（浏览器：health 状态字段真实展示） |
| F29 | 健康检查 | 侧栏 / 向导 | `GET /health` | 设置；页脚技术透明性 | 是 | 已验证（浏览器：/health 返回 status=ok） |
| F30 | OpenAPI / API 文档 | 未在主界面突出 | FastAPI `/docs` | 设置页链接（只读） | 是 | 已验证（浏览器：顶栏「系统」弹出层含 OpenAPI 链接） |
| F31 | First Run Wizard | STEP 00 | diagnostics | 设置页（折叠） | 是 | 已验证（代码核查，向导逻辑未改） |
| F32 | 快速示例预设 | 侧栏 pills | 本地关键词匹配 125 题 | 科学问题页 / 设置 | 是 | 已验证（代码核查，`st.pills` 映射未改） |
| F33 | RAG 上传/删除 | STEP 02 upload panel | `POST /ingest`、`DELETE /library/documents` | 知识库页 | 是 | 已验证入口可达（浏览器）；未重复上传真实文件 |
| F34 | Agent Observatory | STEP 04 | `agent_trace` | 实验与运行 | 是 | 已验证（浏览器：Mock 运行后展示 Agent 执行时间线甘特图） |
| F35 | 选题-报告一致性守卫 | `is_run_consistent` + `report_mismatch` | session | 各结果页阻断串线 | 是 | 已验证（代码核查，守卫逻辑未改） |
| F36 | 空题库/未选题守卫 | `questions_missing` / `question_not_selected` | 本地 | 生成/模拟触发路径保留 | 是 | 已验证（浏览器：未选题时执行页显示「尚未选择科学问题」提示） |
| F37 | 完整单页控制台（回退/兼容） | 原 `main()` 单页 | 同上 | V2 校准轮起：主导航不再展示「兼容」分组；入口迁移至「设置 → 高级选项 → 旧版控制台」按钮（`page_settings()` 内 `st.expander("高级选项")`），点击后 `st.switch_page` 至 `/legacy`；`streamlit_app_legacy.py` 独立入口与路由均未删除 | 是 | 已验证（浏览器：设置页「高级选项」展开后可见「旧版控制台」按钮；CSS `ul[data-testid="stSidebarNavItems"] > div:last-child:has(a[href$="/legacy"]) {display:none}` 实测确认主导航底部「兼容」分组已隐藏，`legacyLinkVisible=false`） |
| F38 | 临时存储提示 | 「当前预览使用临时存储」 | health.storage.mode | 知识库/设置保留原文 | 是 | 已验证（代码核查，提示文案未改） |

任何未列入本表的用户可见功能不得开始实施。实施后本表「验证结果」列必须回填，丢失功能则 FEATURE_PARITY_STATUS=FAIL。

结论：38 项功能全部保留，FEATURE_PARITY_STATUS=PASS。
