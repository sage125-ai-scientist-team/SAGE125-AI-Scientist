# SAGE125-AI-Scientist

## 1. 项目简介

SAGE125-AI-Scientist 是面向赛道 A“科学假设生成与研究计划设计”的 AI Scientist 原型。

用户从《125 Questions: Exploration and Discovery》（PDF：`sjtu-booklet.pdf`）的 125 个科学问题中选择一个问题，系统基于 **Qwen/千问 + 阿里云百炼 API + zvec RAG + 多智能体工作流**，自动输出结构化的《科学假设与研究计划》，而非百科式回答。

> 当前为可运行的应用原型：已实现多智能体 Pipeline、真实/Mock 严格隔离、RAG、证据卡、质量门、调用审计、人在回路、API、Streamlit 控制台和多格式导出。系统输出仍是待实验验证的研究计划，不是已证实的科学结论。

## 2. 用户流程

选择 125 问题之一 → 上传资料（可选）→ 一键生成 → 查看 Evidence Cards → 查看 ResearchPlan → 人在回路反馈 → 导出 PDF / Markdown / JSON。

## 3. 系统内部流程

```
QuestionParser → QueryPlanner → Local RAG → DeepResearch → EvidenceExtractor
→ HypothesisGenerator → ExperimentDesigner → ScientificReviewer → ReportWriter → SchemaValidator
```

| 阶段 | 智能体 | 职责 |
| --- | --- | --- |
| 1 | QuestionParser | 将选中问题解析为结构化背景 |
| 2 | QueryPlanner | 生成多角度检索/研究查询 |
| 3 | Local RAG | 基于 zvec 的本地检索增强 |
| 4 | DeepResearch | 调用 Qwen Deep Research（原生 dashscope SDK）|
| 5 | EvidenceExtractor | 抽取并核验可溯源证据 |
| 6 | HypothesisGenerator | 生成可证伪的科学假设 |
| 7 | ExperimentDesigner | 设计验证实验 |
| 8 | ScientificReviewer | 多维度科学评审 |
| 9 | ReportWriter | 整合为结构化研究计划 |
| 10 | SchemaValidator | 契约校验与反造假检查 |

## 4. Key 配置方式

**真实 Key 只粘贴到本地终端或本地 `.env` 文件，不要粘贴到 Cursor 对话框。**

```powershell
python scripts/setup_env.py
```

在本地终端按提示输入：

- `DASHSCOPE_API_KEY`（阿里云百炼 API Key，敏感、隐藏输入）
- `WORKSPACE_ID`（用于自动生成两个 base_url）
- `OPENALEX_API_KEY`（可选，直接回车跳过）
- `CONTACT_EMAIL`（用于 arXiv / Crossref 礼貌请求）

脚本会根据 `WORKSPACE_ID` 自动生成：

- `DASHSCOPE_BASE_URL=https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- `DASHSCOPE_DEEP_RESEARCH_BASE_URL=https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/api/v1`

> 安全提示：任何日志、README、前端、测试文件都不会打印完整 API Key，仅显示“已配置 / 未配置”或掩码（前 4 位 + 后 4 位）。

## 5. 外部资源说明

| 资源 | 网址 |
| --- | --- |
| 百炼控制台 | https://bailian.console.aliyun.com/ |
| 百炼模型文档 | https://help.aliyun.com/zh/model-studio/models |
| 百炼 OpenAI-compatible 文档 | https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope |
| Qwen-Deep-Research | https://help.aliyun.com/zh/model-studio/qwen-deep-research |
| zvec | https://github.com/alibaba/zvec |
| Qwen-Agent | https://github.com/QwenLM/Qwen-Agent |
| Qwen3-Embedding | https://github.com/QwenLM/Qwen3-Embedding |
| arXiv API | https://info.arxiv.org/help/api/index.html |
| OpenAlex API | https://developers.openalex.org/ |
| Crossref API | https://api.crossref.org/ |

## 6. 安装

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/setup_env.py
```

> 说明：默认不安装本地大模型推理库。Qwen3-Embedding / Reranker 的本地模式为可选项，需自行安装 `transformers` / `torch`，并将 `EMBEDDING_BACKEND` 切换为本地后端。
>
> 若 `weasyprint` 在本机安装失败，PDF 导出会使用 ReportLab 继续生成 PDF，不会导致主流程失败。

