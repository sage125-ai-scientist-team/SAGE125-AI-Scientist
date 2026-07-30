# T04 07/27 RAG 只读审计

## 基线与范围

- 分支：`t04/a-rag-contract`
- 正式基线：`450551f1b7d4dc4a714cf499cd063b8044301f16`
- 只读相关测试：35 passed
- 未读取 `.env`，未访问网络，未创建索引或处理后数据。

正式基线就是 `...1f16`，不存在 commit 冲突。审计时工作树为空。

## 路径分裂：代码层已复现

正式写入和实际查询已经指向用户文献库，但 Supervisor 的启用判断仍使用旧目录：

- `app/rag/library_manager.py:29-33` 定义
  `data/index/user_library/zvec`。
- `LibraryManager.__init__` 在 `app/rag/library_manager.py:121-138`
  采用该目录或显式注入目录。
- `LibraryManager._index_record` 在
  `app/rag/library_manager.py:431-464` 将相同目录传给 `IndexingService`。
- `app/workflow/pipeline.py:_gather_real_evidence` 在
  `app/workflow/pipeline.py:134-149` 从 `USER_LIBRARY_ZVEC_DIR` 建立检索器，
  并使用 `source_role=user_literature` 与 `source_scope=user_upload`。
- `SupervisorAgent.run` 在 `app/agents/supervisor.py:56-60`
  仍检查 `Path(settings.data_dir) / "index" / "zvec"`。
- `run_real_preflight` 已检查新目录，见
  `app/workflow/preflight.py:16-17,82-87`。

路径分裂由代码证据稳定复现。审计时两套物理目录均不存在，所以“已有真实
文献但检索不到”的数据态未复现。仅新索引存在时 Supervisor 会关闭 Local
RAG；仅旧索引存在时 Supervisor 会放行，但 Pipeline 随后查询空的新索引。

## renamed booklet：仅入口识别缺口已复现

- 题源保留名定义在 `app/rag/library_manager.py:36`。
- `_safe_filename` 仅按精确文件名拒绝，见
  `app/rag/library_manager.py:52-69`。
- `_validate_content` 仅做类型和 PDF 魔数校验，见
  `app/rag/library_manager.py:72-80`。
- 入库 metadata 被设为 `source_role=user_literature` 和
  `is_user_upload=True`，见 `app/rag/library_manager.py:447-462`。
- `LocalRAGRetriever.retrieve` 优先依据 `is_user_upload` 决定来源类型，
  再检查 booklet 名称，见 `app/rag/retriever.py:140-149`。
- 质量门依赖来源字段及 `sjtu-booklet.pdf` 字符串，见
  `app/workflow/quality_gates.py:51-61,86-88,232-235`。

内存验证中，`renamed-booklet.pdf` 和最小 PDF 魔数通过入口校验。这只证明
入口无法根据 provenance 或内容身份识别重命名题源。仓库当时不存在真实
`sjtu-booklet.pdf`，未执行真实 booklet 的加载、切分、索引和检索。因此
“真实 booklet 端到端污染”明确为**未复现**。

## 检索结果字段审计

- `SearchResult` 只有 `chunk_id/score/text/metadata`，见
  `app/rag/zvec_store.py:38-48`。
- Loader 生成 `source_path/source_name/file_type/doc_id/is_user_upload/page`，
  见 `app/rag/document_loader.py:51-70,74-110`。
- Chunker 增加 `chunk_index/char_start/char_end/source_hash`，见
  `app/rag/chunker.py:191-238`。
- LibraryManager 增加 `library_document_id/content_sha256/source_role`，见
  `app/rag/library_manager.py:447-456`。
- `chunk_to_evidence_card` 在 `app/rag/evidence.py:73-145` 将 page、path、
  role 和 chunk ID 拼进 `reliability_note`，但未结构化保留 document ID、
  content hash、字符区间或 section。
- `_evidence_catalog` 只保留
  `id/title/source_type/doi/url/year/relevance_score`，见
  `app/workflow/pipeline.py:175-199`。
- `ContextBuilder.build_evidence_pack` 保留 quote，但截断为 300 字，见
  `app/workflow/context_builder.py:56-81`。

分数语义也不统一：zvec 在 `app/rag/zvec_store.py:125-136,362` 将 cosine
distance 转为 0–1 similarity；rerank 在
`app/clients/rerank_client.py:176-187` 只把服务返回值解析为 float，没有
范围保证；EvidenceCard 转换又在 `app/rag/evidence.py:114-115` 将二者夹取
到同一 0–1 字段。审计不能证明所有原始正式分数同尺度。

## 兼容代码与测试

`scripts/build_rag_index.py` 默认扫描 `data/raw` 并写 `data/index/zvec`，
见 `scripts/build_rag_index.py:51-72,99-121,142-190`。README 将其定义为
兼容/诊断索引，并声明正式运行时不读取，见 `README.md:169,183`。

审计执行文献库、retriever、evidence、loader、chunker、文档约束和内存
向量库的 35 个离线测试，全部通过。未运行会写
`data/index/zvec_capabilities.json` 的 capability 测试，见
`app/rag/zvec_store.py:78-121`；也未运行可能生成
`data/processed/questions_125.json` 的问题抽取测试。

## 07/28 红灯方向

1. Supervisor 必须从唯一 `IndexConfig.vector_index_dir` 判断可用性。
2. renamed booklet 必须由 registry/provenance 与内容 SHA-256 识别；文件名
   仅作辅助。
3. 检索结果必须结构化保留 document ID、page/section、chunk、字符区间和
   content hash，不得只塞入说明字符串。
