# T04 IndexConfig 与检索契约 RFC

状态：Draft，面向 Draft PR-A
契约版本：1.0

## 当前问题

Supervisor 在 `app/agents/supervisor.py:56-60` 检查 `data/index/zvec`；
LibraryManager 在 `app/rag/library_manager.py:29-33,121-138` 写入
`data/index/user_library/zvec`；Pipeline 在
`app/workflow/pipeline.py:134-149` 查询后者。检索 metadata 原本含 page、
document ID、hash 和字符区间，但 `app/rag/evidence.py:73-145` 未结构化
保留。booklet 隔离也主要依赖文件名和字符串检查。

## 目标

- 一个可序列化 `IndexConfig` 表达正式索引布局。
- 所有路径从一个 `data_root` 派生。
- 将语义 `SourceType` 与操作来源 `SourceRole` 分成两个正交维度。
- `RetrievalHit`/`SourceLocator` 无损传递 quote 与结构化定位。
- 为迁移、回滚和 T01 adapter 提供稳定边界。

## 非目标

- 本轮不修改 Supervisor、Pipeline、现有 RAG 实现或公共 `EvidenceCard`。
- 不迁移、创建或重建实际索引。
- 不实现完整 SourcePolicy、OCR、论文识别或 DOI 解析。
- 初始 gold set 不宣称真实论文相关性。

## IndexConfig 契约

定义于 `app/contracts/rag.py`。输入为 `data_root` 和 `schema_version`；派生并
序列化：

- `index_root`
- `user_library_root`
- `vector_index_dir`
- `chunks_manifest_path`
- `migration_staging_dir`
- `backup_dir`
- `lock_path`
- `config_version`

默认根为相对路径 `data`，运行环境可注入 Windows/Linux 路径。禁止空路径、
`.`、`..` 穿越和未知字段。正式调用方不得另行拼接索引路径。

## 唯一索引路径

活动用户文献索引为：

```text
<data_root>/index/user_library/zvec
```

配套 manifest 为：

```text
<data_root>/index/user_library/chunks.jsonl
```

`<data_root>/index/zvec` 只是历史兼容/诊断路径，不得决定 Local RAG 可用性。

## source_type 与 source_role 契约

`SourceType` 表达内容语义：

- `paper`
- `booklet`
- `web`
- `dataset`
- `unknown`

`SourceRole` 表达来源角色：

- `user_upload`
- `question_source`
- `external_retrieval`
- `system_fixture`

上传动作不能建立 `paper` 语义；未知用户资料应为
`source_type=unknown, source_role=user_upload`。初始 gold fixture 使用
`source_role=system_fixture`。治理顺序是 provenance/source registry、完整
内容 SHA-256、受控 metadata，最后才是辅助性的文件名拒绝。

## RetrievalHit 与 SourceLocator

`SourceLocator` 包含 `document_id/source_id`、`page`、`section`、`chunk_id`、
`char_start`、`char_end`。PDF page 必须为正整数；TXT/MD/CSV 可无 page，
但必须有 section、chunk ID 或字符区间。字符区间成对出现且 end 大于 start。
不得伪造页码。

`RetrievalHit` 包含 `chunk_id`、`quoted_text`、`retrieval_score`、
`score_kind`、`source_type`、`source_role`、`source_locator`、
`content_hash`、`title`、`doi`、`url` 和 `metadata`。quote/title 非空，
score 必须是有限 float，hash 为完整 SHA-256，locator chunk ID 与顶层一致，
DOI/URL 做低成本格式校验。

`score_kind` 至少包括：

- `vector_similarity`
- `vector_distance`
- `rerank_score`

现有 zvec 路径在 `app/rag/zvec_store.py:125-136,362` 将 cosine distance
转换并夹取成 0–1 similarity；但 rerank 客户端在
`app/clients/rerank_client.py:176-187` 只解析为 float，未证明 API 原始分数
始终处于 0–1。随后 `app/rag/evidence.py:114-115` 的强制夹取还会丢失原始
尺度。因此 T04 不对所有 score 做统一 0–1 限制。不同 `score_kind` 的值
不得直接排序、阈值比较或聚合；比较前必须采用同 kind 或显式、版本化的
校准函数。

## Supervisor 最小适配计划

07/29 仅：

1. 构造或注入同一 `IndexConfig`。
2. 用 `vector_index_dir` 和 `chunks_manifest_path` 判断活动索引。
3. 删除 Supervisor 内的 `index/zvec` 拼接。
4. 不改变其他调度、模型或 trace。

本轮不得修改该非 owner 文件。

## 迁移阶段

1. 只读发现旧、新路径及版本。
2. 验证 manifest、向量维度、hash、数量和磁盘空间。
3. 在 `migration_staging_dir` 生成候选索引。
4. 运行离线 gold set 和 quote/locator 抽样核验。
5. 将被替换活动索引保存到 `backup_dir`。
6. 持有 `lock_path` 后做同卷原子切换。
7. 观察通过后才按显式策略清理备份。

旧索引中的来源必须重新通过 registry/hash policy；不得自动把 booklet 带入。

## 兼容警告

- `scripts/build_rag_index.py` 仍生成可能含 booklet 的旧索引。
- `IndexingService`、`ZvecVectorStore` 和 `get_vector_store` 仍有旧默认路径。
- 历史格式只能显式用于诊断，不得被正式运行时隐式选择。
- schema/config version 不匹配时必须报错或显式迁移，不得静默降级。