## 7. 启动

```bash
# 启动后端 API（OpenAPI 文档：http://127.0.0.1:8000/docs）
uvicorn app.api.main:app --reload --port 8000

# 启动前端界面
streamlit run app/ui/streamlit_app.py
```

运行测试：

```bash
pytest -q
```

## 8. 接口文档（初版）

后端基于 FastAPI，启动后可在 `/docs` 查看交互式 OpenAPI 文档。当前骨架提供以下端点：

### GET `/health`

- 功能：健康检查，返回服务状态与脱敏后的配置摘要。
- 响应示例：

```json
{
  "status": "ok",
  "config": {
    "DASHSCOPE_API_KEY": "未配置",
    "OPENALEX_API_KEY": "未配置",
    "WORKSPACE_ID": "未配置",
    "DASHSCOPE_BASE_URL": "未配置",
    "APP_ENV": "development",
    "EMBEDDING_BACKEND": "bailian"
  }
}
```

### GET `/questions`

- 功能：返回已经抽取并通过语义/版式质量门的 125 Questions 列表。
- 响应示例：`{ "questions": [], "note": "问题列表将在解析 PDF 后提供。" }`

### POST `/generate`

- 功能：针对选定问题运行完整多智能体流水线，返回 `ResearchPlan` 与运行审计。
- 后续参数：`{ "question": "..." }`。

### POST `/export`

- 功能：将 `ResearchPlan` 导出为 PDF / Markdown / JSON。
- 后续参数：`{ "format": "pdf|markdown|json" }`。

> 数据契约见 `app/core/schemas.py`：`QuestionItem`、`EvidenceCard`、`ScientificHypothesis`、`ResearchPlan`、`PipelineState`。References 只能从已检索 EvidenceCards 中选择；DOI/arXiv/OpenAlex 外链会由稳定标识重新构造。元数据存在不等于论文内容已支持报告结论，仍须打开原文核验。

## 8.5 RAG 与证据链构建

本项目**不是百科问答系统**。RAG 的目标不是直接回答问题，而是为「可验证科学假设与研究计划」提供**可追溯证据**。所有事实必须能追溯到某张 `EvidenceCard`；没有证据支撑的内容只能作为 knowledge gap 或 pending hypothesis，不能进入 established facts。

### 1）放置 125 问题 PDF

将 booklet PDF 放到：

```
data/raw/sjtu-booklet.pdf
```

### 2）抽取 125 个科学问题

```bash
python scripts/extract_125_questions.py
```

输出：

```
data/processed/questions_125.json
data/processed/questions_125.csv
data/processed/extraction_report.md
```

抽取基于 PDF 字体样式（问题标题 = MyriadPro-Bold 12pt、领域标题 = MyriadPro-Bold ~20pt）并按**双栏阅读顺序**重建，稳定得到 125 个问题。若数量不是 125，脚本仍会保存结果，但在 `extraction_report.md` 标记 **WARNING** 并列出疑点，不会静默成功。

> **语料边界：** `sjtu-booklet.pdf` 只用于生成 125 问题目录和题目背景，永不作为 Local RAG 的本地文献证据。Local RAG 只检索用户主动上传到独立本地文献库的资料，避免 booklet 的简介文字被误当成论文证据。

### 3）检查旧版独立索引构建链路（兼容/诊断）

```bash
python scripts/build_rag_index.py
```

### 4）检查旧版 mock 索引构建链路（仅测试）

```bash
python scripts/build_rag_index.py --mock-embedding
```

> `build_rag_index.py` 构建的是 `data/index/zvec/` 兼容/诊断索引，可能包含 booklet，**运行时 Local RAG 不会读取它**。活动证据库只使用上传入口维护的 `data/index/user_library/zvec/`，并强制限定为用户文献作用域。mock embedding 使用确定性 hash 向量，**不可用于正式评审结果**，仅用于流程连通性测试。

构建产物：

```
data/index/zvec/               # zvec 向量集合
data/index/chunks.jsonl        # chunk 元数据副本（防向量库 metadata 丢失）
data/index/index_manifest.json # 索引清单（文件/文档/chunk 数、维度、模型等）
data/index/build_report.md     # 构建报告
data/index/zvec_capabilities.json # zvec API 能力探测结果
```

