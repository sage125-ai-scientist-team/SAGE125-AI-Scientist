# SAGE125 AI Scientist · 用户指南

> 本指南说明如何启动与使用 **AI Scientist 应用本体**。
> 本项目**不自动生成**最终参赛 PDF/PPT 或演示视频；那些由团队基于系统运行结果人工整理。

## 一、系统能做什么

选择《125 Questions》中的一个科学问题，系统通过 Qwen/百炼、多智能体、RAG、
DeepResearch 与证据校验，生成可验证《科学假设与研究计划》，并展示证据链、
Agent 追踪、上下文包与质量门；支持人在回路反馈与运行结果导出。

## 二、Mock 模式（无需 Key，推荐先跑通）

```powershell
py -3 scripts/extract_125_questions.py
$env:MOCK_LLM="true"; py -3 scripts/run_demo.py; Remove-Item Env:\MOCK_LLM
uvicorn app.api.main:app --reload --port 8000
streamlit run app/ui/streamlit_app.py
```

Mock 模式下所有结果标记 `mock_for_testing`，Results 为 pending，仅用于界面演示，
不代表真实科研结论。

## 三、Real 模式（需本地 .env 配置百炼 Key）

```powershell
py -3 scripts/setup_env.py
py -3 scripts/smoke_bailian.py --chat
py -3 scripts/smoke_bailian.py --embedding
py -3 scripts/run_demo.py --real
uvicorn app.api.main:app --reload --port 8000
streamlit run app/ui/streamlit_app.py
```

API Key 只允许配置在本地 `.env`；前端不会读取、显示或上传你的 Key。
运行时文献索引无需预构建；启动 API/前端后，从本地文献库上传入口导入资料即可。`scripts/build_rag_index.py` 仅保留用于兼容和诊断，其 `data/index/zvec/` 产物不会进入运行时证据检索。

## 四、本地文献库

### 保存与复用

- `sjtu-booklet.pdf` 只提供 125 个问题及题目背景，**不会作为本地文献证据**；
- 只有你主动上传的 PDF/TXT/MD/CSV 会进入独立的本地文献库；
- 上传成功后资料会永久保存在本机，重启应用或切换问题不会清空；
- 文献库跨所有科学问题复用，同一内容即使文件名不同也只保存、索引一次。

### 默认配额

- 单文件：25 MiB；
- 单批：最多 10 个文件、合计 100 MiB；
- 原文库：最多 2 GiB 或 500 个文件；
- 向量索引：最多 4 GiB；
- 磁盘安全余量：至少保留 `max(5 GiB, 磁盘容量 5%)`。

达到任一配额时，本次导入会被拒绝，不应留下半写入文件。系统状态页会显示文件数、原文/索引占用、chunk 数、配额和磁盘余量。

### 删除资料

在文献库管理区域选择资料并确认删除，或调用：

```text
DELETE /library/documents/{document_id}
```

删除会清理原始上传、活动向量、chunk 清单和文献库记录。此前生成的 `exports/{run_id}/` 是历史快照，可能仍含引用片段；敏感资料需同时删除相关运行导出。

### 隐私提示

- 原始文件保存在本机，不会上传到 arXiv、OpenAlex 或 Crossref；
- 使用真实 `text-embedding-v4` 时，系统会把切分后的文本片段发送到阿里云百炼 embedding 接口；真实运行还可能把检索到的相关片段交给 Qwen 智能体分析；
- 不允许资料离开本机时，请勿使用真实嵌入/真实运行；可先脱敏，或仅使用明确标记为测试用途的 mock embedding；
- 上传目录、索引、缓存、API Key 与包含敏感片段的运行导出都不应提交到版本库或对外分享。

## 五、诊断与可用性检查

```powershell
py -3 scripts/doctor.py           # 一条命令判断系统能否跑
py -3 scripts/api_smoke.py        # API 可启动性
py -3 scripts/frontend_smoke.py   # 前端可启动性
```

## 六、前端使用（科研发现控制台）

打开前端后，页面分为 10 个区域：
1. System Hero（系统状态与模式徽标）；
2. First Run Wizard（首次运行向导，逐项检查并给修复命令）；
3. Select Scientific Question（搜索/领域过滤/大卡片）；
4. Data & RAG Workspace（上传资料并构建索引）；
5. AI Scientist Run Console（Generate / Run Mock Demo / Load Latest Run / Clear）；
6. Agent Observatory（时间线 + 关系图 + 追踪表）；
7. Evidence Wall（证据墙，明确区分“检索候选/报告引用”，合法 DOI/arXiv/OpenAlex 标识可点击查看）；
8. ResearchPlan Studio（始终显示报告对应 QID、问题正文与 Run ID；References 提供安全规范化外链）；
9. Human Feedback Bench（反馈迭代）；
10. ResearchPlan Export Center（运行结果导出）。

## 七、可选：125 问题批量输出

```powershell
$env:MOCK_LLM="true"; py -3 scripts/run_batch_125.py --mock --max-questions 5; Remove-Item Env:\MOCK_LLM
```

输出为每题的 ResearchPlan 运行结果摘要，不是参赛提交文档。

## 八、不属于系统功能的内容

以下由团队后续**人工整理**，系统不自动生成：
- 参赛技术方案 PDF/PPT；
- 20 页以内排版压缩；
- 10 分钟演示视频；
- API 调用截图；
- 作品压缩包提交。