## 回滚策略

切换前同批次备份活动向量目录、chunks manifest 和配置清单；回滚和切换都
必须持有同一 lock，并以完整目录为单位，禁止混搭新旧 zvec 与 manifest。
回滚后重新验证数量、hash 和抽样 locator。失败路径不得自动删除备份。

## 失败处理

- 路径分裂、未知版本、manifest 损坏：停止并报告，不猜测。
- hash/文档数/chunk 数不一致：不得切换。
- lock 冲突：返回可诊断错误，不并行迁移。
- 空间不足：写暂存区前失败。
- 中断：活动索引保持不变，暂存区留待审计或显式清理。
- booklet provenance 不确定：隔离为不可用于 evidence，不标成 paper。

## T01 适配边界

T04 输出 `RetrievalHit`。T01 adapter 必须保留逐字 quote、结构化 locator、
content hash、document/source ID、source type/role、score 及 score kind；
不得把 locator 重新编码进自由文本、伪造 page，或因 `user_upload` 角色
将 `unknown` 改为 `paper`。本轮不修改
`app/core/schemas.py`。最终 adapter 位置需由对应 owner/队长确认。

## 安全与不提交目录

不得提交 `data/index/**`、`data/cache/**`、`data/processed/**`、迁移暂存/
备份/lock、上传原文、敏感 manifest、`.env` 或凭据。测试只使用系统临时
目录、内存对象和小型确定性 fixture，不访问网络。

## 已知限制

- 尚未定义生产 source registry 的持久化格式。
- 未定义 OCR、TXT/MD section 抽取和 CSV 行列 locator。
- 20-query 集只是 `contract_fixture`，annotation 为 provisional。
- 仓库缺少明确 T01 contract；最终 adapter 需跨 owner 确认。
- 历史索引的废弃和保留周期仍需产品决策。

## 07/29 Wave A 契约补充

### 配置来源与优先级

`IndexConfig.resolve()` 是配置解析边界，优先级固定为：

```text
environment > supplied config > model default
```

环境变量名称为 `SAGE_RAG_DATA_ROOT` 和 `SAGE_RAG_SCHEMA_VERSION`。空环境变量不覆盖
显式配置。`LibraryManager` 默认通过这一入口解析项目 `data` 根目录；调用方仍可注入
`IndexConfig`，测试和旧调用方也可显式传入 `index_dir`。

当前 `LibraryManager` 的历史常量曾将用户索引硬编码为
`PROJECT_ROOT/data/index/user_library/zvec`，并在读取 chunk 清单时再次拼接
`chunks.jsonl`。最小接入后，默认向量目录和 chunk 清单分别来自
`IndexConfig.vector_index_dir` 与 `IndexConfig.chunks_manifest_path`。上传原文目录和
library manifest 不属于本轮 IndexConfig 索引布局，保持现状。

### 索引健康状态

`IndexHealth` 只定义可诊断状态，不在本轮探测磁盘或改变索引：

- `READY`：活动索引及其契约完整可用；
- `DEGRADED`：索引可读，但存在可报告的局部问题；
- `MISSING`：活动索引不存在；
- `MIGRATION_REQUIRED`：索引存在，但布局或 schema version 不兼容。

调用方不得把 `MISSING` 或 `MIGRATION_REQUIRED` 静默降级为 `READY`。

### migration dry-run

`MigrationDryRun` 是只读、可序列化的迁移提案，字段固定为 `source`、`target`、
`checksum`、`rollback_available` 和恒为 `true` 的 `dry_run`。`checksum` 是完整
SHA-256，且 source 与 target 必须不同。构造、校验或序列化该模型均不得创建目录、
复制索引、取得迁移锁或执行切换；真实迁移命令明确不在本轮范围。

### renamed booklet 红灯

红灯使用现有 `LibraryManager.ingest_files` 行为：以改名后的 PDF、持久化 registry
记录和内容 SHA-256 为输入，并捕获提交给索引服务的 metadata。旧实现只写
`source_role=user_literature` 且不保留 `source_type=booklet`，因此以断言失败稳定暴露
booklet 可能在检索端默认成为 paper evidence 的缺口。测试不要求、也不调用
`classify_source` 方法。

## Migration command

可执行入口为：

```text
python scripts/migrate_rag_index.py [--data-root PATH]
```

默认只执行 dry-run：检查旧布局 `index/zvec` 与 `index/chunks.jsonl`、拒绝目标
`index/user_library` 冲突、逐行解析 manifest，并校验其中出现的 `source_hash` 和
`content_sha256`。命令计算向量目录与 manifest 的联合 SHA-256，但不创建 staging、
backup 或 lock。

显式迁移：

```text
python scripts/migrate_rag_index.py --apply --expected-checksum SHA256
```

执行顺序为：取得 migration lock、在锁内重新验证源、复制到 staging、验证 staging
checksum、将旧布局移入 backup，最后切换到 `IndexConfig.vector_index_dir` 和
`chunks_manifest_path`。目标、staging、backup 或 lock 已存在均视为冲突，不做覆盖。

显式回滚：

```text
python scripts/migrate_rag_index.py --rollback
```

回滚要求 backup 及 migration record 完整、旧路径为空、迁移后的目标仍与迁移
checksum 一致。目标被修改后拒绝回滚，避免以旧备份覆盖未知新数据。成功回滚后恢复
旧 `index/zvec` 与 `index/chunks.jsonl`，并清除本次 backup。