### 5）zvec 说明

- zvec 是本地 in-process 向量库；不需要 API Key、不需要 Docker、不需要单独启动服务；
- 生产默认使用 zvec；`MemoryVectorStore` 仅用于测试（`MOCK_VECTOR_STORE=true`）；
- 若本地 zvec 版本 API 与封装不兼容，会抛出 `ZvecCompatibilityError`，并可参考 `data/index/zvec_capabilities.json` 按本地版本适配 `app/rag/zvec_store.py`。

### 5.1）本地文献库：持久化、跨问题复用与删除

- 上传成功的资料会**永久保存在本机文献库**，关闭浏览器、重启 API 或切换科学问题都不会自动删除；
- 同一份资料会在后续不同问题中复用，无需为每个问题重复上传；系统按文件内容哈希去重，同内容改名后再次上传不会重复占用原文和向量索引；
- 默认配额为：单文件 25 MiB、单批最多 10 个文件且合计 100 MiB、原文库最多 2 GiB / 500 个文件、索引最多 4 GiB；同时至少保留 `max(5 GiB, 磁盘容量 5%)` 的可用空间；
- 超过文件、批次、总容量或磁盘安全余量时会拒绝导入，不应留下半写入文件或半成品索引；
- 可在文献库管理界面删除资料，也可调用 `DELETE /library/documents/{document_id}`。删除会移除原文、活动向量、chunk 清单和文献库记录；既有运行导出可能已包含该资料的引用片段，需要按需另行删除对应 `exports/{run_id}/`；
- 125 Questions booklet 与用户文献库隔离，删除用户资料不会影响问题目录。

### 5.2）上传资料的隐私边界

- 原始上传文件保存在本机，不会发送到 arXiv、OpenAlex 或 Crossref；这些服务只接收系统生成的公开文献检索词；
- **真实嵌入并非纯离线：** 使用 `text-embedding-v4` 构建真实索引时，文档会被切成文本片段并发送到阿里云百炼嵌入接口计算向量；真实多智能体运行还可能把检索到的相关片段放入 Qwen 分析上下文；
- 若资料不得离开本机，请不要使用真实嵌入/真实运行；仅使用明确标记为测试用途的 mock embedding，或先对资料做脱敏；
- 文件原名可作为本地展示信息，但导出、日志和公开 API 不应包含本机绝对路径；`data/raw/uploads/`、索引和缓存均不得提交到版本库。

### 6）RAG 链路

```
Document -> Chunk -> text-embedding-v4 -> zvec search -> qwen3-rerank -> EvidenceCard
```

### 7）EvidenceCard 说明

- `quoted_text` 必须来自原文，禁止模型改写；
- `summary` 可以是摘要（无 LLM 摘要时取原文前 180 字符）；
- `doi` / `url` 不存在就留空，**禁止伪造**；
- `reliability_note` 说明来源（source_path/page/chunk/query/rerank 状态）；
- rerank 失败时使用向量原排序，并在 `reliability_note` 标记 `rerank_failed_fallback_used`；
- 最终报告中的事实必须能追溯到 `EvidenceCard`。

### 8）arXiv / OpenAlex / Crossref

- arXiv 不需要 Key，但必须限流（`ARXIV_REQUEST_INTERVAL_SECONDS`，默认 3 秒），不下载 PDF 全文；
- OpenAlex Key 可选，缺失时自动跳过，不会导致失败；
- Crossref 不需要 Key，但建议配置 `CONTACT_EMAIL` 进入 polite pool，仅用于元数据 / DOI 核验；
- 用户上传资料只用于本地索引，**绝不**发送到上述公开文献 API。
- 上述“不发送”仅指 arXiv / OpenAlex / Crossref；真实索引仍会把切分后的文本片段发送到百炼 embedding 服务，详见“上传资料的隐私边界”。

### 9）常见问题（FAQ）

- **抽取不到 125 个问题怎么办？** 查看 `data/processed/extraction_report.md` 的 WARNING 段（含各领域数量、低置信问题、被去重问题、疑似漏抽/误抽页面），据此人工校验。
- **zvec 安装失败怎么办？** 运行 `pip install zvec`；临时测试可设置 `MOCK_VECTOR_STORE=true` 使用内存向量库。参考 `data/index/zvec_capabilities.json`。
- **embedding 调用失败怎么办？** 检查 `DASHSCOPE_API_KEY` / `WORKSPACE_ID`（`python scripts/setup_env.py`）。系统不会用随机向量伪造嵌入，会直接报错。
- **上传的资料会自动删除吗？** 不会。资料会永久保存在本机文献库并跨问题复用，直到你在文献库管理界面或删除 API 中明确删除。
- **为什么同一个文件换名后没有再次索引？** 文献库按内容哈希去重，文件名不是去重依据。
- **删除资料后历史报告也会消失吗？** 不会自动级联。文献库删除会清理活动原文与索引；已有运行导出属于历史快照，若其中含敏感片段，请另行删除对应运行目录。
- **为什么不能伪造 References？** 科学假设必须可验证、可追溯；伪造 DOI/URL/作者会破坏证据链，使结论不可信。
- **为什么 DeepResearch 不能直接作为最终报告？** DeepResearch 仅是调研资料来源，其引用需经 EvidenceExtractor 与 Crossref/arXiv 核验后方可采用。
- **为什么 Results 不能写假指标？** 未真实执行实验时写 `AUROC=0.92` 等数字属于造假；`ResearchPlan` 校验器会在 `actual_execution!=True` 时拦截此类数值。

## 9. 多智能体 Pipeline 与科研假设生成

本项目不是普通 ChatBot / 百科问答系统。用户只需选择一个科学问题，系统自动形成**证据链**并输出**可验证科学假设 + 研究计划**（数据集/技术路线/实验设计/评价指标/参考文献/待验证结果状态）。所有事实必须绑定 EvidenceCard，Results 不允许伪造。

### 9.1 Agent 列表与职责

| Agent | 职责 | 模型 |
| --- | --- | --- |
| Supervisor | 调度策略（启用/跳过、风险标记，不产生科学内容） | qwen3.7-plus |
| QuestionParser | 解析领域/关键词/实体/问题类型/科学边界 | qwen3.6-flash |
| QueryPlanner | 生成 8-12 个多角度检索查询 | qwen3.7-plus |
| LocalRAGRetriever | 本地 zvec 检索 + rerank + 证据转换 | text-embedding-v4 / qwen3-rerank |
| DeepResearchAgent | 调用 qwen-deep-research（仅调研资料，需核验） | qwen-deep-research |
| EvidenceExtractor | 抽取事实/争议/知识空白/候选数据集（事实绑定 evidence_ids） | qwen3.7-plus |
| HypothesisGenerator | 生成 2-3 个可证伪假设并推荐 | qwen3.7-max |
| ExperimentDesigner | source/target 数据、baselines/metrics、Results pending | qwen3.7-plus |
| ScientificReviewer | 严格评审，可 fail 并触发最多 1 次自动修订 | qwen3.7-max |
| ReportWriter | 整合为 ResearchPlan（references 来自 EvidenceCards） | qwen3.7-plus |
| SchemaValidator | 结构与真实性校验，给出保守 validation_status | qwen3.6-flash |

### 9.2 Pipeline 流程

```
Question -> Parse -> Query Plan -> RAG / DeepResearch / Open Literature
-> Evidence Extraction -> Hypothesis -> Experiment Plan -> Review
-> Report -> Validation (+ Quality Gates) -> Export
```

编排器为自研轻量状态机（`app/workflow/pipeline.py`），借鉴“节点/边/质量门”思想，
不依赖 LangGraph；多智能体状态流转由 `app/agents` + `app/workflow` 自行实现
（参考 Qwen-Agent 的 planning / tool-use / memory / RAG 思想，但不作为主依赖）。

### 9.3 为什么不是普通 ChatBot

- 用户只选科学问题，不直接获得“答案”；
- 系统自动构建证据链（EvidenceCard），所有事实可追溯；
- 输出是可验证假设与研究计划，而非结论；
- 无真实实验时 Results 一律 pending，禁止伪造 AUROC 等指标。

### 9.4 Artifact 产物（exports/{run_id}/）

`report.json` / `report.md` / `evidence_cards.json` / `agent_trace.json` /
`context_pack.json` / `quality_gates.json` / `pipeline_state.json` /
`errors.json` / `warnings.json` / `run_summary.txt`。

- `agent_trace.json`：逐步执行追踪（模型/状态/摘要/prompt_hash），可用于前端展示；
- `context_pack.json`：上下文工程包（问题/证据/事实/假设/质量门），可用于答辩；
- `quality_gates.json`：证据落地、Results 完整性、Schema、模型合规、引用完整性等质量门结果。

### 9.5 运行 mock demo（无需 Key）

```powershell
$env:MOCK_LLM="true"; py -3 scripts/run_demo.py; Remove-Item Env:\MOCK_LLM
```

可选叠加内存向量库：

```powershell
$env:MOCK_LLM="true"; $env:MOCK_VECTOR_STORE="true"; py -3 scripts/run_demo.py; Remove-Item Env:\MOCK_LLM; Remove-Item Env:\MOCK_VECTOR_STORE
```

### 9.6 运行真实 demo

```powershell
py -3 scripts/setup_env.py
py -3 scripts/extract_125_questions.py
py -3 scripts/run_demo.py --real
```

### 9.7 常见问题（FAQ）

- **DeepResearch 失败为什么不终止？** 它只是调研资料来源，失败时记 warning 并继续，保证 pipeline 不白屏。
- **为什么 References 不能由 LLM 直接写？** 防止伪造文献；references 只能从真实 EvidenceCards 中选择。
- **为什么 Results 不能写假 AUROC？** 未真实执行实验时任何具体指标都是造假，质量门与 schema 会拦截。
- **为什么用户反馈不能作为事实？** 反馈仅作修订偏好；要求造假/去引用/强行 validated 会被拒绝。
- **validation_status 为什么不是 validated？** 只有 `actual_execution=true` 且有真实结果才允许 validated；本系统默认 ready_for_validation。
- **什么是 context_pack？** 每次运行的上下文工程快照，用于答辩展示“系统喂给每个 Agent 的上下文”。
- **什么是 quality_gates？** 一组可解释的质量门，用于证明输出可信（证据落地/Results/Schema/模型合规/引用）。

## 9.10 前端演示：科研发现控制台（Science Exploration Console）

前端为 Streamlit 实现的“科研发现控制台”，深蓝实验室背景 + 白色玻璃卡片，
非普通白底表单、非 ChatBot。页面模块（8 步）：

1. Hero：系统状态（Qwen/DeepResearch/RAG/Questions）+ KPI；
2. Sidebar：System Status / Model Stack / Pipeline Switches / Demo Presets / Security Note；
3. Step 01 选择科学问题（搜索 + 领域过滤 + 大卡片，默认 pandemic）；
4. Step 02 上传资料与 RAG Index（Document→Chunk→Embedding→zvec→Rerank→EvidenceCard）；
5. Step 03 启动 Pipeline（Generate / Run Mock Demo）；
6. Step 04 多智能体工作流（Timeline + 关系网络图 + Agent 卡片 + trace）；
7. Step 05 Evidence Cards 证据墙（筛选 + 分布图 + 相关性直方图）；
8. Step 06 研究计划输出（6 Tab：Summary/Hypotheses/Plan/Reviewer/JSON/Trace）；
9. Step 07 人在回路反馈（快捷反馈 + Revise）；
10. Step 08 ResearchPlan Export Center（运行结果导出：report.md/json/html/pdf、evidence_cards、agent_trace、context_pack、quality_gates、run_summary）；
11. Footer。

### 启动命令

```powershell
# 启动后端 API（OpenAPI: http://localhost:8000/docs）
uvicorn app.api.main:app --reload --port 8000

# 启动前端（另开一个终端）
streamlit run app/ui/streamlit_app.py
```

### Mock 演示（无需 Key，PowerShell）

```powershell
$env:MOCK_LLM="true"; uvicorn app.api.main:app --reload --port 8000
# 另一个终端：
$env:MOCK_LLM="true"; streamlit run app/ui/streamlit_app.py; Remove-Item Env:\MOCK_LLM
```

> 前端默认在 Streamlit 进程内运行，以便实时刷新 Agent/千问调用进度且避免长 HTTP 读超时；设置 `FRONTEND_RUN_VIA_API=1` 时改走本地 FastAPI。
> 前端 API 基址可用 `FRONTEND_API_BASE_URL` 覆盖（默认 http://localhost:8000）。

### 真实模式前置

```powershell
py -3 scripts/setup_env.py
py -3 scripts/extract_125_questions.py
```

运行时文献索引无需预构建；启动 API/前端后，从本地文献库上传入口导入资料即可。

### 前端可选依赖降级

- `streamlit-antd-components` / `streamlit-extras` 不可用时，`components.py` 通过
  `HAS_SAC` / `HAS_EXTRAS` 标志自动降级为原生 Streamlit 组件，页面不崩溃；
- `streamlit-elements` 为可选增强，非主流程硬依赖。

### 答辩截图建议

- Hero + Sidebar（展示 Qwen/Bailian 与多智能体定位）；
- Step 04 Agent Timeline + 关系图；
- Step 05 Evidence Cards 证据墙；
- Step 06 Research Plan（Executive Summary / Research Plan Tab，适合放入 PPT）；
- Step 08 ResearchPlan Export Center（运行结果导出）。

### Key 安全

前端不读取/显示/上传任何 API Key；`/health` 与 `context_pack.json`、`agent_trace.json`、
`report.json` 均不含明文 Key；Key 仅存于本地 `.env`。

## 快速可用路径

**Mock 演示（无需 Key）：**

```powershell
py -3 scripts/extract_125_questions.py
$env:MOCK_LLM="true"; py -3 scripts/run_demo.py; Remove-Item Env:\MOCK_LLM
uvicorn app.api.main:app --reload --port 8000
streamlit run app/ui/streamlit_app.py
```

**真实模式（需本地 .env 配置 Key）：**

```powershell
py -3 scripts/setup_env.py
py -3 scripts/smoke_bailian.py --chat
py -3 scripts/smoke_bailian.py --embedding
py -3 scripts/run_demo.py --real
uvicorn app.api.main:app --reload --port 8000
streamlit run app/ui/streamlit_app.py
```

**诊断：**

```powershell
py -3 scripts/doctor.py
py -3 scripts/frontend_smoke.py
py -3 scripts/api_smoke.py
```

**前端区域（科研发现控制台）：** System Hero · First Run Wizard · Select Scientific Question ·
Data & RAG Workspace · AI Scientist Run Console · Agent Observatory · Evidence Wall ·
ResearchPlan Studio · Human Feedback Bench · ResearchPlan Export Center。

> **本项目不自动生成最终参赛 PDF/PPT 或演示视频。** 详见 `docs/USER_GUIDE.md`。

## 10. 项目范围说明

**SAGE125-AI-Scientist 交付的是 AI Scientist 应用原型，不是参赛材料自动生成器。**
系统输出的是标准化《科学假设与研究计划》及其证据链、Agent Trace、Context Pack、
Quality Gates 与运行结果文件。参赛最终 PDF/PPT 和可选演示视频需要团队**基于系统运行结果人工整理**，不属于本系统功能。

### 10.1 项目核心功能

1. 125 科学问题加载与选择；
2. 用户资料上传；
3. RAG/zvec 索引；
4. Open Literature 检索（arXiv/OpenAlex/Crossref）；
5. Qwen-Deep-Research 调研节点；
6. Evidence Cards；
7. 多智能体 Pipeline；
8. 科学假设生成；
9. 实验/研究计划设计；
10. 审稿人校验；
11. Schema 校验；
12. Quality Gates；
13. 人在回路反馈；
14. FastAPI；
15. 科研发现控制台（Streamlit）；
16. ResearchPlan 导出（当前运行结果）；
17. 可选 125 问题批量输出；
18. 真实百炼 smoke 联调；
19. 安全与真实性审计。

### 10.2 后续人工整理材料（非系统功能）

以下内容**不是**系统自动生成功能，由团队在项目完善后人工整理：
1. 参赛技术方案 PDF/PPT；
2. 20 页以内排版压缩；
3. 10 分钟演示视频；
4. API 调用截图；
5. 作品压缩包提交。

### 10.3 核心运行命令

```powershell
py -3 scripts/setup_env.py
py -3 scripts/extract_125_questions.py
$env:MOCK_LLM="true"; py -3 scripts/run_demo.py; Remove-Item Env:\MOCK_LLM
uvicorn app.api.main:app --reload --port 8000
streamlit run app/ui/streamlit_app.py
```

### 10.4 真实百炼联调（需本地 .env 配置 Key）

```powershell
py -3 scripts/smoke_bailian.py --chat
py -3 scripts/smoke_bailian.py --embedding
py -3 scripts/smoke_bailian.py --rerank
py -3 scripts/smoke_bailian.py --deepresearch
```

报告写入 `exports/smoke_bailian/smoke_report.{json,md}`（仅掩码 Key）。

### 10.5 可选：125 问题批量输出

```powershell
$env:MOCK_LLM="true"; py -3 scripts/run_batch_125.py --mock --max-questions 5; Remove-Item Env:\MOCK_LLM
# 真实小批量（默认不启用 DeepResearch，控制成本）
py -3 scripts/run_batch_125.py --real --max-questions 3 --no-deepresearch
```

输出的是每个问题的 ResearchPlan 运行结果（`exports/batch_125/`：batch_outputs_125.jsonl/csv、
batch_summary.md），**不是**参赛提交文档。

### 10.6 安全审计

```powershell
py -3 scripts/audit_project.py
```

检测：Key 泄露、非千问模型配置、OpenAI 官方 endpoint、伪造 DOI/指标、空引用却 ready、
DeepResearch 未标注需核验、README 是否被误写成参赛材料自动生成器等。报告写入 `exports/audit/`。

### 10.7 ResearchPlan 报告 PDF（运行结果）

`report.pdf` 是**当前运行**的《科学假设与研究计划》报告导出，不限制页数、不是参赛技术方案 PDF。
中文字体使用系统已安装字体（不分发字体文件）；WeasyPrint 不可用时用 ReportLab 内置 CID 字体兜底。

### 10.8 不要提交的内容

`.env` · API Key · `data/raw/uploads/` · 缓存 · `__pycache__/` · 大型临时 exports · 系统字体文件。

## 11. 禁止事项

- 禁止伪造 References（DOI / URL / 作者 / 期刊 / 论文）。
- 禁止伪造实验结果；在缺少真实实验时禁止写 `AUROC=0.92` 等数字。
- 禁止使用非千问生成模型（OpenAI / Claude / Gemini / DeepSeek / Kimi / GLM / MiniMax 等）。
- 禁止把 DeepResearch 输出直接当作最终报告（须经证据抽取与核验）。
- 禁止把 API Key 提交到仓库（`.env` 已在 `.gitignore` 中屏蔽）。
- 禁止把真实 API Key 粘贴到 Cursor 对话框、README、前端、日志或测试文件。

## 12. 目录结构

```
SAGE125-AI-Scientist/
  README.md
  requirements.txt
  .env / .env.example / .gitignore
  conftest.py
  data/{raw,processed,index,cache}/
  app/
    core/     配置、日志、数据模型、常量
    clients/  Qwen 聊天 / DeepResearch / 嵌入 / 重排 / 文献 API
    rag/      document_loader / chunker / zvec_store / retriever /
              evidence / indexing_service / library_manager / open_literature_retriever
    agents/   base / prompts / supervisor / question_parser / query_planner /
              deep_research_agent / evidence_extractor / hypothesis_generator /
              experiment_designer / scientific_reviewer / report_writer / schema_validator
    workflow/ state / mock_outputs / context_builder / quality_gates /
              artifacts / pipeline
    api/      FastAPI 入口与路由（health/questions/ingest/library/runs/feedback/export）
    ui/       Streamlit 科研发现控制台：theme / style.css / charts /
              components / api_client / streamlit_app / assets
    exporters/ markdown / html(Jinja2) / pdf(WeasyPrint→ReportLab) +
               templates(research_plan/batch_summary.html.j2, print.css)
  scripts/    setup_env / extract_125_questions / build_rag_index / run_demo /
              smoke_bailian / run_batch_125 / audit_project / capture_demo_state
  docs/       LIMITATIONS_AND_RISK
  tests/      config / schema / pipeline_mock / no_fake_references /
              extract_questions / document_loader / chunker /
              vector_store_mock / evidence_cards / retriever_mock /
              open_literature_retriever
```

## 13. 使用模式说明

系统严格区分三种运行模式：

### 1）Mock 模式（默认，演示用）

- 不调用真实 Qwen；所有 Agent 输出使用 `app/workflow/mock_outputs.py` 的**领域相关**内容；
- 输出标记 `mock_for_testing`，`validation_status` 不得 `validated`，`Results` 为 pending；
- `llm_call_audit.json` 中 `provider=mock`，`qwen_call_count=0`；
- 不代表真实科研结论，仅用于演示 UI 与流程。

### 2）Real 模式（真实调用）

- 调用 Qwen / 百炼，需要在本地 `.env` 配置 `DASHSCOPE_API_KEY` 与 `WORKSPACE_ID`；
- **未配置时直接报清晰错误，绝不静默降级为 mock**；
- DeepResearch 可跳过（会记 warning），rerank 失败可 fallback（会标记）；
- 运行后可在 Developer Diagnostics 查看脱敏调用审计，证明真实调用；**不显示 API Key**。

### 3）Offline Latest Run 模式（历史结果浏览）

- 只查看历史 run，不调用任何模型；
- 页面显示“历史报告对应问题 + QID + Run ID”，并在渲染前同步下拉框、详情卡和运行状态，避免串线。

## 14. 前端如何显示模型与运行进度

点击运行后，主界面会在现有深色控制台中显示阶段、百分比和友好模型名，例如
“正在连接千问 3.7 Max”“正在等待响应”“正在接收响应”。服务地址、request_id、
原始内部字段和任何 API Key 不会进入进度卡；详细调用审计仍只出现在默认折叠的
「Developer Diagnostics · 开发者诊断」面板。

真实模式启动时先执行约 20 秒的轻量连通性探测。若本机网络无法完成阿里云 TLS
连接，会立即给出 VPN/防火墙/代理提示，不再进行 120 秒 × 多次的静默重试。
JSON Agent 使用流式响应并显式关闭思考模式；`qwen3.7-max` 不发送其不支持的
`response_format`，而是从普通流式文本中安全解析 JSON。

## 15. 如何确认真的调用了 Qwen

系统为每次运行保存脱敏调用审计 `exports/{run_id}/llm_call_audit.json`（含 provider、
model_alias、request_id 掩码、token usage、status、mock/real、fallback 原因），
并提供以下验证手段：

```powershell
# 单能力连通性（真实 Key）：
py -3 scripts/smoke_bailian.py --chat
py -3 scripts/smoke_bailian.py --embedding

# 最小真实链路验证：确认 qwen_call_count>0 且 mock_call_count==0，且报告属于 Q001
py -3 scripts/check_real_qwen_invocation.py --question-id Q001 --no-deepresearch
```

也可通过 API：`GET /runs/{run_id}/llm-calls` 获取脱敏调用摘要与明细。

## 16. 常见问题（FAQ）

- **选题和报告不一致怎么办？** 系统以选中问题为唯一权威来源；若报告 `question_id` 与所选不符，
  前端会**阻断展示**并提示重新运行或切换到对应历史 run。切换问题会自动清空旧 run，不自动加载历史结果。
- **为什么 Mock 模式不会调用 Qwen？** Mock 模式下 `MOCK_LLM=true`，各 Agent 走 `build_mock`，
  审计记录 `provider=mock`，`qwen_call_count=0`。
- **为什么 Real 模式失败不会自动降级 mock？** 为保证结果可信，真实调用失败会直接报错并写
  `status=failed`，绝不伪装成功或静默使用 mock。
- **为什么不在主界面展示模型名？** 见第 14 节；模型代号仅在 Developer Diagnostics 展示。
- **DuplicateElementKey 如何防止？** 所有 widget key 统一经 `app/ui/key_factory.make_widget_key`
  生成（拼接 namespace/run_id/section/filename/index），杜绝 `key="dl_0"` 这类弱 key。
- **为什么 Results 是 pending？** 未执行真实实验时，禁止编造量化指标，`Results` 只能标注待验证。
- **为什么 References 必须来自 EvidenceCards？** 所有事实必须可追溯到证据；无证据支撑的内容
  只能作为 knowledge gap 或 pending，References 只允许引用已检索到的 EvidenceCard。
- **Evidence Wall 中每张卡都是正式参考文献吗？** 不是。Evidence Wall 同时展示检索候选与报告引用，
  只有带“报告引用”标记的条目进入当前 ResearchPlan。OpenAlex/Crossref 标题属于元数据候选，
  不能替代原文证据；点击规范化 DOI/arXiv/OpenAlex 链接后仍需人工核验内容与相关性。
